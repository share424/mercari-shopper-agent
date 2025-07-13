"""Web app for the Mercari shopping agent."""

import asyncio
import os

import gradio as gr
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from app.agent import MercariShoppingAgent
from app.types import ItemRecommendation

load_dotenv()

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
agent = MercariShoppingAgent(client=client, model=os.getenv("MODEL_NAME", "claude-3-5-sonnet-latest"))


def get_item_recommendations_text(
    item_recommendations: list[ItemRecommendation] | None,
) -> str:
    """Return shopper-friendly Markdown for a list of ItemRecommendation objects."""
    # ── Header ────────────────────────────────────────────────────────────────
    text = "## 🎯 Top Picks for You\n"
    if not item_recommendations:
        return text + "No item recommendations found.\n"

    # ── Card for each recommendation ─────────────────────────────────────────
    for i, rec in enumerate(item_recommendations, start=1):
        item = rec.item
        detail = item.item_detail

        # — Quick-view fields —
        condition = detail.condition_type if detail and detail.condition_type else item.condition_grade or "—"

        price = f"{item.currency} {item.price}"
        if detail and detail.converted_price:
            price += f" ({detail.converted_price})"

        # — Card header & hero —
        text += f"### {i}. [{rec.title}]({item.item_url})\n"
        text += f"*{rec.persona_fit}*\n\n"
        text += f"![{item.name}]({item.image_url})\n\n"

        # — Why it made the list —
        text += f"**Why it made the list**\n\n{rec.reasoning_summary}\n\n"

        # — Quick spec bullets —
        text += f"- **Price:** {price}\n- **Condition:** {condition}\n"
        if detail:
            text += (
                "- **Seller:** "
                f"{detail.seller_name} "
                f"({detail.seller_review_stars}★, "
                f"{detail.seller_review} reviews, "
                f"{detail.seller_verification_status})\n"
            )

        # — Collapsible Pros / Cons table —
        text += "\n\n<details>\n"
        text += "<summary><strong>Pros ✅ / Cons ⚠️</strong></summary>\n\n"
        # Build a two-column table; put each list in its own cell with <br>
        pros = "<br>".join(rec.pros) or "—"
        cons = "<br>".join(rec.cons) or "—"
        text += "| Pros | Cons |\n|---|---|\n"
        text += f"| {pros} | {cons} |\n\n"
        text += "</details>\n\n"

        # — Trust signals block —
        text += "**Trust & Seller Info**\n"
        text += f"- **Seller rating:** {rec.trust_signals.seller_rating}\n"
        text += f"- {rec.trust_signals.notes}\n\n"

        # — Deep-dive accordion (kept from your original) —
        text += "<details>\n<summary>More Details</summary>\n\n"
        if detail:
            text += "#### Item Details\n"
            text += f"**Description**\n\n```\n{detail.description}\n```\n"
            if detail.categories:
                text += f"**Categories:** {', '.join(detail.categories)}\n\n"

        if item.market_research_result:
            text += "#### Market Research Result\n```\n"
            text += item.market_research_result.get_llm_friendly_result()
            text += "\n```\n\n"

        if item.relevance_score:
            text += (
                "#### Relevance\n"
                f"**Score:** {item.relevance_score.score}\n\n"
                f"**Reasoning**\n\n```\n"
                f"{item.relevance_score.reasoning}\n```\n"
            )

        text += "</details>\n\n---\n\n"

    return text


async def interact_with_agent(prompt, messages):
    """Interact with the agent."""
    yield messages, "Thinking..."

    async for chunk in agent.run_stream(prompt):
        if chunk.action == "reasoning":
            messages.append(gr.ChatMessage(role="assistant", content=chunk.text, metadata={"title": "Thinking"}))
            yield messages, "Thinking..."
        elif chunk.action == "tool_call":
            messages.append(gr.ChatMessage(role="assistant", content=chunk.text, metadata={"title": "Tool Call"}))
            yield messages, "Executing tool call..."
        elif chunk.action == "tool_result":
            messages.append(gr.ChatMessage(role="assistant", content=chunk.text, metadata={"title": "Tool Result"}))
            yield messages, "Understanding tool result..."
        elif chunk.action == "stop":
            messages.append(
                gr.ChatMessage(
                    role="assistant",
                    content="Showing recommendations",
                    metadata={"title": "Completed"},
                )
            )
            yield messages, get_item_recommendations_text(chunk.item_recommendations)


CSS = """
html, body, .gradio-container {height: 100% !important; min-height: 0 !important;}
#app_row {height: 100vh; min-height: 0 !important;}
#left_col {height: 100%; min-width: 320px; min-height: 0 !important;}
#right_col {height: 100%; min-height: 0 !important; display: flex; flex-direction: column;}
#recommend_box {flex: 1 1 0%; min-height: 0 !important; overflow: auto;}
#chat_log .wrap.svelte-1ipelgc {flex: 1 1 0%; height: 90% !important; min-height: 0 !important; overflow: auto;}
#chat_log {height: 90% !important; min-height: 0 !important;}
"""


async def main():
    """Main function."""
    with gr.Blocks(css=CSS) as demo:
        with gr.Row(elem_id="app_row"):
            # Left column: Chatbot log (fills height)
            with gr.Column(elem_id="left_col", scale=1):
                chat = gr.Chatbot(label="Agent Log", elem_id="chat_log", type="messages")

            # Right column: Search at top, recommendation fills remainder
            with gr.Column(elem_id="right_col", scale=2):
                search = gr.Textbox(label="Search Query", placeholder="What do you want to buy?", lines=1)
                search_btn = gr.Button("Search")
                recommend = gr.Markdown("### Recommendations will appear here", elem_id="recommend_box")

            search.submit(interact_with_agent, [search, chat], [chat, recommend])
            search_btn.click(interact_with_agent, [search, chat], [chat, recommend], preprocess=False)

    demo.launch()


if __name__ == "__main__":
    asyncio.run(main())
