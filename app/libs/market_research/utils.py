"""Market Intelligence Tool for AI Shopping Agent.

This module provides market research insights to help agents understand market conditions
and pricing before making recommendations.
"""

import statistics
from typing import List

import numpy as np

from app.types import BasicProductData, MarketIntelligenceResult, PriceGuidance, PriceRange, ShoppingRecommendation


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
        budget_shopping=f"For budget options, look for items under ${price_ranges.budget_range_max:,.0f}",
        typical_pricing=f"Typical prices range from ${price_ranges.mid_range_min:,.0f} to ${price_ranges.mid_range_max:,.0f}",  # noqa: E501
        premium_pricing=f"Premium options start around ${price_ranges.premium_range_min:,.0f}",
        excellent_deals=f"Excellent deals are items under ${price_ranges.excellent_deal_max:,.0f}",
        good_deals=f"Good deals are items under ${price_ranges.good_deal_max:,.0f}",
        avoid_overpriced=f"Avoid items over ${price_ranges.overpriced_min:,.0f} (likely overpriced)",
        expected_price=f"Expect to pay around ${price_ranges.median:,.0f} for typical quality",
    )


def _assess_price_volatility(prices: List[float]) -> str:
    """Assess price volatility in the market."""
    if not prices or len(prices) < 2:  # noqa: PLR2004
        return "unknown"

    # Calculate coefficient of variation
    cv = statistics.stdev(prices) / statistics.mean(prices)

    if cv <= 0.15:  # noqa: PLR2004
        return "stable"
    elif cv <= 0.30:  # noqa: PLR2004
        return "moderate"
    else:
        return "volatile"


def _generate_shopping_recommendations(price_ranges: PriceRange, price_volatility: str) -> ShoppingRecommendation:
    """Generate specific shopping recommendations based on price analysis."""
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
        f"Best value: items under ${price_ranges.good_deal_max:,.0f}. "
        f"Avoid: items over ${price_ranges.overpriced_min:,.0f}. "
        f"Typical range: ${price_ranges.mid_range_min:,.0f} - ${price_ranges.mid_range_max:,.0f}."
    )

    return recommendations


def _generate_market_summary(
    product_category: str, sample_size: int, price_ranges: PriceRange, price_volatility: str
) -> str:
    """Generate comprehensive market summary based on price analysis."""
    return (
        f"Market intelligence for {product_category}: "
        f"Analyzed {sample_size} items. "
        f"Typical price: ${price_ranges.median:,.0f} "
        f"(range: ${price_ranges.min:,.0f}-${price_ranges.max:,.0f}). "
        f"Price volatility: {price_volatility}. "
        f"Recommendation: Look for items under ${price_ranges.good_deal_max:,.0f} "
        f"for best value. Avoid items over ${price_ranges.overpriced_min:,.0f}."
    )


# Helper function
def create_market_data_from_raw(prices: List[float]) -> List[BasicProductData]:
    """Convert raw market research data into BasicProductData objects."""
    return [BasicProductData(price=p) for p in prices]


# Example usage
if __name__ == "__main__":
    # Market research data (from your search API) - only prices needed
    market_prices = [45000.0, 42000.0, 48000.0, 39000.0, 52000.0, 41000.0, 46000.0, 44000.0, 50000.0, 43000.0]

    # Convert to objects
    market_data = create_market_data_from_raw(market_prices)

    # Research the market
    intelligence = research_market_intelligence(market_data, "Nintendo Switch OLED")
    import json

    print(json.dumps(intelligence.model_dump(), indent=2))

    print("Market Intelligence Report:")
    print(f"Summary: {intelligence.market_summary}")
    print(f"Price Strategy: {intelligence.shopping_recommendations.price_strategy}")
    print(f"Value Strategy: {intelligence.shopping_recommendations.value_strategy}")
    print(f"Expected Price: {intelligence.price_guidance.expected_price}")
    print(f"Price Volatility: {intelligence.price_volatility}")
