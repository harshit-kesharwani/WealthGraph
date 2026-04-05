"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

type Item = { id: string; title?: string; body?: string; createdAt?: string };

type TradeRow = Item & {
  symbol?: string;
  side?: string;
  qty?: number;
  price?: number;
  asset_type?: string;
  status?: string;
};

function describeTrade(t: TradeRow): string {
  const sym = t.symbol ?? "—";
  const sideRaw = (t.side ?? "").toLowerCase();
  const side =
    sideRaw === "buy" ? "Buy" : sideRaw === "sell" ? "Sell" : t.side ? String(t.side) : "Trade";
  const q = t.qty != null && Number.isFinite(Number(t.qty)) ? Number(t.qty) : null;
  const qtyPart =
    q != null
      ? ` · ${q >= 1 ? q.toFixed(2).replace(/\.?0+$/, "") : q.toFixed(4).replace(/\.?0+$/, "")} units`
      : "";
  const p =
    t.price != null && Number.isFinite(Number(t.price))
      ? ` @ ₹${Number(t.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
      : "";
  return `${side} ${sym}${qtyPart}${p}`;
}

export default function InboxPage() {
  const { token } = useAuth();
  const [alerts, setAlerts] = useState<Item[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [clearing, setClearing] = useState(false);

  const loadData = () => {
    if (!token) return;
    Promise.all([
      apiFetch<{ items: Item[] }>("/inbox/alerts", token),
      apiFetch<{ items: TradeRow[] }>("/inbox/trades", token),
    ]).then(([a, t]) => {
      setAlerts(a.items);
      setTrades(t.items);
    });
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleClearAll = async () => {
    if (!token || !confirm("Clear all alerts and activity? This cannot be undone.")) return;
    setClearing(true);
    try {
      await apiFetch("/inbox/all", token, { method: "DELETE" });
      setAlerts([]);
      setTrades([]);
    } catch {
      alert("Failed to clear updates.");
    } finally {
      setClearing(false);
    }
  };

  return (
    <div className="space-y-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Updates</h1>
          <p className="text-sm text-gray-500">Alerts and activity from your account.</p>
        </div>
        {(alerts.length > 0 || trades.length > 0) && (
          <button
            onClick={handleClearAll}
            disabled={clearing}
            className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-300 hover:bg-red-500/20 disabled:opacity-50"
          >
            {clearing ? "Clearing…" : "Clear all"}
          </button>
        )}
      </div>

      <section>
        <h2 className="font-display text-xl font-semibold text-mint-400">Alerts</h2>
        <ul className="mt-4 space-y-3">
          {alerts.length === 0 && <li className="text-gray-500">No alerts yet.</li>}
          {alerts.map((x) => (
            <li key={x.id} className="rounded-lg border border-gray-800 bg-ink-900/60 px-4 py-3">
              <p className="font-medium text-white">{x.title}</p>
              <p className="text-sm text-gray-400">{x.body}</p>
              <p className="mt-1 text-xs text-gray-600">{x.createdAt}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="font-display text-xl font-semibold text-mint-400">Recent activity</h2>
        <p className="mt-1 text-sm text-gray-500">Demo trades and approvals (not real brokerage).</p>
        <ul className="mt-4 space-y-3">
          {trades.length === 0 && <li className="text-gray-500">No activity yet.</li>}
          {trades.map((x) => (
            <li
              key={x.id}
              className="rounded-lg border border-gray-800 bg-ink-900/60 px-4 py-3 text-sm text-gray-300"
            >
              <p className="font-medium text-white">{describeTrade(x)}</p>
              {x.createdAt && (
                <p className="mt-1 text-xs text-gray-600">{x.createdAt}</p>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
