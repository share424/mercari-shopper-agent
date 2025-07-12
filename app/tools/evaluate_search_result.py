"""Evaluate Search Result Tool.

This tool is used to evaluate the relevance of the search results.
"""

import asyncio
from datetime import datetime
from typing import Type

import json_repair
from aioretry.retry import retry
from anthropic import AsyncAnthropic
from loguru import logger
from pydantic import BaseModel, Field

from app.prompts.evaluate_item_jp import SYSTEM_PROMPT, USER_PROMPT
from app.types import Item, ItemRelevanceScore, State, Tool, ToolResult
from app.utils import get_llm_friendly_item, get_llm_friendly_items, retry_policy


class EvaluateSearchResultToolArgs(BaseModel):
    """Arguments for the evaluate_search_result tool."""

    item_ids: list[str] = Field(default_factory=list, description="The IDs of the items to evaluate.")
    """The IDs of the items to evaluate."""


class EvaluateSearchResultTool(Tool):
    """Generate Alternative Keywords Tool."""

    name: str = "evaluate_search_result"
    """The name of the tool."""

    description: str = (
        "Evaluate the relevance of the search results. The score will be stored in the `relevance_score` "
        "field of the items. The score is a number between 0 and 1, where 0 is the lowest relevance and 1 is the "
        "highest relevance. The reasoning will be stored in the `relevance_score_reasoning` field of the items."
    )
    """The description of the tool."""

    client: AsyncAnthropic
    """The client for the Anthropic API."""

    model: str
    """The model to use for the tool."""

    args_schema: Type[BaseModel] = EvaluateSearchResultToolArgs
    """The arguments schema for the tool."""

    @retry(retry_policy)
    async def _evaluate_item(self, state: State, item: Item) -> ItemRelevanceScore:
        """Evaluate an item."""
        response = await self.client.messages.create(
            system=SYSTEM_PROMPT.format(current_date=datetime.now().strftime("%Y-%m-%d")),
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT.format(
                        item_info=get_llm_friendly_item(item),
                        user_query=state.user_query,
                        market_research=item.market_research_result.get_llm_friendly_result()
                        if item.market_research_result
                        else "",
                    ),
                }
            ],
        )
        try:
            text = None
            for content in response.content:
                if content.type == "text":
                    text = content.text
                    break

            if text is None:
                return ItemRelevanceScore(score=0.0, reasoning="")

            json_data = json_repair.loads(text)
            if isinstance(json_data, dict):
                score = json_data.get("score", 0.0) / 5.0
                reasoning = json_data.get("reasoning", "")
                return ItemRelevanceScore(score=score, reasoning=reasoning)

            return ItemRelevanceScore(score=0.0, reasoning="")
        except Exception as e:
            logger.error(f"Error evaluating item: {e}")
            return ItemRelevanceScore(score=0.0, reasoning="")

    async def execute(self, state: State, item_ids: list[str]) -> ToolResult:
        """Execute the tool."""
        logger.info("Evaluating items")
        logger.debug(f"Evaluating items: {item_ids}")
        tasks = [self._evaluate_item(state, item) for item in state.search_results if item.id in item_ids]
        results = await asyncio.gather(*tasks)

        logger.debug(f"Evaluated scores: {results}")

        updated_items = []
        for item_id, relevance_score in zip(item_ids, results, strict=True):
            for item in state.search_results:
                if item.id == item_id:
                    item.relevance_score = relevance_score
                    updated_items.append(item)
                    break

        state.recommended_candidates.extend(updated_items)
        state.remove_duplicate_recommended_candidates()

        return ToolResult(
            is_error=False,
            tool_response=get_llm_friendly_items(updated_items),
            updated_state=state,
            simplified_tool_response=self._get_simplified_tool_response(updated_items),
        )

    def _get_simplified_tool_response(self, items: list[Item]) -> str:
        """Get the simplified tool response."""
        text = ""
        for item in items:
            if item.relevance_score is None:
                continue
            text += f"## [{item.name}]({item.item_url})\n"
            text += f"**Price**: {item.currency} {item.price}\n"
            text += f"**Relevance Score**: {item.relevance_score.score}\n"
            text += f"**Relevance Reasoning**: \n\n```\n{item.relevance_score.reasoning}\n```\n"
        return text
