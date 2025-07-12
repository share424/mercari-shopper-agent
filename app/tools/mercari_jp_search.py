"""Mercari Search Tool.

This tool is used to search for items on Mercari.
"""

from typing import Literal, Type

from pydantic import BaseModel, Field

from app.libs.mercari_jp import MercariJPSearch
from app.types import Item, State, Tool, ToolResult
from app.utils import get_llm_friendly_items


class MercariJPSearchToolArgs(BaseModel):
    """Arguments for the mercari_search tool."""

    query: str = Field(description="The query to search for, better to be in Japanese")
    min_price: int | None = Field(description="The minimum price to search for in JPY")
    max_price: int | None = Field(description="The maximum price to search for in JPY")
    max_items: int = Field(10, description="The maximum number of items to search for. Defaults to 10.")
    sort_by: Literal["num_likes", "score", "created_time", "price"] = Field(
        "score",
        description=(
            "The field to sort by. Available options are:\n"
            "1. num_likes: Sort by the number of likes\n"
            "2. score: Sort by most relevant items (Default)\n"
            "3. created_time: Sort by the created time\n"
            "4. price: Sort by the price\n"
        ),
    )
    order: Literal["asc", "desc"] | None = Field("desc", description="The order to sort by. Defaults to 'desc'.")


class MercariJPSearchTool(Tool):
    """Mercari Search Tool."""

    name: str = "mercari_japan_search"
    """The name of the tool."""

    description: str = "Search for items on Mercari. Each search will add more items to the search results."
    """The description of the tool."""

    args_schema: Type[BaseModel] = MercariJPSearchToolArgs
    """The arguments schema for the tool."""

    async def search_items(  # noqa: PLR0913
        self,
        query: str,
        min_price: int | None,
        max_price: int | None,
        max_items: int = 10,
        sort_by: Literal["num_likes", "score", "created_time", "price"] = "score",
        order: Literal["asc", "desc"] = "desc",
    ) -> list[Item]:
        """Search for items on Mercari.

        Args:
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in USD.
            max_price (int | None): The maximum price to search for in USD.
            max_items (int): The maximum number of items to search for. Defaults to 10.
            sort_by (Literal["num_likes", "score", "created_time", "price"]): The field to sort by. Defaults to "score".
            order (Literal["asc", "desc"]): The order to sort by. Defaults to "desc".

        Returns:
            list[Item]: The list of items found.
        """
        async with MercariJPSearch() as ms:
            return await ms.search_items(query, min_price, max_price, max_items, sort_by, order)

    async def execute(  # noqa: PLR0913
        self,
        state: State,
        query: str,
        min_price: int | None,
        max_price: int | None,
        max_items: int = 10,
        sort_by: Literal["num_likes", "score", "created_time", "price"] = "score",
        order: Literal["asc", "desc"] = "desc",
    ) -> ToolResult:
        """Execute the tool.

        Args:
            state (State): The current state.
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in USD.
            max_price (int | None): The maximum price to search for in USD.
            max_items (int): The maximum number of items to search for. Defaults to 10.
            sort_by (Literal["num_likes", "score", "created_time", "price"]): The field to sort by. Defaults to "score".
            order (Literal["asc", "desc"]): The order to sort by. Defaults to "desc".

        Returns:
            ToolResult: The result of the tool execution.
        """
        try:
            search_results = await self.search_items(query, min_price, max_price, max_items, sort_by, order)
            state.search_results.extend(search_results)
            state.remove_duplicate_search_results()
            return ToolResult(
                is_error=False,
                tool_response=get_llm_friendly_items(search_results),
                updated_state=state,
                simplified_tool_response=self._get_simplified_tool_response(search_results),
            )
        except Exception:
            return ToolResult(
                is_error=True,
                tool_response="Failed to search items. Please try again.",
                updated_state=state,
                simplified_tool_response="Failed to search items. Please try again.",
            )

    def _get_simplified_tool_response(self, items: list[Item]) -> str:
        """Get the simplified tool response."""
        text = "Search results:\n"
        for i, item in enumerate(items, start=1):
            text += f"{i}. [{item.name} ({item.currency} {item.price})]({item.item_url})\n"
        return text
