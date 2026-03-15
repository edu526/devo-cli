"""Unit tests for EventBridge formatters module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.eventbridge.utils.formatters import (
    COMMON_ENVS,
    _extract_environment,
    _format_targets,
    _print_summary,
    format_json_output,
    format_table_output,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(name="my-rule", state="ENABLED", schedule="rate(5 minutes)"):
    return {
        "Name": name,
        "Arn": f"arn:aws:events:us-east-1:123456789012:rule/{name}",
        "State": state,
        "ScheduleExpression": schedule,
        "Description": "Test rule",
    }


def _make_lambda_target(func_name="my-func", region="us-east-1"):
    return {
        "Id": "1",
        "Arn": f"arn:aws:lambda:{region}:123456789012:function:{func_name}",
    }


def _make_other_target(resource_id="sqs-queue"):
    return {
        "Id": "1",
        "Arn": f"arn:aws:sqs:us-east-1:123456789012:{resource_id}",
    }


def _make_item(rule=None, targets=None, tags=None):
    return {
        "rule": rule or _make_rule(),
        "targets": targets if targets is not None else [],
        "tags": tags or {},
    }


# ---------------------------------------------------------------------------
# _format_targets
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatTargets:
    def test_no_targets(self):
        result = _format_targets([])
        assert result == "No targets"

    def test_lambda_target_extracts_function_name(self):
        targets = [_make_lambda_target("my-processor")]
        result = _format_targets(targets)
        assert "my-processor" in result

    def test_non_lambda_target_shows_last_arn_segment(self):
        targets = [_make_other_target("my-sqs-queue")]
        result = _format_targets(targets)
        assert "my-sqs-queue" in result

    def test_multiple_targets_shows_first_two(self):
        targets = [
            _make_lambda_target("func-a"),
            _make_lambda_target("func-b"),
            _make_lambda_target("func-c"),
        ]
        result = _format_targets(targets)
        assert "func-a" in result
        assert "func-b" in result
        assert "+1 more" in result

    def test_exactly_two_targets_no_more(self):
        targets = [_make_lambda_target("func-a"), _make_lambda_target("func-b")]
        result = _format_targets(targets)
        assert "more" not in result

    def test_target_without_arn(self):
        targets = [{"Id": "1"}]
        result = _format_targets(targets)
        assert result == "No targets"

    def test_non_lambda_arn_truncated_to_30_chars(self):
        long_id = "a" * 50
        targets = [{"Id": "1", "Arn": f"arn:aws:sqs:us-east-1:123456789012:{long_id}"}]
        result = _format_targets(targets)
        # last segment after ':' truncated to 30 chars
        assert len(result) <= 30

    def test_lambda_function_name_with_qualifier_stripped(self):
        """Function ARN with qualifier - only base function name extracted."""
        targets = [
            {
                "Id": "1",
                "Arn": "arn:aws:lambda:us-east-1:123456789012:function:my-func:PROD",
            }
        ]
        result = _format_targets(targets)
        assert "my-func" in result


# ---------------------------------------------------------------------------
# _extract_environment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractEnvironment:
    def test_env_tag_priority(self):
        targets = []
        tags = {"Env": "prod", "Team": "ops"}
        result = _extract_environment(targets, tags)
        assert result == "prod"

    def test_environment_tag_fallback(self):
        targets = []
        tags = {"Environment": "staging"}
        result = _extract_environment(targets, tags)
        assert result == "staging"

    def test_env_tag_has_priority_over_environment(self):
        targets = []
        tags = {"Env": "dev", "Environment": "development"}
        result = _extract_environment(targets, tags)
        assert result == "dev"

    def test_extract_from_lambda_function_name(self):
        targets = [_make_lambda_target("service-prod-processor")]
        tags = {}
        result = _extract_environment(targets, tags)
        assert result == "prod"

    def test_extract_dev_from_function_name(self):
        targets = [_make_lambda_target("my-dev-handler")]
        tags = {}
        result = _extract_environment(targets, tags)
        assert result == "dev"

    def test_no_env_returns_empty(self):
        targets = [_make_lambda_target("generic-handler")]
        tags = {}
        result = _extract_environment(targets, tags)
        assert result == ""

    def test_non_lambda_target_no_env(self):
        targets = [_make_other_target("my-queue")]
        tags = {}
        result = _extract_environment(targets, tags)
        assert result == ""

    def test_empty_tags_and_targets(self):
        result = _extract_environment([], {})
        assert result == ""

    def test_all_common_envs_recognized(self):
        for env in COMMON_ENVS:
            targets = [_make_lambda_target(f"service-{env}-handler")]
            result = _extract_environment(targets, {})
            assert result == env, f"Expected '{env}' to be recognized"


# ---------------------------------------------------------------------------
# _print_summary
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrintSummary:
    def test_all_enabled(self):
        rules = [
            _make_item(rule=_make_rule(state="ENABLED")),
            _make_item(rule=_make_rule(state="ENABLED")),
        ]
        # Should not raise
        _print_summary(rules)

    def test_all_disabled(self):
        rules = [_make_item(rule=_make_rule(state="DISABLED"))]
        _print_summary(rules)

    def test_mixed(self):
        rules = [
            _make_item(rule=_make_rule(state="ENABLED")),
            _make_item(rule=_make_rule(state="DISABLED")),
        ]
        _print_summary(rules)

    def test_empty_list(self):
        _print_summary([])


# ---------------------------------------------------------------------------
# format_json_output
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatJsonOutput:
    def test_basic_output(self, capsys):
        rules = [
            _make_item(
                rule=_make_rule("my-rule"),
                targets=[_make_lambda_target("func-a")],
                tags={"Env": "dev"},
            )
        ]
        format_json_output(rules)

    def test_output_contains_rule_fields(self, capsys):
        rules = [
            _make_item(
                rule=_make_rule("test-rule", state="ENABLED", schedule="rate(1 minute)"),
                targets=[],
                tags={},
            )
        ]
        format_json_output(rules)

    def test_target_with_input(self):
        rules = [
            {
                "rule": _make_rule(),
                "targets": [{"Id": "1", "Arn": "arn:aws:lambda:us-east-1:123:function:fn", "Input": '{"key": "val"}'}],
                "tags": {},
            }
        ]
        # Should not raise
        format_json_output(rules)

    def test_target_with_input_path(self):
        rules = [
            {
                "rule": _make_rule(),
                "targets": [{"Id": "1", "Arn": "arn:aws:lambda:us-east-1:123:function:fn", "InputPath": "$.detail"}],
                "tags": {},
            }
        ]
        format_json_output(rules)

    def test_empty_list(self):
        format_json_output([])

    def test_rule_without_schedule(self):
        rule = {
            "Name": "pattern-rule",
            "Arn": "arn:aws:events:us-east-1:123456789012:rule/pattern-rule",
            "State": "ENABLED",
        }
        rules = [{"rule": rule, "targets": [], "tags": {}}]
        format_json_output(rules)

    def test_rule_without_description(self):
        rule = {
            "Name": "simple-rule",
            "Arn": "arn:aws:events:us-east-1:123456789012:rule/simple-rule",
            "State": "DISABLED",
            "ScheduleExpression": "rate(1 hour)",
        }
        rules = [{"rule": rule, "targets": [], "tags": {}}]
        format_json_output(rules)


# ---------------------------------------------------------------------------
# format_table_output
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatTableOutput:
    def test_basic_table_output(self):
        rules = [
            _make_item(
                rule=_make_rule("my-rule", state="ENABLED"),
                targets=[_make_lambda_target("func-a")],
                tags={"Env": "dev"},
            )
        ]
        # Should not raise
        format_table_output(rules)

    def test_with_env_filter_in_title(self):
        rules = [_make_item()]
        format_table_output(rules, env="prod")

    def test_without_env_filter(self):
        rules = [_make_item()]
        format_table_output(rules, env=None)

    def test_disabled_rule_shows_disabled(self):
        rules = [_make_item(rule=_make_rule("disabled-rule", state="DISABLED"))]
        format_table_output(rules)

    def test_empty_rules_list(self):
        format_table_output([])

    def test_rule_with_no_env_tag(self):
        rules = [_make_item(targets=[_make_other_target()], tags={})]
        format_table_output(rules)

    def test_multiple_rules(self):
        rules = [
            _make_item(rule=_make_rule("rule-1", state="ENABLED"), tags={"Env": "dev"}),
            _make_item(rule=_make_rule("rule-2", state="DISABLED"), tags={"Env": "prod"}),
        ]
        format_table_output(rules)

    def test_rule_with_multiple_targets(self):
        targets = [
            _make_lambda_target("func-a"),
            _make_lambda_target("func-b"),
            _make_lambda_target("func-c"),
        ]
        rules = [_make_item(targets=targets)]
        format_table_output(rules)
