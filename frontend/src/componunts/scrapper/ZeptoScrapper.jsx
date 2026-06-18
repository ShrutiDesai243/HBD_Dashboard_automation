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
  const [category, setCategory] = useState("");
  const [pincodes, setPincodes] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusInfo, setStatusInfo] = useState({
    status: "idle",
    current_category: null,
    current_subcategory: null,
    current_pincode: null,
    total_scraped: 0,
    errors_count: 0,
    warnings_count: 0,
  });
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");

  const terminalEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Auto-scroll logs terminal
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // Clean up polling interval on unmount
  useEffect(() => {
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

  const handleStartScrape = async () => {
    setError("");
    setLogs([]);
    setLoading(true);

    try {
      const response = await api.post("/scraper/zepto/start", {
        category: category,
        pincodes: pincodes,
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
      {/* Upper Navigation Card */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-xl border border-blue-gray-100 shadow-sm">
        <div>
          <Typography variant="h3" color="blue-gray" className="font-bold flex items-center gap-3">
            <span className="p-2 bg-deep-purple-600 rounded-lg text-white">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-8 h-8">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5V6a3.75 3.75 0 1 0-7.5 0v4.5m11.356-1.993 1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 0 1-1.12-1.243l1.264-12A1.125 1.125 0 0 1 5.513 7.5h12.974c.576 0 1.059.435 1.119 1.007ZM8.625 10.5a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm7.5 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
              </svg>
            </span>
            Zepto Automation Scraper
          </Typography>
          <Typography className="text-sm text-gray-500 mt-2 font-medium">
            Integrate and manage the Zepto catalog scraper. Extract products by categories sitemap and specific delivery location pincodes.
          </Typography>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Settings Panel */}
        <Card className="lg:col-span-5 shadow-lg border border-blue-gray-100 h-fit">
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
                Enter one or more category names (comma-separated) to match.
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
                Comma-separated delivery pincodes, or leave blank to load from pincodes.txt
              </Typography>
            </div>

            {/* Scraper Status Card */}
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
              <div className="flex justify-between items-center">
                <Typography className="text-xs font-bold text-gray-600 uppercase">Scraper Status</Typography>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${statusDisplay.color} ${statusDisplay.animate}`}>
                  {statusDisplay.text}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-gray-200">
                <div>
                  <Typography className="text-[10px] text-gray-400 font-bold uppercase">Scraped items</Typography>
                  <Typography variant="h5" color="blue-gray" className="font-bold">
                    {statusInfo.total_scraped}
                  </Typography>
                </div>
                <div>
                  <Typography className="text-[10px] text-gray-400 font-bold uppercase">Current Pincode</Typography>
                  <Typography className="text-sm font-semibold text-gray-700">
                    {statusInfo.current_pincode || "None"}
                  </Typography>
                </div>
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

        {/* Right Side: Log Console Terminal */}
        <div className="lg:col-span-7 flex flex-col">
          <Card className="shadow-lg border border-blue-gray-100 flex-1 flex flex-col bg-gray-900 text-white rounded-xl overflow-hidden h-[520px] min-h-[520px] max-h-[520px]">
            {/* Terminal Header */}
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
            <div className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-2 no-scrollbar">
              {logs.length === 0 ? (
                <div className="text-gray-500 italic h-full flex items-center justify-center">
                  Terminal inactive. Configure parameters and click "Start Scrape" to watch live execution logs.
                </div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className="leading-relaxed flex items-start gap-2">
                    <span className="text-gray-500 select-none">[{log.timestamp}]</span>
                    <span
                      className={
                        log.level === "ERROR"
                          ? "text-red-400 font-bold"
                          : log.level === "WARNING"
                          ? "text-yellow-400"
                          : log.message.includes("successfully") || log.message.includes("[+]") || log.message.includes("[=]")
                          ? "text-green-400"
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