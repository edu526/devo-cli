from typing import Any, Callable, List, Optional, Type, TypeVar

from pydantic import BaseModel
from rich.console import Console
from strands import Agent
from strands.models import BedrockModel

from cli_tool.config import BEDROCK_MODEL_ID, FALLBACK_MODEL_ID
from cli_tool.ui.console_ui import console_ui

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    """
    Base class for agents using Strands with integrated rich logging.

    This class provides a clean interface for creating AI agents with:
    - Automatic model fallback (primary -> fallback)
    - Integrated rich console logging with beautiful formatting
    - Dynamic tool management
    - Custom callback support
    - Streaming support with visual feedback

    Features:
    - 🎨 Rich console output with colors and panels
    - 🔧 Dynamic tool addition and removal
    - 📡 Real-time streaming with visual feedback
    - 🛡️ Automatic error handling and model fallback
    - 🔄 Lazy agent initialization for better performance
    - 📝 Custom callback handler support

    Example:
        ```python
        # Simple usage
        agent = BaseAgent(
            name="MyAgent",
            system_prompt="You are a helpful assistant"
        )
        response = agent.query("Hello!")

        # Advanced usage with tools and custom callback
        agent = BaseAgent(
            name="CodeAgent",
            system_prompt="You are a code assistant",
            tools=[get_file_content, search_code_references],
            enable_rich_logging=True,
            custom_callback_handler=my_callback
        )
        response = agent.query_with_streaming("Analyze this code")
        ```
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        llm_model_id: str = BEDROCK_MODEL_ID,
        region_name: str = "us-east-1",
        tools: Optional[List[Any]] = None,
        enable_rich_logging: bool = False,
        custom_callback_handler: Optional[Callable] = None,
    ):
        """
        Initialize the BaseAgent with Strands and integrated ConsoleUI.

        Args:
            name: Agent name (for identification)
            system_prompt: System prompt for the agent
            llm_model_id: AWS Bedrock model ID
            region_name: AWS region name
            tools: List of tools to provide to the agent
            enable_rich_logging: Enable rich console logging instead of ConsoleUI (default: False)
            custom_callback_handler: Optional custom callback for streaming events
        """
        self.name = name
        self.system_prompt = system_prompt
        self.llm_model_id = llm_model_id
        self.region_name = region_name
        self.tools = tools or []
        self.enable_rich_logging = enable_rich_logging
        self.custom_callback_handler = custom_callback_handler
        self.agent = None  # Lazy initialization

        # Initialize rich console for logging
        self.console = Console() if enable_rich_logging else None
        self._event_grouping_active = False

    def _console_ui_callback(self, **kwargs):
        """Built-in ConsoleUI callback handler."""

        # Text generation events - show real AI output
        if "data" in kwargs:
            text_chunk = kwargs["data"]
            console_ui.show_ai_real_response(text_chunk, is_complete=False)

        # Tool usage events - only show when tool changes
        elif "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
            tool_name = kwargs["current_tool_use"]["name"]
            # Reset event grouping when switching to tool usage
            console_ui._reset_event_grouping()
            console_ui.show_ai_thinking(f"AI is using tool: {tool_name}")

        # Reasoning events - group these as they can be frequent
        elif kwargs.get("reasoning", False) and "reasoningText" in kwargs:
            reasoning_text = kwargs["reasoningText"]
            console_ui.show_ai_thinking(f"AI reasoning: {reasoning_text[:100]}...")

        # Lifecycle events - show important ones but group minor ones
        elif kwargs.get("init_event_loop", False):
            console_ui._reset_event_grouping()
            console_ui.show_ai_thinking("AI event loop initialized")
        elif kwargs.get("start_event_loop", False):
            console_ui.show_ai_thinking("AI starting analysis cycle...")
        elif kwargs.get("start", False):
            # Group these as they can happen frequently
            console_ui.show_ai_thinking("AI beginning new processing cycle")
        elif "message" in kwargs and kwargs["message"].get("role") == "assistant":
            # Complete message received - reset grouping
            console_ui._reset_event_grouping()
            message_content = kwargs["message"].get("content", "")
            if isinstance(message_content, list) and len(message_content) > 0:
                if "text" in message_content[0]:
                    full_response = message_content[0]["text"]
                    console_ui.show_ai_real_response(full_response, is_complete=True)
        elif kwargs.get("force_stop", False):
            console_ui._reset_event_grouping()
            reason = kwargs.get("force_stop_reason", "unknown")
            console_ui.show_ai_thinking(f"AI stopped: {reason}")

    def _create_agent(self) -> Agent:
        """Create and configure the Strands agent."""
        try:
            # Try primary model
            bedrock_model = BedrockModel(
                model_id=self.llm_model_id,
                region_name=self.region_name,
            )

            if self.enable_rich_logging and self.console:
                self.console.print(f"🤖 Initializing [bold blue]{self.name}[/bold blue] with primary model: [green]{self.llm_model_id}[/green]")
            else:
                print(
                    f"🤖 Initializing {self.name} with primary model:",
                    self.llm_model_id,
                )

            return Agent(
                tools=self.tools,
                system_prompt=self.system_prompt,
                callback_handler=self._console_ui_callback,
                model=bedrock_model,
                name=self.name,
            )

        except Exception as e:
            error_msg = f"⚠️ Error initializing {self.name} with primary model: {str(e)}"
            fallback_msg = f"🔄 Switching to fallback model: {FALLBACK_MODEL_ID}"

            if self.enable_rich_logging and self.console:
                self.console.print(f"[yellow]{error_msg}[/yellow]")
                self.console.print(f"[blue]{fallback_msg}[/blue]")
            else:
                print(error_msg)
                print(fallback_msg)

            # Fallback to secondary model
            fallback_model = BedrockModel(
                model_id=FALLBACK_MODEL_ID,
                region_name=self.region_name,
            )

            return Agent(
                tools=self.tools,
                system_prompt=self.system_prompt,
                callback_handler=self._console_ui_callback,
                model=fallback_model,
                name=self.name,
            )

    def _get_agent(self) -> Agent:
        """Get the agent instance, creating it if needed."""
        if self.agent is None:
            self.agent = self._create_agent()
        return self.agent

    def query(self, input_text: str) -> str:
        """
        Run the agent with the provided input and return the output.

        Args:
            input_text: The input text to process

        Returns:
            The agent's response as a string
        """
        agent = self._get_agent()
        try:
            result = agent(input_text)
            # Store the last result for metrics access
            self._last_result = result

            # Convert AgentResult to string
            if hasattr(result, "output"):
                return str(result.output)
            elif hasattr(result, "content"):
                return str(result.content)
            else:
                return str(result)
        except Exception as e:
            print(f"❌ Error during {self.name} query:", str(e))
            raise

    def get_last_metrics(self):
        """
        Get metrics from the last agent execution.

        Returns:
            EventLoopMetrics object or None if no execution has occurred
        """
        if hasattr(self, "_last_result") and hasattr(self._last_result, "metrics"):
            return self._last_result.metrics
        return None

    def get_metrics_summary(self) -> dict:
        """
        Get a summary of metrics from the last agent execution.

        Returns:
            Dictionary with metrics summary or empty dict if no metrics available
        """
        metrics = self.get_last_metrics()
        if metrics and hasattr(metrics, "get_summary"):
            return metrics.get_summary()
        return {}

    def query_structured(self, input_text: str, response_model: Type[T]) -> T:
        """
        Run the agent with structured output using Pydantic models.

        Args:
            input_text: The input text to process
            response_model: Pydantic model class for structured response

        Returns:
            Structured response as the specified Pydantic model
        """
        agent = self._get_agent()
        try:
            # Create a new agent instance with the response model as a tool
            # This ensures the model is used correctly for structured output
            bedrock_model = agent.model

            structured_agent = Agent(
                tools=[response_model],
                system_prompt=f"""{self.system_prompt}

CRITICAL INSTRUCTION: You MUST respond by calling the {response_model.__name__} tool exactly ONCE with the appropriate parameters.
After calling the tool once, STOP. Do not call it again. Do not provide additional text responses.
""",
                callback_handler=self._console_ui_callback,
                model=bedrock_model,
                name=f"{self.name}_Structured",
            )

            # Run the structured agent
            result = structured_agent(input_text)

            # Store the last result for metrics access
            self._last_result = result

            # Extract the structured response from tool calls
            if hasattr(result, "tool_calls") and result.tool_calls:
                for tool_call in result.tool_calls:
                    if tool_call.get("name") == response_model.__name__:
                        return response_model(**tool_call.get("input", {}))

            # Fallback: check if result has the data we need
            if isinstance(result, str):
                # Try to parse JSON from the string
                import json

                try:
                    data = json.loads(result)
                    return response_model(**data)
                except (json.JSONDecodeError, TypeError):
                    pass

            raise ValueError(f"Could not extract {response_model.__name__} from agent response. Result type: {type(result)}")

        except Exception as e:
            print(f"❌ Error during {self.name} structured query:", str(e))
            raise
