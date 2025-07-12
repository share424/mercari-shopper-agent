"""Mercari Search Tool.

This tool is used to search for items on Mercari.
"""

from typing import Type

from pydantic import BaseModel, Field

from app.libs.mercari_jp import MercariJPSearch
from app.types import Item, State, Tool, ToolResult
from app.utils import get_llm_friendly_items


class MercariJPSearchToolArgs(BaseModel):
    """Arguments for the mercari_search tool."""

    query: str = Field(description="The query to search for, better to be in Japanese")
    min_price: int | None = Field(description="The minimum price to search for in JPY")
    max_price: int | None = Field(description="The maximum price to search for in JPY")


class MercariJPSearchTool(Tool):
    """Mercari Search Tool."""

    name: str = "mercari_japan_search"
    """The name of the tool."""

    description: str = "Search for items on Mercari. Each search will add more items to the search results."
    """The description of the tool."""

    args_schema: Type[BaseModel] = MercariJPSearchToolArgs
    """The arguments schema for the tool."""

    async def search_items(self, query: str, min_price: int | None, max_price: int | None) -> list[Item]:
        """Search for items on Mercari.

        Args:
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in USD.
            max_price (int | None): The maximum price to search for in USD.

        Returns:
            list[Item]: The list of items found.
        """
        async with MercariJPSearch() as ms:
            return await ms.search_items(query, min_price, max_price)

    async def execute(self, state: State, query: str, min_price: int | None, max_price: int | None) -> ToolResult:
        """Execute the tool.

        Args:
            state (State): The current state.
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in USD.
            max_price (int | None): The maximum price to search for in USD.

        Returns:
            ToolResult: The result of the tool execution.
        """
        try:
            search_results = await self.search_items(query, min_price, max_price)
            state.search_results.extend(search_results)
            state.remove_duplicate_search_results()
            return ToolResult(
                is_error=False,
                tool_response=get_llm_friendly_items(search_results),
                updated_state=state,
            )
        except Exception:
            return ToolResult(
                is_error=True,
                tool_response="Failed to search items. Please try again.",
                updated_state=state,
            )
