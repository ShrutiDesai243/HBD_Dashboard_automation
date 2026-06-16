import React, { useState, useEffect, useRef, useCallback } from "react";
import api from "../../utils/Api";

// ─── Constants ────────────────────────────────────────────────────────────────
const BB_GREEN = "#84C225";
const BB_DARK_GREEN = "#5a8a1a";
const POLL_INTERVAL_MS = 2500;

const STATUS_COLORS = {
  COMPLETED: { bg: "bg-green-100", text: "text-green-700", dot: "bg-green-500" },
  RUNNING:   { bg: "bg-blue-100",  text: "text-blue-700",  dot: "bg-blue-500 animate-pulse" },
  MERGED:    { bg: "bg-purple-100", text: "text-purple-700", dot: "bg-purple-500" },
  FAILED:    { bg: "bg-red-100",   text: "text-red-700",   dot: "bg-red-500" },
  starting:  { bg: "bg-yellow-100", text: "text-yellow-700", dot: "bg-yellow-400 animate-pulse" },
  PENDING:   { bg: "bg-gray-100",  text: "text-gray-600",  dot: "bg-gray-400" },
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const colors = STATUS_COLORS[status] || STATUS_COLORS.PENDING;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${colors.bg} ${colors.text}`}>
      <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
      {status || "UNKNOWN"}
    </span>
  );
}

function ProgressBar({ value }) {
  return (
    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
      <div
        className="h-2 rounded-full transition-all duration-700"
        style={{ width: `${Math.min(100, value || 0)}%`, background: `linear-gradient(90deg, ${BB_GREEN}, ${BB_DARK_GREEN})` }}
      />
    </div>
  );
}

function LogLine({ log }) {
  const colorMap = {
    success: "text-green-400",
    error:   "text-red-400 font-semibold",
    warning: "text-yellow-300",
    system:  "text-sky-300 font-semibold",
    info:    "text-gray-200",
  };
  return (
    <div className="flex gap-2 leading-relaxed">
      <span className="text-gray-500 select-none shrink-0">[{log.timestamp}]</span>
      <span className={colorMap[log.type] || "text-gray-200"}>{log.message}</span>
    </div>
  );
}

function ConfirmModal({ isOpen, title, body, onConfirm, onCancel, loading }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-xl font-bold text-gray-800">{title}</h2>
        </div>
        <div className="p-6">
          <p className="text-gray-600 text-sm leading-relaxed">{body}</p>
        </div>
        <div className="p-6 flex gap-3 justify-end border-t border-gray-100">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-5 py-2.5 rounded-xl border border-gray-300 text-gray-700 font-medium text-sm hover:bg-gray-50 disabled:opacity-50 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-5 py-2.5 rounded-xl text-white font-semibold text-sm disabled:opacity-60 transition-all flex items-center gap-2"
            style={{ background: `linear-gradient(135deg, ${BB_GREEN}, ${BB_DARK_GREEN})` }}
          >
            {loading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            {loading ? "Merging..." : "✅ Confirm Merge"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const BigbasketScrapper = () => {
  // Form state
  const [category, setCategory] = useState("");
  const [subcategories, setSubcategories] = useState("");
  const [pages, setPages] = useState(10);

  // Task state
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [taskProgress, setTaskProgress] = useState(0);
  const [totalFound, setTotalFound] = useState(0);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Logs
  const [logs, setLogs] = useState([]);

  // CSV preview
  const [csvHeaders, setCsvHeaders] = useState([]);
  const [csvRows, setCsvRows] = useState([]);
  const [csvTotal, setCsvTotal] = useState(0);
  const [csvFilename, setCsvFilename] = useState("");

  // Task history
  const [taskHistory, setTaskHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Merge modal
  const [mergeModalOpen, setMergeModalOpen] = useState(false);
  const [merging, setMerging] = useState(false);

  // Refs
  const terminalEndRef = useRef(null);
  const pollRef = useRef(null);

  // ── Auto-scroll terminal ───────────────────────────────────────────────────
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // ── Load task history on mount ────────────────────────────────────────────
  useEffect(() => { fetchTaskHistory(); }, []);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const addLog = useCallback((message, type = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { timestamp, message, type }]);
  }, []);

  const parseLogLines = useCallback((lines) => {
    return lines.map(line => {
      let type = "info";
      let msg = line;
      let timestamp = new Date().toLocaleTimeString();

      const parts = line.split(" | ");
      if (parts.length >= 3) {
        const tsPart = parts[0];
        const level = parts[1].trim();
        msg = parts.slice(2).join(" | ");
        const m = tsPart.match(/\d{2}:\d{2}:\d{2}/);
        if (m) timestamp = m[0];
        if (level === "ERROR" || level === "CRITICAL") type = "error";
        else if (level === "WARNING") type = "warning";
        else if (msg.toUpperCase().includes("SUCCESS") || msg.toUpperCase().includes("COMPLETED")) type = "success";
        else if (msg.startsWith("[") || msg.toUpperCase().includes("START")) type = "system";
      } else {
        const u = line.toUpperCase();
        if (u.includes("ERROR") || u.includes("FAILED") || u.includes("EXCEPTION")) type = "error";
        else if (u.includes("SUCCESS") || u.includes("COMPLETED")) type = "success";
        else if (u.includes("WARNING") || u.includes("SKIP") || u.includes("FALLBACK")) type = "warning";
        else if (line.startsWith("[") || u.includes("STARTING") || u.includes("SCRAPED") || u.includes("CSV")) type = "system";
      }
      return { timestamp, message: msg, type };
    });
  }, []);

  // ── Fetch CSV preview ─────────────────────────────────────────────────────
  const fetchCsvPreview = useCallback(async (tid) => {
    try {
      const res = await api.get(`/scrape_bigbasket/preview/${tid}`);
      setCsvHeaders(res.data.headers || []);
      setCsvRows(res.data.rows || []);
      setCsvTotal(res.data.total || 0);
      setCsvFilename(res.data.filename || "");
    } catch (e) {
      console.error("CSV preview error:", e);
    }
  }, []);

  // ── Fetch task history ────────────────────────────────────────────────────
  const fetchTaskHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await api.get("/scrape_bigbasket/tasks");
      setTaskHistory(res.data || []);
    } catch (e) {
      console.error("History fetch error:", e);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // ── Poll task status ──────────────────────────────────────────────────────
  const startPolling = useCallback((tid) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const [taskRes, logsRes] = await Promise.all([
          api.get(`/tasks/${tid}`),
          api.get(`/tasks/${tid}/logs`),
        ]);

        const task = taskRes.data;
        const logLines = logsRes.data.logs || [];

        setTaskStatus(task.status);
        setTaskProgress(task.progress || 0);
        setTotalFound(task.total_leads || 0);

        if (logLines.length > 0) {
          setLogs(parseLogLines(logLines));
        }

        if (task.status === "COMPLETED") {
          addLog("[SUCCESS] BigBasket scraping completed successfully!", "success");
          setLoading(false);
          clearInterval(pollRef.current);
          pollRef.current = null;
          await fetchCsvPreview(tid);
          await fetchTaskHistory();
        } else if (task.status === "FAILED") {
          const msg = task.error_message || "Scraper failed with an unknown error.";
          addLog(`[ERROR] ${msg}`, "error");
          setError(msg);
          setLoading(false);
          clearInterval(pollRef.current);
          pollRef.current = null;
          await fetchTaskHistory();
        } else if (task.status === "STOPPED") {
          addLog("[WARNING] Scraping was stopped.", "warning");
          setLoading(false);
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (e) {
        console.error("Poll error:", e);
      }
    }, POLL_INTERVAL_MS);
  }, [addLog, fetchCsvPreview, fetchTaskHistory, parseLogLines]);

  // ── Start scrape ──────────────────────────────────────────────────────────
  const handleScrape = async () => {
    if (!category.trim()) {
      setError("Category is required. Please enter a BigBasket main category name.");
      return;
    }

    setError("");
    setSuccessMsg("");
    setLogs([]);
    setCsvHeaders([]);
    setCsvRows([]);
    setCsvTotal(0);
    setCsvFilename("");
    setTaskId(null);
    setTaskStatus("starting");
    setTaskProgress(0);
    setTotalFound(0);
    setLoading(true);

    addLog("[SYSTEM] Initializing BigBasket Category Scraper...", "system");
    addLog(`[CONFIG] Category: ${category}`, "info");
    addLog(`[CONFIG] Subcategories: ${subcategories || "(auto-discover all)"}`, "info");
    addLog(`[CONFIG] Pages (scroll rounds per subcategory): ${pages}`, "info");

    try {
      const res = await api.post("/scrape_bigbasket", {
        category: category.trim(),
        subcategories: subcategories.trim(),
        pages,
      }, { headers: { "Content-Type": "application/json" } });

      const data = res.data;
      setTaskId(data.task_id);
      addLog(`[API] Task created successfully. Task ID: ${data.task_id}`, "success");
      addLog(`[BROWSER] Playwright browser launching — this may take a moment...`, "system");
      startPolling(data.task_id);
    } catch (e) {
      const msg = e.response?.data?.error || "Failed to start BigBasket scraper.";
      setError(msg);
      addLog(`[ERROR] ${msg}`, "error");
      setLoading(false);
      setTaskStatus("FAILED");
    }
  };

  // ── Merge to DB ───────────────────────────────────────────────────────────
  const handleMerge = async () => {
    setMerging(true);
    try {
      const res = await api.post(`/scrape_bigbasket/merge/${taskId}`);
      const data = res.data;
      setMergeModalOpen(false);
      setTaskStatus("MERGED");
      setSuccessMsg(data.message || `Merged ${data.inserted} records into database.`);
      addLog(`[MERGE] ${data.message}`, "success");
      await fetchTaskHistory();
    } catch (e) {
      const msg = e.response?.data?.error || "Merge failed. Please try again.";
      setError(msg);
      addLog(`[ERROR] Merge failed: ${msg}`, "error");
      setMergeModalOpen(false);
    } finally {
      setMerging(false);
    }
  };

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setCategory(""); setSubcategories(""); setPages(10);
    setTaskId(null); setTaskStatus(null); setTaskProgress(0); setTotalFound(0);
    setLoading(false); setError(""); setSuccessMsg("");
    setLogs([]); setCsvHeaders([]); setCsvRows([]); setCsvTotal(0); setCsvFilename("");
  };

  // ── Load historical task into preview ────────────────────────────────────
  const loadHistoricalTask = async (histTask) => {
    setTaskId(histTask.id);
    setTaskStatus(histTask.status);
    setTaskProgress(histTask.progress || (histTask.status === "COMPLETED" ? 100 : 0));
    setTotalFound(histTask.total_found || 0);
    setLogs([]);
    setError("");
    setSuccessMsg("");
    setCsvHeaders([]); setCsvRows([]); setCsvTotal(0); setCsvFilename("");
    if (histTask.status === "COMPLETED" || histTask.status === "MERGED") {
      await fetchCsvPreview(histTask.id);
    }
  };

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-green-50/30 p-6 space-y-6">

      {/* Confirm Merge Modal */}
      <ConfirmModal
        isOpen={mergeModalOpen}
        title="Approve & Merge to Database"
        body={`You are about to insert ${csvTotal.toLocaleString()} scraped BigBasket products into the database. Existing products with the same name + category will be skipped. This action cannot be undone. Proceed?`}
        onConfirm={handleMerge}
        onCancel={() => setMergeModalOpen(false)}
        loading={merging}
      />

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg" style={{ background: `linear-gradient(135deg, ${BB_GREEN}, ${BB_DARK_GREEN})` }}>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="white" className="w-8 h-8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5V6a3.75 3.75 0 1 0-7.5 0v4.5m11.356-1.993 1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 0 1-1.12-1.243l1.264-12A1.125 1.125 0 0 1 5.513 7.5h12.974c.576 0 1.059.435 1.119 1.007Z" />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-gray-800 tracking-tight">BigBasket Category Scraper</h1>
            <p className="text-sm text-gray-500 mt-0.5">Automated product data extraction with live monitoring & DB merge workflow</p>
          </div>
        </div>
        {taskId && taskStatus && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400 font-mono">Task #{taskId}</span>
            <StatusBadge status={taskStatus} />
          </div>
        )}
      </div>

      {/* ── Main Grid ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ── Left: Control Panel ─────────────────────────────────────────── */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">

            <div className="flex items-center gap-2 pb-2 border-b border-gray-100">
              <div className="w-2 h-2 rounded-full" style={{ background: BB_GREEN }} />
              <h2 className="font-bold text-gray-700 text-sm uppercase tracking-wider">Scraper Configuration</h2>
            </div>

            {/* Category input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1">
                Main Category
                <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={category}
                onChange={e => setCategory(e.target.value)}
                placeholder="e.g. Fruits & Vegetables"
                disabled={loading}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-100 transition-all disabled:bg-gray-50 disabled:opacity-60"
              />
              <p className="text-xs text-gray-400">Enter the BigBasket main category name exactly as it appears on the site.</p>
            </div>

            {/* Subcategories input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Subcategories <span className="font-normal text-gray-400">(optional)</span>
              </label>
              <textarea
                value={subcategories}
                onChange={e => setSubcategories(e.target.value)}
                placeholder={"e.g. Fruits, Vegetables\n(one per line or comma-separated)\nLeave blank to auto-discover all."}
                disabled={loading}
                rows={3}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-100 transition-all resize-none disabled:bg-gray-50 disabled:opacity-60"
              />
              <p className="text-xs text-gray-400">Leave blank to auto-discover and scrape <strong>all subcategories</strong>.</p>
            </div>

            {/* Pages input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center justify-between">
                Scroll Rounds per Page
                <span className="font-normal text-gray-400 normal-case">(1–200)</span>
              </label>
              <input
                type="number"
                value={pages}
                min={1}
                max={200}
                onChange={e => setPages(Math.max(1, Math.min(200, Number(e.target.value))))}
                disabled={loading}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-100 transition-all disabled:bg-gray-50 disabled:opacity-60"
              />
              <p className="text-xs text-gray-400">More rounds = more products per page (each round ≈ 2.5s). Recommended: 10–30 for testing, 60+ for full scrape.</p>
            </div>

            {/* Action buttons */}
            <div className="space-y-2 pt-1">
              <button
                onClick={handleScrape}
                disabled={loading}
                className="w-full py-3 rounded-xl text-white font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 shadow-md hover:shadow-lg disabled:opacity-60 disabled:cursor-not-allowed"
                style={{ background: loading ? '#9ca3af' : `linear-gradient(135deg, ${BB_GREEN}, ${BB_DARK_GREEN})` }}
              >
                {loading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Scraping in progress...
                  </>
                ) : (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                    </svg>
                    Start BigBasket Scrape
                  </>
                )}
              </button>
              {!loading && (
                <button
                  onClick={handleReset}
                  className="w-full py-2.5 rounded-xl border border-gray-200 text-gray-600 font-medium text-sm hover:bg-gray-50 transition-all"
                >
                  Reset
                </button>
              )}
            </div>

            {/* Error / Success alerts */}
            {error && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-100 flex gap-2">
                <span className="text-red-500 text-lg leading-none">⚠️</span>
                <p className="text-sm text-red-600 font-medium">{error}</p>
              </div>
            )}
            {successMsg && (
              <div className="p-3 rounded-xl bg-green-50 border border-green-100 flex gap-2">
                <span className="text-lg leading-none">✅</span>
                <p className="text-sm text-green-700 font-medium">{successMsg}</p>
              </div>
            )}

            {/* Live status */}
            {taskId && (
              <div className="space-y-3 pt-2 border-t border-gray-100">
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <span className="font-medium">Scraping Progress</span>
                  <span className="font-bold text-gray-700">{taskProgress}%</span>
                </div>
                <ProgressBar value={taskProgress} />
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">Products found</span>
                  <span className="font-bold text-gray-800">{totalFound.toLocaleString()}</span>
                </div>

                {/* Action buttons post-completion */}
                {(taskStatus === "COMPLETED" || taskStatus === "MERGED") && taskId && (
                  <div className="space-y-2 pt-1">
                    <a
                      href={`http://localhost:8001/api/scrape_bigbasket/csv/${taskId}`}
                      target="_blank"
                      rel="noreferrer"
                      className="w-full py-2.5 rounded-xl border text-sm font-semibold flex items-center justify-center gap-2 transition-all hover:opacity-80"
                      style={{ borderColor: BB_GREEN, color: BB_DARK_GREEN }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
                      </svg>
                      Download CSV ({csvTotal.toLocaleString()} rows)
                    </a>
                    {taskStatus === "COMPLETED" && (
                      <button
                        onClick={() => setMergeModalOpen(true)}
                        className="w-full py-2.5 rounded-xl text-white text-sm font-bold flex items-center justify-center gap-2 transition-all hover:opacity-90 shadow-sm"
                        style={{ background: `linear-gradient(135deg, #7c3aed, #5b21b6)` }}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                        </svg>
                        Approve & Merge to DB
                      </button>
                    )}
                    {taskStatus === "MERGED" && (
                      <div className="py-2.5 rounded-xl bg-purple-50 border border-purple-200 text-center text-sm font-semibold text-purple-700">
                        ✅ Merged into Database
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: Terminal ──────────────────────────────────────────────── */}
        <div className="lg:col-span-8 flex flex-col gap-5">
          {/* Terminal window */}
          <div className="rounded-2xl overflow-hidden border border-gray-800 shadow-2xl bg-gray-950 flex flex-col" style={{ height: "480px" }}>
            {/* Terminal header */}
            <div className="bg-gray-900 px-5 py-3 flex items-center justify-between border-b border-gray-800">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500 hover:bg-red-400 cursor-pointer transition-colors" />
                <div className="w-3 h-3 rounded-full bg-yellow-500 hover:bg-yellow-400 cursor-pointer transition-colors" />
                <div className="w-3 h-3 rounded-full bg-green-500 hover:bg-green-400 cursor-pointer transition-colors" />
                <span className="text-xs text-gray-400 font-mono ml-3">bigbasket-scraper@logs</span>
              </div>
              <div className="flex items-center gap-3">
                {loading && (
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: BB_GREEN }} />
                    <span className="text-xs font-mono" style={{ color: BB_GREEN }}>SCRAPING</span>
                  </div>
                )}
                <span className={`text-xs font-mono px-2 py-0.5 rounded border ${loading ? 'text-green-400 border-green-500/30 bg-green-900/20' : 'text-gray-500 border-gray-700 bg-gray-900'}`}>
                  {loading ? "RUNNING" : taskStatus || "IDLE"}
                </span>
              </div>
            </div>

            {/* Terminal body */}
            <div className="flex-1 overflow-y-auto p-5 font-mono text-xs space-y-1.5 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent">
              {logs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-3">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor" className="w-12 h-12 opacity-30">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0 0 21 18V6a2.25 2.25 0 0 0-2.25-2.25H5.25A2.25 2.25 0 0 0 3 6v12a2.25 2.25 0 0 0 2.25 2.25Z" />
                  </svg>
                  <span className="italic">Terminal idle — configure and start a scrape to see live logs</span>
                </div>
              ) : (
                logs.map((log, i) => <LogLine key={i} log={log} />)
              )}
              <div ref={terminalEndRef} />
            </div>
          </div>

          {/* CSV Preview panel */}
          {csvRows.length > 0 && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full" style={{ background: BB_GREEN }} />
                  <h3 className="font-bold text-gray-700">CSV Preview</h3>
                  <span className="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full font-semibold">
                    {csvTotal.toLocaleString()} rows
                  </span>
                  {csvFilename && (
                    <span className="text-xs text-gray-400 font-mono">{csvFilename}</span>
                  )}
                </div>
                <div className="flex gap-2">
                  {taskStatus === "COMPLETED" && (
                    <button
                      onClick={() => setMergeModalOpen(true)}
                      className="px-4 py-2 rounded-lg text-white text-xs font-bold transition-all hover:opacity-90"
                      style={{ background: "linear-gradient(135deg, #7c3aed, #5b21b6)" }}
                    >
                      ✅ Approve & Merge
                    </button>
                  )}
                  <a
                    href={`http://localhost:8001/api/scrape_bigbasket/csv/${taskId}`}
                    target="_blank"
                    rel="noreferrer"
                    className="px-4 py-2 rounded-lg text-xs font-semibold border transition-all hover:bg-green-50"
                    style={{ borderColor: BB_GREEN, color: BB_DARK_GREEN }}
                  >
                    ⬇ Download
                  </a>
                </div>
              </div>
              <div className="overflow-x-auto max-h-80 overflow-y-auto">
                <table className="min-w-full text-xs">
                  <thead className="sticky top-0 z-10">
                    <tr className="bg-gray-50 border-b border-gray-200">
                      {csvHeaders.map(h => (
                        <th key={h} className="px-4 py-2.5 text-left font-semibold text-gray-600 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {csvRows.map((row, ri) => (
                      <tr key={ri} className={`border-b border-gray-50 hover:bg-green-50/30 transition-colors ${ri % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}>
                        {csvHeaders.map(h => (
                          <td key={h} className="px-4 py-2 text-gray-700 max-w-xs truncate">{row[h]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Task History ─────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full" style={{ background: BB_GREEN }} />
            <h3 className="font-bold text-gray-700">Scrape History</h3>
            <span className="bg-gray-100 text-gray-500 text-xs px-2.5 py-1 rounded-full">{taskHistory.length} tasks</span>
          </div>
          <button
            onClick={fetchTaskHistory}
            disabled={historyLoading}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors disabled:opacity-50"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className={`w-3.5 h-3.5 ${historyLoading ? 'animate-spin' : ''}`}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            Refresh
          </button>
        </div>

        {taskHistory.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-sm">
            No BigBasket scraping tasks yet. Start your first scrape above!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  {["ID", "Category / Query", "Status", "Products", "Progress", "Created", "Actions"].map(h => (
                    <th key={h} className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {taskHistory.map((t, i) => (
                  <tr key={t.id} className={`border-b border-gray-50 hover:bg-green-50/20 transition-colors ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/30'}`}>
                    <td className="px-5 py-3 font-mono text-xs text-gray-500">#{t.id}</td>
                    <td className="px-5 py-3 font-medium text-gray-800 max-w-xs truncate">{t.query}</td>
                    <td className="px-5 py-3"><StatusBadge status={t.status} /></td>
                    <td className="px-5 py-3 font-semibold text-gray-700">{(t.total_found || 0).toLocaleString()}</td>
                    <td className="px-5 py-3 w-32">
                      <div className="flex items-center gap-2">
                        <ProgressBar value={t.status === "COMPLETED" || t.status === "MERGED" ? 100 : (t.progress || 0)} />
                        <span className="text-xs text-gray-500 shrink-0">{t.status === "COMPLETED" || t.status === "MERGED" ? 100 : (t.progress || 0)}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-xs text-gray-400">
                      {t.created_at ? new Date(t.created_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex gap-2">
                        {(t.status === "COMPLETED" || t.status === "MERGED") && (
                          <button
                            onClick={() => loadHistoricalTask(t)}
                            className="text-xs px-3 py-1.5 rounded-lg border font-medium transition-all hover:bg-green-50"
                            style={{ borderColor: BB_GREEN, color: BB_DARK_GREEN }}
                          >
                            View Preview
                          </button>
                        )}
                        {(t.status === "COMPLETED" || t.status === "MERGED") && (
                          <a
                            href={`http://localhost:8001${t.download_url}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 font-medium hover:bg-gray-50 transition-all"
                          >
                            CSV
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default BigbasketScrapper;