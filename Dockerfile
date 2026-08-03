FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy manifest dulu -> layer ini di-cache, cuma invalidate kalau dependency berubah
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Baru copy source code (paling sering berubah, di layer paling akhir)
COPY . .

# Non-root user
RUN groupadd -r app && useradd -r -g app -d /app app \
    && chown -R app:app /app

USER app

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=60s --timeout=10s --start-period=15s --retries=3 \
    CMD pgrep -f "discord_fundamental_bot.py" || exit 1

CMD ["uv", "run", "python", "scripts/discord_fundamental_bot.py"]
