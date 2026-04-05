#!/usr/bin/env python3
"""
Hit deployed Cloud Run API + web /api proxy. No local services required.

Public checks always run.

Authenticated checks run only if you set (do not commit passwords):
  set WEALTHGRAPH_TEST_EMAIL=...
  set WEALTHGRAPH_TEST_PASSWORD=...

Uses the public Firebase Web API key (same as the browser client).
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

API = "https://wealthgraph-api-102631486332.us-central1.run.app"
WEB = "https://wealthgraph-web-102631486332.us-central1.run.app"
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY", "")
WEB_ORIGIN = "https://wealthgraph-web-102631486332.us-central1.run.app"


def _get(url: str, headers: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
        return r.status, r.read().decode()


def _post_json(url: str, body: dict, headers: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode()
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
        return r.status, r.read().decode()


def _options(url: str, hdrs: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=hdrs, method="OPTIONS")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return r.status, dict(r.headers)


def main() -> int:
    failed = 0

    def ok(name: str) -> None:
        print(f"OK  {name}")

    def fail(name: str, detail: str) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL {name}: {detail}")

    # --- API direct ---
    for path, label in [
        ("/health", "GET /health"),
        ("/", "GET / (root)"),
        ("/meta/genai-practices", "GET /meta/genai-practices"),
        ("/openapi.json", "GET /openapi.json"),
    ]:
        try:
            code, body = _get(f"{API}{path}")
            if code != 200:
                fail(label, f"status {code}")
            elif path == "/health" and '"ok"' not in body and "ok" not in body:
                fail(label, body[:200])
            else:
                ok(label)
        except urllib.error.HTTPError as e:
            fail(label, f"HTTP {e.code}")
        except Exception as e:
            fail(label, str(e))

    # CORS preflight (browser-style)
    try:
        st, hdrs = _options(
            f"{API}/me",
            {
                "Origin": WEB_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        aco = hdrs.get("Access-Control-Allow-Origin") or hdrs.get("access-control-allow-origin")
        if st != 200 or aco != WEB_ORIGIN:
            fail("OPTIONS CORS /me", f"status={st} ACAO={aco!r}")
        else:
            ok("OPTIONS CORS /me (web origin)")
    except Exception as e:
        fail("OPTIONS CORS /me", str(e))

    # --- Web nginx /api proxy ---
    try:
        code, body = _get(f"{WEB}/api/health")
        if code == 200 and "ok" in body:
            ok("GET web /api/health (proxy)")
        else:
            fail("GET web /api/health", f"{code} {body[:120]}")
    except Exception as e:
        fail("GET web /api/health", str(e))

    # --- Optional: Firebase sign-in + authenticated API ---
    email = os.environ.get("WEALTHGRAPH_TEST_EMAIL", "").strip()
    password = os.environ.get("WEALTHGRAPH_TEST_PASSWORD", "").strip()
    if not email or not password:
        print("SKIP authenticated routes (set WEALTHGRAPH_TEST_EMAIL + WEALTHGRAPH_TEST_PASSWORD)")
        return 1 if failed else 0

    tok: str | None = None
    try:
        url = (
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            f"?key={FIREBASE_WEB_API_KEY}"
        )
        sc, raw = _post_json(
            url,
            {"email": email, "password": password, "returnSecureToken": True},
        )
        if sc != 200:
            fail("Firebase signIn", raw[:300])
        else:
            tok = json.loads(raw).get("idToken")
            if not tok:
                fail("Firebase signIn", "no idToken")
            else:
                ok("Firebase signInWithPassword")
    except Exception as e:
        fail("Firebase signIn", str(e))

    if not tok:
        return 1 if failed else 0

    auth_h = {"Authorization": f"Bearer {tok}"}
    for path, label in [
        ("/me", "GET /me"),
        ("/policy", "GET /policy"),
        ("/portfolio", "GET /portfolio"),
        ("/dashboard/summary", "GET /dashboard/summary"),
        ("/dashboard/indices", "GET /dashboard/indices"),
        ("/dashboard/news", "GET /dashboard/news"),
        ("/dashboard/insights", "GET /dashboard/insights"),
        ("/portfolio/search?q=reli&asset_type=stock", "GET /portfolio/search (stock)"),
        ("/portfolio/search?q=axis&asset_type=mutual_fund", "GET /portfolio/search (MF)"),
        ("/portfolio/validate?symbol=TCS&asset_type=stock", "GET /portfolio/validate (stock)"),
        ("/inbox/pending", "GET /inbox/pending"),
    ]:
        try:
            code, body = _get(f"{API}{path}", auth_h)
            if code != 200:
                fail(label, f"HTTP {code} {body[:200]}")
            else:
                ok(label)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            fail(label, f"HTTP {e.code} {body[:200]}")
        except Exception as e:
            fail(label, str(e))

    # Test POST /advisor/live/chat
    try:
        code, body = _post_json(
            f"{API}/advisor/live/chat",
            {"messages": [{"role": "user", "content": "Summarize my portfolio in one sentence."}]},
            auth_h,
        )
        if code != 200:
            fail("POST /advisor/live/chat", f"HTTP {code} {body[:200]}")
        else:
            ok("POST /advisor/live/chat")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        fail("POST /advisor/live/chat", f"HTTP {e.code} {body[:200]}")
    except Exception as e:
        fail("POST /advisor/live/chat", str(e))

    # Test web /api proxy with auth
    for path, label in [
        ("/api/dashboard/summary", "GET web /api/dashboard/summary (proxy)"),
        ("/api/dashboard/indices", "GET web /api/dashboard/indices (proxy)"),
    ]:
        try:
            code, body = _get(f"{WEB}{path}", auth_h)
            if code != 200:
                fail(label, f"HTTP {code} {body[:200]}")
            else:
                ok(label)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            fail(label, f"HTTP {e.code} {body[:200]}")
        except Exception as e:
            fail(label, str(e))

    # Test web pages load
    for path, label in [
        ("/", "web / (landing)"),
        ("/login", "web /login"),
        ("/dashboard", "web /dashboard"),
        ("/portfolio", "web /portfolio"),
        ("/policy", "web /policy"),
        ("/advisor", "web /advisor"),
        ("/live-advisor", "web /live-advisor"),
        ("/demo", "web /demo"),
    ]:
        try:
            code, body = _get(f"{WEB}{path}")
            if code != 200:
                fail(label, f"HTTP {code}")
            elif "<html" not in body.lower() and "<!doctype" not in body.lower():
                fail(label, "not HTML")
            else:
                ok(label)
        except Exception as e:
            fail(label, str(e))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
