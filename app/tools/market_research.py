"""Market Research Tool."""

import asyncio
from asyncio import Semaphore
from typing import Type

from loguru import logger
from pydantic import BaseModel, Field

from app.libs.market_research.market_research import MarketResearch
from app.types import MarketIntelligenceResult, State, Tool, ToolResult


class GeneralMarketResearchToolArgs(BaseModel):
    """Arguments for the market_research tool."""

    query: str = Field(
        description="The item name to research. Always one single item name, don't include any other item names."
    )
    """The item name to research."""


class GeneralMarketResearchTool(Tool):
    """GeneralMarket Research Tool."""

    name: str = "general_market_research"
    """The name of the tool."""

    description: str = "Research the market price of the item. The result will be a report of the market price, price strategy, value strategy, expected price, and price volatility."  # noqa: E501

    api_key: str
    """The API key for the SerpApi."""

    args_schema: Type[BaseModel] = GeneralMarketResearchToolArgs
    """The arguments schema for the tool."""

    async def execute(self, state: State, query: str) -> ToolResult:
        """Execute the tool."""
        logger.info(f"Researching the market price of the item: {query}")
        try:
            async with MarketResearch(api_key=self.api_key) as mr:
                result = await mr.get_market_intelligence(query)
                logger.info(f"Market research result: \n{result.get_llm_friendly_result() if result else 'No result'}")
                return ToolResult(
                    is_error=result is None,
                    tool_response=result.get_llm_friendly_result()
                    if result
                    else "Failed to research the market price. Please try again.",
                    updated_state=state,
                )
        except Exception as e:
            logger.error(f"Failed to research the market price: {e}")
            return ToolResult(
                is_error=True,
                tool_response="Failed to research the market price. Please try again.",
                updated_state=state,
            )


class MarketResearchToolArgs(BaseModel):
    """Arguments for the market_research tool."""

    item_ids: list[str] = Field(
        description="The list of item IDs to research. The item IDs must be results from the `mercari_search` tool."
    )
    """The list of item IDs to research."""


class MarketResearchTool(Tool):
    """Market Research Tool."""

    name: str = "market_research"
    """The name of the tool."""

    description: str = "Research the market price of the item that already exists in the search results. The result will be a report of the market price, price strategy, value strategy, expected price, and price volatility."  # noqa: E501

    api_key: str
    """The API key for the SerpApi."""

    concurrent_limit: int = 10
    """The concurrent limit for the market research."""

    args_schema: Type[BaseModel] = MarketResearchToolArgs
    """The arguments schema for the tool."""

    async def _get_market_intelligence(self, query: str) -> MarketIntelligenceResult | None:
        try:
            async with MarketResearch(api_key=self.api_key) as mr:
                return await mr.get_market_intelligence(query)
        except Exception as e:
            logger.error(f"Failed to research the market price: {e}")
            return None

    async def _get_market_intelligence_with_semaphore(
        self, query: str, semaphore: Semaphore
    ) -> MarketIntelligenceResult | None:
        async with semaphore:
            return await self._get_market_intelligence(query)

    async def execute(self, state: State, item_ids: list[str]) -> ToolResult:
        """Execute the tool.

        Args:
            state (State): The state of the tool.
            item_ids (list[str]): The list of item IDs to research.

        Returns:
            ToolResult: The result of the tool.
        """
        logger.info(f"Researching the market price of the items: {item_ids}")
        semaphore = Semaphore(self.concurrent_limit)
        items = [item for item in state.search_results if item.id in item_ids]
        tasks = [self._get_market_intelligence_with_semaphore(item.name, semaphore) for item in items]
        results = await asyncio.gather(*tasks)

        market_research_results = []
        for item, result in zip(items, results, strict=True):
            if result:
                item.market_research_result = result
                market_research_results.append(result.get_llm_friendly_result())
            else:
                market_research_results.append(f"Failed to research the market price of the item: {item.id}")

        debug_msg = "\n\n".join(market_research_results)
        logger.debug(f"Market research results: {debug_msg}")

        return ToolResult(
            is_error=False,
            tool_response="\n\n".join(market_research_results),
            updated_state=state,
        )
