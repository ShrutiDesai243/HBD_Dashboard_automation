import React, { useState, useEffect, useRef } from "react";
import {
  Card,
  CardBody,
  Input,
  Button,
  Typography,
} from "@material-tailwind/react";
import api from "../../utils/Api";

const ZeptoScrapper = () => {
  const [searchTerm, setSearchTerm] = useState("all");
  const mode = "category";
  const [categories, setCategories] = useState("");
  const [maxCategories, setMaxCategories] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);

  const terminalEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

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

  const handleScrape = async (overrideCategories) => {
    setError("");
    setResult(null);
    setLogs([]);
    setLoading(true);

    const targetPincodes = "all";
    const targetCategories =
      overrideCategories !== undefined ? overrideCategories : categories;

    addLog(`[SYSTEM] Initializing Playwright Scraper Engine...`, "system");
    addLog(`[CONFIG] Running across famous pincodes`, "info");
    addLog(`[CONFIG] Mode selected: ${mode.toUpperCase()}`, "info");
    if (targetCategories) addLog(`[CONFIG] Target categories: ${targetCategories}`, "info");
    if (maxCategories) addLog(`[CONFIG] Limit category cap: ${maxCategories}`, "warning");

    try {
      const response = await api.post(
        "/scrape_zepto",
        {
          search_term: searchTerm,
          mode: mode,
          pincodes: targetPincodes,
          categories: targetCategories || null,
          max_categories: maxCategories ? parseInt(maxCategories) : null,
        },
        { headers: { "Content-Type": "application/json" } }
      );

      addLog(`[CELERY] Task successfully queued! Task ID: ${response.data.task_id}`, "success");
      addLog(`[CELERY] Job message: ${response.data.message}`, "info");

      setResult(response.data);
      pollTaskStatus(response.data.task_id);
    } catch (err) {
      console.error("Scraping Error:", err);
      const errMsg = err.response?.data?.error || "Failed to trigger Zepto scraper.";
      setError(errMsg);
      addLog(`[ERROR] Execution halted: ${errMsg}`, "error");
      setLoading(false);
    }
  };

  const handleScrapeAll = () => {
    setCategories("");
    handleScrape("");
  };

  return (
    <div className="bg-gray-50 min-h-screen p-6 space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-xl border border-blue-gray-100 shadow-sm">
        <div>
          <Typography variant="h3" color="blue-gray" className="font-bold flex items-center gap-3">
            <span className="p-2 bg-green-500 rounded-lg text-white">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-8 h-8">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 0 0-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.924-7.138a60.114 60.114 0 0 0-16.536-1.84M7.5 14.25 5.106 5.272M6 20.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm12.75 0a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z" />
              </svg>
            </span>
            Zepto Automation Scraper
          </Typography>
          <Typography className="text-sm text-gray-500 mt-2 font-medium">
            Deploy an asynchronous, Playwright stealth browser to scrape live pricing, details, and availability from Zepto.
          </Typography>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <Card className="lg:col-span-5 shadow-lg border border-blue-gray-100 h-fit">
          <CardBody className="space-y-6">
            <Typography variant="h5" color="blue-gray" className="font-bold flex items-center gap-2">
              🎛️ Control Panel Configuration
            </Typography>

            <div className="space-y-2">
              <Typography className="text-xs uppercase text-gray-500 font-bold">Desired Categories</Typography>
              <Input
                label="Categories to Scrape"
                placeholder="e.g. Grocery & Staples"
                shrink={true}
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
              />
              <Typography className="text-[10px] text-gray-400 mt-1">
                Comma-separated category names/slugs, or leave blank.
              </Typography>
            </div>

            <div className="space-y-2">
              <Typography className="text-xs uppercase text-gray-500 font-bold">Scope Limit (For Testing)</Typography>
              <Input
                label="Max Categories to Scrape"
                placeholder="Empty for no limit (All)"
                type="number"
                shrink={true}
                value={maxCategories}
                onChange={(e) => setMaxCategories(e.target.value)}
              />
              <Typography className="text-[10px] text-gray-400 mt-1">
                Limit categories crawl for rapid verification.
              </Typography>
            </div>

            <div className="space-y-2">
              <Button
                onClick={() => handleScrape()}
                fullWidth
                disabled={loading}
                className="bg-green-600 text-sm font-bold flex items-center justify-center gap-3 py-3"
              >
                {loading ? (
                  <>
                    <span className="h-5 w-5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                    Scraping background jobs active...
                  </>
                ) : (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                    </svg>
                    Start Zepto Scrape
                  </>
                )}
              </Button>

              {!loading && (
                <Button
                  onClick={handleScrapeAll}
                  fullWidth
                  variant="outlined"
                  color="blue-gray"
                  className="text-sm font-bold flex items-center justify-center gap-3 py-3"
                >
                  🧹 Scrape Defaults
                </Button>
              )}

              {error && (
                <div className="p-3 bg-red-50 rounded-md border border-red-100">
                  <Typography color="red" className="text-xs font-semibold">
                    ⚠️ Error: {error}
                  </Typography>
                </div>
              )}
            </div>
          </CardBody>
        </Card>

        <div className="lg:col-span-7 flex flex-col">
          <Card className="shadow-lg border border-blue-gray-100 flex-1 flex flex-col bg-gray-900 text-white rounded-xl overflow-hidden h-[520px] min-h-[520px] max-h-[520px]">
            <div className="bg-gray-800 px-4 py-3 flex justify-between items-center border-b border-gray-700 flex-shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <Typography className="text-xs text-gray-400 font-bold ml-2 font-mono">zepto-playwright-worker@logs</Typography>
              </div>
              <div className="bg-gray-900 text-[10px] px-2 py-0.5 rounded font-mono text-green-400 border border-green-500/20">
                WORKER
              </div>
            </div>

            <div className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-2 no-scrollbar">
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
                        log.type === "success"
                          ? "text-green-400"
                          : log.type === "error"
                          ? "text-red-400 font-bold"
                          : log.type === "system"
                          ? "text-blue-400 font-bold"
                          : log.type === "warning"
                          ? "text-yellow-400"
                          : "text-gray-200"
                      }
                    >
                      {log.message}
                    </span>
                  </div>
                ))
              )}
              <div ref={terminalEndRef} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ZeptoScrapper;

