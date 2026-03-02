"""
Regression test for Issue #123: Config set doesn't create nested keys

This test verifies that the config set command properly creates intermediate
dictionaries when setting deeply nested configuration keys that don't exist.

Bug Description:
  Before the fix, attempting to set a deeply nested key like 'aws.sso.profiles.dev.region'
  would fail with a KeyError if the intermediate keys ('aws', 'sso', 'profiles', 'dev')
  didn't already exist in the configuration.

Expected Behavior:
  The set_config_value function should automatically create all intermediate dictionaries
  needed to set the target key, similar to how 'mkdir -p' works for directories.

GitHub Issue: https://github.com/org/repo/issues/123 (example)
Fixed in: PR #124 (example)
"""

import json

import pytest

from cli_tool.core.utils.config_manager import set_config_value


@pytest.mark.unit
def test_issue_123_config_set_creates_nested_keys(temp_config_dir, mocker):
    """
    Regression test for Issue #123: config set creates nested keys.

    Bug: Setting a deeply nested key (e.g., 'aws.sso.profiles.dev.region')
    would fail with KeyError if intermediate keys didn't exist.

    Fix: Modified config_manager.set_config_value to create intermediate
    dictionaries as needed when navigating the key path.

    Issue: https://github.com/org/repo/issues/123
    """
    # Mock the config file path to use temp directory
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Start with minimal config (no 'aws' key)
    initial_config = {
        "bedrock": {"model_id": "test-model"},
        "github": {"repo_owner": "test", "repo_name": "test-repo"},
    }
    with open(config_file, "w") as f:
        json.dump(initial_config, f)

    # This would have raised KeyError before the fix
    # because 'aws', 'sso', 'profiles', and 'dev' keys didn't exist
    set_config_value("aws.sso.profiles.dev.region", "us-west-2")

    # Verify nested structure was created correctly
    with open(config_file) as f:
        config = json.load(f)

    assert "aws" in config
    assert "sso" in config["aws"]
    assert "profiles" in config["aws"]["sso"]
    assert "dev" in config["aws"]["sso"]["profiles"]
    assert config["aws"]["sso"]["profiles"]["dev"]["region"] == "us-west-2"

    # Verify original config was preserved
    assert config["bedrock"]["model_id"] == "test-model"


@pytest.mark.unit
def test_issue_123_config_set_updates_existing_nested_key(temp_config_dir, mocker):
    """
    Regression test for Issue #123: config set updates existing nested keys.

    Verify that setting a nested key works correctly when some intermediate
    keys already exist (shouldn't overwrite existing data).
    """
    # Mock the config file path to use temp directory
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Start with partial nested structure
    initial_config = {"aws": {"region": "us-east-1", "sso": {"profiles": {"dev": {"account_id": "123456789012"}}}}}
    with open(config_file, "w") as f:
        json.dump(initial_config, f)

    # Add a new key to existing nested structure
    set_config_value("aws.sso.profiles.dev.region", "us-west-2")

    # Verify new key was added without overwriting existing data
    with open(config_file) as f:
        config = json.load(f)

    assert config["aws"]["region"] == "us-east-1"  # Preserved
    assert config["aws"]["sso"]["profiles"]["dev"]["account_id"] == "123456789012"  # Preserved
    assert config["aws"]["sso"]["profiles"]["dev"]["region"] == "us-west-2"  # Added


@pytest.mark.unit
def test_issue_123_config_set_handles_multiple_nested_paths(temp_config_dir, mocker):
    """
    Regression test for Issue #123: config set handles multiple nested paths.

    Verify that multiple deeply nested keys can be set independently without
    interfering with each other.
    """
    # Mock the config file path to use temp directory
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Start with empty config
    initial_config = {}
    with open(config_file, "w") as f:
        json.dump(initial_config, f)

    # Set multiple deeply nested keys
    set_config_value("aws.sso.profiles.dev.region", "us-west-2")
    set_config_value("aws.sso.profiles.prod.region", "us-east-1")
    set_config_value("aws.sso.profiles.dev.account_id", "111111111111")
    set_config_value("aws.sso.profiles.prod.account_id", "222222222222")

    # Verify all nested structures were created correctly
    with open(config_file) as f:
        config = json.load(f)

    assert config["aws"]["sso"]["profiles"]["dev"]["region"] == "us-west-2"
    assert config["aws"]["sso"]["profiles"]["dev"]["account_id"] == "111111111111"
    assert config["aws"]["sso"]["profiles"]["prod"]["region"] == "us-east-1"
    assert config["aws"]["sso"]["profiles"]["prod"]["account_id"] == "222222222222"
