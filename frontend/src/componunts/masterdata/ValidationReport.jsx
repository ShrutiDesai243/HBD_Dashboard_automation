import React, { useState, useEffect, useCallback } from 'react';
import Chart from 'react-apexcharts';
import {
    Card,
    CardBody,
    Typography,
    Button,
    Input,
    IconButton,
} from "@material-tailwind/react";
import {
    ShieldCheckIcon,
    ArrowPathIcon,
    ArrowDownTrayIcon,
    FunnelIcon,
    CalendarIcon,
    ChevronRightIcon,
    CheckCircleIcon,
    XCircleIcon,
    ClipboardDocumentCheckIcon,
    ChartBarIcon,
} from "@heroicons/react/24/solid";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

const ValidationReport = ({ embedMode = false, onViewMissing }) => {
    const [reportData, setReportData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        startDate: '',
        endDate: '',
        batchId: ''
    });

    const fetchReport = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (filters.startDate) params.append("start_date", filters.startDate);
            if (filters.endDate) params.append("end_date", filters.endDate);
            if (filters.batchId) params.append("batch_id", filters.batchId);

            const res = await fetch(`${API_BASE}/api/validation/report?${params.toString()}`);
            const json = await res.json();
            if (json.status === "success") {
                setReportData(json);
            }
        } catch (err) {
            console.error("Report fetch error:", err);
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => {
        fetchReport();
    }, [fetchReport]);

    const handleExportCSV = () => {
        if (!reportData) return;
        const headers = ["Field Name", "Missing Count", "Missing Percentage"];
        const rows = reportData.missing_report.map(m => [m.field, m.count, `${m.percentage}%`]);
        const csvContent = "data:text/csv;charset=utf-8,"
            + headers.join(",") + "\n"
            + rows.map(e => e.join(",")).join("\n");

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `validation_report_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
    };

    if (loading && !reportData) {
        return (
            <div className={`flex flex-col items-center justify-center ${embedMode ? 'h-64' : 'min-h-screen'} bg-transparent`}>
                <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mt-8">Analyzing Data...</span>
            </div>
        );
    }

    const kpis = reportData?.kpis || { total: 0, valid: 0, invalid: 0, accuracy: 0, last_updated: null };

    // Bar Chart Config
    const barChartOptions = {
        chart: { toolbar: { show: false }, fontFamily: 'inherit' },
        plotOptions: { bar: { borderRadius: 8, columnWidth: '40%', distributed: true } },
        dataLabels: { enabled: false },
        colors: ['#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e'],
        xaxis: {
            categories: reportData?.missing_report.map(m => m.field) || [],
            labels: { style: { fontWeight: 600, fontSize: '10px' } }
        },
        yaxis: { labels: { style: { fontWeight: 600 } } },
        grid: { strokeDashArray: 4 },
        tooltip: { theme: 'light' },
        legend: { show: false }
    };

    const barChartSeries = [{
        name: 'Missing Count',
        data: reportData?.missing_report.map(m => m.count) || []
    }];

    // Line Chart Config
    const lineChartOptions = {
        chart: { toolbar: { show: false }, fontFamily: 'inherit' },
        stroke: { curve: 'smooth', width: 4, colors: ['#6366f1'] },
        fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.1, stops: [0, 90, 100] } },
        xaxis: {
            categories: reportData?.trend.map(t => t.date.split('-').slice(1).join('/')) || [],
            labels: { style: { fontWeight: 600, fontSize: '10px' } }
        },
        markers: { size: 5, colors: ['#6366f1'], strokeWidth: 3 },
        grid: { strokeDashArray: 4 },
        tooltip: { theme: 'light' }
    };

    const lineChartSeries = [{
        name: 'Daily Validations',
        data: reportData?.trend.map(t => t.count) || []
    }];

    return (
        <div className={`${embedMode ? '' : 'p-6 lg:p-10 bg-[#f8fbff] min-h-screen text-slate-900'}`}>
            {/* Header */}
            {!embedMode && (
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <div className="bg-indigo-600 p-2 rounded-xl shadow-lg shadow-indigo-100">
                                <ClipboardDocumentCheckIcon className="w-6 h-6 text-white" />
                            </div>
                            <h1 className="text-3xl font-black tracking-tight text-slate-900">Validation <span className="text-indigo-600">Report</span></h1>
                        </div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                            <ChartBarIcon className="w-4 h-4" /> Real-time Quality Analytics
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        <Button
                            variant="outlined"
                            size="sm"
                            className="flex items-center gap-2 border-slate-200 text-slate-600 normal-case font-bold bg-white"
                            onClick={handleExportCSV}
                        >
                            <ArrowDownTrayIcon className="w-4 h-4" /> Export CSV
                        </Button>
                        <IconButton size="sm" variant="text" color="indigo" onClick={fetchReport} className={loading ? 'animate-spin' : ''}>
                            <ArrowPathIcon className="w-5 h-5" />
                        </IconButton>
                    </div>
                </div>
            )}

            {/* Filters */}
            <Card className={`mb-8 border border-white bg-white/50 backdrop-blur-md shadow-sm rounded-3xl ${embedMode ? 'mt-4' : ''}`}>
                <CardBody className="p-4 flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-2xl border border-slate-100 shadow-sm min-w-[200px]">
                        <CalendarIcon className="w-4 h-4 text-slate-400" />
                        <input
                            type="date"
                            className="text-xs font-bold text-slate-700 bg-transparent border-none focus:ring-0 outline-none w-full"
                            value={filters.startDate}
                            onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
                        />
                    </div>
                    <span className="text-slate-300 font-bold">to</span>
                    <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-2xl border border-slate-100 shadow-sm min-w-[200px]">
                        <CalendarIcon className="w-4 h-4 text-slate-400" />
                        <input
                            type="date"
                            className="text-xs font-bold text-slate-700 bg-transparent border-none focus:ring-0 outline-none w-full"
                            value={filters.endDate}
                            onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
                        />
                    </div>
                    <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-2xl border border-slate-100 shadow-sm min-w-[150px]">
                        <FunnelIcon className="w-4 h-4 text-slate-400" />
                        <input
                            placeholder="Batch ID..."
                            className="text-xs font-bold text-slate-700 bg-transparent border-none focus:ring-0 outline-none w-full"
                            value={filters.batchId}
                            onChange={(e) => setFilters({ ...filters, batchId: e.target.value })}
                        />
                    </div>
                    <Button size="sm" color="indigo" className="rounded-xl normal-case font-bold" onClick={fetchReport}>Apply Filters</Button>

                    {embedMode && (
                        <div className="flex-1 flex justify-end gap-2">
                            <Button
                                variant="outlined"
                                size="sm"
                                className="flex items-center gap-2 border-slate-200 text-slate-600 normal-case font-bold bg-white"
                                onClick={handleExportCSV}
                            >
                                <ArrowDownTrayIcon className="w-4 h-4" /> CSV
                            </Button>
                            <IconButton size="sm" variant="text" color="indigo" onClick={fetchReport} className={loading ? 'animate-spin' : ''}>
                                <ArrowPathIcon className="w-5 h-5" />
                            </IconButton>
                        </div>
                    )}
                </CardBody>
            </Card>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {[
                    { label: 'Total Processed', value: kpis.total, icon: ClipboardDocumentCheckIcon, color: 'text-slate-600', bg: 'bg-slate-50' },
                    { label: 'Valid Records', value: kpis.valid, icon: CheckCircleIcon, color: 'text-emerald-600', bg: 'bg-emerald-50' },
                    { label: 'Invalid Records', value: kpis.invalid, icon: XCircleIcon, color: 'text-rose-600', bg: 'bg-rose-50' },
                    { label: 'Validation Accuracy', value: `${kpis.accuracy}%`, icon: ShieldCheckIcon, color: 'text-indigo-600', bg: 'bg-indigo-50' },
                ].map((kpi, i) => (
                    <Card key={i} className={`border border-white bg-white shadow-xl shadow-slate-200/50 rounded-3xl overflow-hidden ${!embedMode ? 'hover:scale-105 transition-transform' : ''}`}>
                        <CardBody className="p-6">
                            <div className="flex justify-between items-start mb-4">
                                <div className={`p-3 rounded-2xl ${kpi.bg}`}>
                                    <kpi.icon className={`w-6 h-6 ${kpi.color}`} />
                                </div>
                                {i === 3 && <div className="text-[10px] font-black text-slate-300 uppercase tracking-widest mt-1">Target 95%</div>}
                            </div>
                            <Typography className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-1">{kpi.label}</Typography>
                            <Typography variant="h3" className="font-black text-slate-900 tabular-nums">
                                {typeof kpi.value === 'number' ? kpi.value.toLocaleString() : kpi.value}
                            </Typography>
                        </CardBody>
                    </Card>
                ))}
            </div>

            {/* Charts & Table Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                {/* Missing Fields Chart */}
                <Card className="lg:col-span-2 border border-white bg-white shadow-xl shadow-slate-200/50 rounded-[32px] p-2">
                    <CardBody>
                        <div className="flex justify-between items-center mb-6">
                            <h4 className="text-sm font-black text-slate-800 uppercase tracking-tight flex items-center gap-2">
                                <ChartBarIcon className="w-5 h-5 text-indigo-600" /> Missing Counts By Field
                            </h4>
                        </div>
                        <Chart options={barChartOptions} series={barChartSeries} type="bar" height={320} />
                    </CardBody>
                </Card>

                {/* Missing Fields Table */}
                <Card className="border border-white bg-white shadow-xl shadow-slate-200/50 rounded-[32px] p-2">
                    <CardBody>
                        <h4 className="text-sm font-black text-slate-800 uppercase tracking-tight mb-6">Missing Breakdown</h4>
                        <div className="space-y-4">
                            {reportData?.missing_report.map((m, i) => (
                                <div key={i} className="flex flex-col gap-2 p-3 bg-slate-50 rounded-2xl border border-slate-100">
                                    <div className="flex justify-between items-center">
                                        <span className="text-xs font-black text-slate-700">{m.field}</span>
                                        <span className="text-[10px] font-black text-rose-500">{m.percentage}% missing</span>
                                    </div>
                                    <div className="flex justify-between items-center text-[10px] font-bold text-slate-400">
                                        <span>Total Missing: {m.count.toLocaleString()}</span>
                                        <button
                                            onClick={() => onViewMissing && onViewMissing(m.raw_field)}
                                            className="flex items-center gap-1 text-indigo-500 hover:text-indigo-700 transition-colors"
                                        >
                                            View <ChevronRightIcon className="w-3 h-3" />
                                        </button>
                                    </div>
                                    <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                        <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${m.percentage}%` }}></div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardBody>
                </Card>
            </div>

            {/* Bottom Row: Trend & Detail */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <Card className="lg:col-span-3 border border-white bg-white shadow-xl shadow-slate-200/50 rounded-[32px] p-2">
                    <CardBody>
                        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4 px-2">
                            <div>
                                <h4 className="text-sm font-black text-slate-800 uppercase tracking-tight flex items-center gap-2 mb-1">
                                    <ShieldCheckIcon className="w-5 h-5 text-indigo-600" /> Validation Velocity
                                </h4>
                                <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Processed rows per day (Last 7 Days)</p>
                            </div>
                            <div className="text-right">
                                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Last Synced</p>
                                <p className="text-xs font-black text-indigo-600 tabular-nums">{kpis.last_updated || 'Never'}</p>
                            </div>
                        </div>
                        <Chart options={lineChartOptions} series={lineChartSeries} type="area" height={280} />
                    </CardBody>
                </Card>
            </div>

            {/* Footer */}
            {!embedMode && (
                <div className="mt-12 text-center text-[10px] font-black text-slate-300 uppercase tracking-[0.5em] pb-10">
                    Validation Report Dashboard • Production Ready v1.0
                </div>
            )}
        </div>
    );
};

export default ValidationReport;
