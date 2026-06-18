import React, { useState, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardBody,
  Typography,
  Spinner,
  Button,
} from "@material-tailwind/react";
import axios from "axios";

// Make sure to use your configured axios instance if you have one
// For this demo we'll use window.location.origin or basic axios
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

export function DynamicTierDashboard() {
  const [stats, setStats] = useState([]);
  const [loadingStats, setLoadingStats] = useState(true);
  
  const [activeTier, setActiveTier] = useState("tier1");
  const [tierData, setTierData] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const [isCleaning, setIsCleaning] = useState(false);
  const [isPreparing, setIsPreparing] = useState(false);
  const [logs, setLogs] = useState([]);
  const [pollInterval, setPollInterval] = useState(null);
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("raw_clean_google_map_data");
  const [viewFilter, setViewFilter] = useState("ALL");
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = React.useRef(null);

  useEffect(() => {
    fetchStats();
    fetchTables();
    checkCleanerStatus();
  }, []);

  useEffect(() => {
    // Re-fetch data when view filter changes
    fetchStats();
    fetchTierData(activeTier);
  }, [viewFilter]);

  useEffect(() => {
    if (isCleaning) {
      const interval = setInterval(fetchLogs, 2000);
      setPollInterval(interval);
      return () => clearInterval(interval);
    } else {
      if (pollInterval) clearInterval(pollInterval);
    }
  }, [isCleaning]);

  useEffect(() => {
    // Auto-scroll logs
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const fetchLogs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/tiers/cleaner-logs`, { withCredentials: true });
      if (res.data.exists) {
        setLogs(res.data.logs);
        // If logs indicate completion, stop polling
        if (res.data.logs.some(l => l.includes("Execution Complete") || l.includes("Stop signal received"))) {
          setIsCleaning(false);
          fetchStats();
          fetchTierData(activeTier);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchTierData(activeTier);
  }, [activeTier]);

  const fetchStats = async () => {
    try {
      setLoadingStats(true);
      const res = await axios.get(`${API_BASE}/api/tiers/stats?source_table=${viewFilter}`, { withCredentials: true });
      if (res.data.status === "success") {
        setStats(res.data.stats);
      }
    } catch (error) {
      console.error("Error fetching tier stats:", error);
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchTables = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/tiers/tables`, { withCredentials: true });
      if (res.data.status === "success") {
        setTables(res.data.tables);
      }
    } catch (error) {
      console.error("Error fetching tables:", error);
    }
  };

  const checkCleanerStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/tiers/cleaner-status`, { withCredentials: true });
      if (res.data.is_running) {
        setIsCleaning(true);
        if (res.data.table) {
          setSelectedTable(res.data.table);
        }
      }
    } catch (error) {
      console.error("Error checking cleaner status:", error);
    }
  };

  const fetchTierData = async (tier) => {
    try {
      setLoadingData(true);
      const res = await axios.get(`${API_BASE}/api/tiers/${tier}?source_table=${viewFilter}`, { withCredentials: true });
      if (res.data.status === "success") {
        setTierData(res.data.data);
      }
    } catch (error) {
      console.error(`Error fetching data for ${tier}:`, error);
      setTierData([]);
    } finally {
      setLoadingData(false);
    }
  };

  const exportTierData = () => {
    // Triggers a file download by navigating to the export route
    const exportUrl = `${API_BASE}/api/tiers/${activeTier}/export?source_table=${viewFilter}`;
    window.location.href = exportUrl;
  };

  const prepareTable = async () => {
    try {
      setIsPreparing(true);
      const res = await axios.post(`${API_BASE}/api/tiers/prepare-table`, { table: selectedTable }, { withCredentials: true });
      if (res.data.status === "success") {
        alert(res.data.message);
      } else {
        alert("Error: " + res.data.message);
      }
    } catch (error) {
      console.error("Error preparing table:", error);
      alert("Failed to prepare table. See console.");
    } finally {
      setIsPreparing(false);
    }
  };

  const runCleaner = async (limit) => {
    try {
      setIsCleaning(true);
      setLogs(["--- Initializing Background Cleaner... ---"]);
      const res = await axios.post(`${API_BASE}/api/tiers/run-cleaner`, { limit, table: selectedTable }, { withCredentials: true });
      if (res.data.status === "success") {
        // Logs will start polling automatically
      } else {
        alert("Error: " + res.data.message);
        setIsCleaning(false);
      }
    } catch (error) {
      console.error("Error running cleaner:", error);
      alert("Failed to run cleaner. See console.");
      setIsCleaning(false);
    }
  };

  const stopCleaner = async () => {
    try {
      const res = await axios.post(`${API_BASE}/api/tiers/stop-cleaner`, {}, { withCredentials: true });
      if (res.data.status === "success") {
        alert(res.data.message);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const formatLogLine = (log) => {
    if (log.includes("Execution Complete") || log.includes("Total Records Processed")) {
      return <span className="text-green-400 font-bold">{log}</span>;
    }
    if (log.includes("Stop signal received")) {
      return <span className="text-red-400 font-bold">{log}</span>;
    }
    if (log.includes("Fetching batch") || log.includes("Processing")) {
      return <span className="text-cyan-400">{log}</span>;
    }
    if (log.includes("--- Starting new cleaner run")) {
      return <span className="text-yellow-400 font-bold">{log}</span>;
    }
    return <span className="text-gray-300">{log}</span>;
  };

  return (
    <div className="mt-12 mb-8 flex flex-col gap-12">
      <Card>
        <CardHeader variant="gradient" color="blue" className="mb-8 p-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <Typography variant="h6" color="white">
            Dynamic Cleaning Engine Tiers
          </Typography>
          <div className="flex flex-wrap items-center gap-2">
            <select 
              className="bg-white text-blue-900 px-3 py-2 rounded-md font-medium text-sm outline-none"
              value={selectedTable}
              onChange={(e) => setSelectedTable(e.target.value)}
              disabled={isCleaning}
            >
              {tables.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
              {tables.length === 0 && <option value="raw_clean_google_map_data">raw_clean_google_map_data</option>}
            </select>
            <Button 
              color="indigo" 
              className="text-white flex items-center gap-2"
              onClick={prepareTable}
              disabled={isCleaning || isPreparing}
            >
              {isPreparing ? <Spinner className="h-4 w-4" /> : null}
              {isPreparing ? "Preparing..." : "Prepare Table"}
            </Button>
            <Button 
              color="white" 
              className="text-blue-500 flex items-center gap-2"
              onClick={() => runCleaner(100)}
              disabled={isCleaning}
            >
              {isCleaning ? <Spinner className="h-4 w-4" /> : null}
              {isCleaning ? "Processing..." : "Run Cleaner (Top 100)"}
            </Button>
            <Button 
              color="orange" 
              className="text-white flex items-center gap-2"
              onClick={() => runCleaner('all')}
              disabled={isCleaning}
            >
              {isCleaning ? <Spinner className="h-4 w-4" /> : null}
              {isCleaning ? "Processing..." : "Run Cleaner (ALL)"}
            </Button>
            {isCleaning && (
              <Button 
                color="red" 
                className="text-white flex items-center gap-2"
                onClick={stopCleaner}
              >
                Stop
              </Button>
            )}
          </div>
        </CardHeader>
        
        <CardBody className="px-4 pb-4">
          
          {/* View Filter Selection & Export */}
          <div className="flex flex-col md:flex-row justify-between items-center mb-4 gap-4">
            <Button 
              color="green" 
              onClick={exportTierData}
              className="flex items-center gap-2 shadow-md hover:shadow-lg transition-shadow"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              Export Active Tier to CSV
            </Button>
            
            <div className="flex items-center">
              <Typography variant="small" color="blue-gray" className="mr-2 font-bold uppercase">
                Viewing Results For:
              </Typography>
              <select 
                className="bg-gray-100 border border-gray-300 text-blue-900 px-3 py-1 rounded-md font-medium text-sm outline-none shadow-sm"
                value={viewFilter}
                onChange={(e) => setViewFilter(e.target.value)}
              >
                <option value="ALL">All Tables (Combined)</option>
                {tables.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Terminal Box for Logs */}
          {logs.length > 0 && (
            <div className="mb-8 rounded-lg overflow-hidden shadow-2xl border border-gray-800">
              {/* Terminal Header */}
              <div className="bg-gray-900 px-4 py-2 flex justify-between items-center border-b border-gray-800">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <div className="text-gray-400 text-xs font-mono tracking-widest">CLEANER_TERMINAL</div>
                <div className="flex gap-3">
                  <button 
                    onClick={() => setAutoScroll(!autoScroll)}
                    className={`text-xs font-mono px-2 py-1 rounded transition-colors ${autoScroll ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
                  >
                    {autoScroll ? 'Auto-Scroll: ON' : 'Auto-Scroll: OFF'}
                  </button>
                  <button 
                    onClick={() => setLogs([])}
                    className="text-xs font-mono bg-gray-700 text-gray-300 px-2 py-1 rounded hover:bg-gray-600 transition-colors"
                  >
                    Clear Logs
                  </button>
                </div>
              </div>
              {/* Terminal Body */}
              <div className="p-4 bg-[#1e1e1e] font-mono text-[13px] h-64 overflow-y-auto leading-relaxed">
                {logs.map((log, idx) => (
                  <div key={idx}>{formatLogLine(log)}</div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          )}
          {/* Stats Cards */}
          {loadingStats ? (
            <div className="flex justify-center p-4"><Spinner className="h-8 w-8" /></div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
              {stats.map((stat) => (
                <div 
                  key={stat.tier} 
                  onClick={() => setActiveTier(stat.tier)}
                  className={`p-4 rounded-lg shadow cursor-pointer transition-all ${
                    activeTier === stat.tier ? 'ring-4 ring-blue-500 scale-105' : 'hover:scale-105'
                  } ${stat.color} text-white`}
                >
                  <Typography variant="h6" className="text-sm opacity-80">{stat.name}</Typography>
                  <Typography variant="h3">{stat.count}</Typography>
                </div>
              ))}
            </div>
          )}

          {/* Data Table */}
          <div className="overflow-x-auto">
            <div className="flex justify-between items-center mb-4">
              <Typography variant="h5" color="blue-gray">
                Preview: {stats.find(s => s.tier === activeTier)?.name || activeTier} (Top 100)
              </Typography>
            </div>
            
            {loadingData ? (
              <div className="flex justify-center p-10"><Spinner className="h-8 w-8 text-blue-500" /></div>
            ) : tierData.length === 0 ? (
              <div className="text-center p-10 text-gray-500">No records found in this tier.</div>
            ) : (
              <table className="w-full min-w-[640px] table-auto">
                <thead>
                  <tr>
                    {/* Dynamically render headers based on first object keys, filtering out long JSON dumps */}
                    {Object.keys(tierData[0] || {})
                      .filter(k => k !== 'duplicate_data' && k !== 'fragment_data')
                      .map((key) => (
                      <th key={key} className="border-b border-blue-gray-50 py-3 px-5 text-left">
                        <Typography variant="small" className="text-[11px] font-bold uppercase text-blue-gray-400">
                          {key.replace(/_/g, ' ')}
                        </Typography>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tierData.map((row, idx) => {
                    const isLast = idx === tierData.length - 1;
                    const classes = isLast ? "p-5" : "p-5 border-b border-blue-gray-50";

                    return (
                      <tr key={idx} className="hover:bg-blue-gray-50 transition-colors">
                        {Object.entries(row)
                           .filter(([k, v]) => k !== 'duplicate_data' && k !== 'fragment_data')
                           .map(([key, val]) => (
                          <td key={key} className={classes}>
                            <Typography variant="small" color="blue-gray" className="font-normal">
                              {val !== null ? String(val) : '-'}
                            </Typography>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

export default DynamicTierDashboard;
