"""Mercari Japan Search Page.

This module contains the Mercari Japan Search Page class.
"""

import asyncio

from loguru import logger
from playwright.async_api import Locator, Page, TimeoutError

from app.exception import SearchNotFoundError
from app.types import Item


class MercariJPSearchPage:
    """Mercari Japan Search Page.

    Used to search for items on Mercari Japan.
    """

    base_url = "https://jp.mercari.com"

    def __init__(self, page: Page, timeout: int = 30 * 1000):
        """Initialize the Mercari Japan Search Page.

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
            min_price (int | None): The minimum price to search for in JPY.
            max_price (int | None): The maximum price to search for in JPY.

        Returns:
            str: The search URL.
        """
        url = f"{self.base_url}/search/?keyword={query}"
        if min_price:
            url += f"&price_min={min_price}"
        if max_price:
            url += f"&price_max={max_price}"
        return url

    async def __aenter__(self):
        """Enter the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        await self.page.close()

    async def search_items(
        self, query: str, min_price: int | None = None, max_price: int | None = None, max_items: int = 10
    ) -> list[Item]:
        """Search for items on Mercari.

        Args:
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in JPY. Defaults to None.
            max_price (int | None): The maximum price to search for in JPY. Defaults to None.
            max_items (int): The maximum number of items to search for. Defaults to 10.

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
        search_results_locator = self.page.get_by_test_id("search-item-grid")

        await no_results_locator.or_(search_results_locator).wait_for(state="visible", timeout=self.timeout)

    async def _is_no_results(self) -> bool:
        """Check if the page has no results.

        Returns:
            bool: True if the page has no results, False otherwise.
        """
        return await self.page.get_by_text("No results found").is_visible()

    async def _get_items(
        self,
        max_items: int = 10,
    ) -> list[Item]:
        """Get the items from the page.

        Returns:
            list[Item]: The list of items found.
        """
        search_results_locator = self.page.get_by_test_id("search-item-grid")
        items_locator = await search_results_locator.get_by_test_id("item-cell").all()

        items: list[Item] = []
        for item_locator in items_locator[:max_items]:
            item = await self._parse_item(item_locator)
            if item:
                items.append(item)

        return items

    async def _parse_item(self, item_locator: Locator) -> Item | None:
        """Parse the item data.

        Args:
            item_locator (Locator): The item locator.

        Returns:
            Item: The parsed item.
        """
        # find url, example: /item/m18276289519
        while True:
            try:
                url_locator = item_locator.get_by_test_id("thumbnail-link")
                url = await url_locator.get_attribute("href", timeout=3 * 1000)
                if not url:
                    return None
                break
            except TimeoutError:
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")

        if not url.startswith("/item/"):
            return None

        item_id = url.split("/")[-1]
        item_url = f"{self.base_url}/item/{item_id}"

        item_container_locator = item_locator.locator(f"#{item_id}")

        # debug_img = await item_container_locator.get_by_role("img").inner_html()
        # logger.info(f"Debug img: {debug_img}")

        task_map = {
            "name": item_container_locator.locator("img").first.get_attribute("alt"),
            "image_url": item_container_locator.locator("img").first.get_attribute("src"),
            "currency": item_container_locator.locator('span[class^="currency__"]').first.text_content(),
            "price": item_container_locator.locator('span[class^="number__"]').first.text_content(),
        }

        results = await asyncio.gather(*task_map.values())

        task_result = {}
        for key, result in zip(task_map.keys(), results, strict=True):
            task_result[key] = result

        logger.debug(f"Parsed item: {task_result}")

        return Item(
            id=item_id,
            name=task_result.get("name", ""),
            price=float(task_result.get("price", 0)),
            currency=task_result.get("currency", ""),
            image_url=task_result.get("image_url", ""),
            item_url=item_url,
        )
