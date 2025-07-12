
# 1. Base Image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# 2. Set up the working directory
WORKDIR /app

# 3. Copy dependency definitions
COPY pyproject.toml uv.lock .python-version ./

# 4. Install dependencies
RUN uv sync --locked

# 6. Copy the rest of the application code
COPY app ./app
COPY web.py ./
COPY cli.py ./

# 7. Install Playwright browsers
RUN uv run playwright install --with-deps chromium

# 8. Set the command to run the application
CMD ["uv", "run", "web.py"]

