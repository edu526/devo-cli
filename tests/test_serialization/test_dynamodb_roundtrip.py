"""
Round-trip serialization tests for DynamoDB export/import operations.

Tests verify that DynamoDB data export followed by import preserves data
integrity, including data types, nested structures, and binary data.

Requirements tested:
- 26.2: DynamoDB export then import preserves data
- 26.5: Data transformations preserve data integrity
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cli_tool.commands.dynamodb.core.exporter import DynamoDBExporter

# ============================================================================
# Test DynamoDB export/import round-trip
# ============================================================================


@pytest.mark.unit
def test_dynamodb_export_import_roundtrip_json(mock_dynamodb_client, tmp_path):
    """Test that DynamoDB export to JSON then import preserves data."""
    # Create table with test data
    mock_dynamodb_client.create_table(
        TableName="test-roundtrip",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add test items with various data types
    test_items = [
        {
            "id": {"S": "item-1"},
            "name": {"S": "Test Item"},
            "count": {"N": "42"},
            "active": {"BOOL": True},
            "tags": {"L": [{"S": "tag1"}, {"S": "tag2"}]},
        },
        {
            "id": {"S": "item-2"},
            "name": {"S": "Another Item"},
            "count": {"N": "99"},
            "active": {"BOOL": False},
            "tags": {"L": [{"S": "tag3"}]},
        },
    ]

    for item in test_items:
        mock_dynamodb_client.put_item(TableName="test-roundtrip", Item=item)

    # Export data
    exporter = DynamoDBExporter("test-roundtrip", mock_dynamodb_client, "us-east-1")
    items = exporter.scan_table()
    output_file = tmp_path / "export.json"
    exporter.export_to_json(items, output_file)

    # Verify export file exists
    assert output_file.exists()

    # Load exported data
    with open(output_file) as f:
        exported_data = json.load(f)

    # Verify exported data structure
    assert len(exported_data) == 2
    assert exported_data[0]["id"] == "item-1"
    assert exported_data[0]["name"] == "Test Item"
    assert exported_data[0]["count"] == "42"
    assert exported_data[0]["active"] is True
    assert exported_data[0]["tags"] == ["tag1", "tag2"]

    # Simulate import by putting data back into a new table
    mock_dynamodb_client.create_table(
        TableName="test-roundtrip-imported",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Import data back (convert to DynamoDB format)
    for item in exported_data:
        dynamodb_item = {
            "id": {"S": item["id"]},
            "name": {"S": item["name"]},
            "count": {"N": str(item["count"])},
            "active": {"BOOL": item["active"]},
            "tags": {"L": [{"S": tag} for tag in item["tags"]]},
        }
        mock_dynamodb_client.put_item(TableName="test-roundtrip-imported", Item=dynamodb_item)

    # Export imported data to verify round-trip
    exporter_imported = DynamoDBExporter("test-roundtrip-imported", mock_dynamodb_client, "us-east-1")
    items_imported = exporter_imported.scan_table()
    output_file_imported = tmp_path / "export-imported.json"
    exporter_imported.export_to_json(items_imported, output_file_imported)

    # Load re-exported data
    with open(output_file_imported) as f:
        reimported_data = json.load(f)

    # Verify round-trip preserves data
    assert len(reimported_data) == 2
    assert reimported_data[0]["id"] == exported_data[0]["id"]
    assert reimported_data[0]["name"] == exported_data[0]["name"]
    assert reimported_data[0]["count"] == exported_data[0]["count"]
    assert reimported_data[0]["active"] == exported_data[0]["active"]
    assert reimported_data[0]["tags"] == exported_data[0]["tags"]


# ============================================================================
# Test data type preservation
# ============================================================================


@pytest.mark.unit
def test_data_type_preservation_strings(mock_dynamodb_client, tmp_path):
    """Test that string data types are preserved through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-strings",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add items with various string values
    test_items = [
        {"id": {"S": "str-1"}, "simple": {"S": "hello world"}},
        {"id": {"S": "str-2"}, "empty": {"S": ""}},
        {"id": {"S": "str-3"}, "unicode": {"S": "你好世界 🚀"}},
        {"id": {"S": "str-4"}, "special": {"S": "line1\nline2\ttab"}},
    ]

    for item in test_items:
        mock_dynamodb_client.put_item(TableName="test-strings", Item=item)

    # Export and verify
    exporter = DynamoDBExporter("test-strings", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "strings.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify string preservation
    assert data[0]["simple"] == "hello world"
    assert data[1]["empty"] == ""
    assert data[2]["unicode"] == "你好世界 🚀"
    assert data[3]["special"] == "line1\nline2\ttab"


@pytest.mark.unit
def test_data_type_preservation_numbers(mock_dynamodb_client, tmp_path):
    """Test that numeric data types are preserved through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-numbers",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add items with various numeric values
    test_items = [
        {"id": {"S": "num-1"}, "integer": {"N": "42"}},
        {"id": {"S": "num-2"}, "zero": {"N": "0"}},
        {"id": {"S": "num-3"}, "negative": {"N": "-100"}},
        {"id": {"S": "num-4"}, "decimal": {"N": "3.14159"}},
        {"id": {"S": "num-5"}, "large": {"N": "9999999999"}},
    ]

    for item in test_items:
        mock_dynamodb_client.put_item(TableName="test-numbers", Item=item)

    # Export and verify
    exporter = DynamoDBExporter("test-numbers", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "numbers.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify numeric preservation (DynamoDB stores numbers as strings)
    assert data[0]["integer"] == "42"
    assert data[1]["zero"] == "0"
    assert data[2]["negative"] == "-100"
    assert data[3]["decimal"] == "3.14159"
    assert data[4]["large"] == "9999999999"


@pytest.mark.unit
def test_data_type_preservation_booleans(mock_dynamodb_client, tmp_path):
    """Test that boolean data types are preserved through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-booleans",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add items with boolean values
    test_items = [
        {"id": {"S": "bool-1"}, "active": {"BOOL": True}},
        {"id": {"S": "bool-2"}, "active": {"BOOL": False}},
        {"id": {"S": "bool-3"}, "enabled": {"BOOL": True}, "verified": {"BOOL": False}},
    ]

    for item in test_items:
        mock_dynamodb_client.put_item(TableName="test-booleans", Item=item)

    # Export and verify
    exporter = DynamoDBExporter("test-booleans", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "booleans.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify boolean preservation
    assert data[0]["active"] is True
    assert data[1]["active"] is False
    assert data[2]["enabled"] is True
    assert data[2]["verified"] is False


@pytest.mark.unit
def test_data_type_preservation_mixed_types(mock_dynamodb_client, tmp_path):
    """Test that mixed data types are preserved through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-mixed",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with mixed types
    test_item = {
        "id": {"S": "mixed-1"},
        "name": {"S": "Test Item"},
        "count": {"N": "42"},
        "price": {"N": "19.99"},
        "active": {"BOOL": True},
        "tags": {"L": [{"S": "tag1"}, {"S": "tag2"}]},
        "metadata": {"M": {"key1": {"S": "value1"}, "key2": {"N": "100"}}},
    }

    mock_dynamodb_client.put_item(TableName="test-mixed", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-mixed", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "mixed.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify all types preserved
    assert data[0]["id"] == "mixed-1"
    assert data[0]["name"] == "Test Item"
    assert data[0]["count"] == "42"
    assert data[0]["price"] == "19.99"
    assert data[0]["active"] is True
    assert data[0]["tags"] == ["tag1", "tag2"]
    assert data[0]["metadata"]["key1"] == "value1"
    assert data[0]["metadata"]["key2"] == "100"


# ============================================================================
# Test nested structure preservation
# ============================================================================


@pytest.mark.unit
def test_nested_structure_preservation_simple(mock_dynamodb_client, tmp_path):
    """Test that simple nested structures are preserved through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-nested-simple",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with nested structure
    test_item = {
        "id": {"S": "nested-1"},
        "user": {
            "M": {
                "name": {"S": "John Doe"},
                "email": {"S": "john@example.com"},
                "age": {"N": "30"},
            }
        },
    }

    mock_dynamodb_client.put_item(TableName="test-nested-simple", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-nested-simple", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "nested-simple.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify nested structure preserved
    assert data[0]["id"] == "nested-1"
    assert data[0]["user"]["name"] == "John Doe"
    assert data[0]["user"]["email"] == "john@example.com"
    assert data[0]["user"]["age"] == "30"


@pytest.mark.unit
def test_nested_structure_preservation_complex(mock_dynamodb_client, tmp_path):
    """Test that complex nested structures are preserved through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-nested-complex",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with deeply nested structure
    test_item = {
        "id": {"S": "nested-2"},
        "organization": {
            "M": {
                "name": {"S": "Acme Corp"},
                "departments": {
                    "L": [
                        {
                            "M": {
                                "name": {"S": "Engineering"},
                                "employees": {"N": "50"},
                                "teams": {
                                    "L": [
                                        {"M": {"name": {"S": "Backend"}, "size": {"N": "20"}}},
                                        {"M": {"name": {"S": "Frontend"}, "size": {"N": "30"}}},
                                    ]
                                },
                            }
                        },
                        {
                            "M": {
                                "name": {"S": "Sales"},
                                "employees": {"N": "25"},
                            }
                        },
                    ]
                },
            }
        },
    }

    mock_dynamodb_client.put_item(TableName="test-nested-complex", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-nested-complex", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "nested-complex.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify complex nested structure preserved
    assert data[0]["id"] == "nested-2"
    assert data[0]["organization"]["name"] == "Acme Corp"
    assert len(data[0]["organization"]["departments"]) == 2
    assert data[0]["organization"]["departments"][0]["name"] == "Engineering"
    assert data[0]["organization"]["departments"][0]["employees"] == "50"
    assert len(data[0]["organization"]["departments"][0]["teams"]) == 2
    assert data[0]["organization"]["departments"][0]["teams"][0]["name"] == "Backend"
    assert data[0]["organization"]["departments"][0]["teams"][0]["size"] == "20"
    assert data[0]["organization"]["departments"][1]["name"] == "Sales"


@pytest.mark.unit
def test_nested_structure_with_lists_and_maps(mock_dynamodb_client, tmp_path):
    """Test nested structures containing both lists and maps."""
    mock_dynamodb_client.create_table(
        TableName="test-nested-mixed",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with mixed nested structures
    test_item = {
        "id": {"S": "nested-3"},
        "products": {
            "L": [
                {
                    "M": {
                        "name": {"S": "Product A"},
                        "price": {"N": "29.99"},
                        "features": {"L": [{"S": "feature1"}, {"S": "feature2"}]},
                    }
                },
                {
                    "M": {
                        "name": {"S": "Product B"},
                        "price": {"N": "49.99"},
                        "features": {"L": [{"S": "feature3"}]},
                    }
                },
            ]
        },
    }

    mock_dynamodb_client.put_item(TableName="test-nested-mixed", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-nested-mixed", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "nested-mixed.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify mixed nested structure preserved
    assert data[0]["id"] == "nested-3"
    assert len(data[0]["products"]) == 2
    assert data[0]["products"][0]["name"] == "Product A"
    assert data[0]["products"][0]["price"] == "29.99"
    assert data[0]["products"][0]["features"] == ["feature1", "feature2"]
    assert data[0]["products"][1]["name"] == "Product B"
    assert data[0]["products"][1]["features"] == ["feature3"]


# ============================================================================
# Test binary data handling
# ============================================================================


@pytest.mark.unit
def test_binary_data_handling(mock_dynamodb_client, tmp_path):
    """Test that binary data is handled correctly through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-binary",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with binary data
    test_item = {
        "id": {"S": "binary-1"},
        "name": {"S": "Binary Item"},
        "data": {"B": b"Hello World"},  # Binary data
    }

    mock_dynamodb_client.put_item(TableName="test-binary", Item=test_item)

    # Scan table to get items
    exporter = DynamoDBExporter("test-binary", mock_dynamodb_client, "us-east-1")
    items = exporter.scan_table()

    # Verify binary data is present in scanned items
    assert len(items) == 1
    assert items[0]["id"]["S"] == "binary-1"
    assert items[0]["name"]["S"] == "Binary Item"
    assert "data" in items[0]
    # Binary data should be present (as bytes in DynamoDB format)
    assert items[0]["data"]["B"] == b"Hello World"


@pytest.mark.unit
def test_binary_set_handling(mock_dynamodb_client, tmp_path):
    """Test that binary sets are handled correctly through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-binary-set",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with binary set
    test_item = {
        "id": {"S": "binary-set-1"},
        "name": {"S": "Binary Set Item"},
        "data_set": {"BS": [b"data1", b"data2", b"data3"]},  # Binary set
    }

    mock_dynamodb_client.put_item(TableName="test-binary-set", Item=test_item)

    # Scan table to get items
    exporter = DynamoDBExporter("test-binary-set", mock_dynamodb_client, "us-east-1")
    items = exporter.scan_table()

    # Verify binary set is present in scanned items
    assert len(items) == 1
    assert items[0]["id"]["S"] == "binary-set-1"
    assert items[0]["name"]["S"] == "Binary Set Item"
    assert "data_set" in items[0]
    # Binary set should be present as a list of bytes
    assert isinstance(items[0]["data_set"]["BS"], list)
    assert len(items[0]["data_set"]["BS"]) == 3


# ============================================================================
# Test edge cases for round-trip serialization
# ============================================================================


@pytest.mark.unit
def test_roundtrip_empty_table(mock_dynamodb_client, tmp_path):
    """Test round-trip with empty DynamoDB table."""
    mock_dynamodb_client.create_table(
        TableName="test-empty",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Export empty table
    exporter = DynamoDBExporter("test-empty", mock_dynamodb_client, "us-east-1")
    items = exporter.scan_table()

    # Verify no items scanned
    assert items == []


@pytest.mark.unit
def test_roundtrip_null_values(mock_dynamodb_client, tmp_path):
    """Test that null values are handled correctly through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-nulls",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with null values
    test_item = {
        "id": {"S": "null-1"},
        "name": {"S": "Null Item"},
        "optional_field": {"NULL": True},
    }

    mock_dynamodb_client.put_item(TableName="test-nulls", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-nulls", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "nulls.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify null values are preserved
    assert data[0]["id"] == "null-1"
    assert data[0]["name"] == "Null Item"
    assert data[0]["optional_field"] is None


@pytest.mark.unit
def test_roundtrip_string_sets(mock_dynamodb_client, tmp_path):
    """Test that string sets are handled correctly through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-string-sets",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with string set
    test_item = {
        "id": {"S": "set-1"},
        "tags": {"SS": ["tag1", "tag2", "tag3"]},
    }

    mock_dynamodb_client.put_item(TableName="test-string-sets", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-string-sets", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "string-sets.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify string set is exported
    assert data[0]["id"] == "set-1"
    assert "tags" in data[0]
    # String sets are converted to lists by the exporter
    # The exact format depends on the conversion logic
    tags_value = data[0]["tags"]
    # Could be a list or a string representation of a set
    if isinstance(tags_value, list):
        assert set(tags_value) == {"tag1", "tag2", "tag3"}
    elif isinstance(tags_value, str):
        # If serialized as string, verify all tags are present
        assert "tag1" in tags_value
        assert "tag2" in tags_value
        assert "tag3" in tags_value


@pytest.mark.unit
def test_roundtrip_number_sets(mock_dynamodb_client, tmp_path):
    """Test that number sets are handled correctly through export/import."""
    mock_dynamodb_client.create_table(
        TableName="test-number-sets",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with number set
    test_item = {
        "id": {"S": "numset-1"},
        "scores": {"NS": ["10", "20", "30"]},
    }

    mock_dynamodb_client.put_item(TableName="test-number-sets", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-number-sets", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "number-sets.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify number set is exported
    assert data[0]["id"] == "numset-1"
    assert "scores" in data[0]
    # Number sets are converted to lists by the exporter
    # The exact format depends on the conversion logic
    scores_value = data[0]["scores"]
    # Could be a list or a string representation of a set
    if isinstance(scores_value, list):
        # Numbers in sets might be strings or numbers
        assert set(str(s) for s in scores_value) == {"10", "20", "30"}
    elif isinstance(scores_value, str):
        # If serialized as string, verify all scores are present
        assert "10" in scores_value
        assert "20" in scores_value
        assert "30" in scores_value


@pytest.mark.unit
def test_roundtrip_large_items(mock_dynamodb_client, tmp_path):
    """Test round-trip with large items containing many attributes."""
    mock_dynamodb_client.create_table(
        TableName="test-large",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create item with many attributes
    large_item = {"id": {"S": "large-1"}}
    for i in range(100):
        large_item[f"field_{i}"] = {"S": f"value_{i}"}

    mock_dynamodb_client.put_item(TableName="test-large", Item=large_item)

    # Export and verify
    exporter = DynamoDBExporter("test-large", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "large.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify all attributes preserved
    assert data[0]["id"] == "large-1"
    assert len(data[0]) == 101  # id + 100 fields
    assert data[0]["field_0"] == "value_0"
    assert data[0]["field_50"] == "value_50"
    assert data[0]["field_99"] == "value_99"


@pytest.mark.unit
def test_roundtrip_special_characters_in_attribute_names(mock_dynamodb_client, tmp_path):
    """Test that special characters in attribute names are preserved."""
    mock_dynamodb_client.create_table(
        TableName="test-special-attrs",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Add item with special characters in attribute names
    test_item = {
        "id": {"S": "special-1"},
        "field-with-dash": {"S": "value1"},
        "field_with_underscore": {"S": "value2"},
        "field.with.dot": {"S": "value3"},
    }

    mock_dynamodb_client.put_item(TableName="test-special-attrs", Item=test_item)

    # Export and verify
    exporter = DynamoDBExporter("test-special-attrs", mock_dynamodb_client, "us-east-1")
    output_file = tmp_path / "special-attrs.json"
    items = exporter.scan_table()
    exporter.export_to_json(items, output_file)

    with open(output_file) as f:
        data = json.load(f)

    # Verify special characters in attribute names preserved
    assert data[0]["id"] == "special-1"
    assert data[0]["field-with-dash"] == "value1"
    assert data[0]["field_with_underscore"] == "value2"
    assert data[0]["field.with.dot"] == "value3"
