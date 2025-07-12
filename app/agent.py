"""Mercari Shopping Agent.

This agent is used to search for items on Mercari and select the best item.
"""

from typing import Any, AsyncGenerator, Generator, cast

from aioretry.retry import retry
from anthropic import AsyncAnthropic
from anthropic.types import (
    Message,
    MessageParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
)
from loguru import logger

from app.prompts.agent import RECOMMEND_MORE_ITEMS_PROMPT, SYSTEM_PROMPT, USER_PROMPT
from app.tools import (
    EvaluateSearchResultTool,
    MarketResearchTool,
    MercariJPSearchTool,
    PriceCalculatorTool,
    SelectBestItemTool,
)
from app.types import AgentAction, ItemRecommendation, State, Tool
from app.utils import retry_policy


class MercariShoppingAgent:
    """Mercari Shopping Agent.

    This agent is used to search for items on Mercari and select the best item.
    """

    def __init__(
        self,
        client: AsyncAnthropic,
        model: str,
        serpapi_api_key: str,
        max_iterations: int = 15,
        tools: list[Tool] | None = None,
    ):
        """Initialize the Mercari Shopping Agent.

        Args:
            client (AsyncAnthropic): The Anthropic client.
            model (str): The model to use.
            serpapi_api_key (str): The API key for the SerpApi.
            max_iterations (int): The maximum number of iterations. Defaults to 15.
            tools (list[Tool]): The tools to use. Defaults to [MercariSearchTool(), SelectBestItemTool(),].
        """
        self.client = client
        self.model = model
        self.max_iterations = max_iterations
        self.tools = tools or [
            MercariJPSearchTool(),
            SelectBestItemTool(),
            MarketResearchTool(api_key=serpapi_api_key, client=client, model=model),
            EvaluateSearchResultTool(client=client, model=model),
            PriceCalculatorTool(),
        ]
        self._tool_params = self._get_tool_params()
        self._tools_by_name = {tool.name: tool for tool in self.tools}

    def _get_tool_params(self) -> list[ToolParam]:
        """Get the tool parameters.

        Returns:
            list[ToolParam]: The tool parameters.
        """
        return [tool.tool_param for tool in self.tools]

    def _add_current_state_to_messages(self, messages: list[MessageParam], state: State) -> list[MessageParam]:
        """Add the current state to the messages.

        Args:
            messages (list[MessageParam]): The messages.
            state (State): The current state.

        Returns:
            list[MessageParam]: The messages.
        """
        messages.append(
            MessageParam(
                role="user",
                content=USER_PROMPT.format(query=state.user_query),
            )
        )
        return messages

    def _add_recommend_more_items_to_messages(self, messages: list[MessageParam], state: State) -> list[MessageParam]:
        """Add the recommend more items to the messages."""
        num_items = len(state.recommended_items)
        num_items_to_recommend = 3 - num_items
        messages.append(
            MessageParam(
                role="user",
                content=RECOMMEND_MORE_ITEMS_PROMPT.format(
                    num_items=num_items,
                    num_items_to_recommend=num_items_to_recommend,
                ),
            )
        )
        return messages

    def _add_tool_results_to_messages(
        self, messages: list[MessageParam], tool_results: list[ToolResultBlockParam]
    ) -> list[MessageParam]:
        """Add the tool results to the messages.

        Args:
            messages (list[MessageParam]): The messages.
            tool_results (list[ToolResultBlockParam]): The tool results.

        Returns:
            list[MessageParam]: The messages.
        """
        messages.append(
            cast(
                MessageParam,
                {
                    "role": "user",
                    "content": tool_results,
                },
            )
        )
        return messages

    def _add_llm_response_to_messages(self, messages: list[MessageParam], response: Message) -> list[MessageParam]:
        """Add the LLM response to the messages.

        Args:
            messages (list[MessageParam]): The messages.
            response (Message): The LLM response.

        Returns:
            list[MessageParam]: The messages.
        """
        messages.append(MessageParam(role=response.role, content=response.content))
        return messages

    @retry(retry_policy)
    async def _get_llm_response(self, messages: list[MessageParam]) -> Message:
        """Get the LLM response.

        Args:
            messages (list[MessageParam]): The messages.

        Returns:
            Message: The LLM response.
        """
        return await self.client.messages.create(
            model=self.model,
            system=SYSTEM_PROMPT,
            tools=self._tool_params,
            messages=messages,
            max_tokens=4096,
        )

    def _should_stop(self, state: State) -> bool:
        """Check if the agent should stop.

        Args:
            state (State): The current state.

        Returns:
            bool: True if the agent should stop, False otherwise.
        """
        return len(state.recommended_items) >= 3  # noqa: PLR2004

    async def _handle_tool_call(self, state: State, response: Message) -> tuple[State, list[ToolResultBlockParam]]:
        """Handle the tool call.

        Args:
            state (State): The current state.
            response (Message): The LLM response.

        Returns:
            tuple[State, list[ToolResultBlockParam]]: The updated state and the tool results.
        """
        tool_calls = [block for block in response.content if isinstance(block, ToolUseBlock)]
        tool_results: list[ToolResultBlockParam] = []
        for tool_call in tool_calls:
            tool = self._tools_by_name.get(tool_call.name, None)
            if not tool:
                tool_results.append(
                    ToolResultBlockParam(
                        tool_use_id=tool_call.id,
                        type="tool_result",
                        content="Tool not found",
                        is_error=True,
                    )
                )
                continue

            kwargs = cast(dict[str, Any], tool_call.input)
            tool_response = await tool.execute(state, **kwargs)
            tool_results.append(
                ToolResultBlockParam(
                    tool_use_id=tool_call.id,
                    type="tool_result",
                    content=tool_response.tool_response,
                    is_error=tool_response.is_error,
                )
            )
            state = tool_response.updated_state
        return state, tool_results

    def _log_llm_response(self, response: Message):
        """Log the LLM response.

        Args:
            response (Message): The LLM response.
        """
        for content in response.content:
            if not content.type == "text":
                logger.debug(f"LLM response: {content.type}")
                continue
            logger.info(f"LLM response: {content.text}")

    def _get_llm_response_text(self, response: Message) -> Generator[str, None, None]:
        """Get the LLM response.

        Args:
            response (Message): The LLM response.
        """
        for content in response.content:
            if not content.type == "text":
                logger.debug(f"LLM response: {content.type}")
                continue
            yield content.text

    @logger.catch
    async def _run(self, query: str) -> list[ItemRecommendation]:
        """Run the agent.

        The actual logic of the agent is implemented in this function.

        Args:
            query (str): The user query.

        Returns:
            list[ItemRecommendation]: The recommended items.
        """
        state = State(user_query=query)
        messages: list[MessageParam] = []
        # 0. Add current state to messages
        messages = self._add_current_state_to_messages(messages, state)

        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}")

            if self._should_stop(state):
                return state.recommended_items

            # if the minimum number of recommended items is not reached,
            # ask the LLM to select the remaining items
            if len(state.recommended_items) > 0:
                messages = self._add_recommend_more_items_to_messages(messages, state)

            # 1. Call LLM with current state
            response = await self._get_llm_response(messages)
            messages = self._add_llm_response_to_messages(messages, response)
            self._log_llm_response(response)

            # 2. Check if there is a tool call
            if response.stop_reason == "tool_use":
                logger.info("Tool call detected")
                state, tool_results = await self._handle_tool_call(state, response)
                messages = self._add_tool_results_to_messages(messages, tool_results)
            else:
                logger.info(f"Stop reason: {response.stop_reason}")
                return state.recommended_items

        logger.info("Max iterations reached")
        return state.recommended_items

    async def run(self, query: str) -> list[ItemRecommendation]:
        """Run the agent.

        Args:
            query (str): The user query.

        Returns:
            list[ItemRecommendation]: The recommended items.
        """
        with logger.contextualize(query=query):
            return await self._run(query)

    async def _handle_tool_call_stream(
        self, state: State, response: Message
    ) -> AsyncGenerator[AgentAction | tuple[State, list[ToolResultBlockParam]], None]:
        """Handle the tool call.

        Args:
            state (State): The current state.
            response (Message): The LLM response.
        """
        tool_calls = [block for block in response.content if isinstance(block, ToolUseBlock)]
        tool_results: list[ToolResultBlockParam] = []
        for tool_call in tool_calls:
            tool = self._tools_by_name.get(tool_call.name, None)
            yield AgentAction(
                action="tool_call",
                text=f"Executing tool call: {tool_call.name}",
            )
            if not tool:
                tool_results.append(
                    ToolResultBlockParam(
                        tool_use_id=tool_call.id,
                        type="tool_result",
                        content="Tool not found",
                        is_error=True,
                    )
                )
                yield AgentAction(
                    action="tool_result",
                    text=f"Tool not found: {tool_call.name}",
                )
                continue

            kwargs = cast(dict[str, Any], tool_call.input)
            tool_response = await tool.execute(state, **kwargs)
            tool_results.append(
                ToolResultBlockParam(
                    tool_use_id=tool_call.id,
                    type="tool_result",
                    content=tool_response.tool_response,
                    is_error=tool_response.is_error,
                )
            )
            state = tool_response.updated_state
            yield AgentAction(
                action="tool_result",
                text=tool_response.simplified_tool_response or "empty tool result",
            )

        yield state, tool_results

    async def _run_stream(self, query: str) -> AsyncGenerator[AgentAction, None]:
        """Run the agent in stream mode.

        The actual logic of the agent is implemented in this function.

        Args:
            query (str): The user query.

        """
        yield AgentAction(
            action="reasoning",
            text="Thinking...",
        )

        state = State(user_query=query)
        messages: list[MessageParam] = []
        # 0. Add current state to messages
        messages = self._add_current_state_to_messages(messages, state)

        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}")

            if self._should_stop(state):
                yield AgentAction(
                    action="stop",
                    text="Final recommendations",
                    item_recommendations=state.recommended_items,
                )
                return

            # if the minimum number of recommended items is not reached,
            # ask the LLM to select the remaining items
            if len(state.recommended_items) > 0:
                messages = self._add_recommend_more_items_to_messages(messages, state)
                yield AgentAction(
                    action="reasoning",
                    text="Recommend more items",
                )

            # 1. Call LLM with current state
            response = await self._get_llm_response(messages)
            messages = self._add_llm_response_to_messages(messages, response)
            for message in self._get_llm_response_text(response):
                yield AgentAction(
                    action="reasoning",
                    text=message,
                )

            # 2. Check if there is a tool call
            if response.stop_reason == "tool_use":
                logger.info("Tool call detected")
                async for action in self._handle_tool_call_stream(state, response):
                    if isinstance(action, AgentAction):
                        yield action
                        continue
                    state, tool_results = action
                    messages = self._add_tool_results_to_messages(messages, tool_results)
                    break
            else:
                logger.info(f"Stop reason: {response.stop_reason}")
                yield AgentAction(
                    action="stop",
                    text=f"Stop reason: {response.stop_reason}",
                    item_recommendations=state.recommended_items,
                )
                return

        logger.info("Max iterations reached")
        yield AgentAction(
            action="stop",
            text="Max iterations reached",
            item_recommendations=state.recommended_items,
        )

    async def run_stream(self, query: str) -> AsyncGenerator[AgentAction, None]:
        """Run the agent.

        Args:
            query (str): The user query.

        Returns:
            AsyncGenerator[str, None]: The recommended items.
        """
        async for chunk in self._run_stream(query):
            yield chunk
