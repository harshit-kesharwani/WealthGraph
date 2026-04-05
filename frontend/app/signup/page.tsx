"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  createUserWithEmailAndPassword,
  sendEmailVerification,
  updateProfile,
} from "firebase/auth";
import { describeFirebaseAuthError } from "@/lib/firebase-errors";
import { getFirebaseAuth } from "@/lib/firebase";
import { validateIndianMobile } from "@/lib/phone";
import { apiFetch } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const name = fullName.trim();
    const em = email.trim();
    const mobileOk = validateIndianMobile(mobile);
    if (name.length < 2) {
      setErr("Please enter your full name.");
      return;
    }
    if (!mobileOk) {
      setErr("Enter a valid 10-digit Indian mobile number (starts with 6–9).");
      return;
    }
    setBusy(true);
    const auth = getFirebaseAuth();
    try {
      const cred = await createUserWithEmailAndPassword(auth, em, password);
      await updateProfile(cred.user, { displayName: name });
      const token = await cred.user.getIdToken();
      try {
        await apiFetch("/me", token, {
          method: "PATCH",
          body: JSON.stringify({
            display_name: name,
            phone: mobileOk,
          }),
        });
      } catch {
        /* profile sync can retry after verification */
      }
      await sendEmailVerification(cred.user);
      router.replace("/verify-email");
    } catch (e: unknown) {
      setErr(describeFirebaseAuthError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <h1 className="font-display text-2xl font-bold text-white">Create your account</h1>
      <p className="mt-2 text-sm text-gray-500">
        We’ll send a verification link to your email before you can use the app.
      </p>
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <div>
          <label className="block text-sm text-gray-400">Full name</label>
          <input
            type="text"
            name="name"
            autoComplete="name"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-900 px-3 py-2 text-white"
            placeholder="As on your PAN / bank"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400">Mobile number</label>
          <input
            type="tel"
            name="phone"
            autoComplete="tel"
            required
            value={mobile}
            onChange={(e) => setMobile(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-900 px-3 py-2 text-white"
            placeholder="10-digit number (e.g. 9876543210)"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400">Email</label>
          <input
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-900 px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400">Password</label>
          <input
            type="password"
            name="new-password"
            autoComplete="new-password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-900 px-3 py-2 text-white"
            placeholder="At least 6 characters"
          />
        </div>
        {err && <p className="text-sm text-red-400">{err}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-mint-500 py-2.5 font-medium text-ink-950 hover:bg-mint-400 disabled:opacity-50"
        >
          {busy ? "Creating account…" : "Continue"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-gray-500">
        Already registered?{" "}
        <Link href="/login" className="text-mint-400 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
