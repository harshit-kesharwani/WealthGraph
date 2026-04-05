/**
 * Single source of truth for deployed WealthGraph (Cloud Run + Firebase Web).
 * Public Firebase keys are safe to ship in the client. Override with NEXT_PUBLIC_* only if you fork.
 */
export const CLOUD_API_BASE_URL =
  "https://wealthgraph-api-102631486332.us-central1.run.app";

export const CLOUD_WEB_APP_URL =
  "https://wealthgraph-web-102631486332.us-central1.run.app";

/** Hostname substring for the static web service (same-origin /api proxy). */
export const CLOUD_WEB_HOST_MARKER = "wealthgraph-web";

export const CLOUD_FIREBASE_CONFIG = {
  apiKey: "AIzaSyAxqvMNhbBdjaefQzYZfzBAgkbYD2J8Wfs",
  authDomain: "genaicohert1firebase.firebaseapp.com",
  projectId: "genaicohert1firebase",
  storageBucket: "genaicohert1firebase.firebasestorage.app",
  messagingSenderId: "796955603320",
  appId: "1:796955603320:web:4b47e45e39f7ed0baf988d",
  measurementId: "G-F6NXS978MZ",
} as const;

export function isCloudWebHost(hostname: string): boolean {
  return hostname.includes(CLOUD_WEB_HOST_MARKER);
}
