"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

export default function DemoPage() {
  const { token } = useAuth();
  const [isDemo, setIsDemo] = useState(false);
  const [salary, setSalary] = useState(50000);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    apiFetch<{ isDemo: boolean }>("/me", token).then((m) => setIsDemo(!!m.isDemo));
  }, [token]);

  async function enableDemo() {
    if (!token) return;
    await apiFetch("/me", token, {
      method: "PATCH",
      body: JSON.stringify({ is_demo: true }),
    });
    setIsDemo(true);
    setMsg("Practice mode is on for your account.");
  }

  async function injectSalary() {
    if (!token) return;
    setErr("");
    try {
      await apiFetch("/demo/inject-salary", token, {
        method: "POST",
        body: JSON.stringify({ amount_inr: salary }),
      });
      setMsg(`Credited ₹${salary} (demo). Check Overview and Live AI Advisor for updated context.`);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  async function crash() {
    if (!token) return;
    setErr("");
    try {
      await apiFetch("/demo/simulate-crash", token, {
        method: "POST",
        body: JSON.stringify({ drop_pct: 20 }),
      });
      setMsg("Applied a demo market dip. Refresh your overview to see the change.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-8">
      <h1 className="font-display text-3xl font-bold text-white">Try scenarios</h1>
      <p className="text-sm text-gray-500">
        Turn on practice mode, then try a salary credit or a market dip to see how the app
        responds — nothing here moves real money.
      </p>

      {!isDemo && (
        <button
          type="button"
          onClick={enableDemo}
          className="rounded-lg border border-mint-500 px-4 py-2 text-mint-400 hover:bg-mint-500/10"
        >
          Turn on practice mode
        </button>
      )}

      {isDemo && (
        <div className="flex items-center gap-4">
          <p className="text-sm text-mint-400">Practice mode is on.</p>
          <button
            type="button"
            onClick={async () => {
              if (!token) return;
              await apiFetch("/me", token, {
                method: "PATCH",
                body: JSON.stringify({ is_demo: false }),
              });
              setIsDemo(false);
              setMsg("Switched to active mode. Your real portfolio is now live.");
            }}
            className="rounded-lg border border-amber-500 px-4 py-2 text-sm text-amber-400 hover:bg-amber-500/10"
          >
            Switch to active mode
          </button>
        </div>
      )}

      <div className="space-y-4 rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-white">Salary credit (demo)</h2>
        <input
          type="number"
          className="w-full rounded-md border border-gray-700 bg-ink-950 px-3 py-2 text-white"
          value={salary}
          onChange={(e) => setSalary(Number(e.target.value))}
        />
        <button
          type="button"
          onClick={injectSalary}
          className="rounded-lg bg-mint-500 px-4 py-2 font-medium text-ink-950"
        >
          Add to demo cash
        </button>
      </div>

      <div className="space-y-4 rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-white">Market dip (demo)</h2>
        <p className="text-sm text-gray-500">
          Temporarily lowers demo prices by about 20% so you can see alerts and suggestions.
        </p>
        <button
          type="button"
          onClick={crash}
          className="rounded-lg bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-500"
        >
          Drop marks ~20%
        </button>
      </div>

      {msg && <p className="text-sm text-mint-400">{msg}</p>}
      {err && <p className="text-sm text-red-400">{err}</p>}
    </div>
  );
}
