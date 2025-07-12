"""Mercari Japan Item Detail Page.

This module contains the Mercari Japan Item Detail Page class.
"""

import asyncio
from typing import Any

from loguru import logger
from playwright.async_api import Page

from app.types import ItemDetail


class MercariJPItemDetailPage:
    """Mercari Japan Item Detail Page.

    Used to get the item detail from the item.
    """

    def __init__(self, page: Page, timeout: int = 10 * 1000, page_ready_timeout: int = 30 * 1000):
        """Initialize the Mercari Japan Item Detail Page.

        Args:
            page (Page): The page to use.
            timeout (int): The timeout to use.
            page_ready_timeout (int): The page ready timeout to use.
        """
        self.page = page
        self.timeout = timeout
        self.page_ready_timeout = page_ready_timeout

    async def __aenter__(self):
        """Enter the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        await self.page.close()

    async def get_item_detail(self, item_url: str) -> ItemDetail:
        """Get the item detail.

        If some of the fields are not found, an empty value is used.

        Args:
            item_url (str): The URL of the item to get the detail for.

        Returns:
            ItemDetail: The item detail.
        """
        logger.debug(f"Getting item detail: {item_url}")
        await self.page.goto(item_url)
        await self._wait_for_page_ready()
        await self.page.evaluate("window.scrollBy(0, window.innerHeight)")

        tasks = {
            "converted_price": self._extract_content_by_test_id("converted-currency-section"),
            "description": self._extract_content_by_test_id("description"),
            "condition_type": self._extract_content_by_test_id("商品の状態"),
            "delivery_from": self._extract_content_by_test_id("発送元の地域"),
            "seller_name": self._extract_seller_name(),
            "seller_review": self._extract_review_count(),
            "seller_review_stars": self._extract_review_stars(),
            "categories": self._extract_categories(),
            "seller_verification_status": self._extract_seller_type(),
            "num_likes": self._extract_content_by_test_id("icon-heart-button", int, "0"),
        }

        results = await asyncio.gather(*tasks.values())
        return ItemDetail.model_validate(dict(zip(tasks.keys(), results, strict=True)))

    async def _wait_for_page_ready(self):
        """Wait for the page to be ready."""
        await self.page.get_by_test_id("description").wait_for(state="visible", timeout=self.page_ready_timeout)

    async def _extract_seller_name(self) -> str:
        """Extract the seller name.

        If the seller name is not found, an empty string is returned.

        Returns:
            str: The seller name.
        """
        try:
            name = (
                await self.page.get_by_test_id("seller-link").first.get_attribute("aria-label", timeout=self.timeout)
            ) or ""
            return name.removesuffix("'s profile").strip()
        except Exception as e:
            logger.debug(f"Could not extract seller name: {e}")
            return ""

    async def _extract_review_stars(self) -> float:
        """Extract the review stars.

        If the review stars are not found, 0.0 is returned.

        Returns:
            float: The review stars.
        """
        try:
            stars = str(
                await self.page.locator("div[class='merRating']").first.get_attribute(
                    "aria-label", timeout=self.timeout
                )
            )
            return float(stars or "0")
        except Exception as e:
            logger.debug(f"Could not extract review stars: {e}")
            return 0.0

    async def _extract_review_count(self) -> int:
        """Extract the review count.

        If the review count is not found, 0 is returned.

        Returns:
            int: The review count.
        """
        try:
            reviews = str(
                await self.page.locator('div[class="merRating"]')
                .first.locator('span[class^="count__"]')
                .first.text_content(timeout=self.timeout)
            )
            return int(reviews or "0")
        except Exception as e:
            logger.debug(f"Could not extract review count: {e}")
            return 0

    async def _extract_seller_type(self) -> str:
        """Extract the seller type.

        unverified = 本人確認前
        verified = 本人確認済
        official = メルカリShops

        Returns:
            str: The seller type.
        """
        try:
            return (
                await self.page.get_by_test_id("seller-link")
                .first.locator('div[class^="verificationContainer__"]')
                .text_content(timeout=self.timeout)
            ) or ""
        except Exception as e:
            logger.debug(f"Could not extract seller type: {e}")
            return ""

    async def _extract_categories(self) -> list[str]:
        """Extract the categories.

        If the categories are not found, an empty list is returned.

        Returns:
            list[str]: The categories.
        """
        try:
            results = await self.page.get_by_test_id("item-detail-category").get_by_role("listitem").all()
            categories = await asyncio.gather(*[result.text_content() for result in results])
            return [category for category in categories if category]
        except Exception as e:
            logger.debug(f"Could not extract categories: {e}")
            return []

    async def _extract_content_by_test_id(self, test_id: str, cast_to: type = str, default: Any = "") -> str:
        """Extract the content by test id.

        If the content is not found, the default value is returned.

        Args:
            test_id (str): The test id to use.
            cast_to (type): The type to cast the content to.
            default (Any): The default value to use if the content is not found.
        """
        try:
            text_content = await self.page.get_by_test_id(test_id).first.text_content(timeout=self.timeout)
            return cast_to(text_content)
        except Exception as e:
            logger.debug(f"Could not extract content by test id: {test_id}. Error: {e}")
            return default
