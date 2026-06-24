import React, { useState, useEffect, useRef } from "react";
import {
  Card,
  CardBody,
  Input,
  Button,
  Typography,
} from "@material-tailwind/react";
import api from "../../utils/Api";

const StatCard = ({ icon, label, value, color = "green" }) => (
  <div className="bg-white rounded-xl p-4 border border-blue-gray-100 shadow-sm flex items-start gap-3">
    <div className={`p-2 rounded-lg bg-${color}-500/10 flex-shrink-0`}>
      <span className={`text-${color}-600 text-xl`}>{icon}</span>
    </div>
    <div>
      <p className="text-gray-500 text-[10px] uppercase font-bold tracking-wider">{label}</p>
      <p className="text-blue-gray-900 text-lg font-bold mt-1">
        {typeof value === "number" ? value.toLocaleString("en-IN") : value}
      </p>
    </div>
  </div>
);

const RecentHistory = () => {
  const [history, setHistory] = useState([]);

  const fetchHistory = async () => {
    try {
      const res = await api.get("/scraper/zepto/history");
      setHistory(res.data?.history || []);
    } catch (err) {
      console.error("Error fetching Zepto history:", err);
    }
  };

  useEffect(() => {
    fetchHistory();
    const timer = setInterval(fetchHistory, 10000);
    return () => clearInterval(timer);
  }, []);

  if (history.length === 0) return null;

  const formatTimeRange = (startedAt, stoppedAt) => {
    if (!startedAt || startedAt === "N/A") return "N/A";
    const startPart = startedAt.slice(0, 16); // "YYYY-MM-DD HH:MM"
    if (!stoppedAt || stoppedAt === "N/A") {
      return `${startPart} → N/A`;
    }
    if (stoppedAt.toLowerCase().includes("running")) {
      return `${startPart} → Running`;
    }
    if (/^\d{4}-\d{2}-\d{2}/.test(stoppedAt)) {
      const startDateStr = startedAt.slice(0, 10);
      const stopDateStr = stoppedAt.slice(0, 10);
      if (startDateStr === stopDateStr) {
        return `${startPart} → ${stoppedAt.slice(11, 16)}`;
      } else {
        return `${startPart} → ${stoppedAt.slice(0, 16)}`;
      }
    }
    return `${startPart} → ${stoppedAt}`;
  };

  const formatPincodes = (pincodes) => {
    if (!pincodes) return "default";
    const arr = pincodes.split(",");
    if (arr.length > 2) {
      return `${arr[0].trim()}, ${arr[1].trim()},...`;
    }
    return pincodes;
  };

  const getStatusBadgeClass = (status) => {
    const s = status ? status.toUpperCase() : "";
    if (s === "COMPLETED") {
      return "bg-green-50 text-green-700 border border-green-200";
    }
    if (s === "RUNNING" || s === "STARTING" || s.includes("SCRAP")) {
      return "bg-yellow-50 text-yellow-700 border border-yellow-200 animate-pulse";
    }
    if (s === "FAILED" || s === "ERROR") {
      return "bg-red-50 text-red-700 border border-red-200";
    }
    if (s === "STOPPED") {
      return "bg-orange-50 text-orange-700 border border-orange-200";
    }
    return "bg-gray-50 text-gray-600 border border-gray-200";
  };

  return (
    <div className="bg-white p-4 rounded-xl border border-blue-gray-100 shadow-sm space-y-3">
      <Typography variant="h6" color="blue-gray" className="font-bold flex items-center gap-2">
        🕐 Recent Scrape History (3 Recent Tasks)
      </Typography>
      <div className="overflow-x-auto">
        <table className="w-full table-auto text-left text-xs text-gray-700">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="py-2 px-3 font-semibold text-gray-600">Query</th>
              <th className="py-2 px-3 font-semibold text-gray-600">Pincodes Scraped</th>
              <th className="py-2 px-3 font-semibold text-gray-600">Time</th>
              <th className="py-2 px-3 font-semibold text-gray-600">Status</th>
              <th className="py-2 px-3 font-semibold text-gray-600">Items Scraped</th>
            </tr>
          </thead>
          <tbody>
            {history.map((t) => (
              <tr key={t.id} title={`Task ID: #${t.id}`} className="border-b border-gray-100 hover:bg-gray-50/50">
                <td className="py-2.5 px-3 font-medium">{t.query}</td>
                <td className="py-2.5 px-3 font-medium" title={t.pincodes}>{formatPincodes(t.pincodes)}</td>
                <td className="py-2.5 px-3 text-gray-500 font-mono">{formatTimeRange(t.started_at, t.stopped_at)}</td>
                <td className="py-2.5 px-3">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${getStatusBadgeClass(t.status)}`}>
                    {t.status}
                  </span>
                </td>
                <td className="py-2.5 px-3 font-bold text-green-600">{t.total_leads?.toLocaleString("en-IN") || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const ZeptoScrapper = () => {
  const [category, setCategory] = useState("");
  const [pincodes, setPincodes] = useState("");
  const [resume, setResume] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dbStats, setDbStats] = useState({ total_products: 0, total_categories: 0 });
  const [statusInfo, setStatusInfo] = useState({
    status: "idle",
    current_category: null,
    current_subcategory: null,
    current_pincode: null,
    total_scraped: 0,
    products_inserted: 0,
    products_updated: 0,
    products_skipped: 0,
    categories_scraped: 0,
    new_categories_mapped: 0,
    errors_count: 0,
    warnings_count: 0,
  });
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");


  const terminalContainerRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Scroll logs inside container without scrolling the main browser page
  useEffect(() => {
    const container = terminalContainerRef.current;
    if (container) {
      // Check if user is scrolled near bottom (100px threshold)
      const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= 100;
      if (isAtBottom) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [logs]);

  const fetchDbStats = async () => {
    try {
      const res = await api.get("/scraper/zepto/db-stats");
      if (res.data && res.data.status === "success") {
        setDbStats({
          total_products: res.data.total_products,
          total_categories: res.data.total_categories,
        });
      }
    } catch (err) {
      console.error("Error fetching Zepto DB stats:", err);
    }
  };

  // Fetch initial status on mount and manage polling if active
  useEffect(() => {
    const fetchInitialStatus = async () => {
      try {
        const res = await api.get("/scraper/zepto/status");
        if (res.data && res.data.data) {
          const stateData = res.data.data;
          setStatusInfo(stateData);
          if (stateData.status !== "idle") {
            setLoading(true);
            startPolling();
          }
        }
      } catch (err) {
        console.error("Error fetching initial Zepto status:", err);
      }
    };
    fetchInitialStatus();
    fetchDbStats();

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Poll scraper status and logs from backend
  const startPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        // Fetch current status
        const statusResponse = await api.get("/scraper/zepto/status");
        if (statusResponse.data && statusResponse.data.data) {
          const stateData = statusResponse.data.data;
          setStatusInfo(stateData);

          if (stateData.status === "idle") {
            setLoading(false);
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            fetchDbStats();
          } else {
            setLoading(true);
          }
        }

        // Fetch latest logs
        const logsResponse = await api.get("/scraper/zepto/logs?limit=200");
        if (logsResponse.data && logsResponse.data.logs) {
          setLogs(logsResponse.data.logs);
        }
      } catch (err) {
        console.error("Error polling scraper state:", err);
      }
    }, 2000);
  };

  const addLog = (message, type = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { timestamp, message, type }]);
  };

  const pollTaskStatus = (taskId) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await api.get(`/tasks/${taskId}`);
        const task = response.data;

        let logLines = [];
        try {
          const logsResponse = await api.get(`/tasks/${taskId}/logs`);
          logLines = logsResponse.data.logs || [];
        } catch (logErr) {
          console.error("Error polling task logs:", logErr);
        }

        let parsedLogs = [];
        if (logLines.length > 0) {
          parsedLogs = logLines.map((line) => {
            let logType = "info";
            let msg = line;
            let timeStr = new Date().toLocaleTimeString();

            const parts = line.split(" | ");
            if (parts.length >= 3) {
              const tsPart = parts[0];
              const levelPart = parts[1].trim();
              const contentPart = parts.slice(2).join(" | ");

              const tsMatch = tsPart.match(/\d{2}:\d{2}:\d{2}/);
              if (tsMatch) timeStr = tsMatch[0];

              msg = contentPart;
              if (levelPart === "ERROR" || levelPart === "CRITICAL") {
                logType = "error";
              } else if (levelPart === "WARNING") {
                logType = "warning";
              } else if (
                contentPart.includes("SUCCESS") ||
                contentPart.includes("complete") ||
                contentPart.includes("synced")
              ) {
                logType = "success";
              } else if (
                contentPart.includes("Stage") ||
                contentPart.includes("START") ||
                contentPart.includes("Initializing") ||
                contentPart.toLowerCase().includes("zepto")
              ) {
                logType = "system";
              }
            } else {
              const u = line.toUpperCase();
              if (
                u.includes("ERROR") ||
                u.includes("FAILED") ||
                u.includes("EXCEPTION") ||
                u.includes("HALTED")
              ) {
                logType = "error";
              } else if (u.includes("SUCCESS") || u.includes("COMPLETED")) {
                logType = "success";
              } else if (
                u.includes("SKIP") ||
                u.includes("WARNING") ||
                u.includes("ALREADY")
              ) {
                logType = "warning";
              } else if (
                line.startsWith("===") ||
                line.includes("Processing:") ||
                line.includes("Starting") ||
                line.startsWith("[")
              ) {
                logType = "system";
              }
            }

            return { timestamp: timeStr, message: msg, type: logType };
          });
        }

        if (parsedLogs.length > 0) setLogs(parsedLogs);

        if (task.status === "COMPLETED") {
          setLoading(false);
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        } else if (task.status === "ERROR") {
          const errMsg = task.error_message || "Scraper crashed with unknown backend exception.";
          setError(errMsg);
          setLoading(false);

          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }

          addLog(`[ERROR] Execution halted: ${errMsg}`, "error");
        }
      } catch (err) {
        console.error("Error polling task:", err);
      }
    }, 2000);
  };

  const handleStartScrape = async () => {
    setError("");
    setLogs([]);
    setLoading(true);

    try {
      const response = await api.post("/scraper/zepto/start", {
        category: category,
        pincodes: pincodes,
        resume: resume,
      });

      if (response.data.status === "success") {
        startPolling();
      } else {
        setError(response.data.message || "Failed to start scraper");
        setLoading(false);
      }
    } catch (err) {
      console.error("Start Scrape Error:", err);
      setError(err.response?.data?.message || "Failed to trigger Zepto scraper.");
      setLoading(false);
    }
  };

  const handleStopScrape = async () => {
    try {
      await api.post("/scraper/zepto/stop");
    } catch (err) {
      console.error("Stop Scrape Error:", err);
      setError(err.response?.data?.message || "Failed to send stop signal.");
    }
  };

  // Helper for status badge color and text styling
  const getStatusDisplay = () => {
    switch (statusInfo.status) {
      case "running":
        return { text: "RUNNING", color: "bg-green-500 text-white", animate: "animate-pulse" };
      case "stopping":
        return { text: "STOPPING", color: "bg-amber-500 text-white", animate: "animate-pulse" };
      default:
        return { text: "IDLE", color: "bg-gray-500 text-white", animate: "" };
    }
  };

  const statusDisplay = getStatusDisplay();



  return (
    <div className="bg-gray-50 min-h-screen p-6 space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-xl border border-blue-gray-100 shadow-sm">
        <div className="flex-1">
          <Typography variant="h3" color="blue-gray" className="font-bold flex items-center gap-3">
            <span className="p-2 bg-deep-purple-600 rounded-lg text-white">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-8 h-8">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 0 0-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.924-7.138a60.114 60.114 0 0 0-16.536-1.84M7.5 14.25 5.106 5.272M6 20.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm12.75 0a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z" />
              </svg>
            </span>
            Zepto Automation Scraper
          </Typography>
          <Typography className="text-sm text-gray-500 mt-2 font-medium">
            Integrate and manage the Zepto catalog scraper. Extract products by categories sitemap and specific delivery location pincodes.
            Deploy an asynchronous, Playwright stealth browser to scrape live pricing, details, and availability from Zepto.
          </Typography>
        </div>
        <div className="flex items-center gap-3 text-sm flex-shrink-0">
          <div className="bg-gray-50 rounded-xl px-4 py-2 border border-gray-200 text-center shadow-sm">
            <p className="text-gray-500 text-[10px] uppercase font-bold tracking-wider">DB Products</p>
            <p className="text-green-600 font-bold text-lg font-mono">{dbStats.total_products.toLocaleString("en-IN")}</p>
          </div>
          <div className="bg-gray-50 rounded-xl px-4 py-2 border border-gray-200 text-center shadow-sm">
            <p className="text-gray-500 text-[10px] uppercase font-bold tracking-wider">Mapped Categories</p>
            <p className="text-blue-600 font-bold text-lg font-mono">{dbStats.total_categories.toLocaleString("en-IN")}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Settings Panel */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <Card className="shadow-lg border border-blue-gray-100 h-fit">
            <CardBody className="space-y-6">
              <Typography variant="h5" color="blue-gray" className="font-bold flex items-center gap-2">
                🎛️ Control Panel Configuration
              </Typography>

              {/* Input: Category keyword */}
              <div className="space-y-2">
                <Typography className="text-xs uppercase text-gray-500 font-bold">
                  Category Keywords (Comma-separated)
                </Typography>
                <Input
                  label="Search Keywords (comma-separated) or Sitemap URL"
                  placeholder="e.g. Snacks, Beverages, Chocolates"
                  shrink={true}
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  disabled={loading}
                />
                 <Typography className="text-[10px] text-gray-400 mt-1">
                   Enter category or leave empty for all categories
                 </Typography>
              </div>

              {/* Input: Pincodes */}
              <div className="space-y-2">
                <Typography className="text-xs uppercase text-gray-500 font-bold">
                  Target Pincodes
                </Typography>
                <Input
                  label="Comma-separated Pincodes"
                  placeholder="e.g. 560001, 400001"
                  shrink={true}
                  value={pincodes}
                  onChange={(e) => setPincodes(e.target.value)}
                  disabled={loading}
                />
                 <Typography className="text-[10px] text-gray-400 mt-1">
                   Enter pincodes or leave empty for default pincodes
                 </Typography>
              </div>

              {/* Resume Toggle */}
              <div className="flex items-center gap-3 bg-gray-50 rounded-xl p-3 border border-gray-200">
                <button
                  type="button"
                  onClick={() => !loading && setResume(r => !r)}
                  disabled={loading}
                  className={`w-11 h-6 rounded-full transition-all relative ${resume ? "bg-deep-purple-600" : "bg-gray-300"}`}
                >
                  <div className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all"
                       style={{ left: resume ? "22px" : "2px" }} />
                </button>
                <div>
                  <Typography className="text-sm font-semibold text-blue-gray-800">Resume Last Run</Typography>
                  <Typography className="text-[10px] text-gray-500">Skips already-scraped pincodes and categories</Typography>
                </div>
              </div>

              {/* Scraper Status Card */}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
                <div className="flex justify-between items-center">
                  <Typography className="text-xs font-bold text-gray-600 uppercase">Scraper Status</Typography>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${statusDisplay.color} ${statusDisplay.animate}`}>
                    {statusDisplay.text}
                  </span>
                </div>

                {statusInfo.current_category && (
                  <div className="pt-2 border-t border-gray-200">
                    <Typography className="text-[10px] text-gray-400 font-bold uppercase">Active Target</Typography>
                    <Typography className="text-xs font-semibold text-gray-700 truncate">
                      {statusInfo.current_category} {statusInfo.current_subcategory && ` > ${statusInfo.current_subcategory}`}
                    </Typography>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex gap-4">
                {statusInfo.status === "idle" ? (
                  <Button
                    onClick={handleStartScrape}
                    fullWidth
                    className="bg-deep-purple-600 text-sm font-bold flex items-center justify-center gap-3 py-3"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                    </svg>
                    Start Scrape
                  </Button>
                ) : (
                  <Button
                    onClick={handleStopScrape}
                    fullWidth
                    disabled={statusInfo.status === "stopping"}
                    className="bg-red-600 text-sm font-bold flex items-center justify-center gap-3 py-3"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 7.5A2.25 2.25 0 0 1 7.5 5.25h9a2.25 2.25 0 0 1 2.25 2.25v9a2.25 2.25 0 0 1-2.25 2.25h-9A2.25 2.25 0 0 1 5.25 16.5v-9Z" />
                    </svg>
                    Stop Scrape
                  </Button>
                )}
              </div>

              {error && (
                <div className="p-3 bg-red-50 rounded-md border border-red-100">
                  <Typography color="red" className="text-xs font-semibold">
                    ⚠️ Error: {error}
                  </Typography>
                </div>
              )}
            </CardBody>
          </Card>

          {/* Active/Last Run Summary Box */}
          <Card className="shadow-lg border border-blue-gray-100 p-4 space-y-3 bg-white">
            <Typography variant="h6" color="blue-gray" className="font-bold flex items-center gap-2">
              📊 Last/Active Scrape Run Details
            </Typography>
            <div className="space-y-2 text-xs text-gray-700">
              <div className="flex justify-between items-center py-1.5 border-b border-gray-100">
                <span className="text-gray-500 font-semibold">Target Pincodes:</span>
                <span className="font-bold text-gray-900 font-mono truncate max-w-[180px]" title={statusInfo.target_pincodes}>{statusInfo.target_pincodes || "None"}</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-100">
                <span className="text-gray-500 font-semibold">Active Pincode:</span>
                <span className="font-bold text-gray-900 font-mono">{statusInfo.current_pincode || "None"}</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-100">
                <span className="text-gray-500 font-semibold">Categories Scraped:</span>
                <span className="font-bold text-blue-600">{statusInfo.categories_scraped}</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-100">
                <span className="text-gray-500 font-semibold">New Categories Mapped:</span>
                <span className="font-bold text-indigo-600">{statusInfo.new_categories_mapped}</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-100">
                <span className="text-gray-500 font-semibold">New Products Added:</span>
                <span className="font-bold text-green-600">{statusInfo.products_inserted}</span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-gray-100">
                <span className="text-gray-500 font-semibold">Updated Products:</span>
                <span className="font-bold text-purple-600">{statusInfo.products_updated}</span>
              </div>

              {/* Newly Added Categories List */}
              <div className="pt-2 border-b border-gray-100 pb-2">
                <Typography className="text-[10px] uppercase text-gray-500 font-bold mb-1">Newly Added Categories</Typography>
                {statusInfo.new_categories && statusInfo.new_categories.length > 0 ? (
                  <div className="max-h-[100px] overflow-y-auto border border-gray-100 rounded p-1.5 space-y-1 bg-gray-50/50">
                    {statusInfo.new_categories.map((c, i) => {
                      const name = typeof c === "object" ? c.name : c;
                      const pincode = typeof c === "object" ? c.pincode : null;
                      return (
                        <div key={i} className="text-[10px] flex justify-between items-center text-indigo-700 gap-2">
                          <span className="truncate max-w-[200px]" title={name}>{name}</span>
                          {pincode && (
                            <span className="font-mono text-indigo-600 bg-indigo-50 px-1 rounded text-[9px] font-bold flex-shrink-0">{pincode}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-[10px] text-gray-400 italic bg-gray-50/50 p-2 rounded border border-gray-100">
                    No new categories mapped in this run.
                  </div>
                )}
              </div>

              {/* Newly Added Products List */}
              <div className="pt-2">
                <Typography className="text-[10px] uppercase text-gray-500 font-bold mb-1">Newly Added Products</Typography>
                {statusInfo.new_products && statusInfo.new_products.length > 0 ? (
                  <div className="max-h-[120px] overflow-y-auto border border-gray-100 rounded p-1.5 space-y-1 bg-gray-50/50">
                    {statusInfo.new_products.map((p, i) => (
                      <div key={i} className="text-[10px] flex justify-between items-center text-gray-800 gap-2">
                        <span className="truncate max-w-[200px]" title={p.name}>{p.name}</span>
                        <span className="font-mono text-green-600 bg-green-50 px-1 rounded text-[9px] font-bold flex-shrink-0">{p.pincode}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-[10px] text-gray-400 italic bg-gray-50/50 p-2 rounded border border-gray-100">
                    No new products added in this run.
                  </div>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Right Side: Stats Grid & Log Console Terminal */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <StatCard icon="🛒" label="Scraped" value={statusInfo.total_scraped} color="green" />
            <StatCard icon="✨" label="Inserted" value={statusInfo.products_inserted} color="blue" />
            <StatCard icon="♻️" label="Updated" value={statusInfo.products_updated} color="purple" />
            <StatCard icon="🛡️" label="Skipped" value={statusInfo.products_skipped} color="orange" />
            <StatCard icon="📂" label="Cats Scraped" value={statusInfo.categories_scraped} color="teal" />
            <StatCard icon="🗂️" label="New Mapped" value={statusInfo.new_categories_mapped} color="indigo" />
          </div>

          <Card className="shadow-lg border border-blue-gray-100 flex-1 flex flex-col bg-gray-900 text-white rounded-xl overflow-hidden h-[380px] min-h-[380px] max-h-[380px]">
            <div className="bg-gray-800 px-4 py-3 flex justify-between items-center border-b border-gray-700 flex-shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <Typography className="text-xs text-gray-400 font-bold ml-2 font-mono">
                  zepto-scraper-background@logs
                </Typography>
              </div>
              <div className="bg-gray-900 text-[10px] px-2 py-0.5 rounded font-mono text-deep-purple-400 border border-deep-purple-500/20">
                {statusInfo.status.toUpperCase()}
              </div>
            </div>

            {/* Terminal Logs Screen */}
            <div
              ref={terminalContainerRef}
              className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-2 no-scrollbar"
            >
              {logs.length === 0 ? (
                <div className="text-gray-500 italic h-full flex items-center justify-center">
                  Terminal inactive. Start Zepto scrape to watch live execution logs.
                </div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className="leading-relaxed flex items-start gap-2">
                    <span className="text-gray-500 select-none">[{log.timestamp}]</span>
                    <span
                      className={
                        log.level === "ERROR" || log.type === "error"
                          ? "text-red-400 font-bold"
                          : log.level === "WARNING" || log.type === "warning"
                          ? "text-yellow-400"
                          : log.type === "success" || log.message?.includes("successfully")
                          ? "text-green-400"
                          : log.type === "system"
                          ? "text-blue-400 font-bold"
                          : "text-gray-200"
                      }
                    >
                      {log.message}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Card>
          <RecentHistory />
        </div>
      </div>
    </div>
  );
};

export default ZeptoScrapper;
