"""Mercari Shopping Agent.

This agent is used to search for items on Mercari and select the best item.
"""

import json
from copy import deepcopy
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
from pydantic import BaseModel

from app.prompts.agent_jp import CONDENSED_PROMPT, RECOMMEND_MORE_ITEMS_PROMPT, SYSTEM_PROMPT, USER_PROMPT
from app.tools import (
    EvaluateSearchResultTool,
    MarketResearchTool,
    MercariJPSearchTool,
    PriceCalculatorTool,
    SelectBestItemTool,
)
from app.types import AgentAction, ItemRecommendation, State, Tool
from app.utils import get_llm_friendly_items, retry_policy


class MercariShoppingAgent:
    """Mercari Shopping Agent.

    This agent is used to search for items on Mercari and select the best item.
    """

    def __init__(  # noqa: PLR0913
        self,
        client: AsyncAnthropic,
        model: str,
        max_tokens: int = 4096,
        max_context_tokens: int = 70000,
        temperature: float = 0.0,
        max_iterations: int = 15,
        keep_n_last_messages: int = 3,
        tools: list[Tool] | None = None,
        save_trajectory: bool = False,
        trajectory_file: str = "trajectory.json",
    ):
        """Initialize the Mercari Shopping Agent.

        Args:
            client (AsyncAnthropic): The Anthropic client.
            model (str): The model to use.
            max_tokens (int): The maximum number of tokens. Defaults to 4096.
            max_context_tokens (int): The maximum number of tokens in the context. Defaults to 40000.
            temperature (float): The temperature to use for the LLM. Defaults to 0.0.
            max_iterations (int): The maximum number of iterations. Defaults to 15.
            keep_n_last_messages (int): The number of last messages to keep. Defaults to 3.
            tools (list[Tool]): The tools to use.
            save_trajectory (bool): Whether to save the trajectory for debugging or evaluation. Defaults to False.
            trajectory_file (str): The file to save the trajectory. Defaults to "trajectory.json".
        """
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.max_context_tokens = max_context_tokens
        self.keep_n_last_messages = keep_n_last_messages
        self.save_trajectory = save_trajectory
        self.trajectory_file = trajectory_file
        self.tools = tools or [
            MercariJPSearchTool(),
            SelectBestItemTool(client=client, model=model),
            MarketResearchTool(client=client, model=model),
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
        self._save_trajectory(messages)
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
        self._save_trajectory(messages)
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
        self._save_trajectory(messages)
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
        self._save_trajectory(messages)
        return messages

    @retry(retry_policy)
    async def _get_llm_response(self, messages: list[MessageParam]) -> Message:
        """Get the LLM response.

        Args:
            messages (list[MessageParam]): The messages.

        Returns:
            Message: The LLM response.
        """
        tools = self._tool_params
        tools[-1]["cache_control"] = {"type": "ephemeral"}
        if isinstance(messages[-1]["content"], list):
            messages[-1]["content"][-1]["cache_control"] = {"type": "ephemeral"}  # type: ignore

        response = await self.client.messages.create(
            model=self.model,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        if isinstance(messages[-1]["content"], list):
            del messages[-1]["content"][-1]["cache_control"]  # type: ignore

        return response

    def _save_trajectory(self, messages: list[MessageParam]):
        """Save the trajectory.

        Args:
            messages (list[MessageParam]): The messages.
        """
        if not self.save_trajectory:
            return

        temp_messages = deepcopy(messages)
        safe_messages = []
        for message in temp_messages:
            if isinstance(message["content"], list):
                fixed_content = []
                for content in message["content"]:
                    if isinstance(content, BaseModel):
                        fixed_content.append(content.model_dump())
                    else:
                        fixed_content.append(content)
                message["content"] = fixed_content
            safe_messages.append(message)

        with open(self.trajectory_file, "w") as f:
            f.write(json.dumps(safe_messages, indent=2, ensure_ascii=False))

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

    async def _is_conversation_too_long(self, messages: list[MessageParam]) -> bool:
        """Check if the conversation is too long."""
        response = await self.client.messages.count_tokens(
            model=self.model,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        return response.input_tokens > self.max_context_tokens

    def _condense_messages(self, state: State, messages: list[MessageParam]) -> list[MessageParam]:
        """Condense the messages."""
        if len(messages) <= self.keep_n_last_messages:
            return messages

        recommended_candidates = get_llm_friendly_items(state.recommended_candidates, include_market_research=True)

        condensed_messages = [
            MessageParam(
                role="user",
                content=CONDENSED_PROMPT.format(
                    n_last_messages=self.keep_n_last_messages,
                    previous_messages=json.dumps(messages[-self.keep_n_last_messages :], indent=2),
                    recommended_candidates=recommended_candidates,
                    user_query=state.user_query,
                ),
            ),
        ]
        return condensed_messages

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
        messages = self._add_current_state_to_messages(messages, state)

        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}")

            if self._should_stop(state):
                return state.recommended_items

            if await self._is_conversation_too_long(messages):
                messages = self._condense_messages(state, messages)

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

            if self._should_recommend_more_items(state, response):
                messages = self._add_recommend_more_items_to_messages(messages, state)

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
        state = State(user_query=query)
        messages: list[MessageParam] = []
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

            if await self._is_conversation_too_long(messages):
                messages = self._condense_messages(state, messages)
                yield AgentAction(
                    action="reasoning",
                    text="The conversation is too long. Condensing the conversation.",
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

            if self._should_recommend_more_items(state, response):
                messages = self._add_recommend_more_items_to_messages(messages, state)
                yield AgentAction(
                    action="reasoning",
                    text="Recommend more items",
                )

        logger.info("Max iterations reached")
        yield AgentAction(
            action="stop",
            text="Max iterations reached",
            item_recommendations=state.recommended_items,
        )

    def _should_recommend_more_items(self, state: State, response: Message) -> bool:
        """Check if the LLM should recommend more items."""
        tool_calls = [block.name for block in response.content if isinstance(block, ToolUseBlock)]
        if "select_best_item" in tool_calls and len(state.recommended_items) < 3:  # noqa: PLR2004
            return True
        return False

    async def run_stream(self, query: str) -> AsyncGenerator[AgentAction, None]:
        """Run the agent.

        Args:
            query (str): The user query.

        Returns:
            AsyncGenerator[str, None]: The recommended items.
        """
        async for chunk in self._run_stream(query):
            yield chunk
