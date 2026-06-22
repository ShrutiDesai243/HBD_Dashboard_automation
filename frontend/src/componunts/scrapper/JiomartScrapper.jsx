import React, { useState, useEffect, useRef } from "react";
import {
  Card,
  CardBody,
  Input,
  Button,
  Typography,
} from "@material-tailwind/react";
import api from "../../utils/Api";

// Helper component for progress bar (DMart style)
function ProgressBar({ value }) {
  return (
    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/50">
      <div
        className="h-full bg-blue-600 rounded-full transition-all duration-500"
        style={{ width: `${Math.min(100, value || 0)}%` }}
      />
    </div>
  );
}

// Helper function to format elapsed time in MM:SS or HH:MM:SS
const formatTime = (seconds) => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`;
};

const JiomartScrapper = () => {
  const [maxCategories, setMaxCategories] = useState("");
  const [resume, setResume] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);
  const [logFilter, setLogFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [recentProducts, setRecentProducts] = useState([]);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [autoScroll, setAutoScroll] = useState(false);
  const [parsedStats, setParsedStats] = useState({
    completed: 0,
    total: 0,
    currentCategory: "Idle",
    totalNew: 0,
    totalUpdated: 0,
  });

  const terminalEndRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const timerRef = useRef(null);

  // Auto-scroll logs terminal
  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, logFilter, searchQuery, autoScroll]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Fetch recent products
  const fetchRecentProducts = async () => {
    try {
      const res = await api.get(`/jiomart/recent_products?t=${Date.now()}`);
      if (res.data && Array.isArray(res.data)) {
        setRecentProducts(res.data);
      } else {
        setRecentProducts([]);
      }
    } catch (err) {
      console.error("Error fetching recent products:", err);
      setRecentProducts([]);
    }
  };

  // Timer logic when running
  useEffect(() => {
    if (loading) {
      setElapsedTime(0);
      timerRef.current = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [loading]);

  // Live products sync during scraping
  useEffect(() => {
    let interval = null;
    if (loading) {
      interval = setInterval(fetchRecentProducts, 6000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loading]);

  // Parse stats from logs
  useEffect(() => {
    if (logs.length > 0) {
      let completed = 0;
      let total = 0;
      let currentCategory = parsedStats.currentCategory;
      let totalNew = 0;
      let totalUpdated = 0;

      logs.forEach((log) => {
        const line = log.message || "";
        
        // Parse completed category status
        // Format: [85/120] [OK] Groceries > Fruits & Vegetables > Fresh Vegetables | Pages: 2 | New: 4 | ...
        const okMatch = line.match(/\[(\d+)\/(\d+)\]\s+\[OK\]\s+(.*?)\s*\|\s*Pages:\s*(\d+)\s*\|\s*New:\s*(\d+)\s*\|\s*Updated:\s*(\d+)/);
        if (okMatch) {
          completed = parseInt(okMatch[1]);
          total = parseInt(okMatch[2]);
          const path = okMatch[3].trim();
          const pathParts = path.split(">");
          const catName = pathParts[pathParts.length - 1].trim();
          currentCategory = catName;
        }

        // Parse running totals
        const totalsMatch = line.match(/\(Total New:\s*(\d+),\s*Updated:\s*(\d+)\)/);
        if (totalsMatch) {
          totalNew = parseInt(totalsMatch[1]);
          totalUpdated = parseInt(totalsMatch[2]);
        }
      });

      setParsedStats({
        completed: completed || parsedStats.completed,
        total: total || parsedStats.total,
        currentCategory: currentCategory,
        totalNew: totalNew || parsedStats.totalNew,
        totalUpdated: totalUpdated || parsedStats.totalUpdated,
      });
    }
  }, [logs]);

  const addLog = (message, type = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { timestamp, message, type }]);
  };

  // Parsing & de-duplicating task logs dynamically
  const parseRawLogLines = (logLines) => {
    let parsed = [];
    if (!Array.isArray(logLines)) return parsed;
    logLines.forEach((line) => {
      if (!line || typeof line !== "string" || !line.trim()) return;

      let logType = "info";
      let msg = line.trim();
      let timeStr = new Date().toLocaleTimeString();

      // 1. Handle task status updates first to avoid incorrect stripping
      if (line.includes("[TASK STATUS]")) {
        const parts = line.split(" | ");
        if (parts.length >= 2) {
          const statusPart = parts[1].trim(); // e.g. "Scraping 'Fresh Vegetables' (1/120)"
          if (statusPart.startsWith("Scraping '")) {
            const catName = statusPart.match(/'(.*?)'/)?.[1] || "Category";
            msg = `Crawl target active: ${catName}`;
            logType = "system";
          } else if (statusPart === "RUNNING") {
            msg = `Crawler engine started...`;
            logType = "system";
          } else {
            // Filter out repetitive progress tracking stats to keep terminal engaging
            return;
          }
        } else {
          return;
        }
      } else if (line.includes(" | ")) {
        // 2. Extract timestamp if standard log prefix (e.g. 2026-06-19 18:55:18,904 | INFO | ...)
        const parts = line.split(" | ");
        if (parts.length >= 3) {
          const tsPart = parts[0];
          const levelPart = parts[1].trim();
          const contentPart = parts.slice(2).join(" | ");

          const tsMatch = tsPart.match(/\d{2}:\d{2}:\d{2}/);
          if (tsMatch) timeStr = tsMatch[0];

          msg = contentPart.trim();
          if (levelPart === "ERROR" || levelPart === "CRITICAL") {
            logType = "error";
          } else if (levelPart === "WARNING") {
            logType = "warning";
          } else if (contentPart.includes("SUCCESS") || contentPart.includes("Complete") || contentPart.includes("synced")) {
            logType = "success";
          } else if (contentPart.includes("Initializing") || contentPart.includes("Process finished")) {
            logType = "system";
          }
        }
      }

      // Categorize log line style by message content
      const u = msg.toUpperCase();
      if (u.includes("ERROR") || u.includes("FAILED")) {
        logType = "error";
      } else if (u.includes("[OK]") || u.includes("COMPLETE!") || u.includes("SUCCESS")) {
        logType = "success";
      } else if (u.includes("WARNING") || u.includes("SKIP") || u.includes("HALTING")) {
        logType = "warning";
      } else if (msg.startsWith("===") || msg.startsWith("---") || msg.startsWith("[DB]") || msg.includes("Initializing")) {
        logType = "system";
      }

      // Avoid consecutive duplicate log message rendering
      if (parsed.length > 0 && parsed[parsed.length - 1].message === msg) {
        return;
      }

      parsed.push({
        timestamp: timeStr,
        message: msg,
        type: logType,
      });
    });
    return parsed;
  };

  const pollTaskStatus = (taskId) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await api.get(`/tasks/${taskId}?t=${Date.now()}`);
        const task = response.data;
        if (!task) return;

        // Fetch real-time logs from task log file
        let logLines = [];
        try {
          const logsResponse = await api.get(`/tasks/${taskId}/logs?t=${Date.now()}`);
          logLines = logsResponse.data.logs || [];
        } catch (logErr) {
          console.error("Error polling task logs:", logErr);
        }

        // Parse and clean logs (de-duplicate & screen spam status lines)
        if (logLines.length > 0) {
          setLogs(parseRawLogLines(logLines));
        }

        const statusUpper = task.status ? task.status.toUpperCase() : "";

        if (statusUpper === "COMPLETED" || statusUpper === "SUCCESS") {
          const finalMsg = `[SUCCESS] JioMart scraping completed successfully! Synced leads correctly.`;
          const finalTime = new Date().toLocaleTimeString();
          setLogs((prev) => {
            const hasFinal = prev.some((l) => l.message.includes("completed successfully!"));
            if (hasFinal) return prev;
            return [...prev, { timestamp: finalTime, message: finalMsg, type: "success" }];
          });
          setLoading(false);
          fetchRecentProducts();
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        } else if (
          statusUpper.startsWith("FAILED") || 
          statusUpper.startsWith("ERROR") || 
          statusUpper === "STOPPED"
        ) {
          const errMsg = task.error_message || task.status || "Scraper failed or halted.";
          const finalMsg = `[ERROR] Execution failed: ${errMsg}`;
          const finalTime = new Date().toLocaleTimeString();
          setLogs((prev) => {
            const hasFinal = prev.some((l) => l.message.includes("Execution failed:"));
            if (hasFinal) return prev;
            return [...prev, { timestamp: finalTime, message: finalMsg, type: "error" }];
          });
          setError(errMsg);
          setLoading(false);
          fetchRecentProducts();
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      } catch (err) {
        console.error("Error polling task status:", err);
      }
    }, 2000);
  };

  // Initial fetch of recent products on mount
  useEffect(() => {
    fetchRecentProducts();
  }, []);

  const handleScrape = async () => {
    setError("");
    setResult(null);
    setLogs([]);
    setLoading(true);
    setParsedStats({
      completed: 0,
      total: 0,
      currentCategory: "Starting...",
      totalNew: 0,
      totalUpdated: 0,
    });

    addLog(`[SYSTEM] Initializing JioMart Scraper Engine...`, "system");
    addLog(`[CONFIG] Resume option: ${resume ? "ENABLED" : "DISABLED"}`, "info");
    if (maxCategories) {
      addLog(`[CONFIG] Scope Limit: ${maxCategories} categories`, "warning");
    } else {
      addLog(`[CONFIG] Scope Limit: ALL categories`, "info");
    }

    try {
      addLog(`[API] Dispatching scraper execution task to backend...`, "info");

      const response = await api.post(
        "/scrape_jiomart",
        {
          resume: resume,
          max_categories: maxCategories ? parseInt(maxCategories) : null,
        },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      addLog(`[CELERY] Task successfully queued! Task ID: ${response.data.task_id}`, "success");
      addLog(`[CELERY] Job message: ${response.data.message}`, "info");

      setResult(response.data);
      pollTaskStatus(response.data.task_id);
    } catch (err) {
      console.error("Scraping Error:", err);
      const errMsg = err.response?.data?.error || "Failed to trigger JioMart scraper.";
      setError(errMsg);
      addLog(`[ERROR] Execution halted: ${errMsg}`, "error");
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!result?.task_id) return;
    addLog(`[SYSTEM] Requesting crawler halt for task ${result.task_id}...`, "warning");
    try {
      await api.post("/stop", { task_id: result.task_id });
      addLog(`[SYSTEM] Stop signal sent. Crawler is stopping...`, "warning");
    } catch (err) {
      console.error("Stop Error:", err);
      addLog(`[ERROR] Failed to send stop signal: ${err.message}`, "error");
    }
  };

  // Download log file utility
  const handleDownloadLogs = () => {
    if (logs.length === 0) return;
    const logContent = logs
      .map((l) => `[${l.timestamp}] [${l.type.toUpperCase()}] ${l.message}`)
      .join("\n");
    const blob = new Blob([logContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `jiomart_scrape_${result?.task_id || "task"}_logs.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Render log lines into clean, highly readable monospaced lines
  const formatTerminalLogLine = (log, index) => {
    const line = log.message || "";
    
    // Parse completed category status
    // [85/120] [OK] Groceries > Fruits & Vegetables > Fresh Vegetables | Pages: 2 | New: 4 | Updated: 80
    const okMatch = line.match(/\[(\d+)\/(\d+)\]\s+\[OK\]\s+(.*?)\s*\|\s*Pages:\s*(\d+)\s*\|\s*New:\s*(\d+)\s*\|\s*Updated:\s*(\d+)/);
    if (okMatch) {
      const idxStr = `[${okMatch[1]}/${okMatch[2]}]`;
      const path = okMatch[3].trim();
      const pages = okMatch[4];
      const newItems = parseInt(okMatch[5]);
      const updatedItems = parseInt(okMatch[6]);
      
      return (
        <div key={index} className="flex flex-wrap gap-x-2 leading-relaxed text-green-400 font-medium">
          <span className="text-gray-500 select-none">[{log.timestamp}]</span>
          <span>✓</span>
          <span className="text-blue-400 font-bold">{idxStr}</span>
          <span className="text-gray-200">{path}</span>
          <span className="text-gray-500">|</span>
          <span className="text-gray-400">Pages: {pages}</span>
          <span className="text-gray-500">|</span>
          {newItems > 0 && <span className="text-emerald-400">+{newItems} New</span>}
          {newItems > 0 && updatedItems > 0 && <span className="text-gray-500">,</span>}
          {updatedItems > 0 && <span className="text-amber-400">+{updatedItems} Updated</span>}
          {newItems === 0 && updatedItems === 0 && <span className="text-gray-500">No Changes</span>}
        </div>
      );
    }

    // Header dividers
    if (line.startsWith("===") || line.startsWith("---")) {
      return (
        <div key={index} className="text-blue-400 py-1 font-bold border-b border-gray-800 tracking-wider">
          {line}
        </div>
      );
    }

    // Database changes
    if (line.startsWith("[DB]") || line.includes("Database")) {
      return (
        <div key={index} className="flex gap-2 leading-relaxed text-indigo-300">
          <span className="text-gray-500 select-none">[{log.timestamp}]</span>
          <span>[DB]</span>
          <span>{line.replace(/^\[DB\]\s*/i, "")}</span>
        </div>
      );
    }

    // Standard log levels
    const colorMap = {
      success: "text-green-400",
      error:   "text-red-400 font-bold",
      warning: "text-amber-300",
      system:  "text-sky-300 font-semibold",
      info:    "text-gray-200",
    };

    return (
      <div key={index} className="flex gap-2 leading-relaxed">
        <span className="text-gray-500 select-none shrink-0">[{log.timestamp}]</span>
        <span className={colorMap[log.type] || "text-gray-200"}>{line}</span>
      </div>
    );
  };

  // Filter logs by search query & filter button selection
  const filteredLogs = logs.filter((log) => {
    // Filter Type
    if (logFilter !== "all" && log.type !== logFilter) return false;
    
    // Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        log.message.toLowerCase().includes(q) ||
        log.timestamp.toLowerCase().includes(q) ||
        log.type.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const progressPercent = parsedStats.total > 0 ? (parsedStats.completed / parsedStats.total) * 100 : 0;

  return (
    <div className="bg-gray-50 min-h-screen p-6 space-y-6">
      
      {/* ── Header Card (DMart Style) ─────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-xl border border-blue-gray-100 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-md bg-blue-600 text-white">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-8 h-8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5V6a3.75 3.75 0 1 0-7.5 0v4.5m11.356-1.993 1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 0 1-1.12-1.243l1.264-12A1.125 1.125 0 0 1 5.513 7.5h12.974c.576 0 1.059.435 1.119 1.007ZM8.625 10.5a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm7.5 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
            </svg>
          </div>
          <div>
            <Typography variant="h3" color="blue-gray" className="font-extrabold tracking-tight">
              JioMart Automation Scraper
            </Typography>
            <Typography className="text-sm text-gray-500 mt-1 font-medium">
              Asynchronous crawler pipeline targeting JioMart grocery catalogues, updating products taxonomy and syncing changes to MySQL.
            </Typography>
          </div>
        </div>
        {result?.task_id && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400 font-mono">Task #{result.task_id}</span>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
              loading ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-600"
            }`}>
              <span className={`w-2 h-2 rounded-full ${loading ? "bg-blue-500 animate-pulse" : "bg-gray-400"}`} />
              {loading ? "RUNNING" : "STANDBY"}
            </span>
          </div>
        )}
      </div>

      {/* ── Main Grid ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Panel: Scraper Controls & Live Status (5 columns) */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <Card className="shadow-sm border border-blue-gray-100 bg-white">
            <CardBody className="p-6 space-y-6">
              <Typography variant="h5" color="blue-gray" className="font-bold flex items-center gap-2 pb-2 border-b border-gray-100">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-600" />
                Scraper Configuration
              </Typography>

              {/* Toggle Resume Mode */}
              <div className="relative flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div className="flex flex-col gap-0.5 max-w-[75%]">
                  <label className="text-sm font-bold text-slate-700 cursor-pointer select-none">
                    Resume Last Run
                  </label>
                  <span className="text-[11px] text-slate-400 leading-tight">
                    Skip previously crawled categories and resume from progress marker.
                  </span>
                </div>
                <button
                  onClick={() => setResume(!resume)}
                  disabled={loading}
                  className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none ${
                    resume ? "bg-blue-600" : "bg-slate-200"
                  } ${loading ? "opacity-50" : ""}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      resume ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              {/* Input Limit */}
              <div className="space-y-1.5">
                <Typography className="text-xs uppercase text-slate-500 font-extrabold tracking-wider">
                  Scope Limit (Max Categories)
                </Typography>
                <Input
                  type="number"
                  placeholder="No limit (scrapes all items)"
                  value={maxCategories}
                  onChange={(e) => setMaxCategories(e.target.value)}
                  disabled={loading}
                  className="!border-t-blue-gray-200 focus:!border-blue-500 !border-slate-200"
                  labelProps={{ className: "hidden" }}
                />
              </div>

              {/* Action Buttons */}
              <div className="pt-2 space-y-2">
                {!loading ? (
                  <Button
                    onClick={handleScrape}
                    fullWidth
                    className="bg-blue-600 hover:bg-blue-700 text-sm font-bold flex items-center justify-center gap-2 py-3 shadow-md hover:shadow-lg text-white rounded-xl transition-all"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                    </svg>
                    Start JioMart Scrape
                  </Button>
                ) : (
                  <Button
                    onClick={handleStop}
                    fullWidth
                    className="bg-red-600 hover:bg-red-700 text-sm font-bold flex items-center justify-center gap-2 py-3 shadow-md hover:shadow-lg text-white rounded-xl transition-all"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 7.5A2.25 2.25 0 0 1 7.5 5.25h9a2.25 2.25 0 0 1 2.25 2.25v9a2.25 2.25 0 0 1-2.25 2.25h-9a2.25 2.25 0 0 1-2.25-2.25v-9Z" />
                    </svg>
                    Stop Scraper Engine
                  </Button>
                )}
              </div>

              {error && (
                <div className="p-3 bg-red-50 border border-red-100 rounded-xl">
                  <Typography className="text-xs text-red-600 font-semibold">
                    ⚠️ Error: {error}
                  </Typography>
                </div>
              )}
            </CardBody>
          </Card>

          {/* Scrape Progress Panel (DMart style) */}
          {result?.task_id && (
            <Card className="shadow-sm border border-blue-gray-100 bg-white">
              <CardBody className="p-6 space-y-4">
                <Typography variant="h6" color="blue-gray" className="font-bold flex items-center gap-2 pb-2 border-b border-gray-100">
                  <div className="w-2.5 h-2.5 rounded-full bg-blue-600" />
                  Live Syncing Progress
                </Typography>

                <div className="space-y-3">
                  <div className="flex justify-between items-center text-xs text-gray-500 font-mono">
                    <span className="font-bold">Execution progress</span>
                    <span className="font-extrabold text-blue-600">{Math.round(progressPercent)}%</span>
                  </div>
                  <ProgressBar value={progressPercent} />
                  <div className="grid grid-cols-2 gap-4 text-xs font-mono pt-1 text-gray-600">
                    <div>
                      <span className="text-gray-400">Categories:</span>{" "}
                      <span className="font-extrabold text-gray-800">{parsedStats.completed} / {parsedStats.total}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Timer:</span>{" "}
                      <span className="font-extrabold text-gray-800">{formatTime(elapsedTime)}</span>
                    </div>
                    <div className="col-span-2 border-t border-slate-50 pt-2 flex justify-between text-slate-700">
                      <span className="text-gray-400">New products found:</span>{" "}
                      <span className="font-extrabold text-emerald-600">+{parsedStats.totalNew.toLocaleString()}</span>
                    </div>
                    <div className="col-span-2 flex justify-between text-slate-700">
                      <span className="text-gray-400">Products updated:</span>{" "}
                      <span className="font-extrabold text-blue-600">+{parsedStats.totalUpdated.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </CardBody>
            </Card>
          )}
        </div>

        {/* Right Panel: Terminal Logs (7 columns) */}
        <div className="lg:col-span-7 flex flex-col">
          <Card className="shadow-lg border border-gray-800 flex-1 flex flex-col bg-gray-900 text-white rounded-xl overflow-hidden h-[540px] min-h-[540px] max-h-[540px]">
            {/* Terminal Window Header */}
            <div className="bg-gray-850 px-5 py-3 border-b border-gray-800 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 flex-shrink-0">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5 flex-shrink-0">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <span className="text-xs text-gray-400 font-mono ml-2">
                  jiomart-pipeline-worker@logs
                </span>
              </div>

              {/* Logs Search Input */}
              <div className="relative w-full sm:w-44">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="absolute left-2 top-2.5 h-3 w-3 text-gray-500">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m21-21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
                </svg>
                <input
                  type="text"
                  placeholder="Filter outputs..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-gray-955 text-[11px] text-slate-200 pl-7 pr-2.5 py-1.5 rounded border border-gray-850 focus:border-blue-500 focus:outline-none placeholder-gray-600 font-mono transition-colors"
                />
              </div>
            </div>

            {/* Terminal Options / Filters bar */}
            <div className="bg-[#1a2130] px-5 py-2.5 border-b border-gray-800 flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
              <div className="flex flex-wrap gap-1">
                {["all", "system", "success", "warning", "error"].map((type) => (
                  <button
                    key={type}
                    onClick={() => setLogFilter(type)}
                    className={`text-[9px] font-mono font-bold uppercase px-2.5 py-1 rounded transition-colors ${
                      logFilter === type
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-4">
                {/* Auto Scroll Toggle */}
                <label className="flex items-center gap-1.5 cursor-pointer select-none text-[9px] font-mono font-bold text-slate-400 hover:text-slate-200">
                  <input
                    type="checkbox"
                    checked={autoScroll}
                    onChange={(e) => setAutoScroll(e.target.checked)}
                    className="w-3.5 h-3.5 rounded border border-gray-800 bg-gray-950 text-blue-600 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-blue-600"
                  />
                  <span>Auto-scroll</span>
                </label>

                <button
                  onClick={handleDownloadLogs}
                  disabled={logs.length === 0}
                  className="text-[9px] font-mono font-bold text-slate-400 hover:text-white flex items-center gap-1 bg-gray-950 border border-gray-800 px-2.5 py-1 rounded transition-colors disabled:opacity-50"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  Export Logs
                </button>
              </div>
            </div>

            {/* Terminal Log Area */}
            <div className="flex-1 p-5 overflow-y-auto space-y-1.5 custom-scrollbar bg-[#0f1422] font-mono text-xs">
              {filteredLogs.length === 0 ? (
                <div className="text-gray-600 italic h-full flex flex-col items-center justify-center gap-2 font-mono text-xs">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor" className="w-10 h-10 opacity-30">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0 0 21 18V6a2.25 2.25 0 0 0-2.25-2.25H5.25A2.25 2.25 0 0 0 3 6v12a2.25 2.25 0 0 0 2.25 2.25Z" />
                  </svg>
                  <span>{searchQuery ? "No matches found." : "Terminal idle — launch a crawl job to watch logs"}</span>
                </div>
              ) : (
                filteredLogs.map((log, idx) => formatTerminalLogLine(log, idx))
              )}
              <div ref={terminalEndRef} />
            </div>
            
            {/* Terminal Window Footer */}
            <div className="bg-gray-850 px-5 py-2.5 flex justify-between items-center border-t border-gray-800 text-[10px] text-gray-500 font-mono flex-shrink-0">
              <span className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${loading ? "bg-blue-500 animate-pulse" : "bg-gray-600"}`} />
                <span>{loading ? "ENGINES ACTIVE" : "ENGINE STANDBY"}</span>
              </span>
              <div className="flex items-center gap-3">
                <span>Lines: {filteredLogs.length}</span>
                <span className="text-gray-700">|</span>
                <button 
                  onClick={() => setLogs([])}
                  className="hover:text-white uppercase font-bold text-gray-600 transition-colors"
                >
                  Clear Console
                </button>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Live Data Grid (10 most recent products) */}
      <div className="space-y-4 pt-4">
        <div className="flex justify-between items-center">
          <div>
            <Typography variant="h5" color="blue-gray" className="font-extrabold text-slate-800">
              JioMart Catalogue - Database Stream
            </Typography>
            <Typography className="text-xs text-slate-500">
              Showing the most recent 10 products successfully saved to the database.
            </Typography>
          </div>
          <Button 
            variant="outlined" 
            size="sm" 
            color="blue-gray" 
            className="flex items-center gap-1.5 font-bold border-slate-200 text-slate-600 py-2 hover:bg-slate-50 bg-white"
            onClick={fetchRecentProducts}
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            Refresh Stream
          </Button>
        </div>

        {!Array.isArray(recentProducts) || recentProducts.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-100 p-8 text-center text-slate-400 italic text-xs">
            No scraped products detected in DB. Start crawling to populate items here.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {recentProducts.map((prod, idx) => {
              const discount = prod.mrp && prod.price && prod.mrp > prod.price 
                ? Math.round(((prod.mrp - prod.price) / prod.mrp) * 100) 
                : 0;

              return (
                <a 
                  key={idx} 
                  href={prod.product_url || `https://www.jiomart.com/search/${encodeURIComponent(prod.product_name)}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="bg-white rounded-xl border border-slate-100 p-3.5 flex flex-col justify-between hover:shadow-md hover:border-blue-200 transition-all duration-200 group cursor-pointer relative"
                >
                  <div className="space-y-3">
                    {/* Image Thumbnail */}
                    <div className="relative aspect-square w-full bg-slate-50 rounded-lg overflow-hidden flex items-center justify-center border border-slate-100">
                      {prod.image_url ? (
                        <img 
                          src={prod.image_url} 
                          alt={prod.product_name} 
                          className="object-contain max-h-full max-w-full p-2 group-hover:scale-105 transition-transform duration-200"
                          loading="lazy"
                        />
                      ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10 text-slate-350">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5V6a3.75 3.75 0 1 0-7.5 0v4.5m11.356-1.993 1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 0 1-1.12-1.243l1.264-12A1.125 1.125 0 0 1 5.513 7.5h12.974c.576 0 1.059.435 1.119 1.007ZM8.625 10.5a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm7.5 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
                        </svg>
                      )}
                      
                      {discount > 0 && (
                        <span className="absolute top-2 left-2 bg-emerald-500 text-white text-[9px] font-bold px-2 py-0.5 rounded shadow-sm">
                          -{discount}%
                        </span>
                      )}

                      {/* Clickable indicator link icon */}
                      {prod.product_url && (
                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 p-1.5 rounded shadow-sm text-slate-500 hover:text-blue-600 hover:scale-110">
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                          </svg>
                        </div>
                      )}
                    </div>

                    <div className="space-y-1">
                      {/* Brand name */}
                      <p className="text-[10px] font-extrabold text-blue-600 uppercase tracking-wider truncate">
                        {prod.brand || "JioMart"}
                      </p>
                      {/* Product Title */}
                      <h4 className="text-xs font-bold text-slate-800 leading-snug line-clamp-2 h-9 group-hover:text-blue-600 transition-colors" title={prod.product_name}>
                        {prod.product_name}
                      </h4>
                    </div>
                  </div>

                  <div className="pt-2 mt-3 border-t border-slate-100 space-y-1.5">
                    {/* Prices */}
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-sm font-extrabold text-slate-900">
                        ₹{prod.price ?? "-"}
                      </span>
                      {discount > 0 && (
                        <span className="text-xs text-slate-400 line-through">
                          ₹{prod.mrp}
                        </span>
                      )}
                    </div>
                    {/* Category Label */}
                    {prod.category_name && (
                      <span className="inline-block max-w-full truncate text-[9px] font-bold bg-slate-50 text-slate-500 px-2 py-0.5 rounded border border-slate-100/50">
                        {prod.category_name}
                      </span>
                    )}
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default JiomartScrapper;