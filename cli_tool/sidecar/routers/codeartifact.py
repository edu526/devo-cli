"""CodeArtifact registry endpoints /api/v1/codeartifact."""

import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cli_tool.sidecar.deps import get_app_state, require_bearer
from cli_tool.sidecar.services.codeartifact_service import (
    SSOLoginRequired,
    _resolve_profile,
    create_domain,
    delete_domain,
    get_domains,
    list_active_tokens,
    login,
    update_domain,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/codeartifact", tags=["codeartifact"], dependencies=[Depends(require_bearer)])


@router.get("/domains")
def list_domains() -> list[dict[str, Any]]:
    return get_domains()


@router.post("/domains", status_code=status.HTTP_201_CREATED)
def create_domain_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """Add a new CodeArtifact domain to ~/.devo/config.json.

    Body: {domain, repository} required; {namespace, account_id, profile, region} optional.
    Returns 201 on success, 409 on duplicate domain, 422 on missing fields.
    """
    if not body.get("domain") or not body.get("repository"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required field(s): both 'domain' and 'repository' are required",
        )
    try:
        return create_domain(body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/domains/{domain}")
def update_domain_endpoint(domain: str, body: dict[str, Any]) -> dict[str, Any]:
    """Patch an existing domain entry. Returns the enriched entry.

    Body: any subset of {repository, namespace, account_id, profile, region}.
    Returns 200 on success, 404 if domain not found.
    """
    try:
        return update_domain(domain, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/domains/{domain}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain_endpoint(domain: str) -> None:
    """Remove a domain from ~/.devo/config.json. Returns 204, or 404 if not found."""
    try:
        delete_domain(domain)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/tokens")
def list_tokens() -> list[dict[str, Any]]:
    """Return all currently active CodeArtifact tokens, read from local config files.

    Reads ~/.npmrc, ~/.pip/pip.conf, and ~/.pypirc. Expiration is parsed from
    the JWT `exp` claim. Used by the UI to restore "logged in" state on page load.
    """
    return list_active_tokens()


def _do_sso_login_and_publish(hub, profile: str) -> None:
    """Run `aws sso login --profile {profile}` in background and publish WS events.

    The frontend listens for `sso.login.completed` to auto-retry the original
    CodeArtifact login that triggered this chain.
    """
    from cli_tool.sidecar.services.sso_service import run_sso_login_sync

    run_sso_login_sync(hub, profile, source="codeartifact")


@router.post("/login")
def login_endpoint(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """Authenticate with a CodeArtifact domain and configure the local tool.

    Body: {domain, tool} where tool is "npm", "pip", or "twine".
    Optional: {profile} to force a specific AWS profile.

    If the SSO session is dead, returns 202 with `{status: "sso_required"}` and
    spawns `aws sso login --profile X` in the background. The frontend listens
    to the `sso.login.completed` WS event and auto-retries.
    """
    domain_name = body.get("domain")
    tool = body.get("tool", "npm")
    profile = body.get("profile")

    if not domain_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing required field: domain")
    if tool not in ("npm", "pip", "twine"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported tool: {tool}. Use npm, pip, or twine.")

    domains = get_domains()
    domain_cfg = next((d for d in domains if d["domain"] == domain_name), None)
    if not domain_cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Domain '{domain_name}' not found in config")

    try:
        return login(domain_cfg, tool, profile_override=profile)
    except SSOLoginRequired as exc:
        # Chain: spawn browser flow in background, tell the frontend via WS.
        # The frontend stays in Registry and auto-retries when SSO completes.
        from fastapi.responses import JSONResponse

        hub = get_app_state(request).event_hub
        threading.Thread(
            target=_do_sso_login_and_publish,
            args=(hub, exc.profile),
            daemon=True,
        ).start()
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "sso_required",
                "profile": exc.profile,
                "message": str(exc),
                "domain": domain_name,
                "tool": tool,
            },
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        # Defense in depth: if a boto3 SSO error slips past _ensure_sso_fresh
        # (e.g. boto3 STS call works but CodeArtifact triggers a different
        # SSO check), chain it to a browser flow.
        msg = str(exc)
        if any(s in msg for s in ("Token has expired", "refresh failed", "SSO", "sso")):
            profile = body.get("profile") or _resolve_profile(domain_cfg)
            if profile:
                from fastapi.responses import JSONResponse

                hub = get_app_state(request).event_hub
                threading.Thread(
                    target=_do_sso_login_and_publish,
                    args=(hub, profile),
                    daemon=True,
                ).start()
                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "status": "sso_required",
                        "profile": profile,
                        "message": f"SSO session for '{profile}' expired: {msg}",
                        "domain": domain_name,
                        "tool": tool,
                    },
                )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=msg) from exc


@router.get("/domains/{domain}/packages")
def list_packages(domain: str) -> dict[str, Any]:
    """List packages and their latest versions in a domain's repository."""
    from cli_tool.commands.codeartifact.core.authenticator import CodeArtifactAuthenticator

    domains_cfg = get_domains()
    domain_cfg = next((d for d in domains_cfg if d["domain"] == domain), None)
    if not domain_cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Domain '{domain}' not found in config")

    profile = _resolve_profile(domain_cfg)
    if not profile:
        logger.warning("No SSO profile resolved for domain %s (account_id=%s)", domain, domain_cfg.get("account_id"))
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"No SSO profile found for account {domain_cfg.get('account_id')}. Run SSO login first.",
        )

    logger.info("Listing packages for %s/%s with profile=%s", domain, domain_cfg["repository"], profile)
    auth = CodeArtifactAuthenticator(domain_cfg["region"], [(domain_cfg["domain"], domain_cfg["repository"], domain_cfg["namespace"])])
    try:
        return auth.list_packages_with_versions(
            domain_cfg["domain"],
            domain_cfg["repository"],
            domain_cfg["namespace"],
            profile,
            domain_cfg["region"],
        )
    except Exception as exc:
        logger.exception("list_packages failed for %s", domain)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
