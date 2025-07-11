"""Ebay Research."""

from typing import Any

import numpy as np
from aiocache import Cache
from httpx import AsyncClient
from loguru import logger

from app.types import MarketResearchResult

STATUS_CODE_OK = 200


class EbayResearch:
    """Ebay Research."""

    def __init__(self, api_key: str):
        """Initialize the EbayResearch.

        Args:
            api_key (str): The API key for the SerpApi.
        """
        self.api_key = api_key
        self._cache: Cache | None = None

    async def __aenter__(self):
        """Enter the context manager."""
        self._cache = Cache(Cache.REDIS, namespace="ebay")  # type: ignore
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        if self._cache:
            await self._cache.close()  # type: ignore
            self._cache = None

    async def search(self, query: str) -> list[dict]:
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
            return response_json["organic_results"]

    def _parse_price(self, data: dict[str, Any]) -> float:
        """Parse the price from the data."""
        price = data.get("price", {})

        if "extracted" in price:
            return float(price["extracted"])

        if "from" in price and "extracted" in price["from"]:
            return float(price["from"]["extracted"])

        return 0

    async def get_market_price(self, query: str) -> MarketResearchResult:
        """Get the market price for the given query.

        Args:
            query (str): The query to search for.

        Returns:
            dict[str, float]: The market statistics.
        """
        result = await self._cache.get(query)  # type: ignore
        if result:
            logger.debug(f"Market research result found in cache: {query}")
            return MarketResearchResult.model_validate(result)

        results = await self.search(query)
        prices = [self._parse_price(item) for item in results]

        if not prices:
            return MarketResearchResult(
                average_price=0,
                median_price=0,
                std_price=0,
                is_error=True,
            )

        average_price = np.mean(prices)
        median_price = np.median(prices)
        std_price = np.std(prices)

        research = MarketResearchResult(
            average_price=float(average_price),
            median_price=float(median_price),
            std_price=float(std_price),
            is_error=False,
        )

        await self._cache.set(query, research.model_dump())  # type: ignore
        return research
