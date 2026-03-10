"""CodeArtifact authentication business logic."""

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple


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
    ) -> List[Tuple[str, str]]:
        """List packages in a CodeArtifact repository.

        Args:
          domain: CodeArtifact domain name
          repository: Repository name
          profile: AWS profile to use
          timeout: Command timeout in seconds

        Returns:
          List of (namespace, package_name) tuples
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
            "packages[].[namespace, package]",
            "--output",
            "text",
        ]

        if profile:
            cmd.extend(["--profile", profile])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0 and result.stdout.strip():
                packages = []
                for line in result.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) == 2:
                        packages.append((parts[0], parts[1]))
                return packages
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
            namespace.lstrip("@"),
            "--region",
            self.region,
            "--sort-by",
            "PUBLISHED_TIME",
            "--query",
            "defaultDisplayVersion",
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

    def list_packages_with_versions(
        self,
        domain: str,
        repository: str,
        namespace: str,
        profile: Optional[str] = None,
        max_workers: int = 10,
    ) -> Dict[str, Optional[str]]:
        """List packages with their latest versions in parallel.

        Args:
          domain: CodeArtifact domain name
          repository: Repository name
          namespace: Package namespace
          profile: AWS profile to use
          max_workers: Max parallel threads for version fetching

        Returns:
          Dict mapping package name to latest version (or None)
        """
        packages = self.list_packages(domain, repository, profile)
        if not packages:
            return {}

        results: Dict[str, Optional[str]] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pkg = {
                executor.submit(self.get_package_version, domain, repository, pkg_name, pkg_ns, profile): (pkg_ns, pkg_name)
                for pkg_ns, pkg_name in packages
            }
            for future in as_completed(future_to_pkg):
                pkg_ns, pkg_name = future_to_pkg[future]
                display_name = f"@{pkg_ns}/{pkg_name}"
                try:
                    results[display_name] = future.result()
                except Exception:
                    results[display_name] = None

        return results
