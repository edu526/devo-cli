"""Unit tests for DynamoDB FilterBuilder."""

import pytest

from cli_tool.commands.dynamodb.utils.filter_builder import FilterBuilder


def make_fb():
    return FilterBuilder()


# ---------------------------------------------------------------------------
# build_filter — empty / invalid input
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildFilterEdgeCases:
    def test_empty_string_returns_empty(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("")
        assert expr == ""
        assert vals == {}
        assert names == {}

    def test_unbalanced_parens_raises(self):
        fb = make_fb()
        with pytest.raises(ValueError, match="Invalid filter syntax"):
            fb.build_filter("(a = 1")

    def test_empty_parens_raises(self):
        fb = make_fb()
        with pytest.raises(ValueError, match="Invalid filter syntax"):
            fb.build_filter("()")

    def test_double_and_raises(self):
        fb = make_fb()
        with pytest.raises(ValueError, match="Invalid filter syntax"):
            fb.build_filter("a = 1 AND AND b = 2")

    def test_double_or_raises(self):
        fb = make_fb()
        with pytest.raises(ValueError, match="Invalid filter syntax"):
            fb.build_filter("a = 1 OR OR b = 2")


# ---------------------------------------------------------------------------
# _parse_value
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseValue:
    def test_true(self):
        fb = make_fb()
        assert fb._parse_value("true") is True

    def test_false(self):
        fb = make_fb()
        assert fb._parse_value("false") is False

    def test_null(self):
        fb = make_fb()
        assert fb._parse_value("null") is None

    def test_none(self):
        fb = make_fb()
        assert fb._parse_value("none") is None

    def test_integer(self):
        fb = make_fb()
        assert fb._parse_value("42") == 42

    def test_float(self):
        fb = make_fb()
        result = fb._parse_value("3.14")
        assert abs(result - 3.14) < 1e-9

    def test_double_quoted_string(self):
        fb = make_fb()
        assert fb._parse_value('"hello world"') == "hello world"

    def test_single_quoted_string(self):
        fb = make_fb()
        assert fb._parse_value("'hello world'") == "hello world"

    def test_bare_string(self):
        fb = make_fb()
        assert fb._parse_value("somevalue") == "somevalue"

    def test_strips_whitespace(self):
        fb = make_fb()
        assert fb._parse_value("  42  ") == 42


# ---------------------------------------------------------------------------
# _get_name_placeholder
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetNamePlaceholder:
    def test_regular_attr_not_escaped(self):
        fb = make_fb()
        result = fb._get_name_placeholder("userId")
        assert result == "userId"

    def test_reserved_keyword_escaped(self):
        fb = make_fb()
        result = fb._get_name_placeholder("status")
        assert result.startswith("#")
        assert "status" in fb.expression_attribute_names.values()

    def test_attr_with_hyphen_escaped(self):
        fb = make_fb()
        result = fb._get_name_placeholder("my-attr")
        assert result.startswith("#")

    def test_nested_attr_creates_placeholders(self):
        fb = make_fb()
        result = fb._get_name_placeholder("metadata.status")
        parts = result.split(".")
        assert len(parts) == 2
        for part in parts:
            assert part.startswith("#")

    def test_counter_increments(self):
        fb = make_fb()
        fb._get_name_placeholder("status")
        fb._get_name_placeholder("name")
        assert fb.name_counter == 2


# ---------------------------------------------------------------------------
# build_filter — comparison operators
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildFilterComparisons:
    def test_equality(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("userId = abc")
        assert "=" in expr
        assert any(v == {"S": "abc"} for v in vals.values())

    def test_inequality(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("count != 0")
        assert "<>" in expr

    def test_greater_than(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("age > 18")
        assert ">" in expr
        assert any(v == {"N": "18"} for v in vals.values())

    def test_greater_than_or_equal(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("score >= 100")
        assert ">=" in expr

    def test_less_than(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("price < 50")
        assert "<" in expr

    def test_less_than_or_equal(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("qty <= 10")
        assert "<=" in expr

    def test_reserved_keyword_attr(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("status = active")
        # 'status' is reserved; should be escaped
        assert "#" in expr
        assert len(names) > 0

    def test_bool_value_true(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("isActive = true")
        assert any(v == {"BOOL": True} for v in vals.values())

    def test_bool_value_false(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("isActive = false")
        assert any(v == {"BOOL": False} for v in vals.values())

    def test_null_value(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("field = null")
        assert any(v == {"NULL": True} for v in vals.values())


# ---------------------------------------------------------------------------
# build_filter — logical operators
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildFilterLogical:
    def test_and_operator(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("userId = abc AND age > 18")
        assert "AND" in expr
        assert len(vals) == 2

    def test_or_operator(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("userId = abc OR userId = def")
        assert "OR" in expr
        assert len(vals) == 2

    def test_and_or_combined(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("(userId = abc OR userId = def) AND age > 18")
        assert "AND" in expr
        assert "OR" in expr

    def test_case_insensitive_and(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("userId = abc and age > 18")
        assert "AND" in expr.upper()

    def test_case_insensitive_or(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("userId = abc or userId = def")
        assert "OR" in expr.upper()


# ---------------------------------------------------------------------------
# build_filter — BETWEEN
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildFilterBetween:
    def test_between_integers(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("age BETWEEN 18 AND 65")
        assert "BETWEEN" in expr
        assert len(vals) == 2

    def test_between_case_insensitive(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("age between 18 and 65")
        assert "BETWEEN" in expr


# ---------------------------------------------------------------------------
# build_filter — IN expression
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildFilterIn:
    def test_in_single_value(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("status IN (active)")
        assert "IN" in expr
        assert len(vals) == 1

    def test_in_multiple_values(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("status IN (active, pending, error)")
        assert "IN" in expr
        assert len(vals) == 3

    def test_in_case_insensitive(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("status in (active)")
        assert "IN" in expr


# ---------------------------------------------------------------------------
# build_filter — functions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildFilterFunctions:
    def test_attribute_exists(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("attribute_exists(myAttr)")
        assert "attribute_exists" in expr

    def test_attribute_not_exists(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("attribute_not_exists(myAttr)")
        assert "attribute_not_exists" in expr

    def test_begins_with(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter('begins_with(myAttr, "prefix")')
        assert "begins_with" in expr
        assert len(vals) == 1

    def test_contains(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter('contains(myAttr, "substring")')
        assert "contains" in expr
        assert len(vals) == 1

    def test_size_gt(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("size(myList) > 0")
        assert "size" in expr
        assert ">" in expr

    def test_size_ne(self):
        fb = make_fb()
        expr, vals, names = fb.build_filter("size(myList) != 0")
        assert "size" in expr
        assert "<>" in expr


# ---------------------------------------------------------------------------
# _validate_syntax
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateSyntax:
    def test_valid_expression(self):
        fb = make_fb()
        assert fb._validate_syntax("a = 1") is True

    def test_unbalanced_open_paren(self):
        fb = make_fb()
        assert fb._validate_syntax("(a = 1") is False

    def test_unbalanced_close_paren(self):
        fb = make_fb()
        assert fb._validate_syntax("a = 1)") is False

    def test_empty_parens(self):
        fb = make_fb()
        assert fb._validate_syntax("()") is False

    def test_double_equals(self):
        fb = make_fb()
        assert fb._validate_syntax("a == 1") is False

    def test_consecutive_and(self):
        fb = make_fb()
        assert fb._validate_syntax("a = 1 AND AND b = 2") is False


# ---------------------------------------------------------------------------
# _count_parentheses
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCountParentheses:
    def test_balanced(self):
        fb = make_fb()
        assert fb._count_parentheses("(a AND b)") == 0

    def test_extra_open(self):
        fb = make_fb()
        assert fb._count_parentheses("((a AND b)") == 1

    def test_extra_close(self):
        fb = make_fb()
        assert fb._count_parentheses("(a AND b))") == -1

    def test_no_parens(self):
        fb = make_fb()
        assert fb._count_parentheses("a AND b") == 0


# ---------------------------------------------------------------------------
# _split_by_operator
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitByOperator:
    def test_splits_on_and(self):
        fb = make_fb()
        result = fb._split_by_operator("a = 1 AND b = 2", "AND")
        assert result is not None
        assert result[0] == "a = 1"
        assert result[1] == "b = 2"

    def test_splits_on_or(self):
        fb = make_fb()
        result = fb._split_by_operator("a = 1 OR b = 2", "OR")
        assert result is not None

    def test_no_operator_returns_none(self):
        fb = make_fb()
        result = fb._split_by_operator("a = 1", "AND")
        assert result is None

    def test_nested_operator_not_split(self):
        """Operator inside parentheses should not be used for splitting."""
        fb = make_fb()
        # The AND inside parens is at level 1, the outer AND is at level 0
        result = fb._split_by_operator("(a = 1 AND b = 2) AND c = 3", "AND")
        assert result is not None
        assert "c = 3" in result[1]


# ---------------------------------------------------------------------------
# value_counter / name_counter reset on build_filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_counters_reset_between_calls():
    fb = make_fb()
    fb.build_filter("a = 1")
    first_val_counter = fb.value_counter
    fb.build_filter("b = 2")
    # After second call, counter restarted from 0 and processed 1 expression
    assert fb.value_counter == 1
