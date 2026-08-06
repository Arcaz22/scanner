def normalize_ticker(ticker: str) -> str:
    """Return canonical IDX ticker without provider suffix."""
    return ticker.strip().upper().removesuffix(".JK")
