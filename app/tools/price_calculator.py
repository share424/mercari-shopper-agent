"""Select Best Item Tool.

This tool is used to select the best item from the search results.
"""

from typing import Type

from pydantic import BaseModel, Field

from app.types import State, Tool, ToolResult
from app.utils import jpy_to_usd, usd_to_jpy


class PriceCalculatorToolArgs(BaseModel):
    """Arguments for the price_calculator tool."""

    source_currency: str = Field(description="The currency of the source price. Only USD and JPY are supported.")
    """The currency of the source price. Only USD and JPY are supported."""

    target_currency: str = Field(description="The currency of the target price. Only USD and JPY are supported.")
    """The currency of the target price."""

    source_price: float = Field(description="The price of the source currency.")
    """The price of the source currency."""


class PriceCalculatorTool(Tool):
    """Price Calculator Tool."""

    name: str = "price_calculator"
    """The name of the tool."""

    description: str = "Convert the price from the source currency to the target currency."
    """The description of the tool."""

    args_schema: Type[BaseModel] = PriceCalculatorToolArgs

    def _convert_price(self, source_currency: str, target_currency: str, source_price: float) -> float:
        """Convert the price from the source currency to the target currency."""
        if source_currency == "JPY" and target_currency == "USD":
            return jpy_to_usd(source_price)
        elif source_currency == "USD" and target_currency == "JPY":
            return usd_to_jpy(source_price)
        else:
            raise ValueError(f"Unsupported currency conversion: {source_currency} to {target_currency}")

    async def execute(
        self, state: State, source_currency: str, target_currency: str, source_price: float
    ) -> ToolResult:
        """Execute the tool.

        Args:
            state (State): The current state.
            source_currency (str): The currency of the source price.
            target_currency (str): The currency of the target price.
            source_price (float): The price of the source currency.

        Returns:
            ToolResult: The result of the tool execution.
        """
        try:
            result = self._convert_price(source_currency, target_currency, source_price)
            return ToolResult(
                is_error=False,
                tool_response=f"The price of {source_price} {source_currency} is {result} {target_currency}",
                updated_state=state,
                simplified_tool_response=f"The price of {source_price} {source_currency} is {result} {target_currency}",
            )
        except Exception:
            return ToolResult(
                is_error=True,
                tool_response=f"Error converting price from {source_currency} to {target_currency}",
                updated_state=state,
                simplified_tool_response=f"Error converting price from {source_currency} to {target_currency}",
            )
