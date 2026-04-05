"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { reload, sendEmailVerification, signOut } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { useAuth } from "@/components/AuthProvider";
import { describeFirebaseAuthError } from "@/lib/firebase-errors";

export default function VerifyEmailPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [resendBusy, setResendBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (user?.emailVerified) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  const refreshStatus = useCallback(async () => {
    setErr("");
    setMsg("");
    const auth = getFirebaseAuth();
    const u = auth.currentUser;
    if (!u) return;
    try {
      await reload(u);
      if (auth.currentUser?.emailVerified) {
        router.replace("/dashboard");
        return;
      }
      setMsg("We still don’t see a verified email. Check spam or tap the link again.");
    } catch (e: unknown) {
      setErr(describeFirebaseAuthError(e));
    }
  }, [router]);

  async function resend() {
    const auth = getFirebaseAuth();
    const u = auth.currentUser;
    if (!u) return;
    setResendBusy(true);
    setErr("");
    setMsg("");
    try {
      await sendEmailVerification(u);
      setMsg("Another email is on the way. Check your inbox and spam.");
    } catch (e: unknown) {
      setErr(describeFirebaseAuthError(e));
    } finally {
      setResendBusy(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-gray-400">
        Loading…
      </div>
    );
  }

  if (user.emailVerified) {
    return null;
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-16">
      <h1 className="font-display text-2xl font-bold text-white">Verify your email</h1>
      <p className="mt-3 text-gray-400">
        We sent a link to <span className="text-white">{user.email}</span>. Open it on this device
        (or any device signed into the same mailbox), then come back here.
      </p>
      <div className="mt-8 space-y-3">
        <button
          type="button"
          onClick={refreshStatus}
          className="w-full rounded-lg bg-mint-500 py-2.5 font-medium text-ink-950 hover:bg-mint-400"
        >
          I’ve verified — continue
        </button>
        <button
          type="button"
          onClick={resend}
          disabled={resendBusy}
          className="w-full rounded-lg border border-gray-600 py-2.5 text-sm text-gray-300 hover:border-mint-500 disabled:opacity-50"
        >
          {resendBusy ? "Sending…" : "Resend verification email"}
        </button>
      </div>
      {msg && <p className="mt-4 text-sm text-mint-400">{msg}</p>}
      {err && <p className="mt-4 text-sm text-red-400">{err}</p>}
      <p className="mt-8 text-center text-sm text-gray-500">
        <button
          type="button"
          onClick={() => {
            void signOut(getFirebaseAuth()).then(() => router.replace("/login"));
          }}
          className="text-mint-400 hover:underline"
        >
          Sign out and use a different email
        </button>
      </p>
    </div>
  );
}
