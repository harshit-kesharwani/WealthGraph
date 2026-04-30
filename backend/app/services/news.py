"""Ticker + macro news fetch (NewsAPI.org) for dashboard and Live Advisor enrichment."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Only keep articles with publishedAt within this window (NewsAPI + client-side filter).
NEWS_RECENT_HOURS = 24


def _newsapi_from_param_utc() -> str:
    """ISO8601 UTC `from` for NewsAPI `everything` (last NEWS_RECENT_HOURS)."""
    t = datetime.now(timezone.utc) - timedelta(hours=NEWS_RECENT_HOURS)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_article_published_at(article: dict[str, Any]) -> datetime | None:
    raw = article.get("publishedAt") or article.get("published_at")
    if not raw:
        return None
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def article_published_within_hours(article: dict[str, Any], hours: int = NEWS_RECENT_HOURS) -> bool:
    """True only if publishedAt parses and is within the last `hours` (UTC)."""
    dt = _parse_article_published_at(article)
    if dt is None:
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)


def filter_articles_by_recency(articles: list[Any], hours: int = NEWS_RECENT_HOURS) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in articles:
        if isinstance(a, dict) and article_published_within_hours(a, hours):
            out.append(a)
    return out


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
                        "from": _newsapi_from_param_utc(),
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 15,
                        "apiKey": s.news_api_key,
                    },
                )
                if r.status_code == 200:
                    micro = filter_articles_by_recency(r.json().get("articles", [])[:20])[:15]
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
                    macro = filter_articles_by_recency(r2.json().get("articles", [])[:20])[:15]
            except Exception as e:
                logger.warning("News macro fetch failed: %s", e)
        else:
            micro = _placeholder_articles(tickers, sectors)
            macro = _placeholder_macro()
    return {"micro": micro, "macro": macro}


_MAX_Q_CHARS = 360


def _chunk_or_terms(terms: list[str]) -> list[list[str]]:
    """Split terms into batches so ' OR '.join(batch) stays under NewsAPI practical limits."""
    batches: list[list[str]] = []
    cur: list[str] = []
    for t in terms:
        t = str(t).strip()
        if not t:
            continue
        trial = " OR ".join(cur + [t]) if cur else t
        if len(trial) > _MAX_Q_CHARS and cur:
            batches.append(cur)
            cur = [t]
        else:
            cur.append(t)
    if cur:
        batches.append(cur)
    return batches or [["Nifty", "Sensex"]]


def fetch_news_extended_micro_macro(micro_terms: list[str], sectors: list[str]) -> dict[str, Any]:
    """Like fetch_news_parallel_sync but supports many OR-terms via multiple everything calls."""
    s = get_settings()
    micro: list[dict[str, Any]] = []
    macro: list[dict[str, Any]] = []
    with httpx.Client(timeout=20.0) as client:
        if s.news_api_key:
            for batch in _chunk_or_terms(micro_terms):
                q = " OR ".join(batch) if batch else "India stock market"
                try:
                    r = client.get(
                        f"{s.news_api_url}/everything",
                        params={
                            "q": q or "India stock market",
                            "from": _newsapi_from_param_utc(),
                            "language": "en",
                            "sortBy": "publishedAt",
                            "pageSize": 12,
                            "apiKey": s.news_api_key,
                        },
                    )
                    if r.status_code == 200:
                        micro.extend(filter_articles_by_recency(r.json().get("articles", [])[:20])[:12])
                except Exception as e:
                    logger.warning("News extended micro fetch failed: %s", e)
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
                    macro = filter_articles_by_recency(r2.json().get("articles", [])[:20])[:15]
            except Exception as e:
                logger.warning("News macro fetch failed: %s", e)
        else:
            micro = _placeholder_articles(micro_terms[:8], sectors)
            macro = _placeholder_macro()
    return {"micro": micro, "macro": macro}


def _article_text(a: dict[str, Any]) -> str:
    title = str(a.get("title", "") or "")
    desc = str(a.get("description", "") or "")
    return f"{title} {desc}".lower()


def merge_rank_dedupe_articles(
    raw: dict[str, Any],
    scoring_tokens: list[str],
    limit: int = 15,
    strong_tokens: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Merge micro + macro, dedupe by title, rank by token hits in title+description."""
    strong = [t.lower() for t in (strong_tokens or []) if t and str(t).strip()]
    strong = list(dict.fromkeys(strong))

    items: list[dict[str, Any]] = []
    for key in ("micro", "macro"):
        arts = raw.get(key)
        if not isinstance(arts, list):
            continue
        for a in arts:
            if not isinstance(a, dict):
                continue
            if not article_published_within_hours(a, NEWS_RECENT_HOURS):
                continue
            items.append(a)

    def score(a: dict[str, Any]) -> int:
        blob = _article_text(a)
        n = sum(1 for tok in scoring_tokens if tok and tok in blob)
        n += sum(2 for tok in strong if tok and tok in blob)
        return n

    seen: set[str] = set()
    ranked: list[tuple[int, dict[str, Any]]] = []
    for a in items:
        title = str(a.get("title", "") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        ranked.append((score(a), a))

    ranked.sort(key=lambda x: (-x[0], x[1].get("publishedAt") or ""))
    out: list[dict[str, Any]] = []
    for _sc, a in ranked[:limit]:
        url = a.get("url", "")
        if "example.com" in str(url):
            continue
        out.append({
            "title": a.get("title", ""),
            "description": a.get("description", ""),
            "source": (a.get("source") or {}).get("name", ""),
            "url": url,
        })
    return out


def _placeholder_articles(tickers: list[str], sectors: list[str]) -> list[dict[str, Any]]:
    t = ", ".join(tickers[:5]) or "portfolio"
    sec = ", ".join(sectors[:5]) or "diversified"
    from urllib.parse import quote

    q = quote(f"{t} India stocks news")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        {
            "title": f"Market watch: flows into {sec} names",
            "description": f"Analysts track positioning around {t}.",
            "url": f"https://www.google.com/search?q={q}",
            "source": {"name": "DemoFeed"},
            "publishedAt": now_iso,
        }
    ]


def _placeholder_macro() -> list[dict[str, Any]]:
    from urllib.parse import quote

    q = quote("RBI India business news")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        {
            "title": "RBI and global rates in focus for emerging markets",
            "description": "Policy expectations drive near-term volatility.",
            "url": f"https://www.google.com/search?q={q}",
            "source": {"name": "DemoMacro"},
            "publishedAt": now_iso,
        }
    ]
