"""Ticker + macro news fetch (NewsAPI.org) for dashboard and Live Advisor enrichment."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def fetch_news_parallel_sync(tickers: list[str], sectors: list[str]) -> dict[str, Any]:
    """Fetch micro (ticker query) and macro (business headlines) articles synchronously."""
    s = get_settings()
    micro: list[dict[str, Any]] = []
    macro: list[dict[str, Any]] = []
    with httpx.Client(timeout=15.0) as client:
        if s.news_api_key:
            q = " OR ".join(tickers[:8]) if tickers else "Nifty OR Sensex"
            try:
                r = client.get(
                    f"{s.news_api_url}/everything",
                    params={
                        "q": q or "India stock market",
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 15,
                        "apiKey": s.news_api_key,
                    },
                )
                if r.status_code == 200:
                    micro = r.json().get("articles", [])[:15]
            except Exception as e:
                logger.warning("News micro fetch failed: %s", e)
            try:
                r2 = client.get(
                    f"{s.news_api_url}/top-headlines",
                    params={
                        "category": "business",
                        "language": "en",
                        "pageSize": 15,
                        "apiKey": s.news_api_key,
                    },
                )
                if r2.status_code == 200:
                    macro = r2.json().get("articles", [])[:15]
            except Exception as e:
                logger.warning("News macro fetch failed: %s", e)
        else:
            micro = _placeholder_articles(tickers, sectors)
            macro = _placeholder_macro()
    return {"micro": micro, "macro": macro}


def _placeholder_articles(tickers: list[str], sectors: list[str]) -> list[dict[str, Any]]:
    t = ", ".join(tickers[:5]) or "portfolio"
    sec = ", ".join(sectors[:5]) or "diversified"
    return [
        {
            "title": f"Market watch: flows into {sec} names",
            "description": f"Analysts track positioning around {t}.",
            "url": "https://example.com/placeholder",
            "source": {"name": "DemoFeed"},
        }
    ]


def _placeholder_macro() -> list[dict[str, Any]]:
    return [
        {
            "title": "RBI and global rates in focus for emerging markets",
            "description": "Policy expectations drive near-term volatility.",
            "url": "https://example.com/macro",
            "source": {"name": "DemoMacro"},
        }
    ]
