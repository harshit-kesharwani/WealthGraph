import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.auth_firebase import require_user
from app.firestore_service import ensure_user, get_user, set_portfolio
from app.models import CASPayload, PortfolioUpdate
from app.services.amfi_nav import lookup_isin_meta
from app.services.valuation import fetch_equity_price, fetch_mf_nav, value_portfolio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
def get_portfolio(uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    return u.get("portfolio", {})


_mf_codes_cache: dict[str, str] | None = None


def _mf_codes() -> dict[str, str]:
    global _mf_codes_cache
    if _mf_codes_cache is None:
        from mftool import Mftool
        raw = Mftool().get_scheme_codes()
        _mf_codes_cache = {k: v for k, v in raw.items() if k != "Scheme Code"}
    return _mf_codes_cache


@router.get("/search")
def search_assets(
    q: str = Query(..., min_length=2),
    asset_type: str = Query("stock"),
    limit: int = Query(10, ge=1, le=30),
):
    """Search stocks by name/ticker or mutual funds by name. No auth required for fast UX."""
    query = q.strip().upper()
    if asset_type == "mutual_fund":
        query_lower = q.strip().lower()
        codes = _mf_codes()
        results = []
        for code, name in codes.items():
            if query_lower in name.lower() or query_lower in code:
                results.append({"code": code, "name": name})
                if len(results) >= limit:
                    break
        return {"results": results}

    from app.data.nse_stocks import NSE_STOCKS

    results = []
    for ticker, name in NSE_STOCKS.items():
        if query in ticker.upper() or query in name.upper():
            results.append({"ticker": ticker, "name": name})
            if len(results) >= limit:
                break
    return {"results": results}


@router.get("/validate")
def validate_ticker(
    symbol: str = Query(..., min_length=1),
    asset_type: str = Query("stock"),
):
    """Check whether a stock ticker or MF scheme code is valid and return its name + live price."""
    symbol = symbol.strip()
    if asset_type == "mutual_fund":
        sym_u = symbol.strip().upper()
        if sym_u.startswith("IN") and len(sym_u) == 12:
            from app.services.amfi_nav import fetch_mf_nav_by_isin

            nav_val, nav_date, ok = fetch_mf_nav_by_isin(sym_u)
            meta = lookup_isin_meta(sym_u)
            name = (meta or {}).get("scheme_name") or sym_u
            if nav_val is not None:
                return {
                    "valid": True,
                    "isin": sym_u,
                    "name": name,
                    "currentPrice": nav_val,
                    "navDate": nav_date,
                    "amfiCode": (meta or {}).get("scheme_code"),
                }
            return {"valid": False, "name": None, "currentPrice": None, "error": f"ISIN '{sym_u}' not found in AMFI NAV data."}

        from mftool import Mftool

        mf = Mftool()
        try:
            q = mf.get_scheme_quote(symbol)
            if q and q.get("scheme_name"):
                nav_val = None
                raw = q.get("nav")
                if raw:
                    try:
                        nav_val = float(str(raw).replace(",", ""))
                    except ValueError:
                        pass
                if nav_val is None:
                    nav_val, _ = fetch_mf_nav(symbol)
                return {"valid": True, "name": q["scheme_name"], "currentPrice": nav_val}
        except Exception:
            pass
        return {"valid": False, "name": None, "currentPrice": None, "error": f"Scheme '{symbol}' not found on AMFI."}

    import re
    import yfinance as yf
    from app.services.valuation import _normalize_equity_ticker

    yf_sym = _normalize_equity_ticker(symbol)
    name: str | None = None
    price: float | None = None

    try:
        tk = yf.Ticker(yf_sym)
        info = tk.info or {}
        name = info.get("shortName") or info.get("longName") or None
        fast = info.get("regularMarketPrice") or info.get("currentPrice")
        if fast:
            price = float(fast)
        if price is None:
            hist = tk.history(period="5d")
            if hist is not None and not hist.empty:
                price = float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.debug("yf.Ticker %s: %s", yf_sym, e)

    if price is None:
        p2, ok = fetch_equity_price(symbol)
        if ok and p2:
            price = p2

    if price is not None:
        return {"valid": True, "name": name or yf_sym, "currentPrice": price}
    if name:
        return {"valid": True, "name": name, "currentPrice": None}

    clean = re.sub(r"\.(NS|BO)$", "", yf_sym, flags=re.IGNORECASE)
    if re.fullmatch(r"[A-Z][A-Z0-9&\-]{1,19}", clean):
        return {
            "valid": True,
            "name": f"{clean} (NSE)",
            "currentPrice": None,
            "note": "Live price unavailable; ticker format is valid for NSE/BSE.",
        }

    return {"valid": False, "name": None, "currentPrice": None, "error": f"Ticker '{symbol}' not recognised."}


@router.put("")
def put_portfolio(body: PortfolioUpdate, uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    p = dict(u.get("portfolio") or {})
    if body.cash is not None:
        p["cash"] = body.cash
    if body.stocks is not None:
        p["stocks"] = [
            {
                "ticker": s.ticker,
                "qty": s.qty,
                "buyPrice": s.buy_price,
                **({"buyDate": s.buy_date} if s.buy_date else {}),
            }
            for s in body.stocks
        ]
    if body.mutual_funds is not None:
        rows = []
        for m in body.mutual_funds:
            code = (m.amfi_code or "").strip()
            isin = m.isin
            meta = None
            if isin:
                meta = lookup_isin_meta(isin)
                if not code and meta and meta.get("scheme_code"):
                    code = str(meta["scheme_code"])
            row: dict = {
                "units": m.units,
                "buyNav": m.buy_nav,
                **({"buyDate": m.buy_date} if m.buy_date else {}),
            }
            if isin:
                row["isin"] = isin
            if code:
                row["amfiCode"] = code
            if meta and meta.get("scheme_name"):
                row["name"] = meta["scheme_name"]
            rows.append(row)
        p["mutualFunds"] = rows
    set_portfolio(uid, p)
    return p


@router.post("/cas")
def post_cas(body: CASPayload, uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    p = dict(u.get("portfolio") or {})
    p["cash"] = float(body.cash)
    p["stocks"] = [
        {"ticker": s.ticker, "qty": s.qty, "buyPrice": s.buy_price} for s in body.stocks
    ]
    p["mutualFunds"] = []
    for m in body.mutual_funds:
        code = (m.amfi_code or "").strip()
        isin = m.isin
        meta = None
        if isin:
            meta = lookup_isin_meta(isin)
            if not code and meta and meta.get("scheme_code"):
                code = str(meta["scheme_code"])
        r: dict = {"units": m.units, "buyNav": m.buy_nav}
        if isin:
            r["isin"] = isin
        if code:
            r["amfiCode"] = code
        if meta and meta.get("scheme_name"):
            r["name"] = meta["scheme_name"]
        p["mutualFunds"].append(r)
    if "priceMultiplier" not in p:
        p["priceMultiplier"] = 1.0
    if "lastPrices" not in p:
        p["lastPrices"] = {}
    set_portfolio(uid, p)
    return p


@router.get("/valuation")
def get_valuation(uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    p = u.get("portfolio") or {}
    fb = dict(p.get("lastPrices") or {})
    result = value_portfolio(p, fb)
    new_p = {**p, "lastPrices": result.pop("lastPrices", {})}
    set_portfolio(uid, new_p)
    return result


def _extract_text_from_pdf(contents: bytes) -> str:
    from PyPDF2 import PdfReader
    import io

    reader = PdfReader(io.BytesIO(contents))
    text_parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text_parts.append(t)
    return "\n".join(text_parts)


@router.post("/cas-pdf")
async def upload_cas_pdf(
    file: UploadFile = File(...),
    uid: str = Depends(require_user),
):
    """Parse a CAS PDF statement using Gemini and import mutual fund holdings."""
    ensure_user(uid)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "PDF too large (max 10 MB).")

    pdf_text = _extract_text_from_pdf(contents)
    if not pdf_text.strip():
        raise HTTPException(400, "Could not extract text from PDF. The file may be image-based.")

    prompt = f"""You are a financial document parser. Extract mutual fund holdings from this CAS (Consolidated Account Statement) text.

For each mutual fund holding, extract:
- scheme_name: full name of the mutual fund scheme
- amfi_code: the AMFI scheme code (numeric, from the scheme name prefix like "102", "127FMGDG", etc.). If the ISIN is available, note it. Look for numeric scheme codes.
- folio_no: the folio number
- isin: ISIN code if available
- units: closing unit balance (number)
- cost_value: cost value in INR (number)
- nav: latest NAV/price per unit (number)
- nav_date: NAV date
- market_value: current market value in INR (number)

Return ONLY valid JSON, no markdown:
{{"holdings": [{{"scheme_name": "", "amfi_code": "", "folio_no": "", "isin": "", "units": 0, "cost_value": 0, "nav": 0, "nav_date": "", "market_value": 0}}], "total_cost": 0, "total_market_value": 0}}

CAS TEXT:
{pdf_text[:15000]}"""

    from app.services.gemini_vertex import _call_gemini, _ensure_genai, _init_vertex
    import re

    if not _ensure_genai():
        _init_vertex()

    try:
        raw = _call_gemini(prompt)
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
    except Exception as e:
        logger.exception("CAS PDF parsing failed: %s", e)
        raise HTTPException(500, f"Failed to parse CAS PDF: {e}")

    holdings = parsed.get("holdings", [])

    mf_entries = []
    for h in holdings:
        raw_isin = str(h.get("isin", "")).strip().upper()
        code = str(h.get("amfi_code", "")).strip()
        units_val = float(h.get("units", 0))
        cost = float(h.get("cost_value", 0))
        nav_val = float(h.get("nav", 0))
        buy_nav = (cost / units_val) if units_val > 0 else nav_val

        if units_val <= 0:
            continue
        if raw_isin.startswith("IN") and len(raw_isin) == 12:
            isin = raw_isin
        else:
            isin = ""
        if isin and not code:
            meta = lookup_isin_meta(isin)
            if meta and meta.get("scheme_code"):
                code = str(meta["scheme_code"])
        if not isin and not code:
            continue

        mf_entries.append({
            **({"amfiCode": code} if code else {}),
            **({"isin": isin} if isin else {}),
            "name": h.get("scheme_name", ""),
            "units": round(units_val, 3),
            "buyNav": round(buy_nav, 4),
            "buyDate": h.get("nav_date"),
            "folio": h.get("folio_no"),
            "marketValue": float(h.get("market_value", 0)),
        })

    u = get_user(uid) or {}
    p = dict(u.get("portfolio") or {})
    existing_mfs = p.get("mutualFunds") or []

    def _mf_key(m: dict) -> str:
        i = (m.get("isin") or "").strip().upper()
        if i.startswith("IN") and len(i) == 12:
            return f"isin:{i}"
        return f"code:{m.get('amfiCode', '')}"

    existing_keys = {_mf_key(m) for m in existing_mfs}
    new_mfs = [m for m in mf_entries if _mf_key(m) not in existing_keys]

    merged = existing_mfs + [
        {
            **({"amfiCode": m["amfiCode"]} if m.get("amfiCode") else {}),
            **({"isin": m["isin"]} if m.get("isin") else {}),
            "name": m.get("name"),
            "units": m["units"],
            "buyNav": m["buyNav"],
            **({"buyDate": m["buyDate"]} if m.get("buyDate") else {}),
        }
        for m in new_mfs
    ]

    p["mutualFunds"] = merged
    set_portfolio(uid, p)

    return {
        "parsed": mf_entries,
        "imported": len(new_mfs),
        "skipped_existing": len(mf_entries) - len(new_mfs),
        "total_cost": parsed.get("total_cost"),
        "total_market_value": parsed.get("total_market_value"),
    }
