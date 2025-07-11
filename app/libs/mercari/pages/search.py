"""Mercari Search Page.

This module contains the Mercari Search Page class.
"""

from typing import Any

import json_repair
from loguru import logger
from playwright.async_api import Page

from app.exception import SearchNotFoundError
from app.types import Item


class MercariSearchPage:
    """Mercari Search Page.

    Used to search for items on Mercari.
    """

    def __init__(self, page: Page, timeout: int = 30 * 1000):
        """Initialize the Mercari Search Page.

        Args:
            page (Page): The page to use.
            timeout (int): The timeout to use. Defaults to 30 seconds.
        """
        self.page = page
        self.timeout = timeout

    def _build_search_url(self, query: str, min_price: int | None = None, max_price: int | None = None) -> str:
        """Build the search URL.

        Args:
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in USD.
            max_price (int | None): The maximum price to search for in USD.

        Returns:
            str: The search URL.
        """
        url = f"https://www.mercari.com/search/?keyword={query}"
        if min_price:
            url += f"&minPrice={min_price * 100}"
        if max_price:
            url += f"&maxPrice={max_price * 100}"
        return url

    async def __aenter__(self):
        """Enter the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        await self.page.close()

    async def search_items(self, query: str, min_price: int | None = None, max_price: int | None = None) -> list[Item]:
        """Search for items on Mercari.

        Args:
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in USD. Defaults to None.
            max_price (int | None): The maximum price to search for in USD. Defaults to None.

        Returns:
            list[Item]: The list of items found.
        """
        logger.info(f"Searching for items: {query}, min_price: {min_price}, max_price: {max_price}")
        await self.page.goto(self._build_search_url(query, min_price, max_price))
        await self._wait_for_page_ready()

        if await self._is_no_results():
            logger.error("No results found")
            raise SearchNotFoundError("No results found")

        items = await self._get_items()
        logger.info(f"Found {len(items)} items")
        return items

    async def _wait_for_page_ready(self):
        """Wait for the page to be ready."""
        no_results_locator = self.page.get_by_text("No results found")
        search_results_locator = self.page.get_by_test_id("Search-items")

        await no_results_locator.or_(search_results_locator).wait_for(state="visible", timeout=self.timeout)

    async def _is_no_results(self) -> bool:
        """Check if the page has no results.

        Returns:
            bool: True if the page has no results, False otherwise.
        """
        return await self.page.get_by_text("No results found").is_visible()

    async def _get_items(
        self,
    ) -> list[Item]:
        """Get the items from the page.

        Returns:
            list[Item]: The list of items found.
        """
        search_results_locator = self.page.get_by_test_id("Search-items")
        items_locator = await search_results_locator.locator('div[data-itemstatus="on_sale"]').all()

        items: list[Item] = []
        for item_locator in items_locator:
            script_locator = item_locator.locator('script[type="application/ld+json"]')
            json_text = await script_locator.text_content(timeout=self.timeout) or "{}"
            try:
                data = json_repair.loads(json_text)
                if not isinstance(data, dict):
                    continue

                item = self._parse_item(data)
                items.append(item)
            except Exception as e:
                logger.warning(f"Could not parse item data: {e}. Raw data: {json_text[:200]}...")

        return items

    def _parse_item(self, data: dict[str, Any]) -> Item:
        """Parse the item data.

        Args:
            data (dict[str, Any]): The item data.

        Returns:
            Item: The parsed item.
        """
        offers = data.get("offers", {})

        condition_url = offers.get("itemCondition", "")
        availability_url = offers.get("availability", "")

        flat_data = {
            "id": offers.get("url", "").split("/")[-2],
            "name": data.get("name"),
            "price": offers.get("price"),
            "currency": offers.get("priceCurrency"),
            "brand": data.get("brand", {}).get("name"),
            "image_url": data.get("image"),
            "condition_grade": condition_url.split("/")[-1],
            "availability": availability_url.split("/")[-1],
            "item_url": "https://www.mercari.com" + offers.get("url", ""),
        }
        return Item.model_validate(flat_data, strict=False)
