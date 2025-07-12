"""Mercari Search Japan.

This module contains the Mercari Search Japan class.
"""

import asyncio

from aiocache import Cache
from aioretry.retry import retry
from loguru import logger
from playwright.async_api import Browser, Page, async_playwright
from playwright_stealth import Stealth

from app.libs.mercari_jp.config import BROWSER_CONFIG
from app.libs.mercari_jp.pages.item_detail import MercariJPItemDetailPage
from app.libs.mercari_jp.pages.search import MercariJPSearchPage
from app.types import Item, ItemDetail
from app.utils import retry_policy


class MercariJPSearch:
    """Mercari Search Japan.

    This class is used to search for items on Mercari Japan.
    """

    def __init__(self, headless: bool = True, max_concurrent_pages: int = 5):
        """Initialize the Mercari Japan Search.

        Args:
            headless (bool): Whether to run the browser in headless mode.
            max_concurrent_pages (int): The maximum number of concurrent pages. Defaults to 5.
        """
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._semaphore = asyncio.Semaphore(max_concurrent_pages)
        self._manager = Stealth().use_async(async_playwright())

    async def __aenter__(self):
        """Enter the context manager."""
        logger.debug("Starting browser...")
        self._playwright = await self._manager.__aenter__()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._cache = Cache(Cache.REDIS, namespace="mercari_jp")  # type: ignore
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._manager.__aexit__(exc_type, exc_val, exc_tb)
            self._playwright = None

        if self._cache:
            await self._cache.close()  # type: ignore
            self._cache = None

    async def clear_cache(self):
        """Clear the cache."""
        if self._cache:
            await self._cache.clear()  # type: ignore

    async def _create_new_page(self) -> Page:
        """Create a new page.

        Returns:
            Page: The new page.

        Raises:
            ValueError: If the browser is not initialized.
        """
        if not self._browser:
            raise ValueError("Browser not initialized")

        return await self._browser.new_page(**BROWSER_CONFIG)

    @retry(retry_policy=retry_policy)
    async def _search_items(
        self, query: str, min_price: int | None = None, max_price: int | None = None, max_items: int = 10
    ) -> list[Item]:
        """Search for items on Mercari Japan.

        Sometimes, the search is failed due to bot detection.
        This function will retry the search up to 3 times.

        Args:
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in USD.
            max_price (int | None): The maximum price to search for in USD.
            max_items (int): The maximum number of items to search for. Defaults to 10.
        """
        page = await self._create_new_page()
        async with MercariJPSearchPage(page) as search_page:
            return await search_page.search_items(query, min_price, max_price, max_items)

    async def _get_item_detail(self, item: Item) -> ItemDetail | None:
        """Get the item detail on Mercari Japan.

        If the item detail is not found in the cache, it will be fetched from the page.

        Args:
            item (Item): The item to get the detail for.

        Returns:
            ItemDetail | None: The item detail. If the item detail is not found, None is returned.
        """
        item_detail = await self._cache.get(item.id)  # type: ignore
        if item_detail:
            logger.debug(f"Item detail found in cache: {item.id}")
            return ItemDetail.model_validate(item_detail)

        page = await self._create_new_page()
        async with MercariJPItemDetailPage(page) as item_detail_page:
            try:
                item_detail = await item_detail_page.get_item_detail(item.item_url)
                await self._cache.set(item.id, item_detail.model_dump())  # type: ignore
                return item_detail
            except Exception as e:
                logger.error(f"Failed to get item detail: {e}")
                return None

    async def _get_item_detail_with_semaphore(self, item: Item) -> ItemDetail | None:
        """Get the item detail with semaphore.

        Args:
            item (Item): The item to get the detail for.

        Returns:
            ItemDetail | None: The item detail. If the item detail is not found, None is returned.
        """
        async with self._semaphore:
            return await self._get_item_detail(item)

    async def search_items(
        self, query: str, min_price: int | None = None, max_price: int | None = None, max_items: int = 10
    ) -> list[Item]:
        """Search for items on Mercari Japan.

        Args:
            query (str): The query to search for.
            min_price (int | None): The minimum price to search for in JPY.
            max_price (int | None): The maximum price to search for in JPY.
            max_items (int): The maximum number of items to search for. Defaults to 10.

        Returns:
            list[Item]: The list of items with the item detail.
        """
        items = await self._search_items(query, min_price, max_price, max_items)

        item_detail_tasks = [self._get_item_detail_with_semaphore(item) for item in items]
        item_details = await asyncio.gather(*item_detail_tasks)
        for item, item_detail in zip(items, item_details, strict=False):
            if not item_detail:
                continue
            item.item_detail = item_detail
        return items
