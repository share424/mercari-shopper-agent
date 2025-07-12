"""Clear the cache."""

import asyncio

from app.libs.mercari_jp.search import MercariJPSearch


async def main():
    """Clear the cache."""
    async with MercariJPSearch(headless=False) as search:
        await search.clear_cache()


if __name__ == "__main__":
    asyncio.run(main())
