"""SSO login background service for the sidecar."""

import logging
import re
import subprocess
from typing import Optional

from cli_tool.commands.aws_login.core.credentials import verify_credentials
from cli_tool.sidecar.state import EventHub

logger = logging.getLogger(__name__)


def run_sso_login_sync(hub: EventHub, profile_name: str, source: str) -> bool:
    """Run `aws sso login` using Popen to capture stdout and emit WS events.
    
    Listens for device code URLs and emits `sso.login.url_ready` if found,
    so the UI can display a manual fallback if the browser fails to open.
    At the end, validates credentials and emits `sso.login.completed`.
    Returns True if the credentials are valid, False otherwise.
    """
    logger.info("Starting SSO login for profile '%s' (source=%s)", profile_name, source)
    hub.publish("sso.login.started", {"profile": profile_name, "source": source})

    cmd = ["aws", "sso", "login", "--profile", profile_name]
    
    process = None
    try:
        # bufsize=1 and text=True to read line-by-line as it's printed
        import os
        import platform
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            shell=platform.system() == "Windows"
        )
        
        url_found: Optional[str] = None
        code_found: Optional[str] = None
        emitted = False
        
        if process.stdout:
            # Iterating over process.stdout blocks until a line is available
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                logger.debug("aws sso login [%s]: %s", profile_name, line)
                
                # The AWS CLI might output an OIDC local-callback URL or a device code URL.
                # Local callback: "https://oidc.region.amazonaws.com/authorize?..."
                # Device code: "https://device.sso.region.amazonaws.com/"
                if "https://" in line and ("oidc." in line or "device.sso." in line):
                    words = line.split()
                    for w in words:
                        if w.startswith("https://"):
                            url_found = w
                            break
                
                # Match 8-character alphanumeric hyphenated code e.g. ABCD-1234
                code_match = re.search(r'\b([A-Z0-9]{4}-[A-Z0-9]{4})\b', line)
                if code_match:
                    code_found = code_match.group(1)
                
                # If we found an OIDC url, there is no code. Emit immediately.
                if url_found and "oidc." in url_found and not emitted:
                    hub.publish("sso.login.url_ready", {
                        "profile": profile_name,
                        "source": source,
                        "url": url_found,
                        "code": "",
                    })
                    emitted = True
                
                # If we found a device code URL, we need to wait for the code.
                if url_found and "device.sso." in url_found and code_found and not emitted:
                    hub.publish("sso.login.url_ready", {
                        "profile": profile_name,
                        "source": source,
                        "url": url_found,
                        "code": code_found,
                    })
                    emitted = True

            process.stdout.close()
            
        # Wait up to 120s for the user to complete the browser flow
        process.wait(timeout=120)
        
        if process.returncode == 0:
            if verify_credentials(profile_name):
                logger.info("SSO login successful for '%s'", profile_name)
                hub.publish("sso.login.completed", {"profile": profile_name, "source": source, "success": True})
                return True
            else:
                msg = f"Credential verification failed for '{profile_name}'"
                logger.error(msg)
                hub.publish("sso.login.completed", {"profile": profile_name, "source": source, "success": False, "error": msg})
                return False
        else:
            msg = f"SSO login failed for '{profile_name}' (exit {process.returncode})"
            logger.error(msg)
            hub.publish("sso.login.completed", {"profile": profile_name, "source": source, "success": False, "error": msg})
            return False
            
    except subprocess.TimeoutExpired:
        if process:
            process.kill()
        msg = "SSO login timed out after 120 seconds"
        logger.error(msg)
        hub.publish("sso.login.completed", {"profile": profile_name, "source": source, "success": False, "error": msg})
        return False
    except Exception as exc:
        logger.exception("Unexpected error refreshing profile '%s'", profile_name)
        hub.publish("sso.login.completed", {"profile": profile_name, "source": source, "success": False, "error": str(exc)})
        return False
