import React, { useState, useEffect, useRef, useCallback } from "react";
import api from "../../utils/Api";

// ── Color helpers ────────────────────────────────────────────────────────────
const LOG_COLORS = {
  success: "text-emerald-400",
  error:   "text-red-400 font-bold",
  warning: "text-yellow-400",
  system:  "text-blue-400 font-bold",
  info:    "text-gray-200",
};

// ── Stat Card ─────────────────────────────────────────────────────────────────
const StatCard = ({ icon, label, value, sub, color = "green", pulse = false }) => (
  <div className="bg-gray-800/60 rounded-xl p-4 border border-gray-700/50 flex items-start gap-3">
    <div className={`p-2 rounded-lg bg-${color}-500/20 flex-shrink-0`}>
      <span className={`text-${color}-400 text-xl`}>{icon}</span>
    </div>
    <div>
      <p className="text-gray-400 text-xs font-medium">{label}</p>
      <p className={`text-white text-xl font-bold tabular-nums ${pulse ? "animate-pulse" : ""}`}>
        {typeof value === "number" ? value.toLocaleString("en-IN") : value}
      </p>
      {sub && <p className="text-gray-500 text-xs mt-0.5">{sub}</p>}
    </div>
  </div>
);

// ── Phase Badge ───────────────────────────────────────────────────────────────
const PhaseBadge = ({ phase }) => {
  const map = {
    resolving:  { label: "📂 Resolving Categories",     color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
    scraping:   { label: "🛒 Scraping Listings",        color: "bg-green-500/20 text-green-300 border-green-500/30" },
    completed:  { label: "✅ Complete",                color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
    idle:       { label: "⏸ Idle",                     color: "bg-gray-500/20 text-gray-400 border-gray-500/30" },
    error:      { label: "❌ Error",                    color: "bg-red-500/20 text-red-300 border-red-500/30" },
    running:    { label: "⚡ Running in Background",   color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
  };
  const info = map[phase] || map.idle;
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${info.color}`}>
      {info.label}
    </span>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
const IndiamartScrapper = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Task state
  const [taskId, setTaskId] = useState(null);
  const [taskData, setTaskData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [phase, setPhase] = useState("idle");

  // DB stats (live)
  const [dbStats, setDbStats] = useState({
    total_products: 0,
    total_categories: 0,
    distinct_brands: 0,
    available_products: 0,
    mapping_duplicates: 0,
    products_null_category_id: 0,
    top_categories: [],
    last_scrape_state: {},
  });

  // Session counters
  const [runStats, setRunStats] = useState({
    products_scraped: 0,
    products_inserted: 0,
    products_updated: 0,
    duplicates_prevented: 0,
    categories_synced: 0,
  });

  const pollRef = useRef(null);
  const logEndRef = useRef(null);
  const prevLogsLen = useRef(0);

  // ── Auto-scroll logs ───────────────────────────────────────────────────────
  useEffect(() => {
    if (logs.length !== prevLogsLen.current) {
      logEndRef.current?.scrollIntoView({ behavior: "smooth" });
      prevLogsLen.current = logs.length;
    }
  }, [logs]);

  // ── Fetch DB stats ─────────────────────────────────────────────────────────
  const fetchDbStats = useCallback(async () => {
    try {
      const res = await api.get("/scrape_indiamart/db-stats");
      setDbStats(res.data);
      const st = res.data.last_scrape_state || {};
      setRunStats({
        products_scraped: st.products_scraped || 0,
        products_inserted: st.products_inserted || 0,
        products_updated: st.products_updated || 0,
        duplicates_prevented: st.duplicates_prevented || 0,
        categories_synced: st.categories_synced || 0,
      });
    } catch (_) {}
  }, []);

  // ── Initial load ───────────────────────────────────────────────────────────
  useEffect(() => {
    fetchDbStats();
    
    // Check if there is an active running task for IndiaMart
    api.get("/tasks")
      .then(res => {
        const active = (res.data || []).find(t => t.platform === "IndiaMart" && t.status === "RUNNING");
        if (active) {
          setTaskId(active.id);
          setTaskData(active);
          setLoading(true);
          setPhase("running");
          startPolling(active.id);
        }
      })
      .catch(() => {});
  }, [fetchDbStats]);

  // ── Cleanup poll on unmount ────────────────────────────────────────────────
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // ── Log parser ─────────────────────────────────────────────────────────────
  const parseLogLine = (line) => {
    let type = "info";
    let msg = line;
    let ts = new Date().toLocaleTimeString("en-IN", { hour12: false });

    const parts = line.split(" | ");
    if (parts.length >= 3) {
      const tsMatch = parts[0].match(/\d{2}:\d{2}:\d{2}/);
      if (tsMatch) ts = tsMatch[0];
      const level = (parts[1] || "").trim();
      msg = parts.slice(2).join(" | ");
      if (["ERROR", "CRITICAL"].includes(level)) type = "error";
      else if (level === "WARNING") type = "warning";
      else if (msg.includes("SUCCESS") || msg.includes("complete") || msg.includes("COMPLETE")) type = "success";
      else if (msg.includes("START") || msg.includes("===") || msg.includes("Resolving")) type = "system";
    } else {
      const u = line.toUpperCase();
      if (u.includes("ERROR") || u.includes("FAILED") || u.includes("FATAL") || u.includes("SIGNATURE VERIFICATION")) type = "error";
      else if (u.includes("SUCCESS") || u.includes("COMPLETED")) type = "success";
      else if (u.includes("WARNING") || u.includes("SKIP")) type = "warning";
      else if (line.startsWith("===") || line.includes("Processing:") || line.includes("[Config")) type = "system";
    }
    return { ts, msg, type };
  };

  // ── Start polling for task updates ─────────────────────────────────────────
  const startPolling = (tid) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        // Task status
        const taskRes = await api.get(`/tasks/${tid}`);
        const task = taskRes.data;
        setTaskData(task);

        // Logs
        try {
          const logRes = await api.get(`/tasks/${tid}/logs`);
          const lines = logRes.data.logs || [];
          if (lines.length > 0) {
            setLogs(lines.map(parseLogLine));

            // Extract real-time counters from log lines
            let scraped = 0, inserted = 0, updated = 0, prevented = 0;
            lines.forEach(line => {
              if (line.includes("Run completed:")) {
                const insertMatch = line.match(/(\d+)\s+inserted/);
                const updateMatch = line.match(/(\d+)\s+updated/);
                const preventMatch = line.match(/Duplicates\s+Prevented:\s*(\d+)/);
                if (insertMatch) inserted = parseInt(insertMatch[1]);
                if (updateMatch) updated = parseInt(updateMatch[1]);
                if (preventMatch) prevented = parseInt(preventMatch[1]);
                scraped = inserted + updated;
              } else if (line.includes("Database Sync:")) {
                const ingestMatch = line.match(/Ingested\s+(\d+)\/(\d+)/);
                if (ingestMatch) {
                  scraped = parseInt(ingestMatch[1]);
                  inserted = scraped;
                }
              }
            });

            if (scraped > 0 || inserted > 0 || updated > 0 || prevented > 0) {
              setRunStats({
                products_scraped: scraped,
                products_inserted: inserted,
                products_updated: updated,
                duplicates_prevented: prevented,
                categories_synced: categoriesListCount(lines),
              });
            }
          }
        } catch (_) {}

        // DB stats
        fetchDbStats();

        // Phase detection
        if (task.status) {
          const st = task.status.toLowerCase();
          if (st.includes("resolv") || st.includes("categor")) setPhase("resolving");
          else if (st.includes("scrap") || st.includes("sync")) setPhase("scraping");
          else if (st === "completed") setPhase("completed");
          else if (st === "error") setPhase("error");
          else if (st === "running") setPhase("running");
        }

        // Stop polling on terminal states
        if (["COMPLETED", "ERROR", "STOPPED"].includes(task.status)) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setLoading(false);
          fetchDbStats();

          const finalMsg = task.status === "COMPLETED"
            ? `✅ IndiaMART scrape COMPLETED! ${task.total_leads || 0} products processed.`
            : `❌ Scraper ${task.status}: ${task.error_message || "Unknown execution error"}`;
          setLogs(prev => [...prev, {
            ts: new Date().toLocaleTimeString("en-IN"),
            msg: finalMsg,
            type: task.status === "COMPLETED" ? "success" : "error",
          }]);
        }
      } catch (_) {}
    }, 2500);
  };

  const categoriesListCount = (lines) => {
    let count = 0;
    lines.forEach(line => {
      if (line.includes("Category nodes synced successfully")) {
        count += 1;
      }
    });
    return count;
  };

  // ── Handle Scrape ──────────────────────────────────────────────────────────
  const handleScrape = async () => {
    if (!searchTerm.trim()) {
      setError("Please specify a valid B2B search term.");
      return;
    }

    setError("");
    setLogs([]);
    setPhase("resolving");
    setLoading(true);

    const addLog = (msg, type = "system") =>
      setLogs(prev => [...prev, { ts: new Date().toLocaleTimeString("en-IN"), msg, type }]);

    addLog(`[SYSTEM] Initializing Playwright Stealth Browser...`);
    addLog(`[CONFIG] Query: "${searchTerm.trim()}" | Page Crawl Limit: ${pages}`);
    addLog(`[INFO] Scraper running in background — you can continue using the dashboard.`, "success");

    try {
      addLog(`[API] Dispatching IndiaMART background scraper job...`);
      const res = await api.post("/scrape_indiamart", {
        search_term: searchTerm.trim(),
        pages: parseInt(pages) || 1,
      });

      const { task_id, message } = res.data;
      setTaskId(task_id);
      setPhase("running");
      addLog(`[SYSTEM] Task started! Task ID: #${task_id}`, "success");
      addLog(`[INFO] ${message}`, "info");
      startPolling(task_id);

    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.error || "Failed to start IndiaMART scraper.";
      setError(msg);
      addLog(`[ERROR] ${msg}`, "error");
      setLoading(false);
      setPhase("error");
    }
  };

  // ── Handle Stop ────────────────────────────────────────────────────────────
  const handleStop = async () => {
    try {
      await api.post("/stop", { task_id: taskId });
      setLogs(prev => [...prev, {
        ts: new Date().toLocaleTimeString("en-IN"),
        msg: "[SYSTEM] Stop signal sent to scraper.",
        type: "warning",
      }]);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      setLoading(false);
      setPhase("idle");
    } catch (err) {
      setError(err.response?.data?.error || "Failed to stop scraper.");
    }
  };

  const progress = taskData?.progress || 0;
  const totalFound = taskData?.total_leads || 0;

  return (
    <div className="min-h-screen p-6 space-y-6"
         style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)" }}>

      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4
                      bg-white/5 backdrop-blur-sm p-6 rounded-2xl border border-white/10 shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shadow-lg"
               style={{ background: "linear-gradient(135deg, #0ea5e9, #0284c7)" }}>
            🏢
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2 flex-wrap">
              IndiaMART B2B Automation
              <PhaseBadge phase={phase} />
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              SEO crawler · Bypasses OTP registration gate · Dynamic Category Mapping · Deduplication by ASIN
            </p>
            {loading && (
              <p className="text-yellow-400 text-xs mt-1 animate-pulse">
                ⚡ Scraper is running in the background — dashboard is fully usable
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">DB Products</p>
            <p className="text-sky-400 font-bold text-lg">{dbStats.total_products.toLocaleString("en-IN")}</p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">Categories</p>
            <p className="text-teal-400 font-bold text-lg">{dbStats.total_categories.toLocaleString("en-IN")}</p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">Suppliers</p>
            <p className="text-orange-400 font-bold text-lg">{dbStats.distinct_brands.toLocaleString("en-IN")}</p>
          </div>
        </div>
      </div>

      {/* ── Progress Bar ── */}
      {loading && (
        <div className="bg-white/5 backdrop-blur-sm rounded-xl border border-white/10 p-4 space-y-2">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Overall Scraping Progress</span>
            <span className="text-white font-bold">{progress}% — {totalFound.toLocaleString("en-IN")} products found</span>
          </div>
          <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progress}%`,
                background: "linear-gradient(90deg, #0ea5e9, #0284c7)",
                boxShadow: "0 0 12px rgba(14,165,233,0.5)",
              }}
            />
          </div>
          <p className="text-sky-400 text-xs font-mono animate-pulse">
            {taskData?.status || "Running background tasks..."} · Task #{taskId}
          </p>
        </div>
      )}

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ── LEFT: Control Panel ── */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-5 space-y-5">
            <h2 className="text-white font-bold text-base flex items-center gap-2">🎛️ Control Panel</h2>

            {/* B2B Query */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                B2B Query / Category Slugs
              </label>
              <input
                type="text"
                placeholder="e.g. angular contact bearing"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-sky-500 transition placeholder-gray-600"
              />
              <p className="text-gray-500 text-xs mt-1.5">
                OTP registration login wall is bypassed using dynamic category resolution. Use queries representing standard product groups.
              </p>
            </div>

            {/* Scope Limit */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Scope Limit (Paging Depth)
              </label>
              <input
                type="number"
                min="1"
                placeholder="Number of pages (e.g. 1)"
                value={pages}
                onChange={e => setPages(Math.max(1, parseInt(e.target.value) || 1))}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-yellow-500 transition placeholder-gray-600"
              />
              <p className="text-gray-500 text-xs mt-1">Each page retrieves around 20-30 supplier listings.</p>
            </div>

            {/* Action Button */}
            <div className="space-y-2 pt-1">
              {!loading ? (
                <button
                  onClick={handleScrape}
                  className="w-full py-3.5 rounded-xl text-white font-bold text-sm flex items-center justify-center gap-2 transition hover:opacity-90 active:scale-95"
                  style={{ background: "linear-gradient(135deg, #0ea5e9, #0284c7)" }}
                >
                  <span>🚀</span> Start IndiaMART Scraper
                </button>
              ) : (
                <>
                  <div className="text-xs text-gray-400 bg-gray-800/40 rounded-xl p-3 border border-gray-700/50 text-center">
                    <p className="text-yellow-400 font-semibold mb-1">⚡ Scraper running in background</p>
                    <p>You can browse the system; the worker task will keep running.</p>
                  </div>
                  <button
                    onClick={handleStop}
                    className="w-full py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30"
                  >
                    <span className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                    Stop Scraper
                  </button>
                </>
              )}
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3">
                <p className="text-red-400 text-xs font-semibold">⚠️ {error}</p>
              </div>
            )}
          </div>

          {/* ── Integrity Report ── */}
          <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-4 space-y-3">
            <h3 className="text-white font-bold text-sm flex items-center gap-2">🛡️ Integrity Report</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center py-1.5 border-b border-gray-800">
                <span className="text-gray-400">Mapping duplicates</span>
                <span className={`font-bold ${dbStats.mapping_duplicates > 0 ? "text-red-400" : "text-green-400"}`}>
                  {dbStats.mapping_duplicates > 0 ? `⚠️ ${dbStats.mapping_duplicates}` : "✅ 0"}
                </span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-800">
                <span className="text-gray-400">Unmapped mapping entries</span>
                <span className="text-white font-bold">{dbStats.products_null_category_id}</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-800">
                <span className="text-gray-400">Products in DB</span>
                <span className="text-white font-bold">{dbStats.total_products.toLocaleString("en-IN")}</span>
              </div>
              <div className="flex justify-between items-center py-1.5">
                <span className="text-gray-400">Priced products</span>
                <span className="text-green-400 font-bold">{dbStats.available_products.toLocaleString("en-IN")}</span>
              </div>
            </div>
          </div>

          {/* ── Top Categories ── */}
          {dbStats.top_categories.length > 0 && (
            <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-4">
              <h3 className="text-white font-bold text-sm mb-3">📊 Top Ingested Categories</h3>
              <div className="space-y-1.5">
                {dbStats.top_categories.slice(0, 8).map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-full bg-gray-800 rounded-full h-1.5 flex-1">
                      <div
                        className="h-1.5 rounded-full bg-gradient-to-r from-sky-500 to-sky-600"
                        style={{ width: `${Math.min(100, (c.count / (dbStats.top_categories[0]?.count || 1)) * 100)}%` }}
                      />
                    </div>
                    <span className="text-gray-400 text-xs w-36 truncate text-right" title={c.category}>{c.category}</span>
                    <span className="text-gray-500 text-xs w-14 text-right">{c.count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT: Stats + Terminal ── */}
        <div className="lg:col-span-8 flex flex-col gap-4">

          {/* Live Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <StatCard icon="🛒" label="Items Parsed" value={runStats.products_scraped}
                      pulse={loading} color="sky" sub="this run" />
            <StatCard icon="✨" label="New Insertions" value={runStats.products_inserted}
                      pulse={loading} color="teal" sub="brand new items" />
            <StatCard icon="♻️" label="Updated (Prices/Seller)" value={runStats.products_updated}
                      color="purple" sub="existing products" />
            <StatCard icon="🛡️" label="Duplicates Prevented"
                      value={runStats.duplicates_prevented || "✓ None"}
                      color={runStats.duplicates_prevented > 0 ? "green" : "teal"} />
            <StatCard icon="📂" label="Categories Resolved" value={runStats.categories_synced}
                      color="yellow" sub="to indiamart_mappings" />
            <StatCard icon="📦" label="Total IndiaMART Products" value={dbStats.total_products}
                      color="indigo" sub="indiamart_products table" />
          </div>

          {/* ── Terminal ── */}
          <div className="flex-1 rounded-2xl overflow-hidden border border-gray-700/50 shadow-2xl"
               style={{ background: "#0d1117" }}>
            {/* Terminal Header */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900 border-b border-gray-700/50">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="text-gray-500 text-xs font-mono ml-2">indiamart-scraper@worker</span>
              </div>
              <div className="flex items-center gap-2">
                {taskId && (
                  <span className="text-gray-500 text-xs font-mono">task #{taskId}</span>
                )}
                <span className={`text-xs font-bold px-2 py-0.5 rounded font-mono border ${
                  loading
                    ? "text-sky-400 border-sky-500/30 bg-sky-500/10"
                    : "text-gray-500 border-gray-600/30 bg-gray-800"
                }`}>
                  {loading ? "● LIVE" : "○ IDLE"}
                </span>
              </div>
            </div>

            {/* Terminal Body */}
            <div className="h-[420px] overflow-y-auto p-4 space-y-1 font-mono text-xs" id="terminal-body">
              {logs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-3">
                  <span className="text-4xl">🤖</span>
                  <p className="text-center">IndiaMART Scraper Engine ready.</p>
                  <p className="text-center text-gray-700">Enter a B2B product query and click <strong className="text-gray-500">Start IndiaMART Scraper</strong> to begin.</p>
                  <p className="text-center text-gray-700 text-xs">The scraper runs in the background — you can continue using other dashboard features while it runs.</p>
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-gray-600 select-none flex-shrink-0">[{log.ts}]</span>
                    <span className={LOG_COLORS[log.type] || "text-gray-200"}>{log.msg}</span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          {/* Scrape History */}
          <RecentHistory />
        </div>
      </div>
    </div>
  );
};

// ── Recent Scrape History ─────────────────────────────────────────────────────
const RecentHistory = () => {
  const [history, setHistory] = useState([]);
  useEffect(() => {
    api.get("/tasks")
      .then(r => {
        const platformTasks = (r.data || [])
          .filter(t => t.platform === "IndiaMart")
          .slice(0, 5);
        setHistory(platformTasks);
      })
      .catch(() => {});
  }, []);

  if (!history.length) return null;

  return (
    <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-4">
      <h3 className="text-white font-bold text-sm mb-3">🕐 Recent Scrape History</h3>
      <div className="space-y-1.5">
        {history.map(t => (
          <div key={t.id}
               className="flex items-center justify-between text-xs bg-gray-800/50 rounded-xl px-4 py-2.5 border border-gray-700/30">
            <span className="text-gray-400 font-mono">#{t.id}</span>
            <span className="text-gray-300 flex-1 mx-4 truncate">{t.query}</span>
            <span className="text-sky-400 font-mono mr-4">{(t.total_leads || 0).toLocaleString("en-IN")} products</span>
            <span className={`px-2 py-0.5 rounded-full font-bold ${
              t.status === "COMPLETED" ? "bg-green-500/20 text-green-400" :
              t.status === "ERROR"     ? "bg-red-500/20 text-red-400" :
              t.status === "RUNNING"   ? "bg-yellow-500/20 text-yellow-400" :
                                          "bg-gray-600/20 text-gray-400"
            }`}>
              {t.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default IndiamartScrapper;