"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

type EquityLine = {
  ticker: string;
  name?: string;
  qty: number;
  buyPrice: number;
  buyDate?: string;
  currentPrice: number;
  invested: number;
  currentValue: number;
  pnl: number;
  pnlPct: number;
  live: boolean;
};

type MFLine = {
  amfiCode?: string;
  isin?: string;
  name?: string;
  units: number;
  buyNav: number;
  buyDate?: string;
  currentNav: number;
  navDate?: string | null;
  invested: number;
  currentValue: number;
  pnl: number;
  pnlPct: number;
  live: boolean;
};

type Summary = {
  netWorth: number;
  totalInvested: number;
  cash: number;
  totalPnl: number;
  approxReturnPct: number;
  xirrNote?: string;
  allocation: { equity: number; mutualFunds: number; cash: number };
  equity: EquityLine[];
  mutualFunds: MFLine[];
  priceWarnings?: string[];
  goalProgress: Array<{
    id: string;
    name: string;
    targetAmount: number;
    targetYear?: number;
    progressPct: number;
  }>;
  autopilot: boolean;
};

type IndexData = {
  name: string;
  value: number | null;
  changePct: number | null;
  lastUpdated: string | null;
  sessionLabel?: string | null;
};

type NewsArticle = { title: string; description: string; source: string; url: string };

type Insight = {
  type: string;
  severity: string;
  title: string;
  description: string;
  amount?: number;
  ticker?: string;
  pnlPct?: number;
  monthlyNeeded?: number;
};

type ActionItem = { what?: string; why?: string };
type FundAlt = { name?: string; reason?: string };
type AdvisorReply = {
  reply: string;
  structured?: {
    actions?: ActionItem[];
    fund_alternatives?: FundAlt[];
  };
};

const COLORS = ["#10b981", "#f59e0b", "#6366f1"];
const pnlColor = (v: number) => (v >= 0 ? "text-mint-400" : "text-red-400");
const pnlSign = (v: number) => (v >= 0 ? "+" : "");

const severityStyles: Record<string, string> = {
  critical: "border-red-500/40 bg-red-500/10 text-red-200",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  info: "border-blue-500/30 bg-blue-500/5 text-blue-200",
};

export default function DashboardPage() {
  const { token } = useAuth();
  const [data, setData] = useState<Summary | null>(null);
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [newsSummary, setNewsSummary] = useState<string | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [advisor, setAdvisor] = useState<AdvisorReply | null>(null);
  const [advisorLoading, setAdvisorLoading] = useState(false);
  const [err, setErr] = useState("");

  function runAdvisorAnalysis() {
    if (!token) return;
    setAdvisorLoading(true);
    apiFetch<AdvisorReply>("/advisor/live/chat", token, {
      method: "POST",
      body: JSON.stringify({
        messages: [
          {
            role: "user",
            content:
              "Give me a comprehensive analysis of my portfolio. For each holding, state whether I should HOLD, EXIT, or SWITCH with bold reasoning. " +
              "If any mutual fund should be switched, name 2-3 specific alternative schemes by full fund name and explain why. " +
              "If a stock has crossed stop-loss but fundamentals are strong, say HOLD and explain. " +
              "Be direct and specific — reference actual tickers, fund names, and amounts from my portfolio. Use the mfAnalysis data to provide informed advice.",
          },
        ],
      }),
    })
      .then(setAdvisor)
      .catch(() => {})
      .finally(() => setAdvisorLoading(false));
  }

  useEffect(() => {
    if (!token) return;
    apiFetch<Summary>("/dashboard/summary", token)
      .then(setData)
      .catch((e) => setErr(String(e.message)));
    apiFetch<{ indices: IndexData[] }>("/dashboard/indices", token)
      .then((r) => setIndices(r.indices || []))
      .catch(() => {});
    apiFetch<{ articles: NewsArticle[]; summary: string | null }>("/dashboard/news", token)
      .then((r) => {
        setArticles(r.articles || []);
        setNewsSummary(r.summary || null);
      })
      .catch(() => {});
    apiFetch<{ insights: Insight[] }>("/dashboard/insights", token)
      .then((r) => setInsights(r.insights || []))
      .catch(() => {});
    runAdvisorAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (err) {
    return <p className="text-red-400">Could not load dashboard: {err}</p>;
  }
  if (!data) {
    return <p className="text-gray-500">Loading dashboard…</p>;
  }

  const nwDenom = data.netWorth > 0 ? data.netWorth : 1;
  const equityFromHoldings =
    data.equity.length > 0
      ? (data.equity.reduce((s, e) => s + e.currentValue, 0) / nwDenom) * 100
      : data.allocation.equity * 100;
  let equityPct = data.allocation.equity * 100;
  if (data.equity.length > 0 && equityPct < 0.01 && equityFromHoldings > 0) {
    equityPct = equityFromHoldings;
  }
  const rawPie = [
    { name: "Equity", value: equityPct },
    { name: "Mutual funds", value: data.allocation.mutualFunds * 100 },
    { name: "Cash", value: data.allocation.cash * 100 },
  ];
  const pieData = rawPie
    .map((d) => {
      let v = Math.round(d.value * 100) / 100;
      if (d.name === "Equity" && data.equity.length > 0 && v > 0 && v < 0.1) {
        v = 0.1;
      }
      return { ...d, value: v };
    })
    .filter((d) => d.value > 0);

  const indicesDate = indices.find((i) => i.lastUpdated)?.lastUpdated;

  const criticalInsights = insights.filter((i) => i.severity === "critical");
  const otherInsights = insights.filter((i) => i.severity !== "critical");

  return (
    <div className="space-y-10">
      <div>
        <h1 className="font-display text-3xl font-bold text-white">Overview</h1>
        <p className="mt-1 text-sm text-gray-500">
          Autopilot is in development and is not available yet.
        </p>
      </div>

      {/* Market Indices */}
      {indices.length > 0 && (
        <div>
          <div className="flex flex-wrap gap-4">
            {indices.map((idx) => (
              <div
                key={idx.name}
                className="flex items-center gap-3 rounded-lg border border-gray-800 bg-ink-900/60 px-4 py-3"
              >
                <span className="text-sm font-medium text-gray-300">{idx.name}</span>
                {idx.value != null ? (
                  <>
                    <span className="font-display text-lg text-white">
                      {idx.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </span>
                    {idx.changePct != null && (
                      <span
                        className={`text-sm font-medium ${idx.changePct >= 0 ? "text-mint-400" : "text-red-400"}`}
                      >
                        {idx.changePct >= 0 ? "▲" : "▼"} {Math.abs(idx.changePct).toFixed(2)}%
                      </span>
                    )}
                  </>
                ) : (
                  <span className="text-xs text-gray-500">Market closed / unavailable</span>
                )}
              </div>
            ))}
          </div>
          {indicesDate && (
            <p className="mt-1 text-xs text-gray-600">
              {indices.some((i) => i.sessionLabel) ? "Last trading session: " : "Last updated: "}
              {indicesDate}
              {indices.some((i) => i.sessionLabel) && (
                <span className="text-gray-500"> (values from most recent session with data)</span>
              )}
            </p>
          )}
        </div>
      )}

      {/* Critical alerts */}
      {criticalInsights.length > 0 && (
        <div className="space-y-3">
          {criticalInsights.map((ins, i) => (
            <div
              key={i}
              className={`rounded-lg border px-4 py-3 ${severityStyles[ins.severity]}`}
            >
              <p className="font-medium">{ins.title}</p>
              <p className="mt-1 text-sm opacity-90">{ins.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid gap-6 md:grid-cols-4">
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <p className="text-sm text-gray-500">Net worth</p>
          <p className="mt-2 font-display text-3xl text-white">
            ₹{data.netWorth.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <p className="text-sm text-gray-500">Invested</p>
          <p className="mt-2 font-display text-3xl text-white">
            ₹{(data.totalInvested ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <p className="text-sm text-gray-500">Total P&amp;L</p>
          <p className={`mt-2 font-display text-3xl ${pnlColor(data.totalPnl)}`}>
            {pnlSign(data.totalPnl)}₹{Math.abs(data.totalPnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
          <p className={`mt-1 text-sm ${pnlColor(data.approxReturnPct)}`}>
            {pnlSign(data.approxReturnPct)}{data.approxReturnPct.toFixed(2)}%
          </p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <p className="text-sm text-gray-500">Cash</p>
          <p className="mt-2 font-display text-3xl text-white">
            ₹{data.cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
        </div>
      </div>

      {data.priceWarnings && data.priceWarnings.length > 0 && (
        <div className="rounded-lg border border-gold-500/40 bg-gold-500/10 px-4 py-3 text-sm text-gold-200">
          {data.priceWarnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {/* Holdings: Stocks */}
      {data.equity && data.equity.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <h2 className="font-display text-lg font-semibold text-white">Stock Holdings</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-500">
                  <th className="pb-2 pr-4">Stock</th>
                  <th className="pb-2 pr-4 text-right">Qty</th>
                  <th className="pb-2 pr-4 text-right">Buy Price</th>
                  <th className="pb-2 pr-4 text-right">Current</th>
                  <th className="pb-2 pr-4 text-right">Invested</th>
                  <th className="pb-2 pr-4 text-right">Current Value</th>
                  <th className="pb-2 text-right">P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {data.equity.map((eq) => (
                  <tr key={eq.ticker} className="border-b border-gray-800/50">
                    <td className="py-2 pr-4">
                      <span className="text-white">{eq.name || eq.ticker}</span>
                      {eq.name && eq.name !== eq.ticker && (
                        <span className="ml-1 text-gray-600">({eq.ticker})</span>
                      )}
                      {eq.buyDate && (
                        <span className="ml-2 text-xs text-gray-600">{eq.buyDate}</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-300">{eq.qty}</td>
                    <td className="py-2 pr-4 text-right text-gray-300">₹{eq.buyPrice.toLocaleString()}</td>
                    <td className="py-2 pr-4 text-right text-gray-300">
                      ₹{eq.currentPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-400">
                      ₹{eq.invested.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td className="py-2 pr-4 text-right text-white">
                      ₹{eq.currentValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td className={`py-2 text-right font-medium ${pnlColor(eq.pnl)}`}>
                      {pnlSign(eq.pnl)}₹{Math.abs(eq.pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      <span className="ml-1 text-xs">({pnlSign(eq.pnlPct)}{Math.abs(eq.pnlPct).toFixed(1)}%)</span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="text-white font-medium">
                  <td className="pt-2" colSpan={4}>Total Equity</td>
                  <td className="pt-2 text-right">
                    ₹{data.equity.reduce((s, e) => s + e.invested, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td className="pt-2 text-right">
                    ₹{data.equity.reduce((s, e) => s + e.currentValue, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td className={`pt-2 text-right ${pnlColor(data.equity.reduce((s, e) => s + e.pnl, 0))}`}>
                    {pnlSign(data.equity.reduce((s, e) => s + e.pnl, 0))}₹{Math.abs(data.equity.reduce((s, e) => s + e.pnl, 0)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Holdings: Mutual Funds */}
      {data.mutualFunds && data.mutualFunds.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <h2 className="font-display text-lg font-semibold text-white">Mutual Fund Holdings</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-gray-500">
                  <th className="pb-2 pr-4">Fund</th>
                  <th className="pb-2 pr-4 text-right">Units</th>
                  <th className="pb-2 pr-4 text-right">Buy NAV</th>
                  <th className="pb-2 pr-4 text-right">Current NAV</th>
                  <th className="pb-2 pr-4 text-right">NAV as of</th>
                  <th className="pb-2 pr-4 text-right">Invested</th>
                  <th className="pb-2 pr-4 text-right">Current Value</th>
                  <th className="pb-2 text-right">P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {data.mutualFunds.map((mf) => (
                  <tr key={mf.isin || mf.amfiCode || mf.name} className="border-b border-gray-800/50">
                    <td className="py-2 pr-4">
                      <span className="text-white">{mf.name || mf.amfiCode || mf.isin}</span>
                      {mf.isin && (
                        <span className="ml-1 block text-xs text-gray-600">ISIN {mf.isin}</span>
                      )}
                      {mf.amfiCode && (
                        <span className="ml-1 text-gray-600">({mf.amfiCode})</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-300">{mf.units}</td>
                    <td className="py-2 pr-4 text-right text-gray-300">₹{mf.buyNav.toLocaleString()}</td>
                    <td className="py-2 pr-4 text-right text-gray-300">
                      ₹{mf.currentNav.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-2 pr-4 text-right text-xs text-gray-500">
                      {mf.navDate || "—"}
                      {mf.navDate && (
                        <span className="mt-0.5 block text-gray-600">Latest published</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-right text-gray-400">
                      ₹{mf.invested.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td className="py-2 pr-4 text-right text-white">
                      ₹{mf.currentValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td className={`py-2 text-right font-medium ${pnlColor(mf.pnl)}`}>
                      {pnlSign(mf.pnl)}₹{Math.abs(mf.pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      <span className="ml-1 text-xs">({pnlSign(mf.pnlPct)}{Math.abs(mf.pnlPct).toFixed(1)}%)</span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="text-white font-medium">
                  <td className="pt-2" colSpan={5}>Total Mutual Funds</td>
                  <td className="pt-2 text-right">
                    ₹{data.mutualFunds.reduce((s, m) => s + m.invested, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td className="pt-2 text-right">
                    ₹{data.mutualFunds.reduce((s, m) => s + m.currentValue, 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td className={`pt-2 text-right ${pnlColor(data.mutualFunds.reduce((s, m) => s + m.pnl, 0))}`}>
                    {pnlSign(data.mutualFunds.reduce((s, m) => s + m.pnl, 0))}₹{Math.abs(data.mutualFunds.reduce((s, m) => s + m.pnl, 0)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Allocation chart */}
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <h2 className="font-display text-lg font-semibold text-white">Asset allocation</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => `${v}%`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Goal progress */}
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <h2 className="font-display text-lg font-semibold text-white">Goal progress</h2>
          <ul className="mt-4 space-y-4">
            {data.goalProgress.length === 0 && (
              <li className="text-gray-500">Add goals under Goals &amp; limits.</li>
            )}
            {data.goalProgress.map((g) => (
              <li key={g.id || g.name}>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-300">{g.name}</span>
                  <span className="text-gray-500">
                    ₹{g.targetAmount.toLocaleString()}
                    {g.targetYear != null ? ` by ${g.targetYear}` : ""}
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-gray-800">
                  <div
                    className="h-full rounded-full bg-mint-500 transition-all"
                    style={{ width: `${Math.min(100, g.progressPct)}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {g.progressPct.toFixed(1)}% of target
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* AI Insights */}
      {otherInsights.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <h2 className="font-display text-lg font-semibold text-white">AI Insights &amp; Recommendations</h2>
          <div className="mt-4 space-y-3">
            {otherInsights.map((ins, i) => (
              <div
                key={i}
                className={`rounded-lg border px-4 py-3 ${severityStyles[ins.severity] || severityStyles.info}`}
              >
                <p className="font-medium">{ins.title}</p>
                <p className="mt-1 text-sm opacity-90">{ins.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Advisor Analysis */}
      <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-semibold text-white">AI Portfolio Advisor</h2>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={runAdvisorAnalysis}
              disabled={advisorLoading || !token}
              className="rounded-lg bg-mint-500/20 px-4 py-1.5 text-xs font-medium text-mint-400 hover:bg-mint-500/30 disabled:opacity-40"
            >
              {advisorLoading ? "Analyzing..." : "Refresh"}
            </button>
            <Link
              href="/live-advisor"
              className="rounded-lg border border-gray-700 px-4 py-1.5 text-xs text-gray-400 hover:bg-gray-800 hover:text-white"
            >
              Chat with Advisor
            </Link>
          </div>
        </div>

        {/* Portfolio News Summary merged into advisor card */}
        {newsSummary && (
          <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/5 px-4 py-3 mb-4">
            <h3 className="text-sm font-semibold text-cyan-400 mb-1">Market News &amp; Your Portfolio</h3>
            <p className="text-sm text-gray-200">{newsSummary}</p>
            {articles.length > 0 && (
              <ul className="mt-2 space-y-1">
                {articles.slice(0, 5).map((a, i) => (
                  <li key={i}>
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-gray-400 hover:text-white"
                    >
                      {a.title}
                      {a.source && <span className="ml-1 text-gray-600">— {a.source}</span>}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {advisorLoading && (
          <p className="text-sm text-gray-400 animate-pulse">Analyzing your portfolio with AI...</p>
        )}

        {advisor && !advisorLoading && (
          <div className="space-y-5">
            <div className="prose prose-invert prose-sm max-w-none">
              {advisor.reply.split("\n").map((line, i) => {
                const trimmed = line.trim();
                if (!trimmed) return <br key={i} />;
                const isHeading = /^#+\s/.test(trimmed) || /^(HOLD|EXIT|SWITCH|RECOMMENDATION|ANALYSIS|VERDICT)/i.test(trimmed);
                const isBold = /^\*\*/.test(trimmed) || isHeading;
                if (isBold || isHeading) {
                  return (
                    <p key={i} className="font-bold text-white mt-3">
                      {trimmed.replace(/^#+\s*/, "").replace(/\*\*/g, "")}
                    </p>
                  );
                }
                return (
                  <p key={i} className="text-gray-300 mt-1">
                    {trimmed.replace(/\*\*/g, "")}
                  </p>
                );
              })}
            </div>

            {advisor.structured?.actions && advisor.structured.actions.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-white mb-2">Recommended Actions</h3>
                <div className="space-y-2">
                  {advisor.structured.actions.map((a, i) => (
                    <div key={i} className="rounded-lg border border-mint-500/30 bg-mint-500/5 px-4 py-3">
                      <p className="font-semibold text-mint-400 text-sm">{a.what}</p>
                      {a.why && <p className="mt-1 text-xs text-gray-300">{a.why}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {advisor.structured?.fund_alternatives && advisor.structured.fund_alternatives.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-white mb-2">Alternative Fund Suggestions</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-800 text-left text-gray-500">
                        <th className="pb-2 pr-4">Fund Name</th>
                        <th className="pb-2">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {advisor.structured.fund_alternatives.map((f, i) => (
                        <tr key={i} className="border-b border-gray-800/50">
                          <td className="py-2 pr-4 font-medium text-white">{f.name || "—"}</td>
                          <td className="py-2 text-gray-300">{f.reason || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {!advisor && !advisorLoading && (
          <p className="text-sm text-gray-500">Click Refresh to get AI analysis of your portfolio.</p>
        )}
      </div>

      {/* Remaining article links if there's no summary but articles exist */}
      {!newsSummary && articles.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
          <h2 className="font-display text-lg font-semibold text-white">News for your portfolio</h2>
          <ul className="mt-4 space-y-3">
            {articles.map((a, i) => (
              <li key={i}>
                <a
                  href={a.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-300 hover:text-white"
                >
                  {a.title}
                </a>
                {a.source && <span className="ml-2 text-xs text-gray-600">— {a.source}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
