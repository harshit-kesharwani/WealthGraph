import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import { CLOUD_FIREBASE_CONFIG } from "./cloud-config";

const cfg = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || CLOUD_FIREBASE_CONFIG.apiKey,
  authDomain:
    process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ||
    CLOUD_FIREBASE_CONFIG.authDomain,
  projectId:
    process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ||
    CLOUD_FIREBASE_CONFIG.projectId,
  storageBucket:
    process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ||
    CLOUD_FIREBASE_CONFIG.storageBucket,
  messagingSenderId:
    process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ||
    CLOUD_FIREBASE_CONFIG.messagingSenderId,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || CLOUD_FIREBASE_CONFIG.appId,
  measurementId:
    process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID ||
    CLOUD_FIREBASE_CONFIG.measurementId,
};

let app: FirebaseApp | undefined;
let auth: Auth | undefined;

export function getFirebaseApp(): FirebaseApp {
  if (!getApps().length) {
    app = initializeApp(cfg);
  }
  return app ?? getApps()[0]!;
}

export function getFirebaseAuth(): Auth {
  if (!auth) {
    auth = getAuth(getFirebaseApp());
  }
  return auth;
}

/** Call once from a client useEffect; no-op on server / unsupported. */
export function initFirebaseAnalytics(): void {
  if (typeof window === "undefined") return;
  const mid = process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID;
  if (!mid) return;
  void import("firebase/analytics").then(({ getAnalytics, isSupported }) => {
    void isSupported().then((ok) => {
      if (ok) getAnalytics(getFirebaseApp());
    });
  });
}
