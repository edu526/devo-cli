import os

from cli_tool.utils.config_manager import get_config_value

BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# AWS Bedrock model configuration
# Using Claude Sonnet 4 (latest and most capable) with inference profile - confirmed working
SONNET_3_7_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
SONNET_4_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
FALLBACK_MODEL_ID = get_config_value("bedrock.fallback_model_id", SONNET_3_7_MODEL_ID)
DEFAULT_MODEL_ID = get_config_value("bedrock.model_id", SONNET_3_7_MODEL_ID)

# Get model ID from environment variable or config file
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
BEDROCK_REGION = os.getenv(
    "BEDROCK_REGION", get_config_value("bedrock.region", "us-east-1")
)

# GitHub Configuration
GITHUB_REPO_OWNER = os.getenv(
    "GITHUB_REPO_OWNER", get_config_value("github.repo_owner", "edu526")
)
GITHUB_REPO_NAME = os.getenv(
    "GITHUB_REPO_NAME", get_config_value("github.repo_name", "devo-cli")
)
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
GITHUB_API_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

# CodeArtifact Configuration
CODEARTIFACT_REGION = os.getenv(
    "CODEARTIFACT_REGION", get_config_value("codeartifact.region", "us-east-1")
)
CODEARTIFACT_ACCOUNT_ID = os.getenv(
    "CODEARTIFACT_ACCOUNT_ID",
    get_config_value("codeartifact.account_id", "123456789012"),
)
CODEARTIFACT_SSO_URL = os.getenv(
    "CODEARTIFACT_SSO_URL",
    get_config_value("codeartifact.sso_url", "https://my-org.awsapps.com/start"),
)
CODEARTIFACT_REQUIRED_ROLE = os.getenv(
    "CODEARTIFACT_REQUIRED_ROLE",
    get_config_value("codeartifact.required_role", "Developer"),
)

# Load CodeArtifact domains from config
_domains_config = get_config_value("codeartifact.domains", [])
CODEARTIFACT_DOMAINS = (
    [(d["domain"], d["repository"], d["namespace"]) for d in _domains_config]
    if _domains_config
    else []
)

# Legacy AWS config names (for backward compatibility)
AWS_REGION = CODEARTIFACT_REGION
AWS_ACCOUNT_ID = CODEARTIFACT_ACCOUNT_ID
AWS_SSO_URL = CODEARTIFACT_SSO_URL
AWS_REQUIRED_ROLE = CODEARTIFACT_REQUIRED_ROLE
