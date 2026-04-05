import logging
import time
from typing import Any

from fastapi import APIRouter, Depends

from app.auth_firebase import require_user
from app.config import get_settings
from app.firestore_service import ensure_user, get_user
from app.services.valuation import value_portfolio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_indices_cache: dict[str, Any] = {}
_indices_ts: float = 0


@router.get("/summary")
def dashboard_summary(uid: str = Depends(require_user)):
    """Fast path: no LangGraph. Updates lastPrices when live fetch succeeds."""
    ensure_user(uid)
    u = get_user(uid) or {}
    p = u.get("portfolio") or {}
    pol = u.get("policy") or {}
    fb = dict(p.get("lastPrices") or {})
    v = value_portfolio(p, fb)
    last_prices = v.pop("lastPrices", {})
    from app.firestore_service import set_portfolio

    set_portfolio(uid, {**p, "lastPrices": last_prices})
    goals = pol.get("goals") or []
    goal_progress = []
    nw = float(v.get("netWorth", 0))
    for g in goals:
        tgt = float(g.get("targetAmount", 0))
        goal_progress.append(
            {
                "id": g.get("id"),
                "name": g.get("name"),
                "targetAmount": tgt,
                "targetYear": g.get("targetYear"),
                "progressPct": min(100.0, (nw / tgt * 100) if tgt > 0 else 0),
            }
        )
    return {
        "netWorth": v.get("netWorth"),
        "totalInvested": v.get("totalInvested"),
        "cash": v.get("cash"),
        "totalPnl": v.get("totalPnl"),
        "approxReturnPct": v.get("approxReturnPct"),
        "xirrNote": v.get("xirrNote"),
        "allocation": v.get("allocation"),
        "equity": v.get("equity"),
        "mutualFunds": v.get("mutualFunds"),
        "priceWarnings": v.get("priceWarnings"),
        "goalProgress": goal_progress,
        "autopilot": False,
    }


_INDEX_SYMBOLS = [
    ("NIFTY 50", "^NSEI"),
    ("SENSEX", "^BSESN"),
    ("BANK NIFTY", "^NSEBANK"),
]


@router.get("/indices")
def market_indices():
    """Last business day close + change for major Indian indices. Cached 5 min."""
    global _indices_cache, _indices_ts
    if _indices_cache and time.time() - _indices_ts < 300:
        return _indices_cache

    import datetime as _dt

    import yfinance as yf

    results = []
    for label, sym in _INDEX_SYMBOLS:
        entry: dict[str, Any] = {
            "name": label,
            "symbol": sym,
            "value": None,
            "changePct": None,
            "lastUpdated": None,
            "sessionLabel": None,
        }
        hist = None
        for period in ("5d", "1mo", "3mo", "6mo"):
            try:
                h = yf.Ticker(sym).history(period=period)
                if h is not None and not h.empty:
                    hist = h
                    break
            except Exception as exc:
                logger.debug("yfinance index %s %s: %s", sym, period, exc)
        try:
            if hist is not None and len(hist) >= 2:
                close_today = float(hist["Close"].iloc[-1])
                close_prev = float(hist["Close"].iloc[-2])
                entry["value"] = round(close_today, 2)
                entry["changePct"] = round(
                    (close_today - close_prev) / close_prev * 100, 2
                ) if close_prev > 0 else 0.0
                entry["lastUpdated"] = str(hist.index[-1].date())
            elif hist is not None and len(hist) == 1:
                entry["value"] = round(float(hist["Close"].iloc[-1]), 2)
                entry["lastUpdated"] = str(hist.index[-1].date())
        except Exception as exc:
            logger.debug("yfinance index %s: %s", sym, exc)

        if entry["lastUpdated"]:
            try:
                bar_d = _dt.date.fromisoformat(entry["lastUpdated"])
                today = _dt.date.today()
                if bar_d < today:
                    entry["sessionLabel"] = "Last trading session"
            except ValueError:
                entry["sessionLabel"] = "Last trading session"
        results.append(entry)

    resp = {"indices": results}
    if any(r["value"] for r in results):
        _indices_cache = resp
        _indices_ts = time.time()
    return resp


@router.get("/news")
def portfolio_news(uid: str = Depends(require_user)):
    """News articles relevant to the user's portfolio, with optional LLM summary."""
    ensure_user(uid)
    u = get_user(uid) or {}
    p = u.get("portfolio") or {}

    tickers = [s.get("ticker", "") for s in (p.get("stocks") or [])]
    if not tickers:
        tickers = ["NIFTY", "SENSEX"]

    articles: list[dict[str, Any]] = []
    try:
        from app.services.news import fetch_news_parallel_sync

        raw = fetch_news_parallel_sync(tickers[:5], [])
        for _key, arts in raw.items():
            for a in (arts if isinstance(arts, list) else []):
                url = a.get("url", "")
                if "example.com" in url:
                    continue
                articles.append({
                    "title": a.get("title", ""),
                    "description": a.get("description", ""),
                    "source": (a.get("source") or {}).get("name", ""),
                    "url": url,
                })
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for a in articles:
            if a["title"] not in seen:
                seen.add(a["title"])
                deduped.append(a)
        articles = deduped[:8]
    except Exception as exc:
        logger.warning("News fetch failed: %s", exc)

    llm_summary: str | None = None
    if articles:
        s = get_settings()
        if s.gemini_api_key or s.gcp_project_id:
            try:
                from app.services.gemini_vertex import _call_gemini, _ensure_genai, _init_vertex

                if not _ensure_genai():
                    _init_vertex()
                headlines = "; ".join(a["title"] for a in articles[:6])
                prompt = (
                    f"The user's portfolio includes these tickers: {', '.join(tickers[:5])}. "
                    f"Headlines: {headlines}. "
                    "Write a 3-sentence plain-English summary of what these news items "
                    "mean specifically for those holdings. Do not discuss assets they do not hold."
                )
                llm_summary = _call_gemini(prompt) or None
            except Exception as exc:
                logger.warning("News LLM summary failed: %s", exc)

    return {"articles": articles, "summary": llm_summary}


@router.get("/insights")
def portfolio_insights(uid: str = Depends(require_user)):
    """AI-driven portfolio insights: surplus detection, stop-loss alerts, hold/sell analysis."""
    ensure_user(uid)
    u = get_user(uid) or {}
    p = u.get("portfolio") or {}
    pol = u.get("policy") or {}
    fb = dict(p.get("lastPrices") or {})
    v = value_portfolio(p, fb)

    cash = float(v.get("cash", 0))
    expenses = float(pol.get("fixedExpenses", 0))
    buffer = float(pol.get("minBankBuffer", 0))
    threshold = expenses + buffer
    max_dd = float(pol.get("maxDrawdownPct", 15))

    insights: list[dict[str, Any]] = []
    breached_for_llm: list[dict[str, Any]] = []

    # 1. Surplus detection
    if threshold > 0 and cash > threshold:
        surplus = cash - threshold
        insights.append({
            "type": "surplus",
            "severity": "info",
            "title": "Investable surplus detected",
            "description": (
                f"Your cash balance (₹{cash:,.0f}) exceeds your minimum buffer "
                f"(₹{threshold:,.0f}) by ₹{surplus:,.0f}. Consider investing the surplus "
                f"in diversified index funds or blue-chip stocks for better returns."
            ),
            "amount": surplus,
        })

    # 2. Stop-loss / drawdown alerts per holding
    for eq in v.get("equity", []):
        pnl_pct = eq.get("pnlPct", 0)
        if pnl_pct < -max_dd:
            insights.append({
                "type": "stop_loss",
                "severity": "critical",
                "title": f"{eq.get('name', eq['ticker'])} breached stop-loss",
                "description": (
                    f"{eq.get('name', eq['ticker'])} ({eq['ticker']}) is down "
                    f"{abs(pnl_pct):.1f}% from your buy price, exceeding your "
                    f"{max_dd:.0f}% max drawdown limit. Consider exiting to protect capital."
                ),
                "ticker": eq["ticker"],
                "pnlPct": pnl_pct,
            })
            breached_for_llm.append({
                "id": f"eq:{eq['ticker']}",
                "type": "stock",
                "name": eq.get("name", eq["ticker"]),
                "ticker": eq["ticker"],
                "pnlPct": pnl_pct,
            })
        elif pnl_pct < -(max_dd * 0.7):
            insights.append({
                "type": "stop_loss_warning",
                "severity": "warning",
                "title": f"{eq.get('name', eq['ticker'])} nearing stop-loss",
                "description": (
                    f"{eq.get('name', eq['ticker'])} is down {abs(pnl_pct):.1f}%. "
                    f"Your max drawdown limit is {max_dd:.0f}%. Monitor closely."
                ),
                "ticker": eq["ticker"],
                "pnlPct": pnl_pct,
            })

    for mf in v.get("mutualFunds", []):
        pnl_pct = mf.get("pnlPct", 0)
        mf_label = mf.get("name") or mf.get("isin") or mf.get("amfiCode") or "Fund"
        mf_key = mf.get("isin") or mf.get("amfiCode") or ""
        if pnl_pct < -max_dd:
            insights.append({
                "type": "stop_loss",
                "severity": "critical",
                "title": f"MF {mf_label} breached stop-loss",
                "description": (
                    f"Mutual fund {mf_label} is down "
                    f"{abs(pnl_pct):.1f}% from your buy NAV. Review and consider switching."
                ),
                **({"amfiCode": mf.get("amfiCode")} if mf.get("amfiCode") else {}),
                **({"isin": mf.get("isin")} if mf.get("isin") else {}),
                "pnlPct": pnl_pct,
            })
            breached_for_llm.append({
                "id": f"mf:{mf_key}",
                "type": "mutual_fund",
                "name": mf.get("name", mf_label),
                "isin": mf.get("isin") or "",
                "amfiCode": mf.get("amfiCode") or "",
                "pnlPct": pnl_pct,
            })

    # 3. Overall portfolio health
    total_pnl_pct = float(v.get("approxReturnPct", 0))
    if total_pnl_pct < -5:
        insights.append({
            "type": "portfolio_health",
            "severity": "warning",
            "title": "Portfolio under stress",
            "description": (
                f"Your overall portfolio is down {abs(total_pnl_pct):.1f}%. "
                f"Consider rebalancing toward defensive sectors or increasing cash reserves."
            ),
        })

    # 4. Concentration check
    alloc = v.get("allocation", {})
    eq_pct = float(alloc.get("equity", 0)) * 100
    mf_pct = float(alloc.get("mutualFunds", 0)) * 100
    cash_pct = float(alloc.get("cash", 0)) * 100
    if eq_pct > 80:
        insights.append({
            "type": "rebalance",
            "severity": "info",
            "title": "High equity concentration",
            "description": (
                f"Equities make up {eq_pct:.0f}% of your portfolio. "
                f"Consider diversifying into mutual funds or fixed-income for stability."
            ),
        })
    if cash_pct > 60 and cash > 10000:
        insights.append({
            "type": "rebalance",
            "severity": "info",
            "title": "Excess cash",
            "description": (
                f"Cash is {cash_pct:.0f}% of your portfolio. "
                f"Idle cash loses value to inflation. Consider investing in a liquid fund "
                f"or systematic equity allocation."
            ),
        })

    # 5. Goal pacing
    nw = float(v.get("netWorth", 0))
    import datetime as _dt
    current_year = _dt.date.today().year
    for g in (pol.get("goals") or []):
        tgt = float(g.get("targetAmount", 0))
        yr = int(g.get("targetYear", current_year + 5))
        years_left = max(1, yr - current_year)
        progress = (nw / tgt * 100) if tgt > 0 else 0
        if progress < 100:
            monthly_needed = (tgt - nw) / (years_left * 12)
            if monthly_needed > 0:
                insights.append({
                    "type": "goal_pace",
                    "severity": "info",
                    "title": f"Goal: {g.get('name', 'Unnamed')}",
                    "description": (
                        f"You're at {progress:.0f}% of ₹{tgt:,.0f} (by {yr}). "
                        f"To reach it, invest ~₹{monthly_needed:,.0f}/month. "
                        f"SIP in a diversified index fund can help."
                    ),
                    "monthlyNeeded": monthly_needed,
                })

    # 6. Tax harvesting hint (if any holding has loss > 5%)
    losers = [
        eq for eq in v.get("equity", [])
        if eq.get("pnlPct", 0) < -5 and eq.get("buyDate")
    ]
    if losers:
        names = ", ".join(e.get("name", e["ticker"]) for e in losers[:3])
        insights.append({
            "type": "tax_harvest",
            "severity": "info",
            "title": "Tax-loss harvesting opportunity",
            "description": (
                f"{names} {'are' if len(losers) > 1 else 'is'} in loss. You can book the "
                f"loss to offset capital gains tax and reinvest in similar alternatives."
            ),
        })

    if breached_for_llm:
        from app.services.gemini_vertex import portfolio_breach_followup_notes

        risk = str(pol.get("riskProfile") or pol.get("risk_profile") or "moderate")
        for note in portfolio_breach_followup_notes(breached_for_llm, risk, max_dd):
            alt_txt = ""
            alts = note.get("alternatives") or []
            if alts:
                bits = []
                for a in alts[:3]:
                    if isinstance(a, dict):
                        nm = a.get("name", "")
                        rs = a.get("reason", "")
                        bits.append(f"{nm}" + (f": {rs}" if rs else ""))
                if bits:
                    alt_txt = " Alternatives to consider: " + "; ".join(bits) + "."
            insights.append({
                "type": "hold_review",
                "severity": note.get("severity", "info"),
                "title": note.get("title", "Review holding"),
                "description": (note.get("description") or "") + alt_txt,
                "ref": note.get("ref", ""),
                "stance": note.get("stance", ""),
                "alternatives": alts,
            })

    return {"insights": insights, "portfolioSummary": {
        "netWorth": v.get("netWorth"),
        "totalPnl": v.get("totalPnl"),
        "cash": cash,
        "buffer": threshold,
        "surplus": max(0, cash - threshold) if threshold > 0 else 0,
    }}
