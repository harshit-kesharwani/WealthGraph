import type { FirebaseError } from "firebase/app";

function isFirebaseError(err: unknown): err is FirebaseError {
  return (
    typeof err === "object" &&
    err !== null &&
    "code" in err &&
    typeof (err as FirebaseError).code === "string"
  );
}

/** Human-readable copy for Firebase Auth errors (real cause was hidden before). */
export function describeFirebaseAuthError(err: unknown): string {
  if (!isFirebaseError(err)) {
    if (err instanceof Error && err.message) return err.message;
    return "Something went wrong. Try again.";
  }
  const code = err.code;
  const raw = err.message || "";

  const map: Record<string, string> = {
    "auth/email-already-in-use":
      "This email is already registered. Use Log in, or reset password from Firebase Console.",
    "auth/invalid-email": "That email address doesn’t look valid.",
    "auth/invalid-credential":
      "Wrong email or password, or this sign-in method isn’t enabled for this account.",
    "auth/wrong-password": "Wrong password.",
    "auth/user-not-found": "No account with this email. Sign up first.",
    "auth/too-many-requests": "Too many attempts. Wait a few minutes and try again.",
    "auth/weak-password":
      "Password is considered too weak by Firebase. Try a longer mix of letters, numbers, and symbols.",
    "auth/operation-not-allowed":
      "Email/Password is turned off in Firebase. In Console: Authentication → Sign-in method → enable Email/Password.",
    "auth/network-request-failed":
      "Network error (blocked request, offline, or bad DNS). Check connection and try again.",
    "auth/invalid-api-key":
      "Invalid Firebase web API key. Rebuild the app with correct NEXT_PUBLIC_FIREBASE_* in .env.production.",
    "auth/app-deleted": "Firebase app was deleted or project misconfigured.",
    "auth/missing-email": "Enter your email address.",
    "auth/invalid-continue-uri":
      "Password reset link domain is not allowed. In Firebase Console → Authentication → Settings → Authorized domains, add your site host.",
  };

  if (map[code]) return map[code];
  return raw ? `${code}: ${raw}` : code || "Sign-in failed.";
}
