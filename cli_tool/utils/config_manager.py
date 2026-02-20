"""Configuration manager for Devo CLI."""

import json
from pathlib import Path
from typing import Any, Dict


def get_config_dir():
    """Get the configuration directory path."""
    config_dir = Path.home() / ".devo"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_config_file():
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


def get_default_config():
    """Get default configuration values."""
    return {
        "bedrock": {
            "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "fallback_model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "region": "us-east-1",
        },
        "github": {"repo_owner": "edu526", "repo_name": "devo-cli"},
        "codeartifact": {
            "region": "us-east-1",
            "account_id": "123456789012",
            "sso_url": "https://my-org.awsapps.com/start",
            "required_role": "Developer",
            "domains": [],
        },
        "version_check": {"enabled": True},
    }


def load_config():
    """Load configuration from file or create default."""
    config_file = get_config_file()

    if not config_file.exists():
        # Create default config file
        default_config = get_default_config()
        save_config(default_config)
        return default_config

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        # Merge with defaults to ensure all keys exist
        default_config = get_default_config()
        merged_config = _deep_merge(default_config, user_config)
        return merged_config
    except Exception:
        # If config is corrupted, return defaults
        return get_default_config()


def save_config(config: Dict[str, Any]):
    """Save configuration to file."""
    config_file = get_config_file()
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        raise Exception(f"Failed to save configuration: {str(e)}")


def get_config_value(key_path: str, default: Any = None) -> Any:
    """
    Get a configuration value by dot-notation path.

    Examples:
      get_config_value("aws.region")
      get_config_value("bedrock.model_id")
    """
    config = load_config()
    keys = key_path.split(".")
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def set_config_value(key_path: str, value: Any):
    """
    Set a configuration value by dot-notation path.

    Examples:
      set_config_value("aws.region", "us-west-2")
      set_config_value("bedrock.model_id", "new-model-id")
    """
    config = load_config()
    keys = key_path.split(".")
    current = config

    # Navigate to the parent of the target key
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Set the value
    current[keys[-1]] = value
    save_config(config)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def reset_config():
    """Reset configuration to defaults."""
    default_config = get_default_config()
    save_config(default_config)
    return default_config


def get_config_path():
    """Get the path to the configuration file."""
    return str(get_config_file())
