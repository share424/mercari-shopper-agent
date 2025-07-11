"""Main module.

This module contains the main function to run the Mercari Shopping Agent.
"""

import asyncio
import os

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from app.agent import MercariShoppingAgent


async def main():
    """Main function to run the Mercari Shopping Agent."""
    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    agent = MercariShoppingAgent(client=client, model="claude-3-5-sonnet-latest")
    recommendations = await agent.run("I want to buy a new phone for my self, my budget is $500")
    print("===========RECOMMENDATIONS===========")
    for recommendation in recommendations:
        print(recommendation.model_dump_json(indent=2))
        print("-" * 100)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
