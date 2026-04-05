import io
import logging
import re
import wave
from typing import Any

import yfinance as yf
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth_firebase import require_user
from app.firestore_service import ensure_user, get_user
from app.services.gemini_vertex import gemini_tts, live_advisor_reply
from app.services.mfdata_service import enrich_mf_for_advisor, search_and_enrich
from app.services.news import fetch_news_parallel_sync
from app.services.valuation import value_portfolio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["advisor"])


def _extract_tickers_from_message(text: str) -> list[str]:
    """Best-effort extraction of stock ticker-like words from user text."""
    words = re.findall(r"\b[A-Z][A-Z0-9&]{1,19}\b", text.upper())
    stop = {
        "I", "A", "THE", "AND", "OR", "NOT", "FOR", "IN", "ON", "MY", "IS",
        "IT", "TO", "OF", "DO", "IF", "BE", "AT", "SO", "AS", "AN", "BY",
        "AM", "ARE", "WAS", "HAS", "CAN", "ALL", "BUT", "HOW", "YOU", "YES",
        "NO", "OK", "HOLD", "EXIT", "BUY", "SELL", "SWITCH", "SHOULD", "WHAT",
        "WHICH", "WHEN", "WHERE", "WHY", "WILL", "WOULD", "COULD", "THIS",
        "THAT", "FROM", "WITH", "HAVE", "FUND", "MF", "NAV", "SIP", "STOCK",
        "ETF", "INDEX", "MARKET", "INVEST", "PORTFOLIO", "ABOUT", "THINK",
        "GOOD", "BAD", "TIME", "NOW", "INTO", "OUT", "LIKE", "WANT", "NEED",
        "GIVE", "GET", "MAKE", "KEEP", "REMOVE", "REVIEW", "ANALYZE", "TELL",
        "NIFTY", "SENSEX", "BANKNIFTY", "NSE", "BSE",
    }
    return list(dict.fromkeys(w for w in words if w not in stop and len(w) >= 2))


def _fetch_stock_snapshot(ticker: str) -> dict[str, Any] | None:
    """Fetch real-time stock data via yfinance for a single ticker."""
    suffixes = [".NS", ".BO", ""]
    for sfx in suffixes:
        sym = ticker + sfx
        try:
            tk = yf.Ticker(sym)
            info = tk.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            if not price:
                hist = tk.history(period="5d")
                if hist is not None and not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if not price:
                continue

            week52_data: dict[str, Any] = {}
            if info.get("fiftyTwoWeekHigh"):
                week52_data["high"] = info["fiftyTwoWeekHigh"]
                week52_data["low"] = info.get("fiftyTwoWeekLow")
                pct_from_high = ((price - info["fiftyTwoWeekHigh"]) / info["fiftyTwoWeekHigh"]) * 100
                week52_data["pct_from_52w_high"] = round(pct_from_high, 1)

            hist_30d = tk.history(period="1mo")
            recent_trend = ""
            if hist_30d is not None and len(hist_30d) >= 2:
                month_start = float(hist_30d["Close"].iloc[0])
                month_end = float(hist_30d["Close"].iloc[-1])
                change = ((month_end - month_start) / month_start) * 100
                recent_trend = f"{'Up' if change >= 0 else 'Down'} {abs(change):.1f}% in last month"

            return {
                "symbol": sym,
                "name": info.get("shortName") or info.get("longName") or ticker,
                "currentPrice": round(price, 2),
                "currency": info.get("currency", "INR"),
                "marketCap_cr": round(info["marketCap"] / 1e7, 0) if info.get("marketCap") else None,
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "pb_ratio": info.get("priceToBook"),
                "dividend_yield_pct": round(info["dividendYield"] * 100, 2) if info.get("dividendYield") else None,
                "52_week": week52_data,
                "volume": info.get("regularMarketVolume"),
                "avg_volume": info.get("averageVolume"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_margins": info.get("profitMargins"),
                "debt_to_equity": info.get("debtToEquity"),
                "roe": info.get("returnOnEquity"),
                "recent_trend": recent_trend,
                "beta": info.get("beta"),
            }
        except Exception as e:
            logger.debug("yfinance snapshot %s failed: %s", sym, e)
            continue
    return None


def _enrich_query_context(last_user_msg: str) -> dict[str, Any]:
    """Extract tickers from user message, fetch live data + news for them."""
    tickers = _extract_tickers_from_message(last_user_msg)
    if not tickers:
        return {}

    stock_data: list[dict[str, Any]] = []
    for t in tickers[:3]:
        snap = _fetch_stock_snapshot(t)
        if snap:
            stock_data.append(snap)

    news_data: list[dict[str, str]] = []
    if stock_data:
        search_tickers = [s.get("name", s["symbol"]) for s in stock_data]
        try:
            raw = fetch_news_parallel_sync(search_tickers, [])
            for article in (raw.get("micro") or [])[:5]:
                news_data.append({
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "source": (article.get("source") or {}).get("name", ""),
                })
        except Exception:
            pass

    if not stock_data:
        return {}

    return {
        "queried_stocks": stock_data,
        "related_news": news_data,
    }


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=8000)


class LiveChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=32)


@router.post("/live/chat")
def advisor_live_chat(body: LiveChatRequest, uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    p = u.get("portfolio") or {}
    pol = u.get("policy") or {}
    fb = dict(p.get("lastPrices") or {})
    v = value_portfolio(p, fb)
    v.pop("lastPrices", None)

    mf_enrichments: list[dict[str, Any]] = []
    for mf_line in v.get("mutualFunds") or []:
        code = str(mf_line.get("amfiCode") or "").strip()
        fund_name = str(mf_line.get("name") or "").strip()
        enriched: dict[str, Any] = {}
        if code:
            enriched = enrich_mf_for_advisor(code)
        if not enriched and fund_name and len(fund_name) > 4:
            enriched = search_and_enrich(fund_name)
        if enriched:
            enriched["user_holding_name"] = fund_name
            enriched["user_isin"] = mf_line.get("isin", "")
            enriched["user_pnl_pct"] = mf_line.get("pnlPct", 0)
            mf_enrichments.append(enriched)

    portfolio_snapshot = {
        "cash": p.get("cash"),
        "stocks": p.get("stocks") or [],
        "mutualFunds": p.get("mutualFunds") or [],
        "valuation": {
            "netWorth": v.get("netWorth"),
            "totalPnl": v.get("totalPnl"),
            "approxReturnPct": v.get("approxReturnPct"),
            "equity": v.get("equity"),
            "mutualFunds": v.get("mutualFunds"),
            "allocation": v.get("allocation"),
        },
        "mfAnalysis": mf_enrichments,
    }
    policy_snapshot = {
        "goals": pol.get("goals") or [],
        "maxDrawdownPct": pol.get("maxDrawdownPct"),
        "riskProfile": pol.get("riskProfile") or pol.get("risk_profile"),
        "minBankBuffer": pol.get("minBankBuffer"),
        "currentAccountBalance": pol.get("currentAccountBalance"),
    }

    msgs = [{"role": m.role, "content": m.content} for m in body.messages]

    last_user_msg = ""
    for m in reversed(msgs):
        if m["role"] == "user":
            last_user_msg = m["content"]
            break
    query_context = _enrich_query_context(last_user_msg) if last_user_msg else {}

    out = live_advisor_reply(msgs, portfolio_snapshot, policy_snapshot, query_context)
    return out


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = Field(default="Kore")


@router.post("/tts")
def advisor_tts(body: TTSRequest, uid: str = Depends(require_user)):
    """Convert text to natural human-like speech using Gemini TTS."""
    pcm = gemini_tts(body.text, voice=body.voice)
    if pcm is None:
        return Response(content=b"", status_code=503, media_type="text/plain")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)
    return Response(
        content=buf.getvalue(),
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=advisor.wav"},
    )
