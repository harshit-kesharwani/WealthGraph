"""Gemini LLM calls — uses Google AI (API key) or Vertex AI (GCP project)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_BACKOFF_BASE = 2.0
_genai_configured = False

# Substrings in Gemini / transport errors worth retrying (rate limits, overload, network).
_TRANSIENT_ERR_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "resource exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "too many requests",
    "timeout",
    "timed out",
    "deadline exceeded",
    "unavailable",
    "temporarily unavailable",
    "try again",
    "overloaded",
    "internal error",
    "econnreset",
    "connection reset",
    "broken pipe",
    "ssl",
    "handshake",
    "stream removed",
)


def _is_transient_gemini_error(exc: BaseException) -> bool:
    msg = f"{type(exc).__name__} {exc!s}".lower()
    return any(m in msg for m in _TRANSIENT_ERR_MARKERS)


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _extract_first_json_object(s: str) -> str | None:
    """If the model wrapped JSON in prose, pull the outermost {...} block."""
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _ensure_genai() -> bool:
    """Configure google.generativeai with API key. Returns True if available."""
    global _genai_configured
    s = get_settings()
    if s.gemini_api_key:
        if not _genai_configured:
            import google.generativeai as genai
            genai.configure(api_key=s.gemini_api_key)
            _genai_configured = True
        return True
    return False


def _init_vertex() -> None:
    s = get_settings()
    if not s.gcp_project_id:
        raise RuntimeError("GCP_PROJECT_ID not set")
    import vertexai
    vertexai.init(project=s.gcp_project_id, location=s.gcp_location)


def _call_gemini(
    prompt: str,
    *,
    response_mime_json: bool = False,
    retries: int = _MAX_RETRIES,
) -> str:
    """Call Gemini with retry. Prefers API key, falls back to Vertex AI."""
    s = get_settings()
    last_exc: BaseException | None = None

    for attempt in range(retries):
        try:
            if _ensure_genai():
                import google.generativeai as genai

                gen_cfg = (
                    genai.GenerationConfig(response_mime_type="application/json")
                    if response_mime_json
                    else None
                )
                model = genai.GenerativeModel(s.gemini_model)
                if gen_cfg is not None:
                    resp = model.generate_content(prompt, generation_config=gen_cfg)
                else:
                    resp = model.generate_content(prompt)
                try:
                    out = (resp.text or "").strip()
                except ValueError:
                    out = ""
                if not out:
                    raise RuntimeError("Gemini returned empty or blocked response")
                return out
            else:
                _init_vertex()
                from vertexai.generative_models import GenerativeModel, GenerationConfig

                v_cfg = (
                    GenerationConfig(response_mime_type="application/json")
                    if response_mime_json
                    else None
                )
                model = GenerativeModel(s.gemini_model)
                resp = (
                    model.generate_content(prompt, generation_config=v_cfg)
                    if v_cfg
                    else model.generate_content(prompt)
                )
                try:
                    out = (resp.text or "").strip()
                except ValueError:
                    out = ""
                if not out:
                    raise RuntimeError("Gemini returned empty or blocked response")
                return out
        except Exception as e:
            last_exc = e
            transient = _is_transient_gemini_error(e) or (
                isinstance(e, RuntimeError) and "empty or blocked" in str(e).lower()
            )
            if transient and attempt + 1 < retries:
                wait = _BACKOFF_BASE**attempt
                logger.info(
                    "Gemini transient error (%s), retry in %.1fs (%d/%d)",
                    type(e).__name__,
                    wait,
                    attempt + 1,
                    retries,
                )
                time.sleep(wait)
                continue
            raise
    raise last_exc  # type: ignore[misc]


def _parse_live_advisor_json(raw: str) -> dict[str, Any]:
    """Parse model output into dict with reply + structured."""
    cleaned = _strip_json_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        frag = _extract_first_json_object(cleaned)
        if frag:
            return json.loads(frag)
        raise


def _repair_live_advisor_json(bad_text: str) -> dict[str, Any]:
    """One short follow-up call to recover valid JSON (only on parse failure)."""
    snippet = bad_text.strip()[:10000]
    fix_prompt = f"""The text below was supposed to be a single JSON object with keys "reply" (string) and "structured" (object with "actions" and "fund_alternatives" arrays only).
Output ONLY valid JSON matching that shape. No markdown, no commentary.

---BEGIN---
{snippet}
---END---"""
    fixed = _call_gemini(fix_prompt, response_mime_json=True, retries=3)
    return _parse_live_advisor_json(fixed)


def portfolio_breach_followup_notes(
    breached: list[dict[str, Any]],
    risk_profile: str,
    max_drawdown_pct: float,
) -> list[dict[str, Any]]:
    """
    For holdings past max drawdown: hold vs exit/switch with named MF alternatives when relevant.
    Returns list of {ref, title, description, severity}.
    """
    s = get_settings()
    if not breached or (not s.gemini_api_key and not s.gcp_project_id):
        return []
    payload = json.dumps(breached, ensure_ascii=False)[:12000]
    prompt = f"""You are a SEBI-aware financial educator (not a registered advisor). The user holds ONLY the positions in this JSON. Each has breached their stated max drawdown of {max_drawdown_pct}%.

User risk profile: {risk_profile or "moderate"}.

For EACH position, respond with VALID JSON only (no markdown), shape:
{{"notes": [
  {{"ref": "same id as input", "stance": "hold" or "reduce" or "switch_mf", "confidence": "e.g. 85% HOLD or 100% SWITCH", "title": "short headline", "description": "2-4 sentences referencing THIS holding only by its full fund name", "severity": "info" or "warning",
   "alternatives": [{{"name": "full fund scheme name like 'Motilal Oswal Midcap Fund - Direct Plan - Growth'", "reason": "one line"}}]
  }}
]}}

Rules:
- NEVER use markdown formatting (**, ##, #, *) in any text fields. Write in plain English only.
- Always refer to funds by their FULL SCHEME NAME (e.g. "LIC MF Infrastructure Fund - Direct Plan-Growth"), NEVER by ISIN or amfiCode.
- Only discuss positions in the JSON. Never invent holdings.
- Include a confidence percentage for each stance (e.g. "90% HOLD" or "100% SWITCH") based on returns, Sharpe ratio, top holdings quality, and category performance.
- If stance is switch_mf for a mutual fund, alternatives MUST have 2-3 real widely known direct-plan growth or index funds in the same category.
- If fundamentals/time horizon could justify holding despite the paper loss, use stance hold and explain (horizon, SIP, fund quality) in description.
- Use plain English for an Indian retail investor.

BREACHING_HOLDINGS_JSON:
{payload}"""

    try:
        text = _call_gemini(prompt)
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        out = []
        for n in data.get("notes") or []:
            if not isinstance(n, dict):
                continue
            desc = str(n.get("description", "")).replace("**", "").replace("##", "")
            out.append(
                {
                    "ref": n.get("ref", ""),
                    "title": str(n.get("title", "Review holding")).replace("**", ""),
                    "description": desc,
                    "severity": n.get("severity", "info"),
                    "stance": n.get("stance", ""),
                    "confidence": n.get("confidence", ""),
                    "alternatives": n.get("alternatives") or [],
                }
            )
        return out
    except Exception as e:
        logger.warning("breach follow-up Gemini failed: %s", e)
        return []


def live_advisor_reply(
    messages: list[dict[str, str]],
    portfolio_snapshot: dict[str, Any],
    policy_snapshot: dict[str, Any],
    query_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Chat completion grounded in user's portfolio, real-time data, and market context."""
    s = get_settings()
    sys_ctx = json.dumps(
        {"portfolio": portfolio_snapshot, "policy": policy_snapshot},
        ensure_ascii=False,
    )[:14000]
    hist = json.dumps(messages[-16:], ensure_ascii=False)[:8000]

    real_time_block = ""
    if query_context and query_context.get("queried_stocks"):
        real_time_block = f"""
REAL-TIME MARKET DATA (fetched just now via yfinance — use these numbers in your analysis):
{json.dumps(query_context["queried_stocks"], ensure_ascii=False)[:6000]}

RELATED NEWS:
{json.dumps(query_context.get("related_news", []), ensure_ascii=False)[:3000]}
"""

    prompt = f"""You are an expert Indian financial advisor with deep knowledge of stock markets, mutual funds, and portfolio management. You think like a seasoned fund manager who reads candlestick charts, analyses fundamentals, and tracks market sentiment daily. You are NOT a SEBI-registered investment adviser — always include this disclaimer.

PORTFOLIO CONTEXT (what the user currently owns):
{sys_ctx}
{real_time_block}
CONVERSATION:
{hist}

Respond with VALID JSON only, no markdown:
{{"reply": "main answer in plain English", "structured": {{"actions": [{{"what": "", "why": ""}}], "fund_alternatives": [{{"name": "full scheme name like 'Mirae Asset Large Cap Fund - Direct Plan - Growth'", "reason": ""}}]}}}}

CRITICAL FORMATTING RULES:
- NEVER use markdown formatting (**, ##, #, *, etc.) in the reply text. Write in plain English only.
- When referring to mutual funds, ALWAYS use the full scheme name. NEVER use amfiCode, ISIN, or internal codes.

WHEN THE USER ASKS ABOUT A SPECIFIC STOCK OR FUND (whether they hold it or not):
- You MUST give a concrete, data-driven analysis. NEVER give generic textbook advice like "look at revenue growth and management quality".
- Use the REAL-TIME MARKET DATA provided above. Quote actual numbers: current price, PE ratio, 52-week high/low, market cap, recent trend, volume, debt-to-equity, ROE, profit margins.
- Give a clear BUY / HOLD / AVOID verdict with a confidence percentage (e.g. "75% BUY" or "60% AVOID").
- Explain your reasoning in 3-5 specific points referencing the actual data. For example: "Trading at Rs 345, which is 18% below its 52-week high of Rs 421. PE of 22x is reasonable for IT sector. Monthly trend shows 8% decline, suggesting possible accumulation zone."
- Factor in: valuation (PE, PB), momentum (recent trend, volume), fundamentals (ROE, margins, debt), sector outlook, and news sentiment.
- If RELATED NEWS is available, incorporate it into your analysis.
- Mention key risks and what price levels to watch (support/resistance if inferable from 52W data).

PORTFOLIO ANALYSIS RULES:
- When discussing the user's holdings, reference them by full fund/stock name and amounts.
- For EACH mutual fund holding, provide a confidence-based verdict: e.g. "90% HOLD" or "100% SWITCH".
- If mfAnalysis has top_holdings data, analyze the quality of the underlying stocks.
- If they ask about switching, name 2-3 specific alternative schemes by FULL FUND NAME.

ALWAYS end with: "Disclaimer: I am not a SEBI-registered investment advisor. This is for educational and informational purposes only."

Keep reply specific and data-rich. Avoid vague or generic statements."""

    if not s.gemini_api_key and not s.gcp_project_id:
        return {
            "reply": "AI is not configured. Add GEMINI_API_KEY to enable Live Advisor.",
            "structured": {"actions": [], "fund_alternatives": []},
        }

    try:
        try:
            text = _call_gemini(prompt, response_mime_json=True)
        except Exception as e:
            logger.info("live_advisor JSON mime mode unavailable, using text mode: %s", e)
            text = _call_gemini(prompt, response_mime_json=False)
        try:
            data = _parse_live_advisor_json(text)
        except json.JSONDecodeError as je:
            logger.warning("live_advisor JSON parse failed, repair pass: %s", je)
            data = _repair_live_advisor_json(text)
        reply = str(data.get("reply", "")).strip() or "I could not generate a reply."
        reply = reply.replace("**", "").replace("##", "").replace("# ", "")
        return {
            "reply": reply,
            "structured": data.get("structured") or {},
        }
    except Exception as e:
        logger.warning("live_advisor_reply failed: %s", e)
        return {
            "reply": "I ran into a temporary issue. Please try again in a moment.",
            "structured": {"actions": [], "fund_alternatives": []},
        }


def synthesize_intelligence(
    articles_bundle: dict[str, Any],
    tickers: list[str],
    retrieved_passages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """RAG-grounded synthesis: use retrieved passages with chunk_id citations."""
    s = get_settings()
    passages = retrieved_passages or []
    rag_block = json.dumps(
        [{"chunk_id": p.get("chunk_id"), "text": p.get("text"), "title": p.get("title")} for p in passages],
        ensure_ascii=False,
    )[:10000]
    prompt = f"""You are a financial analyst. User holds: {tickers}.

RETRIEVED_PASSAGES (RAG — base answers ONLY on these; cite chunk_id in why_it_matters when used):
{rag_block}

Optional broader context (may contradict passages; prefer passages): {json.dumps(articles_bundle)[:6000]}

Respond with VALID JSON only, no markdown:
{{"top_three": [{{"title": "", "why_it_matters": "", "source_hint": "", "cited_chunk_ids": []}}], "sentiment": "Bullish" or "Bearish", "one_line_summary": ""}}
Max 3 items in top_three. cited_chunk_ids must list chunk_ids you relied on."""

    if not s.gemini_api_key and not s.gcp_project_id:
        return {
            "top_three": [
                {
                    "title": "Offline mode",
                    "why_it_matters": "Set GEMINI_API_KEY or GCP_PROJECT_ID for live synthesis.",
                    "source_hint": "config",
                    "cited_chunk_ids": [p.get("chunk_id") for p in passages[:1]],
                }
            ],
            "sentiment": "Bearish",
            "one_line_summary": "AI not configured; using stub intelligence.",
        }

    try:
        text = _call_gemini(prompt)
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception as e:
        logger.exception("Gemini intelligence failed: %s", e)
        return {
            "top_three": [],
            "sentiment": "Neutral",
            "one_line_summary": "Market analysis temporarily unavailable. Your portfolio rules still apply.",
        }


def gemini_tts(text: str, voice: str = "Kore") -> bytes | None:
    """Convert text to speech using Gemini 2.5 Flash TTS. Returns raw PCM bytes or None."""
    s = get_settings()
    if not s.gemini_api_key:
        return None
    try:
        from google import genai as genai_new
        from google.genai import types as genai_types

        client = genai_new.Client(api_key=s.gemini_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=f"Say in a warm, professional, knowledgeable tone like a human financial advisor:\n{text[:4000]}",
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            ),
        )
        data = response.candidates[0].content.parts[0].inline_data.data
        return data if isinstance(data, bytes) else None
    except Exception as e:
        logger.warning("Gemini TTS failed: %s", e)
        return None


def build_rationale_bullets(
    context: str,
    action: str,
) -> list[str]:
    """Three bullet rationale for a proposed action."""
    s = get_settings()
    prompt = f"""{context}
Proposed action: {action}
Return exactly 3 short bullet points (one line each), plain text, separated by newlines starting with "- "."""

    if not s.gemini_api_key and not s.gcp_project_id:
        return [
            f"Policy-aligned suggestion: {action}",
            "Risk checks applied per user max drawdown.",
            "Surplus or overlap logic triggered this recommendation.",
        ]

    try:
        text = _call_gemini(prompt)
        bullets = [ln.strip()[2:].strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
        while len(bullets) < 3:
            bullets.append("Aligned with stated goals and risk guardrails.")
        return bullets[:3]
    except Exception as e:
        logger.warning("Gemini rationale fallback: %s", e)
        return [
            f"Policy-aligned suggestion: {action.split(' ')[0].capitalize()} position.",
            "Risk checks applied per your drawdown and buffer rules.",
            "Aligned with stated goals and risk guardrails.",
        ]
