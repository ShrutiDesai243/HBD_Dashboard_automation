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
    links:      { label: "🔗 Collecting Links", color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
    extraction: { label: "📍 Extracting Data", color: "bg-green-500/20 text-green-300 border-green-500/30" },
    completed:  { label: "✅ Complete",        color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
    idle:       { label: "⏸ Idle",             color: "bg-gray-500/20 text-gray-400 border-gray-500/30" },
    error:      { label: "❌ Error",            color: "bg-red-500/20 text-red-300 border-red-500/30" },
    running:    { label: "⚡ Running",         color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
  };
  const info = map[phase] || map.idle;
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${info.color}`}>
      {info.label}
    </span>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
const GoogleMapScrapper = () => {
  // Controls
  const [category, setCategory] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Task state
  const [taskId, setTaskId] = useState(null);
  const [taskData, setTaskData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [phase, setPhase] = useState("idle");

  // DB stats (live)
  const [dbStats, setDbStats] = useState({
    total_raw_scraped: 0,
    total_master_integrated: 0,
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
      const res = await api.get("/tasks/google-map-stats");
      setDbStats(res.data);
    } catch (_) {}
  }, []);

  // ── Initial load ───────────────────────────────────────────────────────────
  useEffect(() => {
    fetchDbStats();
  }, [fetchDbStats]);

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
      else if (level === "SUCCESS" || msg.includes("COMPLETE") || msg.includes("✅")) type = "success";
      else if (level === "SYSTEM" || msg.includes("Phase") || msg.includes("===")) type = "system";
    } else {
      const u = line.toUpperCase();
      if (u.includes("ERROR") || u.includes("FAILED") || u.includes("FATAL"))  type = "error";
      else if (u.includes("SUCCESS") || u.includes("COMPLETE") || u.includes("✅")) type = "success";
      else if (u.includes("WARNING") || u.includes("SKIP"))                    type = "warning";
      else if (line.startsWith("===") || line.includes("[Phase") || line.includes("[SYSTEM]")) type = "system";
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
          const logRes = await api.get(`/tasks/${tid}/logs`);
          const lines  = logRes.data.logs || [];
          if (lines.length > 0) {
            setLogs(lines.map(parseLogLine));
          }
        } catch (_) {}

        // Phase detection from logs or status
        if (task.status) {
          const st = task.status.toLowerCase();
          if (st === "completed") setPhase("completed");
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
            ? `✅ Scrape COMPLETED! Data inserted to Master Table.`
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
    if (!category || !city) {
      setError("Category and City are required.");
      return;
    }

    setError("");
    setLogs([]);
    setPhase("running");
    setLoading(true);

    const addLog = (msg, type = "system") =>
      setLogs(prev => [...prev, { ts: new Date().toLocaleTimeString("en-IN"), msg, type }]);

    addLog(`[SYSTEM] Initializing Google Maps Automation Engine...`);
    addLog(`[CONFIG] Category: ${category} | City: ${city} | State: ${state || "N/A"}`);

    try {
      const res = await api.post("/scrape", {
        platform: "Google Maps",
        category,
        city,
        state
      });

      const { task_id, message } = res.data;
      setTaskId(task_id);
      addLog(`[SYSTEM] Task started! Task ID: #${task_id}`, "success");
      addLog(`[INFO] ${message}`, "info");
      startPolling(task_id);

    } catch (err) {
      const msg = err.response?.data?.error || "Failed to start scraper.";
      setError(msg);
      addLog(`[ERROR] ${msg}`, "error");
      setLoading(false);
      setPhase("error");
    }
  };

  // ── Handle Stop ────────────────────────────────────────────────────────────
  const handleStop = async () => {
    if (!taskId) return;
    try {
      await api.post("/stop", { task_id: taskId });
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

  const progress   = taskData?.progress || 0;
  const totalFound = taskData?.total_found || 0;

  return (
    <div className="min-h-screen p-6 space-y-6"
         style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)" }}>

      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4
                      bg-white/5 backdrop-blur-sm p-6 rounded-2xl border border-white/10 shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shadow-lg"
               style={{ background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}>
            📍
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2 flex-wrap">
              Google Maps Extractor
              <PhaseBadge phase={phase} />
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Automated data extraction · Seamless ETL into Master Table
            </p>
            {loading && (
              <p className="text-yellow-400 text-xs mt-1 animate-pulse">
                ⚡ Scraper is running... logs streaming below
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <button 
            onClick={fetchDbStats}
            className="text-gray-400 hover:text-white px-2 cursor-pointer transition"
            title="Refresh Stats"
          >
            🔄
          </button>
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">Raw Scraped</p>
            <p className="text-blue-400 font-bold text-lg">{dbStats.total_raw_scraped.toLocaleString("en-IN")}</p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">Master Table</p>
            <p className="text-green-400 font-bold text-lg">{dbStats.total_master_integrated.toLocaleString("en-IN")}</p>
          </div>
        </div>
      </div>

      {/* ── Progress Bar ── */}
      {loading && (
        <div className="bg-white/5 backdrop-blur-sm rounded-xl border border-white/10 p-4 space-y-2">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Extraction Progress</span>
            <span className="text-white font-bold">{progress}% — {totalFound.toLocaleString("en-IN")} listings found</span>
          </div>
          <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progress}%`,
                background: "linear-gradient(90deg, #3b82f6, #2563eb)",
                boxShadow: "0 0 12px rgba(59,130,246,0.5)",
              }}
            />
          </div>
        </div>
      )}

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ── LEFT: Control Panel ── */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-5 space-y-5">
            <h2 className="text-white font-bold text-base flex items-center gap-2">🎛️ Search Parameters</h2>

            {/* Category */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Category / Keyword *
              </label>
              <input
                type="text"
                placeholder="e.g., Restaurants, Plumbers, IT Services"
                value={category}
                onChange={e => setCategory(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-blue-500 transition"
              />
            </div>

            {/* City */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                City *
              </label>
              <input
                type="text"
                placeholder="e.g., Ahmedabad"
                value={city}
                onChange={e => setCity(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-blue-500 transition"
              />
            </div>

            {/* State */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                State (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g., Gujarat"
                value={state}
                onChange={e => setState(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-blue-500 transition"
              />
            </div>

            {/* Buttons */}
            <div className="space-y-2 pt-2">
              {!loading ? (
                <button
                  onClick={handleScrape}
                  className="w-full py-3.5 rounded-xl text-white font-bold text-sm flex items-center justify-center gap-2 transition hover:opacity-90 active:scale-95"
                  style={{ background: "linear-gradient(135deg, #3b82f6, #2563eb)" }}
                >
                  <span>🚀</span> Start Extraction
                </button>
              ) : (
                <button
                  onClick={handleStop}
                  className="w-full py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30"
                >
                  <span className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                  Stop Scraper
                </button>
              )}
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3">
                <p className="text-red-400 text-xs font-semibold">⚠️ {error}</p>
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: Stats + Terminal ── */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          
          <div className="grid grid-cols-2 gap-3">
            <StatCard icon="📍" label="Current Extraction Count" value={totalFound}
                      pulse={loading} color="blue" sub="listings found in current run" />
            <StatCard icon="🔄" label="Task Status" value={taskData ? taskData.status : "READY"}
                      color={taskData?.status === "COMPLETED" ? "green" : taskData?.status === "ERROR" ? "red" : "yellow"} 
                      sub={taskData ? `Task ID: ${taskId}` : "Awaiting input"} />
          </div>

          {/* ── Terminal ── */}
          <div className="flex-1 rounded-2xl overflow-hidden border border-gray-700/50 shadow-2xl flex flex-col min-h-[400px]"
               style={{ background: "#0d1117" }}>
            {/* Terminal Header */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900 border-b border-gray-700/50">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="text-gray-500 text-xs font-mono ml-2">google-map-scraper@worker</span>
              </div>
              <div className="flex items-center gap-2">
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
            <div className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-xs" id="terminal-body">
              {logs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-3">
                  <span className="text-4xl">🤖</span>
                  <p className="text-center">Google Maps Automation ready.</p>
                  <p className="text-center text-gray-700">Enter category and location, then click <strong className="text-gray-500">Start Extraction</strong>.</p>
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
        </div>
      </div>
    </div>
  );
};

export default GoogleMapScrapper;
