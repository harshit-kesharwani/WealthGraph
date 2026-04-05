"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { signInWithEmailAndPassword } from "firebase/auth";
import { describeFirebaseAuthError } from "@/lib/firebase-errors";
import { getFirebaseAuth } from "@/lib/firebase";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const em = email.trim();
    try {
      await signInWithEmailAndPassword(getFirebaseAuth(), em, password);
      router.replace("/dashboard");
    } catch (e: unknown) {
      setErr(describeFirebaseAuthError(e));
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-20">
      <h1 className="font-display text-2xl font-bold text-white">Log in</h1>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <div>
          <label className="block text-sm text-gray-400">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-900 px-3 py-2 text-white"
          />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className="block text-sm text-gray-400">Password</label>
            <Link href="/forgot-password" className="text-xs text-mint-400 hover:underline">
              Forgot password?
            </Link>
          </div>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-900 px-3 py-2 text-white"
          />
        </div>
        {err && <p className="text-sm text-red-400">{err}</p>}
        <button
          type="submit"
          className="w-full rounded-lg bg-mint-500 py-2.5 font-medium text-ink-950 hover:bg-mint-400"
        >
          Sign in
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-gray-500">
        <Link href="/signup" className="text-mint-400 hover:underline">
          Create account
        </Link>
        {" · "}
        <Link href="/" className="hover:text-white">
          Home
        </Link>
      </p>
    </div>
  );
}
