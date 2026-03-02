"""CodeArtifact authentication business logic."""

import subprocess
from typing import List, Optional, Tuple


class CodeArtifactAuthenticator:
    """Handles CodeArtifact authentication operations."""

    def __init__(self, region: str, domains: List[Tuple[str, str, str]]):
        """Initialize authenticator.

        Args:
          region: AWS region for CodeArtifact
          domains: List of (domain, repository, namespace) tuples
        """
        self.region = region
        self.domains = domains

    def authenticate_domain(
        self,
        domain: str,
        repository: str,
        namespace: str,
        profile: Optional[str] = None,
        timeout: int = 30,
    ) -> Tuple[bool, Optional[str]]:
        """Authenticate with a single CodeArtifact domain.

        Args:
          domain: CodeArtifact domain name
          repository: Repository name
          namespace: Package namespace
          profile: AWS profile to use
          timeout: Command timeout in seconds

        Returns:
          Tuple of (success, error_message)
        """
        cmd = [
            "aws",
            "codeartifact",
            "login",
            "--tool",
            "npm",
            "--domain",
            domain,
            "--repository",
            repository,
            "--namespace",
            namespace,
            "--region",
            self.region,
        ]

        if profile:
            cmd.extend(["--profile", profile])

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
            return True, None
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except subprocess.CalledProcessError as e:
            return False, e.stderr if e.stderr else "Authentication failed"

    def list_packages(
        self,
        domain: str,
        repository: str,
        profile: Optional[str] = None,
        timeout: int = 10,
    ) -> List[str]:
        """List packages in a CodeArtifact repository.

        Args:
          domain: CodeArtifact domain name
          repository: Repository name
          profile: AWS profile to use
          timeout: Command timeout in seconds

        Returns:
          List of package names
        """
        cmd = [
            "aws",
            "codeartifact",
            "list-packages",
            "--domain",
            domain,
            "--repository",
            repository,
            "--region",
            self.region,
            "--format",
            "npm",
            "--query",
            "packages[].package",
            "--output",
            "text",
        ]

        if profile:
            cmd.extend(["--profile", profile])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0 and result.stdout.strip():
                return [pkg for pkg in result.stdout.strip().split("\t") if pkg]
            return []
        except Exception:
            return []

    def get_package_version(
        self,
        domain: str,
        repository: str,
        package: str,
        namespace: str,
        profile: Optional[str] = None,
        timeout: int = 5,
    ) -> Optional[str]:
        """Get the latest version of a package.

        Args:
          domain: CodeArtifact domain name
          repository: Repository name
          package: Package name
          namespace: Package namespace
          profile: AWS profile to use
          timeout: Command timeout in seconds

        Returns:
          Latest version string or None
        """
        cmd = [
            "aws",
            "codeartifact",
            "list-package-versions",
            "--domain",
            domain,
            "--repository",
            repository,
            "--format",
            "npm",
            "--package",
            package,
            "--namespace",
            namespace,
            "--region",
            self.region,
            "--query",
            "versions[0].version",
            "--output",
            "text",
        ]

        if profile:
            cmd.extend(["--profile", profile])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                return version if version and version != "None" else None
            return None
        except Exception:
            return None
