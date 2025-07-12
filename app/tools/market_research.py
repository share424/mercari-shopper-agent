"""Market Research Tool."""

import asyncio
from asyncio import Semaphore
from typing import Type

import json_repair
from aioretry.retry import retry
from anthropic import AsyncAnthropic
from loguru import logger
from pydantic import BaseModel, Field

from app.libs.market_research.market_research import MarketResearch
from app.prompts.market_research_query import SYSTEM_PROMPT, USER_PROMPT
from app.types import Item, MarketIntelligenceResult, State, Tool, ToolResult
from app.utils import retry_policy


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

    concurrent_limit: int = 1
    """The concurrent limit for the market research."""

    client: AsyncAnthropic
    """The client for the Anthropic API."""

    model: str
    """The model to use for the tool."""

    args_schema: Type[BaseModel] = MarketResearchToolArgs
    """The arguments schema for the tool."""

    @retry(retry_policy)
    async def _get_query(self, item: Item) -> str:
        """Get the query for the market research.

        Args:
            item (Item): The item to get the query for.

        Returns:
            str: The query for the market research. Return the item name if the query is not found.
        """
        response = await self.client.messages.create(
            system=SYSTEM_PROMPT,
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT.format(
                        item_name=item.name,
                        item_description=item.item_detail.description if item.item_detail else "",
                        item_categories=item.item_detail.categories if item.item_detail else "",
                    ),
                }
            ],
        )

        try:
            text = None
            for content in response.content:
                if content.type == "text":
                    text = content.text
                    break

            if text is None:
                return item.name

            json_data = json_repair.loads(text)
            if isinstance(json_data, dict):
                query = json_data.get("query", item.name)
                return query

            return item.name
        except Exception as e:
            logger.error(f"Error evaluating item: {e}")
            return item.name

    async def _get_market_intelligence(self, item: Item) -> MarketIntelligenceResult | None:
        try:
            query = await self._get_query(item)
            async with MarketResearch(api_key=self.api_key) as mr:
                return await mr.get_market_intelligence(query)
        except Exception as e:
            logger.error(f"Failed to research the market price: {e}")
            return None

    async def _get_market_intelligence_with_semaphore(
        self, item: Item, semaphore: Semaphore
    ) -> MarketIntelligenceResult | None:
        async with semaphore:
            return await self._get_market_intelligence(item)

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
        tasks = [self._get_market_intelligence_with_semaphore(item, semaphore) for item in items]
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
            simplified_tool_response=self._get_simplified_tool_response(items),
        )

    def _get_simplified_tool_response(self, items: list[Item]) -> str:
        """Get the simplified tool response."""
        text = ""
        for item in items:
            if item.market_research_result is None:
                continue
            text += f"## [{item.name}]({item.item_url})\n"
            text += f"### Market Research Result: \n\n{item.market_research_result.get_llm_friendly_result()}\n\n"
        return text
