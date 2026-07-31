FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY . .

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "python", "scripts/discord_fundamental_bot.py"]
