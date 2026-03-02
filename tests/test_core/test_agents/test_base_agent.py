"""
Unit tests for BaseAgent class.

Tests cover:
- BaseAgent initialization with AWS Bedrock client
- BaseAgent.query method with text responses
- BaseAgent.query_structured method with Pydantic responses
- Error handling for API rate limits
- Error handling for invalid responses
- Mock bedrock-runtime client using pytest-mock

Requirements: 3.1, 3.2, 7.1, 7.4, 7.5
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from cli_tool.core.agents.base_agent import BaseAgent

# ============================================================================
# Test Data Models
# ============================================================================


class MockResponse(BaseModel):
    """Mock Pydantic model for structured responses."""

    message: str
    status: str


# ============================================================================
# BaseAgent Initialization Tests
# ============================================================================


@pytest.mark.unit
def test_base_agent_initialization():
    """Test BaseAgent initialization with default parameters."""
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    assert agent.name == "TestAgent"
    assert agent.system_prompt == "You are a test assistant"
    assert agent.llm_model_id is not None
    assert agent.region_name == "us-east-1"
    assert agent.profile_name is None
    assert agent.tools == []
    assert agent.enable_rich_logging is False
    assert agent.custom_callback_handler is None
    assert agent.agent is None  # Lazy initialization


@pytest.mark.unit
def test_base_agent_initialization_with_custom_params():
    """Test BaseAgent initialization with custom parameters."""
    custom_tools = [MagicMock()]
    custom_callback = MagicMock()

    agent = BaseAgent(
        name="CustomAgent",
        system_prompt="Custom prompt",
        llm_model_id="custom-model-id",
        region_name="us-west-2",
        profile_name="test-profile",
        tools=custom_tools,
        enable_rich_logging=True,
        custom_callback_handler=custom_callback,
    )

    assert agent.name == "CustomAgent"
    assert agent.system_prompt == "Custom prompt"
    assert agent.llm_model_id == "custom-model-id"
    assert agent.region_name == "us-west-2"
    assert agent.profile_name == "test-profile"
    assert agent.tools == custom_tools
    assert agent.enable_rich_logging is True
    assert agent.custom_callback_handler == custom_callback
    assert agent.console is not None  # Rich console created when logging enabled


# ============================================================================
# BaseAgent.query Method Tests
# ============================================================================


@pytest.mark.unit
def test_base_agent_query_text_response(mocker):
    """Test BaseAgent.query method with text responses."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent and its response
    mock_agent_result = MagicMock()
    mock_agent_result.output = "This is a test response"
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify response
    assert response == "This is a test response"
    assert agent.agent is not None  # Agent was created
    mock_agent_instance.assert_called_once_with("Test input")


@pytest.mark.unit
def test_base_agent_query_with_content_attribute(mocker):
    """Test BaseAgent.query when result has content attribute instead of output."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with content attribute
    mock_agent_result = MagicMock()
    del mock_agent_result.output  # Remove output attribute
    mock_agent_result.content = "Content response"
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify response uses content attribute
    assert response == "Content response"


@pytest.mark.unit
def test_base_agent_query_with_string_result(mocker):
    """Test BaseAgent.query when result is a plain string."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with plain string result
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = "Plain string response"
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify response converts to string
    assert response == "Plain string response"


@pytest.mark.unit
def test_base_agent_query_stores_metrics(mocker):
    """Test that BaseAgent.query stores metrics from the result."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with metrics
    mock_metrics = MagicMock()
    mock_agent_result = MagicMock()
    mock_agent_result.output = "Response"
    mock_agent_result.metrics = mock_metrics
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    agent.query("Test input")

    # Verify metrics are stored
    assert hasattr(agent, "_last_result")
    assert agent._last_result.metrics == mock_metrics
    assert agent.get_last_metrics() == mock_metrics


# ============================================================================
# BaseAgent.query_structured Method Tests
# ============================================================================


@pytest.mark.unit
def test_base_agent_query_structured_pydantic_response(mocker):
    """Test BaseAgent.query_structured method with Pydantic responses."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with tool call response
    mock_agent_result = MagicMock()
    mock_agent_result.tool_calls = [{"name": "MockResponse", "input": {"message": "Structured response", "status": "success"}}]
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query_structured("Test input", MockResponse)

    # Verify structured response
    assert isinstance(response, MockResponse)
    assert response.message == "Structured response"
    assert response.status == "success"


@pytest.mark.unit
def test_base_agent_query_structured_json_fallback(mocker):
    """Test BaseAgent.query_structured with JSON string fallback."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with JSON string response
    json_response = '{"message": "JSON response", "status": "ok"}'
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = json_response
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query_structured("Test input", MockResponse)

    # Verify structured response from JSON
    assert isinstance(response, MockResponse)
    assert response.message == "JSON response"
    assert response.status == "ok"


@pytest.mark.unit
def test_base_agent_query_structured_invalid_response(mocker):
    """Test BaseAgent.query_structured with invalid response raises error."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with invalid response (no tool calls, not JSON)
    mock_agent_result = MagicMock()
    mock_agent_result.tool_calls = []
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify error is raised
    with pytest.raises(ValueError, match="Could not extract MockResponse"):
        agent.query_structured("Test input", MockResponse)


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.unit
def test_base_agent_query_api_error(mocker):
    """Test error handling for API errors during query."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent that raises an exception
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = Exception("API rate limit exceeded")
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify error is raised
    with pytest.raises(Exception, match="API rate limit exceeded"):
        agent.query("Test input")


@pytest.mark.unit
def test_base_agent_query_structured_api_error(mocker):
    """Test error handling for API errors during structured query."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent that raises an exception
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = Exception("Service unavailable")
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify error is raised
    with pytest.raises(Exception, match="Service unavailable"):
        agent.query_structured("Test input", MockResponse)


@pytest.mark.unit
def test_base_agent_fallback_model_on_initialization_error(mocker):
    """Test that BaseAgent falls back to fallback model on initialization error."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel to fail on first call, succeed on second
    mock_primary_model = MagicMock()
    mock_fallback_model = MagicMock()

    bedrock_model_calls = [mock_primary_model, mock_fallback_model]
    mock_bedrock_model_class = MagicMock(side_effect=bedrock_model_calls)
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", mock_bedrock_model_class)

    # Mock Agent to fail on first call (primary model), succeed on second (fallback)
    mock_agent_class = MagicMock()
    mock_agent_class.side_effect = [Exception("Primary model not available"), MagicMock()]  # Fallback agent succeeds
    mocker.patch("cli_tool.core.agents.base_agent.Agent", mock_agent_class)

    # Mock FALLBACK_MODEL_ID
    mocker.patch("cli_tool.core.agents.base_agent.FALLBACK_MODEL_ID", "fallback-model-id")

    # Create agent (should trigger fallback)
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Force agent creation
    agent._get_agent()

    # Verify fallback was used (Agent called twice)
    assert mock_agent_class.call_count == 2


@pytest.mark.unit
def test_base_agent_invalid_response_format(mocker):
    """Test error handling for invalid response format."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with None response
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = None
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify response converts None to string
    assert response == "None"


# ============================================================================
# Lazy Initialization Tests
# ============================================================================


@pytest.mark.unit
def test_base_agent_lazy_initialization():
    """Test that agent is not created until first query."""
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Agent should not be created yet
    assert agent.agent is None

    # No AWS calls should have been made yet
    # (This is implicit - if AWS calls were made, they would fail without mocks)


@pytest.mark.unit
def test_base_agent_reuses_agent_instance(mocker):
    """Test that agent instance is reused across multiple queries."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent
    mock_agent_result = MagicMock()
    mock_agent_result.output = "Response"
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mock_agent_class = MagicMock(return_value=mock_agent_instance)
    mocker.patch("cli_tool.core.agents.base_agent.Agent", mock_agent_class)

    # Create agent and make multiple queries
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    agent.query("First query")
    agent.query("Second query")

    # Verify Agent was only created once
    assert mock_agent_class.call_count == 1

    # Verify agent instance was called twice
    assert mock_agent_instance.call_count == 2


# ============================================================================
# Metrics Tests
# ============================================================================


@pytest.mark.unit
def test_base_agent_get_metrics_summary(mocker):
    """Test get_metrics_summary returns summary from last execution."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with metrics
    mock_metrics = MagicMock()
    mock_metrics.get_summary.return_value = {"tokens": 100, "duration": 1.5}
    mock_agent_result = MagicMock()
    mock_agent_result.output = "Response"
    mock_agent_result.metrics = mock_metrics
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    agent.query("Test input")

    # Verify metrics summary
    summary = agent.get_metrics_summary()
    assert summary == {"tokens": 100, "duration": 1.5}


@pytest.mark.unit
def test_base_agent_get_metrics_summary_no_execution():
    """Test get_metrics_summary returns empty dict when no execution occurred."""
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # No query has been made yet
    summary = agent.get_metrics_summary()
    assert summary == {}


@pytest.mark.unit
def test_base_agent_get_last_metrics_no_execution():
    """Test get_last_metrics returns None when no execution occurred."""
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # No query has been made yet
    metrics = agent.get_last_metrics()
    assert metrics is None


# ============================================================================
# Edge Case Tests (Task 2.6)
# ============================================================================


@pytest.mark.unit
def test_base_agent_query_empty_response(mocker):
    """Test handling of empty responses from the agent."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with empty string response
    mock_agent_result = MagicMock()
    mock_agent_result.output = ""
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify empty response is handled
    assert response == ""


@pytest.mark.unit
def test_base_agent_query_whitespace_only_response(mocker):
    """Test handling of whitespace-only responses from the agent."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with whitespace-only response
    mock_agent_result = MagicMock()
    mock_agent_result.output = "   \n\t  "
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify whitespace response is preserved
    assert response == "   \n\t  "


@pytest.mark.unit
def test_base_agent_query_structured_empty_response(mocker):
    """Test handling of empty responses in structured queries."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with empty response (no tool calls, empty string)
    mock_agent_result = MagicMock()
    mock_agent_result.tool_calls = []
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = ""
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify error is raised for empty structured response
    with pytest.raises(ValueError, match="Could not extract MockResponse"):
        agent.query_structured("Test input", MockResponse)


@pytest.mark.unit
def test_base_agent_query_structured_malformed_json(mocker):
    """Test handling of malformed JSON responses in structured queries."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with malformed JSON response
    malformed_json = '{"message": "test", "status": incomplete'
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = malformed_json
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify error is raised for malformed JSON
    with pytest.raises(ValueError, match="Could not extract MockResponse"):
        agent.query_structured("Test input", MockResponse)


@pytest.mark.unit
def test_base_agent_query_structured_invalid_json_schema(mocker):
    """Test handling of JSON with invalid schema in structured queries."""
    from pydantic import ValidationError

    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with valid JSON but wrong schema
    invalid_schema_json = '{"wrong_field": "value", "another_field": 123}'
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = invalid_schema_json
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify ValidationError is raised for invalid schema
    with pytest.raises(ValidationError, match="validation error"):
        agent.query_structured("Test input", MockResponse)


@pytest.mark.unit
def test_base_agent_query_structured_partial_json(mocker):
    """Test handling of partial JSON responses in structured queries."""
    from pydantic import ValidationError

    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with partial JSON (missing required field)
    partial_json = '{"message": "test only"}'
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = partial_json
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify ValidationError is raised for partial JSON (missing required field)
    with pytest.raises(ValidationError, match="validation error"):
        agent.query_structured("Test input", MockResponse)


@pytest.mark.unit
def test_base_agent_query_transient_failure_retry(mocker):
    """Test retry logic for transient failures during query."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent to fail first, then succeed
    mock_agent_result = MagicMock()
    mock_agent_result.output = "Success after retry"
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = [Exception("Transient network error"), mock_agent_result]
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # First call should fail
    with pytest.raises(Exception, match="Transient network error"):
        agent.query("Test input")

    # Second call should succeed (simulating retry by user)
    response = agent.query("Test input")
    assert response == "Success after retry"


@pytest.mark.unit
def test_base_agent_query_timeout_error(mocker):
    """Test timeout handling during query execution."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent to raise timeout error
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = TimeoutError("Request timed out after 30 seconds")
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify timeout error is raised
    with pytest.raises(TimeoutError, match="Request timed out"):
        agent.query("Test input")


@pytest.mark.unit
def test_base_agent_query_structured_timeout_error(mocker):
    """Test timeout handling during structured query execution."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent to raise timeout error
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = TimeoutError("Structured query timed out")
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify timeout error is raised
    with pytest.raises(TimeoutError, match="Structured query timed out"):
        agent.query_structured("Test input", MockResponse)


@pytest.mark.unit
def test_base_agent_query_connection_error(mocker):
    """Test handling of connection errors during query."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent to raise connection error
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = ConnectionError("Unable to connect to Bedrock service")
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify connection error is raised
    with pytest.raises(ConnectionError, match="Unable to connect"):
        agent.query("Test input")


@pytest.mark.unit
def test_base_agent_query_throttling_error(mocker):
    """Test handling of throttling/rate limit errors during query."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent to raise throttling error
    mock_agent_instance = MagicMock()
    mock_agent_instance.side_effect = Exception("ThrottlingException: Rate exceeded")
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    # Verify throttling error is raised
    with pytest.raises(Exception, match="ThrottlingException"):
        agent.query("Test input")


@pytest.mark.unit
def test_base_agent_query_structured_with_extra_fields(mocker):
    """Test handling of JSON with extra fields in structured queries."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with JSON containing extra fields
    json_with_extra = '{"message": "test", "status": "ok", "extra_field": "ignored", "another": 123}'
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = json_with_extra
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query with structured response
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query_structured("Test input", MockResponse)

    # Verify structured response ignores extra fields (Pydantic default behavior)
    assert isinstance(response, MockResponse)
    assert response.message == "test"
    assert response.status == "ok"
    assert not hasattr(response, "extra_field")


@pytest.mark.unit
def test_base_agent_query_very_long_response(mocker):
    """Test handling of very long responses from the agent."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with very long response (10,000 characters)
    long_response = "A" * 10000
    mock_agent_result = MagicMock()
    mock_agent_result.output = long_response
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify long response is handled correctly
    assert len(response) == 10000
    assert response == long_response


@pytest.mark.unit
def test_base_agent_query_unicode_response(mocker):
    """Test handling of Unicode characters in responses."""
    # Mock AWS session creation
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    # Mock BedrockModel
    mock_bedrock_model = MagicMock()
    mocker.patch("cli_tool.core.agents.base_agent.BedrockModel", return_value=mock_bedrock_model)

    # Mock Agent with Unicode response
    unicode_response = "Hello 世界 🌍 Привет مرحبا"
    mock_agent_result = MagicMock()
    mock_agent_result.output = unicode_response
    mock_agent_instance = MagicMock()
    mock_agent_instance.return_value = mock_agent_result
    mocker.patch("cli_tool.core.agents.base_agent.Agent", return_value=mock_agent_instance)

    # Create agent and query
    agent = BaseAgent(name="TestAgent", system_prompt="You are a test assistant")

    response = agent.query("Test input")

    # Verify Unicode response is handled correctly
    assert response == unicode_response
    assert "世界" in response
    assert "🌍" in response
