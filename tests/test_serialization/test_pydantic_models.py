"""
Tests for Pydantic model serialization and deserialization.

This module tests round-trip serialization for all Pydantic models used in the project,
ensuring data integrity is maintained through serialize/deserialize cycles.

Requirements: 26.4, 26.5
"""

import json
from typing import List, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError

# ============================================================================
# Test Models (representing AI response structures)
# ============================================================================


class CommitMessage(BaseModel):
    """Pydantic model for structured commit message responses."""

    type: str = Field(..., description="Commit type (feat, fix, refactor, etc.)")
    scope: str = Field(..., description="Commit scope")
    subject: str = Field(..., description="Commit subject line")
    body: Optional[str] = Field(None, description="Commit body with details")
    ticket: Optional[str] = Field(None, description="Ticket number")


class CodeIssue(BaseModel):
    """Pydantic model for code review issues."""

    severity: str = Field(..., description="Issue severity (low, medium, high, critical)")
    category: str = Field(..., description="Issue category (style, security, performance, etc.)")
    description: str = Field(..., description="Issue description")
    file: str = Field(..., description="File path")
    line: Optional[int] = Field(None, description="Line number")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class CodeReview(BaseModel):
    """Pydantic model for structured code review responses."""

    summary: str = Field(..., description="Overall review summary")
    issues: List[CodeIssue] = Field(default_factory=list, description="List of identified issues")
    security_concerns: List[str] = Field(default_factory=list, description="Security concerns")
    performance_notes: List[str] = Field(default_factory=list, description="Performance notes")
    approved: bool = Field(False, description="Whether changes are approved")


class AIResponse(BaseModel):
    """Generic Pydantic model for AI responses."""

    response: str = Field(..., description="AI response text")
    confidence: Optional[float] = Field(None, description="Confidence score")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


# ============================================================================
# CommitMessage Model Serialization Tests
# ============================================================================


@pytest.mark.unit
def test_commit_message_serialization_basic():
    """Test basic CommitMessage serialization and deserialization."""
    # Create model instance
    commit = CommitMessage(
        type="feat", scope="auth", subject="add user authentication", body="Implement JWT-based authentication for API endpoints.", ticket="DEVO-123"
    )

    # Serialize to dict
    commit_dict = commit.model_dump()
    assert commit_dict["type"] == "feat"
    assert commit_dict["scope"] == "auth"
    assert commit_dict["subject"] == "add user authentication"
    assert commit_dict["body"] == "Implement JWT-based authentication for API endpoints."
    assert commit_dict["ticket"] == "DEVO-123"

    # Serialize to JSON
    commit_json = commit.model_dump_json()
    assert isinstance(commit_json, str)
    assert "feat" in commit_json
    assert "DEVO-123" in commit_json

    # Deserialize from dict
    commit_from_dict = CommitMessage(**commit_dict)
    assert commit_from_dict.type == commit.type
    assert commit_from_dict.scope == commit.scope
    assert commit_from_dict.subject == commit.subject
    assert commit_from_dict.body == commit.body
    assert commit_from_dict.ticket == commit.ticket

    # Deserialize from JSON
    commit_from_json = CommitMessage.model_validate_json(commit_json)
    assert commit_from_json.type == commit.type
    assert commit_from_json.scope == commit.scope
    assert commit_from_json.subject == commit.subject


@pytest.mark.unit
def test_commit_message_round_trip():
    """Test CommitMessage round-trip serialization preserves all data."""
    original = CommitMessage(
        type="fix",
        scope="database",
        subject="resolve connection timeout issue",
        body="- Increased connection timeout to 30 seconds\n- Added retry logic\n- Improved error messages",
        ticket="BUG-456",
    )

    # Round-trip through JSON
    json_str = original.model_dump_json()
    restored = CommitMessage.model_validate_json(json_str)

    # Verify all fields match
    assert restored.type == original.type
    assert restored.scope == original.scope
    assert restored.subject == original.subject
    assert restored.body == original.body
    assert restored.ticket == original.ticket


@pytest.mark.unit
def test_commit_message_optional_fields():
    """Test CommitMessage serialization with optional fields omitted."""
    # Create with minimal required fields
    commit = CommitMessage(type="chore", scope="deps", subject="update dependencies")

    # Serialize and deserialize
    json_str = commit.model_dump_json()
    restored = CommitMessage.model_validate_json(json_str)

    # Verify required fields
    assert restored.type == "chore"
    assert restored.scope == "deps"
    assert restored.subject == "update dependencies"

    # Verify optional fields are None
    assert restored.body is None
    assert restored.ticket is None


@pytest.mark.unit
def test_commit_message_validation_error():
    """Test CommitMessage validation with missing required fields."""
    # Missing required field 'type'
    with pytest.raises(ValidationError) as exc_info:
        CommitMessage(scope="auth", subject="add authentication")

    # Verify error mentions missing field
    error_str = str(exc_info.value)
    assert "type" in error_str.lower()


# ============================================================================
# CodeReview Model Serialization Tests
# ============================================================================


@pytest.mark.unit
def test_code_review_serialization_basic():
    """Test basic CodeReview serialization and deserialization."""
    # Create model instance with issues
    review = CodeReview(
        summary="Code changes look good with minor suggestions",
        issues=[
            CodeIssue(
                severity="low",
                category="style",
                description="Consider adding type hints",
                file="generator.py",
                line=15,
                suggestion="Add type hints to function parameters",
            ),
            CodeIssue(
                severity="medium",
                category="security",
                description="Potential SQL injection vulnerability",
                file="database.py",
                line=42,
                suggestion="Use parameterized queries",
            ),
        ],
        security_concerns=["SQL injection risk in database.py"],
        performance_notes=["Consider caching results"],
        approved=False,
    )

    # Serialize to dict
    review_dict = review.model_dump()
    assert review_dict["summary"] == "Code changes look good with minor suggestions"
    assert len(review_dict["issues"]) == 2
    assert review_dict["issues"][0]["severity"] == "low"
    assert review_dict["issues"][1]["severity"] == "medium"
    assert len(review_dict["security_concerns"]) == 1
    assert review_dict["approved"] is False

    # Serialize to JSON
    review_json = review.model_dump_json()
    assert isinstance(review_json, str)

    # Deserialize from JSON
    review_from_json = CodeReview.model_validate_json(review_json)
    assert review_from_json.summary == review.summary
    assert len(review_from_json.issues) == 2
    assert review_from_json.issues[0].severity == "low"
    assert review_from_json.issues[1].severity == "medium"


@pytest.mark.unit
def test_code_review_round_trip():
    """Test CodeReview round-trip serialization preserves nested data."""
    original = CodeReview(
        summary="Comprehensive review completed",
        issues=[CodeIssue(severity="high", category="bug", description="Null pointer dereference", file="main.py", line=100)],
        security_concerns=["Unvalidated user input", "Missing authentication"],
        performance_notes=["N+1 query problem", "Large memory allocation"],
        approved=False,
    )

    # Round-trip through JSON
    json_str = original.model_dump_json()
    restored = CodeReview.model_validate_json(json_str)

    # Verify all fields match
    assert restored.summary == original.summary
    assert len(restored.issues) == len(original.issues)
    assert restored.issues[0].severity == original.issues[0].severity
    assert restored.issues[0].category == original.issues[0].category
    assert restored.issues[0].description == original.issues[0].description
    assert restored.issues[0].file == original.issues[0].file
    assert restored.issues[0].line == original.issues[0].line
    assert restored.security_concerns == original.security_concerns
    assert restored.performance_notes == original.performance_notes
    assert restored.approved == original.approved


@pytest.mark.unit
def test_code_review_empty_lists():
    """Test CodeReview serialization with empty lists."""
    # Create with no issues or concerns
    review = CodeReview(summary="No issues found", approved=True)

    # Serialize and deserialize
    json_str = review.model_dump_json()
    restored = CodeReview.model_validate_json(json_str)

    # Verify empty lists are preserved
    assert restored.summary == "No issues found"
    assert restored.issues == []
    assert restored.security_concerns == []
    assert restored.performance_notes == []
    assert restored.approved is True


@pytest.mark.unit
def test_code_issue_serialization():
    """Test CodeIssue nested model serialization."""
    issue = CodeIssue(
        severity="critical",
        category="security",
        description="Hardcoded credentials detected",
        file="config.py",
        line=25,
        suggestion="Use environment variables",
    )

    # Serialize to dict
    issue_dict = issue.model_dump()
    assert issue_dict["severity"] == "critical"
    assert issue_dict["category"] == "security"
    assert issue_dict["line"] == 25

    # Round-trip through JSON
    json_str = issue.model_dump_json()
    restored = CodeIssue.model_validate_json(json_str)

    assert restored.severity == issue.severity
    assert restored.category == issue.category
    assert restored.description == issue.description
    assert restored.file == issue.file
    assert restored.line == issue.line
    assert restored.suggestion == issue.suggestion


# ============================================================================
# AIResponse Model Serialization Tests
# ============================================================================


@pytest.mark.unit
def test_ai_response_serialization_basic():
    """Test basic AIResponse serialization and deserialization."""
    response = AIResponse(response="This is an AI-generated response", confidence=0.95, metadata={"model": "claude-3-7-sonnet", "tokens": 150})

    # Serialize to dict
    response_dict = response.model_dump()
    assert response_dict["response"] == "This is an AI-generated response"
    assert response_dict["confidence"] == 0.95
    assert response_dict["metadata"]["model"] == "claude-3-7-sonnet"

    # Round-trip through JSON
    json_str = response.model_dump_json()
    restored = AIResponse.model_validate_json(json_str)

    assert restored.response == response.response
    assert restored.confidence == response.confidence
    assert restored.metadata == response.metadata


@pytest.mark.unit
def test_ai_response_with_complex_metadata():
    """Test AIResponse serialization with complex nested metadata."""
    response = AIResponse(
        response="Complex response",
        confidence=0.87,
        metadata={
            "model": "claude-3-7-sonnet",
            "metrics": {"input_tokens": 100, "output_tokens": 50, "latency_ms": 1234},
            "tags": ["code-review", "security"],
            "timestamp": "2024-01-15T10:30:00Z",
        },
    )

    # Round-trip through JSON
    json_str = response.model_dump_json()
    restored = AIResponse.model_validate_json(json_str)

    # Verify nested metadata is preserved
    assert restored.metadata["model"] == "claude-3-7-sonnet"
    assert restored.metadata["metrics"]["input_tokens"] == 100
    assert restored.metadata["metrics"]["output_tokens"] == 50
    assert restored.metadata["tags"] == ["code-review", "security"]
    assert restored.metadata["timestamp"] == "2024-01-15T10:30:00Z"


# ============================================================================
# Edge Cases and Special Characters
# ============================================================================


@pytest.mark.unit
def test_commit_message_with_special_characters():
    """Test CommitMessage serialization with special characters."""
    commit = CommitMessage(
        type="fix",
        scope="api",
        subject="handle special chars: <>&\"'",
        body='Fixed issue with:\n- Quotes: "test"\n- Ampersands: A & B\n- Brackets: <tag>',
        ticket="SPEC-789",
    )

    # Round-trip through JSON
    json_str = commit.model_dump_json()
    restored = CommitMessage.model_validate_json(json_str)

    # Verify special characters are preserved
    assert restored.subject == "handle special chars: <>&\"'"
    assert '"test"' in restored.body
    assert "A & B" in restored.body
    assert "<tag>" in restored.body


@pytest.mark.unit
def test_code_review_with_unicode():
    """Test CodeReview serialization with Unicode characters."""
    review = CodeReview(
        summary="Review completed ✓",
        issues=[CodeIssue(severity="low", category="style", description="Consider using → instead of ->", file="utils.py", line=10)],
        approved=True,
    )

    # Round-trip through JSON
    json_str = review.model_dump_json()
    restored = CodeReview.model_validate_json(json_str)

    # Verify Unicode is preserved
    assert "✓" in restored.summary
    assert "→" in restored.issues[0].description


@pytest.mark.unit
def test_model_with_empty_strings():
    """Test model serialization with empty strings."""
    commit = CommitMessage(type="chore", scope="", subject="update config", body="", ticket=None)  # Empty scope  # Empty body

    # Round-trip through JSON
    json_str = commit.model_dump_json()
    restored = CommitMessage.model_validate_json(json_str)

    # Verify empty strings are preserved (not converted to None)
    assert restored.scope == ""
    assert restored.body == ""
    assert restored.ticket is None


# ============================================================================
# JSON Compatibility Tests
# ============================================================================


@pytest.mark.unit
def test_model_json_compatibility():
    """Test that Pydantic models produce standard JSON compatible with json module."""
    review = CodeReview(
        summary="Test review", issues=[CodeIssue(severity="low", category="style", description="Test issue", file="test.py")], approved=True
    )

    # Serialize with Pydantic
    pydantic_json = review.model_dump_json()

    # Parse with standard json module
    parsed = json.loads(pydantic_json)
    assert parsed["summary"] == "Test review"
    assert len(parsed["issues"]) == 1
    assert parsed["approved"] is True

    # Verify we can deserialize from standard json
    standard_json = json.dumps(parsed)
    restored = CodeReview.model_validate_json(standard_json)
    assert restored.summary == review.summary


@pytest.mark.unit
def test_model_dict_compatibility():
    """Test that model_dump produces standard Python dicts."""
    commit = CommitMessage(type="feat", scope="cli", subject="add new command")

    # Get dict representation
    commit_dict = commit.model_dump()

    # Verify it's a standard dict
    assert isinstance(commit_dict, dict)
    assert commit_dict["type"] == "feat"

    # Verify we can serialize with standard json module
    json_str = json.dumps(commit_dict)
    parsed = json.loads(json_str)
    assert parsed["type"] == "feat"


# ============================================================================
# Validation and Error Handling Tests
# ============================================================================


@pytest.mark.unit
def test_invalid_json_deserialization():
    """Test that invalid JSON raises appropriate errors."""
    invalid_json = '{"type": "feat", "scope": "cli", invalid}'

    with pytest.raises(Exception):  # Could be ValidationError or JSONDecodeError
        CommitMessage.model_validate_json(invalid_json)


@pytest.mark.unit
def test_missing_required_fields():
    """Test that missing required fields raise ValidationError."""
    # Missing 'summary' field
    with pytest.raises(ValidationError) as exc_info:
        CodeReview(issues=[], approved=True)

    error_str = str(exc_info.value)
    assert "summary" in error_str.lower()


@pytest.mark.unit
def test_invalid_field_types():
    """Test that invalid field types raise ValidationError."""
    # 'approved' should be bool, not a non-coercible type
    with pytest.raises(ValidationError):
        CodeReview(summary="Test", approved={"invalid": "dict"})  # Invalid type that can't be coerced


@pytest.mark.unit
def test_extra_fields_ignored():
    """Test that extra fields are ignored by default."""
    data = {"type": "feat", "scope": "cli", "subject": "add command", "extra_field": "should be ignored"}

    # Should not raise error, extra field is ignored
    commit = CommitMessage(**data)
    assert commit.type == "feat"
    assert not hasattr(commit, "extra_field")


# ============================================================================
# Performance and Large Data Tests
# ============================================================================


@pytest.mark.unit
def test_large_code_review_serialization():
    """Test serialization of CodeReview with many issues."""
    # Create review with 100 issues
    issues = [CodeIssue(severity="low", category="style", description=f"Issue {i}", file=f"file{i}.py", line=i) for i in range(100)]

    review = CodeReview(summary="Large review", issues=issues, approved=False)

    # Round-trip through JSON
    json_str = review.model_dump_json()
    restored = CodeReview.model_validate_json(json_str)

    # Verify all issues are preserved
    assert len(restored.issues) == 100
    assert restored.issues[0].description == "Issue 0"
    assert restored.issues[99].description == "Issue 99"


@pytest.mark.unit
def test_deeply_nested_metadata():
    """Test AIResponse with deeply nested metadata."""
    response = AIResponse(response="Test", metadata={"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}})

    # Round-trip through JSON
    json_str = response.model_dump_json()
    restored = AIResponse.model_validate_json(json_str)

    # Verify deep nesting is preserved
    assert restored.metadata["level1"]["level2"]["level3"]["level4"]["value"] == "deep"
