import React, { useState, useEffect, useCallback } from 'react';
import SlotCounter from 'react-slot-counter';
import {
    ShieldCheckIcon,
    ExclamationTriangleIcon,
    CheckBadgeIcon,
    XCircleIcon,
    ArrowPathIcon,
    DocumentDuplicateIcon,
    FunnelIcon,
    TableCellsIcon,
    SparklesIcon,
    InboxStackIcon,
    ClockIcon,
    ChevronRightIcon,
    DocumentTextIcon,
} from "@heroicons/react/24/solid";
import ValidationReport from './ValidationReport';

/**
 * ═══════════════════════════════════════════════════════════════════════════════
 *  VALIDATION PIPELINE DASHBOARD v1.0
 * ═══════════════════════════════════════════════════════════════════════════════
 *  Real-time monitoring dashboard for the 3-layer ETL validation pipeline.
 *  Shows: Pipeline progress, validation breakdown, error table, clean data.
 * ═══════════════════════════════════════════════════════════════════════════════
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

const ValidationDashboard = () => {
    const [dashData, setDashData] = useState(null);
    const [viewMode, setViewMode] = useState('overview'); // overview | errors | clean | report
    const [loading, setLoading] = useState(true);
    const [errorFilter, setErrorFilter] = useState(null);
    const [errorField, setErrorField] = useState(null); // 🔍 Filter by specific missing field (name, address, etc.)
    const [errorPage, setErrorPage] = useState(1);
    const [cleanPage, setCleanPage] = useState(1);
    const [paginatedErrors, setPaginatedErrors] = useState([]);
    const [paginatedClean, setPaginatedClean] = useState([]);
    const [totalErrors, setTotalErrors] = useState(0);
    const [totalClean, setTotalClean] = useState(0);
    const [autoRefresh, setAutoRefresh] = useState(true);

    // Fetch main dashboard data
    const fetchDashboard = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/validation/dashboard`);
            const json = await res.json();
            if (json.status === "success") setDashData(json);
        } catch (err) { console.error("Dashboard fetch error:", err); }
        finally { setLoading(false); }
    }, []);

    // Fetch paginated errors
    const fetchErrors = useCallback(async () => {
        try {
            const params = new URLSearchParams({ page: errorPage, limit: 50 });
            if (errorFilter) params.append("status", errorFilter);
            if (errorField) params.append("field", errorField);
            const res = await fetch(`${API_BASE}/api/validation/errors?${params.toString()}`);
            const json = await res.json();
            if (json.status === "success") {
                setPaginatedErrors(json.data);
                setTotalErrors(json.total);
            }
        } catch (err) { console.error("Errors fetch error:", err); }
    }, [errorPage, errorFilter, errorField]);

    // Fetch paginated clean data
    const fetchClean = useCallback(async () => {
        try {
            const params = new URLSearchParams({ page: cleanPage, limit: 50 });
            const res = await fetch(`${API_BASE}/api/validation/clean?${params.toString()}`);
            const json = await res.json();
            if (json.status === "success") {
                setPaginatedClean(json.data);
                setTotalClean(json.total);
            }
        } catch (err) { console.error("Clean fetch error:", err); }
    }, [cleanPage]);

    useEffect(() => { fetchDashboard(); }, [fetchDashboard]);
    useEffect(() => { if (viewMode === 'errors') fetchErrors(); }, [viewMode, fetchErrors]);
    useEffect(() => { if (viewMode === 'clean') fetchClean(); }, [viewMode, fetchClean]);

    // Auto refresh every 10s
    useEffect(() => {
        if (!autoRefresh) return;
        const interval = setInterval(() => {
            fetchDashboard();
            if (viewMode === 'errors') fetchErrors();
            if (viewMode === 'clean') fetchClean();
        }, 10000);
        return () => clearInterval(interval);
    }, [autoRefresh, fetchDashboard, fetchErrors, fetchClean, viewMode]);

    if (loading || !dashData) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-[#f8fbff]">
                <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mt-8">Loading Validation Dashboard...</span>
            </div>
        );
    }

    const { raw_count, validation_count, clean_count, summary, progress } = dashData;

    // Status color map
    const statusColors = {
        PENDING: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', icon: ClockIcon, dot: 'bg-amber-400' },
        STRUCTURED: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', icon: CheckBadgeIcon, dot: 'bg-emerald-400' },
        INVALID: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', icon: XCircleIcon, dot: 'bg-red-400' },
        MISSING: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200', icon: ExclamationTriangleIcon, dot: 'bg-orange-400' },
        DUPLICATE: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200', icon: DocumentDuplicateIcon, dot: 'bg-purple-400' },
    };

    const ProgressBar = ({ label, value, color, emoji }) => (
        <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{emoji} {label}</span>
                <span className="text-sm font-black text-slate-800">{value}%</span>
            </div>
            <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
                <div
                    className={`h-full ${color} rounded-full transition-all duration-1000 ease-out`}
                    style={{ width: `${Math.min(value, 100)}%` }}
                />
            </div>
        </div>
    );

    return (
        <div className="p-8 bg-[#f8fbff] min-h-screen text-slate-900 font-sans">

            {/* HEADER */}
            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center mb-10 gap-8">
                <div className="relative">
                    <div className="flex items-center gap-4 mb-2">
                        <div className="bg-gradient-to-br from-indigo-600 to-violet-600 p-3 rounded-2xl shadow-indigo-200 shadow-2xl">
                            <ShieldCheckIcon className="w-8 h-8 text-white" />
                        </div>
                        <div>
                            <h1 className="text-4xl font-black tracking-tighter text-slate-900">Validation <span className="text-indigo-600">Pipeline</span></h1>
                            <div className="flex items-center gap-2 mt-1">
                                <div className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-green-500 animate-ping' : 'bg-slate-300'}`}></div>
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                                    3-Layer ETL • {autoRefresh ? 'Auto-Refresh ON' : 'Manual Refresh'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Auto-refresh toggle */}
                    <button
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={`flex items-center gap-2 px-4 py-3 rounded-xl text-[10px] font-black tracking-wider transition-all border ${autoRefresh ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-slate-50 text-slate-400 border-slate-200 hover:bg-slate-100'}`}
                    >
                        <ArrowPathIcon className={`w-4 h-4 ${autoRefresh ? 'animate-spin' : ''}`} /> LIVE
                    </button>

                    {/* Manual refresh */}
                    <button
                        onClick={() => { setLoading(true); fetchDashboard(); }}
                        className="flex items-center gap-2 px-4 py-3 rounded-xl text-[10px] font-black tracking-wider bg-indigo-50 text-indigo-600 border border-indigo-200 hover:bg-indigo-100 transition-all"
                    >
                        <ArrowPathIcon className="w-4 h-4" /> REFRESH
                    </button>

                    {/* Nav toggle */}
                    <div className="flex p-1.5 bg-slate-200/50 backdrop-blur-md rounded-2xl border border-white">
                        {[
                            { key: 'overview', label: 'OVERVIEW', icon: SparklesIcon },
                            { key: 'errors', label: 'ERRORS', icon: ExclamationTriangleIcon },
                            { key: 'clean', label: 'CLEAN DATA', icon: CheckBadgeIcon },
                            { key: 'report', label: 'REPORT', icon: DocumentTextIcon },
                        ].map(tab => (
                            <button
                                key={tab.key}
                                onClick={() => {
                                    setViewMode(tab.key);
                                    if (tab.key !== 'errors') {
                                        setErrorField(null);
                                        setErrorFilter(null);
                                    }
                                }}
                                className={`flex items-center gap-2 px-5 py-3 rounded-xl text-[10px] font-black tracking-widest transition-all ${viewMode === tab.key ? 'bg-white text-indigo-600 shadow-xl border border-indigo-50' : 'text-slate-500 hover:text-indigo-400'}`}
                            >
                                <tab.icon className="w-4 h-4" /> {tab.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* PIPELINE FLOW CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                {/* Raw Source */}
                <div className="bg-white p-6 rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 flex items-center gap-5 hover:scale-[1.02] transition-transform duration-300">
                    <div className="p-4 rounded-2xl bg-slate-700">
                        <InboxStackIcon className="w-8 h-8 text-white" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase font-black tracking-[0.2em] text-slate-400">📥 Raw Source</span>
                        <div className="text-3xl font-black text-slate-800 tabular-nums">
                            <SlotCounter value={raw_count.toLocaleString()} duration={2} />
                        </div>
                        <span className="text-[9px] text-slate-400 font-bold">raw_google_map_drive_data</span>
                    </div>
                </div>

                {/* Validation Layer */}
                <div className="bg-white p-6 rounded-3xl shadow-xl shadow-indigo-100/50 border border-indigo-100 flex items-center gap-5 hover:scale-[1.02] transition-transform duration-300">
                    <div className="p-4 rounded-2xl bg-indigo-600">
                        <ShieldCheckIcon className="w-8 h-8 text-white" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase font-black tracking-[0.2em] text-indigo-400">🔍 Validated</span>
                        <div className="text-3xl font-black text-slate-800 tabular-nums">
                            <SlotCounter value={validation_count.toLocaleString()} duration={2} />
                        </div>
                        <span className="text-[9px] text-indigo-400 font-bold">validation_raw_google_map</span>
                    </div>
                </div>

                {/* Clean Production */}
                <div className="bg-white p-6 rounded-3xl shadow-xl shadow-emerald-100/50 border border-emerald-100 flex items-center gap-5 hover:scale-[1.02] transition-transform duration-300">
                    <div className="p-4 rounded-2xl bg-emerald-500">
                        <CheckBadgeIcon className="w-8 h-8 text-white" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase font-black tracking-[0.2em] text-emerald-500">🧹 Production Clean</span>
                        <div className="text-3xl font-black text-slate-800 tabular-nums">
                            <SlotCounter value={clean_count.toLocaleString()} duration={2} />
                        </div>
                        <span className="text-[9px] text-emerald-400 font-bold">raw_clean_google_map_data</span>
                    </div>
                </div>
            </div>

            {/* ==================== OVERVIEW ==================== */}
            {viewMode === 'overview' && (
                <div className="animate-in fade-in duration-700 space-y-8">

                    {/* PIPELINE PROGRESS */}
                    <div className="bg-white/70 backdrop-blur-xl border border-white rounded-[32px] shadow-2xl shadow-indigo-100 p-8 lg:p-10">
                        <h3 className="text-sm font-black text-slate-800 uppercase tracking-tight mb-8 flex items-center gap-2">
                            <FunnelIcon className="w-5 h-5 text-indigo-600" /> Pipeline Progress
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                            <ProgressBar label="Ingestion" value={progress.ingestion_pct} color="bg-slate-600" emoji="📥" />
                            <ProgressBar label="Validation" value={progress.validation_pct} color="bg-indigo-600" emoji="🔍" />
                            <ProgressBar label="Cleaning" value={progress.cleaning_pct} color="bg-emerald-500" emoji="🧹" />
                        </div>
                    </div>

                    {/* VALIDATION STATUS BREAKDOWN */}
                    <div className="bg-white/70 backdrop-blur-xl border border-white rounded-[32px] shadow-2xl shadow-indigo-100 p-8 lg:p-10">
                        <h3 className="text-sm font-black text-slate-800 uppercase tracking-tight mb-8 flex items-center gap-2">
                            <ShieldCheckIcon className="w-5 h-5 text-indigo-600" /> Validation Status Breakdown
                        </h3>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                            {Object.entries(statusColors).map(([status, config]) => {
                                const count = summary[status.toLowerCase()] || 0;
                                const Icon = config.icon;
                                return (
                                    <div
                                        key={status}
                                        className={`${config.bg} ${config.border} border-2 rounded-2xl p-5 flex flex-col items-center text-center cursor-pointer hover:scale-105 transition-transform`}
                                        onClick={() => { setErrorFilter(status === 'PENDING' || status === 'STRUCTURED' ? null : status); setViewMode('errors'); }}
                                    >
                                        <Icon className={`w-8 h-8 ${config.text} mb-3`} />
                                        <span className={`text-2xl font-black ${config.text} tabular-nums`}>
                                            <SlotCounter value={count.toLocaleString()} duration={1.5} />
                                        </span>
                                        <span className={`text-[9px] font-black ${config.text} uppercase tracking-widest mt-1`}>{status}</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* CLEANING STATUS */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="bg-slate-900 rounded-[32px] p-8 shadow-2xl relative overflow-hidden">
                            <div className="relative z-10">
                                <h4 className="flex items-center gap-3 text-white font-black uppercase tracking-widest text-xs mb-6">
                                    <ClockIcon className="w-5 h-5 text-indigo-400" /> Cleaning Progress
                                </h4>
                                <div className="space-y-6">
                                    <div className="flex justify-between items-center">
                                        <div className="flex items-center gap-3">
                                            <div className="w-3 h-3 rounded-full bg-emerald-400"></div>
                                            <span className="text-white text-sm font-bold">CLEANED</span>
                                        </div>
                                        <span className="text-emerald-400 text-2xl font-black tabular-nums">
                                            <SlotCounter value={(summary.cleaned || 0).toLocaleString()} duration={2} />
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <div className="flex items-center gap-3">
                                            <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                                            <span className="text-white text-sm font-bold">NOT STARTED</span>
                                        </div>
                                        <span className="text-amber-400 text-2xl font-black tabular-nums">
                                            <SlotCounter value={(summary.not_started || 0).toLocaleString()} duration={2} />
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div className="absolute top-0 right-0 w-[200px] h-[200px] bg-indigo-600/10 blur-[80px] rounded-full"></div>
                        </div>

                        {/* Quick stats */}
                        <div className="bg-gradient-to-br from-indigo-600 to-violet-600 rounded-[32px] p-8 shadow-2xl text-white relative overflow-hidden">
                            <div className="relative z-10">
                                <span className="text-[10px] font-black uppercase tracking-[0.3em] opacity-60 mb-6 block">Pipeline Throughput</span>
                                <div className="text-5xl font-black tabular-nums tracking-tighter mb-3">
                                    {clean_count.toLocaleString()}
                                </div>
                                <span className="text-xs font-black uppercase tracking-widest opacity-80 bg-white/10 px-4 py-2 rounded-full border border-white/10">
                                    Rows in Production
                                </span>
                                <div className="mt-6 flex items-center gap-2">
                                    <ChevronRightIcon className="w-4 h-4 opacity-60" />
                                    <span className="text-[10px] font-bold opacity-60">
                                        {validation_count > 0 ? ((clean_count / validation_count) * 100).toFixed(1) : 0}% pass rate from validated rows
                                    </span>
                                </div>
                            </div>
                            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 to-violet-700 opacity-0 hover:opacity-100 transition-opacity duration-700"></div>
                        </div>
                    </div>

                    {/* RECENT CLEAN DATA PREVIEW */}
                    {dashData.clean_data && dashData.clean_data.length > 0 && (
                        <div className="bg-white/70 backdrop-blur-xl border border-white rounded-[32px] shadow-2xl shadow-indigo-100 p-8 lg:p-10">
                            <div className="flex justify-between items-center mb-6">
                                <h3 className="text-sm font-black text-slate-800 uppercase tracking-tight flex items-center gap-2">
                                    <TableCellsIcon className="w-5 h-5 text-emerald-500" /> Recent Clean Data (Latest 50)
                                </h3>
                                <button
                                    onClick={() => setViewMode('clean')}
                                    className="text-[10px] font-black text-indigo-600 uppercase tracking-wider hover:underline"
                                >
                                    View All →
                                </button>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full border-collapse">
                                    <thead>
                                        <tr className="border-b-2 border-slate-100">
                                            {['Name', 'Phone', 'Category', 'City', 'State', 'Reviews', 'Rating'].map(h => (
                                                <th key={h} className="text-left text-[9px] font-black text-slate-400 uppercase tracking-widest py-3 px-4">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {dashData.clean_data.slice(0, 10).map(row => (
                                            <tr key={row.id} className="border-b border-slate-50 hover:bg-indigo-50/30 transition-colors">
                                                <td className="py-3 px-4 text-xs font-bold text-slate-800 max-w-[200px] truncate">{row.name}</td>
                                                <td className="py-3 px-4 text-xs font-mono text-slate-500">{row.phone_number || '---'}</td>
                                                <td className="py-3 px-4"><span className="text-[9px] bg-indigo-50 text-indigo-600 px-2 py-1 rounded-full font-black uppercase">{row.category}</span></td>
                                                <td className="py-3 px-4 text-xs text-slate-600">{row.city}</td>
                                                <td className="py-3 px-4 text-[10px] text-slate-400 uppercase">{row.state}</td>
                                                <td className="py-3 px-4 text-xs font-bold text-slate-600">{row.reviews_count}</td>
                                                <td className="py-3 px-4"><span className="text-[9px] bg-yellow-100 px-2 py-0.5 rounded font-bold">★ {row.reviews_avg}</span></td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ==================== ERRORS VIEW ==================== */}
            {viewMode === 'errors' && (
                <div className="animate-in fade-in duration-700">
                    <div className="bg-white/70 backdrop-blur-xl border border-white rounded-[32px] shadow-2xl shadow-indigo-100 p-8 lg:p-10">
                        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                            <h3 className="text-sm font-black text-slate-800 uppercase tracking-tight flex items-center gap-2">
                                <ExclamationTriangleIcon className="w-5 h-5 text-red-500" /> Validation Errors & Issues
                            </h3>
                            <div className="flex flex-wrap items-center gap-2">
                                {['All', 'INVALID', 'MISSING', 'DUPLICATE'].map(f => (
                                    <button
                                        key={f}
                                        onClick={() => {
                                            setErrorFilter(f === 'All' ? null : f);
                                            setErrorField(null); // Clear field filter when switching main status
                                            setErrorPage(1);
                                        }}
                                        className={`px-3 py-2 rounded-lg text-[9px] font-black uppercase tracking-wider transition-all ${(f === 'All' && !errorFilter) || errorFilter === f ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}
                                    >
                                        {f}
                                    </button>
                                ))}
                                {errorField && (
                                    <span className="bg-rose-50 text-rose-600 px-3 py-2 rounded-lg text-[9px] font-black uppercase tracking-wider border border-rose-100 flex items-center gap-2">
                                        Field: {errorField}
                                        <button onClick={() => setErrorField(null)} className="text-rose-400 hover:text-rose-600">×</button>
                                    </span>
                                )}
                                <span className="text-[9px] font-bold text-slate-400 ml-2">Total: {totalErrors}</span>
                            </div>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr className="border-b-2 border-slate-100">
                                        {['ID', 'Name', 'City', 'State', 'Status', 'Missing Fields', 'Invalid Fields', 'Duplicate', 'Processed'].map(h => (
                                            <th key={h} className="text-left text-[9px] font-black text-slate-400 uppercase tracking-widest py-3 px-3">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {paginatedErrors.map(row => {
                                        const sConfig = statusColors[row.validation_status] || {};
                                        return (
                                            <tr key={row.id} className="border-b border-slate-50 hover:bg-red-50/30 transition-colors">
                                                <td className="py-3 px-3 text-[10px] font-mono text-slate-400">{row.id}</td>
                                                <td className="py-3 px-3 text-xs font-bold text-slate-800 max-w-[180px] truncate">{row.name || '---'}</td>
                                                <td className="py-3 px-3 text-xs text-slate-600">{row.city || '---'}</td>
                                                <td className="py-3 px-3 text-[10px] text-slate-400 uppercase">{row.state || '---'}</td>
                                                <td className="py-3 px-3">
                                                    <span className={`text-[8px] ${sConfig.bg || ''} ${sConfig.text || ''} px-2 py-1 rounded-full font-black uppercase`}>{row.validation_status}</span>
                                                </td>
                                                <td className="py-3 px-3 text-[10px] text-red-500 font-mono max-w-[150px] truncate" title={row.missing_fields}>{row.missing_fields || '---'}</td>
                                                <td className="py-3 px-3 text-[10px] text-orange-500 font-mono max-w-[150px] truncate" title={row.invalid_format_fields}>{row.invalid_format_fields || '---'}</td>
                                                <td className="py-3 px-3 text-[10px] text-purple-500 font-mono">{row.duplicate_reason || '---'}</td>
                                                <td className="py-3 px-3 text-[9px] text-slate-400">{row.processed_at || '---'}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>

                        {/* Pagination */}
                        <div className="mt-8 flex justify-between items-center pt-6 border-t border-slate-50">
                            <button
                                disabled={errorPage === 1}
                                onClick={() => setErrorPage(p => p - 1)}
                                className="px-6 py-3 bg-slate-50 text-slate-600 rounded-xl text-[10px] font-black uppercase disabled:opacity-30"
                            >PREVIOUS</button>
                            <span className="text-[10px] font-black text-slate-400 uppercase">Page {errorPage} • {totalErrors} total</span>
                            <button
                                onClick={() => setErrorPage(p => p + 1)}
                                className="px-6 py-3 bg-slate-50 text-slate-600 rounded-xl text-[10px] font-black uppercase"
                            >NEXT</button>
                        </div>
                    </div>
                </div>
            )}

            {/* ==================== CLEAN DATA VIEW ==================== */}
            {viewMode === 'clean' && (
                <div className="animate-in fade-in duration-700">
                    <div className="bg-white/70 backdrop-blur-xl border border-white rounded-[32px] shadow-2xl shadow-indigo-100 p-8 lg:p-10">
                        <div className="flex justify-between items-center mb-8">
                            <h3 className="text-sm font-black text-slate-800 uppercase tracking-tight flex items-center gap-2">
                                <CheckBadgeIcon className="w-5 h-5 text-emerald-500" /> Clean Production Data
                            </h3>
                            <span className="text-[9px] font-bold text-emerald-500 bg-emerald-50 px-3 py-1 rounded-full">Total: {totalClean}</span>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr className="border-b-2 border-slate-100">
                                        {['ID', 'Name', 'Address', 'Phone', 'Bank/Toll-Free', 'Category', 'City', 'State', 'Reviews', 'Rating'].map(h => (
                                            <th key={h} className="text-left text-[9px] font-black text-slate-400 uppercase tracking-widest py-3 px-3">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {paginatedClean.map(row => (
                                        <tr key={row.id} className="border-b border-slate-50 hover:bg-emerald-50/30 transition-colors">
                                            <td className="py-3 px-3 text-[10px] font-mono text-slate-400">{row.id}</td>
                                            <td className="py-3 px-3 text-xs font-bold text-slate-800 max-w-[200px] truncate">{row.name}</td>
                                            <td className="py-3 px-3 text-[10px] text-slate-500 max-w-[200px] truncate" title={row.address}>{row.address}</td>
                                            <td className="py-3 px-3 text-xs font-mono text-slate-500">{row.phone_number || '---'}</td>
                                            <td className="py-3 px-3 text-xs font-mono text-indigo-600 font-bold">{row.toll_free_number || '---'}</td>
                                            <td className="py-3 px-3"><span className="text-[9px] bg-indigo-50 text-indigo-600 px-2 py-1 rounded-full font-black uppercase">{row.category}</span></td>
                                            <td className="py-3 px-3 text-xs text-slate-600">{row.city}</td>
                                            <td className="py-3 px-3 text-[10px] text-slate-400 uppercase">{row.state}</td>
                                            <td className="py-3 px-3 text-xs font-bold">{row.reviews_count}</td>
                                            <td className="py-3 px-3"><span className="text-[9px] bg-yellow-100 px-2 py-0.5 rounded font-bold">★ {row.reviews_avg}</span></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {/* Pagination */}
                        <div className="mt-8 flex justify-between items-center pt-6 border-t border-slate-50">
                            <button
                                disabled={cleanPage === 1}
                                onClick={() => setCleanPage(p => p - 1)}
                                className="px-6 py-3 bg-slate-50 text-slate-600 rounded-xl text-[10px] font-black uppercase disabled:opacity-30"
                            >PREVIOUS</button>
                            <span className="text-[10px] font-black text-slate-400 uppercase">Page {cleanPage} • {totalClean} total</span>
                            <button
                                onClick={() => setCleanPage(p => p + 1)}
                                className="px-6 py-3 bg-slate-50 text-slate-600 rounded-xl text-[10px] font-black uppercase"
                            >NEXT</button>
                        </div>
                    </div>
                </div>
            )}

            {/* ==================== REPORT VIEW ==================== */}
            {viewMode === 'report' && (
                <div className="animate-in fade-in duration-700">
                    <ValidationReport
                        embedMode={true}
                        onViewMissing={(field) => {
                            setErrorFilter('MISSING');
                            setErrorField(field);
                            setErrorPage(1);
                            setViewMode('errors');
                        }}
                    />
                </div>
            )}

            {/* FOOTER */}
            <div className="mt-12 text-center">
                <p className="text-[10px] font-black text-slate-300 uppercase tracking-[0.5em]">Validation Pipeline Dashboard • ETL v1.0</p>
            </div>
        </div>
    );
};

export default ValidationDashboard;
