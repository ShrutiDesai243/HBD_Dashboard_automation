import React, { useState, useEffect, useRef } from "react";
import { Card, CardBody, Input, Button, Typography } from "@material-tailwind/react";
import api from "../../utils/Api";

/**
 * FlipkartScrapper – UI component for triggering Flipkart scraping jobs.
 * Layout:
 *   • Top full‑width configuration bar containing the search term input,
 *     max‑pages input and a START SCRAPING button.
 *   • Bottom dark terminal‑style card that streams live logs from the backend.
 * The API request mirrors the D‑Mart implementation and posts to
 * "/scrape_flipkart". The Axios instance (utils/Api.jsx) is configured with
 * `withCredentials: true`, so the JWT access token cookie is automatically sent.
 */
const FlipkartScrapper = () => {
  // ==== State ====
  const [searchTerm, setSearchTerm] = useState("all");
  const [maxPages, setMaxPages] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);

  // ==== Refs for scrolling & polling ====
  const terminalEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Auto‑scroll terminal when new logs arrive
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const addLog = (msg, type = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { timestamp, message: msg, type }]);
  };

  // Poll backend for task status and logs
  const pollTaskStatus = (taskId) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      try {
        const { data: task } = await api.get(`/tasks/${taskId}`);
        // Fetch real‑time logs
        let logLines = [];
        try { const { data } = await api.get(`/tasks/${taskId}/logs`); logLines = data.logs || []; } catch (_) {}
        const parsed = logLines.map(line => {
          let type = "info";
          let msg = line;
          let time = new Date().toLocaleTimeString();
          const parts = line.split(" | ");
          if (parts.length >= 3) {
            const ts = parts[0];
            const lvl = parts[1].trim();
            const content = parts.slice(2).join(" | ");
            const tsMatch = ts.match(/\d{2}:\d{2}:\d{2}/);
            if (tsMatch) time = tsMatch[0];
            msg = content;
            if (lvl === "ERROR" || lvl === "CRITICAL") type = "error";
            else if (lvl === "WARNING") type = "warning";
            else if (content.toLowerCase().includes("success")) type = "success";
            else if (content.toLowerCase().includes("start") || content.toLowerCase().includes("initializing")) type = "system";
          } else {
            const up = line.toUpperCase();
            if (up.includes("ERROR") || up.includes("FAIL") || up.includes("EXCEPTION")) type = "error";
            else if (up.includes("SUCCESS") || up.includes("COMPLETED")) type = "success";
            else if (up.includes("WARN")) type = "warning";
            else if (up.startsWith("===") || up.includes("START") || up.includes("PROCESSING")) type = "system";
          }
          return { timestamp: time, message: msg, type };
        });
        if (parsed.length) setLogs(parsed);
        // Handle terminal states
        if (task.status === "COMPLETED") {
          addLog(`[SUCCESS] Flipkart scraping completed.`, "success");
          setLoading(false);
          clearInterval(pollIntervalRef.current);
        } else if (task.status === "ERROR" || task.status === "FAILED") {
          const errMsg = task.error_message || "Backend error";
          addLog(`[ERROR] ${errMsg}`, "error");
          setError(errMsg);
          setLoading(false);
          clearInterval(pollIntervalRef.current);
        }
      } catch (_) { }
    }, 2000);
  };

  const handleScrape = async () => {
    setError("");
    setLogs([]);
    setLoading(true);
    addLog(`[CONFIG] Search term: ${searchTerm}`, "info");
    if (maxPages) addLog(`[CONFIG] Max pages: ${maxPages}`, "info");
    try {
      const resp = await api.post(
        "/scrape_flipkart",
        { search_term: searchTerm, max_pages: maxPages ? parseInt(maxPages) : null },
        { headers: { "Content-Type": "application/json" } }
      );
      addLog(`[CELERY] Task queued – ID ${resp.data.task_id}`, "success");
      pollTaskStatus(resp.data.task_id);
    } catch (e) {
      const msg = e.response?.data?.error || "Failed to start Flipkart scraper";
      setError(msg);
      addLog(`[ERROR] ${msg}`, "error");
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-50 min-h-screen p-6 space-y-6">
      {/* Top configuration bar */}
      <Card className="w-full shadow-lg border border-blue-gray-100 p-4 flex flex-col md:flex-row items-start md:items-center gap-4 mb-4">
        <Input label="Search Term" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} shrink={true} />
        <Input label="Max Pages" type="number" value={maxPages} onChange={e => setMaxPages(e.target.value)} shrink={true} />
        <Button onClick={handleScrape} disabled={loading} className="bg-green-600 text-white">
          {loading ? 'Running…' : 'START SCRAPING'}
        </Button>
      </Card>
      {error && (
        <div className="p-3 bg-red-50 border border-red-100 text-red-600 rounded mb-4">⚠️ {error}</div>
      )}
      {/* Bottom terminal log window */}
      <Card className="bg-gray-900 text-white shadow-lg border border-blue-gray-100 h-[520px] flex flex-col">
        <CardBody className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1">
          {logs.length === 0 ? (
            <div className="text-gray-400 italic">No logs yet – start a scrape.</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-gray-600">[{log.timestamp}]</span>
                <span className={
                  log.type === "success" ? "text-green-400" :
                  log.type === "error" ? "text-red-400 font-bold" :
                  log.type === "warning" ? "text-yellow-400" :
                  log.type === "system" ? "text-blue-400" :
                  "text-gray-200"
                }>{log.message}</span>
              </div>
            ))
          )}
          <div ref={terminalEndRef} />
        </CardBody>
      </Card>
    </div>
  );
};

export default FlipkartScrapper;