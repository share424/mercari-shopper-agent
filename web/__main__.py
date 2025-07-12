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
agent = MercariShoppingAgent(client=client, model="claude-3-5-sonnet-latest")


def get_item_recommendations_text(item_recommendations: list[ItemRecommendation] | None) -> str:
    """Get the item recommendation markdown text."""
    text = "# Item Recommendations\n"
    if not item_recommendations:
        text += "No item recommendations found.\n"
        return text
    for i, item_recommendation in enumerate(item_recommendations, start=1):
        item = item_recommendation.item
        item_detail = item.item_detail
        if item_detail and item_detail.condition_type:
            condition = item_detail.condition_type
        else:
            condition = item.condition_grade

        price = f"{item.currency} {item.price}"
        if item_detail and item_detail.converted_price:
            price = f"{price} ({item_detail.converted_price})"

        text += f"## [{i}. {item_recommendation.item.name}]({item_recommendation.item.item_url})\n"
        text += f"![{item_recommendation.item.name}]({item_recommendation.item.image_url})\n\n"
        text += f"- **Price**: {price}\n"
        text += f"- **Condition**: {condition}\n"
        if item_detail:
            text += f"- **Seller**: {item_detail.seller_name} ({item_detail.seller_review_stars}★, {item_detail.seller_review} reviews, {item_detail.seller_verification_status})\n"  # noqa: E501
        text += f"- **Why Recommended**: \n\n{item_recommendation.reason}\n\n"
        text += "<details>\n"
        text += "<summary>More Details</summary>\n\n"

        if item_detail:
            text += "## Item Details\n"
            text += f"**Description**: \n\n```\n{item_detail.description}\n```\n"

        if item_detail and item_detail.categories:
            text += f"**Categories**: {', '.join(item_detail.categories)}\n"

        if item.market_research_result:
            text += "## Market Research Result\n"
            text += "```\n"
            text += item.market_research_result.get_llm_friendly_result()
            text += "\n```\n"
            text += "\n\n"

        if item.relevance_score:
            text += "## Relevance\n"
            text += f"**Score**: {item.relevance_score.score}\n\n"
            text += f"**Reasoning**: \n\n```\n{item.relevance_score.reasoning}\n```\n"

        text += "</details>\n\n"
        text += "---"
        text += "\n\n"
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
