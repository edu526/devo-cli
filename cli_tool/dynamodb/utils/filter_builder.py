"""Generic filter builder for DynamoDB expressions."""

import re
from typing import Any, Dict, List, Optional, Tuple

from boto3.dynamodb.types import TypeSerializer


class FilterBuilder:
    """Build DynamoDB filter expressions from simple syntax."""

    # Reserved keywords in DynamoDB
    RESERVED_KEYWORDS = {
        "abort",
        "absolute",
        "action",
        "add",
        "after",
        "agent",
        "aggregate",
        "all",
        "allocate",
        "alter",
        "analyze",
        "and",
        "any",
        "archive",
        "are",
        "array",
        "as",
        "asc",
        "ascii",
        "asensitive",
        "assertion",
        "asymmetric",
        "at",
        "atomic",
        "attach",
        "attribute",
        "auth",
        "authorization",
        "authorize",
        "auto",
        "avg",
        "back",
        "backup",
        "base",
        "batch",
        "before",
        "begin",
        "between",
        "bigint",
        "binary",
        "bit",
        "blob",
        "block",
        "boolean",
        "both",
        "breadth",
        "bucket",
        "bulk",
        "by",
        "byte",
        "call",
        "called",
        "calling",
        "capacity",
        "cascade",
        "cascaded",
        "case",
        "cast",
        "catalog",
        "char",
        "character",
        "check",
        "class",
        "clob",
        "close",
        "cluster",
        "clustered",
        "clustering",
        "clusters",
        "coalesce",
        "collate",
        "collation",
        "collection",
        "column",
        "columns",
        "combine",
        "comment",
        "commit",
        "compact",
        "compile",
        "compress",
        "condition",
        "conflict",
        "connect",
        "connection",
        "consistency",
        "consistent",
        "constraint",
        "constraints",
        "constructor",
        "consumed",
        "continue",
        "convert",
        "copy",
        "corresponding",
        "count",
        "counter",
        "create",
        "cross",
        "cube",
        "current",
        "cursor",
        "cycle",
        "data",
        "database",
        "date",
        "datetime",
        "day",
        "deallocate",
        "dec",
        "decimal",
        "declare",
        "default",
        "deferrable",
        "deferred",
        "define",
        "defined",
        "definition",
        "delete",
        "delimited",
        "depth",
        "deref",
        "desc",
        "describe",
        "descriptor",
        "detach",
        "deterministic",
        "diagnostics",
        "directories",
        "disable",
        "disconnect",
        "distinct",
        "distribute",
        "do",
        "domain",
        "double",
        "drop",
        "dump",
        "duration",
        "dynamic",
        "each",
        "element",
        "else",
        "elseif",
        "empty",
        "enable",
        "end",
        "equal",
        "equals",
        "error",
        "escape",
        "escaped",
        "eval",
        "evaluate",
        "exceeded",
        "except",
        "exception",
        "exceptions",
        "exclusive",
        "exec",
        "execute",
        "exists",
        "exit",
        "explain",
        "explode",
        "export",
        "expression",
        "extended",
        "external",
        "extract",
        "fail",
        "false",
        "family",
        "fetch",
        "fields",
        "file",
        "filter",
        "filtering",
        "final",
        "finish",
        "first",
        "fixed",
        "flattern",
        "float",
        "for",
        "force",
        "foreign",
        "format",
        "forward",
        "found",
        "free",
        "from",
        "full",
        "function",
        "functions",
        "general",
        "generate",
        "get",
        "glob",
        "global",
        "go",
        "goto",
        "grant",
        "greater",
        "group",
        "grouping",
        "handler",
        "hash",
        "have",
        "having",
        "heap",
        "hidden",
        "hold",
        "hour",
        "identified",
        "identity",
        "if",
        "ignore",
        "immediate",
        "import",
        "in",
        "including",
        "inclusive",
        "increment",
        "incremental",
        "index",
        "indexed",
        "indexes",
        "indicator",
        "infinite",
        "initially",
        "inline",
        "inner",
        "innter",
        "inout",
        "input",
        "insensitive",
        "insert",
        "instead",
        "int",
        "integer",
        "intersect",
        "interval",
        "into",
        "invalidate",
        "is",
        "isolation",
        "item",
        "items",
        "iterate",
        "join",
        "key",
        "keys",
        "lag",
        "language",
        "large",
        "last",
        "lateral",
        "lead",
        "leading",
        "leave",
        "left",
        "length",
        "less",
        "level",
        "like",
        "limit",
        "limited",
        "lines",
        "list",
        "load",
        "local",
        "localtime",
        "localtimestamp",
        "location",
        "locator",
        "lock",
        "locks",
        "log",
        "loged",
        "long",
        "loop",
        "lower",
        "map",
        "match",
        "materialized",
        "max",
        "maxlen",
        "member",
        "merge",
        "method",
        "metrics",
        "min",
        "minus",
        "minute",
        "missing",
        "mod",
        "mode",
        "modifies",
        "modify",
        "module",
        "month",
        "multi",
        "multiset",
        "name",
        "names",
        "national",
        "natural",
        "nchar",
        "nclob",
        "new",
        "next",
        "no",
        "none",
        "not",
        "null",
        "nullif",
        "number",
        "numeric",
        "object",
        "of",
        "offline",
        "offset",
        "old",
        "on",
        "online",
        "only",
        "opaque",
        "open",
        "operator",
        "option",
        "or",
        "order",
        "ordinality",
        "other",
        "others",
        "out",
        "outer",
        "output",
        "over",
        "overlaps",
        "override",
        "owner",
        "pad",
        "parallel",
        "parameter",
        "parameters",
        "partial",
        "partition",
        "partitioned",
        "partitions",
        "path",
        "percent",
        "percentile",
        "permission",
        "permissions",
        "pipe",
        "pipelined",
        "plan",
        "pool",
        "position",
        "precision",
        "prepare",
        "preserve",
        "primary",
        "prior",
        "private",
        "privileges",
        "procedure",
        "processed",
        "project",
        "projection",
        "property",
        "provisioning",
        "public",
        "put",
        "query",
        "quit",
        "quorum",
        "raise",
        "random",
        "range",
        "rank",
        "raw",
        "read",
        "reads",
        "real",
        "rebuild",
        "record",
        "recursive",
        "reduce",
        "ref",
        "reference",
        "references",
        "referencing",
        "regexp",
        "region",
        "reindex",
        "relative",
        "release",
        "remainder",
        "rename",
        "repeat",
        "replace",
        "request",
        "reset",
        "resignal",
        "resource",
        "response",
        "restore",
        "restrict",
        "result",
        "return",
        "returning",
        "returns",
        "reverse",
        "revoke",
        "right",
        "role",
        "roles",
        "rollback",
        "rollup",
        "routine",
        "row",
        "rows",
        "rule",
        "rules",
        "sample",
        "satisfies",
        "save",
        "savepoint",
        "scan",
        "schema",
        "scope",
        "scroll",
        "search",
        "second",
        "section",
        "segment",
        "segments",
        "select",
        "self",
        "semi",
        "sensitive",
        "separate",
        "sequence",
        "serializable",
        "session",
        "set",
        "sets",
        "shard",
        "share",
        "shared",
        "short",
        "show",
        "signal",
        "similar",
        "size",
        "skewed",
        "smallint",
        "snapshot",
        "some",
        "source",
        "space",
        "spaces",
        "sparse",
        "specific",
        "specifictype",
        "split",
        "sql",
        "sqlcode",
        "sqlerror",
        "sqlexception",
        "sqlstate",
        "sqlwarning",
        "start",
        "state",
        "static",
        "status",
        "storage",
        "store",
        "stored",
        "stream",
        "string",
        "struct",
        "style",
        "sub",
        "submultiset",
        "subpartition",
        "substring",
        "subtype",
        "sum",
        "super",
        "symmetric",
        "synonym",
        "system",
        "table",
        "tablesample",
        "temp",
        "temporary",
        "terminated",
        "text",
        "than",
        "then",
        "throughput",
        "time",
        "timestamp",
        "timezone",
        "tinyint",
        "to",
        "token",
        "total",
        "touch",
        "trailing",
        "transaction",
        "transform",
        "translate",
        "translation",
        "treat",
        "trigger",
        "trim",
        "true",
        "truncate",
        "ttl",
        "tuple",
        "type",
        "under",
        "undo",
        "union",
        "unique",
        "unit",
        "unknown",
        "unlogged",
        "unnest",
        "unprocessed",
        "unsigned",
        "until",
        "update",
        "upper",
        "url",
        "usage",
        "use",
        "user",
        "users",
        "using",
        "uuid",
        "vacuum",
        "value",
        "valued",
        "values",
        "varchar",
        "variable",
        "variance",
        "varint",
        "varying",
        "view",
        "views",
        "virtual",
        "void",
        "wait",
        "when",
        "whenever",
        "where",
        "while",
        "window",
        "with",
        "within",
        "without",
        "work",
        "wrapped",
        "write",
        "year",
        "zone",
    }

    def __init__(self):
        self.value_counter = 0
        self.name_counter = 0
        self.expression_attribute_values = {}
        self.expression_attribute_names = {}
        self.serializer = TypeSerializer()

    def _get_value_placeholder(self) -> str:
        """Generate unique value placeholder."""
        placeholder = f":val{self.value_counter}"
        self.value_counter += 1
        return placeholder

    def _get_name_placeholder(self, attr_name: str) -> str:
        """Generate name placeholder for reserved keywords or special chars."""
        # Check if attribute name needs escaping
        if attr_name.lower() in self.RESERVED_KEYWORDS or "." in attr_name or "-" in attr_name:
            placeholder = f"#attr{self.name_counter}"
            self.name_counter += 1
            self.expression_attribute_names[placeholder] = attr_name
            return placeholder
        return attr_name

    def _parse_value(self, value_str: str) -> Any:
        """Parse string value to appropriate Python type."""
        value_str = value_str.strip()

        # Boolean
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False

        # Null
        if value_str.lower() in ("null", "none"):
            return None

        # Number
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass

        # String (remove quotes if present)
        if (value_str.startswith('"') and value_str.endswith('"')) or (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]

        return value_str

    def build_filter(self, filter_str: str) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
        """
        Build DynamoDB filter expression from simple syntax.

        Supported syntax:
          - attribute = value
          - attribute != value
          - attribute > value
          - attribute >= value
          - attribute < value
          - attribute <= value
          - attribute BETWEEN value1 AND value2
          - attribute IN (value1, value2, ...)
          - attribute_exists(attribute)
          - attribute_not_exists(attribute)
          - begins_with(attribute, value)
          - contains(attribute, value)
          - size(attribute) > value
          - attribute1 = value1 AND attribute2 = value2
          - attribute1 = value1 OR attribute2 = value2
          - (attribute1 = value1) AND (attribute2 = value2)  # with parentheses

        Returns:
          Tuple of (expression, attribute_values, attribute_names)
        """
        if not filter_str:
            return "", {}, {}

        # Validate basic syntax
        if not self._validate_syntax(filter_str):
            raise ValueError(f"Invalid filter syntax: {filter_str}")

        # Reset counters
        self.value_counter = 0
        self.name_counter = 0
        self.expression_attribute_values = {}
        self.expression_attribute_names = {}

        # Process the filter string
        expression = self._process_expression(filter_str)

        return expression, self.expression_attribute_values, self.expression_attribute_names

    def _validate_syntax(self, expr: str) -> bool:
        """Validate basic filter syntax."""
        # Check for balanced parentheses
        if expr.count("(") != expr.count(")"):
            return False

        # Check for empty parentheses
        if "()" in expr:
            return False

        # Check for consecutive operators
        invalid_patterns = [
            r"AND\s+AND",
            r"OR\s+OR",
            r"AND\s+OR\s+AND",
            r"OR\s+AND\s+OR",
            r"=\s*=",
            r">\s*>",
            r"<\s*<",
        ]
        for pattern in invalid_patterns:
            if re.search(pattern, expr, re.IGNORECASE):
                return False

        return True

    def _process_expression(self, expr: str) -> str:
        """Process a filter expression."""
        expr = expr.strip()

        # Handle parentheses first
        if expr.startswith("(") and expr.endswith(")"):
            # Remove outer parentheses and process inner expression
            inner = expr[1:-1].strip()
            # Only remove if they're balanced outer parentheses
            if self._count_parentheses(inner) == 0:
                return self._process_expression(inner)

        # Handle BETWEEN first (contains AND keyword)
        if " BETWEEN " in expr or " between " in expr:
            return self._process_between(expr)

        # Handle logical operators (AND, OR) before processing other expressions
        # Split by AND/OR at the top level (not inside parentheses)
        and_split = self._split_by_operator(expr, "AND")
        if and_split:
            left = self._process_expression(and_split[0])
            right = self._process_expression(and_split[1])
            return f"({left} AND {right})"

        or_split = self._split_by_operator(expr, "OR")
        if or_split:
            left = self._process_expression(or_split[0])
            right = self._process_expression(or_split[1])
            return f"({left} OR {right})"

        # Handle function calls
        if "attribute_exists(" in expr:
            return self._process_function(expr, "attribute_exists")
        if "attribute_not_exists(" in expr:
            return self._process_function(expr, "attribute_not_exists")
        if "begins_with(" in expr:
            return self._process_function_with_value(expr, "begins_with")
        if "contains(" in expr:
            return self._process_function_with_value(expr, "contains")
        if "size(" in expr:
            return self._process_size_function(expr)

        # Handle IN
        if " IN " in expr or " in " in expr:
            return self._process_in(expr)

        # Handle comparison operators
        for op in ["!=", ">=", "<=", "=", ">", "<"]:
            if f" {op} " in expr:
                return self._process_comparison(expr, op)

        return expr

    def _count_parentheses(self, expr: str) -> int:
        """Count unmatched parentheses in expression."""
        count = 0
        for char in expr:
            if char == "(":
                count += 1
            elif char == ")":
                count -= 1
        return count

    def _split_by_operator(self, expr: str, operator: str) -> Optional[List[str]]:
        """Split expression by operator at top level (not inside parentheses)."""
        pattern = rf"\s+(?:{operator}|{operator.lower()})\s+"

        # Find all matches
        matches = list(re.finditer(pattern, expr))
        if not matches:
            return None

        # Find the match at parentheses level 0
        for match in matches:
            # Check if this operator is at top level (not inside parentheses)
            before = expr[: match.start()]
            paren_count = 0
            for char in before:
                if char == "(":
                    paren_count += 1
                elif char == ")":
                    paren_count -= 1

            # If we're at level 0, this is a top-level operator
            if paren_count == 0:
                left = expr[: match.start()].strip()
                right = expr[match.end() :].strip()
                return [left, right]

        return None

    def _process_comparison(self, expr: str, operator: str) -> str:
        """Process comparison expression."""
        parts = expr.split(f" {operator} ", 1)
        if len(parts) != 2:
            return expr

        attr_name = parts[0].strip()
        value_str = parts[1].strip()

        # Get placeholders
        name_placeholder = self._get_name_placeholder(attr_name)
        value_placeholder = self._get_value_placeholder()

        # Parse and store value with DynamoDB serialization
        value = self._parse_value(value_str)
        self.expression_attribute_values[value_placeholder] = self.serializer.serialize(value)

        # Map != to <>
        if operator == "!=":
            operator = "<>"

        return f"{name_placeholder} {operator} {value_placeholder}"

    def _process_between(self, expr: str) -> str:
        """Process BETWEEN expression."""
        match = re.match(r"(\w+)\s+(?:BETWEEN|between)\s+(.+?)\s+(?:AND|and)\s+(.+)", expr)
        if not match:
            return expr

        attr_name = match.group(1).strip()
        value1_str = match.group(2).strip()
        value2_str = match.group(3).strip()

        name_placeholder = self._get_name_placeholder(attr_name)
        value1_placeholder = self._get_value_placeholder()
        value2_placeholder = self._get_value_placeholder()

        self.expression_attribute_values[value1_placeholder] = self.serializer.serialize(self._parse_value(value1_str))
        self.expression_attribute_values[value2_placeholder] = self.serializer.serialize(self._parse_value(value2_str))

        return f"{name_placeholder} BETWEEN {value1_placeholder} AND {value2_placeholder}"

    def _process_in(self, expr: str) -> str:
        """Process IN expression."""
        match = re.match(r"(\w+)\s+(?:IN|in)\s+\((.+)\)", expr)
        if not match:
            return expr

        attr_name = match.group(1).strip()
        values_str = match.group(2).strip()

        name_placeholder = self._get_name_placeholder(attr_name)

        # Parse values
        values = [v.strip() for v in values_str.split(",")]
        value_placeholders = []

        for value_str in values:
            value_placeholder = self._get_value_placeholder()
            self.expression_attribute_values[value_placeholder] = self.serializer.serialize(self._parse_value(value_str))
            value_placeholders.append(value_placeholder)

        return f"{name_placeholder} IN ({', '.join(value_placeholders)})"

    def _process_function(self, expr: str, func_name: str) -> str:
        """Process function without value (attribute_exists, attribute_not_exists)."""
        match = re.match(rf"{func_name}\((\w+)\)", expr)
        if not match:
            return expr

        attr_name = match.group(1).strip()
        name_placeholder = self._get_name_placeholder(attr_name)

        return f"{func_name}({name_placeholder})"

    def _process_function_with_value(self, expr: str, func_name: str) -> str:
        """Process function with value (begins_with, contains)."""
        # Match function with attribute and value, stopping at closing parenthesis
        match = re.match(rf"{func_name}\(([^,]+),\s*([^)]+)\)", expr)
        if not match:
            return expr

        attr_name = match.group(1).strip()
        value_str = match.group(2).strip()

        name_placeholder = self._get_name_placeholder(attr_name)
        value_placeholder = self._get_value_placeholder()

        self.expression_attribute_values[value_placeholder] = self.serializer.serialize(self._parse_value(value_str))

        return f"{func_name}({name_placeholder}, {value_placeholder})"

    def _process_size_function(self, expr: str) -> str:
        """Process size() function with comparison."""
        match = re.match(r"size\((\w+)\)\s*([><=!]+)\s*(.+)", expr)
        if not match:
            return expr

        attr_name = match.group(1).strip()
        operator = match.group(2).strip()
        value_str = match.group(3).strip()

        name_placeholder = self._get_name_placeholder(attr_name)
        value_placeholder = self._get_value_placeholder()

        self.expression_attribute_values[value_placeholder] = self.serializer.serialize(self._parse_value(value_str))

        if operator == "!=":
            operator = "<>"

        return f"size({name_placeholder}) {operator} {value_placeholder}"
