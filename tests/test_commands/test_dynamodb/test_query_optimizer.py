"""Unit tests for DynamoDB query_optimizer module."""

import pytest

from cli_tool.commands.dynamodb.core.query_optimizer import (
    detect_usable_index,
    should_use_parallel_scan,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_table_info(
    gsi_list=None,
    key_schema=None,
):
    """Build a minimal table_info dict."""
    return {
        "global_indexes": gsi_list or [],
        "key_schema": key_schema or [],
    }


def _make_gsi(index_name, hash_key, status="ACTIVE"):
    return {
        "IndexName": index_name,
        "IndexStatus": status,
        "KeySchema": [{"AttributeName": hash_key, "KeyType": "HASH"}],
    }


# ---------------------------------------------------------------------------
# detect_usable_index
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectUsableIndex:
    def test_detect_usable_index_no_filter(self):
        """None/empty filter expression returns None immediately (covers line 23)."""
        assert detect_usable_index(None, None, {}) is None
        assert detect_usable_index("", None, {}) is None

    def test_detect_usable_index_with_or_and_no_equality(self):
        """OR filter without any equality condition hits line 55 (returns None)."""
        # An OR expression with no "attr = :val" pattern
        result = detect_usable_index(
            "begins_with(#n, :v) OR contains(#n, :w)",
            {"#n": "name"},
            _make_table_info(),
        )
        assert result is None

    def test_detect_or_inactive_gsi(self):
        """An inactive GSI is skipped in the OR path (covers line 63)."""
        gsi = _make_gsi("MyIndex", "userId", status="CREATING")
        table_info = _make_table_info(gsi_list=[gsi])

        result = detect_usable_index(
            "userId = :uid OR age = :a",
            None,
            table_info,
        )
        # GSI is inactive and there is no matching main-table key → None
        assert result is None

    def test_detect_or_main_table_key_match(self):
        """OR filter where equality matches the main table partition key (covers line 88)."""
        table_info = _make_table_info(key_schema=[{"AttributeName": "userId", "KeyType": "HASH"}])

        result = detect_usable_index(
            "userId = :uid OR status = :s",
            None,
            table_info,
        )

        assert result is not None
        assert result["has_or"] is True
        attrs = result["indexed_attributes"]
        assert any(a["key_attribute"] == "userId" and a["index_name"] is None for a in attrs)

    def test_detect_or_no_indexed_attrs_returns_none(self):
        """OR expression with equality but no matching index returns None (covers line 104)."""
        table_info = _make_table_info(
            gsi_list=[_make_gsi("OtherIndex", "tenantId")],
            key_schema=[{"AttributeName": "orderId", "KeyType": "HASH"}],
        )

        # Neither "userId" nor "age" matches any key
        result = detect_usable_index(
            "userId = :u OR age = :a",
            None,
            table_info,
        )
        assert result is None

    def test_detect_single_inactive_gsi(self):
        """Inactive GSI is skipped in single-attribute path (covers line 132)."""
        gsi = _make_gsi("MyIndex", "email", status="DELETING")
        table_info = _make_table_info(gsi_list=[gsi])

        result = detect_usable_index(
            "email = :e",
            None,
            table_info,
        )
        # GSI inactive, no main-table key → None
        assert result is None

    def test_detect_single_main_table_key_match(self):
        """Single equality on the main table partition key is detected (covers lines 162-170)."""
        table_info = _make_table_info(key_schema=[{"AttributeName": "customerId", "KeyType": "HASH"}])

        result = detect_usable_index(
            "customerId = :cid",
            None,
            table_info,
        )

        assert result is not None
        assert result["has_or"] is False
        assert result["index_name"] is None
        assert result["key_attribute"] == "customerId"
        assert "customerId = :cid" in result["key_condition"]


# ---------------------------------------------------------------------------
# should_use_parallel_scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShouldUseParallelScan:
    def test_use_parallel_500k_to_1m(self):
        """Explicit parallel=True with 500k–1M items returns (True, 12) (covers line 227)."""
        result = should_use_parallel_scan(600_000, use_parallel=True)
        assert result == (True, 12)

    def test_use_parallel_100k_to_500k(self):
        """Explicit parallel=True with 100k–500k items returns (True, 8) (covers line 229)."""
        result = should_use_parallel_scan(200_000, use_parallel=True)
        assert result == (True, 8)

    def test_auto_parallel_500k_to_1m(self):
        """Auto mode with 500k–1M items enables parallel with 12 segments (covers line 235)."""
        result = should_use_parallel_scan(600_000, use_parallel=False)
        assert result == (True, 12)

    def test_auto_parallel_100k_to_500k(self):
        """Auto mode with 100k–500k items enables parallel with 8 segments (covers line 237)."""
        result = should_use_parallel_scan(200_000, use_parallel=False)
        assert result == (True, 8)

    def test_no_parallel_small_table(self):
        """Auto mode with small table returns (False, 4) (covers line 240)."""
        result = should_use_parallel_scan(1_000, use_parallel=False)
        assert result == (False, 4)

    def test_use_parallel_over_1m(self):
        """Explicit parallel=True with >1M items returns (True, 16) (covers line 225)."""
        result = should_use_parallel_scan(1_500_000, use_parallel=True)
        assert result == (True, 16)

    def test_use_parallel_under_100k(self):
        """Explicit parallel=True with <=100k items returns (True, 4) (covers line 230)."""
        result = should_use_parallel_scan(50_000, use_parallel=True)
        assert result == (True, 4)

    def test_auto_parallel_over_1m(self):
        """Auto mode with >1M items enables parallel with 16 segments (covers line 234)."""
        result = should_use_parallel_scan(1_500_000, use_parallel=False)
        assert result == (True, 16)
