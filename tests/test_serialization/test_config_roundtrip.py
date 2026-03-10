"""
Round-trip serialization tests for configuration management.

Tests verify that configuration export followed by import produces equivalent
configuration, ensuring data integrity through serialization cycles.

Requirements tested:
- 26.1: Config export then import produces equivalent config
- 26.3: JSON serialization round-trip for all config types
"""

import json
from pathlib import Path

import pytest

from cli_tool.core.utils.config_manager import (
    export_config,
    get_config_value,
    import_config,
    load_config,
    save_config,
)

# ============================================================================
# Test config export/import round-trip
# ============================================================================


@pytest.mark.unit
def test_config_export_import_roundtrip_full(temp_config_dir, mocker):
    """Test that full config export then import produces equivalent config."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create a comprehensive test config
    original_config = {
        "bedrock": {
            "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "fallback_model_id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "region": "us-east-1",
        },
        "codeartifact": {"region": "us-west-2", "domain": "test-domain"},
        "version_check": {"enabled": True, "last_check": 1234567890},
        "ssm": {
            "databases": {
                "prod-db": {
                    "instance_id": "i-1234567890abcdef0",
                    "local_port": 5432,
                    "remote_port": 5432,
                    "host": "prod-db.example.com",
                }
            },
            "instances": {"web-server": {"instance_id": "i-abcdef1234567890"}},
        },
        "dynamodb": {
            "export_templates": {
                "users-export": {
                    "table_name": "users",
                    "format": "json",
                    "filter_expression": "active = :val",
                }
            }
        },
    }

    save_config(original_config)

    # Export config to file
    export_file = temp_config_dir / "export.json"
    exported = export_config(output_path=str(export_file))

    # Clear current config
    save_config({})

    # Import config back
    import_config(str(export_file), merge=False)

    # Load and verify - compare with exported data (not original, since load_config merges with defaults)
    restored_config = load_config()

    # Verify key sections match the exported data
    assert restored_config["bedrock"]["model_id"] == exported["bedrock"]["model_id"]
    assert restored_config["ssm"]["databases"] == exported["ssm"]["databases"]
    assert restored_config["ssm"]["instances"] == exported["ssm"]["instances"]
    assert restored_config["dynamodb"]["export_templates"] == exported["dynamodb"]["export_templates"]


@pytest.mark.unit
def test_config_export_import_roundtrip_partial_sections(temp_config_dir, mocker):
    """Test that partial config export/import preserves selected sections."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create initial config
    original_config = {
        "bedrock": {"model_id": "original-model", "region": "us-east-1"},
        "ssm": {"databases": {"db1": {"instance_id": "i-original"}}, "instances": {}},
    }

    save_config(original_config)

    # Export only SSM section
    export_file = temp_config_dir / "ssm-export.json"
    exported_ssm = export_config(sections=["ssm"], output_path=str(export_file))

    # Modify SSM section
    modified_config = original_config.copy()
    modified_config["ssm"] = {"databases": {}, "instances": {}}
    save_config(modified_config)

    # Import SSM section back
    import_config(str(export_file), sections=["ssm"], merge=False)

    # Verify SSM section was restored
    restored_config = load_config()
    assert restored_config["ssm"]["databases"] == exported_ssm["ssm"]["databases"]
    # Other sections should remain unchanged
    assert restored_config["bedrock"]["model_id"] == "original-model"


@pytest.mark.unit
def test_config_export_import_roundtrip_with_merge(temp_config_dir, mocker):
    """Test that config import with merge preserves existing data."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create initial config
    initial_config = {
        "bedrock": {"model_id": "initial-model", "region": "us-east-1"},
    }
    save_config(initial_config)

    # Export config
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))

    # Modify config (add new keys)
    modified_config = load_config()
    modified_config["bedrock"]["new_key"] = "new_value"
    save_config(modified_config)

    # Import with merge (should preserve new keys)
    import_config(str(export_file), merge=True)

    # Verify merge behavior
    restored_config = load_config()
    # Original values should be restored
    assert restored_config["bedrock"]["model_id"] == "initial-model"
    # New keys should be preserved (deep merge)
    assert restored_config["bedrock"]["new_key"] == "new_value"


# ============================================================================
# Test JSON serialization round-trip for all config types
# ============================================================================


@pytest.mark.unit
def test_json_roundtrip_string_values(temp_config_dir, mocker):
    """Test JSON round-trip for string configuration values."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "strings": {
            "simple": "hello world",
            "with_spaces": "  leading and trailing  ",
            "with_newlines": "line1\nline2\nline3",
            "with_tabs": "col1\tcol2\tcol3",
            "empty": "",
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify all string values preserved
    restored = load_config()
    assert restored["strings"]["simple"] == "hello world"
    assert restored["strings"]["with_spaces"] == "  leading and trailing  "
    assert restored["strings"]["with_newlines"] == "line1\nline2\nline3"
    assert restored["strings"]["with_tabs"] == "col1\tcol2\tcol3"
    assert restored["strings"]["empty"] == ""


@pytest.mark.unit
def test_json_roundtrip_numeric_values(temp_config_dir, mocker):
    """Test JSON round-trip for numeric configuration values."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "numbers": {
            "integer": 42,
            "zero": 0,
            "negative": -100,
            "float": 3.14159,
            "large": 9999999999,
            "scientific": 1.23e10,
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify all numeric values preserved
    restored = load_config()
    assert restored["numbers"]["integer"] == 42
    assert restored["numbers"]["zero"] == 0
    assert restored["numbers"]["negative"] == -100
    assert restored["numbers"]["float"] == 3.14159
    assert restored["numbers"]["large"] == 9999999999
    assert restored["numbers"]["scientific"] == 1.23e10


@pytest.mark.unit
def test_json_roundtrip_boolean_values(temp_config_dir, mocker):
    """Test JSON round-trip for boolean configuration values."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "booleans": {
            "true_value": True,
            "false_value": False,
            "nested": {"enabled": True, "disabled": False},
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify all boolean values preserved
    restored = load_config()
    assert restored["booleans"]["true_value"] is True
    assert restored["booleans"]["false_value"] is False
    assert restored["booleans"]["nested"]["enabled"] is True
    assert restored["booleans"]["nested"]["disabled"] is False


@pytest.mark.unit
def test_json_roundtrip_null_values(temp_config_dir, mocker):
    """Test JSON round-trip for null/None configuration values."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "nulls": {
            "explicit_none": None,
            "nested": {"value": None, "other": "not-none"},
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify None values preserved
    restored = load_config()
    assert restored["nulls"]["explicit_none"] is None
    assert restored["nulls"]["nested"]["value"] is None
    assert restored["nulls"]["nested"]["other"] == "not-none"


@pytest.mark.unit
def test_json_roundtrip_array_values(temp_config_dir, mocker):
    """Test JSON round-trip for array/list configuration values."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "arrays": {
            "strings": ["one", "two", "three"],
            "numbers": [1, 2, 3, 4, 5],
            "mixed": [1, "two", 3.0, True, None],
            "empty": [],
            "nested": [[1, 2], [3, 4], [5, 6]],
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify all array values preserved
    restored = load_config()
    assert restored["arrays"]["strings"] == ["one", "two", "three"]
    assert restored["arrays"]["numbers"] == [1, 2, 3, 4, 5]
    assert restored["arrays"]["mixed"] == [1, "two", 3.0, True, None]
    assert restored["arrays"]["empty"] == []
    assert restored["arrays"]["nested"] == [[1, 2], [3, 4], [5, 6]]


@pytest.mark.unit
def test_json_roundtrip_mixed_types(temp_config_dir, mocker):
    """Test JSON round-trip for configuration with mixed data types."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "mixed": {
            "string": "text",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify all mixed types preserved
    restored = load_config()
    assert restored["mixed"]["string"] == "text"
    assert restored["mixed"]["number"] == 42
    assert restored["mixed"]["float"] == 3.14
    assert restored["mixed"]["boolean"] is True
    assert restored["mixed"]["null"] is None
    assert restored["mixed"]["array"] == [1, 2, 3]
    assert restored["mixed"]["object"] == {"nested": "value"}


# ============================================================================
# Test nested config structure preservation
# ============================================================================


@pytest.mark.unit
def test_nested_structure_preservation_simple(temp_config_dir, mocker):
    """Test that simple nested structures are preserved through round-trip."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {"level1": {"level2": {"level3": {"value": "deep"}}}}

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify nested structure preserved
    restored = load_config()
    assert restored["level1"]["level2"]["level3"]["value"] == "deep"


@pytest.mark.unit
def test_nested_structure_preservation_complex(temp_config_dir, mocker):
    """Test that complex nested structures are preserved through round-trip."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "aws": {
            "regions": {
                "us-east-1": {
                    "services": {
                        "dynamodb": {"tables": ["users", "orders"]},
                        "s3": {"buckets": ["data", "logs"]},
                    }
                },
                "us-west-2": {
                    "services": {
                        "ec2": {"instances": ["i-123", "i-456"]},
                    }
                },
            }
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify complex nested structure preserved
    restored = load_config()
    assert restored["aws"]["regions"]["us-east-1"]["services"]["dynamodb"]["tables"] == ["users", "orders"]
    assert restored["aws"]["regions"]["us-east-1"]["services"]["s3"]["buckets"] == ["data", "logs"]
    assert restored["aws"]["regions"]["us-west-2"]["services"]["ec2"]["instances"] == ["i-123", "i-456"]


@pytest.mark.unit
def test_nested_structure_with_arrays_and_objects(temp_config_dir, mocker):
    """Test nested structures containing both arrays and objects."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "profiles": [
            {"name": "dev", "settings": {"region": "us-east-1", "debug": True}},
            {"name": "prod", "settings": {"region": "us-west-2", "debug": False}},
        ]
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify nested structure with arrays and objects preserved
    restored = load_config()
    assert len(restored["profiles"]) == 2
    assert restored["profiles"][0]["name"] == "dev"
    assert restored["profiles"][0]["settings"]["region"] == "us-east-1"
    assert restored["profiles"][0]["settings"]["debug"] is True
    assert restored["profiles"][1]["name"] == "prod"
    assert restored["profiles"][1]["settings"]["region"] == "us-west-2"
    assert restored["profiles"][1]["settings"]["debug"] is False


# ============================================================================
# Test special characters in config values
# ============================================================================


@pytest.mark.unit
def test_special_characters_unicode(temp_config_dir, mocker):
    """Test that Unicode characters are preserved through round-trip."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "unicode": {
            "chinese": "你好世界",
            "japanese": "こんにちは",
            "emoji": "🚀🎯🔥",
            "mixed": "Hello 世界 🌍",
            "arabic": "مرحبا",
            "cyrillic": "Привет",
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify Unicode characters preserved
    restored = load_config()
    assert restored["unicode"]["chinese"] == "你好世界"
    assert restored["unicode"]["japanese"] == "こんにちは"
    assert restored["unicode"]["emoji"] == "🚀🎯🔥"
    assert restored["unicode"]["mixed"] == "Hello 世界 🌍"
    assert restored["unicode"]["arabic"] == "مرحبا"
    assert restored["unicode"]["cyrillic"] == "Привет"


@pytest.mark.unit
def test_special_characters_escape_sequences(temp_config_dir, mocker):
    """Test that escape sequences are preserved through round-trip."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "escapes": {
            "newline": "line1\nline2",
            "tab": "col1\tcol2",
            "carriage_return": "text\rmore",
            "backslash": "path\\to\\file",
            "quote": 'He said "hello"',
            "single_quote": "It's working",
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify escape sequences preserved
    restored = load_config()
    assert restored["escapes"]["newline"] == "line1\nline2"
    assert restored["escapes"]["tab"] == "col1\tcol2"
    assert restored["escapes"]["carriage_return"] == "text\rmore"
    assert restored["escapes"]["backslash"] == "path\\to\\file"
    assert restored["escapes"]["quote"] == 'He said "hello"'
    assert restored["escapes"]["single_quote"] == "It's working"


@pytest.mark.unit
def test_special_characters_in_keys(temp_config_dir, mocker):
    """Test that special characters in keys are preserved through round-trip."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "section-with-dash": {"value": "dash"},
        "section_with_underscore": {"value": "underscore"},
        "section:with:colon": {"value": "colon"},
        "section@with@at": {"value": "at"},
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify special characters in keys preserved
    restored = load_config()
    assert restored["section-with-dash"]["value"] == "dash"
    assert restored["section_with_underscore"]["value"] == "underscore"
    assert restored["section:with:colon"]["value"] == "colon"
    assert restored["section@with@at"]["value"] == "at"


@pytest.mark.unit
def test_special_characters_whitespace(temp_config_dir, mocker):
    """Test that various whitespace characters are preserved through round-trip."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "whitespace": {
            "leading": "   text",
            "trailing": "text   ",
            "both": "   text   ",
            "multiple_spaces": "word1    word2",
            "mixed": " \t text \n more \r\n end ",
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify whitespace preserved
    restored = load_config()
    assert restored["whitespace"]["leading"] == "   text"
    assert restored["whitespace"]["trailing"] == "text   "
    assert restored["whitespace"]["both"] == "   text   "
    assert restored["whitespace"]["multiple_spaces"] == "word1    word2"
    assert restored["whitespace"]["mixed"] == " \t text \n more \r\n end "


@pytest.mark.unit
def test_special_characters_json_control_characters(temp_config_dir, mocker):
    """Test that JSON control characters are properly escaped and preserved."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {
        "control": {
            "quotes": 'Text with "quotes" inside',
            "backslash": "Path\\with\\backslashes",
            "forward_slash": "url/path/to/resource",
            "braces": "Object {key: value}",
            "brackets": "Array [1, 2, 3]",
        }
    }

    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify control characters preserved
    restored = load_config()
    assert restored["control"]["quotes"] == 'Text with "quotes" inside'
    assert restored["control"]["backslash"] == "Path\\with\\backslashes"
    assert restored["control"]["forward_slash"] == "url/path/to/resource"
    assert restored["control"]["braces"] == "Object {key: value}"
    assert restored["control"]["brackets"] == "Array [1, 2, 3]"


# ============================================================================
# Test edge cases for round-trip serialization
# ============================================================================


@pytest.mark.unit
def test_roundtrip_empty_config(temp_config_dir, mocker):
    """Test round-trip with empty configuration."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    test_config = {}
    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    exported = export_config(output_path=str(export_file))

    # Note: export_config calls load_config which merges with defaults
    # So exported will contain defaults, not an empty dict
    # The key test is that the round-trip preserves the data

    save_config({"temp": "data"})  # Add temp data
    import_config(str(export_file), merge=False)

    # Verify that after import, we get back the exported data
    restored = load_config()
    # Compare key sections to verify round-trip integrity
    assert restored["bedrock"] == exported["bedrock"]


@pytest.mark.unit
def test_roundtrip_very_large_config(temp_config_dir, mocker):
    """Test round-trip with very large configuration."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create large config with many entries
    test_config = {"large_section": {f"key_{i}": f"value_{i}" for i in range(1000)}}
    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    export_config(output_path=str(export_file))
    save_config({})
    import_config(str(export_file), merge=False)

    # Verify large config preserved
    restored = load_config()
    assert len(restored["large_section"]) == 1000
    assert restored["large_section"]["key_0"] == "value_0"
    assert restored["large_section"]["key_500"] == "value_500"
    assert restored["large_section"]["key_999"] == "value_999"


@pytest.mark.unit
def test_roundtrip_preserves_key_order(temp_config_dir, mocker):
    """Test that round-trip preserves key order (Python 3.7+ dict ordering)."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Use a custom section that won't be affected by defaults
    test_config = {
        "custom_section": {
            "z_last": "value_z",
            "a_first": "value_a",
            "m_middle": "value_m",
        }
    }
    save_config(test_config)

    # Export and import
    export_file = temp_config_dir / "export.json"
    exported = export_config(output_path=str(export_file))

    # Verify key order in the custom section
    custom_keys = list(exported["custom_section"].keys())
    assert custom_keys == ["z_last", "a_first", "m_middle"]

    save_config({})
    import_config(str(export_file), merge=False)

    # Verify key order preserved after round-trip
    restored = load_config()
    restored_keys = list(restored["custom_section"].keys())
    assert restored_keys == ["z_last", "a_first", "m_middle"]


@pytest.mark.unit
def test_roundtrip_multiple_cycles(temp_config_dir, mocker):
    """Test that multiple export/import cycles preserve data integrity."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    original_config = {
        "bedrock": {"model_id": "test-model", "region": "us-east-1"},
    }
    save_config(original_config)

    # Perform multiple export/import cycles
    for i in range(5):
        export_file = temp_config_dir / f"export_{i}.json"
        export_config(output_path=str(export_file))
        save_config({})
        import_config(str(export_file), merge=False)

    # Verify config values are preserved after multiple cycles
    final_config = load_config()
    assert final_config["bedrock"]["model_id"] == original_config["bedrock"]["model_id"]
    assert final_config["bedrock"]["region"] == original_config["bedrock"]["region"]
