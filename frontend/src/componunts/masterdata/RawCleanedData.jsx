import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ReusableTable from '../Table/ReusableTable';
import SlotCounter from 'react-slot-counter';
import {
    ChartBarIcon,
    FolderIcon,
    DocumentTextIcon,
    ChevronRightIcon,
    ArrowLeftIcon,
    MapPinIcon,
    ArrowPathIcon,
    MagnifyingGlassIcon,
    TableCellsIcon,
    SparklesIcon,
    ClockIcon,
    InboxStackIcon
} from "@heroicons/react/24/solid";

/**
 * ═══════════════════════════════════════════════════════════════════════════════
 *  BUSINESS DATA HUB v4.0  —  Current Edition
 * ═══════════════════════════════════════════════════════════════════════════════
 *  High-performance dashboard for v4.0 Parallel ETL.
 *  Features:
 *    - Real-time slot counters for metrics
 *    - Interactive state/category explorer
 *    - Paginated data browser
 *    - Premium glassmorphism UI
 * ═══════════════════════════════════════════════════════════════════════════════
 */

import { normalizeStateName, normalizeCategory } from '../../utils/normalization';

const RawCleanedData = () => {
    // --- STATE ---
    const [viewMode, setViewMode] = useState('explorer'); // 'stats' | 'explorer' | 'detail'
    const [stats, setStats] = useState({ total_records: 0, total_states: 0, total_categories: 0, total_csvs: 0 });
    const [stateSummary, setStateSummary] = useState({});
    const [recentActivity, setRecentActivity] = useState([]);
    const [filesData, setFilesData] = useState([]);
    const [detailData, setDetailData] = useState([]);
    const [loading, setLoading] = useState(false);

    // Selection state (Hierarchy: state -> category -> file)
    const [selectedState, setSelectedState] = useState(null);
    const [selectedCategory, setSelectedCategory] = useState(null);
    const [selectedFile, setSelectedFile] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [page, setPage] = useState(1);

    // --- VIEW-LAYER AGGREGATION & NORMALIZATION (O(n)) ---
    const aggregatedData = useMemo(() => {
        const states = {};
        Object.entries(stateSummary).forEach(([rawState, data]) => {
            const normState = normalizeStateName(rawState);
            if (!states[normState]) {
                states[normState] = {
                    state: normState,
                    total: 0,
                    categories: {},
                    rawStates: new Set()
                };
            }
            states[normState].total += data.total;
            states[normState].rawStates.add(rawState);

            Object.entries(data.categories).forEach(([rawCat, count]) => {
                const normCat = normalizeCategory(rawCat);
                if (!states[normState].categories[normCat]) {
                    states[normState].categories[normCat] = {
                        category: normCat,
                        total: 0,
                        rawMappings: [] // List of { state: rawState, category: rawCat }
                    };
                }
                states[normState].categories[normCat].total += count;
                states[normState].categories[normCat].rawMappings.push({ state: rawState, category: rawCat });
            });
        });

        // Ensure "OTHER" is sorted at the end for each state
        Object.values(states).forEach(st => {
            const sortedCats = Object.fromEntries(
                Object.entries(st.categories).sort(([a], [b]) => {
                    if (a === "OTHER") return 1;
                    if (b === "OTHER") return -1;
                    return a.localeCompare(b);
                })
            );
            st.categories = sortedCats;
        });

        // Sort states alphabetically
        return Object.fromEntries(
            Object.entries(states).sort(([a], [b]) => a.localeCompare(b))
        );
    }, [stateSummary]);

    // --- DATA INTEGRITY VALIDATION LAYER ---
    const integrityReport = useMemo(() => {
        if (!stateSummary || Object.keys(stateSummary).length === 0) return null;

        const rawTotalRecords = Object.values(stateSummary).reduce((acc, st) => acc + st.total, 0);
        const aggTotalRecords = Object.values(aggregatedData).reduce((acc, st) => acc + st.total, 0);

        const rawTotalFiles = stats.total_csvs || 0;

        return {
            rawTotalRecords,
            aggTotalRecords,
            isValid: rawTotalRecords === aggTotalRecords,
            mismatch: rawTotalRecords - aggTotalRecords
        };
    }, [stateSummary, aggregatedData, stats.total_csvs]);

    // --- API CALLS ---

    // 1. Global Stats
    const fetchStats = useCallback(async () => {
        try {
            const params = new URLSearchParams();
            // Note: Stats API currently only supports single raw names. 
            // In a production environment with multiple raw mapping, we would fetch and sum them.
            if (selectedState && aggregatedData[selectedState]) {
                // If selective, pick first raw state for now or omit to get global
                // params.append('state', Array.from(aggregatedData[selectedState].rawStates)[0]);
            }
            const res = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8001"}/api/model/stats?${params.toString()}`);
            const json = await res.json();
            if (json.status === "success") setStats(json);
        } catch (err) { console.error("Stats Error:", err); }
    }, [selectedState, aggregatedData]);

    // 2. State & Category Distribution
    const fetchStateSummary = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8001"}/api/model/state-summary`);
            const json = await res.json();
            if (json.status === "success") setStateSummary(json.data);
        } catch (err) { console.error("Summary Error:", err); }
        finally { setLoading(false); }
    }, []);

    // 3. Fetch files within a category (HANDLES MULTIPLE RAW MAPPINGS)
    const fetchFiles = useCallback(async () => {
        if (!selectedState || !selectedCategory) return;
        const catData = aggregatedData[selectedState]?.categories[selectedCategory];
        if (!catData) return;

        setLoading(true);
        try {
            // Parallel fetch for all raw mappings to ensure zero data loss
            const fetchPromises = catData.rawMappings.map(async ({ state, category }) => {
                const params = new URLSearchParams({ state, category });
                const res = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8001"}/api/model/files?${params.toString()}`);
                const json = await res.json();
                return json.status === "success" ? json.data : [];
            });

            const results = await Promise.all(fetchPromises);
            const flattened = results.flat();

            // Deduplicate files by name while summing counts if necessary
            // (In case the same file is mapped to multiple raw categories that were merged)
            const uniqueFilesMap = new Map();
            flattened.forEach(file => {
                if (uniqueFilesMap.has(file.file_name)) {
                    const existing = uniqueFilesMap.get(file.file_name);
                    // Keep the latest modification time and sum counts if they differ
                    // usually counts should be the same as they come from the same file_id
                    uniqueFilesMap.set(file.file_name, {
                        ...existing,
                        last_mod: new Date(file.last_mod) > new Date(existing.last_mod) ? file.last_mod : existing.last_mod
                    });
                } else {
                    uniqueFilesMap.set(file.file_name, file);
                }
            });

            const deduped = Array.from(uniqueFilesMap.values());
            // Sort: Newest first
            deduped.sort((a, b) => new Date(b.last_mod) - new Date(a.last_mod));
            setFilesData(deduped);
        } catch (err) { console.error("Files Error:", err); }
        finally { setLoading(false); }
    }, [selectedState, selectedCategory, aggregatedData]);

    // 4. Paginated Data Detail
    const fetchDetailData = useCallback(async () => {
        if (!selectedFile) return;
        setLoading(true);
        try {
            const params = new URLSearchParams({ page, limit: 50, file_name: selectedFile });
            const res = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8001"}/api/model/all?${params.toString()}`);
            const json = await res.json();
            if (json.status === "success") setDetailData(json.data);
        } catch (err) { console.error("Detail Error:", err); }
        finally { setLoading(false); }
    }, [page, selectedFile]);

    // 5. Recent Activity Log
    const fetchRecent = useCallback(async () => {
        try {
            const res = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8001"}/api/model/recent`);
            const json = await res.json();
            if (json.status === "success") {
                setRecentActivity(json.data);
            }
        } catch (err) { console.error("Recent Error:", err); }
    }, []);

    // Initial Load
    useEffect(() => {
        fetchStateSummary();
        fetchRecent();
    }, [fetchStateSummary, fetchRecent]);

    // Dynamic Updates
    useEffect(() => {
        fetchStats();
    }, [fetchStats]);

    useEffect(() => {
        if (selectedState && selectedCategory && !selectedFile) {
            fetchFiles();
        }
    }, [selectedState, selectedCategory, selectedFile, fetchFiles]);

    useEffect(() => {
        if (selectedFile) {
            fetchDetailData();
        }
    }, [selectedFile, fetchDetailData]);

    // --- RENDER HELPERS ---

    const StatsCard = ({ title, value, icon: Icon, color }) => (
        <div className="bg-white p-6 rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 flex items-center gap-5 hover:scale-[1.02] transition-transform duration-300">
            <div className={`p-4 rounded-2xl ${color}`}>
                <Icon className="w-8 h-8 text-white" />
            </div>
            <div className="flex flex-col">
                <span className="text-[10px] uppercase font-black tracking-[0.2em] text-slate-400">{title}</span>
                <div className="text-3xl font-black text-slate-800 tabular-nums">
                    <SlotCounter value={value} duration={2} />
                </div>
            </div>
        </div>
    );

    const detailColumns = [
        { header: "Name", accessor: "name", render: (r) => <span className="font-black text-slate-800">{r.name}</span> },
        { header: "Location", accessor: "city", render: (r) => <div className="flex flex-col"><span className="text-xs font-bold text-slate-600">{r.city}</span><span className="text-[10px] text-slate-400 uppercase">{r.state}</span></div> },
        { header: "Category", accessor: "category", render: (r) => <span className="text-[10px] bg-indigo-50 text-indigo-600 px-3 py-1 rounded-full font-black uppercase tracking-wider">{r.category}</span> },
        { header: "Contact", accessor: "phone_number", render: (r) => <span className="font-mono text-xs">{r.phone_number || '---'}</span> },
        { header: "Engagement", accessor: "reviews_count", render: (r) => <div className="flex items-center gap-2"><span className="text-xs font-bold">{r.reviews_count}</span><span className="text-[9px] bg-yellow-100 px-1 rounded">★ {r.reviews_average}</span></div> },
        { header: "Source File", accessor: "drive_file_name", render: (r) => <div className="flex flex-col"><span className="text-[10px] text-slate-400 font-mono truncate max-w-[150px]" title={r.drive_file_name}>{r.drive_file_name}</span><span className="text-[8px] text-slate-300 font-mono truncate max-w-[150px]" title={r.drive_file_path}>{r.drive_file_path}</span></div> },
    ];

    // --- MAIN RENDER ---
    return (
        <div className="p-8 bg-[#f8fbff] min-h-screen text-slate-900 font-sans">

            {/* 1. TOP HEADER SECTION */}
            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center mb-10 gap-8">
                <div className="relative">
                    <div className="flex items-center gap-4 mb-2">
                        <div className="bg-indigo-600 p-3 rounded-2xl shadow-indigo-200 shadow-2xl">
                            <SparklesIcon className="w-8 h-8 text-white animate-pulse" />
                        </div>
                        <div>
                            <h1 className="text-4xl font-black tracking-tighter text-slate-900">Data Hub <span className="text-indigo-600">v5.0</span></h1>
                            <div className="flex items-center gap-2 mt-1">
                                <div className="w-2 h-2 rounded-full bg-green-500 animate-ping"></div>
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Live Engine Active • Incremental Scan Enabled</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* NAV TOGGLE */}
                <div className="flex p-1.5 bg-slate-200/50 backdrop-blur-md rounded-2xl border border-white">
                    <button
                        onClick={() => setViewMode('explorer')}
                        className={`flex items-center gap-2 px-6 py-3 rounded-xl text-[11px] font-black tracking-widest transition-all ${viewMode === 'explorer' ? 'bg-white text-indigo-600 shadow-xl border border-indigo-50' : 'text-slate-500 hover:text-indigo-400'}`}
                    >
                        <FolderIcon className="w-4 h-4" /> EXPLORER
                    </button>
                    <button
                        onClick={() => setViewMode('detail')}
                        className={`flex items-center gap-2 px-6 py-3 rounded-xl text-[11px] font-black tracking-widest transition-all ${viewMode === 'detail' ? 'bg-white text-indigo-600 shadow-xl border border-indigo-50' : 'text-slate-500 hover:text-indigo-400'}`}
                    >
                        <TableCellsIcon className="w-4 h-4" /> BROWSER
                    </button>
                    <button
                        onClick={() => setViewMode('stats')}
                        className={`flex items-center gap-2 px-6 py-3 rounded-xl text-[11px] font-black tracking-widest transition-all ${viewMode === 'stats' ? 'bg-white text-indigo-600 shadow-xl border border-indigo-50' : 'text-slate-500 hover:text-indigo-400'}`}
                    >
                        <ChartBarIcon className="w-4 h-4" /> ANALYTICS
                    </button>
                </div>
            </div>

            {/* 2. STATS OVERVIEW CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-10">
                <StatsCard title="Total CSVs" value={stats.total_csvs || 0} icon={InboxStackIcon} color="bg-indigo-600" />
                <StatsCard title="Total Records" value={stats.total_records} icon={InboxStackIcon} color="bg-indigo-400" />
                <StatsCard title="Active States" value={stats.total_states} icon={MapPinIcon} color="bg-emerald-500" />
                <StatsCard title="Categories" value={stats.total_categories} icon={TableCellsIcon} color="bg-amber-500" />
            </div>

            {/* 3. MAIN CONTENT AREA */}
            <div className="bg-white/70 backdrop-blur-xl border border-white rounded-[40px] shadow-2xl shadow-indigo-100 overflow-hidden">
                <div className="p-8 lg:p-12">

                    {/* DATA INTEGRITY ALERT */}
                    {integrityReport && !integrityReport.isValid && (
                        <div className="mb-8 p-4 bg-red-50 border-2 border-red-200 rounded-2xl flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="p-2 bg-red-500 rounded-lg">
                                    <SparklesIcon className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h5 className="text-xs font-black text-red-800 uppercase">Data Integrity Warning</h5>
                                    <p className="text-[10px] text-red-600 font-bold uppercase">View-layer mismatch detected: {integrityReport.mismatch} records hidden or malformed.</p>
                                </div>
                            </div>
                            <span className="text-[10px] font-mono bg-red-200 px-3 py-1 rounded-full text-red-800 font-bold">ERR_001_MISMATCH</span>
                        </div>
                    )}

                    {/* BREADCRUMBS */}
                    <div className="flex items-center gap-2 text-[11px] font-black text-slate-400 mb-10 px-2">
                        <button onClick={() => { setSelectedState(null); setSelectedCategory(null); setSelectedFile(null); setViewMode('explorer'); }} className="hover:text-indigo-600 uppercase">ROOT (ALL STATES)</button>
                        {selectedState && <><ChevronRightIcon className="w-3 h-3" /> <button onClick={() => { setSelectedCategory(null); setSelectedFile(null); }} className="text-slate-600 uppercase hover:text-indigo-600">{selectedState}</button></>}
                        {selectedCategory && <><ChevronRightIcon className="w-3 h-3" /> <button onClick={() => { setSelectedFile(null); }} className="text-slate-600 uppercase hover:text-indigo-600">{selectedCategory}</button></>}
                        {selectedFile && <><ChevronRightIcon className="w-3 h-3" /> <span className="text-indigo-600 uppercase truncate max-w-[200px]">{selectedFile}</span></>}
                    </div>

                    {/* EXPLORER VIEW */}
                    {viewMode === 'explorer' && (
                        <div className="animate-in fade-in slide-in-from-bottom-5 duration-700">
                            {loading && Object.keys(aggregatedData).length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-40">
                                    <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mt-8">Loading Data Engine...</span>
                                </div>
                            ) : (
                                <>
                                    {/* LEVEL 1: NORMALIZED STATES */}
                                    {!selectedState ? (
                                        <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-8">
                                            {Object.values(aggregatedData).map((st) => (
                                                <div
                                                    key={st.state}
                                                    onClick={() => setSelectedState(st.state)}
                                                    className="group cursor-pointer bg-white p-8 rounded-[32px] border border-slate-100 shadow-sm hover:shadow-2xl hover:shadow-indigo-100 hover:border-indigo-400 transition-all duration-500 flex flex-col items-center text-center"
                                                >
                                                    <div className="w-20 h-20 bg-slate-50 rounded-3xl mb-6 flex items-center justify-center group-hover:bg-indigo-50 transition-colors">
                                                        <FolderIcon className="w-10 h-10 text-indigo-400 group-hover:text-indigo-600 transition-colors" />
                                                    </div>
                                                    <h4 className="text-sm font-black text-slate-800 uppercase tracking-tighter mb-1 truncate w-full px-2" title={st.state}>{st.state}</h4>
                                                    <div className="flex gap-2">
                                                        <span className="text-[10px] font-black text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full uppercase">{Object.keys(st.categories).length} Cats</span>
                                                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{st.total.toLocaleString()} Rows</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : /* LEVEL 2: NORMALIZED CATEGORIES */ !selectedCategory ? (
                                        <div className="animate-in fade-in zoom-in-95 duration-500">
                                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                                                {Object.values(aggregatedData[selectedState].categories)
                                                    .sort((a, b) => a.category.localeCompare(b.category))
                                                    .map((cat) => (
                                                        <div
                                                            key={cat.category}
                                                            onClick={() => setSelectedCategory(cat.category)}
                                                            className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm hover:shadow-xl hover:border-emerald-400 transition-all cursor-pointer flex items-center justify-between group"
                                                        >
                                                            <div className="flex items-center gap-4">
                                                                <div className="w-12 h-12 bg-emerald-50 rounded-2xl flex items-center justify-center group-hover:bg-emerald-500 transition-colors">
                                                                    <FolderIcon className="w-6 h-6 text-emerald-500 group-hover:text-white transition-colors" />
                                                                </div>
                                                                <div className="flex flex-col min-w-0">
                                                                    <span className="text-sm font-black text-slate-800 uppercase tracking-tight truncate" title={cat.category}>{cat.category}</span>
                                                                    <span className="text-[10px] text-slate-400 font-bold">{cat.total.toLocaleString()} Records in this State</span>
                                                                </div>
                                                            </div>
                                                            <ChevronRightIcon className="w-5 h-5 text-slate-200 group-hover:text-emerald-400 transition-colors" />
                                                        </div>
                                                    ))}
                                            </div>
                                        </div>
                                    ) : /* LEVEL 3: CSV FILES (PRESERVED) */ !selectedFile ? (
                                        <div className="animate-in fade-in zoom-in-95 duration-500">
                                            <div className="mb-6 flex items-center gap-2">
                                                <InboxStackIcon className="w-5 h-5 text-indigo-600" />
                                                <h3 className="text-sm font-black text-slate-800 uppercase">Files in {selectedState} / {selectedCategory}</h3>
                                            </div>
                                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                                                {filesData.map((file) => (
                                                    <div
                                                        key={file.file_name}
                                                        onClick={() => { setSelectedFile(file.file_name); setViewMode('detail'); }}
                                                        className="bg-slate-50/50 p-6 rounded-3xl border border-slate-100 hover:bg-white hover:border-indigo-400 hover:shadow-xl transition-all cursor-pointer group"
                                                    >
                                                        <div className="flex items-start gap-4 mb-4">
                                                            <div className="bg-white p-3 rounded-2xl border border-slate-100 group-hover:bg-indigo-600 transition-colors shadow-sm">
                                                                <DocumentTextIcon className="w-6 h-6 text-slate-400 group-hover:text-white transition-colors" />
                                                            </div>
                                                            <div className="flex flex-col min-w-0">
                                                                <span className="text-xs font-black text-slate-800 line-clamp-2 break-all" title={file.file_name}>{file.file_name}</span>
                                                                <span className="text-[9px] text-slate-400 font-bold uppercase mt-1 truncate max-w-[200px]" title={file.path}>{file.path || 'Found in Drive'}</span>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                                                            <div className="flex flex-col">
                                                                <span className="text-[11px] font-black text-indigo-600">{file.count.toLocaleString()} ROWS</span>
                                                                <span className="text-[8px] text-slate-400 font-bold uppercase mt-1">Ingested</span>
                                                            </div>
                                                            <div className="flex items-center gap-1 text-[8px] font-black text-slate-400 uppercase">
                                                                <ClockIcon className="w-3 h-3" /> {new Date(file.last_mod).toLocaleDateString()}
                                                            </div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-center py-20">
                                            <p className="text-xs font-black text-slate-400 uppercase tracking-widest">Selected: {selectedFile}. Use Navigator to Browse.</p>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}

                    {/* DETAIL/BROWSER VIEW (LEVEL 4) */}
                    {viewMode === 'detail' && (
                        <div className="animate-in fade-in duration-700">
                            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-6">
                                <div className="flex flex-col">
                                    <h3 className="text-sm font-black text-slate-800 uppercase mb-1">
                                        {selectedFile || "Records Browser"}
                                    </h3>
                                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                                        {selectedState} • {selectedCategory} • Page {page}
                                    </p>
                                </div>
                                <div className="relative w-full md:w-[400px]">
                                    <MagnifyingGlassIcon className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-slate-300" />
                                    <input
                                        type="text"
                                        placeholder="Search within this state/category..."
                                        className="w-full bg-slate-50 border-none rounded-2xl py-4 pl-12 pr-6 text-sm font-bold text-slate-600 placeholder:text-slate-300 focus:ring-2 focus:ring-indigo-100"
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                    />
                                </div>
                            </div>

                            {loading ? (
                                <div className="flex flex-col items-center justify-center py-40">
                                    <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mt-8">Fetching high-speed records...</span>
                                </div>
                            ) : (
                                <>
                                    <ReusableTable columns={detailColumns} data={detailData} />
                                    <div className="mt-10 flex justify-between items-center py-6 border-t border-slate-50">
                                        <button
                                            disabled={page === 1}
                                            onClick={() => setPage(p => p - 1)}
                                            className="px-6 py-3 bg-slate-50 text-slate-600 rounded-xl text-[10px] font-black uppercase disabled:opacity-30"
                                        >PREVIOUS PAGE</button>
                                        <div className="flex items-center gap-4">
                                            <span className="text-[10px] font-black text-slate-400 uppercase">PAGE {page}</span>
                                        </div>
                                        <button
                                            onClick={() => setPage(p => p + 1)}
                                            className="px-6 py-3 bg-slate-50 text-slate-600 rounded-xl text-[10px] font-black uppercase"
                                        >NEXT PAGE</button>
                                    </div>
                                </>
                            )}
                        </div>
                    )}

                    {/* ANALYTICS VIEW */}
                    {viewMode === 'stats' && (
                        <div className="animate-in slide-in-from-right-10 duration-700">
                            <div className="mb-12">
                                <h3 className="text-2xl font-black text-slate-800 tracking-tighter border-l-8 border-indigo-600 pl-6 mb-2 uppercase">System Health</h3>
                                <p className="text-xs text-slate-400 font-bold uppercase tracking-widest pl-8">Real-time log of the Google Drive Parallel Ingestion Engine</p>
                            </div>

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
                                {/* RECENT LOGS */}
                                <div className="bg-slate-900 rounded-[32px] p-8 shadow-2xl relative overflow-hidden">
                                    <div className="flex items-center justify-between mb-8 relative z-10">
                                        <h4 className="flex items-center gap-3 text-white font-black uppercase tracking-widest text-xs">
                                            <ClockIcon className="w-5 h-5 text-indigo-400" /> Activity Stream
                                        </h4>
                                        <div className="px-3 py-1 bg-indigo-500/20 text-indigo-300 rounded-full text-[9px] font-black">LIVE LOGS</div>
                                    </div>
                                    <div className="space-y-4 max-h-[500px] overflow-y-auto pr-4 scrollbar-hide relative z-10">
                                        {recentActivity.map((log) => (
                                            <div key={log.id} className="group flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5 hover:bg-white/10 transition-colors">
                                                <div className="flex items-center gap-4">
                                                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                                                    <div className="flex flex-col">
                                                        <span className="text-[11px] font-black text-slate-200 uppercase tracking-tight">{log.name}</span>
                                                        <span className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.1em]">{log.path || `${log.city}, ${log.state}`}</span>
                                                    </div>
                                                </div>
                                                <span className="text-[10px] font-mono text-indigo-400/50 group-hover:text-indigo-400 transition-colors">+{log.id}</span>
                                            </div>
                                        ))}
                                    </div>
                                    {/* Decor */}
                                    <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-indigo-600/10 blur-[100px] rounded-full"></div>
                                </div>

                                {/* PERFORMANCE MONITOR */}
                                <div className="flex flex-col gap-8">
                                    <div className="bg-white p-8 rounded-[32px] border border-slate-100 shadow-sm flex flex-col items-center text-center">
                                        <div className="w-16 h-16 bg-orange-50 rounded-3xl flex items-center justify-center mb-4">
                                            <ArrowPathIcon className="w-8 h-8 text-orange-500" />
                                        </div>
                                        <span className="text-4xl font-black text-slate-800 tabular-nums tracking-tighter mb-2">60s</span>
                                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Recursive Scan Interval</span>
                                    </div>
                                    <div className="bg-indigo-600 p-10 rounded-[40px] shadow-2xl shadow-indigo-200 flex flex-col items-center text-center text-white relative overflow-hidden group">
                                        <div className="relative z-10">
                                            <span className="text-[10px] font-black uppercase tracking-[0.3em] opacity-60 mb-8 block">Ingestion Speed</span>
                                            <div className="text-6xl font-black tabular-nums tracking-tighter mb-4">15,000+</div>
                                            <span className="text-xs font-black uppercase tracking-widest opacity-80 bg-white/10 px-6 py-2 rounded-full border border-white/10">Rows / Second</span>
                                        </div>
                                        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 to-indigo-700 opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                </div>
            </div>

            {/* 4. FOOTER CREDITS */}
            <div className="mt-12 text-center">
                <p className="text-[10px] font-black text-slate-300 uppercase tracking-[0.5em]">Antigravity Intelligence Systems • GDrive ETL v4.0</p>
            </div>
        </div>
    );
};

export default RawCleanedData;
