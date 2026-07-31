"""
scripts/test_tavily.py
-----------------------
Test Tavily adapter - pastikan news bisa di-fetch & sentiment terdeteksi.
Usage: python scripts/test_tavily.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.adapters.tavily_adapter import TavilyAdapter
from app.core.logging import get_logger

logger = get_logger("test_tavily")

TEST_CASES = [
    {"ticker": "TPIA", "nama": "Chandra Asri Pacific"},
    {"ticker": "GMFI", "nama": "Garuda Maintenance Facility Semesta"}
]


def test_news():
    adapter = TavilyAdapter()

    for case in TEST_CASES:
        ticker = case["ticker"]
        nama   = case["nama"]

        print(f"\n{'='*50}")
        print(f"🔍 {ticker} - {nama}")
        print(f"{'='*50}")

        result = adapter.search_news(ticker, nama)

        if not result:
            print(f"❌ GAGAL fetch news untuk {ticker}")
            continue

        print(f"✅ Overall Sentiment : {result.overall_sentiment.value.upper()}")
        print(f"   Foreign Interest  : {'✅ YA' if result.has_foreign_interest else '❌ TIDAK'}")
        print(f"   Total Berita      : {len(result.items)}")
        print()

        if not result.items:
            print("   (Tidak ada berita relevan ditemukan)")

        for i, item in enumerate(result.items, 1):
            sentiment_icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(
                item.sentiment.value, "⚪"
            )
            print(f"   [{i}] {sentiment_icon} {item.title}")
            print(f"       URL : {item.url}")
            if item.published_date:
                print(f"       📅  : {item.published_date}")
            print()


if __name__ == "__main__":
    print("\n📰 Testing Tavily adapter...\n")
    test_news()
    print("\n✅ Test selesai.")
