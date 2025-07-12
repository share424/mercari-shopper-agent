"""Ebay Research."""

from typing import Any

from aiocache import Cache
from httpx import AsyncClient
from loguru import logger

from app.libs.market_research.utils import research_market_intelligence
from app.types import BasicProductData, MarketIntelligenceResult

STATUS_CODE_OK = 200


class MarketResearch:
    """Market Research."""

    def __init__(self, api_key: str):
        """Initialize the MarketResearch.

        Args:
            api_key (str): The API key for the SerpApi.
        """
        self.api_key = api_key
        self._cache: Cache | None = None

    async def __aenter__(self):
        """Enter the context manager."""
        self._cache = Cache(Cache.REDIS, namespace="market_intelligence")  # type: ignore
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        if self._cache:
            await self._cache.close()  # type: ignore
            self._cache = None

    async def search(self, query: str) -> list[BasicProductData]:
        """Search the web for the given query.

        Args:
            query (str): The query to search for.

        Returns:
            list[dict]: The search results.
        """
        async with AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "ebay",
                    "_nkw": query,
                    "ebay_domain": "ebay.com",
                    "api_key": self.api_key,
                },
            )
            if response.status_code != STATUS_CODE_OK:
                logger.error(f"Failed to search: {response.text}")
                raise Exception(f"Failed to search: {response.status_code}")

            response_json = response.json()
            shopping_results: list[dict[str, Any]] = response_json["organic_results"]

            return [
                BasicProductData(
                    price=self._parse_price(item),
                )
                for item in shopping_results
            ]

    def _parse_price(self, data: dict[str, Any]) -> float:
        """Parse the price from the data."""
        price = data.get("price", {})

        if "extracted" in price:
            return float(price["extracted"])

        if "from" in price and "extracted" in price["from"]:
            return float(price["from"]["extracted"])

        return 0

    async def get_market_intelligence(self, query: str) -> MarketIntelligenceResult | None:
        """Get the market price for the given query.

        Args:
            query (str): The query to search for.

        Returns:
            dict[str, float]: The market statistics.
        """
        logger.debug(f"Getting market intelligence for: {query}")
        result = await self._cache.get(query)  # type: ignore
        if result:
            logger.debug(f"Market research result found in cache: {query}")
            return MarketIntelligenceResult.model_validate(result)

        results = await self.search(query)

        if not results:
            return None

        intelligence = research_market_intelligence(results, query)

        return intelligence
