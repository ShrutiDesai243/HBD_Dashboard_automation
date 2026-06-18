import React, { useState, useEffect } from "react";
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Button,
  Spinner,
  Alert
} from "@material-tailwind/react";
import {
  ArrowPathIcon,
  TrashIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ArrowUturnLeftIcon
} from "@heroicons/react/24/solid";
import api from "../../utils/Api";

const DataCleaningDashboard = () => {
  const [selectedTable, setSelectedTable] = useState("all"); // 'all', 'master_table', 'product_master'
  const [metrics, setMetrics] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTask, setActiveTask] = useState(null); // { runId, type, status }
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmType, setConfirmType] = useState(null); // 'apply' or 'rollback'
  const [rollbackTargetId, setRollbackTargetId] = useState(null);
  const [message, setMessage] = useState(null); // { type: 'success' | 'error', text }
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [errorModalTitle, setErrorModalTitle] = useState("");
  const [errorRows, setErrorRows] = useState([]);
  const [errorModalLoading, setErrorModalLoading] = useState(false);
  const [safeTables, setSafeTables] = useState([]);
  const [selectedSafeTable, setSelectedSafeTable] = useState("");
  const [safeLoading, setSafeLoading] = useState(false);
  const [safeTablesLoading, setSafeTablesLoading] = useState(false);
  const [safeTablesError, setSafeTablesError] = useState("");
  const [safeResult, setSafeResult] = useState(null);

  // Load metrics & history
  useEffect(() => {
    fetchData();
    fetchHistory();
    fetchSafeTables();
  }, []);

  // Poll active background task if exists
  useEffect(() => {
    let intervalId;
    if (activeTask && activeTask.status === "running") {
      intervalId = setInterval(async () => {
        try {
          const res = await api.get(`/cleaning/status/${activeTask.runId}`);
          if (res.data.status === "success") {
            const taskData = res.data.data;
            if (taskData.status !== "running") {
              // Task finished
              setActiveTask(null);
              fetchData();
              fetchHistory();
              const errMsg = taskData.error_message || "Unknown error occurred.";
              setMessage({
                type: taskData.status === "completed" ? "success" : "error",
                text: taskData.status === "completed" 
                  ? `Task ${taskData.run_id} completed successfully! Cleaned: ${taskData.cleaned_rows} rows.`
                  : `Task failed: ${errMsg.length > 200 ? errMsg.substring(0, 200) + "..." : errMsg}`
              });
            }
          }
        } catch (err) {
          console.error("Status check error:", err);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [activeTask]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.get("/cleaning/analyze");
      setMetrics(res.data.data);
    } catch (err) {
      console.error(err);
      if (err.response?.status === 401) {
        window.location.href = "/auth/sign-in";
        return;
      }
      setMessage({ type: "error", text: "Failed to connect to backend cleaning APIs." });
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await api.get("/cleaning/history");
      setHistory(res.data.data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchSafeTables = async () => {
    setSafeTablesLoading(true);
    setSafeTablesError("");
    try {
      const res = await api.get("/cleaning/safe-clean/tables");
      const tables = res.data.data || [];
      setSafeTables(tables);
      if (!selectedSafeTable && tables.length > 0) {
        setSelectedSafeTable(tables.includes("master_table") ? "master_table" : tables[0]);
      }
    } catch (err) {
      console.error("Error fetching safe clean tables:", err);
      setSafeTablesError(err.response?.data?.message || "Could not load table suggestions. You can type a table name manually.");
    } finally {
      setSafeTablesLoading(false);
    }
  };

  const runSafeClean = async (dryRun = true) => {
    if (!selectedSafeTable) {
      setMessage({ type: "error", text: "Please select a table first." });
      return;
    }
    setSafeLoading(true);
    setSafeResult(null);
    setMessage(null);
    try {
      const res = await api.post("/cleaning/safe-clean/run", {
        table_name: selectedSafeTable,
        dry_run: dryRun,
        chunk_size: 10000,
      });
      const result = res.data.data;
      setSafeResult(result);
      const changed = result.table?.changed_rows_reported || 0;
      setMessage({
        type: result.table?.status === "failed" ? "error" : "success",
        text: dryRun
          ? `Dry run finished for ${selectedSafeTable}: ${changed.toLocaleString()} row(s) need safe text cleanup.`
          : `Safe cleanup finished for ${selectedSafeTable}: ${changed.toLocaleString()} row(s) cleaned.`
      });
    } catch (err) {
      console.error("Safe cleanup error:", err);
      setMessage({ type: "error", text: err.response?.data?.message || "Safe cleanup failed." });
    } finally {
      setSafeLoading(false);
    }
  };

  const fetchErrorData = async (tableName, errorType, title) => {
    setErrorModalTitle(title);
    setErrorModalLoading(true);
    setShowErrorModal(true);
    setErrorRows([]);
    try {
      const res = await api.get(`/cleaning/errors`, {
        params: { table_name: tableName, error_type: errorType }
      });
      if (res.data.status === "success") {
        setErrorRows(res.data.data || []);
      }
    } catch (err) {
      console.error("Error fetching error samples:", err);
    } finally {
      setErrorModalLoading(false);
    }
  };

  const handleDryRun = async () => {
    setMessage(null);
    try {
      const res = await api.post("/cleaning/dry-run", { table_name: selectedTable });
      const result = res.data;
      if (result.status === "success") {
        setActiveTask({ runId: result.run_id, type: "dry-run", status: "running" });
        setMessage({ type: "success", text: "Asynchronous dry clean simulation started..." });
      } else {
        setMessage({ type: "error", text: result.message });
      }
    } catch (err) {
      setMessage({ type: "error", text: "Error starting dry clean task." });
    }
  };

  const handleApply = async () => {
    setShowConfirm(false);
    setMessage(null);
    try {
      const res = await api.post("/cleaning/apply", { table_name: selectedTable });
      const result = res.data;
      if (result.status === "success") {
        setActiveTask({ runId: result.run_id, type: "apply", status: "running" });
        setMessage({ type: "success", text: "Asynchronous live cleaning & backup creation started..." });
      } else {
        setMessage({ type: "error", text: result.message });
      }
    } catch (err) {
      setMessage({ type: "error", text: "Error starting live clean task." });
    }
  };

  const handleRollback = async (targetId) => {
    setShowConfirm(false);
    setMessage(null);
    try {
      const res = await api.post("/cleaning/rollback", { target_run_id: targetId });
      const result = res.data;
      if (result.status === "success") {
        setActiveTask({ runId: result.run_id, type: "rollback", status: "running" });
        setMessage({ type: "success", text: "Rollback restoration task started..." });
      } else {
        setMessage({ type: "error", text: result.message });
      }
    } catch (err) {
      setMessage({ type: "error", text: "Error starting rollback task." });
    }
  };

  const safeTableResult = safeResult?.table;

  return (
    <div className="container mx-auto my-8 px-4 text-black">
      {/* HEADER SECTION */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <Typography variant="h3" className="font-bold text-gray-800 tracking-tight flex items-center gap-2">
            ✨ Data Cleaning Dashboard
          </Typography>
          <Typography variant="paragraph" className="text-gray-600 font-normal">
            Safely deduplicate, standardize location spelling, and clean data in database tables.
          </Typography>
        </div>
        <div className="flex gap-2">
          <select
            value={selectedTable}
            onChange={(e) => setSelectedTable(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white font-medium"
            disabled={activeTask && activeTask.status === "running"}
          >
            <option value="all">All Tables</option>
            <option value="master_table">Listing Data (master_table)</option>
            <option value="product_master">Product Data (product_master)</option>
          </select>
          <Button
            size="sm"
            color="blue"
            className="flex items-center gap-2"
            onClick={() => { fetchData(); fetchHistory(); }}
            disabled={loading || (activeTask && activeTask.status === "running")}
          >
            <ArrowPathIcon className="h-4 w-4" /> Refresh
          </Button>
        </div>
      </div>

      {/* ALERT MESSAGE */}
      {message && (
        <Alert
          className="mb-6 font-medium"
          color={message.type === "success" ? "green" : "red"}
          icon={message.type === "success" ? <CheckCircleIcon className="h-5 w-5" /> : <ExclamationTriangleIcon className="h-5 w-5" />}
        >
          {message.text}
        </Alert>
      )}

      {/* BACKGROUND TASK RUNNING LOADER */}
      {activeTask && activeTask.status === "running" && (
        <Card className="mb-6 border border-blue-200 bg-blue-50/50">
          <CardBody className="flex items-center gap-4 py-4">
            <Spinner className="h-8 w-8 text-blue-500" />
            <div>
              <Typography className="font-bold text-blue-800">
                Running Cleaning Operation ({activeTask.type === "dry-run" ? "Simulation Mode" : activeTask.type === "apply" ? "Live Clean" : "Rollback"})
              </Typography>
              <Typography className="text-xs text-blue-600 font-normal">
                Executing database processes in the background (Run ID: {activeTask.runId}). Please do not refresh.
              </Typography>
            </div>
          </CardBody>
        </Card>
      )}

      {/* STATS OVERVIEW CARDS */}
      {metrics ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* master_table Stats */}
          {selectedTable !== "product_master" && (
            <Card className="border border-gray-200 shadow-sm bg-white rounded-xl">
              <CardHeader className="bg-gray-50 border-b border-gray-150 p-4" floated={false} shadow={false}>
                <Typography className="font-bold text-gray-800">Listing Data (master_table)</Typography>
              </CardHeader>
              <CardBody className="grid grid-cols-2 gap-4">
                <div>
                  <Typography className="text-xs text-gray-500 font-semibold uppercase">Total Rows</Typography>
                  <Typography className="text-xl font-bold text-gray-800">{metrics.master_table.total_rows.toLocaleString()}</Typography>
                </div>
                <div 
                  className="cursor-pointer hover:bg-red-50/70 p-2.5 rounded-lg border border-transparent hover:border-red-100 transition-all group"
                  onClick={() => fetchErrorData("master_table", "duplicates", "Duplicate Listing Records")}
                >
                  <Typography className="text-[11px] text-red-500 font-semibold uppercase tracking-wider group-hover:text-red-700">Duplicates 🔍</Typography>
                  <Typography className="text-xl font-bold text-red-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics.master_table.duplicate_rows.toLocaleString()}</Typography>
                </div>
                <div 
                  className="cursor-pointer hover:bg-amber-50/70 p-2.5 rounded-lg border border-transparent hover:border-amber-100 transition-all group"
                  onClick={() => fetchErrorData("master_table", "missing_location", "Missing City / State / Area Listings")}
                >
                  <Typography className="text-[11px] text-amber-500 font-semibold uppercase tracking-wider group-hover:text-amber-700">Missing Cities/States 🔍</Typography>
                  <Typography className="text-xl font-bold text-amber-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics.master_table.missing_location.toLocaleString()}</Typography>
                </div>
                <div 
                  className="cursor-pointer hover:bg-orange-50/70 p-2.5 rounded-lg border border-transparent hover:border-orange-100 transition-all group"
                  onClick={() => fetchErrorData("master_table", "invalid_phone_email", "Invalid Phone Number or Email Contacts")}
                >
                  <Typography className="text-[11px] text-orange-500 font-semibold uppercase tracking-wider group-hover:text-orange-700">Invalid Contacts 🔍</Typography>
                  <Typography className="text-xl font-bold text-orange-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics.master_table.invalid_phone_email.toLocaleString()}</Typography>
                </div>
                <div 
                  className="cursor-pointer hover:bg-cyan-50/70 p-2.5 rounded-lg border border-transparent hover:border-cyan-100 transition-all group"
                  onClick={() => fetchErrorData("master_table", "incomplete_records", "Incomplete Listing Records")}
                >
                  <Typography className="text-[11px] text-cyan-500 font-semibold uppercase tracking-wider group-hover:text-cyan-700">Incomplete Data 🔍</Typography>
                  <Typography className="text-xl font-bold text-cyan-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics?.master_table?.incomplete_records?.toLocaleString() || '0'}</Typography>
                </div>
                <div 
                  className="col-span-2 cursor-pointer hover:bg-deep-purple-50/70 p-2.5 rounded-lg border border-transparent hover:border-deep-purple-100 transition-all group"
                  onClick={() => fetchErrorData("master_table", "unmatched_location", "Unmatched Indian Locations (Not in Reference DB)")}
                >
                  <Typography className="text-[11px] text-deep-purple-500 font-semibold uppercase tracking-wider group-hover:text-deep-purple-700">Unmatched Locations 🔍</Typography>
                  <Typography className="text-xl font-bold text-deep-purple-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics.master_table.unmatched_location.toLocaleString()}</Typography>
                </div>
              </CardBody>
            </Card>
          )}

          {/* product_master Stats */}
          {selectedTable !== "master_table" && (
            <Card className="border border-gray-200 shadow-sm bg-white rounded-xl">
              <CardHeader className="bg-gray-50 border-b border-gray-150 p-4" floated={false} shadow={false}>
                <Typography className="font-bold text-gray-800">Product Data (product_master)</Typography>
              </CardHeader>
              <CardBody className="grid grid-cols-2 gap-4">
                <div>
                  <Typography className="text-xs text-gray-500 font-semibold uppercase">Total Rows</Typography>
                  <Typography className="text-xl font-bold text-gray-800">{metrics.product_master.total_rows.toLocaleString()}</Typography>
                </div>
                <div 
                  className="cursor-pointer hover:bg-red-50/70 p-2.5 rounded-lg border border-transparent hover:border-red-100 transition-all group"
                  onClick={() => fetchErrorData("product_master", "duplicates", "Duplicate Product Records")}
                >
                  <Typography className="text-[11px] text-red-500 font-semibold uppercase tracking-wider group-hover:text-red-700">Duplicate Products 🔍</Typography>
                  <Typography className="text-xl font-bold text-red-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics.product_master.duplicate_rows.toLocaleString()}</Typography>
                </div>
                <div 
                  className="col-span-2 cursor-pointer hover:bg-amber-50/70 p-2.5 rounded-lg border border-transparent hover:border-amber-100 transition-all group"
                  onClick={() => fetchErrorData("product_master", "wrong_category", "Wrong Category Mappings (Not in Reference DB)")}
                >
                  <Typography className="text-[11px] text-amber-500 font-semibold uppercase tracking-wider group-hover:text-amber-700">Wrong Category Mappings 🔍</Typography>
                  <Typography className="text-xl font-bold text-amber-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics.product_master.wrong_category.toLocaleString()}</Typography>
                </div>
                <div 
                  className="col-span-2 cursor-pointer hover:bg-cyan-50/70 p-2.5 rounded-lg border border-transparent hover:border-cyan-100 transition-all group"
                  onClick={() => fetchErrorData("product_master", "incomplete_records", "Incomplete Product Records")}
                >
                  <Typography className="text-[11px] text-cyan-500 font-semibold uppercase tracking-wider group-hover:text-cyan-700">Incomplete Data 🔍</Typography>
                  <Typography className="text-xl font-bold text-cyan-600 group-hover:scale-[1.02] origin-left transition-transform">{metrics?.product_master?.incomplete_records?.toLocaleString() || '0'}</Typography>
                </div>
              </CardBody>
            </Card>
          )}

          {/* Core Dashboard Control Actions */}
          <Card className="border border-gray-200 shadow-sm bg-white rounded-xl flex flex-col justify-between p-6">
            <div>
              <Typography variant="h6" className="font-bold text-gray-800 mb-2">Operations Control</Typography>
              <Typography className="text-xs text-gray-500 font-normal leading-relaxed mb-4">
                Perform a <strong>Dry Clean</strong> to verify duplicate and mismatch statistics safely. Perform <strong>Apply Cleaning</strong> to run real updates with backups.
              </Typography>
            </div>
            <div className="flex flex-col gap-3">
              <Button
                color="indigo"
                className="w-full flex items-center justify-center gap-2"
                onClick={handleDryRun}
                disabled={activeTask && activeTask.status === "running"}
              >
                <ClockIcon className="h-4 w-4" /> Run Dry Clean
              </Button>
              <Button
                color="red"
                className="w-full flex items-center justify-center gap-2"
                onClick={() => { setConfirmType("apply"); setShowConfirm(true); }}
                disabled={activeTask && activeTask.status === "running"}
              >
                <TrashIcon className="h-4 w-4" /> Apply Cleaning
              </Button>
            </div>
          </Card>
        </div>
      ) : (
        <div className="flex flex-col justify-center items-center py-20 gap-3">
          <Spinner className="h-10 w-10 text-blue-500" />
          <Typography className="text-gray-500 font-medium animate-pulse">Analyzing Tables...</Typography>
        </div>
      )}

      <Card className="border border-gray-200 rounded-xl shadow-sm bg-white mb-8">
        <CardHeader className="bg-gray-50 border-b border-gray-150 p-4" floated={false} shadow={false}>
          <Typography variant="h5" className="font-bold text-gray-800">Safe Single-Table Text Cleanup</Typography>
        </CardHeader>
        <CardBody className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_auto] gap-4 items-end">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto_auto] gap-3 items-end">
            <div>
              <Typography className="text-xs text-gray-500 font-semibold uppercase mb-1">Table</Typography>
              <input
                list="safe-clean-table-options"
                value={selectedSafeTable}
                onChange={(e) => {
                  setSelectedSafeTable(e.target.value);
                  setSafeResult(null);
                }}
                placeholder={safeTablesLoading ? "Loading tables..." : "Select or type a table name"}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white font-medium"
                disabled={safeLoading}
              />
              <datalist id="safe-clean-table-options">
                {safeTables.map((table) => (
                  <option key={table} value={table}>{table}</option>
                ))}
              </datalist>
              <div className="mt-1 flex items-center justify-between gap-2">
                <Typography className={`text-[11px] ${safeTablesError ? "text-red-500" : "text-gray-500"}`}>
                  {safeTablesError || `${safeTables.length.toLocaleString()} table suggestion(s) loaded`}
                </Typography>
                <button
                  type="button"
                  className="text-[11px] font-semibold text-blue-600 hover:text-blue-800"
                  onClick={fetchSafeTables}
                  disabled={safeTablesLoading || safeLoading}
                >
                  Reload
                </button>
              </div>
            </div>
            <Button
              color="indigo"
              variant="outlined"
              className="flex items-center justify-center gap-2"
              onClick={() => runSafeClean(true)}
              disabled={safeLoading || !selectedSafeTable}
            >
              {safeLoading ? <Spinner className="h-4 w-4" /> : <ClockIcon className="h-4 w-4" />}
              Dry Run
            </Button>
            <Button
              color="green"
              className="flex items-center justify-center gap-2"
              onClick={() => {
                setConfirmType("safe-apply");
                setShowConfirm(true);
              }}
              disabled={safeLoading || !selectedSafeTable}
            >
              <CheckCircleIcon className="h-4 w-4" />
              Clean Selected
            </Button>
          </div>

          {safeTableResult && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 min-w-[260px]">
              <Typography className="text-xs font-semibold uppercase text-gray-500">Last Result</Typography>
              <Typography className="text-sm font-bold text-gray-800">{safeTableResult.table}</Typography>
              <Typography className="text-xs text-gray-600">
                Rows: {(safeTableResult.changed_rows_reported || 0).toLocaleString()} | Status: {safeTableResult.status}
              </Typography>
              <Typography className="text-xs text-gray-600">
                Row count unchanged: {safeTableResult.row_count_unchanged ? "Yes" : "No"}
              </Typography>
              {safeTableResult.backup_table && (
                <Typography className="text-[11px] text-gray-500 break-all">
                  Backup: {safeTableResult.backup_table}
                </Typography>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      {/* CLEANING HISTORY LOG */}
      <Card className="border border-gray-200 rounded-xl shadow-sm bg-white overflow-hidden">
        <CardHeader className="bg-gray-50 border-b border-gray-150 p-4" floated={false} shadow={false}>
          <Typography variant="h5" className="font-bold text-gray-800">Cleaning Log & Rollback Registry</Typography>
        </CardHeader>
        <CardBody className="p-0 overflow-x-auto">
          {history.length > 0 ? (
            <table className="w-full min-w-[800px] table-auto text-left">
              <thead>
                <tr className="bg-gray-100 border-b border-gray-200">
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Run ID</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Date/Time</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Type</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Table</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Duplicates Removed</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Unmatched Fixed</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Status</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Backup Tables</th>
                  <th className="px-4 py-3 text-xs font-bold uppercase text-gray-600">Action</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr key={row.run_id} className="border-b hover:bg-gray-50/50">
                    <td className="px-4 py-4 text-sm font-semibold text-gray-800">{row.run_id}</td>
                    <td className="px-4 py-4 text-xs text-gray-600 font-normal">
                      {row.created_at ? new Date(row.created_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-4 text-xs">
                      <span className={`px-2 py-0.5 rounded font-bold uppercase ${
                        row.run_type === "apply" ? "bg-red-50 text-red-600 border border-red-200" 
                        : row.run_type === "dry-run" ? "bg-blue-50 text-blue-600 border border-blue-200"
                        : "bg-amber-50 text-amber-600 border border-amber-200"
                      }`}>
                        {row.run_type}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-xs font-medium">{row.table_name}</td>
                    <td className="px-4 py-4 text-sm font-medium">{(row.duplicate_rows || 0).toLocaleString()}</td>
                    <td className="px-4 py-4 text-sm font-medium">
                      {((row.unmatched_location_rows || 0) + (row.wrong_category_rows || 0)).toLocaleString()}
                    </td>
                    <td className="px-4 py-4 text-xs">
                      <span className={`px-2 py-0.5 rounded font-bold uppercase ${
                        row.status === "completed" ? "bg-green-50 text-green-700"
                        : row.status === "failed" ? "bg-red-50 text-red-700"
                        : "bg-blue-50 text-blue-700 animate-pulse"
                      }`}>
                        {row.status}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-xs text-gray-500 font-mono break-all">{row.backup_table_name || "-"}</td>
                    <td className="px-4 py-4">
                      {row.run_type === "apply" && row.status === "completed" && (
                        <Button
                          size="sm"
                          color="amber"
                          className="flex items-center gap-1 py-1 px-2 text-xs"
                          onClick={() => {
                            setRollbackTargetId(row.run_id);
                            setConfirmType("rollback");
                            setShowConfirm(true);
                          }}
                          disabled={activeTask && activeTask.status === "running"}
                        >
                          <ArrowUturnLeftIcon className="h-3 w-3" /> Rollback
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="py-10 text-center text-gray-500 font-medium">No cleaning history records found.</div>
          )}
        </CardBody>
      </Card>

      {/* WARNING CONFIRMATION MODAL */}
      {showConfirm && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <Card className="w-full max-w-md border border-gray-200 p-6 bg-white shadow-xl rounded-2xl">
            <div className="flex items-center gap-3 mb-4 text-red-600">
              <ExclamationTriangleIcon className="h-8 w-8" />
              <Typography variant="h5" className="font-bold">
                {confirmType === "apply"
                  ? "Confirm Live Database Clean"
                  : confirmType === "safe-apply"
                  ? "Confirm Safe Table Cleanup"
                  : "Confirm Database Rollback"}
              </Typography>
            </div>
            
            <Typography variant="paragraph" className="text-gray-600 font-normal leading-relaxed mb-6">
              {confirmType === "apply" 
                ? "WARNING: This operation will modify active tables. A safe backup table will be created. Duplicates and invalid/unmatched records will be removed from main tables and saved in reviews. Do you want to proceed?"
                : confirmType === "safe-apply"
                ? `This will trim text fields only in ${selectedSafeTable}. No rows will be deleted and changed rows will be backed up first. Do you want to proceed?`
                : `WARNING: This operation will drop active tables and restore data to the state of Backup created in Run ID: ${rollbackTargetId}. This cannot be undone. Do you want to proceed?`
              }
            </Typography>

            <div className="flex justify-end gap-3">
              <Button
                variant="outlined"
                color="gray"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                color={confirmType === "apply" ? "red" : confirmType === "safe-apply" ? "green" : "amber"}
                onClick={() => {
                  if (confirmType === "apply") {
                    handleApply();
                  } else if (confirmType === "safe-apply") {
                    setShowConfirm(false);
                    runSafeClean(false);
                  } else {
                    handleRollback(rollbackTargetId);
                  }
                }}
              >
                Yes, Proceed
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* ERROR ROWS AUDITING MODAL */}
      {showErrorModal && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black bg-opacity-65 backdrop-blur-sm p-4">
          <Card className="w-full max-w-5xl max-h-[85vh] bg-white shadow-2xl border border-gray-200 overflow-hidden flex flex-col rounded-xl">
            <CardHeader floated={false} shadow={false} className="bg-gray-50 border-b border-gray-200 px-6 py-4 m-0 flex justify-between items-center rounded-none">
              <Typography variant="h5" className="font-bold text-gray-800 flex items-center gap-2">
                🔍 {errorModalTitle}
              </Typography>
              <button 
                onClick={() => setShowErrorModal(false)}
                className="text-gray-400 hover:text-gray-700 hover:bg-gray-200 p-1.5 rounded-lg transition-colors font-bold text-lg leading-none"
              >
                ✕
              </button>
            </CardHeader>
            <CardBody className="overflow-y-auto p-6 flex-1">
              <Typography className="text-xs text-gray-500 font-normal mb-4">
                Showing a sample of up to 50 active database records flagged with this error. Run "Apply Cleaning" to resolve these or move them to review tables.
              </Typography>
              
              {errorModalLoading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-2">
                  <Spinner className="h-8 w-8 text-blue-500" />
                  <Typography className="text-sm font-medium text-gray-500 animate-pulse">Querying database samples...</Typography>
                </div>
              ) : errorRows.length > 0 ? (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                  <table className="w-full min-w-[800px] table-auto text-left text-xs">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        {Object.keys(errorRows[0]).map((key) => (
                          <th key={key} className="py-3 px-4 font-bold text-gray-600 uppercase border-b border-gray-200">
                            {key.replace("_", " ")}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {errorRows.map((row, idx) => (
                        <tr key={idx} className="hover:bg-blue-50/30 border-b border-gray-100 last:border-0 transition-colors">
                          {Object.values(row).map((val, colIdx) => (
                            <td key={colIdx} className="py-2.5 px-4 text-gray-700 truncate max-w-[250px]" title={String(val || "")}>
                              {val === null || val === "" ? <em className="text-gray-400">null</em> : String(val)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-20 text-gray-500 font-medium">
                  🎉 No matching records found! All data is clean for this check.
                </div>
              )}
            </CardBody>
            <div className="bg-gray-50 px-6 py-4 border-t border-gray-200 flex justify-end">
              <Button size="sm" color="blue-gray" onClick={() => setShowErrorModal(false)}>
                Close Auditing
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default DataCleaningDashboard;
