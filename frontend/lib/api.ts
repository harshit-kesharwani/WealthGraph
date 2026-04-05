import { getFirebaseAuth } from "./firebase";
import {
  CLOUD_API_BASE_URL,
  CLOUD_WEB_APP_URL,
  isCloudWebHost,
} from "./cloud-config";

/**
 * API base: same-origin /api on the deployed web host (nginx proxy), else direct Cloud Run API.
 * No localhost defaults — all paths target cloud unless NEXT_PUBLIC_API_URL overrides (forks).
 */
function resolveApiBase(): string {
  const override = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/$/, "") || "";
  if (override) return override;

  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (isCloudWebHost(host)) {
      return `${window.location.origin}/api`.replace(/\/$/, "");
    }
    return CLOUD_API_BASE_URL;
  }

  return CLOUD_API_BASE_URL;
}

function buildHeaders(
  token: string | null,
  init?: RequestInit
): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init?.headers || {}),
  };
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function fetchWithAuth(
  path: string,
  token: string | null,
  init?: RequestInit
): Promise<Response> {
  const root = resolveApiBase();
  const url = `${root}${path.startsWith("/") ? path : `/${path}`}`;
  try {
    return await fetch(url, {
      ...init,
      headers: buildHeaders(token, init),
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (
      msg === "Failed to fetch" ||
      (e instanceof TypeError && msg.toLowerCase().includes("fetch"))
    ) {
      throw new Error(
        `Could not reach the API at ${url.split("?")[0]}. Use the deployed app at ${CLOUD_WEB_APP_URL} (same-origin /api proxy) or confirm Cloud Run API is up.`
      );
    }
    throw e;
  }
}

/**
 * Calls the API with a Firebase ID token. If the token expired (401), refreshes
 * once via Firebase and retries — stale tokens in React state are common after ~1h.
 */
export async function apiFetch<T>(
  path: string,
  token: string | null,
  init?: RequestInit
): Promise<T> {
  let res = await fetchWithAuth(path, token, init);

  if (res.status === 401 && typeof window !== "undefined") {
    const u = getFirebaseAuth().currentUser;
    if (u) {
      const fresh = await u.getIdToken(true);
      if (fresh) {
        res = await fetchWithAuth(path, fresh, init);
      }
    }
  }

  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
