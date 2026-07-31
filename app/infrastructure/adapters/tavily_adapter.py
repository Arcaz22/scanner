"""
infrastructure/adapters/tavily_adapter.py
------------------------------------------
Fetch berita & detect foreign interest via Tavily Search API.
Satu-satunya tempat yang boleh panggil Tavily.
"""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from tavily import TavilyClient

from app.domain.enums import Sentiment
from app.domain.news import NewsItem, NewsResult
from app.utils.helper import normalize_ticker
from app.core.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Keyword untuk detect foreign/institutional interest
FOREIGN_KEYWORDS = [
    "foreign", "asing", "institutional", "fund", "investor asing",
    "net buy", "net foreign", "beli asing", "foreign net buy",
]

# Keyword sentiment positif
POSITIVE_KEYWORDS = [
    "naik", "bullish", "rekomendasi beli", "target price", "upgrade",
    "akuisisi", "dividen", "laba naik", "profit", "ekspansi",
    "buy", "strong buy", "outperform", "overweight", "accumulate",
]

# Keyword sentiment negatif
NEGATIVE_KEYWORDS = [
    "turun", "bearish", "jual", "rugi", "penurunan", "downgrade",
    "sell", "underperform", "underweight", "suspend", "delisting",
    "kerugian", "gagal bayar", "default", "pailit",
]


class TavilyAdapter:

    def __init__(self):
        settings = get_settings()
        if not settings.tavily_api_key:
            raise ValueError("TAVILY_API_KEY tidak ditemukan di .env")
        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.max_results = settings.tavily_max_results
        self.search_days = settings.tavily_search_days
        self.include_domains = self._csv(settings.tavily_include_domains)
        self.exclude_domains = self._csv(settings.tavily_exclude_domains)
        self.validate_urls = settings.tavily_validate_urls
        self.url_check_timeout = settings.tavily_url_check_timeout
        self.debug_results = settings.tavily_debug_results
        self.allow_broad_retry = settings.tavily_allow_broad_retry

    def search_news(self, ticker: str, company_name: str = "") -> Optional[NewsResult]:
        """
        Cari berita untuk satu saham.
        Jalankan 2 search: general news + foreign interest.
        Return NewsResult dengan max 3 berita paling relevan.
        """
        try:
            clean_ticker = normalize_ticker(ticker)
            name = self._compact_company_name(company_name) or clean_ticker

            all_items: list[NewsItem] = []

            # ── Search 1: General news & catalyst (Exact match query) ───────
            results_1 = self._search(
                query=f'"{clean_ticker}" saham OR "{name}" IDX',
                ticker=clean_ticker,
                company_name=name,
            )
            all_items.extend(results_1)

            # ── Search 2: Foreign/institutional interest ───────────────────
            results_2 = self._search(
                query=f'"{clean_ticker}" asing net buy OR foreign',
                ticker=clean_ticker,
                company_name=name,
            )
            all_items.extend(results_2)

            # Deduplicate by URL
            seen_urls = set()
            unique = []
            for item in all_items:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    unique.append(item)

            # Batasi max results sesuai setting
            top_items = unique[:self.max_results]

            # Detect foreign interest dari semua results
            has_foreign = self._detect_foreign_interest(all_items)

            # Overall sentiment dari top items
            sentiment = self._overall_sentiment(top_items)

            logger.info(
                f"{ticker}: {len(top_items)} berita | "
                f"sentiment={sentiment.value} | foreign={has_foreign}"
            )

            return NewsResult(
                ticker               = ticker,
                items                = top_items,
                overall_sentiment    = sentiment,
                has_foreign_interest = has_foreign,
                searched_at          = datetime.now(),
            )

        except Exception as e:
            logger.error(f"{ticker}: Gagal fetch news - {e}")
            return None

    def search_news_batch(
        self,
        tickers: list[str],
        saham_names: dict[str, str] = None,
    ) -> dict[str, Optional[NewsResult]]:
        """
        Fetch news untuk list of tickers.
        saham_names: dict {ticker: nama_perusahaan}
        """
        results = {}
        names = saham_names or {}

        for ticker in tickers:
            company_name = names.get(ticker, "")
            results[ticker] = self.search_news(ticker, company_name)

        return results

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _search(
        self,
        query: str,
        ticker: str,
        company_name: str,
        include_domains: list[str] | None = None,
    ) -> list[NewsItem]:
        """
        Raw Tavily search, return list of NewsItem.
        """
        try:
            include_domains = self.include_domains if include_domains is None else include_domains
            response = self.client.search(
                query         = query,
                search_depth  = "basic",
                max_results   = max(10, self.max_results * 4),
                include_answer= False,
                include_domains=include_domains,
                exclude_domains=self.exclude_domains,
                days=self.search_days,
                topic="news",
            )

            items = self._parse_results(response.get("results", []), include_domains, ticker, company_name)
            if not items and include_domains and self.allow_broad_retry:
                logger.info("Tavily kosong setelah filter domain; retry tanpa include_domains untuk '%s'", query)
                return self._search(query, ticker=ticker, company_name=company_name, include_domains=[])
            return items

        except TypeError:
            return self._search_compat(
                query,
                ticker=ticker,
                company_name=company_name,
                include_domains=include_domains,
            )
        except Exception as e:
            logger.warning(f"Tavily search gagal untuk '{query}': {e}")
            return []

    def _search_compat(
        self,
        query: str,
        ticker: str,
        company_name: str,
        include_domains: list[str] | None = None,
    ) -> list[NewsItem]:
        """
        Fallback untuk SDK versi lama.
        """
        try:
            include_domains = self.include_domains if include_domains is None else include_domains
            response = self.client.search(
                query=query,
                search_depth="basic",
                max_results=max(10, self.max_results * 4),
                include_answer=False,
                include_domains=include_domains,
                exclude_domains=self.exclude_domains,
                days=self.search_days,
            )
            items = self._parse_results(response.get("results", []), include_domains, ticker, company_name)
            if not items and include_domains and self.allow_broad_retry:
                logger.info("Tavily kosong setelah filter domain; retry tanpa include_domains untuk '%s'", query)
                return self._search_compat(
                    query,
                    ticker=ticker,
                    company_name=company_name,
                    include_domains=[],
                )
            return items
        except Exception as e:
            logger.warning(f"Tavily search gagal untuk '{query}': {e}")
            return []

    def _parse_results(
        self,
        results: list[dict],
        include_domains: list[str],
        ticker: str,
        company_name: str,
    ) -> list[NewsItem]:
        items = []
        for result in results:
            item = self._parse_result(result, include_domains, ticker, company_name)
            if item:
                items.append(item)
        return items

    def _parse_result(
        self,
        result: dict,
        include_domains: list[str],
        ticker: str,
        company_name: str,
    ) -> NewsItem | None:
        title = (result.get("title") or "").strip()
        url = (result.get("url") or "").strip()
        content = (result.get("content") or result.get("snippet") or "").strip()

        if self.debug_results:
            logger.info("Tavily raw result title=%r url=%s", title, url)

        if not title or not url:
            if self.debug_results:
                logger.info("Tavily result dibuang: title/url kosong")
            return None
        if not self._allowed_url(url, include_domains):
            if self.debug_results:
                logger.info("Tavily result dibuang: domain tidak diizinkan url=%s", url)
            return None
        if not self._relevant_result(title, content, ticker, company_name):
            if self.debug_results:
                logger.info("Tavily result dibuang: tidak relevan ticker=%s title=%r", ticker, title)
            return None
        if not self._reachable_url(url):
            if self.debug_results:
                logger.info("Tavily result dibuang: URL tidak reachable url=%s", url)
            return None

        sentiment = self._classify_sentiment(f"{title} {content}")
        return NewsItem(
            title          = title,
            url            = url,
            snippet        = content[:200],
            published_date = result.get("published_date") or result.get("publishedDate"),
            sentiment      = sentiment,
        )

    def _allowed_url(self, url: str, include_domains: list[str]) -> bool:
        hostname = (urlparse(url).hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if self.exclude_domains and any(hostname == d or hostname.endswith(f".{d}") for d in self.exclude_domains):
            return False
        if not include_domains:
            return True
        return any(hostname == d or hostname.endswith(f".{d}") for d in include_domains)

    def _relevant_result(self, title: str, content: str, ticker: str, company_name: str) -> bool:
        """
        Validasi ketat relevansi berita terhadap Ticker & Nama Perusahaan.
        """
        text = f"{title} {content}".lower()
        ticker_clean = ticker.lower()

        # 1. Cek apakah ticker ada sebagai KATA UTUH (bukan substring kata lain)
        if re.search(rf"\b{re.escape(ticker_clean)}\b", text):
            return True

        # 2. Kata-kata generic/stop words yang sering membuat false positive
        stop_words = {
            "pt", "tbk", "persero", "saham", "berita", "indonesia",
            "pacific", "facility", "maintenance", "global", "asia", "the", "dan"
        }

        tokens = [
            token for token in re.findall(r"[a-z0-9]+", company_name.lower())
            if len(token) >= 4 and token not in stop_words
        ]

        if not tokens:
            return False

        # Minimal 2 kata kunci spesifik harus cocok (e.g. "chandra" AND "asri")
        matches = sum(1 for token in tokens if token in text)
        return matches >= min(2, len(tokens))

    def _reachable_url(self, url: str) -> bool:
        if not self.validate_urls:
            return True
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        try:
            # Gunakan GET langsung dengan stream=True agar hemat bandwidth dan menghindari blokir HEAD
            response = requests.get(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=self.url_check_timeout,
                stream=True,
            )
            content = next(response.iter_content(chunk_size=4096, decode_unicode=True), "") or ""
            response.close()

            if self.debug_results:
                logger.info("Tavily URL check GET status=%s url=%s", response.status_code, url)

            if response.status_code in {403, 404, 410, 451}:
                logger.info("Tavily URL dibuang status=%s url=%s", response.status_code, url)
                return False

            if self._looks_like_soft_404(response.url, content):
                logger.info("Tavily URL dibuang soft-404 url=%s final_url=%s", url, response.url)
                return False

            return 200 <= response.status_code < 400
        except requests.RequestException as err:
            logger.info("Tavily URL dibuang karena timeout/connection error: %s url=%s", err, url)
            return False

    def _looks_like_soft_404(self, final_url: str, content: str) -> bool:
        parsed = urlparse(final_url)
        path = parsed.path.strip("/").lower()
        if path == "404" or path.startswith("404/"):
            return True
        text = content.lower()
        soft_404_markers = (
            "the page you requested was not found",
            "page not found",
            "404 not found",
            "halaman tidak ditemukan",
        )
        return any(marker in text for marker in soft_404_markers)

    def _compact_company_name(self, value: str) -> str:
        ignored = {"pt", "tbk", "persero", "the", "dan", "&"}
        words = [
            word.strip(".,()").lower()
            for word in (value or "").split()
            if word.strip(".,()")
        ]
        selected = [word for word in words if word not in ignored]
        return " ".join(selected[:3])

    def _csv(self, value: str) -> list[str]:
        return [
            item.strip().lower().removeprefix("www.")
            for item in (value or "").split(",")
            if item.strip()
        ]

    def _classify_sentiment(self, text: str) -> Sentiment:
        text_lower = text.lower()
        pos_score = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
        neg_score = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)

        if pos_score > neg_score:
            return Sentiment.POSITIVE
        elif neg_score > pos_score:
            return Sentiment.NEGATIVE
        return Sentiment.NEUTRAL

    def _detect_foreign_interest(self, items: list[NewsItem]) -> bool:
        for item in items:
            text = (item.title + " " + item.snippet).lower()
            if any(kw in text for kw in FOREIGN_KEYWORDS):
                return True
        return False

    def _overall_sentiment(self, items: list[NewsItem]) -> Sentiment:
        if not items:
            return Sentiment.NEUTRAL

        pos = sum(1 for i in items if i.sentiment == Sentiment.POSITIVE)
        neg = sum(1 for i in items if i.sentiment == Sentiment.NEGATIVE)

        if pos > neg:
            return Sentiment.POSITIVE
        elif neg > pos:
            return Sentiment.NEGATIVE
        return Sentiment.NEUTRAL
