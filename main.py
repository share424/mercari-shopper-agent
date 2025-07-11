"""Main module.

This module contains the main function to run the Mercari Shopping Agent.
"""

import asyncio
import os
from argparse import ArgumentParser

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from app.agent import MercariShoppingAgent


async def main():
    """Main function to run the Mercari Shopping Agent."""
    parser = ArgumentParser()
    parser.add_argument("--query", "-q", type=str, required=True)
    args = parser.parse_args()

    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    agent = MercariShoppingAgent(
        client=client,
        model="claude-3-5-sonnet-latest",
        serpapi_api_key=os.getenv("SERPAPI_API_KEY", ""),
    )
    recommendations = await agent.run(args.query)
    if not recommendations:
        print("No recommendations found")
        return

    print("===========RECOMMENDATIONS===========")
    for recommendation in recommendations:
        print(recommendation.model_dump_json(indent=2))
        print("-" * 100)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
