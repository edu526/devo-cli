"""CodeArtifact authentication — boto3 get_authorization_token + tool config writer."""

import base64
import configparser
import json as _json
import logging
import re as _re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import boto3

logger = logging.getLogger(__name__)

# ponytail: 12h is the max boto3 allows; shorter durations are pointless for dev workflows
_TOKEN_DURATION = 43200


def _token_registry_path() -> Path:
    # ponytail: persist login metadata so the UI can show expiration without re-parsing
    # the JWT from ~/.npmrc (which is URL-encoded by `aws codeartifact login` and may
    # also have been written by an external tool that strips `exp`).
    return Path.home() / ".devo" / "registry-tokens.json"


def _load_domains_from_config() -> list[dict[str, Any]]:
    from cli_tool.core.utils.config_manager import get_config_value

    return get_config_value("codeartifact.domains", [])


def _resolve_profile(domain_cfg: dict[str, Any]) -> Optional[str]:
    """Find a valid SSO profile for a domain config entry.

    If domain_cfg has `profile`, use it directly (validated via STS).
    Otherwise iterate all SSO profiles matching the domain's account_id.
    Returns the first profile whose credentials are valid.
    """
    # ponytail: direct profile assignment, no iteration needed
    if domain_cfg.get("profile"):
        return domain_cfg["profile"]

    target_account = domain_cfg.get("account_id") or _get_global_account_id()
    if not target_account:
        return None

    from cli_tool.commands.aws_login.core.config import list_aws_profiles
    from cli_tool.commands.aws_login.core.credentials import verify_credentials

    try:
        profiles = list_aws_profiles()
    except Exception:
        return None

    for name, src in profiles:
        if src not in ("sso", "both"):
            continue
        identity = verify_credentials(name)
        if identity and identity.get("account") == target_account:
            return name

    return None


def _get_global_account_id() -> str:
    from cli_tool.core.utils.config_manager import get_config_value

    return get_config_value("codeartifact.account_id", "")


def _region_for(domain_cfg: dict[str, Any]) -> str:
    from cli_tool.core.utils.config_manager import get_config_value

    return domain_cfg.get("region") or get_config_value("codeartifact.region", "us-east-1")


def _account_id_for(domain_cfg: dict[str, Any]) -> str:
    return domain_cfg.get("account_id") or _get_global_account_id()


def get_domains() -> list[dict[str, Any]]:
    """Return configured domains enriched with resolved account_id and region."""
    domains = _load_domains_from_config()
    result: list[dict[str, Any]] = []
    for d in domains:
        result.append(
            {
                "domain": d["domain"],
                "repository": d["repository"],
                "namespace": d.get("namespace", ""),
                "account_id": _account_id_for(d),
                "profile": d.get("profile", ""),
                "region": _region_for(d),
            }
        )
    return result


def _get_token(domain: str, account_id: str, region: str, profile: str) -> tuple[str, str]:
    """Call boto3 get_authorization_token. Returns (token, iso8601_expiration)."""
    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client("codeartifact")
    resp = client.get_authorization_token(
        domain=domain,
        domainOwner=account_id,
        durationSeconds=_TOKEN_DURATION,
    )
    token = resp["authorizationToken"]
    expires = resp["expiration"]  # datetime
    return token, expires.isoformat()


def _registry_url(domain: str, account_id: str, region: str, repository: str, tool: str) -> str:
    """Build the registry URL for a given tool."""
    base = f"{domain}-{account_id}.d.codeartifact.{region}.amazonaws.com"
    if tool == "npm":
        return f"https://{base}/npm/{repository}/"
    return f"https://{base}/pypi/{repository}/"


def _write_npmrc(registry_url: str, token: str, namespace: str) -> None:
    """Write scoped npm registry config to ~/.npmrc."""
    npmrc = Path.home() / ".npmrc"
    scope = namespace.lstrip("@") if namespace.startswith("@") else namespace
    scope_line = f"@{scope}:registry={registry_url}"
    auth_token = f"//{registry_url.replace('https://', '')}:_authToken={token}"

    lines_to_add = [scope_line, auth_token]
    existing: dict[str, str] = {}
    if npmrc.exists():
        for line in npmrc.read_text().splitlines():
            line = line.strip()
            if "=" in line:
                key, _, _ = line.partition("=")
                existing[key.strip()] = line

    for line in lines_to_add:
        key = line.partition("=")[0].strip()
        existing[key] = line

    npmrc.write_text("\n".join(existing.values()) + "\n")
    logger.info("Wrote %d lines to %s", len(existing), npmrc)


def _write_pip_conf(registry_url: str, token: str) -> None:
    """Write pip index config to ~/.pip/pip.conf."""
    pip_dir = Path.home() / ".pip"
    pip_dir.mkdir(exist_ok=True)
    pip_conf = pip_dir / "pip.conf"

    config = configparser.ConfigParser()
    if pip_conf.exists():
        config.read(str(pip_conf))
    if "global" not in config:
        config["global"] = {}

    index_url = registry_url.rstrip("/") + "/simple/"
    config["global"]["index-url"] = f"https://aws:{token}@{index_url.replace('https://', '')}"

    with open(pip_conf, "w") as f:
        config.write(f)
    logger.info("Wrote pip config to %s", pip_conf)


def _write_pypirc(registry_url: str, token: str) -> None:
    """Write twine upload config to ~/.pypirc."""
    pypirc = Path.home() / ".pypirc"

    config = configparser.ConfigParser()
    if pypirc.exists():
        config.read(str(pypirc))
    if "distutils" not in config:
        config["distutils"] = {}
    config["distutils"]["index-servers"] = "codeartifact"

    if "codeartifact" not in config:
        config["codeartifact"] = {}
    config["codeartifact"]["repository"] = registry_url.rstrip("/") + "/"
    config["codeartifact"]["username"] = "aws"
    config["codeartifact"]["password"] = token

    with open(pypirc, "w") as f:
        config.write(f)
    logger.info("Wrote pypirc config to %s", pypirc)


_writers = {
    "npm": _write_npmrc,
    "pip": _write_pip_conf,
    "twine": _write_pypirc,
}

# ponytail: if the SSO access token has <5 min left, force boto3 to refresh it
# via the refresh token before we hit CodeArtifact — saves the user a round trip
# when they click Login on a stale profile
_SSO_REFRESH_THRESHOLD = 300


class SSOLoginRequired(Exception):
    """Raised when SSO session is dead and needs browser flow to recover.

    The router catches this, spawns `aws sso login` in background, publishes
    a WS event for the UI, and returns 202 so the user stays in their context.
    """

    def __init__(self, profile: str, message: str) -> None:
        super().__init__(message)
        self.profile = profile


def _ensure_sso_fresh(profile: str) -> None:
    """Validate the SSO session using boto3 itself and trigger a lazy refresh.

    Why boto3 (not the AWS CLI subprocess): the cached temp credentials in
    `~/.aws/credentials` (12h TTL) can be valid even when the underlying SSO
    access token is dead. The CLI subprocess happily uses the cached creds
    without checking the SSO token, so a probe via `verify_credentials`
    passes while the subsequent boto3 CodeArtifact call fails with a generic
    "Token has expired and refresh failed". Using boto3 to probe goes
    through the same SSO provider path the CodeArtifact call will use.
    """
    from datetime import datetime, timezone

    from cli_tool.commands.aws_login.core.config import get_profile_config

    cfg = get_profile_config(profile)
    if not cfg:
        # No profile config — let boto3 surface the real error
        _boto3_probe(profile)
        return

    sso_start_url = cfg.get("sso_start_url")
    if not sso_start_url:
        # Legacy / non-SSO profile — boto3 will use the configured credentials
        _boto3_probe(profile)
        return

    expires = _sso_token_expiration_from_cache(sso_start_url)
    if expires is None:
        # No SSO cache yet — let boto3 try; it will fail clearly
        _boto3_probe(profile)
        return

    seconds_left = (expires - datetime.now(timezone.utc)).total_seconds()
    if seconds_left > _SSO_REFRESH_THRESHOLD:
        # File says healthy; still probe to catch server-side dead refresh tokens
        _boto3_probe(profile)
        return

    logger.info("SSO token for %s has %.0fs left, forcing refresh", profile, seconds_left)
    _boto3_probe(profile)


def _sso_token_expiration_from_cache(sso_start_url: str):
    """Read the SSO access token expiration from ~/.aws/sso/cache/."""
    from cli_tool.commands.aws_login.core.credentials import get_sso_token_expiration

    return get_sso_token_expiration(sso_start_url)


def _boto3_probe(profile: str) -> None:
    """Use boto3 to do the real SSO check. Raises SSOLoginRequired on failure."""
    from botocore.exceptions import BotoCoreError, ProfileNotFound

    try:
        session = boto3.Session(profile_name=profile)
        # STS get-caller-identity forces boto3 to validate the SSO chain
        # (cached creds → access token → refresh token).
        session.client("sts").get_caller_identity()
    except BotoCoreError as exc:
        # boto3's SSO provider raises a variety of BotoCoreError subclasses
        # for SSO failures (SSOTokenLoadError, TokenRetrievalError, etc.).
        # Match by message text to be safe across versions.
        msg = str(exc)
        if any(s in msg for s in ("Token has expired", "refresh failed", "SSO", "sso")):
            raise SSOLoginRequired(profile, f"SSO session for '{profile}' expired: {exc}") from exc
        raise
    except Exception as exc:
        msg = str(exc)
        if any(s in msg for s in ("Token has expired", "refresh failed", "SSO", "sso")):
            raise SSOLoginRequired(profile, f"SSO session for '{profile}' expired: {exc}") from exc
        if isinstance(exc, ProfileNotFound):
            raise
        raise


def login(domain_cfg: dict[str, Any], tool: str, profile_override: str | None = None) -> dict[str, Any]:
    """Get a CodeArtifact token and write the tool config file.

    Returns {tool, registry_url, expires_at, profile_used}.
    Raises ValueError on missing config or auth failure.
    """
    domain = domain_cfg["domain"]
    repository = domain_cfg["repository"]
    namespace = domain_cfg.get("namespace", "")
    region = _region_for(domain_cfg)
    account_id = _account_id_for(domain_cfg)
    profile = profile_override or _resolve_profile(domain_cfg)

    if not account_id:
        raise ValueError(f"No account_id configured for domain '{domain}'")
    if not profile:
        raise ValueError(
            f"No valid SSO profile found for account {account_id}. " f"Log in via Profiles page first, or set 'profile' on the domain config."
        )

    # ponytail: refresh the upstream SSO token before boto3 fails noisily on it
    _ensure_sso_fresh(profile)

    token, expires_at = _get_token(domain, account_id, region, profile)
    registry_url = _registry_url(domain, account_id, region, repository, tool)
    writer = _writers.get(tool)
    if not writer:
        raise ValueError(f"Unsupported tool: {tool}. Use npm, pip, or twine.")

    if tool == "npm":
        _write_npmrc(registry_url, token, namespace)
    else:
        writer(registry_url, token)

    _save_token_metadata(domain, account_id, region, repository, tool, registry_url, expires_at, profile)

    return {
        "tool": tool,
        "registry_url": registry_url,
        "expires_at": expires_at,
        "profile_used": profile,
    }


def _save_token_metadata(
    domain: str,
    account_id: str,
    region: str,
    repository: str,
    tool: str,
    registry_url: str,
    expires_at: str,
    profile: str,
) -> None:
    """Persist login metadata so the UI can show expiration without re-parsing JWTs."""
    registry = _load_token_registry()
    registry[f"{domain}::{tool}"] = {
        "domain": domain,
        "account_id": account_id,
        "region": region,
        "repository": repository,
        "tool": tool,
        "registry_url": registry_url,
        "expires_at": expires_at,
        "profile_used": profile,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    path = _token_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(registry, indent=2))


def _load_token_registry() -> dict[str, Any]:
    path = _token_registry_path()
    if not path.exists():
        return {}
    try:
        return _json.loads(path.read_text())
    except Exception:
        return {}


# ── CRUD: domain config ──────────────────────────────────────────────────────

_REQUIRED_DOMAIN_FIELDS = ("domain", "repository")
_OPTIONAL_DOMAIN_FIELDS = ("namespace", "account_id", "profile", "region")


def create_domain(body: dict[str, Any]) -> dict[str, Any]:
    """Append a new domain entry to ~/.devo/config.json. Returns the enriched entry."""
    from cli_tool.core.utils.config_manager import load_config, save_config

    missing = [f for f in _REQUIRED_DOMAIN_FIELDS if not body.get(f)]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    config = load_config()
    domains = config.setdefault("codeartifact", {}).setdefault("domains", [])

    if any(d.get("domain") == body["domain"] for d in domains):
        raise ValueError(f"Domain '{body['domain']}' already exists")

    new_domain: dict[str, Any] = {"domain": body["domain"], "repository": body["repository"]}
    for field in _OPTIONAL_DOMAIN_FIELDS:
        if field in body and body[field]:
            new_domain[field] = body[field]

    domains.append(new_domain)
    save_config(config)
    logger.info("Created CodeArtifact domain '%s'", body["domain"])

    enriched = get_domains()
    return next(d for d in enriched if d["domain"] == body["domain"])


def update_domain(domain_name: str, body: dict[str, Any]) -> dict[str, Any]:
    """Patch an existing domain entry. Returns the enriched entry."""
    from cli_tool.core.utils.config_manager import load_config, save_config

    config = load_config()
    domains = config.setdefault("codeartifact", {}).setdefault("domains", [])

    for i, d in enumerate(domains):
        if d.get("domain") == domain_name:
            for field in _OPTIONAL_DOMAIN_FIELDS + ("repository", "namespace"):
                if field in body:
                    domains[i][field] = body[field] or ""
            save_config(config)
            logger.info("Updated CodeArtifact domain '%s'", domain_name)
            enriched = get_domains()
            return next(d for d in enriched if d["domain"] == domain_name)

    raise ValueError(f"Domain '{domain_name}' not found")


def delete_domain(domain_name: str) -> None:
    """Remove a domain entry from ~/.devo/config.json."""
    from cli_tool.core.utils.config_manager import load_config, save_config

    config = load_config()
    domains = config.setdefault("codeartifact", {}).setdefault("domains", [])

    for i, d in enumerate(domains):
        if d.get("domain") == domain_name:
            domains.pop(i)
            save_config(config)
            # ponytail: clear cached token metadata so the UI doesn't show stale "Connected"
            registry = _load_token_registry()
            for tool in ("npm", "pip", "twine"):
                registry.pop(f"{domain_name}::{tool}", None)
            if registry:
                _token_registry_path().write_text(_json.dumps(registry, indent=2))
            else:
                _token_registry_path().unlink(missing_ok=True)
            logger.info("Deleted CodeArtifact domain '%s'", domain_name)
            return

    raise ValueError(f"Domain '{domain_name}' not found")


# ── Token introspection (read ~/.npmrc / .pip/pip.conf / .pypirc) ────────────
#
# The login endpoint writes a token to the tool config file. On page reload we
# re-read it so the UI can show "logged in" without forcing the user to log in
# again. Expiration comes from the JWT `exp` claim (no signature validation —
# we only care about the timestamp, not trust).


_REGISTRY_URL_RE = _re.compile(r"^//?(.+)-(\d+)\.d\.codeartifact\.([^.]+)\.amazonaws\.com/(npm|pypi)/(.+?)/?$")


def _jwt_exp(token: str) -> str | None:
    from urllib.parse import unquote

    try:
        # Tokens in ~/.npmrc are URL-encoded (e.g. + → %2B, = → %3D)
        token = unquote(token.strip())
        payload_b64 = token.split(".", 2)[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        data = _json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = data.get("exp")
        if exp:
            return datetime.fromtimestamp(int(exp), tz=timezone.utc).isoformat()
    except Exception:
        return None
    return None


def _parse_npm_tokens() -> list[dict[str, Any]]:
    """Extract CodeArtifact tokens from ~/.npmrc."""
    npmrc = Path.home() / ".npmrc"
    if not npmrc.exists():
        return []

    seen: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []
    for line in npmrc.read_text().splitlines():
        if ":_authToken=" not in line or "codeartifact" not in line:
            continue
        url_part, _, token = line.partition(":_authToken=")
        m = _REGISTRY_URL_RE.match(url_part.strip())
        if not m:
            continue
        host, account_id, region, kind, repo = m.groups()
        # The host part is "domain-account_id" split on the LAST hyphen
        domain = host.rsplit(f"-{account_id}", 1)[0]
        key = (domain, repo)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "domain": domain,
                "repository": repo,
                "account_id": account_id,
                "region": region,
                "tool": "npm",
                "registry_url": f"https://{host}.d.codeartifact.{region}.amazonaws.com/{kind}/{repo}/",
                "expires_at": _jwt_exp(token.strip()),
            }
        )
    return results


def _parse_pip_tokens() -> list[dict[str, Any]]:
    """Extract CodeArtifact tokens from ~/.pip/pip.conf."""
    pip_conf = Path.home() / ".pip" / "pip.conf"
    if not pip_conf.exists():
        return []

    config = configparser.ConfigParser()
    config.read(str(pip_conf))
    index_url = config.get("global", "index-url", fallback="")
    if "codeartifact" not in index_url or "@" not in index_url:
        return []

    # Format: https://aws:{token}@{host}/pypi/{repo}/simple/
    m = _re.match(r"https://aws:([^@]+)@(.+)/pypi/([^/]+)/simple/?", index_url)
    if not m:
        return []
    token, host, repo = m.groups()
    host_m = _REGISTRY_URL_RE.match(f"//{host}/pypi/{repo}/")
    if not host_m:
        return []
    _, account_id, region, _, _ = host_m.groups()
    domain = host.rsplit(f"-{account_id}", 1)[0]
    return [
        {
            "domain": domain,
            "repository": repo,
            "account_id": account_id,
            "region": region,
            "tool": "pip",
            "registry_url": f"https://{host}/pypi/{repo}/",
            "expires_at": _jwt_exp(token.strip()),
        }
    ]


def _parse_twine_tokens() -> list[dict[str, Any]]:
    """Extract CodeArtifact tokens from ~/.pypirc."""
    pypirc = Path.home() / ".pypirc"
    if not pypirc.exists():
        return []

    config = configparser.ConfigParser()
    config.read(str(pypirc))
    if "codeartifact" not in config:
        return []

    repo_url = config.get("codeartifact", "repository", fallback="")
    token = config.get("codeartifact", "password", fallback="")
    if "codeartifact" not in repo_url or not token:
        return []

    # Format: https://{host}/pypi/{repo}/
    m = _re.match(r"https://(.+)/pypi/([^/]+)/?", repo_url)
    if not m:
        return []
    host, repo = m.groups()
    host_m = _REGISTRY_URL_RE.match(f"//{host}/pypi/{repo}/")
    if not host_m:
        return []
    _, account_id, region, _, _ = host_m.groups()
    domain = host.rsplit(f"-{account_id}", 1)[0]
    return [
        {
            "domain": domain,
            "repository": repo,
            "account_id": account_id,
            "region": region,
            "tool": "twine",
            "registry_url": repo_url,
            "expires_at": _jwt_exp(token.strip()),
        }
    ]


def list_active_tokens() -> list[dict[str, Any]]:
    """Return all active CodeArtifact tokens, deduped by (domain, tool).

    Source of truth is the sidecar's own token registry (written on each login).
    JWT parsing from config files is a fallback for tokens issued by external tools
    (e.g. `aws codeartifact login` from a terminal).
    """
    now = datetime.now(timezone.utc)
    registry = _load_token_registry()

    tokens: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in registry.values():
        expires = entry.get("expires_at")
        if expires:
            try:
                if datetime.fromisoformat(expires.replace("Z", "+00:00")) < now:
                    continue
            except Exception:
                pass
        tokens.append(
            {
                "domain": entry["domain"],
                "repository": entry["repository"],
                "account_id": entry["account_id"],
                "region": entry["region"],
                "tool": entry["tool"],
                "registry_url": entry["registry_url"],
                "expires_at": entry.get("expires_at"),
            }
        )
        seen.add((entry["domain"], entry["tool"]))

    # Fallback: parse JWTs from config files for tokens we didn't issue
    for t in _parse_npm_tokens() + _parse_pip_tokens() + _parse_twine_tokens():
        if (t["domain"], t["tool"]) not in seen:
            tokens.append(t)

    return tokens
