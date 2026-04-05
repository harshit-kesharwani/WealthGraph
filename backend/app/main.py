import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth_firebase import init_firebase
from app.config import cors_list, get_settings
from app.routers import (
    advisor_routes,
    dashboard_routes,
    demo_routes,
    health,
    inbox_routes,
    meta_routes,
    policy_routes,
    portfolio_routes,
    trades_routes,
    user_routes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WealthGraph API", version="0.1.0")


@app.get("/", include_in_schema=False)
def root():
    """API root — no HTML UI; browsers show JSON here."""
    return {
        "service": "WealthGraph API",
        "message": "This URL is the REST API only. Open the WealthGraph web app (Next.js) for the UI — e.g. the Cloud Run `wealthgraph-web` service or local dev.",
        "health": "/health",
        "openapi_docs": "/docs",
        "openapi_json": "/openapi.json",
        "meta": "/meta/genai-practices",
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(meta_routes.router)
app.include_router(user_routes.router)
app.include_router(policy_routes.router)
app.include_router(portfolio_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(advisor_routes.router)
app.include_router(trades_routes.router)
app.include_router(inbox_routes.router)
app.include_router(demo_routes.router)


@app.on_event("startup")
def startup():
    try:
        init_firebase()
    except Exception as e:
        logger.warning("Firebase init deferred or failed (ok for local without creds): %s", e)
