"""Select Best Item Tool.

This tool is used to select the best item from the search results.
"""

from typing import Type

from loguru import logger
from pydantic import BaseModel, Field

from app.types import Item, ItemRecommendation, State, Tool, ToolResult
from app.utils import get_llm_friendly_items


class SelectBestItemToolArgs(BaseModel):
    """Arguments for the select_best_item tool."""

    recommended_items: list[tuple[str, str]] = Field(description="The IDs and reasons of the items to select")


class SelectBestItemTool(Tool):
    """Select Best Item Tool."""

    name: str = "select_best_item"
    """The name of the tool."""

    description: str = "Select the best item from the search results"
    """The description of the tool."""

    args_schema: Type[BaseModel] = SelectBestItemToolArgs

    async def execute(self, state: State, recommended_items: list[tuple[str, str]]) -> ToolResult:
        """Execute the tool.

        Args:
            state (State): The current state.
            recommended_items (list[tuple[str, str]]): The IDs and reasons of the items to select.

        Returns:
            ToolResult: The result of the tool execution.
        """
        logger.debug(f"Selecting best item: {recommended_items}")
        selected_items: list[Item] = []
        for item_id, reason in recommended_items:
            selected_item = [item for item in state.search_results if item.id == item_id]
            if len(selected_item) == 0:
                return ToolResult(
                    is_error=False,
                    tool_response=f"Item with id {item_id} not found",
                    updated_state=state,
                )
            selected_items.append(selected_item[0])
            state.recommended_items.append(ItemRecommendation(item=selected_item[0], reason=reason))

        return ToolResult(
            is_error=False,
            tool_response=get_llm_friendly_items(selected_items),
            updated_state=state,
            simplified_tool_response=self._get_simplified_tool_response(selected_items),
        )

    def _get_simplified_tool_response(self, items: list[Item]) -> str:
        """Get the simplified tool response."""
        text = "Selected items:\n"
        for i, item in enumerate(items, start=1):
            text += f"{i}. [{item.name} ({item.currency} {item.price})]({item.item_url})\n"
        return text
