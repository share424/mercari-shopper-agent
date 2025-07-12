# Mercari AI Shopper Documentation

## 1. Project Overview

The Mercari AI Shopper is a Python-based AI agent designed to automate the process of finding and recommending products on Mercari Japan based on a user's natural language request.

The agent's core responsibilities are:
1.  **Interpreting User Needs**: Understanding a user's query (e.g., "I'm looking for a used Sony WH-1000XM4 headphone in good condition").
2.  **Searching Mercari**: Performing intelligent searches on `mercari.com`.
3.  **Gathering Market Intelligence**: Researching the broader market (via eBay) to establish fair pricing and market conditions.
4.  **Evaluating Candidates**: Scoring search results for relevance against the user's query.
5.  **Recommending Products**: Analyzing all gathered data to select the top 3 items and provide a clear justification for each recommendation.

The project adheres to the technical requirement of not using third-party AI agent frameworks like LangChain, instead implementing the agent's control flow and tool-calling logic from scratch using the official Anthropic Python SDK.

## 2. System Architecture

The agent is built on a stateful, tool-based architecture. A central `MercariShoppingAgent` orchestrates a series of specialized tools to accomplish its goal. The entire system is asynchronous, leveraging `asyncio` for high-performance I/O operations (API calls and web scraping).

The architecture can be broken down into the following key components:

-   **Agent (`app/agent.py`)**: The "brain" of the system. It manages the main loop, maintains the state, and decides which tool to call based on the conversation history and the LLM's suggestions.
-   **Tools (`app/tools/`)**: A collection of modules that represent the actions the agent can perform. Each tool is a self-contained unit that interacts with the agent's state.
-   **State (`app/types.py`)**: A central Pydantic model (`State`) that holds all the information gathered during the agent's run, including the user query, search results, and final recommendations. It acts as the agent's short-term memory.
-   **Libraries (`app/libs/`)**: Low-level modules responsible for interacting with external services. This includes a robust web scraper for Mercari and a market research client that uses SerpApi.
-   **Prompts (`app/prompts/`)**: Python files containing the prompt templates used to instruct the LLM for different tasks (e.g., the main agent prompt, the item evaluation prompt).
-   **Entry Point (`main.py`)**: A simple script to initialize and run the agent from the command line.

### Data Flow

The agent's operational flow follows a logical sequence of data gathering, enrichment, and decision-making:

1.  **Initiation**: The user provides a query via the command line. The `MercariShoppingAgent` is initialized with a blank `State` object containing this query.
2.  **Search**: The agent typically first calls the `mercari_search` tool. This tool uses the Playwright-based scraper in `app/libs/mercari/` to fetch search results. These results are parsed into `Item` objects and added to the `search_results` list in the `State`.
3.  **Market Research (Optional)**: The agent can call the `general_market_research` tool to get a high-level view of the market for a product, or the `market_research` tool to analyze specific items found in the search results. This uses SerpApi to fetch eBay data, performs a statistical analysis, and attaches a `MarketIntelligenceResult` to the relevant items in the `State`.
4.  **Evaluation (Optional)**: The agent can call the `evaluate_search_result` tool. This tool acts as a sub-agent, making a separate LLM call for each item to score its relevance. The resulting `ItemRelevanceScore` is attached to the items in the `State`.
5.  **Selection**: After one or more cycles of the steps above, the LLM has enough information. It then calls the `select_best_item` tool, providing the IDs of the final recommended items and a reason for each.
6.  **Termination**: The `select_best_item` tool populates the `recommended_items` list in the `State`. The agent's main loop detects that this list is no longer empty and terminates the run, printing the final recommendations.

## 3. Core Components Deep Dive

### 3.1. Web Scraper (`app/libs/mercari/`)

The web scraper is a particularly robust and well-engineered component.

-   **Technology**: It uses `Playwright` for browser automation, allowing it to handle modern, JavaScript-heavy websites. It also employs `playwright-stealth` to reduce the likelihood of being detected and blocked.
-   **Data Extraction Strategy**: Instead of relying on fragile CSS selectors for individual data points, the scraper smartly targets `<script type="application/ld+json">` tags embedded in the Mercari search results. This JSON-LD data is a structured, reliable source of product information, making the scraper resilient to minor UI changes.
-   **Concurrency & Caching**: The scraper fetches item details concurrently using an `asyncio.Semaphore` to limit simultaneous requests. Furthermore, it uses `aiocache` with a Redis backend to cache item details, dramatically speeding up subsequent runs and reducing the load on Mercari's servers.

### 3.2. Market Intelligence Engine (`app/libs/market_research/`)

This component provides data-driven insights into product pricing.

-   **Data Source**: It uses the `serpapi` service to query eBay's search results for a given product, using eBay as a proxy for the general second-hand market.
-   **Statistical Analysis**: The engine does not just average prices. It performs a sophisticated statistical analysis using `numpy` and `statistics` to:
    -   Calculate price percentiles to define tiers (e.g., "budget", "mid-range", "premium", "excellent deal").
    -   Determine price volatility by calculating the coefficient of variation.
-   **Actionable Insights**: The raw statistics are translated into human-readable guidance on price strategy, timing, and value, which the agent can then reason about.

### 3.3. "Sub-Agent" Evaluator Tool (`app/tools/evaluate_search_result.py`)

This tool demonstrates an advanced agentic pattern. Instead of relying on simple heuristics, it acts as a specialized sub-agent to evaluate items.

-   For each item it needs to evaluate, it makes a new, focused call to the Anthropic API.
-   It uses a specific prompt that provides the LLM with rich context: the original user query, the item's details, and any available market research data.
-   It expects a structured JSON response containing a relevance score and reasoning, which it then attaches back to the item in the agent's state.

This "agent-within-a-tool" approach allows the main agent to delegate complex, nuanced reasoning tasks, keeping the main loop focused on high-level orchestration.

## 4. How to Run

1.  Create a `.env` file in the root directory and add your API keys:
    ```
    ANTHROPIC_API_KEY="your_anthropic_key"
    SERPAPI_API_KEY="your_serpapi_key"
    ```
2.  Install dependencies: `pip install -r requirements.txt` (assuming a requirements file exists).
3.  Run the agent with a query:
    ```sh
    python main.py --query "your search query here"
    ```
