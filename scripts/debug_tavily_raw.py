"""
scripts/debug_tavily_raw.py
----------------------------
Cek langsung respon mentah dari Tavily API tanpa filter domain/relevansi/URL validation.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tavily import TavilyClient
from app.core.settings import get_settings

def debug_raw():
    settings = get_settings()
    client = TavilyClient(api_key=settings.tavily_api_key)

    queries = [
        "TPIA saham Chandra Asri Pacific berita",
        "GMFI saham Garuda Maintenance berita"
    ]

    for q in queries:
        print(f"\n{'='*60}\n🔍 Query: {q}\n{'='*60}")
        try:
            # 1. Panggil tanpa include_domains (Broad Search)
            response = client.search(
                query=q,
                search_depth="basic",
                max_results=5,
                topic="news"
            )
            results = response.get("results", [])
            print(f"Total hasil dari Tavily (Tanpa Filter Domain): {len(results)}")

            for idx, res in enumerate(results, 1):
                print(f"  [{idx}] {res.get('title')}")
                print(f"      URL: {res.get('url')}")
                print(f"      Published: {res.get('published_date')}")

        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_raw()
