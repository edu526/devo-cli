"""Tests for SSMConfigManager — cli_tool/commands/ssm/core/config.py."""

import json

import pytest

from cli_tool.commands.ssm.core.config import SSMConfigManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config(mocker):
    """Return a fresh mutable config dict and patch load/save."""
    config = {"ssm": {"databases": {}, "instances": {}}}
    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value=config)
    mocker.patch("cli_tool.commands.ssm.core.config.save_config")
    return config


@pytest.fixture
def manager():
    return SSMConfigManager()


# ---------------------------------------------------------------------------
# load / save
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_returns_ssm_section(mock_config, manager):
    """load() extracts the 'ssm' key from the consolidated config."""
    result = manager.load()
    assert result == {"databases": {}, "instances": {}}


@pytest.mark.unit
def test_load_returns_default_when_ssm_missing(mocker, manager):
    """load() returns a default dict when 'ssm' key is absent."""
    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value={})
    result = manager.load()
    assert result == {"databases": {}, "instances": {}}


@pytest.mark.unit
def test_save_writes_ssm_section(mocker, manager):
    """save() merges the ssm_config into the consolidated config and calls save_config."""
    config = {}
    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value=config)
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.save({"databases": {"db1": {}}})

    mock_save.assert_called_once()
    saved_arg = mock_save.call_args[0][0]
    assert "db1" in saved_arg["ssm"]["databases"]


# ---------------------------------------------------------------------------
# add_database
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_add_database_creates_databases_key_when_missing(mocker, manager):
    """add_database initialises 'databases' dict when the key is absent (line 39)."""
    # Simulate ssm section without 'databases'
    config = {"ssm": {"instances": {}}}
    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value=config)
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.add_database(
        name="mydb",
        bastion="i-abc",
        host="mydb.example.com",
        port=5432,
    )

    mock_save.assert_called()
    saved = mock_save.call_args[0][0]
    assert "mydb" in saved["ssm"]["databases"]


@pytest.mark.unit
def test_add_database_full_params(mock_config, manager, mocker):
    """add_database stores all provided fields."""
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.add_database(
        name="mydb",
        bastion="i-abc",
        host="mydb.example.com",
        port=5432,
        region="eu-west-1",
        profile="my-profile",
        local_port=15432,
        local_address="127.0.0.2",
    )

    mock_save.assert_called()
    saved = mock_save.call_args[0][0]
    db = saved["ssm"]["databases"]["mydb"]
    assert db["bastion"] == "i-abc"
    assert db["host"] == "mydb.example.com"
    assert db["port"] == 5432
    assert db["region"] == "eu-west-1"
    assert db["profile"] == "my-profile"
    assert db["local_port"] == 15432
    assert db["local_address"] == "127.0.0.2"


@pytest.mark.unit
def test_add_database_local_port_defaults_to_port(mock_config, manager, mocker):
    """When local_port is None it falls back to the remote port value."""
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.add_database(name="mydb", bastion="i-abc", host="h.example.com", port=5432)

    saved = mock_save.call_args[0][0]
    assert saved["ssm"]["databases"]["mydb"]["local_port"] == 5432


# ---------------------------------------------------------------------------
# remove_database
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_remove_database_existing(mock_config, manager, mocker):
    """remove_database deletes the entry and returns True."""
    mock_config["ssm"]["databases"]["mydb"] = {"host": "h.example.com"}
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    result = manager.remove_database("mydb")

    assert result is True
    mock_save.assert_called()
    saved = mock_save.call_args[0][0]
    assert "mydb" not in saved["ssm"]["databases"]


@pytest.mark.unit
def test_remove_database_not_found(mock_config, manager, mocker):
    """remove_database returns False when the name does not exist."""
    mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    result = manager.remove_database("nonexistent")

    assert result is False


# ---------------------------------------------------------------------------
# get_database / list_databases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_database_found(mock_config, manager):
    """get_database returns the dict for a known database."""
    mock_config["ssm"]["databases"]["mydb"] = {"host": "h.example.com"}

    result = manager.get_database("mydb")

    assert result == {"host": "h.example.com"}


@pytest.mark.unit
def test_get_database_not_found(mock_config, manager):
    """get_database returns None when the database does not exist."""
    assert manager.get_database("unknown") is None


@pytest.mark.unit
def test_list_databases_returns_all(mock_config, manager):
    """list_databases returns the entire databases dict."""
    mock_config["ssm"]["databases"] = {"a": {}, "b": {}}

    result = manager.list_databases()

    assert set(result.keys()) == {"a", "b"}


@pytest.mark.unit
def test_list_databases_empty(mock_config, manager):
    """list_databases returns an empty dict when none are configured."""
    assert manager.list_databases() == {}


# ---------------------------------------------------------------------------
# add_instance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_add_instance_creates_instances_key_when_missing(mocker, manager):
    """add_instance initialises 'instances' dict when the key is absent (lines 78-79)."""
    config = {"ssm": {"databases": {}}}
    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value=config)
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.add_instance(name="bastion", instance_id="i-123", region="us-east-1")

    mock_save.assert_called()
    saved = mock_save.call_args[0][0]
    assert "bastion" in saved["ssm"]["instances"]


@pytest.mark.unit
def test_add_instance_full_params(mock_config, manager, mocker):
    """add_instance stores instance_id, region and profile."""
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.add_instance(name="bastion", instance_id="i-abc", region="eu-west-1", profile="my-profile")

    saved = mock_save.call_args[0][0]
    inst = saved["ssm"]["instances"]["bastion"]
    assert inst["instance_id"] == "i-abc"
    assert inst["region"] == "eu-west-1"
    assert inst["profile"] == "my-profile"


@pytest.mark.unit
def test_add_instance_default_region(mock_config, manager, mocker):
    """add_instance defaults region to us-east-1."""
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.add_instance(name="bastion", instance_id="i-abc")

    saved = mock_save.call_args[0][0]
    assert saved["ssm"]["instances"]["bastion"]["region"] == "us-east-1"


# ---------------------------------------------------------------------------
# remove_instance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_remove_instance_existing(mock_config, manager, mocker):
    """remove_instance deletes the entry and returns True."""
    mock_config["ssm"]["instances"]["bastion"] = {"instance_id": "i-abc", "region": "us-east-1"}
    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    result = manager.remove_instance("bastion")

    assert result is True
    mock_save.assert_called()
    saved = mock_save.call_args[0][0]
    assert "bastion" not in saved["ssm"]["instances"]


@pytest.mark.unit
def test_remove_instance_not_found(mock_config, manager, mocker):
    """remove_instance returns False when the name does not exist (line 94)."""
    mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    result = manager.remove_instance("nonexistent")

    assert result is False


# ---------------------------------------------------------------------------
# get_instance / list_instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_instance_found(mock_config, manager):
    """get_instance returns the dict for a known instance (lines 98-99)."""
    mock_config["ssm"]["instances"]["bastion"] = {"instance_id": "i-abc"}

    result = manager.get_instance("bastion")

    assert result == {"instance_id": "i-abc"}


@pytest.mark.unit
def test_get_instance_not_found(mock_config, manager):
    """get_instance returns None when the instance does not exist."""
    assert manager.get_instance("unknown") is None


@pytest.mark.unit
def test_list_instances_returns_all(mock_config, manager):
    """list_instances returns the entire instances dict (lines 103-104)."""
    mock_config["ssm"]["instances"] = {"a": {}, "b": {}}

    result = manager.list_instances()

    assert set(result.keys()) == {"a", "b"}


@pytest.mark.unit
def test_list_instances_empty(mock_config, manager):
    """list_instances returns an empty dict when none are configured."""
    assert manager.list_instances() == {}


# ---------------------------------------------------------------------------
# export_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_export_config_writes_json(mock_config, manager, tmp_path):
    """export_config writes the current ssm config as JSON (lines 108-112)."""
    mock_config["ssm"]["databases"]["db1"] = {"host": "db1.example.com"}
    output_file = tmp_path / "export.json"

    manager.export_config(str(output_file))

    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert "db1" in data["databases"]


@pytest.mark.unit
def test_export_config_empty(mock_config, manager, tmp_path):
    """export_config with no data produces valid empty JSON."""
    output_file = tmp_path / "export.json"

    manager.export_config(str(output_file))

    data = json.loads(output_file.read_text())
    assert "databases" in data


# ---------------------------------------------------------------------------
# import_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_import_config_file_not_found(manager):
    """import_config raises FileNotFoundError for a missing file (line 119)."""
    with pytest.raises(FileNotFoundError):
        manager.import_config("/nonexistent/path/config.json")


@pytest.mark.unit
def test_import_config_replace(mock_config, manager, mocker, tmp_path):
    """import_config with merge=False replaces the entire ssm config (line 134)."""
    new_data = {"databases": {"imported-db": {"host": "imported.example.com"}}, "instances": {}}
    import_file = tmp_path / "import.json"
    import_file.write_text(json.dumps(new_data))

    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.import_config(str(import_file), merge=False)

    mock_save.assert_called_once()
    saved = mock_save.call_args[0][0]
    assert saved["ssm"] == new_data


@pytest.mark.unit
def test_import_config_merge_databases(mock_config, manager, mocker, tmp_path):
    """import_config with merge=True merges databases into existing config (lines 124-132)."""
    mock_config["ssm"]["databases"]["existing-db"] = {"host": "existing.example.com"}

    new_data = {"databases": {"imported-db": {"host": "imported.example.com"}}}
    import_file = tmp_path / "import.json"
    import_file.write_text(json.dumps(new_data))

    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.import_config(str(import_file), merge=True)

    mock_save.assert_called_once()
    saved = mock_save.call_args[0][0]
    dbs = saved["ssm"]["databases"]
    assert "existing-db" in dbs
    assert "imported-db" in dbs


@pytest.mark.unit
def test_import_config_merge_instances(mock_config, manager, mocker, tmp_path):
    """import_config with merge=True merges instances into existing config."""
    mock_config["ssm"]["instances"]["existing-inst"] = {"instance_id": "i-existing"}

    new_data = {"instances": {"new-inst": {"instance_id": "i-new"}}}
    import_file = tmp_path / "import.json"
    import_file.write_text(json.dumps(new_data))

    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.import_config(str(import_file), merge=True)

    mock_save.assert_called_once()
    saved = mock_save.call_args[0][0]
    insts = saved["ssm"]["instances"]
    assert "existing-inst" in insts
    assert "new-inst" in insts


@pytest.mark.unit
def test_import_config_merge_no_databases_key(mock_config, manager, mocker, tmp_path):
    """import_config merge skips databases key when absent in import file."""
    mock_config["ssm"]["databases"]["existing-db"] = {"host": "existing.example.com"}

    new_data = {"instances": {"new-inst": {"instance_id": "i-new"}}}
    import_file = tmp_path / "import.json"
    import_file.write_text(json.dumps(new_data))

    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.import_config(str(import_file), merge=True)

    saved = mock_save.call_args[0][0]
    # Existing db should still be there
    assert "existing-db" in saved["ssm"]["databases"]


@pytest.mark.unit
def test_import_config_merge_no_instances_key(mock_config, manager, mocker, tmp_path):
    """import_config merge skips instances key when absent in import file."""
    mock_config["ssm"]["instances"]["existing-inst"] = {"instance_id": "i-existing"}

    new_data = {"databases": {"new-db": {"host": "new.example.com"}}}
    import_file = tmp_path / "import.json"
    import_file.write_text(json.dumps(new_data))

    mock_save = mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    manager.import_config(str(import_file), merge=True)

    saved = mock_save.call_args[0][0]
    # Existing instance should still be there
    assert "existing-inst" in saved["ssm"]["instances"]
