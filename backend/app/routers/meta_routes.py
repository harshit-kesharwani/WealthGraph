"""GenAI interoperability: MCP-style tool manifest + practice notes (no stdio MCP on Cloud Run)."""

from fastapi import APIRouter

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/mcp-tools")
def mcp_tool_manifest():
    """
    JSON list aligned with MCP tool discovery shape so desktop/IDE MCP bridges
    can wrap these as HTTP tools (Bearer = Firebase ID token).
    """
    return {
        "protocol_note": "Native MCP uses stdio/SSE; Cloud Run exposes REST. Map each tool to authenticated HTTP below.",
        "base_path": "",
        "tools": [
            {
                "name": "wealthgraph_get_me",
                "description": "Current user profile, policy snapshot, portfolio snapshot.",
                "method": "GET",
                "path": "/me",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "wealthgraph_get_dashboard_summary",
                "description": "Net worth, allocation, goals, indices, and cached prices.",
                "method": "GET",
                "path": "/dashboard/summary",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "wealthgraph_live_advisor_chat",
                "description": "Live AI Advisor: portfolio-grounded chat (JSON messages + structured alternatives).",
                "method": "POST",
                "path": "/advisor/live/chat",
                "inputSchema": {
                    "type": "object",
                    "required": ["messages"],
                    "properties": {
                        "messages": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["role", "content"],
                                "properties": {
                                    "role": {"type": "string", "enum": ["user", "assistant"]},
                                    "content": {"type": "string"},
                                },
                            },
                        }
                    },
                },
            },
            {
                "name": "wealthgraph_simulate_trade",
                "description": "Mock buy execution updating portfolio.",
                "method": "POST",
                "path": "/trades/simulate",
                "inputSchema": {
                    "type": "object",
                    "required": ["symbol", "qty", "price"],
                    "properties": {
                        "symbol": {"type": "string"},
                        "asset_type": {"type": "string", "enum": ["stock", "mutual_fund"]},
                        "side": {"type": "string", "enum": ["buy", "sell"]},
                        "qty": {"type": "number"},
                        "price": {"type": "number"},
                    },
                },
            },
        ],
    }


@router.get("/genai-practices")
def genai_practices():
    return {
        "truth_summary": (
            "Coordinator = FastAPI + one Gemini reasoning step per call; sub-steps are deterministic services "
            "(not separate LLM agents). RAG = structured API/DB retrieval then generate (no vector index). "
            "MCP = HTTP tool manifest only (no stdio server; no bundled calendar/tasks MCP). "
            "External agents may call REST with Bearer tokens; not formal Google A2A protocol."
        ),
        "agent_coordination": {
            "level": "partial",
            "description": (
                "Primary reasoning: Gemini. Sub-capabilities orchestrated in code: valuation, mfdata.in, "
                "yfinance, NewsAPI, drawdown rules — then context passed to the model. Not multi-LLM sub-agents."
            ),
        },
        "rag": {
            "level": "partial",
            "implemented": True,
            "description": (
                "Production: retrieve from Firestore, AMFI, mfdata.in, yfinance, NewsAPI (optional), PDF text; "
                "inject into Gemini prompts before generation."
            ),
            "embedding_store": False,
            "passage_rag_helper": "synthesize_intelligence() exists but is not called from any router.",
        },
        "mcp": {
            "level": "partial",
            "implemented": True,
            "description": (
                "GET /meta/mcp-tools: MCP-shaped tool manifest mapping to WealthGraph REST endpoints + Bearer auth. "
                "No stdio/SSE MCP server in-container. Third-party tools (calendar, tasks, notes) are out of scope "
                "but the same manifest pattern can register more tools."
            ),
            "discovery_path": "/meta/mcp-tools",
        },
        "a2a": {
            "level": "partial",
            "description": (
                "Stateless HTTPS/JSON APIs with Firebase Bearer tokens — suitable for external orchestrators. "
                "Not an implementation of the formal Agent2Agent (A2A) protocol."
            ),
            "typical_entrypoints": [
                "POST /advisor/live/chat",
                "GET /dashboard/summary",
                "GET /me",
            ],
        },
        "live_advisor": {
            "implemented": True,
            "description": "POST /advisor/live/chat: Gemini with Firestore portfolio + policy; optional yfinance + news for ticker questions; TTS at POST /advisor/tts.",
        },
        "documentation": "docs/GENAI_ARCHITECTURE.md",
        "safety": [
            "Mock trade execution only — no broker integration",
            "Structured JSON prompts for advisor replies",
            "Firestore user scoping; no broker credentials stored",
        ],
    }
