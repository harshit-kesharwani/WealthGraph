"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  apiFetch,
  postPortfolioNewsTabRefresh,
  PortfolioNewsCooldownError,
  type PortfolioNewsTabPayload,
} from "@/lib/api";

export default function PortfolioNewsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<PortfolioNewsTabPayload | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [countdown, setCountdown] = useState(0);

  const load = useCallback(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    apiFetch<PortfolioNewsTabPayload>("/dashboard/portfolio-news", token)
      .then((d) => {
        setData(d);
        setCountdown(d.secondsUntilRefresh ?? 0);
      })
      .catch((e: Error) => setErr(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = setInterval(() => setCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
  }, [countdown]);

  async function onRefresh() {
    if (!token) return;
    setRefreshing(true);
    setErr("");
    try {
      const d = await postPortfolioNewsTabRefresh(token);
      setData(d);
      setCountdown(d.secondsUntilRefresh ?? 0);
    } catch (e: unknown) {
      if (e instanceof PortfolioNewsCooldownError) {
        setCountdown(e.retryAfterSeconds);
        setErr(e.message);
      } else if (e instanceof Error) {
        setErr(e.message);
      } else {
        setErr("Refresh failed");
      }
    } finally {
      setRefreshing(false);
    }
  }

  if (!token) {
    return <p className="text-gray-500">Sign in to view portfolio news.</p>;
  }
  if (loading && !data) {
    return <p className="text-gray-500">Loading…</p>;
  }

  const canClick = (data?.canRefresh ?? true) && countdown === 0 && !refreshing;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold text-white">Portfolio news</h1>
          <p className="mt-1 text-sm text-gray-500">
            News is biased toward your <strong className="text-gray-400">value-weighted sector tilt</strong> (direct
            stocks) and <strong className="text-gray-400">MF categories</strong>, not generic indices. Refresh is
            limited to once every 5 minutes.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            type="button"
            onClick={onRefresh}
            disabled={!canClick}
            className="rounded-lg bg-mint-500/20 px-4 py-2 text-sm font-medium text-mint-400 hover:bg-mint-500/30 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {refreshing ? "Refreshing…" : "Refresh news"}
          </button>
          {countdown > 0 && (
            <span className="text-xs text-gray-500">Next refresh in {countdown}s</span>
          )}
        </div>
      </div>

      {err && <p className="text-sm text-amber-400">{err}</p>}

      {data?.portfolioFocus && (
        <div className="rounded-xl border border-mint-500/25 bg-mint-500/5 p-5 space-y-4">
          <h2 className="font-display text-sm font-semibold text-mint-400">Where your money is concentrated</h2>
          <p className="text-sm text-gray-200 leading-relaxed">{data.portfolioFocus.allocationSummary}</p>
          {data.portfolioFocus.topStockSectors && data.portfolioFocus.topStockSectors.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Equity sectors (by value)</h3>
              <ul className="mt-2 space-y-1 text-sm text-gray-300">
                {data.portfolioFocus.topStockSectors.slice(0, 6).map((row) => (
                  <li key={row.sector} className="flex justify-between gap-4">
                    <span>{row.sector}</span>
                    <span className="shrink-0 text-gray-500">
                      {row.pctOfRiskAssets}% of stocks+MF · ₹{Math.round(row.value).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.portfolioFocus.topMfCategories && data.portfolioFocus.topMfCategories.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Mutual fund categories</h3>
              <ul className="mt-2 space-y-1 text-sm text-gray-300">
                {data.portfolioFocus.topMfCategories.slice(0, 6).map((row) => (
                  <li key={row.category} className="flex justify-between gap-4">
                    <span className="pr-2">{row.category}</span>
                    <span className="shrink-0 text-gray-500">
                      {row.pctOfRiskAssets}% of stocks+MF · ₹{Math.round(row.value).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.portfolioFocus.themeSearchPhrases && data.portfolioFocus.themeSearchPhrases.length > 0 && (
            <p className="text-xs text-gray-600">
              Search themes used for headlines: {data.portfolioFocus.themeSearchPhrases.join(" · ")}
            </p>
          )}
        </div>
      )}

      {data?.relatedPages && data.relatedPages.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-ink-900/60 p-4">
          <h2 className="text-sm font-semibold text-gray-400">Your stocks (quick links)</h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {data.relatedPages.map((l) => (
              <li key={l.url}>
                <a
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-mint-400 hover:underline"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data?.summary && (
        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-5">
          <h2 className="font-display text-sm font-semibold text-cyan-400">What this means for you</h2>
          <p className="mt-2 text-sm text-gray-200 whitespace-pre-wrap">{data.summary}</p>
        </div>
      )}

      {data?.fetchedAt && (
        <p className="text-xs text-gray-600">Last updated: {new Date(data.fetchedAt).toLocaleString()}</p>
      )}

      {!data?.fetchedAt && (!data?.articles || data.articles.length === 0) && (
        <p className="text-sm text-gray-500">
          No saved news yet. Press <strong className="text-gray-400">Refresh news</strong> to fetch headlines
          tailored to your portfolio.
        </p>
      )}

      <ul className="space-y-4">
        {(data?.articles || []).map((a, i) => (
          <li
            key={`${a.url}-${i}`}
            className="rounded-xl border border-gray-800 bg-ink-900/40 p-4 transition hover:border-gray-700"
          >
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-white hover:text-mint-400"
            >
              {a.title || "Untitled"}
            </a>
            {a.source && <span className="ml-2 text-xs text-gray-600">— {a.source}</span>}
            {a.description && <p className="mt-2 text-sm text-gray-400 line-clamp-3">{a.description}</p>}
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-xs text-mint-500/80 hover:text-mint-400"
            >
              Open article →
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
