FROM python:3.12-slim

WORKDIR /app

# System deps minimal
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Default: jalankan Discord bot (bisa di-override dari docker-compose)
CMD ["python", "scripts/discord_fundamental_bot.py"]
