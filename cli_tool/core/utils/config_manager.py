"""Configuration manager for Devo CLI."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_config_dir():
    """Get the configuration directory path."""
    config_dir = Path.home() / ".devo"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_config_file():
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


def get_legacy_ssm_config_file():
    """Get legacy SSM config file path."""
    return get_config_dir() / "ssm-config.json"


def get_legacy_dynamodb_config_file():
    """Get legacy DynamoDB config file path."""
    return get_config_dir() / "dynamodb" / "export_templates.json"


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
        "ssm": {"databases": {}, "instances": {}},
        "dynamodb": {"export_templates": {}},
    }


def load_config():
    """Load configuration from file or create default."""
    config_file = get_config_file()

    if not config_file.exists():
        # Try to migrate from legacy configs
        migrated = _try_migrate_legacy_configs()
        if migrated:
            return load_config()  # Reload after migration

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


def _try_migrate_legacy_configs() -> bool:
    """Try to migrate legacy config files automatically."""
    config_file = get_config_file()
    if config_file.exists():
        return False

    legacy_ssm = get_legacy_ssm_config_file()
    legacy_dynamodb = get_legacy_dynamodb_config_file()

    has_legacy = legacy_ssm.exists() or legacy_dynamodb.exists()
    if not has_legacy:
        return False

    # Perform silent migration
    new_config = get_default_config()

    # Migrate SSM config
    if legacy_ssm.exists():
        try:
            with open(legacy_ssm, "r", encoding="utf-8") as f:
                ssm_config = json.load(f)
                new_config["ssm"] = ssm_config
        except Exception:
            pass

    # Migrate DynamoDB config
    if legacy_dynamodb.exists():
        try:
            with open(legacy_dynamodb, "r", encoding="utf-8") as f:
                dynamodb_templates = json.load(f)
                new_config["dynamodb"]["export_templates"] = dynamodb_templates
        except Exception:
            pass

    # Save consolidated config
    save_config(new_config)

    # Backup legacy files
    backup_dir = get_config_dir() / "backup"
    backup_dir.mkdir(exist_ok=True)

    if legacy_ssm.exists():
        import shutil

        shutil.move(str(legacy_ssm), str(backup_dir / "ssm-config.json.bak"))

    if legacy_dynamodb.exists():
        import shutil

        shutil.move(str(legacy_dynamodb), str(backup_dir / "export_templates.json.bak"))

    return True


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


def export_config(sections: Optional[List[str]] = None, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Export configuration (full or partial).

    Args:
      sections: List of top-level sections to export (e.g., ['ssm', 'dynamodb']).
                If None, exports full config.
      output_path: Optional file path to save the export. If None, returns dict only.

    Returns:
      Exported configuration dictionary

    Examples:
      # Export full config
      export_config()

      # Export only SSM config
      export_config(sections=['ssm'])

      # Export SSM and DynamoDB to file
      export_config(sections=['ssm', 'dynamodb'], output_path='my-config.json')
    """
    config = load_config()

    if sections:
        # Export only specified sections
        exported = {}
        for section in sections:
            if section in config:
                exported[section] = config[section]
    else:
        # Export full config
        exported = config

    if output_path:
        output_file = Path(output_path)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(exported, f, indent=2)

    return exported


def import_config(input_path: str, sections: Optional[List[str]] = None, merge: bool = True):
    """
    Import configuration from file.

    Args:
      input_path: Path to config file to import
      sections: List of sections to import. If None, imports all sections from file.
      merge: If True, merges with existing config. If False, replaces sections.

    Examples:
      # Import full config (merge)
      import_config('backup.json')

      # Import only SSM section (merge)
      import_config('ssm-backup.json', sections=['ssm'])

      # Replace SSM section completely
      import_config('ssm-backup.json', sections=['ssm'], merge=False)
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Config file not found: {input_path}")

    with open(input_file, "r", encoding="utf-8") as f:
        imported_config = json.load(f)

    current_config = load_config()

    if sections:
        # Import only specified sections
        for section in sections:
            if section in imported_config:
                if merge and section in current_config:
                    # Merge section
                    if isinstance(current_config[section], dict) and isinstance(imported_config[section], dict):
                        current_config[section] = _deep_merge(current_config[section], imported_config[section])
                    else:
                        current_config[section] = imported_config[section]
                else:
                    # Replace section
                    current_config[section] = imported_config[section]
    else:
        # Import all sections
        if merge:
            current_config = _deep_merge(current_config, imported_config)
        else:
            current_config = imported_config

    save_config(current_config)


def migrate_legacy_configs(backup: bool = True) -> Dict[str, bool]:
    """
    Manually migrate legacy config files to consolidated format.

    Args:
      backup: If True, backs up legacy files before removing them

    Returns:
      Dictionary with migration status for each legacy file
    """
    from rich.console import Console

    console = Console()

    config_file = get_config_file()
    legacy_ssm = get_legacy_ssm_config_file()
    legacy_dynamodb = get_legacy_dynamodb_config_file()

    status = {"ssm": False, "dynamodb": False, "already_migrated": config_file.exists() and not (legacy_ssm.exists() or legacy_dynamodb.exists())}

    if status["already_migrated"]:
        console.print("[yellow]Configuration already consolidated[/yellow]")
        return status

    # Load or create base config
    if config_file.exists():
        new_config = load_config()
    else:
        new_config = get_default_config()

    # Migrate SSM config
    if legacy_ssm.exists():
        try:
            with open(legacy_ssm, "r", encoding="utf-8") as f:
                ssm_config = json.load(f)
                new_config["ssm"] = ssm_config
                status["ssm"] = True
                console.print(f"[green]✓ Migrated SSM config from {legacy_ssm}[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to migrate SSM config: {e}[/red]")

    # Migrate DynamoDB config
    if legacy_dynamodb.exists():
        try:
            with open(legacy_dynamodb, "r", encoding="utf-8") as f:
                dynamodb_templates = json.load(f)
                new_config["dynamodb"]["export_templates"] = dynamodb_templates
                status["dynamodb"] = True
                console.print(f"[green]✓ Migrated DynamoDB config from {legacy_dynamodb}[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to migrate DynamoDB config: {e}[/red]")

    # Save consolidated config
    if status["ssm"] or status["dynamodb"]:
        save_config(new_config)
        console.print(f"\n[green]✓ Consolidated config saved to {config_file}[/green]")

        # Backup and remove legacy files
        if backup:
            backup_dir = get_config_dir() / "backup"
            backup_dir.mkdir(exist_ok=True)

            import shutil

            if legacy_ssm.exists() and status["ssm"]:
                backup_path = backup_dir / "ssm-config.json.bak"
                shutil.move(str(legacy_ssm), str(backup_path))
                console.print(f"[dim]Backed up to {backup_path}[/dim]")

            if legacy_dynamodb.exists() and status["dynamodb"]:
                backup_path = backup_dir / "export_templates.json.bak"
                shutil.move(str(legacy_dynamodb), str(backup_path))
                console.print(f"[dim]Backed up to {backup_path}[/dim]")

    return status


def list_config_sections() -> List[str]:
    """List all available configuration sections."""
    config = load_config()
    return list(config.keys())


# ============================================================================
# DynamoDB Export Templates Manager
# ============================================================================


def get_dynamodb_templates() -> Dict[str, Dict[str, Any]]:
    """Get all DynamoDB export templates."""
    config = load_config()
    return config.get("dynamodb", {}).get("export_templates", {})


def save_dynamodb_template(name: str, template: Dict[str, Any]):
    """Save a DynamoDB export template."""
    config = load_config()
    if "dynamodb" not in config:
        config["dynamodb"] = {"export_templates": {}}
    if "export_templates" not in config["dynamodb"]:
        config["dynamodb"]["export_templates"] = {}

    config["dynamodb"]["export_templates"][name] = template
    save_config(config)


def get_dynamodb_template(name: str) -> Optional[Dict[str, Any]]:
    """Get a specific DynamoDB export template."""
    templates = get_dynamodb_templates()
    return templates.get(name)


def delete_dynamodb_template(name: str) -> bool:
    """Delete a DynamoDB export template."""
    config = load_config()
    templates = config.get("dynamodb", {}).get("export_templates", {})

    if name in templates:
        del templates[name]
        config["dynamodb"]["export_templates"] = templates
        save_config(config)
        return True

    return False
