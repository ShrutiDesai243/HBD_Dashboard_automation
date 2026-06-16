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

const PINCODE_OPTIONS = [
  { label: "Delhi (110001)",      value: "110001" },
  { label: "Mumbai (400001)",     value: "400001" },
  { label: "Bangalore (560001)",  value: "560001" },
  { label: "Chennai (600001)",    value: "600001" },
  { label: "Kolkata (700001)",    value: "700001" },
  { label: "Hyderabad (500001)",  value: "500001" },
  { label: "Ahmedabad (380001)",  value: "380001" },
  { label: "Pune (411001)",       value: "411001" },
];

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
    categories: { label: "📂 Discovering Categories", color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
    products:   { label: "🛒 Scraping Products",       color: "bg-green-500/20 text-green-300 border-green-500/30" },
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

// ── Category Multi-Select ─────────────────────────────────────────────────────
const CategorySelect = ({ categories, selected, onChange, disabled }) => {
  const [open, setOpen] = useState(false);

  const toggle = (name) => {
    if (selected.includes(name)) {
      onChange(selected.filter(s => s !== name));
    } else {
      onChange([...selected, name]);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen(o => !o)}
        disabled={disabled}
        className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 text-left outline-none focus:border-green-500 transition flex items-center justify-between"
      >
        <span className={selected.length === 0 ? "text-gray-500" : "text-green-300"}>
          {selected.length === 0 ? "All categories (recommended)" : `${selected.length} selected`}
        </span>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>
      {open && !disabled && (
        <div className="absolute z-50 w-full mt-1 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl max-h-64 overflow-y-auto">
          <div className="p-2">
            <button
              onClick={() => onChange([])}
              className="w-full text-left text-xs px-3 py-2 rounded-lg text-gray-400 hover:bg-gray-800 mb-1"
            >
              ✨ Clear (all categories)
            </button>
            {categories.map(cat => (
              <label
                key={cat.id}
                className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-800 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(cat.name)}
                  onChange={() => toggle(cat.name)}
                  className="accent-green-500"
                />
                <span className="text-white text-xs flex-1">{cat.name}</span>
                <span className="text-gray-600 text-xs">{cat.product_count?.toLocaleString()}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
const BlinkitScrapper = () => {
  // Controls
  const [pincode,             setPincode]            = useState("110001");
  const [mode,                setMode]               = useState("full");
  const [maxCategories,       setMaxCategories]      = useState("");
  const [resume,              setResume]             = useState(false);
  const [selectedCategories,  setSelectedCategories] = useState([]);
  const [loading,             setLoading]            = useState(false);
  const [error,               setError]              = useState("");

  // Categories list for filter UI
  const [categoriesList, setCategoriesList] = useState([]);

  // Task state
  const [taskId,   setTaskId]   = useState(null);
  const [taskData, setTaskData] = useState(null);
  const [logs,     setLogs]     = useState([]);
  const [phase,    setPhase]    = useState("idle");

  // DB stats (live)
  const [dbStats, setDbStats] = useState({
    total_products:    0,
    total_categories:  0,
    distinct_brands:   0,
    available_products: 0,
    mapping_duplicates: 0,
    products_null_category_id: 0,
    top_categories:    [],
    last_scrape_state: {},
  });

  // Session counters — from state file (current or last run)
  const [runStats, setRunStats] = useState({
    products_scraped:     0,
    products_inserted:    0,
    products_updated:     0,
    duplicates_prevented: 0,
    categories_synced:    0,
  });

  const pollRef    = useRef(null);
  const logEndRef  = useRef(null);
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
      const res = await api.get("/scrape_blinkit/db-stats");
      setDbStats(res.data);
      const st = res.data.last_scrape_state || {};
      setRunStats({
        products_scraped:     st.products_scraped     || 0,
        products_inserted:    st.products_inserted    || 0,
        products_updated:     st.products_updated     || 0,
        duplicates_prevented: st.duplicates_prevented || 0,
        categories_synced:    st.categories_synced    || 0,
      });
    } catch (_) {}
  }, []);

  // ── Fetch categories for filter ────────────────────────────────────────────
  const fetchCategories = useCallback(async () => {
    try {
      const res = await api.get("/scrape_blinkit/categories");
      setCategoriesList(res.data?.categories || []);
    } catch (_) {}
  }, []);

  // ── Initial load ───────────────────────────────────────────────────────────
  useEffect(() => {
    fetchDbStats();
    fetchCategories();
    api.get("/scrape_blinkit/status")
      .then(res => {
        if (res.data?.task)         setTaskData(res.data.task);
        if (res.data?.state?.phase) setPhase(res.data.state.phase);
        if (res.data?.task?.status === "RUNNING") {
          setLoading(true);
          setPhase("running");
          // Resume polling if already running
          if (res.data.task.id) {
            setTaskId(res.data.task.id);
            startPolling(res.data.task.id);
          }
        }
      })
      .catch(() => {});
  }, [fetchDbStats, fetchCategories]);

  // ── Cleanup poll on unmount ────────────────────────────────────────────────
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // ── Log parser ─────────────────────────────────────────────────────────────
  const parseLogLine = (line) => {
    let type = "info";
    let msg  = line;
    let ts   = new Date().toLocaleTimeString("en-IN", { hour12: false });

    const parts = line.split(" | ");
    if (parts.length >= 3) {
      const tsMatch = parts[0].match(/\d{2}:\d{2}:\d{2}/);
      if (tsMatch) ts = tsMatch[0];
      const level = (parts[1] || "").trim();
      msg         = parts.slice(2).join(" | ");
      if (["ERROR", "CRITICAL"].includes(level)) type = "error";
      else if (level === "WARNING")               type = "warning";
      else if (msg.includes("SUCCESS") || msg.includes("complete") || msg.includes("COMPLETE")) type = "success";
      else if (msg.includes("Phase") || msg.includes("START") || msg.includes("==="))           type = "system";
    } else {
      const u = line.toUpperCase();
      if (u.includes("ERROR") || u.includes("FAILED") || u.includes("FATAL"))  type = "error";
      else if (u.includes("SUCCESS") || u.includes("COMPLETE"))                type = "success";
      else if (u.includes("WARNING") || u.includes("SKIP"))                    type = "warning";
      else if (line.startsWith("===") || line.includes("[Phase") || line.includes("[Config")) type = "system";
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
        const task    = taskRes.data;
        setTaskData(task);

        // Logs
        try {
          const logRes = await api.get(`/tasks/${tid}/blinkit-logs`);
          const lines  = logRes.data.logs || [];
          if (lines.length > 0) {
            setLogs(lines.map(parseLogLine));
          }
        } catch (_) {}

        // DB stats + run stats
        fetchDbStats();

        // Phase detection from status string
        if (task.status) {
          const st = task.status.toLowerCase();
          if      (st.includes("categor"))  setPhase("categories");
          else if (st.includes("scrap"))    setPhase("products");
          else if (st === "completed")      setPhase("completed");
          else if (st === "error")          setPhase("error");
          else if (st === "running" || st.includes("inserting")) setPhase("running");
        }

        // Stop polling on terminal states
        if (["COMPLETED", "ERROR", "STOPPED"].includes(task.status)) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setLoading(false);
          fetchDbStats();

          const finalMsg = task.status === "COMPLETED"
            ? `✅ Blinkit scrape COMPLETED! ${task.total_leads?.toLocaleString("en-IN") || ""} products processed.`
            : `❌ Scraper ${task.status}: ${task.error_message || "Unknown error"}`;
          setLogs(prev => [...prev, {
            ts:   new Date().toLocaleTimeString("en-IN"),
            msg:  finalMsg,
            type: task.status === "COMPLETED" ? "success" : "error",
          }]);
        }
      } catch (_) {}
    }, 2500);
  };

  // ── Handle Scrape ──────────────────────────────────────────────────────────
  const handleScrape = async () => {
    setError("");
    setLogs([]);
    setPhase("categories");
    setLoading(true);

    const addLog = (msg, type = "system") =>
      setLogs(prev => [...prev, { ts: new Date().toLocaleTimeString("en-IN"), msg, type }]);

    addLog(`[SYSTEM] Initializing Blinkit Automation Engine...`);
    addLog(`[CONFIG] Pincode: ${pincode} | Mode: ${mode.toUpperCase()} | MaxCat: ${maxCategories || "ALL"} | Resume: ${resume}`);
    if (selectedCategories.length > 0) {
      addLog(`[CONFIG] Category filter: ${selectedCategories.join(", ")}`, "info");
    }
    addLog(`[INFO] Scraper running in background — you can continue using the dashboard.`, "success");

    try {
      const res = await api.post("/scrape_blinkit", {
        pincode,
        mode,
        max_categories:       maxCategories ? parseInt(maxCategories) : null,
        resume,
        selected_categories:  selectedCategories.length > 0 ? selectedCategories : null,
      });

      const { task_id, message } = res.data;
      setTaskId(task_id);
      setPhase("running");
      addLog(`[SYSTEM] Task started! Task ID: #${task_id}`, "success");
      addLog(`[INFO] ${message}`, "info");
      startPolling(task_id);

    } catch (err) {
      const msg = err.response?.data?.error || "Failed to start Blinkit scraper.";
      setError(msg);
      addLog(`[ERROR] ${msg}`, "error");
      setLoading(false);
      setPhase("error");
    }
  };

  // ── Handle Stop ────────────────────────────────────────────────────────────
  const handleStop = async () => {
    try {
      await api.post("/scrape_blinkit/stop", { task_id: taskId });
      setLogs(prev => [...prev, {
        ts:   new Date().toLocaleTimeString("en-IN"),
        msg:  "[SYSTEM] Stop signal sent to scraper.",
        type: "warning",
      }]);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      setLoading(false);
      setPhase("idle");
    } catch (err) {
      setError(err.response?.data?.error || "Failed to stop scraper.");
    }
  };

  // ── Derived progress ───────────────────────────────────────────────────────
  const progress   = taskData?.progress || 0;
  const totalFound = taskData?.total_leads || 0;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen p-6 space-y-6"
         style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)" }}>

      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4
                      bg-white/5 backdrop-blur-sm p-6 rounded-2xl border border-white/10 shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shadow-lg"
               style={{ background: "linear-gradient(135deg, #22c55e, #16a34a)" }}>
            🛒
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2 flex-wrap">
              Blinkit Automation System
              <PhaseBadge phase={phase} />
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Production-grade crawler · Auto-discovers 40,000+ products · Zero duplicates guaranteed
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
            <p className="text-green-400 font-bold text-lg">{dbStats.total_products.toLocaleString("en-IN")}</p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">Categories</p>
            <p className="text-blue-400 font-bold text-lg">{dbStats.total_categories.toLocaleString("en-IN")}</p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">Brands</p>
            <p className="text-purple-400 font-bold text-lg">{dbStats.distinct_brands.toLocaleString("en-IN")}</p>
          </div>
        </div>
      </div>

      {/* ── Progress Bar (shown when active) ── */}
      {loading && (
        <div className="bg-white/5 backdrop-blur-sm rounded-xl border border-white/10 p-4 space-y-2">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Overall Progress</span>
            <span className="text-white font-bold">{progress}% — {totalFound.toLocaleString("en-IN")} products found</span>
          </div>
          <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progress}%`,
                background: "linear-gradient(90deg, #22c55e, #16a34a)",
                boxShadow: "0 0 12px rgba(34,197,94,0.5)",
              }}
            />
          </div>
          <p className="text-green-400 text-xs font-mono animate-pulse">
            {taskData?.status || "Processing..."} · Task #{taskId}
          </p>
        </div>
      )}

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ── LEFT: Control Panel ── */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-5 space-y-5">
            <h2 className="text-white font-bold text-base flex items-center gap-2">🎛️ Control Panel</h2>

            {/* Pincode */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Delivery Pincode (City)
              </label>
              <select
                value={pincode}
                onChange={e => setPincode(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-green-500 transition"
              >
                {PINCODE_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <p className="text-gray-500 text-xs mt-1">Blinkit catalog varies by location. Delhi gives largest coverage.</p>
            </div>

            {/* Mode */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Scrape Mode
              </label>
              <div className="grid grid-cols-3 gap-2">
                {["full", "categories", "incremental"].map(m => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    disabled={loading}
                    className={`py-2 rounded-xl text-xs font-bold border transition capitalize
                      ${mode === m
                        ? "bg-green-500/20 border-green-500/50 text-green-300"
                        : "bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500"
                      }`}
                  >
                    {m === "full" ? "🚀 Full" : m === "categories" ? "📂 Cats" : "⚡ Incr."}
                  </button>
                ))}
              </div>
              <p className="text-gray-500 text-xs mt-1">
                {mode === "full"       ? "Scrape ALL categories + products (recommended)" :
                 mode === "categories" ? "Only sync category tree (fast)" :
                                         "Only new products since last run"}
              </p>
            </div>

            {/* Category Filter */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Category Filter <span className="text-gray-600 normal-case">(empty = all)</span>
              </label>
              <CategorySelect
                categories={categoriesList}
                selected={selectedCategories}
                onChange={setSelectedCategories}
                disabled={loading}
              />
              <p className="text-gray-500 text-xs mt-1">Select specific L1 categories to scrape</p>
            </div>

            {/* Scope Limit */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Scope Limit <span className="text-gray-600 normal-case">(empty = all)</span>
              </label>
              <input
                type="number"
                min="1"
                placeholder="e.g. 5 for quick test"
                value={maxCategories}
                onChange={e => setMaxCategories(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-yellow-500 transition placeholder-gray-600"
              />
            </div>

            {/* Resume Toggle */}
            <div className="flex items-center gap-3 bg-gray-800/40 rounded-xl p-3 border border-gray-700/50">
              <button
                onClick={() => !loading && setResume(r => !r)}
                className={`w-11 h-6 rounded-full transition-all relative ${resume ? "bg-green-500" : "bg-gray-600"}`}
              >
                <div className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all"
                     style={{ left: resume ? "22px" : "2px" }} />
              </button>
              <div>
                <p className="text-white text-sm font-medium">Resume from last run</p>
                <p className="text-gray-500 text-xs">Skips already-scraped categories</p>
              </div>
            </div>

            {/* Buttons */}
            <div className="space-y-2 pt-1">
              {!loading ? (
                <button
                  onClick={handleScrape}
                  className="w-full py-3.5 rounded-xl text-white font-bold text-sm flex items-center justify-center gap-2 transition hover:opacity-90 active:scale-95"
                  style={{ background: "linear-gradient(135deg, #22c55e, #16a34a)" }}
                >
                  <span>🚀</span> Start Blinkit Scraper
                </button>
              ) : (
                <>
                  <div className="text-xs text-gray-400 bg-gray-800/40 rounded-xl p-3 border border-gray-700/50 text-center">
                    <p className="text-yellow-400 font-semibold mb-1">⚡ Scraper running in background</p>
                    <p>You can navigate to other pages and the scraper will continue working.</p>
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
                <span className="text-gray-400">Products NULL category_id</span>
                <span className={`font-bold ${dbStats.products_null_category_id > 0 ? "text-orange-400" : "text-green-400"}`}>
                  {dbStats.products_null_category_id > 0 ? `⚠️ ${dbStats.products_null_category_id}` : "✅ 0"}
                </span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-800">
                <span className="text-gray-400">Products in DB</span>
                <span className="text-white font-bold">{dbStats.total_products.toLocaleString("en-IN")}</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-800">
                <span className="text-gray-400">Available products</span>
                <span className="text-green-400 font-bold">{dbStats.available_products.toLocaleString("en-IN")}</span>
              </div>
              <div className="flex justify-between items-center py-1.5">
                <span className="text-gray-400">Last run — inserted</span>
                <span className="text-blue-400 font-bold">{runStats.products_inserted.toLocaleString("en-IN")}</span>
              </div>
            </div>
          </div>

          {/* ── Top Categories ── */}
          {dbStats.top_categories.length > 0 && (
            <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-4">
              <h3 className="text-white font-bold text-sm mb-3">📊 Top Categories</h3>
              <div className="space-y-1.5">
                {dbStats.top_categories.slice(0, 8).map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-full bg-gray-800 rounded-full h-1.5 flex-1">
                      <div
                        className="h-1.5 rounded-full bg-gradient-to-r from-green-500 to-emerald-600"
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
            <StatCard icon="🛒" label="Products Scraped" value={runStats.products_scraped}
                      pulse={loading} color="green" sub="this run" />
            <StatCard icon="✨" label="New Insertions"   value={runStats.products_inserted}
                      pulse={loading} color="blue" sub="truly new products" />
            <StatCard icon="♻️" label="Updated (Price)"  value={runStats.products_updated}
                      color="purple" sub="existing products" />
            <StatCard icon="🛡️" label="Duplicates Prevented"
                      value={dbStats.mapping_duplicates === 0 ? "✓ None" : dbStats.mapping_duplicates}
                      color={dbStats.mapping_duplicates === 0 ? "green" : "red"} />
            <StatCard icon="📂" label="Categories Synced" value={runStats.categories_synced}
                      color="yellow" sub="to blinkit_mapping" />
            <StatCard icon="📦" label="Total in DB"      value={dbStats.total_products}
                      color="indigo" sub="blinkit table" />
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
                <span className="text-gray-500 text-xs font-mono ml-2">blinkit-scraper@worker</span>
              </div>
              <div className="flex items-center gap-2">
                {taskId && (
                  <span className="text-gray-500 text-xs font-mono">task #{taskId}</span>
                )}
                <span className={`text-xs font-bold px-2 py-0.5 rounded font-mono border ${
                  loading
                    ? "text-green-400 border-green-500/30 bg-green-500/10"
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
                  <p className="text-center">Blinkit Automation Engine ready.</p>
                  <p className="text-center text-gray-700">Configure settings and click <strong className="text-gray-500">Start Blinkit Scraper</strong> to begin.</p>
                  <p className="text-center text-gray-700 text-xs">The scraper runs in the background — you can use other dashboard features while it runs.</p>
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

          {/* Recent History */}
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
    api.get("/scrape_blinkit/history?limit=5")
      .then(r => setHistory(r.data || []))
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
            <span className="text-green-400 font-mono mr-4">{(t.total_leads || 0).toLocaleString("en-IN")} products</span>
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

export default BlinkitScrapper;