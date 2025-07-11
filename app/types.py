"""Types for the Mercari Shopping Agent.

This module contains the types for the Mercari Shopping Agent.
"""

import json
from typing import Any, Type

from anthropic.types import ToolParam
from pydantic import BaseModel, ConfigDict, Field


class ItemRelevanceScore(BaseModel):
    """A structured representation of a relevance score for an item."""

    score: float = Field(default=0.0, description="The relevance score of the item.")
    """The relevance score of the item."""

    reasoning: str = Field(default="", description="The reasoning for the relevance score.")
    """The reasoning for the relevance score."""


class ToolResult(BaseModel):
    """Base class for a tool result.

    This class is designed to be subclassed for each specific tool result.
    """

    is_error: bool
    """Whether the tool call was successful."""

    tool_response: str
    """The response from the tool."""

    updated_state: "State"
    """The updated state of the tool call."""


class Tool(BaseModel):
    """Base class for a tool that can be called by a language model.

    This class is designed to be subclassed for each specific tool. The subclass
    should define an inner class `Args` that inherits from `pydantic.BaseModel`
    to specify the tool's arguments.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The Pydantic model for the tool's arguments.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    """The model config for the tool."""

    name: str
    """The name of the tool."""

    description: str
    """A description of what the tool does."""

    args_schema: Type[BaseModel]
    """The Pydantic model for the tool's arguments."""

    @property
    def tool_param(self) -> ToolParam:
        """The tool parameter for the tool.

        Returns:
            ToolParam: The tool parameter for the tool.
        """
        return ToolParam(
            name=self.name,
            description=self.description,
            input_schema=self.args_schema.model_json_schema(),
        )

    async def execute(self, state: "State", **kwargs: Any) -> ToolResult:
        """Executes the tool with the given arguments.

        This method should be implemented by subclasses.

        Args:
            state (State): The state of the tool call.
            **kwargs: The arguments for the tool call.

        Returns:
            ToolResult: The result of the tool call.

        Raises:
            NotImplementedError: If the method is not implemented by the subclass.
        """
        raise NotImplementedError


class ItemDetail(BaseModel):
    """A structured representation of a product listing from Mercari."""

    price_drop: str
    """The price drop of the item."""

    description: str
    """The description of the item."""

    condition_type: str
    """The condition type of the item."""

    posted_date: str
    """The date the item was posted."""

    delivery_from: str
    """The country the item is being delivered from."""

    shipping_fee: str
    """The shipping fee of the item."""

    seller_name: str
    """The name of the seller."""

    seller_username: str
    """The username of the seller."""

    seller_review: int
    """The number of reviews the seller has."""

    seller_review_stars: float
    """The average rating of the seller."""

    categories: list[str]
    """The categories the item belongs to."""


class MarketResearchResult(BaseModel):
    """A structured representation of the market research result."""

    average_price: float
    """The average price of the item."""

    median_price: float
    """The median price of the item."""

    std_price: float
    """The standard deviation of the price."""

    is_error: bool
    """Whether the market research was successful."""


class PriceRange(BaseModel):
    """A structured representation of the price range."""

    min: float
    """The minimum price of the price range."""

    max: float
    """The maximum price of the price range."""

    average: float
    """The average price of the price range."""

    median: float
    """The median price of the price range."""

    budget_range_max: float
    """The maximum price of the budget range."""

    mid_range_min: float
    """The minimum price of the mid range."""

    mid_range_max: float
    """The maximum price of the mid range."""

    premium_range_min: float
    """The minimum price of the premium range."""

    excellent_deal_max: float
    """The maximum price of the excellent deal."""

    good_deal_max: float
    """The maximum price of the good deal."""

    overpriced_min: float
    """The minimum price of the overpriced range."""


class PriceGuidance(BaseModel):
    """A structured representation of the price guidance."""

    budget_shopping: str
    """The budget shopping guidance."""

    typical_pricing: str
    """The typical pricing guidance."""

    premium_pricing: str
    """The premium pricing guidance."""

    excellent_deals: str
    """The excellent deals guidance."""

    good_deals: str
    """The good deals guidance."""

    avoid_overpriced: str
    """The avoid overpriced guidance."""

    expected_price: str
    """The expected price guidance."""


class ShoppingRecommendation(BaseModel):
    """A structured representation of the shopping recommendation."""

    price_strategy: str
    """The price strategy."""

    timing_strategy: str
    """The timing strategy."""

    value_strategy: str
    """The value strategy."""


class MarketIntelligenceResult(BaseModel):
    """A structured representation of the market intelligence."""

    typical_price_range: PriceRange
    """The typical price range."""

    price_guidance: PriceGuidance
    """The price guidance."""

    price_volatility: str
    """The price volatility."""

    shopping_recommendations: ShoppingRecommendation
    """The shopping recommendations."""

    market_summary: str
    """The market summary."""

    def get_llm_friendly_result(self) -> str:
        """Get the LLM friendly result."""
        report = "Market Intelligence Report:"
        report += f"\nSummary: {self.market_summary}"
        report += f"\nPrice Strategy: {self.shopping_recommendations.price_strategy}"
        report += f"\nValue Strategy: {self.shopping_recommendations.value_strategy}"
        report += f"\nExpected Price: {self.price_guidance.expected_price}"
        report += f"\nPrice Volatility: {self.price_volatility}"
        return report


class BasicProductData(BaseModel):
    """A structured representation of the basic product data."""

    price: float
    """The price of the product."""


class Item(BaseModel):
    """A structured representation of a product listing from Mercari."""

    id: str
    """The ID of the item."""

    name: str
    """The name of the item."""

    price: float
    """The price of the item."""

    currency: str
    """The currency of the item."""

    brand: str | None = None
    """The brand of the item."""

    condition_grade: str
    """The condition grade of the item."""

    availability: str
    """The availability of the item."""

    image_url: str
    """The URL of the item's image."""

    item_url: str
    """The URL of the item."""

    item_detail: ItemDetail | None = None
    """The detail of the item."""

    relevance_score: ItemRelevanceScore | None = None
    """The relevance score of the item."""

    market_research_result: MarketIntelligenceResult | None = None
    """The market research result of the item."""


class ItemRecommendation(BaseModel):
    """A recommendation for an item."""

    item: Item
    """The item to recommend."""

    reason: str
    """The reason for the recommendation."""


class State(BaseModel):
    """Base class for a state.

    This class is designed to be subclassed for each specific state.
    """

    user_query: str
    """The user query."""

    search_results: list[Item] = Field(default_factory=list)
    """The search results."""

    recommended_items: list[ItemRecommendation] = Field(default_factory=list)
    """The recommended items."""

    def remove_duplicate_search_results(self):
        """Remove duplicate search results."""
        # avoid circular import
        from app.utils import remove_duplicate_items  # noqa: PLC0415

        unique_items = remove_duplicate_items(self.search_results)
        self.search_results = unique_items

    def get_llm_friendly_state(self) -> str:
        """Get the LLM friendly state.

        Returns:
            str: The LLM friendly state.
        """
        # avoid circular import
        from app.utils import get_llm_friendly_items  # noqa: PLC0415

        return json.dumps(
            {
                "user_query": self.user_query,
                "search_results": get_llm_friendly_items(self.search_results),
            },
            indent=2,
        )
