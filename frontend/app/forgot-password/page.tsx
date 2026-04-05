"use client";

import Link from "next/link";
import { useState } from "react";
import { sendPasswordResetEmail } from "firebase/auth";
import { describeFirebaseAuthError } from "@/lib/firebase-errors";
import { getFirebaseAuth } from "@/lib/firebase";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setDone(false);
    const em = email.trim();
    if (!em) return;
    setBusy(true);
    try {
      const auth = getFirebaseAuth();
      const continueUrl =
        typeof window !== "undefined" ? `${window.location.origin}/login` : undefined;
      await sendPasswordResetEmail(auth, em, continueUrl ? { url: continueUrl } : undefined);
      setDone(true);
    } catch (e: unknown) {
      setErr(describeFirebaseAuthError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-20">
      <h1 className="font-display text-2xl font-bold text-white">Reset password</h1>
      <p className="mt-2 text-sm text-gray-500">
        Enter your email and we&apos;ll send a link to choose a new password.
      </p>

      {done && (
        <p className="mt-6 rounded-lg border border-mint-500/40 bg-mint-500/10 px-4 py-3 text-sm text-mint-200">
          If an account exists for that email, you&apos;ll get a message shortly. Check your inbox
          and spam folder, then open the link to finish.
        </p>
      )}

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <div>
          <label className="block text-sm text-gray-400">Email</label>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-900 px-3 py-2 text-white"
          />
        </div>
        {err && <p className="text-sm text-red-400">{err}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-mint-500 py-2.5 font-medium text-ink-950 hover:bg-mint-400 disabled:opacity-50"
        >
          {busy ? "Sending…" : "Send reset link"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-gray-500">
        <Link href="/login" className="text-mint-400 hover:underline">
          Back to log in
        </Link>
        {" · "}
        <Link href="/signup" className="hover:text-white">
          Create account
        </Link>
      </p>
    </div>
  );
}
