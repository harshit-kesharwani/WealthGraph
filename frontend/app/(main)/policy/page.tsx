"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

type Goal = { id?: string; name: string; targetAmount: number; targetYear: number };

const RISK_PROFILES = [
  { value: "conservative", label: "Conservative", desc: "Low risk, stable returns. Focus on debt funds and fixed income." },
  { value: "moderate", label: "Moderate", desc: "Balanced mix of equity and debt. Suitable for most investors." },
  { value: "aggressive", label: "Aggressive", desc: "Higher equity allocation for long-term growth. Higher volatility." },
];

export default function PolicyPage() {
  const { token } = useAuth();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [maxDd, setMaxDd] = useState(15);
  const [income, setIncome] = useState(0);
  const [expenses, setExpenses] = useState(0);
  const [buffer, setBuffer] = useState(0);
  const [accountBal, setAccountBal] = useState(0);
  const [riskProfile, setRiskProfile] = useState("moderate");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    apiFetch<{
      goals: Goal[];
      maxDrawdownPct: number;
      monthlyIncome: number;
      fixedExpenses: number;
      minBankBuffer: number;
      currentAccountBalance: number;
      riskProfile: string;
    }>("/policy", token)
      .then((p) => {
        setGoals(p.goals?.length ? p.goals : [{ name: "Emergency", targetAmount: 100000, targetYear: 2027 }]);
        setMaxDd(p.maxDrawdownPct ?? 15);
        setIncome(p.monthlyIncome ?? 0);
        setExpenses(p.fixedExpenses ?? 0);
        setBuffer(p.minBankBuffer ?? 0);
        setAccountBal(p.currentAccountBalance ?? 0);
        setRiskProfile(p.riskProfile || "moderate");
      })
      .catch(() => {});
  }, [token]);

  async function save() {
    if (!token) return;
    setErr("");
    setMsg("");
    try {
      await apiFetch("/policy", token, {
        method: "PUT",
        body: JSON.stringify({
          goals: goals.map((g) => ({
            id: g.id,
            name: g.name,
            target_amount: g.targetAmount,
            target_year: g.targetYear,
          })),
          max_drawdown_pct: maxDd,
          monthly_income: income,
          fixed_expenses: expenses,
          min_bank_buffer: buffer,
          current_account_balance: accountBal,
          risk_profile: riskProfile,
          autopilot: false,
        }),
      });
      setMsg("Saved.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="font-display text-3xl font-bold text-white">Goals &amp; limits</h1>

      <section className="space-y-4 rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Goals</h2>
        {goals.map((g, i) => (
          <div key={i} className="flex items-start gap-2 border-b border-gray-800 pb-4">
            <div className="grid flex-1 gap-2 md:grid-cols-3">
              <input
                className="rounded-md border border-gray-700 bg-ink-950 px-2 py-1.5 text-sm text-white"
                placeholder="Name"
                value={g.name}
                onChange={(e) => {
                  const n = [...goals];
                  n[i] = { ...n[i], name: e.target.value };
                  setGoals(n);
                }}
              />
              <input
                type="number"
                className="rounded-md border border-gray-700 bg-ink-950 px-2 py-1.5 text-sm text-white"
                placeholder="Target ₹"
                value={g.targetAmount || ""}
                onChange={(e) => {
                  const n = [...goals];
                  n[i] = { ...n[i], targetAmount: Number(e.target.value) };
                  setGoals(n);
                }}
              />
              <input
                type="number"
                className="rounded-md border border-gray-700 bg-ink-950 px-2 py-1.5 text-sm text-white"
                placeholder="Year"
                value={g.targetYear || ""}
                onChange={(e) => {
                  const n = [...goals];
                  n[i] = { ...n[i], targetYear: Number(e.target.value) };
                  setGoals(n);
                }}
              />
            </div>
            <button
              type="button"
              onClick={() => setGoals(goals.filter((_, idx) => idx !== i))}
              className="mt-1 rounded p-1 text-red-500 hover:bg-red-500/10 hover:text-red-400"
              title="Remove goal"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        ))}
        <button
          type="button"
          className="text-sm text-mint-400 hover:underline"
          onClick={() => setGoals([...goals, { name: "New goal", targetAmount: 50000, targetYear: 2030 }])}
        >
          + Add goal
        </button>
      </section>

      {/* Risk Profile */}
      <section className="space-y-4 rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Risk profile</h2>
        <p className="text-sm text-gray-500">Choose your investment temperament. This guides AI recommendations.</p>
        <div className="grid gap-3 md:grid-cols-3">
          {RISK_PROFILES.map((rp) => (
            <button
              key={rp.value}
              type="button"
              onClick={() => setRiskProfile(rp.value)}
              className={`rounded-lg border p-4 text-left transition-colors ${
                riskProfile === rp.value
                  ? "border-mint-500 bg-mint-500/10"
                  : "border-gray-700 bg-ink-950 hover:border-gray-600"
              }`}
            >
              <p className={`font-medium ${riskProfile === rp.value ? "text-mint-400" : "text-white"}`}>
                {rp.label}
              </p>
              <p className="mt-1 text-xs text-gray-500">{rp.desc}</p>
            </button>
          ))}
        </div>
      </section>

      {/* Bank & Cash Flow */}
      <section className="space-y-4 rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Bank &amp; cash flow</h2>
        <label className="block text-sm text-gray-400">
          Current account balance ₹
          <input
            type="number"
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-950 px-3 py-2 text-white"
            value={accountBal || ""}
            onChange={(e) => setAccountBal(Number(e.target.value))}
          />
          <span className="mt-1 block text-xs text-gray-600">Your savings/current account balance. We&apos;ll alert you when there&apos;s investable surplus.</span>
        </label>
        <label className="block text-sm text-gray-400">
          Min bank buffer ₹
          <input
            type="number"
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-950 px-3 py-2 text-white"
            value={buffer || ""}
            onChange={(e) => setBuffer(Number(e.target.value))}
          />
          <span className="mt-1 block text-xs text-gray-600">Always keep at least this much in your bank. Surplus above this is investable.</span>
        </label>
        {accountBal > 0 && buffer > 0 && accountBal > (expenses + buffer) && (
          <div className="rounded-lg border border-mint-500/30 bg-mint-500/5 px-4 py-3 text-sm text-mint-300">
            You have ₹{(accountBal - expenses - buffer).toLocaleString()} investable surplus. Check the Overview for AI suggestions.
          </div>
        )}
        <label className="block text-sm text-gray-400">
          Monthly income ₹
          <input
            type="number"
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-950 px-3 py-2 text-white"
            value={income || ""}
            onChange={(e) => setIncome(Number(e.target.value))}
          />
        </label>
        <label className="block text-sm text-gray-400">
          Fixed expenses ₹
          <input
            type="number"
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-950 px-3 py-2 text-white"
            value={expenses || ""}
            onChange={(e) => setExpenses(Number(e.target.value))}
          />
        </label>
      </section>

      {/* Risk Limits */}
      <section className="space-y-4 rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Risk limits</h2>
        <label className="block text-sm text-gray-400">
          Max drawdown % (stop-loss threshold)
          <input
            type="number"
            className="mt-1 w-full rounded-md border border-gray-700 bg-ink-950 px-3 py-2 text-white"
            value={maxDd}
            onChange={(e) => setMaxDd(Number(e.target.value))}
          />
          <span className="mt-1 block text-xs text-gray-600">
            If any holding drops more than this from your buy price, you&apos;ll see a stop-loss alert.
          </span>
        </label>
      </section>

      <section className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-white">Autopilot</h2>
        <p className="mt-1 text-sm text-gray-500">Allow simulated trades without manual approval.</p>
        <div className="mt-4 flex items-center gap-3 opacity-60">
          <button
            type="button"
            disabled
            aria-disabled="true"
            className="relative h-8 w-14 cursor-not-allowed rounded-full bg-gray-700"
          >
            <span className="absolute left-1 top-1 h-6 w-6 rounded-full bg-white" />
          </button>
          <span className="text-sm text-gray-400">Off</span>
        </div>
        <p className="mt-3 text-xs text-gray-600">
          Autopilot is in development and cannot be enabled yet.
        </p>
      </section>

      {err && <p className="text-sm text-red-400">{err}</p>}
      {msg && <p className="text-sm text-mint-400">{msg}</p>}
      <button
        type="button"
        onClick={save}
        className="rounded-lg bg-mint-500 px-6 py-2.5 font-medium text-ink-950 hover:bg-mint-400"
      >
        Save
      </button>
    </div>
  );
}
