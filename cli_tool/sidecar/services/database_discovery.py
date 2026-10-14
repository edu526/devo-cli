"""List the RDS databases a profile can see, to pick one instead of typing it."""

import logging
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_CONFIG = Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2})
_DEFAULT_PORTS = {"postgres": 5432, "mysql": 3306, "mariadb": 3306}


def discover_databases(profile: Optional[str], region: str) -> dict[str, Any]:
    """RDS endpoints in `region` with `profile`'s credentials.

    Returns {"databases": [...], "error": str | None}. Each database:
    {"id", "host", "port", "engine", "kind"} where kind is "writer" /
    "reader" (cluster endpoints), "instance" or "global" (global database
    writer). Never raises: a profile without rds:Describe* permissions or
    with an expired login gets an error the form shows, and the host can
    still be typed.
    """
    try:
        rds = boto3.Session(profile_name=profile or None, region_name=region).client("rds", config=_CONFIG)
        clusters = _all(rds, "describe_db_clusters", "DBClusters")
        instances = _all(rds, "describe_db_instances", "DBInstances")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("AccessDenied", "AccessDeniedException", "UnauthorizedOperation"):
            return _failed(f"{profile or 'This profile'} can't list RDS databases (missing rds:Describe* permissions). Type the host instead.")
        return _failed(f"Couldn't list RDS databases: {e}")
    except BotoCoreError as e:
        logger.info("RDS discovery for %s in %s failed: %s", profile, region, e)
        return _failed(f"Couldn't list RDS databases with {profile or 'the default profile'}: {e}. Log in to AWS, or type the host.")

    found: list[dict[str, Any]] = []
    port_by_cluster_arn = {}
    for c in clusters:
        port = c.get("Port") or _default_port(c.get("Engine"))
        port_by_cluster_arn[c.get("DBClusterArn")] = port
        for kind, key in (("writer", "Endpoint"), ("reader", "ReaderEndpoint")):
            if c.get(key):
                found.append(_entry(c["DBClusterIdentifier"], c[key], port, c.get("Engine"), kind))
    for i in instances:
        endpoint = i.get("Endpoint") or {}
        if endpoint.get("Address"):
            found.append(_entry(i["DBInstanceIdentifier"], endpoint["Address"], endpoint.get("Port"), i.get("Engine"), "instance"))

    try:  # best effort: global databases are listed from any of their regions
        for g in _all(rds, "describe_global_clusters", "GlobalClusters"):
            if g.get("Endpoint"):
                members = [m.get("DBClusterArn") for m in g.get("GlobalClusterMembers", [])]
                port = next((port_by_cluster_arn[a] for a in members if a in port_by_cluster_arn), None)
                found.append(_entry(g["GlobalClusterIdentifier"], g["Endpoint"], port or _default_port(g.get("Engine")), g.get("Engine"), "global"))
    except (ClientError, BotoCoreError) as e:
        logger.info("Listing global databases failed: %s", e)

    return {"databases": sorted(found, key=lambda d: (d["id"], d["kind"])), "error": None}


def _all(client: Any, operation: str, key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in client.get_paginator(operation).paginate():
        items.extend(page.get(key, []))
    return items


def _default_port(engine: Optional[str]) -> Optional[int]:
    engine = (engine or "").lower()
    return next((port for name, port in _DEFAULT_PORTS.items() if name in engine), None)


def _entry(identifier: str, host: str, port: Optional[int], engine: Optional[str], kind: str) -> dict[str, Any]:
    return {"id": identifier, "host": host, "port": port, "engine": engine, "kind": kind}


def _failed(message: str) -> dict[str, Any]:
    return {"databases": [], "error": message}
