"""Utils for the Mercari Shopping Agent.

This module contains the utils for the Mercari Shopping Agent.
"""

import json
import random

from aioretry.retry import RetryInfo, RetryPolicyStrategy
from anthropic import InternalServerError
from loguru import logger

from app.exception import SearchNotFoundError
from app.types import Item

INITIAL_RETRY_DELAY = 3
MAX_RETRIES = 5
MAX_BACKOFF = 60
JITTER_FACTOR = 0.1


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
    logger.info(f"Retry attempt {info.fails} of {MAX_RETRIES}")
    logger.error(f"Error: {info.exception}")
    should_stop = True
    if isinstance(info.exception, (SearchNotFoundError, InternalServerError)) or info.fails <= MAX_RETRIES:
        should_stop = False

    delay = min(INITIAL_RETRY_DELAY * (2 ** (info.fails - 1)), MAX_BACKOFF)
    jitter = random.uniform(-JITTER_FACTOR * delay, JITTER_FACTOR * delay)
    delay = max(0, int(delay + jitter))

    return should_stop, delay


def get_llm_friendly_items(items: list[Item], include_market_research: bool = False) -> str:
    """Convert the items to a format that is friendly to the LLM.

    Args:
        items (list[Item]): The list of items to convert.
        include_market_research (bool): Whether to include the market research.

    Returns:
        str: The items in a format that is friendly to the LLM.
    """
    data = []
    for item in items:
        data.append(get_llm_friendly_item(item, return_dict=True, include_market_research=include_market_research))
    return json.dumps(data, indent=2, ensure_ascii=False)


def get_llm_friendly_item(
    item: Item,
    return_dict: bool = False,
    include_market_research: bool = False,
) -> str | dict:
    """Get the LLM friendly item.

    Args:
        item (Item): The item to convert.
        return_dict (bool): Whether to return a dictionary or a JSON string.
        include_relevance_score (bool): Whether to include the relevance score.
        include_market_research (bool): Whether to include the market research.

    Returns:
        str | dict: The LLM friendly item.
    """
    item_detail = item.item_detail
    if item_detail and item_detail.condition_type:
        condition = item_detail.condition_type
    else:
        condition = item.condition_grade

    price = f"{item.currency} {item.price}"
    if item_detail and item_detail.converted_price:
        price = [price, item_detail.converted_price]

    data = {
        "id": item.id,
        "name": item.name,
        "price": price,
        "description": item_detail.description if item_detail else "",
        "condition": condition,
        "brand": item.brand,
        "num_likes": item_detail.num_likes if item_detail else None,
        "seller_stars": item_detail.seller_review_stars if item_detail else None,
        "seller_total_person_reviews": item_detail.seller_review if item_detail else None,
        "delivery_from": item_detail.delivery_from if item_detail else None,
        "categories": item_detail.categories if item_detail else [],
        "relevance_score": item.relevance_score.score if item.relevance_score else None,
        "relevance_score_reasoning": item.relevance_score.reasoning if item.relevance_score else None,
    }

    if item_detail and item_detail.seller_verification_status:
        data["seller_verification_status "] = item_detail.seller_verification_status

    if item_detail and item_detail.shipping_fee:
        data["shipping_fee"] = item_detail.shipping_fee

    if item_detail and item_detail.posted_date:
        data["posted_date"] = item_detail.posted_date

    if include_market_research and item.market_research_result:
        data["market_research"] = item.market_research_result.get_llm_friendly_result()

    if return_dict:
        return data
    return json.dumps(data, indent=2, ensure_ascii=False)


def jpy_to_usd(jpy_price: float) -> float:
    """Convert JPY to USD."""
    return jpy_price * 0.0068  # 2025/07/12


def usd_to_jpy(usd_price: float) -> float:
    """Convert USD to JPY."""
    return usd_price * 147.42  # 2025/07/12
