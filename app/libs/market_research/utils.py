"""Market Intelligence Tool for AI Shopping Agent.

This module provides market research insights to help agents understand market conditions
and pricing before making recommendations.
"""

import statistics
from typing import List

import numpy as np

from app.types import BasicProductData, MarketIntelligenceResult, PriceGuidance, PriceRange, ShoppingRecommendation
from app.utils import usd_to_jpy


def research_market_intelligence(
    market_data: List[BasicProductData], product_category: str = "Product"
) -> MarketIntelligenceResult:
    """Research market to understand typical pricing expectations.

    Args:
        market_data (list[BasicProductData]): List of similar items found in market research
        product_category (str): Category/name of the product being researched

    Returns:
        MarketIntelligenceResult: for informed shopping decisions
    """
    if not market_data:
        raise ValueError("No market data provided for research")

    # Price Intelligence
    prices = [item.price for item in market_data]
    typical_price_range = _analyze_price_ranges(prices)
    price_guidance = _generate_price_guidance(typical_price_range)

    # Market Conditions
    price_volatility = _assess_price_volatility(prices)

    # Shopping Guidance
    shopping_recommendations = _generate_shopping_recommendations(typical_price_range, price_volatility)

    # Market Summary
    market_summary = _generate_market_summary(product_category, len(market_data), typical_price_range, price_volatility)

    return MarketIntelligenceResult(
        typical_price_range=typical_price_range,
        price_guidance=price_guidance,
        price_volatility=price_volatility,
        shopping_recommendations=shopping_recommendations,
        market_summary=market_summary,
    )


def _analyze_price_ranges(prices: List[float]) -> PriceRange:
    """Analyze price ranges and establish benchmarks.

    Args:
        prices (list[float]): The prices to analyze.

    Returns:
        PriceRange: The price range.
    """
    return PriceRange(
        min=min(prices),
        max=max(prices),
        average=statistics.mean(prices),
        median=statistics.median(prices),
        # use quartiles to segment the price range
        budget_range_max=float(np.percentile(prices, 25)),  # Budget-friendly upper limit
        mid_range_min=float(np.percentile(prices, 25)),  # Mid-range lower limit
        mid_range_max=float(np.percentile(prices, 75)),  # Mid-range upper limit
        premium_range_min=float(np.percentile(prices, 75)),  # Premium lower limit
        excellent_deal_max=float(np.percentile(prices, 10)),  # Excellent deals threshold
        good_deal_max=float(np.percentile(prices, 40)),  # Good deals threshold
        overpriced_min=float(np.percentile(prices, 90)),  # Overpriced threshold
    )


def _generate_price_guidance(price_ranges: PriceRange) -> PriceGuidance:
    """Generate price guidance for different scenarios.

    Args:
        price_ranges (PriceRange): The price ranges to generate guidance for.

    Returns:
        PriceGuidance: The price guidance.
    """
    return PriceGuidance(
        budget_shopping=f"For budget options, look for items under USD{price_ranges.budget_range_max:,.0f} (¥{usd_to_jpy(price_ranges.budget_range_max):,.0f})",  # noqa: E501
        typical_pricing=f"Typical prices range from USD{price_ranges.mid_range_min:,.0f} (¥{usd_to_jpy(price_ranges.mid_range_min):,.0f}) to USD{price_ranges.mid_range_max:,.0f} (¥{usd_to_jpy(price_ranges.mid_range_max):,.0f})",  # noqa: E501
        premium_pricing=f"Premium options start around USD{price_ranges.premium_range_min:,.0f} (¥{usd_to_jpy(price_ranges.premium_range_min):,.0f})",  # noqa: E501
        excellent_deals=f"Excellent deals are items under USD{price_ranges.excellent_deal_max:,.0f} (¥{usd_to_jpy(price_ranges.excellent_deal_max):,.0f})",  # noqa: E501
        good_deals=f"Good deals are items under USD{price_ranges.good_deal_max:,.0f} (¥{usd_to_jpy(price_ranges.good_deal_max):,.0f})",  # noqa: E501
        avoid_overpriced=f"Avoid items over USD{price_ranges.overpriced_min:,.0f} (¥{usd_to_jpy(price_ranges.overpriced_min):,.0f}) (likely overpriced)",  # noqa: E501
        expected_price=f"Expect to pay around USD{price_ranges.median:,.0f} (¥{usd_to_jpy(price_ranges.median):,.0f}) for typical quality",  # noqa: E501
    )


def _assess_price_volatility(prices: List[float]) -> str:
    """Assess price volatility using a method robust to outliers.

    Args:
        prices (list[float]): The prices to analyze.

    Returns:
        str: The price volatility.
    """
    if not prices or len(prices) < 4:  # Need at least 4 data points for quartiles # noqa: PLR2004
        return "unknown"

    # use Interquartile Range to assess price volatility
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)

    # Avoid division by zero if all prices are the same
    if (q3 + q1) == 0:
        return "stable"

    # Calculate the Quartile Coefficient of Dispersion
    qcd = (q3 - q1) / (q3 + q1)

    # Use similar thresholds, but they may need adjustment for QCD
    if qcd <= 0.10:  # QCD values are typically lower than CV # noqa: PLR2004
        return "stable"
    elif qcd <= 0.20:  # noqa: PLR2004
        return "moderate"
    else:
        return "volatile"


def _generate_shopping_recommendations(price_ranges: PriceRange, price_volatility: str) -> ShoppingRecommendation:
    """Generate specific shopping recommendations based on price analysis.

    Args:
        price_ranges (PriceRange): The price ranges to generate recommendations for.
        price_volatility (str): The price volatility.

    Returns:
        ShoppingRecommendation: The shopping recommendations.
    """
    recommendations = ShoppingRecommendation(
        price_strategy="",
        timing_strategy="",
        value_strategy="",
    )

    # Price strategy
    if price_volatility == "stable":
        recommendations.price_strategy = "Prices are stable. Safe to buy at typical market rates."
    elif price_volatility == "moderate":
        recommendations.price_strategy = "Moderate price variation. Look for deals below median."
    else:
        recommendations.price_strategy = "High price volatility. Wait for significant discounts."

    # Timing strategy based on price volatility
    if price_volatility == "stable":
        recommendations.timing_strategy = "Good time to buy. Stable pricing indicates mature market."
    elif price_volatility == "moderate":
        recommendations.timing_strategy = "Decent time to buy. Some price variation allows for deals."
    else:
        recommendations.timing_strategy = "Consider waiting for price drops. High volatility suggests unstable market."

    # Value strategy
    recommendations.value_strategy = (
        f"Best value: items under USD{price_ranges.good_deal_max:,.0f} (¥{usd_to_jpy(price_ranges.good_deal_max):,.0f}). "  # noqa: E501
        f"Avoid: items over USD{price_ranges.overpriced_min:,.0f} (¥{usd_to_jpy(price_ranges.overpriced_min):,.0f}). "  # noqa: E501
        f"Typical range: USD{price_ranges.mid_range_min:,.0f} (¥{usd_to_jpy(price_ranges.mid_range_min):,.0f}) - "  # noqa: E501
        f"USD{price_ranges.mid_range_max:,.0f} (¥{usd_to_jpy(price_ranges.mid_range_max):,.0f})."
    )

    return recommendations


def _generate_market_summary(
    product_category: str, sample_size: int, price_ranges: PriceRange, price_volatility: str
) -> str:
    """Generate comprehensive market summary based on price analysis.

    Args:
        product_category (str): The product category.
        sample_size (int): The sample size.
        price_ranges (PriceRange): The price ranges.
        price_volatility (str): The price volatility.

    Returns:
        str: The market summary.
    """
    return (
        f"Market intelligence for {product_category}: \n"
        f"Analyzed {sample_size} items. \n"
        f"Typical price: USD{price_ranges.median:,.0f} (¥{usd_to_jpy(price_ranges.median):,.0f}) "
        f"(range: USD{price_ranges.min:,.0f} (¥{usd_to_jpy(price_ranges.min):,.0f})-"
        f"USD{price_ranges.max:,.0f} (¥{usd_to_jpy(price_ranges.max):,.0f})). \n"
        f"Price volatility: {price_volatility}. "
        f"Recommendation: Look for items under USD{price_ranges.good_deal_max:,.0f} "
        f"(¥{usd_to_jpy(price_ranges.good_deal_max):,.0f}) for best value. Avoid items over "
        f"USD{price_ranges.overpriced_min:,.0f} (¥{usd_to_jpy(price_ranges.overpriced_min):,.0f})."
    )


# Helper function
def create_market_data_from_raw(prices: List[float]) -> List[BasicProductData]:
    """Convert raw market research data into BasicProductData objects.

    Args:
        prices (list[float]): The prices to convert.

    Returns:
        list[BasicProductData]: The converted prices.
    """
    return [BasicProductData(price=p) for p in prices]
