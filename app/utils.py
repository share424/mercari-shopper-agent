"""Utils for the Mercari Shopping Agent.

This module contains the utils for the Mercari Shopping Agent.
"""

import json

from aioretry.retry import RetryInfo, RetryPolicyStrategy
from loguru import logger

from app.exception import SearchNotFoundError
from app.types import Item

RETRY_MAX_ATTEMPTS = 3
RETRY_DELAY = 0.5


def remove_duplicate_items(items: list[Item]) -> list[Item]:
    """Remove duplicate items from the list.

    Args:
        items (list[Item]): The list of items to remove duplicates from.

    Returns:
        list[Item]: The list of items with duplicates removed.
    """
    items_ids = set()
    new_items: list[Item] = []
    for item in items:
        if item.id not in items_ids:
            items_ids.add(item.id)
            new_items.append(item)
    return new_items


def retry_policy(info: RetryInfo) -> RetryPolicyStrategy:
    """Retry policy for the search_items function.

    If the exception is a SearchNotFoundError, retry max 3 times.
    Otherwise, retry once.

    Args:
        info (RetryInfo): The retry info object.

    Returns:
        RetryPolicyStrategy: The retry policy strategy.
    """
    logger.info(f"Retry attempt {info.fails + 1}")
    return info.fails < RETRY_MAX_ATTEMPTS or isinstance(info.exception, SearchNotFoundError), info.fails * RETRY_DELAY


def get_llm_friendly_items(items: list[Item]) -> str:
    """Convert the items to a format that is friendly to the LLM.

    Args:
        items (list[Item]): The list of items to convert.

    Returns:
        str: The items in a format that is friendly to the LLM.
    """
    data = []
    for item in items:
        item_detail = item.item_detail
        if item_detail:
            condition = item_detail.condition_type
        else:
            condition = item.condition_grade
        data.append(
            {
                "id": item.id,
                "name": item.name,
                "price": f"{item.currency} {item.price}",
                "description": item_detail.description if item_detail else "",
                "condition": condition,
                "brand": item.brand,
                "seller_stars": item_detail.seller_review_stars if item_detail else "unknown",
                "seller_total_person_reviews": item_detail.seller_review if item_detail else "unknown",
                "delivery_from": item_detail.delivery_from if item_detail else "unknown",
                "shipping_fee": item_detail.shipping_fee if item_detail else "unknown",
                "categories": item_detail.categories if item_detail else [],
                "posted_date": item_detail.posted_date if item_detail else "",
            }
        )
    return json.dumps(data, indent=2)
