"""Select Best Item Tool.

This tool is used to select the best item from the search results.
"""

from typing import Type

import json_repair
from aioretry.retry import retry
from anthropic import AsyncAnthropic
from loguru import logger
from pydantic import BaseModel

from app.prompts.select_best_item import SYSTEM_PROMPT, USER_PROMPT
from app.types import Item, ItemRecommendation, State, Tool, ToolResult
from app.utils import get_llm_friendly_items, retry_policy


class SelectBestItemToolArgs(BaseModel):
    """Arguments for the select_best_item tool."""


class SelectBestItemTool(Tool):
    """Select Best Item Tool."""

    name: str = "select_best_item"
    """The name of the tool."""

    description: str = "Select the best item based on item that has been evaluated and has a relevance score greater than or equal to the minimum relevance score."  # noqa: E501
    """The description of the tool."""

    min_relevance_score: float = 0.8
    """The minimum relevance score to select an item."""

    temperature: float = 0.0
    """The temperature to use for the tool."""

    client: AsyncAnthropic
    """The client for the tool."""

    model: str = "claude-3-5-sonnet-latest"
    """The model to use for the tool."""

    args_schema: Type[BaseModel] = SelectBestItemToolArgs

    @retry(retry_policy)
    async def _select_best_item(self, items: list[Item], user_query: str) -> list[ItemRecommendation]:
        """Select the best item from the search results."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=self.temperature,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT.format(candidate_items=get_llm_friendly_items(items), user_query=user_query),
                },
            ],
        )
        try:
            text = None
            for content in response.content:
                if content.type == "text":
                    text = content.text
                    break

            if text is None:
                return []

            parsed_item_recommendations = json_repair.loads(text)
            if not isinstance(parsed_item_recommendations, list):
                return []

            recommendations: list[ItemRecommendation] = []
            for parsed_item in parsed_item_recommendations:
                if not isinstance(parsed_item, dict):
                    continue

                item_id = parsed_item.get("item_id", "")
                item = [item for item in items if item.id == item_id][0]
                del parsed_item["item_id"]
                parsed_item["item"] = item
                recommendations.append(ItemRecommendation.model_validate(parsed_item, strict=False))

            return recommendations
        except Exception as e:
            logger.error(f"Error evaluating item: {e}")
            return []

    async def execute(self, state: State) -> ToolResult:
        """Execute the tool.

        Args:
            state (State): The current state.
            recommended_items (list[tuple[str, str]]): The IDs and reasons of the items to select.

        Returns:
            ToolResult: The result of the tool execution.
        """
        candidates = [
            item
            for item in state.recommended_candidates
            if item.relevance_score and item.relevance_score.score >= self.min_relevance_score
        ]
        recommendations = await self._select_best_item(candidates, state.user_query)
        state.recommended_items.extend(recommendations)

        is_error = recommendations == []
        error_msg = "No recommendations found" if is_error else ""

        return ToolResult(
            is_error=recommendations == [],
            tool_response="Successfully added items to recommendation items" if not is_error else error_msg,
            updated_state=state,
            simplified_tool_response=self._get_simplified_tool_response(recommendations),
        )

    def _get_simplified_tool_response(self, items: list[ItemRecommendation]) -> str:
        """Get the simplified tool response."""
        text = "Selected items:\n"
        for i, item in enumerate(items, start=1):
            text += f"{i}. [{item.item.name} ({item.item.currency} {item.item.price})]({item.item.item_url})\n"
        return text
