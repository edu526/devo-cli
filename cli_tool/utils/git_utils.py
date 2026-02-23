import re
import subprocess


def get_staged_diff() -> str:
    result = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip()


def get_branch_name() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def get_remote_url() -> str:
    """Get the remote URL of the repository and convert it to HTTPS if it's an SSH URL."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Remove username from URL, e.g., https://user@github.com -> https://github.com
        url = re.sub(r"//.*@", "//", url)
        if url.startswith("git@"):
            # Convert SSH URL to HTTPS URL: git@github.com:user/repo.git -> https://github.com/user/repo
            url = url.replace(":", "/", 1).replace("git@", "https://")
        return url
    except subprocess.CalledProcessError:
        return None
