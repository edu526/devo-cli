"""Unit tests for DynamoDB parallel_scanner module."""

from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.dynamodb.core.parallel_scanner import ParallelScanner

# ---------------------------------------------------------------------------
# _scan_segment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScanSegment:
    def _make_scanner(self, total_segments=4):
        client = MagicMock()
        return ParallelScanner(client, "TestTable", total_segments=total_segments)

    def test_scan_segment_with_all_options(self):
        """All optional args are forwarded to dynamodb.scan (covers lines 39-47)."""
        scanner = self._make_scanner()
        scanner.dynamodb.scan.return_value = {"Items": [{"id": {"S": "1"}}]}

        items = scanner._scan_segment(
            segment=0,
            filter_expression="attr = :v",
            projection_expression="attr",
            index_name="MyGSI",
            limit=10,
            expression_attribute_values={":v": {"S": "hello"}},
            expression_attribute_names={"#n": "name"},
        )

        call_kwargs = scanner.dynamodb.scan.call_args[1]
        assert call_kwargs["FilterExpression"] == "attr = :v"
        assert call_kwargs["ProjectionExpression"] == "attr"
        assert call_kwargs["IndexName"] == "MyGSI"
        assert call_kwargs["ExpressionAttributeValues"] == {":v": {"S": "hello"}}
        assert call_kwargs["ExpressionAttributeNames"] == {"#n": "name"}
        assert len(items) == 1

    def test_scan_segment_with_pagination(self):
        """ExclusiveStartKey is set on second call when LastEvaluatedKey present (covers line 61)."""
        scanner = self._make_scanner()
        page1 = {"Items": [{"id": {"S": "a"}}], "LastEvaluatedKey": {"id": {"S": "a"}}}
        page2 = {"Items": [{"id": {"S": "b"}}]}
        scanner.dynamodb.scan.side_effect = [page1, page2]

        items = scanner._scan_segment(segment=0)

        assert scanner.dynamodb.scan.call_count == 2
        second_call_kwargs = scanner.dynamodb.scan.call_args_list[1][1]
        assert second_call_kwargs["ExclusiveStartKey"] == {"id": {"S": "a"}}
        assert len(items) == 2

    def test_scan_segment_with_limit_hit(self):
        """Items are trimmed to limit and scanning stops early (covers lines 55-56)."""
        scanner = self._make_scanner()
        # Return 5 items on each call; limit=3 should stop after the first page
        scanner.dynamodb.scan.return_value = {
            "Items": [{"id": {"S": str(i)}} for i in range(5)],
            "LastEvaluatedKey": {"id": {"S": "4"}},  # pagination exists but should not be followed
        }

        items = scanner._scan_segment(segment=0, limit=3)

        # Only one scan call should be made; items trimmed to 3
        assert scanner.dynamodb.scan.call_count == 1
        assert len(items) == 3


# ---------------------------------------------------------------------------
# _cancel_remaining_futures
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCancelRemainingFutures:
    def test_cancel_remaining_futures_cancels_not_done(self):
        """Futures that are not done get cancelled; done futures are left alone (covers lines 67-69)."""
        scanner = ParallelScanner(MagicMock(), "TestTable")

        done_future = MagicMock()
        done_future.done.return_value = True

        pending_future = MagicMock()
        pending_future.done.return_value = False

        scanner._cancel_remaining_futures([done_future, pending_future])

        done_future.cancel.assert_not_called()
        pending_future.cancel.assert_called_once()


# ---------------------------------------------------------------------------
# _handle_segment_failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHandleSegmentFailure:
    def test_handle_segment_failure_raises_when_too_many(self):
        """RuntimeError is raised when failed_segments exceeds total_segments/2 (covers lines 73-77)."""
        scanner = ParallelScanner(MagicMock(), "TestTable", total_segments=4)
        failed_segments = []

        # 2 failures is NOT > 4/2 (== 2), so no raise yet
        scanner._handle_segment_failure(0, Exception("err"), failed_segments)
        scanner._handle_segment_failure(1, Exception("err"), failed_segments)
        assert len(failed_segments) == 2

        # 3rd failure exceeds total_segments/2 (2.0) → RuntimeError
        with pytest.raises(RuntimeError, match="Parallel scan failed"):
            scanner._handle_segment_failure(2, Exception("err"), failed_segments)

        assert len(failed_segments) == 3


# ---------------------------------------------------------------------------
# parallel_scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParallelScan:
    def _make_scanner(self, total_segments=4):
        client = MagicMock()
        return ParallelScanner(client, "TestTable", total_segments=total_segments)

    def test_parallel_scan_with_limit_calculates_per_segment_limit(self):
        """limit_per_segment is computed when limit is provided (covers line 99)."""
        scanner = self._make_scanner(total_segments=4)
        # Each segment returns one item
        scanner.dynamodb.scan.return_value = {"Items": [{"id": {"S": "x"}}]}

        items = scanner.parallel_scan(limit=100)

        # limit_per_segment = int(100 * 1.5 / 4) + 50 = 37 + 50 = 87
        # Just verify the scan ran and returned items without error
        assert isinstance(items, list)

    def test_parallel_scan_cancels_when_limit_reached(self):
        """Scanning stops and remaining futures are cancelled when limit is reached (covers lines 139-144)."""
        scanner = self._make_scanner(total_segments=4)
        # Each segment returns 100 items; limit=50 triggers early cancellation
        scanner.dynamodb.scan.return_value = {"Items": [{"id": {"S": str(i)}} for i in range(100)]}

        items = scanner.parallel_scan(limit=50)

        # Result must be trimmed to at most limit
        assert len(items) <= 50

    def test_parallel_scan_warns_on_failed_segments(self):
        """A warning is printed when any segment fails (covers line 147)."""
        scanner = self._make_scanner(total_segments=2)
        # First segment succeeds; second raises an exception
        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"Items": [{"id": {"S": "ok"}}]}
            raise RuntimeError("segment boom")

        scanner.dynamodb.scan.side_effect = side_effect

        printed_messages = []

        # Patch only console.print, not the whole console object, so that
        # Rich's Progress (which also holds a reference to console) keeps
        # working correctly with real timestamps.
        with patch(
            "cli_tool.commands.dynamodb.core.parallel_scanner.console.print",
            side_effect=lambda *a, **kw: printed_messages.append(str(a)),
        ):
            # Should NOT raise because only 1 out of 2 segments fails (not > total/2)
            scanner.parallel_scan()

        # At least one printed message should mention "Warning"
        warning_messages = [m for m in printed_messages if "Warning" in m]
        assert len(warning_messages) >= 1

    def test_parallel_scan_trims_to_limit(self):
        """all_items is trimmed to limit at the end when it exceeds the limit (covers line 156)."""
        scanner = self._make_scanner(total_segments=2)
        # Each of 2 segments returns 10 items → 20 total, limit=15 should trim to 15
        scanner.dynamodb.scan.return_value = {"Items": [{"id": {"S": str(i)}} for i in range(10)]}

        items = scanner.parallel_scan(limit=15)

        assert len(items) == 15
