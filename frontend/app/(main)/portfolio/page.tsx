"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";

type Stock = { ticker: string; name?: string; qty: number; buyPrice: number; buyDate?: string };
type MF = { amfiCode?: string; isin?: string; name?: string; units: number; buyNav: number; buyDate?: string };
type StockHit = { ticker: string; name: string };
type MFHit = { code: string; name: string };

export default function PortfolioPage() {
  const { token } = useAuth();
  const [cash, setCash] = useState(0);

  const [stockQuery, setStockQuery] = useState("");
  const [stockHits, setStockHits] = useState<StockHit[]>([]);
  const [selectedTicker, setSelectedTicker] = useState("");
  const [selectedStockName, setSelectedStockName] = useState("");
  const [qty, setQty] = useState(1);
  const [buy, setBuy] = useState(0);
  const [stockDate, setStockDate] = useState("");

  const [mfQuery, setMfQuery] = useState("");
  const [mfHits, setMfHits] = useState<MFHit[]>([]);
  const [mfIsinInput, setMfIsinInput] = useState("");
  const [selectedAmfi, setSelectedAmfi] = useState("");
  const [selectedIsin, setSelectedIsin] = useState("");
  const [selectedMfName, setSelectedMfName] = useState("");
  const [units, setUnits] = useState(1);
  const [nav, setNav] = useState(0);
  const [mfDate, setMfDate] = useState("");

  const [stocks, setStocks] = useState<Stock[]>([]);
  const [mfs, setMfs] = useState<MF[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [casParsing, setCasParsing] = useState(false);
  const [casResult, setCasResult] = useState<{ parsed: Array<{ amfiCode?: string; isin?: string; name: string; units: number; buyNav: number; marketValue: number }>; imported: number; skipped_existing: number; total_cost?: number; total_market_value?: number } | null>(null);

  const stockTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mfTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<{ cash: number; stocks: Stock[]; mutualFunds: MF[] }>("/portfolio", token)
      .then((p) => {
        setCash(p.cash ?? 0);
        setStocks(p.stocks || []);
        setMfs(p.mutualFunds || []);
      })
      .catch(() => {});
  }, [token]);

  const searchStocks = useCallback(
    (q: string) => {
      if (!token || q.trim().length < 2) { setStockHits([]); return; }
      apiFetch<{ results: StockHit[] }>(`/portfolio/search?q=${encodeURIComponent(q.trim())}&asset_type=stock`, token)
        .then((r) => setStockHits(r.results || []))
        .catch(() => setStockHits([]));
    },
    [token],
  );

  const searchMfs = useCallback(
    (q: string) => {
      if (!token || q.trim().length < 2) { setMfHits([]); return; }
      apiFetch<{ results: MFHit[] }>(`/portfolio/search?q=${encodeURIComponent(q.trim())}&asset_type=mutual_fund`, token)
        .then((r) => setMfHits(r.results || []))
        .catch(() => setMfHits([]));
    },
    [token],
  );

  function onStockQueryChange(v: string) {
    setStockQuery(v);
    setSelectedTicker("");
    setSelectedStockName("");
    if (stockTimer.current) clearTimeout(stockTimer.current);
    stockTimer.current = setTimeout(() => searchStocks(v), 300);
  }

  function pickStock(h: StockHit) {
    setSelectedTicker(h.ticker);
    setSelectedStockName(h.name);
    setStockQuery(`${h.name} (${h.ticker})`);
    setStockHits([]);
  }

  function onMfQueryChange(v: string) {
    setMfQuery(v);
    setSelectedAmfi("");
    setSelectedMfName("");
    setSelectedIsin("");
    setMfIsinInput("");
    if (mfTimer.current) clearTimeout(mfTimer.current);
    mfTimer.current = setTimeout(() => searchMfs(v), 300);
  }

  function pickMf(h: MFHit) {
    setSelectedAmfi(h.code);
    setSelectedMfName(h.name);
    setSelectedIsin("");
    setMfIsinInput("");
    setMfQuery(`${h.name} (${h.code})`);
    setMfHits([]);
  }

  async function lookupMfIsin() {
    if (!token) return;
    const raw = mfIsinInput.trim().toUpperCase();
    if (!raw.startsWith("IN") || raw.length !== 12) {
      setErr("Enter a 12-character ISIN (e.g. INF247L01445).");
      return;
    }
    setErr("");
    try {
      const r = await apiFetch<{
        valid: boolean;
        name?: string;
        currentPrice?: number;
        amfiCode?: string;
        isin?: string;
        error?: string;
      }>(
        `/portfolio/validate?symbol=${encodeURIComponent(raw)}&asset_type=mutual_fund`,
        token,
      );
      if (!r.valid) {
        setErr(r.error || "ISIN not found.");
        return;
      }
      setSelectedIsin(raw);
      setSelectedMfName(r.name || raw);
      if (r.amfiCode) setSelectedAmfi(String(r.amfiCode));
      else setSelectedAmfi("");
      if (r.currentPrice != null) setNav(r.currentPrice);
      setMfQuery("");
      setMfHits([]);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Lookup failed");
    }
  }

  async function saveAll() {
    if (!token) return;
    setErr(""); setMsg("");
    try {
      await apiFetch("/portfolio", token, {
        method: "PUT",
        body: JSON.stringify({
          cash,
          stocks: stocks.map((s) => ({
            ticker: s.ticker, qty: s.qty, buy_price: s.buyPrice,
            ...(s.buyDate ? { buy_date: s.buyDate } : {}),
          })),
          mutual_funds: mfs.map((m) => ({
            ...(m.isin ? { isin: m.isin } : {}),
            ...(m.amfiCode ? { amfi_code: m.amfiCode } : {}),
            units: m.units,
            buy_nav: m.buyNav,
            ...(m.buyDate ? { buy_date: m.buyDate } : {}),
          })),
        }),
      });
      setMsg("Portfolio saved.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  function addStock() {
    if (!selectedTicker || buy <= 0) return;
    setStocks([...stocks, {
      ticker: selectedTicker,
      name: selectedStockName || undefined,
      qty, buyPrice: buy,
      buyDate: stockDate || undefined,
    }]);
    setStockQuery(""); setSelectedTicker(""); setSelectedStockName("");
    setQty(1); setBuy(0); setStockDate("");
  }

  function removeStock(i: number) { setStocks(stocks.filter((_, idx) => idx !== i)); }

  function addMf() {
    if (!(selectedAmfi || selectedIsin) || nav <= 0) return;
    setMfs([
      ...mfs,
      {
        ...(selectedIsin ? { isin: selectedIsin } : {}),
        ...(selectedAmfi ? { amfiCode: selectedAmfi } : {}),
        name: selectedMfName || undefined,
        units,
        buyNav: nav,
        buyDate: mfDate || undefined,
      },
    ]);
    setMfQuery("");
    setMfIsinInput("");
    setSelectedAmfi("");
    setSelectedIsin("");
    setSelectedMfName("");
    setUnits(1);
    setNav(0);
    setMfDate("");
  }

  function removeMf(i: number) { setMfs(mfs.filter((_, idx) => idx !== i)); }

  function onCasFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f || !token) return;
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const json = JSON.parse(String(reader.result));
        await apiFetch("/portfolio/cas", token, {
          method: "POST",
          body: JSON.stringify({
            cash: json.cash ?? 0,
            stocks: (json.stocks || []).map(
              (s: { ticker: string; qty: number; buy_price?: number; buyPrice?: number }) => ({
                ticker: s.ticker, qty: s.qty, buy_price: s.buy_price ?? s.buyPrice ?? 0,
              }),
            ),
            mutual_funds: (json.mutual_funds || json.mutualFunds || []).map(
              (m: {
                isin?: string;
                amfi_code?: string;
                amfiCode?: string;
                units: number;
                buy_nav?: number;
                buyNav?: number;
              }) => ({
                ...(m.isin ? { isin: String(m.isin).trim().toUpperCase() } : {}),
                amfi_code: m.amfi_code ?? m.amfiCode ?? "",
                units: m.units,
                buy_nav: m.buy_nav ?? m.buyNav ?? 0,
              }),
            ),
          }),
        });
        setMsg("CAS imported.");
        const p = await apiFetch<{ cash: number; stocks: Stock[]; mutualFunds: MF[] }>("/portfolio", token);
        setCash(p.cash ?? 0); setStocks(p.stocks || []); setMfs(p.mutualFunds || []);
      } catch { setErr("Invalid JSON CAS file."); }
    };
    reader.readAsText(f);
  }

  const inputCls = "rounded-md border border-gray-700 bg-ink-950 px-2 py-1.5 text-sm text-white";

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="font-display text-3xl font-bold text-white">Portfolio</h1>

      {/* Cash */}
      <section className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Cash</h2>
        <input
          type="number"
          className="mt-2 w-full rounded-md border border-gray-700 bg-ink-950 px-3 py-2 text-white"
          value={cash}
          onChange={(e) => setCash(Number(e.target.value))}
        />
      </section>

      {/* Stocks */}
      <section className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Stocks</h2>
        <div className="mt-4 space-y-2">
          <div className="flex flex-wrap gap-2">
            <div className="relative flex-1 min-w-[180px]">
              <input
                placeholder="Search by name or ticker (e.g. Reliance, TCS)"
                className={`w-full ${inputCls} ${selectedTicker ? "border-green-600" : ""}`}
                value={stockQuery}
                onChange={(e) => onStockQueryChange(e.target.value)}
              />
              {selectedTicker && (
                <p className="mt-1 text-xs text-green-500">{selectedStockName} ({selectedTicker})</p>
              )}
              {stockHits.length > 0 && !selectedTicker && (
                <ul className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-gray-700 bg-ink-950 shadow-lg">
                  {stockHits.map((h) => (
                    <li key={h.ticker}>
                      <button type="button" onClick={() => pickStock(h)} className="w-full px-3 py-2 text-left text-sm text-gray-200 hover:bg-ink-900">
                        {h.name} <span className="text-gray-500">({h.ticker})</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <input type="number" placeholder="Qty" className={`w-20 ${inputCls}`} value={qty} onChange={(e) => setQty(Number(e.target.value))} />
            <input type="number" placeholder="Buy ₹" className={`w-24 ${inputCls}`} value={buy || ""} onChange={(e) => setBuy(Number(e.target.value))} />
            <input type="date" className={`w-36 ${inputCls}`} value={stockDate} onChange={(e) => setStockDate(e.target.value)} title="Purchase date" />
            <button
              type="button"
              onClick={addStock}
              disabled={!selectedTicker || buy <= 0}
              className="rounded-md bg-gray-700 px-3 py-1.5 text-sm text-white disabled:opacity-40"
            >
              Add
            </button>
          </div>
        </div>
        <ul className="mt-4 space-y-2 text-sm text-gray-400">
          {stocks.map((s, i) => (
            <li key={i} className="flex items-center justify-between rounded-md border border-gray-800 bg-ink-950/50 px-3 py-2">
              <span>
                <span className="font-medium text-white">{s.name || s.ticker}</span>
                {s.name && <span className="ml-1 text-gray-600">({s.ticker})</span>}
                {" "}× {s.qty} @ ₹{s.buyPrice}
                {s.buyDate && <span className="ml-2 text-gray-600">· {s.buyDate}</span>}
              </span>
              <button type="button" onClick={() => removeStock(i)} className="ml-3 text-red-500 hover:text-red-400 text-xs">Remove</button>
            </li>
          ))}
        </ul>
      </section>

      {/* Mutual Funds */}
      <section className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Mutual funds</h2>
        <p className="mt-1 text-xs text-gray-500">
          Prefer ISIN for daily NAV (AMFI). You can also search by fund name — AMFI code is stored when available.
        </p>
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            <label className="block min-w-[200px] flex-1 text-xs text-gray-500">
              ISIN
              <input
                placeholder="e.g. INF247L01445"
                className={`mt-1 w-full ${inputCls} ${selectedIsin ? "border-green-600" : ""}`}
                value={mfIsinInput}
                onChange={(e) => {
                  setMfIsinInput(e.target.value.toUpperCase());
                  setSelectedAmfi("");
                  setSelectedIsin("");
                  setSelectedMfName("");
                  setMfQuery("");
                }}
              />
            </label>
            <button
              type="button"
              onClick={lookupMfIsin}
              className="rounded-md border border-gray-600 bg-ink-900 px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-800"
            >
              Look up NAV
            </button>
          </div>
          <p className="text-xs text-gray-600">— or search —</p>
          <div className="flex flex-wrap gap-2">
            <div className="relative flex-1 min-w-[180px]">
              <input
                placeholder="Search by fund name or AMFI code"
                className={`w-full ${inputCls} ${selectedAmfi && !selectedIsin ? "border-green-600" : ""}`}
                value={mfQuery}
                onChange={(e) => onMfQueryChange(e.target.value)}
              />
              {(selectedAmfi || selectedIsin) && (
                <p className="mt-1 text-xs text-green-500">
                  {selectedMfName}
                  {selectedIsin && <span className="ml-1">· {selectedIsin}</span>}
                  {selectedAmfi && <span className="ml-1">({selectedAmfi})</span>}
                </p>
              )}
              {mfHits.length > 0 && !selectedAmfi && !selectedIsin && (
                <ul className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-gray-700 bg-ink-950 shadow-lg">
                  {mfHits.map((h) => (
                    <li key={h.code}>
                      <button type="button" onClick={() => pickMf(h)} className="w-full px-3 py-2 text-left text-sm text-gray-200 hover:bg-ink-900">
                        {h.name} <span className="text-gray-500">({h.code})</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <input type="number" placeholder="Units" className={`w-20 ${inputCls}`} value={units} onChange={(e) => setUnits(Number(e.target.value))} />
            <input type="number" placeholder="Buy NAV" className={`w-24 ${inputCls}`} value={nav || ""} onChange={(e) => setNav(Number(e.target.value))} />
            <input type="date" className={`w-36 ${inputCls}`} value={mfDate} onChange={(e) => setMfDate(e.target.value)} title="Purchase date" />
            <button
              type="button"
              onClick={addMf}
              disabled={!(selectedAmfi || selectedIsin) || nav <= 0}
              className="rounded-md bg-gray-700 px-3 py-1.5 text-sm text-white disabled:opacity-40"
            >
              Add
            </button>
          </div>
        </div>
        <ul className="mt-4 space-y-2 text-sm text-gray-400">
          {mfs.map((m, i) => (
            <li key={`${m.isin || ""}-${m.amfiCode || ""}-${i}`} className="flex items-center justify-between rounded-md border border-gray-800 bg-ink-950/50 px-3 py-2">
              <span>
                <span className="font-medium text-white">{m.name || m.amfiCode || m.isin}</span>
                {m.isin && <span className="ml-1 text-gray-600">ISIN {m.isin}</span>}
                {m.amfiCode && <span className="ml-1 text-gray-600">({m.amfiCode})</span>}
                {" "}— {m.units} units @ ₹{m.buyNav}
                {m.buyDate && <span className="ml-2 text-gray-600">· {m.buyDate}</span>}
              </span>
              <button type="button" onClick={() => removeMf(i)} className="ml-3 text-red-500 hover:text-red-400 text-xs">Remove</button>
            </li>
          ))}
        </ul>
      </section>

      {/* CAS Import */}
      <section className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <h2 className="font-medium text-mint-400">Import CAS Statement</h2>
        <p className="mt-1 text-sm text-gray-500">
          Upload your Consolidated Account Statement (CAS) PDF from CAMS/KFintech.
          AI will extract your mutual fund holdings automatically.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-gray-600 bg-ink-950/50 px-4 py-3 text-sm text-gray-300 hover:border-mint-500/60 hover:text-white">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
            {casParsing ? "Parsing…" : "Upload PDF"}
            <input
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              disabled={casParsing}
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f || !token) return;
                setCasParsing(true);
                setCasResult(null);
                setErr("");
                setMsg("");
                try {
                  const formData = new FormData();
                  formData.append("file", f);
                  const root = typeof window !== "undefined" && window.location.hostname.includes("run.app")
                    ? `${window.location.origin}/api`
                    : process.env.NEXT_PUBLIC_API_URL || "";
                  const res = await fetch(`${root}/portfolio/cas-pdf`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                    body: formData,
                  });
                  if (!res.ok) {
                    const t = await res.text();
                    throw new Error(t || res.statusText);
                  }
                  const result = await res.json();
                  setCasResult(result);
                  setMsg(`Imported ${result.imported} fund(s) from CAS.`);
                  const p = await apiFetch<{ cash: number; stocks: Stock[]; mutualFunds: MF[] }>("/portfolio", token);
                  setCash(p.cash ?? 0);
                  setStocks(p.stocks || []);
                  setMfs(p.mutualFunds || []);
                } catch (ex: unknown) {
                  setErr(ex instanceof Error ? ex.message : "Failed to parse CAS PDF.");
                } finally {
                  setCasParsing(false);
                  e.target.value = "";
                }
              }}
            />
          </label>
          {casParsing && <span className="text-sm text-gray-400 animate-pulse">Analyzing PDF with AI…</span>}
        </div>

        {casResult && casResult.parsed.length > 0 && (
          <div className="mt-4">
            <p className="text-sm text-gray-400 mb-2">
              Found {casResult.parsed.length} fund(s) — {casResult.imported} imported, {casResult.skipped_existing} already existed.
              {casResult.total_cost != null && (
                <span className="ml-2">Total cost: ₹{casResult.total_cost.toLocaleString()}</span>
              )}
              {casResult.total_market_value != null && (
                <span className="ml-2">· Market value: ₹{casResult.total_market_value.toLocaleString()}</span>
              )}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-800 text-left text-gray-500">
                    <th className="pb-2 pr-3">Scheme</th>
                    <th className="pb-2 pr-3 text-right">Units</th>
                    <th className="pb-2 pr-3 text-right">Avg. Cost/Unit</th>
                    <th className="pb-2 text-right">Market Value</th>
                  </tr>
                </thead>
                <tbody>
                  {casResult.parsed.map((h, i) => (
                    <tr key={i} className="border-b border-gray-800/50">
                      <td className="py-1.5 pr-3 text-gray-300">
                        {h.name || h.isin || h.amfiCode}
                        {h.isin && <span className="ml-1 block text-gray-600">{h.isin}</span>}
                      </td>
                      <td className="py-1.5 pr-3 text-right text-gray-400">{h.units.toFixed(3)}</td>
                      <td className="py-1.5 pr-3 text-right text-gray-400">₹{h.buyNav.toFixed(2)}</td>
                      <td className="py-1.5 text-right text-white">₹{h.marketValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Legacy JSON CAS */}
      <details className="rounded-xl border border-gray-800 bg-ink-900/60 p-6">
        <summary className="cursor-pointer font-medium text-gray-500 text-sm">Advanced: Import JSON CAS</summary>
        <p className="mt-2 text-sm text-gray-500">Choose a JSON file with cash, stocks, mutual_funds — parsed in browser only.</p>
        <input type="file" accept=".json,application/json" className="mt-2 text-sm text-gray-400" onChange={onCasFile} />
      </details>

      {err && <p className="text-sm text-red-400">{err}</p>}
      {msg && <p className="text-sm text-mint-400">{msg}</p>}
      <button type="button" onClick={saveAll} className="rounded-lg bg-mint-500 px-6 py-2.5 font-medium text-ink-950 hover:bg-mint-400">
        Save portfolio
      </button>
    </div>
  );
}
