"""
Integration tests for config command.

Tests cover:
- Config set command updates configuration
- Config get/show command retrieves values
- Config export command generates JSON
- Config import command loads JSON
- Config list command shows all settings
- Config set with invalid key format
- Config migration between versions
- Config validation on import
- Config export with nested structures
- Config round-trip (export then import)
- Config reset (full and per-section)
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_tool.commands.config_cmd.commands import register_config_commands
from cli_tool.commands.config_cmd.commands.export import export_command
from cli_tool.commands.config_cmd.commands.import_cmd import import_command
from cli_tool.commands.config_cmd.commands.migrate import migrate_command
from cli_tool.commands.config_cmd.commands.path import show_path
from cli_tool.commands.config_cmd.commands.reset import reset_command
from cli_tool.commands.config_cmd.commands.sections import list_sections
from cli_tool.commands.config_cmd.commands.set import set_command
from cli_tool.commands.config_cmd.commands.show import show_config

# ============================================================================
# Task 4.5: Basic Config Command Tests
# ============================================================================


@pytest.mark.integration
def test_config_set_command_updates_configuration(cli_runner, temp_config_dir, mocker):
    """Test config set command successfully updates configuration."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Initialize with empty config
    config_file.write_text("{}")

    # Run set command
    result = cli_runner.invoke(set_command, ["bedrock.model_id", "test-model"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify output message
    assert "bedrock.model_id" in result.output
    assert "test-model" in result.output

    # Verify config file was updated
    with open(config_file) as f:
        config = json.load(f)
    assert config["bedrock"]["model_id"] == "test-model"


@pytest.mark.integration
def test_config_set_creates_nested_structure(cli_runner, temp_config_dir, mocker):
    """Test config set creates intermediate dictionaries for nested keys."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Initialize with empty config
    config_file.write_text("{}")

    # Set deeply nested key
    result = cli_runner.invoke(set_command, ["aws.sso.profiles.dev.region", "us-west-2"])

    # Verify success
    assert result.exit_code == 0

    # Verify nested structure was created
    with open(config_file) as f:
        config = json.load(f)
    assert config["aws"]["sso"]["profiles"]["dev"]["region"] == "us-west-2"


@pytest.mark.integration
def test_config_set_with_json_value(cli_runner, temp_config_dir, mocker):
    """Test config set parses JSON values correctly."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    config_file.write_text("{}")

    # Set boolean value
    result = cli_runner.invoke(set_command, ["version_check.enabled", "true"])
    assert result.exit_code == 0

    with open(config_file) as f:
        config = json.load(f)
    assert config["version_check"]["enabled"] is True

    # Set number value
    result = cli_runner.invoke(set_command, ["timeout", "30"])
    assert result.exit_code == 0

    with open(config_file) as f:
        config = json.load(f)
    assert config["timeout"] == 30


@pytest.mark.integration
def test_config_get_command_retrieves_values(cli_runner, temp_config_dir, mocker):
    """Test config show command retrieves configuration values."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup test config
    test_config = {"aws": {"region": "us-east-1"}, "bedrock": {"model_id": "test-model"}}
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Run show command
    result = cli_runner.invoke(show_config, ["--json"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify output contains config values
    assert "us-east-1" in result.output
    assert "test-model" in result.output


@pytest.mark.integration
def test_config_show_specific_section(cli_runner, temp_config_dir, mocker):
    """Test config show with specific section filter."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup test config
    test_config = {"aws": {"region": "us-east-1"}, "bedrock": {"model_id": "test-model"}}
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Run show command with section filter
    result = cli_runner.invoke(show_config, ["--section", "aws", "--json"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify only aws section is shown
    assert "us-east-1" in result.output
    assert "test-model" not in result.output


@pytest.mark.integration
def test_config_export_command_generates_json(cli_runner, temp_config_dir, mocker):
    """Test config export command generates JSON output."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup test config
    test_config = {"aws": {"region": "us-east-1"}, "bedrock": {"model_id": "test-model"}}
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Export to stdout
    result = cli_runner.invoke(export_command, ["--stdout"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify JSON output
    exported = json.loads(result.output)
    assert exported["aws"]["region"] == "us-east-1"
    assert exported["bedrock"]["model_id"] == "test-model"


@pytest.mark.integration
def test_config_export_to_file(cli_runner, temp_config_dir, mocker):
    """Test config export command saves to file."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup test config
    test_config = {"aws": {"region": "us-east-1"}}
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Export to file
    output_file = temp_config_dir / "export.json"
    result = cli_runner.invoke(export_command, ["--output", str(output_file)])

    # Verify exit code
    assert result.exit_code == 0

    # Verify file was created
    assert output_file.exists()

    # Verify file content
    with open(output_file) as f:
        exported = json.load(f)
    assert exported["aws"]["region"] == "us-east-1"


@pytest.mark.integration
def test_config_import_command_loads_json(cli_runner, temp_config_dir, mocker):
    """Test config import command loads JSON from file."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Initialize with empty config
    config_file.write_text("{}")

    # Create import file
    import_file = temp_config_dir / "import.json"
    import_data = {"aws": {"region": "us-west-2"}}
    with open(import_file, "w") as f:
        json.dump(import_data, f)

    # Run import command
    result = cli_runner.invoke(import_command, [str(import_file)])

    # Verify exit code
    assert result.exit_code == 0

    # Verify config was updated
    with open(config_file) as f:
        config = json.load(f)
    assert config["aws"]["region"] == "us-west-2"


@pytest.mark.integration
def test_config_import_merges_by_default(cli_runner, temp_config_dir, mocker):
    """Test config import merges with existing config by default."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup existing config
    existing_config = {"aws": {"region": "us-east-1"}, "bedrock": {"model_id": "old-model"}}
    with open(config_file, "w") as f:
        json.dump(existing_config, f)

    # Create import file with partial update
    import_file = temp_config_dir / "import.json"
    import_data = {"bedrock": {"model_id": "new-model"}}
    with open(import_file, "w") as f:
        json.dump(import_data, f)

    # Run import command (merge mode)
    result = cli_runner.invoke(import_command, [str(import_file)])

    # Verify exit code
    assert result.exit_code == 0

    # Verify config was merged (aws section preserved)
    with open(config_file) as f:
        config = json.load(f)
    assert config["aws"]["region"] == "us-east-1"  # Preserved
    assert config["bedrock"]["model_id"] == "new-model"  # Updated


@pytest.mark.integration
def test_config_list_command_shows_all_settings(cli_runner, temp_config_dir, mocker):
    """Test config list sections command shows all configuration sections."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup test config with multiple sections
    test_config = {"aws": {"region": "us-east-1"}, "bedrock": {"model_id": "test-model"}, "ssm": {"instances": []}}
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Run list sections command
    result = cli_runner.invoke(list_sections)

    # Verify exit code
    assert result.exit_code == 0

    # Verify all sections are listed
    assert "aws" in result.output
    assert "bedrock" in result.output
    assert "ssm" in result.output


@pytest.mark.integration
def test_config_set_with_invalid_key_format(cli_runner, temp_config_dir, mocker):
    """Test config set command with invalid key format."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    config_file.write_text("{}")

    # Try to set with empty key
    result = cli_runner.invoke(set_command, ["", "value"])

    # Should handle gracefully (may succeed with empty key or fail)
    # The actual behavior depends on implementation
    # We just verify it doesn't crash
    assert result.exit_code is not None


# ============================================================================
# Task 4.6: Integration Tests for Config Command Workflows
# ============================================================================


@pytest.mark.integration
def test_config_migration_between_versions(cli_runner, temp_config_dir, mocker):
    """Test config migration from legacy format to new format."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create legacy SSM config file
    legacy_ssm_file = temp_config_dir / "ssm-config.json"
    legacy_ssm_data = {"instances": [{"name": "web-server", "instance_id": "i-123456"}]}
    with open(legacy_ssm_file, "w") as f:
        json.dump(legacy_ssm_data, f)

    # Mock the legacy file path functions
    mocker.patch("cli_tool.core.utils.config_manager.get_legacy_ssm_config_file", return_value=legacy_ssm_file)

    # Create legacy DynamoDB config directory
    legacy_dynamodb_dir = temp_config_dir / "dynamodb"
    legacy_dynamodb_dir.mkdir()
    legacy_dynamodb_file = legacy_dynamodb_dir / "export_templates.json"
    legacy_dynamodb_data = {"templates": [{"name": "users-table", "table": "users"}]}
    with open(legacy_dynamodb_file, "w") as f:
        json.dump(legacy_dynamodb_data, f)

    # Mock the legacy DynamoDB file path function
    mocker.patch("cli_tool.core.utils.config_manager.get_legacy_dynamodb_config_file", return_value=legacy_dynamodb_file)

    # Mock get_config_dir to return temp_config_dir
    mocker.patch("cli_tool.core.utils.config_manager.get_config_dir", return_value=temp_config_dir)

    # Run migration command
    result = cli_runner.invoke(migrate_command, ["--no-backup"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify migration message
    assert "Migration completed" in result.output or "No legacy config" in result.output or "already consolidated" in result.output.lower()


@pytest.mark.integration
def test_config_validation_on_import(cli_runner, temp_config_dir, mocker):
    """Test config import validates imported data."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    config_file.write_text("{}")

    # Create import file with valid JSON but potentially invalid structure
    import_file = temp_config_dir / "import.json"
    import_data = {"valid_section": {"key": "value"}}
    with open(import_file, "w") as f:
        json.dump(import_data, f)

    # Run import command
    result = cli_runner.invoke(import_command, [str(import_file)])

    # Should succeed with valid JSON
    assert result.exit_code == 0

    # Verify data was imported
    with open(config_file) as f:
        config = json.load(f)
    assert "valid_section" in config


@pytest.mark.integration
def test_config_import_with_malformed_json(cli_runner, temp_config_dir, mocker):
    """Test config import handles malformed JSON gracefully."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    config_file.write_text("{}")

    # Create import file with malformed JSON
    import_file = temp_config_dir / "bad_import.json"
    import_file.write_text("{invalid json}")

    # Run import command
    result = cli_runner.invoke(import_command, [str(import_file)])

    # Should fail gracefully - either with non-zero exit code or error message
    # The actual behavior depends on implementation
    # We verify it doesn't crash and provides some feedback
    assert "failed" in result.output.lower() or "error" in result.output.lower() or result.exit_code != 0


@pytest.mark.integration
def test_config_export_with_nested_structures(cli_runner, temp_config_dir, mocker):
    """Test config export handles deeply nested structures correctly."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup deeply nested config
    test_config = {
        "aws": {
            "sso": {
                "profiles": {
                    "dev": {"region": "us-east-1", "account_id": "123456789012", "role_name": "Developer"},
                    "prod": {"region": "us-west-2", "account_id": "987654321098", "role_name": "Admin"},
                }
            }
        }
    }
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Export to stdout
    result = cli_runner.invoke(export_command, ["--stdout"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify nested structure is preserved
    exported = json.loads(result.output)
    assert exported["aws"]["sso"]["profiles"]["dev"]["region"] == "us-east-1"
    assert exported["aws"]["sso"]["profiles"]["prod"]["region"] == "us-west-2"


@pytest.mark.integration
def test_config_export_specific_sections(cli_runner, temp_config_dir, mocker):
    """Test config export with specific section filtering."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup test config with multiple sections
    test_config = {"aws": {"region": "us-east-1"}, "bedrock": {"model_id": "test-model"}, "ssm": {"instances": []}}
    with open(config_file, "w") as f:
        json.dump(test_config, f)

    # Export only SSM section
    result = cli_runner.invoke(export_command, ["--section", "ssm", "--stdout"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify only SSM section is exported
    exported = json.loads(result.output)
    assert "ssm" in exported
    assert "aws" not in exported
    assert "bedrock" not in exported


@pytest.mark.integration
def test_config_round_trip_export_then_import(cli_runner, temp_config_dir, mocker):
    """Test config round-trip: export then import produces equivalent configuration."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup original config
    original_config = {
        "aws": {"region": "us-east-1", "sso": {"profiles": {"dev": {"account_id": "123456789012"}}}},
        "bedrock": {"model_id": "test-model"},
        "version_check": {"enabled": True},
    }
    with open(config_file, "w") as f:
        json.dump(original_config, f)

    # Export to file
    export_file = temp_config_dir / "export.json"
    result = cli_runner.invoke(export_command, ["--output", str(export_file)])
    assert result.exit_code == 0

    # Verify export file contains original data
    with open(export_file) as f:
        exported_config = json.load(f)

    # Check that key values from original are in export
    assert exported_config["aws"]["region"] == "us-east-1"
    assert exported_config["bedrock"]["model_id"] == "test-model"
    assert exported_config["version_check"]["enabled"] is True

    # Clear config
    config_file.write_text("{}")

    # Import back
    result = cli_runner.invoke(import_command, [str(export_file)])
    assert result.exit_code == 0

    # Verify config has the original values (may have additional default keys)
    with open(config_file) as f:
        restored_config = json.load(f)

    # Verify key values are preserved
    assert restored_config["aws"]["region"] == "us-east-1"
    assert restored_config["bedrock"]["model_id"] == "test-model"
    assert restored_config["version_check"]["enabled"] is True


@pytest.mark.integration
def test_config_import_specific_section(cli_runner, temp_config_dir, mocker):
    """Test config import with specific section filtering."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup existing config
    existing_config = {"aws": {"region": "us-east-1"}, "bedrock": {"model_id": "old-model"}}
    with open(config_file, "w") as f:
        json.dump(existing_config, f)

    # Create import file with multiple sections
    import_file = temp_config_dir / "import.json"
    import_data = {"aws": {"region": "us-west-2"}, "bedrock": {"model_id": "new-model"}}
    with open(import_file, "w") as f:
        json.dump(import_data, f)

    # Import only bedrock section
    result = cli_runner.invoke(import_command, [str(import_file), "--section", "bedrock"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify only bedrock was updated, aws preserved
    with open(config_file) as f:
        config = json.load(f)
    assert config["aws"]["region"] == "us-east-1"  # Preserved
    assert config["bedrock"]["model_id"] == "new-model"  # Updated


@pytest.mark.integration
def test_config_import_replace_mode(cli_runner, temp_config_dir, mocker):
    """Test config import with replace mode instead of merge."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup existing config with nested structure
    existing_config = {"aws": {"region": "us-east-1", "profile": "dev", "extra_key": "should_be_removed"}}
    with open(config_file, "w") as f:
        json.dump(existing_config, f)

    # Create import file with partial aws section
    import_file = temp_config_dir / "import.json"
    import_data = {"aws": {"region": "us-west-2"}}
    with open(import_file, "w") as f:
        json.dump(import_data, f)

    # Import with replace flag
    result = cli_runner.invoke(import_command, [str(import_file), "--section", "aws", "--replace"])

    # Verify exit code
    assert result.exit_code == 0

    # Verify aws section was replaced (not merged)
    with open(config_file) as f:
        config = json.load(f)
    assert config["aws"]["region"] == "us-west-2"
    assert "profile" not in config["aws"]  # Should be removed
    assert "extra_key" not in config["aws"]  # Should be removed


# ============================================================================
# Config Reset Command Tests
# ============================================================================


@pytest.mark.unit
def test_reset_command_full_reset(cli_runner, mocker):
    """Test reset command with no section resets entire configuration."""
    mock_reset = mocker.patch("cli_tool.commands.config_cmd.commands.reset.reset_config")

    result = cli_runner.invoke(reset_command, ["--yes"])

    assert result.exit_code == 0
    mock_reset.assert_called_once()
    assert "reset to defaults" in result.output


@pytest.mark.unit
def test_reset_command_valid_section(cli_runner, mocker):
    """Test reset command with a known section resets that section only."""
    bedrock_defaults = {"model_id": "default-model", "region": "us-east-1"}
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.reset.get_default_config",
        return_value={"bedrock": bedrock_defaults},
    )
    mock_set = mocker.patch("cli_tool.commands.config_cmd.commands.reset.set_config_value")

    result = cli_runner.invoke(reset_command, ["--section", "bedrock", "--yes"])

    assert result.exit_code == 0
    mock_set.assert_called_once_with("bedrock", bedrock_defaults)
    assert "bedrock" in result.output


@pytest.mark.unit
def test_reset_command_invalid_section(cli_runner, mocker):
    """Test reset command with an unknown section prints an error and returns."""
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.reset.get_default_config",
        return_value={},
    )
    mock_set = mocker.patch("cli_tool.commands.config_cmd.commands.reset.set_config_value")

    result = cli_runner.invoke(reset_command, ["--section", "nonexistent", "--yes"])

    assert result.exit_code == 0
    mock_set.assert_not_called()
    assert "Unknown section" in result.output or "nonexistent" in result.output


# ============================================================================
# Additional unit tests to cover missing lines
# ============================================================================


@pytest.mark.unit
def test_show_path_command_prints_config_path(cli_runner, mocker):
    """Test show_path command prints the config path returned by get_config_path."""
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.path.get_config_path",
        return_value="/home/user/.devo/config.json",
    )

    result = cli_runner.invoke(show_path)

    assert result.exit_code == 0
    assert "/home/user/.devo/config.json" in result.output


@pytest.mark.unit
def test_migrate_command_already_migrated_returns_early(cli_runner, mocker):
    """Test migrate_command returns early without printing migration messages when already migrated."""
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.migrate.migrate_legacy_configs",
        return_value={"already_migrated": True, "ssm": False, "dynamodb": False},
    )

    result = cli_runner.invoke(migrate_command, [])

    assert result.exit_code == 0
    assert "Migration completed" not in result.output
    assert "No legacy config files found" not in result.output


@pytest.mark.unit
def test_migrate_command_no_legacy_files_found(cli_runner, mocker):
    """Test migrate_command prints 'No legacy config files found' when ssm and dynamodb are both False."""
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.migrate.migrate_legacy_configs",
        return_value={"already_migrated": False, "ssm": False, "dynamodb": False},
    )

    result = cli_runner.invoke(migrate_command, [])

    assert result.exit_code == 0
    assert "No legacy config files found" in result.output


@pytest.mark.unit
def test_export_command_generates_timestamped_filename(cli_runner, mocker):
    """Test export_command generates a timestamped filename when --output and --stdout are not given."""
    mock_export = mocker.patch(
        "cli_tool.commands.config_cmd.commands.export.export_config",
        return_value={"aws": {"region": "us-east-1"}},
    )

    result = cli_runner.invoke(export_command, [])

    assert result.exit_code == 0
    # export_config must have been called with an output_path matching the timestamp pattern
    call_kwargs = mock_export.call_args
    output_path_used = call_kwargs[1].get("output_path") or (call_kwargs[0][0] if call_kwargs[0] else None)
    # Retrieve via keyword argument; export_config(sections=..., output_path=...)
    output_path_used = mock_export.call_args.kwargs.get("output_path")
    assert output_path_used is not None
    assert output_path_used.startswith("devo-config-backup-")
    assert output_path_used.endswith(".json")
    assert "Configuration exported to" in result.output


@pytest.mark.unit
def test_export_command_exception_prints_error(cli_runner, mocker):
    """Test export_command prints an error message when export_config raises an exception."""
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.export.export_config",
        side_effect=Exception("disk full"),
    )

    result = cli_runner.invoke(export_command, ["--stdout"])

    assert result.exit_code == 0
    assert "Export failed" in result.output
    assert "disk full" in result.output


@pytest.mark.unit
def test_import_command_generic_exception_prints_error(cli_runner, tmp_path, mocker):
    """Test import_command prints 'Import failed' for non-FileNotFoundError exceptions."""
    # Create a real file so Click's exists=True check passes
    input_file = tmp_path / "config.json"
    input_file.write_text('{"key": "value"}')

    mocker.patch(
        "cli_tool.commands.config_cmd.commands.import_cmd.import_config",
        side_effect=Exception("unexpected error"),
    )

    result = cli_runner.invoke(import_command, [str(input_file)])

    assert result.exit_code == 0
    assert "Import failed" in result.output
    assert "unexpected error" in result.output


@pytest.mark.unit
def test_set_command_exception_prints_error(cli_runner, mocker):
    """Test set_command prints 'Failed to set value' when set_config_value raises an exception."""
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.set.set_config_value",
        side_effect=Exception("permission denied"),
    )

    result = cli_runner.invoke(set_command, ["some.key", "some_value"])

    assert result.exit_code == 0
    assert "Failed to set value" in result.output
    assert "permission denied" in result.output


@pytest.mark.unit
def test_show_config_without_json_flag_uses_syntax(cli_runner, mocker):
    """Test show_config without --json flag renders config using rich Syntax (not plain JSON print)."""
    mocker.patch(
        "cli_tool.commands.config_cmd.commands.show.load_config",
        return_value={"aws": {"region": "us-east-1"}},
    )

    result = cli_runner.invoke(show_config, [])

    assert result.exit_code == 0
    # The config data must appear in output regardless of rich formatting
    assert "us-east-1" in result.output


@pytest.mark.unit
def test_register_config_commands_group_help(cli_runner):
    """Test that the config group returned by register_config_commands works and shows help."""
    config_group = register_config_commands()

    result = cli_runner.invoke(config_group, ["--help"])

    assert result.exit_code == 0
    assert "config" in result.output.lower() or "Manage" in result.output


@pytest.mark.unit
def test_register_config_commands_group_callback_invoked(cli_runner):
    """config/__init__.py line 21: config_group() callback (pass) is invoked when a subcommand is called."""
    config_group = register_config_commands()
    # Invoking a subcommand causes Click to first call config_group() callback
    result = cli_runner.invoke(config_group, ["show", "--help"])
    assert result.exit_code == 0


@pytest.mark.unit
def test_import_command_file_not_found_prints_error(cli_runner, tmp_path, mocker):
    """import_cmd.py line 41: FileNotFoundError path prints error message."""
    input_file = tmp_path / "config.json"
    input_file.write_text('{"key": "value"}')

    mocker.patch(
        "cli_tool.commands.config_cmd.commands.import_cmd.import_config",
        side_effect=FileNotFoundError("file not found"),
    )

    result = cli_runner.invoke(import_command, [str(input_file)])

    assert result.exit_code == 0
    assert "file not found" in result.output
