import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import {
  ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, AreaChart, Area, LineChart, Line,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ScatterChart, Scatter, ZAxis, Treemap, ComposedChart
} from "recharts";
import api from "../utils/Api";

/* ================================================================
   GLOBAL CSS – injected once
   ================================================================ */
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  .pdr-root {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #f0f2f7;
    min-height: 100vh;
    color: #1a1d2e;
  }

  /* ── Scrollbar ── */
  .pdr-root ::-webkit-scrollbar { width: 5px; height: 5px; }
  .pdr-root ::-webkit-scrollbar-track { background: rgba(0,0,0,0.04); border-radius: 99px; }
  .pdr-root ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 99px; }

  /* ── Header ── */
  .pdr-header {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    padding: 28px 36px 24px;
    position: relative;
    overflow: hidden;
  }
  .pdr-header::before {
    content: '';
    position: absolute; top: -60px; right: -60px;
    width: 260px; height: 260px;
    background: radial-gradient(circle, rgba(139,92,246,0.25) 0%, transparent 70%);
    pointer-events: none;
  }
  .pdr-header-title { font-size: 26px; font-weight: 800; color: #fff; letter-spacing: -0.5px; line-height: 1.2; }
  .pdr-header-sub { font-size: 12px; color: rgba(255,255,255,0.5); margin-top: 4px; font-weight: 400; }
  .pdr-live-dot {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 10px; font-weight: 700; color: #60a5fa; text-transform: uppercase;
    letter-spacing: 1px; background: rgba(96,165,250,0.12);
    padding: 4px 10px; border-radius: 99px; border: 1px solid rgba(96,165,250,0.2);
    margin-bottom: 8px;
  }
  .pdr-live-dot span {
    width: 6px; height: 6px; border-radius: 50%; background: #60a5fa;
    box-shadow: 0 0 0 0 rgba(96,165,250,0.4); animation: liveBlip 1.8s infinite;
  }
  @keyframes liveBlip {
    0%   { box-shadow: 0 0 0 0 rgba(96,165,250,0.5); }
    70%  { box-shadow: 0 0 0 8px rgba(96,165,250,0); }
    100% { box-shadow: 0 0 0 0 rgba(96,165,250,0); }
  }

  /* ── Marketplace Cards ── */
  .pdr-mktplace-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px; padding: 24px 36px;
  }
  .pdr-mktplace-card {
    background: #fff; border-radius: 16px; border: 2px solid transparent;
    padding: 18px 16px; cursor: pointer;
    transition: all 0.28s cubic-bezier(0.4,0,0.2,1);
    position: relative; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .pdr-mktplace-card:hover { transform: translateY(-3px); box-shadow: 0 12px 30px rgba(0,0,0,0.1); }
  .pdr-mktplace-card.active { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-a15), 0 12px 30px rgba(0,0,0,0.1); }
  .pdr-mktplace-card .mc-icon { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; margin-bottom: 12px; background: var(--accent-a10); border: 1px solid var(--accent-a20); }
  .pdr-mktplace-card .mc-name { font-size: 14px; font-weight: 700; color: #1a1d2e; }
  .pdr-mktplace-card .mc-count { font-size: 20px; font-weight: 900; color: var(--accent); margin-top: 4px; }
  .pdr-mktplace-card .mc-avg { font-size: 10px; font-weight: 600; color: #94a3b8; margin-top: 2px; }
  .pdr-mktplace-card .mc-badge { position: absolute; top: 10px; right: 10px; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; padding: 3px 7px; border-radius: 99px; }

  /* ── KPI Cards ── */
  .pdr-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; padding: 0 36px 24px; }
  .pdr-kpi-card {
    background: #fff; border-radius: 16px; padding: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid var(--accent, #6366f1);
    position: relative; overflow: hidden; transition: all 0.2s;
  }
  .pdr-kpi-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
  .pdr-kpi-card .kpi-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; }
  .pdr-kpi-card .kpi-value { font-size: 28px; font-weight: 900; color: #1a1d2e; margin-top: 4px; letter-spacing: -1px; }
  .pdr-kpi-card .kpi-sub { font-size: 11px; color: #64748b; margin-top: 6px; font-weight: 500; }
  .pdr-kpi-card .kpi-icon { position: absolute; right: 16px; top: 16px; font-size: 28px; opacity: 0.1; }

  /* ── Nav Tabs ── */
  .pdr-nav { display: flex; gap: 4px; padding: 0 36px 16px; border-bottom: 1px solid #e8ecf0; margin-bottom: 24px; overflow-x: auto; -ms-overflow-style: none; scrollbar-width: none; }
  .pdr-nav::-webkit-scrollbar { display: none; }
  .pdr-nav-tab { display: flex; align-items: center; gap: 7px; padding: 10px 18px; border-radius: 12px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; background: transparent; color: #64748b; white-space: nowrap; transition: all 0.2s; }
  .pdr-nav-tab:hover { background: #f1f5f9; color: #334155; }
  .pdr-nav-tab.active { background: #1a1d2e; color: #fff; }
  .pdr-nav-tab .tab-count { font-size: 10px; padding: 2px 7px; border-radius: 99px; font-weight: 800; }
  .pdr-nav-tab.active .tab-count { background: rgba(255,255,255,0.18); color: rgba(255,255,255,0.85); }
  .pdr-nav-tab:not(.active) .tab-count { background: #e2e8f0; color: #64748b; }

  /* ── Controls ── */
  .pdr-controls { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 36px 20px; flex-wrap: wrap; }
  .pdr-search { display: flex; align-items: center; gap: 10px; background: #fff; border: 1.5px solid #e2e8f0; border-radius: 12px; padding: 9px 14px; min-width: 260px; transition: border-color 0.2s; }
  .pdr-search:focus-within { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
  .pdr-search input { border: none; outline: none; font-size: 12px; font-weight: 500; color: #1a1d2e; width: 100%; font-family: inherit; background: transparent; }
  .pdr-select { padding: 9px 14px; border-radius: 12px; border: 1.5px solid #e2e8f0; background: #fff; font-size: 12px; font-weight: 600; color: #374151; cursor: pointer; outline: none; font-family: inherit; transition: border-color 0.2s; }
  .pdr-select:focus { border-color: #6366f1; }

  /* ── Buttons ── */
  .pdr-btn { display: inline-flex; align-items: center; gap: 7px; padding: 10px 18px; border-radius: 12px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; font-family: inherit; transition: all 0.2s; white-space: nowrap; }
  .pdr-btn-primary { background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: #fff; box-shadow: 0 4px 12px rgba(99,102,241,0.3); }
  .pdr-btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(99,102,241,0.4); }
  .pdr-btn-green { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: #fff; box-shadow: 0 4px 12px rgba(34,197,94,0.3); }
  .pdr-btn-green:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(34,197,94,0.4); }
  .pdr-btn-ghost { background: #fff; color: #374151; border: 1.5px solid #e2e8f0; }
  .pdr-btn-ghost:hover { background: #f8fafc; }
  .pdr-btn-icon { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; background: #fff; border: 1.5px solid #e2e8f0; cursor: pointer; transition: all 0.2s; }
  .pdr-btn-icon:hover { background: #f1f5f9; }
  .pdr-btn-icon.spinning svg { animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Spinner / Empty ── */
  .pdr-spinner-wrap { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px 0; gap: 14px; }
  .pdr-spinner { width: 40px; height: 40px; border-radius: 50%; border: 3px solid #e2e8f0; border-top-color: #6366f1; animation: spin 0.75s linear infinite; }
  .pdr-spinner-text { font-size: 12px; color: #94a3b8; font-weight: 500; }
  .pdr-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px 0; gap: 12px; }
  .pdr-empty-icon { font-size: 48px; opacity: 0.3; }
  .pdr-empty-text { font-size: 14px; font-weight: 600; color: #64748b; }
  .pdr-empty-sub { font-size: 12px; color: #94a3b8; }

  /* ── Stars ── */
  .pdr-stars { display: flex; gap: 2px; align-items: center; }
  .pdr-star { font-size: 11px; }

  /* ── Badges ── */
  .badge-green { background: #dcfce7; color: #16a34a; }
  .badge-red { background: #fee2e2; color: #dc2626; }
  .badge-blue { background: #dbeafe; color: #2563eb; }
  .badge-amber { background: #fef3c7; color: #d97706; }
  .badge-purple { background: #ede9fe; color: #7c3aed; }
  .badge-gray { background: #f1f5f9; color: #475569; }

  /* ── Analytics Panel ── */
  .pdr-analytics-wrap { padding: 0 36px 32px; }
  .pdr-analytics-header {
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
    margin-bottom: 20px;
    background: #fff; border-radius: 16px; padding: 18px 22px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06); border: 1px solid #f0f2f7;
  }
  .pdr-analytics-title { font-size: 15px; font-weight: 800; color: #1a1d2e; }
  .pdr-analytics-sub { font-size: 11px; color: #94a3b8; font-weight: 500; margin-top: 2px; }
  .pdr-action-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }

  /* ── Charts Grid ── */
  .pdr-charts-grid {
    display: grid; gap: 18px;
    grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
  }
  .pdr-charts-grid.two-col { grid-template-columns: repeat(2, 1fr); }
  .pdr-chart-card {
    background: #fff; border-radius: 20px; padding: 22px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    transition: all 0.25s; position: relative; overflow: hidden;
    border: 1px solid #f0f2f7;
  }
  .pdr-chart-card:hover { box-shadow: 0 8px 28px rgba(0,0,0,0.09); transform: translateY(-1px); }
  .pdr-chart-card.span-2 { grid-column: 1 / -1; }
  .pdr-chart-card .cc-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 18px; }
  .pdr-chart-card .cc-title { font-size: 13px; font-weight: 800; color: #1a1d2e; }
  .pdr-chart-card .cc-sub { font-size: 10px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }
  .pdr-chart-card .cc-badge { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; padding: 4px 8px; border-radius: 99px; }
  .cc-no-data { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 200px; gap: 8px; }
  .cc-no-data .nd-icon { font-size: 32px; opacity: 0.3; }
  .cc-no-data .nd-text { font-size: 12px; color: #94a3b8; font-weight: 600; }

  /* ── Tooltip ── */
  .pdr-tooltip { background: #0f172a; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 10px 14px; font-size: 12px; color: #fff; box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
  .pdr-tooltip-label { font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.45); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .pdr-tooltip-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 4px; }
  .pdr-tooltip-row .dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .pdr-tooltip-row .name { color: rgba(255,255,255,0.65); font-weight: 500; }
  .pdr-tooltip-row .val { font-weight: 800; color: #fff; }

  /* ── Products Table ── */
  .pdr-table-wrap { padding: 0 36px 32px; }
  .pdr-table-card { background: #fff; border-radius: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); overflow: hidden; }
  .pdr-table-header { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }
  .pdr-table-header .th-title { font-size: 14px; font-weight: 800; color: #1a1d2e; }
  .pdr-table-header .th-count { font-size: 11px; font-weight: 600; color: #94a3b8; }
  .pdr-table { width: 100%; border-collapse: collapse; }
  .pdr-table thead tr { background: #f8fafc; }
  .pdr-table thead th { padding: 12px 18px; text-align: left; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; color: #94a3b8; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
  .pdr-table tbody tr { border-bottom: 1px solid #f8fafc; transition: background 0.15s; }
  .pdr-table tbody tr:hover { background: #f8fafc; }
  .pdr-table tbody td { padding: 13px 18px; font-size: 12px; font-weight: 500; color: #374151; vertical-align: middle; }

  /* ── Product Cards ── */
  .pdr-product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 16px; padding: 0 36px 32px; }
  .pdr-product-card { background: #fff; border-radius: 18px; overflow: hidden; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,0.06); transition: all 0.25s; display: flex; flex-direction: column; border: 1px solid #f0f2f7; }
  .pdr-product-card:hover { transform: translateY(-4px); box-shadow: 0 14px 36px rgba(0,0,0,0.12); border-color: #c7d2fe; }
  .pdr-product-card .pc-img { height: 160px; background: #f8fafc; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid #f0f2f7; position: relative; overflow: hidden; }
  .pdr-product-card .pc-img img { width: 100%; height: 100%; object-fit: contain; padding: 12px; }
  .pdr-product-card .pc-img .pc-rank { position: absolute; top: 8px; left: 8px; background: #0f172a; color: #fff; font-size: 9px; font-weight: 900; padding: 3px 8px; border-radius: 6px; letter-spacing: 0.5px; }
  .pdr-product-card .pc-body { padding: 14px; flex: 1; display: flex; flex-direction: column; gap: 8px; }
  .pdr-product-card .pc-cat { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; color: #6366f1; }
  .pdr-product-card .pc-name { font-size: 12px; font-weight: 700; color: #1a1d2e; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .pdr-product-card .pc-price { font-size: 18px; font-weight: 900; color: #1a1d2e; }
  .pdr-product-card .pc-mrp { font-size: 11px; color: #94a3b8; text-decoration: line-through; margin-left: 6px; }
  .pdr-product-card .pc-footer { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #f0f2f7; margin-top: auto; padding-top: 10px; }

  /* ── Drawer ── */
  .pdr-drawer-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.5); backdrop-filter: blur(4px); z-index: 1000; }
  .pdr-drawer { position: fixed; right: 0; top: 0; bottom: 0; width: 480px; max-width: 100vw; background: #fff; z-index: 1001; display: flex; flex-direction: column; box-shadow: -20px 0 60px rgba(0,0,0,0.15); border-left: 1px solid #f0f2f7; animation: slideIn 0.3s cubic-bezier(0.4,0,0.2,1); }
  @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
  .pdr-drawer-head { display: flex; align-items: center; justify-content: space-between; padding: 20px 22px; border-bottom: 1px solid #f0f2f7; flex-shrink: 0; }
  .pdr-drawer-body { flex: 1; overflow-y: auto; padding: 20px 22px; }
  .pdr-drawer-footer { padding: 16px 22px; border-top: 1px solid #f0f2f7; flex-shrink: 0; display: flex; gap: 10px; }

  /* ── Report Panel ── */
  .pdr-report-panel { background: #fff; border-radius: 20px; margin: 0 36px 20px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border: 1.5px solid #c7d2fe; animation: fadeDown 0.25s ease; }
  @keyframes fadeDown { from { opacity:0; transform: translateY(-8px); } to { opacity:1; transform: translateY(0); } }

  /* ── Responsive ── */
  @media (max-width: 1200px) { .pdr-charts-grid.two-col { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 900px) {
    .pdr-header { padding: 20px 18px 18px; }
    .pdr-mktplace-grid { padding: 16px 18px; grid-template-columns: repeat(2, 1fr); }
    .pdr-kpi-grid { padding: 0 18px 16px; }
    .pdr-charts-grid, .pdr-charts-grid.two-col { grid-template-columns: 1fr !important; padding: 0; }
    .pdr-chart-card.span-2 { grid-column: auto; }
    .pdr-table-wrap { padding: 0 18px 24px; }
    .pdr-product-grid { padding: 0 18px 24px; grid-template-columns: repeat(2, 1fr); }
    .pdr-nav { padding: 0 18px 12px; }
    .pdr-analytics-wrap { padding: 0 18px 24px; }
    .pdr-report-panel { margin: 0 18px 16px; }
    .pdr-controls { padding: 0 18px 16px; }
  }
  @media (max-width: 600px) {
    .pdr-mktplace-grid { grid-template-columns: repeat(2, 1fr); }
    .pdr-kpi-grid { grid-template-columns: repeat(2, 1fr); }
    .pdr-product-grid { grid-template-columns: 1fr 1fr; }
  }


  /* ── Slicers Panel ── */
  .pdr-slicers-panel {
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(12px);
    border-radius: 20px;
    margin: 0 36px 20px;
    padding: 20px 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.04);
    border: 1px solid rgba(255,255,255,0.6);
  }
  .pdr-slicers-panel .slicers-title {
    font-size: 13px;
    font-weight: 800;
    color: #1a1d2e;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .pdr-slicers-panel .reset-btn {
    font-size: 11px;
    font-weight: 700;
    color: #ef4444;
    background: transparent;
    border: none;
    cursor: pointer;
    text-decoration: underline;
  }
  .pdr-slicers-panel .slicers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
  }
  .pdr-slicers-panel .slicer-card {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .pdr-slicers-panel .slicer-card label {
    font-size: 9px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #94a3b8;
  }
  .pdr-slicers-panel .slicer-card select,
  .pdr-slicers-panel .slicer-card input {
    width: 100%;
    padding: 8px 12px;
    border-radius: 10px;
    border: 1.5px solid #e2e8f0;
    background: #fff;
    font-size: 11px;
    font-weight: 600;
    color: #374151;
    outline: none;
    transition: all 0.2s;
  }
  .pdr-slicers-panel .slicer-card select:focus,
  .pdr-slicers-panel .slicer-card input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.08);
  }
  .pdr-slicers-panel .slicer-search-input {
    display: flex;
    gap: 6px;
  }
  .pdr-slicers-panel .slicer-search-input button {
    padding: 8px 12px;
    border-radius: 10px;
    background: #1a1d2e;
    color: #fff;
    border: none;
    cursor: pointer;
    font-size: 11px;
    transition: background 0.2s;
  }
  .pdr-slicers-panel .slicer-search-input button:hover {
    background: #312b63;
  }
  .pdr-slicers-panel .price-inputs {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .pdr-slicers-panel .price-inputs span {
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8;
  }
  .pdr-slicers-panel .flags-card {
    justify-content: center;
  }
  .pdr-slicers-panel .flags-row {
    display: flex;
    gap: 12px;
    margin-top: 4px;
  }
  .pdr-slicers-panel .checkbox-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px !important;
    font-weight: 700 !important;
    color: #374151 !important;
    cursor: pointer;
    text-transform: none !important;
    letter-spacing: normal !important;
  }
  .pdr-slicers-panel .checkbox-label input {
    width: auto !important;
    cursor: pointer;
  }

  /* ── Insights Panel ── */
  .pdr-insights-panel {
    background: #fff;
    border-radius: 20px;
    padding: 22px;
    margin-bottom: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border: 1px solid #f0f2f7;
  }
  .pdr-insights-panel .insights-header {
    font-size: 12px;
    font-weight: 800;
    color: #1a1d2e;
    margin-bottom: 16px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .pdr-insights-panel .insights-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 16px;
  }
  .pdr-insights-panel .insight-card {
    display: flex;
    gap: 14px;
    padding: 16px;
    border-radius: 14px;
    border: 1.5px solid transparent;
  }
  .pdr-insights-panel .insight-info {
    background: rgba(99,102,241,0.04);
    border-color: rgba(99,102,241,0.12);
  }
  .pdr-insights-panel .insight-success {
    background: rgba(34,197,94,0.04);
    border-color: rgba(34,197,94,0.12);
  }
  .pdr-insights-panel .insight-warning {
    background: rgba(245,158,11,0.04);
    border-color: rgba(245,158,11,0.12);
  }
  .pdr-insights-panel .insight-icon {
    font-size: 20px;
    flex-shrink: 0;
  }
  .pdr-insights-panel .insight-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .pdr-insights-panel .insight-title {
    font-size: 11px;
    font-weight: 800;
    color: #1a1d2e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .pdr-insights-panel .insight-text {
    font-size: 11px;
    color: #64748b;
    font-weight: 500;
    line-height: 1.5;
  }

  /* ── Print ── */
  @media print {
    body { background: #fff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .pdr-mktplace-grid, .pdr-nav, .pdr-drawer-overlay, .pdr-drawer, .pdr-live-dot, .pdr-action-row, .pdr-product-grid, .pdr-report-panel, .pdr-slicers-panel, .reset-btn { display: none !important; }
    
    .pdr-root { background: #fff !important; min-height: auto !important; }
    .pdr-header {
      background: #0f0c29 !important;
      color: #fff !important;
      padding: 30px !important;
      border-radius: 0 !important;
      text-align: center !important;
      page-break-after: avoid !important;
    }
    .pdr-header::before { display: none !important; }
    .pdr-header-title { font-size: 26px !important; color: #fff !important; }
    .pdr-header-sub { font-size: 13px !important; color: rgba(255,255,255,0.7) !important; margin-top: 6px !important; }

    .pdr-kpi-grid {
      display: grid !important;
      grid-template-columns: repeat(3, 1fr) !important;
      gap: 12px !important;
      padding: 20px 0 !important;
      page-break-after: avoid !important;
    }
    .pdr-kpi-card {
      border: 1.5px solid #e2e8f0 !important;
      box-shadow: none !important;
      padding: 14px !important;
      border-left: 5px solid var(--accent, #6366f1) !important;
      background: #fff !important;
    }
    .pdr-kpi-card .kpi-value { font-size: 22px !important; }

    .pdr-insights-panel {
      border: 1.5px solid #e2e8f0 !important;
      box-shadow: none !important;
      padding: 20px !important;
      margin-top: 10px !important;
      page-break-after: always !important; /* Force break after KPIs + Insights */
    }
    .pdr-insights-panel .insights-grid {
      grid-template-columns: repeat(3, 1fr) !important;
    }

    .pdr-analytics-wrap { padding: 0 !important; }
    .pdr-analytics-header {
      background: #f8fafc !important;
      border: 1.5px solid #e2e8f0 !important;
      border-radius: 8px !important;
      margin-bottom: 16px !important;
      padding: 16px !important;
      box-shadow: none !important;
      page-break-inside: avoid !important;
    }
    .pdr-analytics-title { font-size: 15px !important; }
    .pdr-analytics-sub { font-size: 11px !important; }

    .pdr-charts-grid {
      display: grid !important;
      grid-template-columns: repeat(2, 1fr) !important;
      gap: 16px !important;
      padding: 0 !important;
    }
    .pdr-chart-card {
      page-break-inside: avoid !important;
      border: 1.5px solid #e2e8f0 !important;
      box-shadow: none !important;
      background: #fff !important;
      border-radius: 12px !important;
      padding: 16px !important;
    }
    .pdr-chart-card.span-2 { grid-column: 1 / -1 !important; }
    
    .pdr-table-wrap {
      display: block !important;
      padding: 20px 0 !important;
      page-break-before: always !important;
    }
    .pdr-table-card { border: 1.5px solid #e2e8f0 !important; box-shadow: none !important; }
  }
`;

/* ================================================================
   PLATFORM DESIGN TOKENS
   ================================================================ */
const PLATFORMS = {
  All: {
    label: "All Platforms", emoji: "🌐", accent: "#6366f1",
    accentA10: "rgba(99,102,241,0.08)", accentA15: "rgba(99,102,241,0.12)", accentA20: "rgba(99,102,241,0.2)",
    gradient: "linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%)",
    palette: ["#6366f1","#f59e0b","#22c55e","#06b6d4","#f43f5e","#8b5cf6","#10b981","#a855f7","#0ea5e9"],
  },
  Amazon: {
    label: "Amazon", emoji: "📦", accent: "#f59e0b",
    accentA10: "rgba(245,158,11,0.08)", accentA15: "rgba(245,158,11,0.12)", accentA20: "rgba(245,158,11,0.2)",
    gradient: "linear-gradient(135deg,#f59e0b 0%,#ef4444 100%)",
    palette: ["#f59e0b","#ef4444","#f97316","#eab308","#dc2626","#fbbf24","#fb923c","#facc15","#fca5a5"],
  },
  Blinkit: {
    label: "Blinkit", emoji: "⚡", accent: "#eab308",
    accentA10: "rgba(234,179,8,0.08)", accentA15: "rgba(234,179,8,0.12)", accentA20: "rgba(234,179,8,0.2)",
    gradient: "linear-gradient(135deg,#eab308 0%,#22c55e 100%)",
    palette: ["#eab308","#22c55e","#84cc16","#fbbf24","#4ade80","#a3e635","#facc15","#bbf7d0","#fef08a"],
  },
  BigBasket: {
    label: "BigBasket", emoji: "🛒", accent: "#22c55e",
    accentA10: "rgba(34,197,94,0.08)", accentA15: "rgba(34,197,94,0.12)", accentA20: "rgba(34,197,94,0.2)",
    gradient: "linear-gradient(135deg,#22c55e 0%,#059669 100%)",
    palette: ["#22c55e","#059669","#10b981","#16a34a","#4ade80","#6ee7b7","#86efac","#34d399","#a7f3d0"],
  },
  DMart: {
    label: "DMart", emoji: "🏪", accent: "#e02020",
    accentA10: "rgba(224,32,32,0.08)", accentA15: "rgba(224,32,32,0.12)", accentA20: "rgba(224,32,32,0.2)",
    gradient: "linear-gradient(135deg,#e02020 0%,#c0392b 100%)",
    palette: ["#e02020","#f97316","#ef4444","#dc2626","#f87171","#fca5a5","#fbbf24","#fb923c","#fcd34d"],
  },
  IndiaMart: {
    label: "IndiaMart", emoji: "🏭", accent: "#0084ff",
    accentA10: "rgba(0,132,255,0.08)", accentA15: "rgba(0,132,255,0.12)", accentA20: "rgba(0,132,255,0.2)",
    gradient: "linear-gradient(135deg,#0084ff 0%,#0060cc 100%)",
    palette: ["#0084ff","#0060cc","#3b82f6","#60a5fa","#93c5fd","#1d4ed8","#2563eb","#1e40af","#dbeafe"],
  },
  Zepto: {
    label: "Zepto", emoji: "🛒", accent: "#db2777",
    accentA10: "rgba(219,39,119,0.08)", accentA15: "rgba(219,39,119,0.12)", accentA20: "rgba(219,39,119,0.2)",
    gradient: "linear-gradient(135deg,#db2777 0%,#701a75 100%)",
    palette: ["#db2777","#701a75","#a855f7","#9333ea","#ec4899","#ef4444","#f43f5e","#c084fc","#fbcfe8"],
  },
};

/* ================================================================
   TOOLTIP COMPONENT
   ================================================================ */
const ChartTooltip = ({ active, payload, label, prefix = "", suffix = "" }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="pdr-tooltip">
      {label && <p className="pdr-tooltip-label">{label}</p>}
      {payload.map((item, i) => (
        <div className="pdr-tooltip-row" key={i}>
          <span className="dot" style={{ background: item.color || item.fill }} />
          <span className="name">{item.name}</span>
          <span className="val">{prefix}{typeof item.value === "number" ? item.value.toLocaleString("en-IN") : item.value}{suffix}</span>
        </div>
      ))}
    </div>
  );
};

const Stars = ({ val }) => {
  if (!val) return <span style={{ color: "#94a3b8", fontSize: 11 }}>—</span>;
  return (
    <div className="pdr-stars">
      {[1,2,3,4,5].map(i => (
        <span key={i} className="pdr-star" style={{ color: i <= Math.round(val) ? "#f59e0b" : "#e2e8f0" }}>★</span>
      ))}
      <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginLeft: 4 }}>{Number(val).toFixed(1)}</span>
    </div>
  );
};

const Badge = ({ label, cls = "badge-gray" }) => (
  <span className={`pdr-btn ${cls}`} style={{ padding: "3px 9px", fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.5px", borderRadius: 99, cursor: "default" }}>
    {label}
  </span>
);

/* ================================================================
   CHART CARD WRAPPER — auto-hides if no data
   ================================================================ */
const ChartCard = ({ title, sub, badge, badgeCls = "badge-purple", span2 = false, hasData, children }) => {
  if (!hasData) return null;
  return (
    <div className={`pdr-chart-card${span2 ? " span-2" : ""}`}>
      <div className="cc-header">
        <div>
          <div className="cc-title">{title}</div>
          <div className="cc-sub">{sub}</div>
        </div>
        <span className={`cc-badge ${badgeCls}`}>{badge}</span>
      </div>
      {children}
    </div>
  );
};

/* ================================================================
   MAIN COMPONENT
   ================================================================ */
export default function ProductDataReport() {
  const [platform, setPlatform] = useState(() => localStorage.getItem("pdr_platform") || "All");
  const [activeTab, setActiveTab] = useState("analytics");
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);

  const [summary, setSummary] = useState(null);
  const [roster, setRoster] = useState([]);
  const [products, setProducts] = useState([]);
  const [chartData, setChartData] = useState({});
  const [allCatMapping, setAllCatMapping] = useState([]);
  const [mappedCats, setMappedCats] = useState([]);
  const [unmappedCats, setUnmappedCats] = useState([]);
  const [unmappedProds, setUnmappedProds] = useState([]);
  const [mappingData, setMappingData] = useState([]);
  const [mappingReport, setMappingReport] = useState({});
  const [csvExporting, setCsvExporting] = useState(false);
  const [marketplaceCategories, setMarketplaceCategories] = useState([]);

  // Load platform-specific category options for the dropdown
  useEffect(() => {
    const mp = platform === "All" ? "all" : platform.toLowerCase();
    let endpoint = `/product-report/mapping/${mp}`;
    if (mp === "all") {
      endpoint = `/product-report/mapping/all-categories?marketplace=all`;
    }
    api.get(endpoint)
      .then(r => {
        const cats = [...new Set((r.data?.data || []).map(x => x.category_name))].filter(Boolean).sort();
        setMarketplaceCategories(cats);
      })
      .catch(() => setMarketplaceCategories([]));
  }, [platform]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefreshMsg, setAutoRefreshMsg] = useState("");

  // Slicer / filter state
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [catFilter, setCatFilter] = useState("All Categories");
  const [brandFilter, setBrandFilter] = useState("All Brands");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minRating, setMinRating] = useState(0);
  const [stockFilter, setStockFilter] = useState("All");
  const [bestSellerOnly, setBestSellerOnly] = useState(false);
  const [primeOnly, setPrimeOnly] = useState(false);

  // Reset filters when platform changes
  useEffect(() => {
    setSearch("");
    setAppliedSearch("");
    setCatFilter("All Categories");
    setBrandFilter("All Brands");
    setMinPrice("");
    setMaxPrice("");
    setMinRating(0);
    setStockFilter("All");
    setBestSellerOnly(false);
    setPrimeOnly(false);
  }, [platform]);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerProduct, setDrawerProduct] = useState(null);
  const [drawerLoading, setDrawerLoading] = useState(false);

  const [reportOpen, setReportOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genProgress, setGenProgress] = useState(0);

  const pt = PLATFORMS[platform] || PLATFORMS.All;

  useEffect(() => { localStorage.setItem("pdr_platform", platform); }, [platform]);

  /* ── Fetch chart data from server (full dataset, no sampling) ── */
  const fetchChartData = useCallback(async () => {
    try {
      const mp = platform === "All" ? "all" : platform.toLowerCase();
      const r = await api.get(`/product-report/chart-data?marketplace=${mp}`);
      setChartData(r.data?.data || {});
    } catch (e) { console.warn("chart-data fetch error", e); }
  }, [platform]);

  /* ── Fetch all-categories mapping ── */
  const fetchAllCatMapping = useCallback(async (search = "") => {
    try {
      const mp = platform === "All" ? "all" : platform.toLowerCase();
      const r = await api.get(`/product-report/mapping/all-categories?marketplace=${mp}&search=${encodeURIComponent(search)}`);
      const rawData = r.data?.data || [];
      setAllCatMapping(rawData);
      // Map backend fields to frontend expected fields
      const formatted = rawData.map(c => ({
        id: c.id,
        marketplace_name: c.marketplace,
        category_level: c.level,
        category_name: c.category_name,
        subcategory_name: c.sub_category,
        category_path: c.path,
      }));
      setMappedCats(formatted);
    } catch (e) { console.warn("all-categories fetch error", e); }
  }, [platform]);

  /* ── Fetch all data ── */
  const fetchAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const mp = platform === "All" ? "all" : platform;
      // Build server-side filter params for top-products
      const filterParams = new URLSearchParams({ marketplace: mp, limit: 1000 });
      if (appliedSearch) filterParams.append("search", appliedSearch);
      if (catFilter && catFilter !== "All Categories") filterParams.append("category", catFilter);

      const [sumR, rosterR, prodR] = await Promise.all([
        api.get(`/product-report/summary?marketplace=${mp}`),
        api.get(`/product-report/roster`),
        api.get(`/product-report/top-products?${filterParams}`),
      ]);
      setSummary(sumR.data?.data || null);
      setRoster(rosterR.data?.data || []);
      setProducts(prodR.data?.data || []);
      setLastRefreshedAt(new Date());

      // Also fetch chart data and mapping in background
      fetchChartData();

      // If marketplace has no data, auto-trigger backend refresh
      const sum = sumR.data?.data;
      if (sum && sum.status_badge === "Pending Data Upload" && mp !== "all") {
        setAutoRefreshMsg(`Syncing ${platform} data from DB…`);
        try {
          await api.post(`/product-report/refresh`);
          // Re-fetch after refresh
          const [s2, r2, p2] = await Promise.all([
            api.get(`/product-report/summary?marketplace=${mp}`),
            api.get(`/product-report/roster`),
            api.get(`/product-report/top-products?${filterParams}`),
          ]);
          setSummary(s2.data?.data || null);
          setRoster(r2.data?.data || []);
          setProducts(p2.data?.data || []);
        } catch (refreshErr) {
          console.warn("Auto-refresh failed:", refreshErr);
        } finally {
          setAutoRefreshMsg("");
        }
      }
    } catch (e) {
      console.error("PDR fetch error", e);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [platform, appliedSearch, catFilter, fetchChartData]);

  useEffect(() => { fetchAll(); }, [platform, appliedSearch, catFilter]);

  // Real-time: auto-refresh every 3 minutes
  useEffect(() => {
    const interval = setInterval(() => { fetchAll(true); }, 3 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // Re-fetch when filters are applied (e.g. search keyword)
  const applyFilters = useCallback(() => { fetchAll(); }, [fetchAll]);

  /* ── Fetch tab-specific data ── */
  useEffect(() => {
    const mp = platform === "All" ? "all" : platform;
    const sq = appliedSearch ? encodeURIComponent(appliedSearch) : "";
    if (activeTab === "mapped") {
      // Fetch per-marketplace mapping report from actual DB mapping tables
      const mpParam = platform === "All" ? "all" : platform.toLowerCase();
      api.get(`/product-report/mapping-report?marketplace=${mpParam}`)
        .then(r => setMappingReport(r.data?.data || {}))
        .catch(() => {});
      fetchAllCatMapping(appliedSearch);
    } else if (activeTab === "unmapped") {
      api.get(`/product-report/unmapped-categories?marketplace=${mp}&search=${sq}`).then(r => setUnmappedCats(r.data?.data || [])).catch(() => {});
    } else if (activeTab === "pending") {
      api.get(`/product-report/unmapped-products?marketplace=${mp}&search=${sq}`).then(r => setUnmappedProds(r.data?.data || [])).catch(() => {});
    }
  }, [activeTab, platform, appliedSearch, fetchAllCatMapping]);

  /* ── Refresh ── */
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const mp = platform === "All" ? "all" : platform;
      await api.post(`/product-report/refresh?marketplace=${mp}`);
      await fetchAll();
    } catch (e) { console.error(e); }
    finally { setRefreshing(false); }
  };

  /* ── Drawer ── */
  const openDrawer = async (prod) => {
    setDrawerOpen(true); setDrawerLoading(true); setDrawerProduct(null);
    try {
      let r;
      if (prod.marketplace_name?.toLowerCase() === "amazon" && prod.asin) {
        r = await api.get(`/product-report/products/amazon/${prod.asin}`);
      } else {
        r = await api.get(`/product-report/products/${prod.marketplace_name}/${prod.product_id}`);
      }
      setDrawerProduct(r.data?.status === "success" ? r.data.data : prod);
    } catch { setDrawerProduct(prod); }
    finally { setDrawerLoading(false); }
  };

  /* ── CSV Export — fetches ALL records from backend (no page limit) ── */
  const exportCSV = async () => {
    setCsvExporting(true);
    try {
      const mp = platform === "All" ? "all" : platform;
      const url = `/api/product-report/export-csv?marketplace=${encodeURIComponent(mp)}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error("Export failed");
      const blob = await response.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `HBD_${platform}_Full_Export_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      alert("CSV export failed: " + e.message);
    } finally {
      setCsvExporting(false);
    }
  };

  const simulateGenerate = () => {
    setGenerating(true); setGenProgress(0);
    const steps = [15,35,60,80,95,100];
    steps.forEach((p, i) => setTimeout(() => {
      setGenProgress(p);
      if (p === 100) { exportCSV(); setTimeout(() => { setGenerating(false); setReportOpen(false); }, 600); }
    }, (i + 1) * 350));
  };

  /* ================================================================
     HELPER: safe numeric parser
     ================================================================ */
  const safeNum = (v) => {
    const n = parseFloat(v);
    return isNaN(n) ? 0 : n;
  };

  /* ── Filtered products ── */
  const filteredProducts = products.filter(p => {
    // Search filter
    const q = appliedSearch.toLowerCase();
    const matchSearch = !q || (p.product_name || "").toLowerCase().includes(q) || (p.brand || "").toLowerCase().includes(q) || (p.asin || "").toLowerCase().includes(q);
    
    // Category filter
    const matchCat = catFilter === "All Categories" || p.category_name === catFilter;
    
    // Brand filter
    const matchBrand = brandFilter === "All Brands" || p.brand === brandFilter;
    
    // Price range filter
    const priceVal = safeNum(p.price);
    const minP = minPrice === "" ? -Infinity : safeNum(minPrice);
    const maxP = maxPrice === "" ? Infinity : safeNum(maxPrice);
    const matchPrice = priceVal >= minP && priceVal <= maxP;
    
    // Star Rating filter
    const matchRating = safeNum(p.stars) >= minRating;
    
    // Stock Availability filter
    const av = String(p.availability || "").toLowerCase();
    const isOut = av.includes("out") || av === "0" || av === "false";
    const matchStock = stockFilter === "All" || 
                       (stockFilter === "In Stock" && !isOut) || 
                       (stockFilter === "Out of Stock" && isOut);
                       
    // Best Seller filter
    const matchBestSeller = !bestSellerOnly || p.is_best_seller;
    
    // Prime filter
    const matchPrime = !primeOnly || p.is_prime;
    
    return matchSearch && matchCat && matchBrand && matchPrice && matchRating && matchStock && matchBestSeller && matchPrime;
  });

  const uniqueCategories = ["All Categories", ...Array.from(new Set(products.map(p => p.category_name).filter(Boolean))).sort()];
  const uniqueBrands = ["All Brands", ...Array.from(new Set(products.map(p => p.brand).filter(Boolean))).sort()];

  const dropdownCategories = useMemo(() => {
    return ["All Categories", ...marketplaceCategories];
  }, [marketplaceCategories]);

  const getRosterStats = (name) => roster.find(r => r.marketplace_name?.toLowerCase() === name.toLowerCase());

  const isPending = summary?.status_badge === "Pending Data Upload";

  /* ================================================================
     KEY INSIGHTS CALCULATIONS
     ================================================================ */
  const insights = (() => {
    const list = [];
    if (filteredProducts.length === 0) return list;

    // 1. Dominant Category
    const catCounts = {};
    filteredProducts.forEach(p => { const c = p.category_name || "Other"; catCounts[c] = (catCounts[c] || 0) + 1; });
    const topCat = Object.entries(catCounts).sort((a,b) => b[1] - a[1])[0];
    if (topCat) {
      const pct = ((topCat[1] / filteredProducts.length) * 100).toFixed(0);
      list.push({
        type: "info",
        title: "Category Dominant",
        text: `"${topCat[0]}" holds the highest share, making up ${pct}% (${topCat[1]} items) of this catalog selection.`,
        icon: "📁"
      });
    }

    // 2. Average Discount
    let totalDiscount = 0, discountCount = 0;
    filteredProducts.forEach(p => {
      const price = safeNum(p.price);
      const listPrice = safeNum(p.list_price);
      if (listPrice > 0 && price > 0 && listPrice > price) {
        totalDiscount += ((listPrice - price) / listPrice) * 100;
        discountCount++;
      }
    });
    if (discountCount > 0) {
      const avgDisc = (totalDiscount / discountCount).toFixed(1);
      list.push({
        type: "success",
        title: "Discount Health",
        text: `Average discount across active items is ${avgDisc}%, offering a strong value proposition.`,
        icon: "🏷️"
      });
    }

    // 3. Stock warning
    let outCount = 0;
    filteredProducts.forEach(p => {
      const av = String(p.availability || "").toLowerCase();
      if (av.includes("out") || av === "0" || av === "false") outCount++;
    });
    const outRate = ((outCount / filteredProducts.length) * 100);
    if (outRate > 15) {
      list.push({
        type: "warning",
        title: "Stock Alert",
        text: `${outRate.toFixed(1)}% of your products are out-of-stock. Restock immediately to maintain sales velocity.`,
        icon: "⚠️"
      });
    } else {
      list.push({
        type: "success",
        title: "Inventory Status",
        text: `Optimal stock levels. ${(100 - outRate).toFixed(1)}% of active products are in-stock and purchasable.`,
        icon: "✅"
      });
    }

    // 4. Star Rating
    let ratedCount = 0, highRatedCount = 0;
    filteredProducts.forEach(p => {
      const stars = safeNum(p.stars);
      if (stars > 0) {
        ratedCount++;
        if (stars >= 4.0) highRatedCount++;
      }
    });
    if (ratedCount > 0) {
      const highRatedPct = ((highRatedCount / ratedCount) * 100).toFixed(0);
      list.push({
        type: "success",
        title: "Quality Benchmarking",
        text: `${highRatedPct}% of rated products score above 4.0 ★, indicating high customer satisfaction.`,
        icon: "★"
      });
    }

    // 5. Best Seller Presence
    const bestSellers = filteredProducts.filter(p => p.is_best_seller).length;
    if (bestSellers > 0) {
      list.push({
        type: "info",
        title: "Demand Analytics",
        text: `Active catalog contains ${bestSellers} items tagged as Best Sellers, indicating top tier traction.`,
        icon: "🔥"
      });
    }

    return list.slice(0, 3);
  })();


  /* ================================================================
     CHART DATA COMPILERS
     (Only compile for the selected platform — no cross-contamination)
     ================================================================ */

  // ── 1. Category-wise Product Count (All platforms)
  const categoryBarData = (() => {
    const g = {};
    filteredProducts.forEach(p => { const c = p.category_name || "Other"; g[c] = (g[c] || 0) + 1; });
    const sorted = Object.entries(g).sort((a, b) => b[1] - a[1]);
    const top8 = sorted.slice(0, 8).map(([name, value]) => ({ name: name.length > 14 ? name.slice(0,14)+"…" : name, value }));
    if (sorted.length > 8) top8.push({ name: "Others", value: sorted.slice(8).reduce((s, [, v]) => s + v, 0) });
    return top8.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }));
  })();

  // ── 2. Sub-Category Distribution (BigBasket, Amazon)
  const subCategoryData = (() => {
    const g = {};
    filteredProducts.forEach(p => { const c = p.sub_category_name || "Other"; g[c] = (g[c] || 0) + 1; });
    const sorted = Object.entries(g).sort((a, b) => b[1] - a[1]);
    const top7 = sorted.slice(0, 7).map(([name, value]) => ({ name: name.length > 18 ? name.slice(0,18)+"…" : name, value }));
    if (sorted.length > 7) top7.push({ name: "Others", value: sorted.slice(7).reduce((s, [, v]) => s + v, 0) });
    return top7.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }));
  })();

  // ── 3. Brand-wise Product Analysis (All platforms)
  const brandBarData = (() => {
    const g = {};
    filteredProducts.forEach(p => { if (p.brand) g[p.brand] = (g[p.brand] || 0) + 1; });
    return Object.entries(g).sort((a, b) => b[1] - a[1]).slice(0, 10)
      .map(([name, count]) => ({ name: name.length > 16 ? name.slice(0,16)+"…" : name, count }));
  })();

  // ── 4. Price Range Segmentation – histogram (All platforms)
  const priceRangeData = (() => {
    const buckets = [
      { name: "₹0–100", min: 0, max: 100, count: 0 },
      { name: "₹100–300", min: 100, max: 300, count: 0 },
      { name: "₹300–500", min: 300, max: 500, count: 0 },
      { name: "₹500–1K", min: 500, max: 1000, count: 0 },
      { name: "₹1K–3K", min: 1000, max: 3000, count: 0 },
      { name: "₹3K–5K", min: 3000, max: 5000, count: 0 },
      { name: "₹5K+", min: 5000, max: Infinity, count: 0 },
    ];
    filteredProducts.forEach(p => {
      const pr = safeNum(p.price);
      if (pr <= 0) return;
      const b = buckets.find(bk => pr >= bk.min && pr < bk.max);
      if (b) b.count++;
    });
    return buckets.filter(b => b.count > 0);
  })();

  // ── 5. Sale Price vs Market Price / MRP (Blinkit, BigBasket, Amazon)
  const saleMrpData = (() => {
    const g = {};
    filteredProducts.forEach(p => {
      const c = p.category_name || "Other";
      if (!g[c]) g[c] = { sumPrice: 0, sumList: 0, count: 0 };
      const price = safeNum(p.price);
      const list = safeNum(p.list_price);
      if (price > 0) { g[c].sumPrice += price; g[c].sumList += list || price; g[c].count++; }
    });
    return Object.entries(g)
      .filter(([, d]) => d.count > 0)
      .map(([name, d]) => ({
        name: name.length > 12 ? name.slice(0, 12) + "…" : name,
        "Sale Price": parseFloat((d.sumPrice / d.count).toFixed(0)),
        "Market Price": parseFloat((d.sumList / d.count).toFixed(0)),
      }))
      .sort((a, b) => b["Sale Price"] - a["Sale Price"])
      .slice(0, 8);
  })();

  // ── 6. Discount Analysis by Category (Blinkit – has numeric discount, Amazon, BigBasket)
  const discountData = (() => {
    const g = {};
    filteredProducts.forEach(p => {
      const c = p.category_name || "Other";
      const price = safeNum(p.price);
      const list = safeNum(p.list_price);
      let disc = 0;
      if (list > 0 && price > 0 && list > price) disc = ((list - price) / list) * 100;
      if (disc > 0) {
        if (!g[c]) g[c] = { sum: 0, count: 0 };
        g[c].sum += disc; g[c].count++;
      }
    });
    return Object.entries(g)
      .filter(([, d]) => d.count >= 2)
      .map(([name, d]) => ({
        name: name.length > 14 ? name.slice(0, 14) + "…" : name,
        "Avg Discount %": parseFloat((d.sum / d.count).toFixed(1)),
      }))
      .sort((a, b) => b["Avg Discount %"] - a["Avg Discount %"])
      .slice(0, 8);
  })();

  // ── 7. Stock Availability Pie (Blinkit – boolean, Amazon – string)
  const stockPieData = (() => {
    let inStock = 0, outOfStock = 0;
    filteredProducts.forEach(p => {
      const av = String(p.availability || "").toLowerCase();
      if (av.includes("out") || av === "0" || av === "false") outOfStock++;
      else if (av.includes("in") || av === "1" || av === "true") inStock++;
      else inStock++; // BigBasket always In Stock
    });
    if (inStock === 0 && outOfStock === 0 && summary) {
      inStock = summary.available_products || 0;
      outOfStock = summary.out_of_stock_products || 0;
    }
    return [
      { name: "In Stock", value: inStock, fill: "#22c55e" },
      { name: "Out of Stock", value: outOfStock, fill: "#f43f5e" },
    ].filter(d => d.value > 0);
  })();

  // ── 8. Rating Distribution Histogram (Amazon, BigBasket only)
  const ratingHistData = (() => {
    const buckets = [
      { name: "1–2 ★", min: 1, max: 2, count: 0 },
      { name: "2–3 ★", min: 2, max: 3, count: 0 },
      { name: "3–4 ★", min: 3, max: 4, count: 0 },
      { name: "4–4.5 ★", min: 4, max: 4.5, count: 0 },
      { name: "4.5–5 ★", min: 4.5, max: 5.01, count: 0 },
    ];
    filteredProducts.forEach(p => {
      const s = safeNum(p.stars);
      if (s <= 0) return;
      const b = buckets.find(bk => s >= bk.min && s < bk.max);
      if (b) b.count++;
    });
    return buckets.filter(b => b.count > 0);
  })();

  // ── 9. Top Rated Products (Amazon, BigBasket)
  const topRatedData = filteredProducts
    .filter(p => safeNum(p.stars) >= 4)
    .sort((a, b) => safeNum(b.stars) - safeNum(a.stars) || safeNum(b.reviews) - safeNum(a.reviews))
    .slice(0, 10)
    .map(p => ({
      name: (p.product_name || "").slice(0, 14) + "…",
      Rating: safeNum(p.stars),
    }));

  // ── 10. Reviews by Category (Amazon only)
  const reviewsByCatData = (() => {
    const g = {};
    filteredProducts.forEach(p => {
      if (!p.reviews || p.reviews === 0) return;
      const c = p.category_name || "Other";
      g[c] = (g[c] || 0) + safeNum(p.reviews);
    });
    return Object.entries(g)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, reviews]) => ({
        name: name.length > 14 ? name.slice(0, 14) + "…" : name,
        Reviews: reviews,
      }));
  })();

  // ── 11. Best Sellers by Category Pie (Amazon only)
  const bestSellerData = (() => {
    const g = {};
    filteredProducts.forEach(p => {
      if (!p.is_best_seller) return;
      const c = p.category_name || "Other";
      g[c] = (g[c] || 0) + 1;
    });
    const sorted = Object.entries(g).sort((a, b) => b[1] - a[1]);
    const top7 = sorted.slice(0, 7).map(([name, value]) => ({ name: name.slice(0, 16), value }));
    if (sorted.length > 7) top7.push({ name: "Others", value: sorted.slice(7).reduce((s, [, v]) => s + v, 0) });
    return top7.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }));
  })();

  // ── 12. BigBasket Product Type Breakdown (BigBasket only — `type` field via sub_category_name)
  const productTypeData = (() => {
    const g = {};
    filteredProducts.forEach(p => {
      const t = p.sub_category_name || p.category_name || "Other";
      g[t] = (g[t] || 0) + 1;
    });
    const sorted = Object.entries(g).sort((a, b) => b[1] - a[1]);
    const top7 = sorted.slice(0, 7).map(([name, value]) => ({ name: name.slice(0, 18), value }));
    if (sorted.length > 7) top7.push({ name: "Others", value: sorted.slice(7).reduce((s, [, v]) => s + v, 0) });
    return top7.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }));
  })();

  // ── 13. Platform Comparison (All only) — from roster
  const platformCompData = roster
    .filter(r => r.total_products > 0)
    .map(r => ({
      name: r.marketplace_name,
      Products: r.total_products,
      Brands: r.total_brands,
      Categories: r.total_categories,
    }));

  // ── 14. Avg Price per Platform (All only)
  const avgPriceCompData = roster
    .filter(r => r.total_products > 0 && r.avg_selling_price > 0)
    .map(r => ({
      name: r.marketplace_name,
      "Avg Price (₹)": parseFloat(Number(r.avg_selling_price).toFixed(0)),
      fill: PLATFORMS[r.marketplace_name]?.accent || "#6366f1",
    }));

  // ── 15. Stock Availability Comparison (All only)
  const stockCompData = roster
    .filter(r => r.total_products > 0)
    .map(r => ({
      name: r.marketplace_name,
      "In Stock": r.available_products,
      "Out of Stock": r.out_of_stock_products,
    }));

  // ── 16. Category Coverage Ratio (All only)
  const catCoverageData = roster
    .filter(r => r.total_categories > 0)
    .map(r => ({
      name: r.marketplace_name,
      Mapped: r.completed_categories,
      Pending: r.pending_categories,
    }));

  // ── 17. Top 10 Cross-Platform Category Distribution (All only)
  const crossCatData = (() => {
    const g = {};
    products.forEach(p => {
      const c = p.category_name || "Other";
      const mp = p.marketplace_name || "Unknown";
      if (!g[c]) g[c] = {};
      g[c][mp] = (g[c][mp] || 0) + 1;
    });
    return Object.entries(g)
      .map(([cat, mp]) => ({ cat, total: Object.values(mp).reduce((s, v) => s + v, 0), ...mp }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 8)
      .map(d => ({ ...d, name: d.cat.length > 14 ? d.cat.slice(0, 14) + "…" : d.cat }));
  })();

  const mpNames = [...new Set(products.map(p => p.marketplace_name).filter(Boolean))];

  /* ================================================================
     RENDER HELPERS
     ================================================================ */
  const TICK_STYLE = { fill: "#94a3b8", fontSize: 10, fontWeight: 600 };

  const renderAxisTick = ({ x, y, payload }) => (
    <text x={x} y={y + 4} textAnchor="end" fill="#94a3b8" fontSize={9} fontWeight={600}>
      {payload.value}
    </text>
  );

  /* ================================================================
     MAIN RENDER
     ================================================================ */
  return (
    <div className="pdr-root">
      <style dangerouslySetInnerHTML={{ __html: GLOBAL_CSS }} />

      {/* ── HEADER ── */}
      <div className="pdr-header">
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div className="pdr-live-dot"><span /> 📦 Local DB Analytics · {Object.keys(PLATFORMS).length - 1} Marketplaces</div>
            <h1 className="pdr-header-title">Product Intelligence Dashboard</h1>
            <p className="pdr-header-sub">
              Real-time catalog analytics · {platform === "All" ? "All Platforms" : platform}
              {lastRefreshedAt && (
                <span style={{ marginLeft: 8, fontSize: 10, opacity: 0.7 }}>
                  · Last refreshed: {lastRefreshedAt.toLocaleTimeString("en-IN")}
                </span>
              )}
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            {autoRefreshMsg && (
              <div style={{ background: "rgba(255,255,255,0.15)", border: "1px solid rgba(255,255,255,0.25)", borderRadius: 10, padding: "6px 14px", fontSize: 11, fontWeight: 700, color: "#fff", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "#22c55e", animation: "pulse 1s ease-in-out infinite" }} />
                {autoRefreshMsg}
              </div>
            )}
            <button className="pdr-btn pdr-btn-ghost" onClick={() => setReportOpen(v => !v)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 15V3M8 11l4 4 4-4M5 21h14"/></svg>
              Export Report
            </button>
            <button
              className={`pdr-btn-icon ${refreshing ? "spinning" : ""}`}
              onClick={handleRefresh}
              style={{ background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.2)" }}
              title="Refresh all marketplace data from DB"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10M23 14l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
            </button>
          </div>
        </div>
      </div>

      {/* ── REPORT PANEL ── */}
      {reportOpen && (
        <div className="pdr-report-panel">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: "#1a1d2e" }}>✨ Export Report</div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>Download filtered catalog data or print charts as PDF</div>
            </div>
            <button className="pdr-btn-icon" onClick={() => setReportOpen(false)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {generating ? (
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 8 }}>
                  <span>Compiling CSV…</span><span style={{ color: "#6366f1" }}>{genProgress}%</span>
                </div>
                <div style={{ background: "#f1f5f9", borderRadius: 99, height: 6, overflow: "hidden" }}>
                  <div style={{ height: "100%", borderRadius: 99, background: "linear-gradient(90deg,#6366f1,#8b5cf6)", width: `${genProgress}%`, transition: "width 0.35s" }} />
                </div>
              </div>
            ) : (
              <>
                <button className="pdr-btn pdr-btn-primary" onClick={simulateGenerate} style={{ flex: 1, justifyContent: "center" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 15V3M8 11l4 4 4-4M5 21h14"/></svg>
                  Download CSV
                </button>
                <button className="pdr-btn pdr-btn-green" onClick={() => window.print()} style={{ flex: 1, justifyContent: "center" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                  Print / PDF Charts
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── MARKETPLACE SELECTOR ── */}
      <div className="pdr-mktplace-grid">
        {Object.entries(PLATFORMS).map(([key, p]) => {
          const rs = key === "All" ? null : getRosterStats(key);
          const cnt = key === "All"
            ? roster.reduce((a, r) => a + (r.total_products || 0), 0)
            : (rs?.total_products || 0);
          const avgP = key === "All"
            ? (roster.reduce((a, r) => a + (r.avg_selling_price || 0), 0) / Math.max(roster.length, 1))
            : (rs?.avg_selling_price || 0);
          return (
            <div
              key={key}
              className={`pdr-mktplace-card ${platform === key ? "active" : ""}`}
              style={{ "--accent": p.accent, "--accent-a10": p.accentA10, "--accent-a15": p.accentA15, "--accent-a20": p.accentA20 }}
              onClick={() => { setPlatform(key); setActiveTab("analytics"); }}
            >
              <Badge label={cnt > 0 || key === "All" ? "Active" : "Offline"} cls={cnt > 0 || key === "All" ? "badge-green" : "badge-gray"} />
              <div className="mc-icon" style={{ background: p.accentA10, borderColor: p.accentA20 }}>{p.emoji}</div>
              <div className="mc-name">{p.label}</div>
              <div className="mc-count">{cnt > 0 ? cnt.toLocaleString("en-IN") : "—"}</div>
              <div className="mc-avg">{avgP > 0 ? `Avg ₹${Number(avgP).toFixed(0)}` : "No data"}</div>
            </div>
          );
        })}
      </div>

      {/* ── KPI SUMMARY ── */}
      {loading ? (
        <div className="pdr-spinner-wrap"><div className="pdr-spinner" /><span className="pdr-spinner-text">Loading analytics…</span></div>
      ) : summary && !isPending ? (
        <div className="pdr-kpi-grid">
          {[
            { label: "Total Products", value: Number(summary.total_products || 0).toLocaleString("en-IN"), sub: `${Number(summary.mapped_products || 0).toLocaleString()} mapped`, icon: "📊", accent: pt.accent },
            { label: "Avg Selling Price", value: `₹${Number(summary.avg_selling_price || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`, sub: `${Number(summary.total_brands || 0)} brands`, icon: "💰", accent: "#f59e0b" },
            { label: "In Stock Rate", value: `${summary.total_products > 0 ? ((summary.available_products / summary.total_products) * 100).toFixed(1) : 0}%`, sub: `${Number(summary.available_products || 0).toLocaleString()} available`, icon: "✅", accent: "#22c55e" },
            { label: "Categories", value: Number(summary.total_categories || 0).toLocaleString(), sub: `${summary.completed_categories} mapped · ${summary.pending_categories} pending`, icon: "📁", accent: "#6366f1" },
            { label: "Mapped Products", value: Number(summary.mapped_products || 0).toLocaleString("en-IN"), sub: `${summary.unmapped_products || 0} unmapped`, icon: "🔗", accent: "#8b5cf6" },
            { label: "Out of Stock", value: Number(summary.out_of_stock_products || 0).toLocaleString("en-IN"), sub: `${summary.total_products > 0 ? ((summary.out_of_stock_products / summary.total_products) * 100).toFixed(1) : 0}% of catalog`, icon: "⚠️", accent: "#f43f5e" },
          ].map((k, i) => (
            <div key={i} className="pdr-kpi-card" style={{ "--accent": k.accent }}>
              <div className="kpi-icon">{k.icon}</div>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-sub">{k.sub}</div>
            </div>
          ))}
        </div>
      ) : isPending ? (
        <div style={{ padding: "0 36px 24px" }}>
          <div style={{ background: "#fff", borderRadius: 20, padding: "48px 36px", textAlign: "center", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#1a1d2e" }}>No Data for {platform}</div>
            <div style={{ fontSize: 13, color: "#64748b", marginTop: 8, marginBottom: 20 }}>Click Refresh to sync data from the database.</div>
            <button className="pdr-btn pdr-btn-primary" onClick={handleRefresh}>Sync Now</button>
          </div>
        </div>
      ) : null}

      {/* ── POWERBI SLICERS PANEL ── */}
      {!loading && !isPending && (
        <div className="pdr-slicers-panel">
          <div className="slicers-title">
            <span>🎛️ Interactive Slicers & Filters (PowerBI style)</span>
            <button className="reset-btn" onClick={() => {
              setSearch("");
              setAppliedSearch("");
              setCatFilter("All Categories");
              setBrandFilter("All Brands");
              setMinPrice("");
              setMaxPrice("");
              setMinRating(0);
              setStockFilter("All");
              setBestSellerOnly(false);
              setPrimeOnly(false);
              setTimeout(applyFilters, 50);
            }}>Reset Slicers</button>
          </div>
          <div className="slicers-grid">
            <div className="slicer-card">
              <label>Search Catalog</label>
              <div className="slicer-search-input">
                <input 
                  value={search} 
                  onChange={e => setSearch(e.target.value)} 
                  placeholder="Keyword, ASIN or brand..." 
                  onKeyDown={e => { if (e.key === "Enter") { setAppliedSearch(search); setTimeout(applyFilters, 0); } }}
                />
                <button onClick={() => { setAppliedSearch(search); setTimeout(applyFilters, 0); }}>Filter</button>
              </div>
            </div>

            <div className="slicer-card">
              <label>Category Name</label>
              <select value={catFilter} onChange={e => setCatFilter(e.target.value)}>
                {dropdownCategories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div className="slicer-card">
              <label>Brand</label>
              <select value={brandFilter} onChange={e => setBrandFilter(e.target.value)}>
                {uniqueBrands.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>

            <div className="slicer-card">
              <label>Price Range</label>
              <div className="price-inputs">
                <input type="number" placeholder="Min" value={minPrice} onChange={e => setMinPrice(e.target.value)} style={{ padding: "8px 6px" }} />
                <span>-</span>
                <input type="number" placeholder="Max" value={maxPrice} onChange={e => setMaxPrice(e.target.value)} style={{ padding: "8px 6px" }} />
              </div>
            </div>

            <div className="slicer-card">
              <label>Minimum Rating</label>
              <select value={minRating} onChange={e => setMinRating(Number(e.target.value))}>
                <option value={0}>All Ratings</option>
                <option value={4.5}>4.5 ★ & above</option>
                <option value={4.0}>4.0 ★ & above</option>
                <option value={3.5}>3.5 ★ & above</option>
                <option value={3.0}>3.0 ★ & above</option>
              </select>
            </div>

            <div className="slicer-card">
              <label>Availability</label>
              <select value={stockFilter} onChange={e => setStockFilter(e.target.value)}>
                <option value="All">All Items</option>
                <option value="In Stock">In Stock</option>
                <option value="Out of Stock">Out of Stock</option>
              </select>
            </div>

            <div className="slicer-card flags-card">
              <label>Segment Badges</label>
              <div className="flags-row">
                <label className="checkbox-label">
                  <input type="checkbox" checked={bestSellerOnly} onChange={e => setBestSellerOnly(e.target.checked)} />
                  Best Seller
                </label>
                {platform === "Amazon" && (
                  <label className="checkbox-label">
                    <input type="checkbox" checked={primeOnly} onChange={e => setPrimeOnly(e.target.checked)} />
                    Prime
                  </label>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── NAV TABS ── */}
      {!loading && !isPending && (
        <>
          <div className="pdr-nav" style={{ padding: "0 36px 0" }}>
            {[
              { id: "analytics", icon: "📈", label: "Analytics & Charts", count: null },
              { id: "products", icon: "🛍️", label: "Top Products", count: filteredProducts.length },
              { id: "mapped", icon: "✅", label: "Mapped Categories", count: summary?.completed_categories },
              { id: "unmapped", icon: "⚠️", label: "Unmapped Categories", count: summary?.pending_categories },
              { id: "pending", icon: "🔴", label: "Unmapped Products", count: summary?.unmapped_products },
            ].map(t => (
              <button key={t.id} className={`pdr-nav-tab ${activeTab === t.id ? "active" : ""}`} onClick={() => setActiveTab(t.id)}>
                {t.icon} {t.label}
                {t.count != null && <span className="tab-count">{Number(t.count).toLocaleString()}</span>}
              </button>
            ))}
          </div>

          {/* ================================================================
              TAB: ANALYTICS
              ================================================================ */}
          {activeTab === "analytics" && (
            <div className="pdr-analytics-wrap" style={{ marginTop: 8 }}>
              {/* Analytics Header */}
              <div className="pdr-analytics-header">
                <div>
                  <div className="pdr-analytics-title">
                    {pt.emoji} {platform === "All" ? "Cross-Platform Comparison" : `${platform} Analytics`}
                  </div>
                  <div className="pdr-analytics-sub">
                    {platform === "All"
                      ? "Comparative analytics across all marketplaces from local database"
                      : `Platform-specific charts from local ${platform} database · Live queries`}
                  </div>
                </div>
                <div className="pdr-action-row">
                  <button className="pdr-btn pdr-btn-ghost" onClick={() => setReportOpen(true)}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 15V3M8 11l4 4 4-4M5 21h14"/></svg>
                    Download CSV
                  </button>
                  <button className="pdr-btn pdr-btn-primary" onClick={() => window.print()}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                    Print PDF Report
                  </button>
                </div>
              </div>

              {/* ── KEY INSIGHTS PANEL ── */}
              {insights.length > 0 && (
                <div className="pdr-insights-panel">
                  <div className="insights-header">
                    <span className="icon">💡</span> Dynamic Business Insights (Auto-calculated)
                  </div>
                  <div className="insights-grid">
                    {insights.map((insight, idx) => (
                      <div key={idx} className={`insight-card insight-${insight.type}`}>
                        <span className="insight-icon">{insight.icon}</span>
                        <div className="insight-content">
                          <div className="insight-title">{insight.title}</div>
                          <div className="insight-text">{insight.text}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}


              {/* ──────────────────────────────────────────────────────────────
                  ALL PLATFORMS: Comparison Charts
                  ────────────────────────────────────────────────────────────── */}
              {platform === "All" && (
                <div className="pdr-charts-grid">

                  {/* 1. Platform Volume Comparison */}
                  <ChartCard
                    title="Platform Volume Comparison"
                    sub="Products · Brands · Categories across all marketplaces"
                    badge="Grouped Bar"
                    hasData={platformCompData.length > 0}
                  >
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={platformCompData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                        <XAxis dataKey="name" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                        <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v} />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                        <Bar dataKey="Products" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={22} />
                        <Bar dataKey="Brands" fill="#f59e0b" radius={[4, 4, 0, 0]} barSize={22} />
                        <Bar dataKey="Categories" fill="#22c55e" radius={[4, 4, 0, 0]} barSize={22} />
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  {/* 2. Avg Price Benchmark */}
                  <ChartCard
                    title="Average Selling Price Benchmark"
                    sub="Average selling price per platform in INR"
                    badge="Bar"
                    hasData={avgPriceCompData.length > 0}
                  >
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={avgPriceCompData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                        <XAxis dataKey="name" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                        <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `₹${(v/1000).toFixed(0)}K`} />
                        <Tooltip content={<ChartTooltip prefix="₹" />} />
                        <Bar dataKey="Avg Price (₹)" radius={[6, 6, 0, 0]} barSize={48}>
                          {avgPriceCompData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  {/* 3. Stock Availability Comparison */}
                  <ChartCard
                    title="Stock Availability Comparison"
                    sub="In-stock vs Out-of-stock volume across platforms"
                    badge="Stacked Bar"
                    hasData={stockCompData.length > 0 && stockCompData.some(d => d["In Stock"] > 0 || d["Out of Stock"] > 0)}
                  >
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={stockCompData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                        <XAxis dataKey="name" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                        <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v} />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                        <Bar dataKey="In Stock" stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} barSize={40} />
                        <Bar dataKey="Out of Stock" stackId="a" fill="#f43f5e" radius={[4, 4, 0, 0]} barSize={40} />
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  {/* 4. Category Coverage Ratio */}
                  <ChartCard
                    title="Category Coverage Ratio"
                    sub="Mapped vs Pending categories per platform"
                    badge="Grouped Bar"
                    hasData={catCoverageData.length > 0 && catCoverageData.some(d => d.Mapped > 0 || d.Pending > 0)}
                  >
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={catCoverageData} layout="vertical" margin={{ top: 5, right: 20, left: 60, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                        <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                        <YAxis type="category" dataKey="name" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                        <Bar dataKey="Mapped" fill="#6366f1" radius={[0, 4, 4, 0]} barSize={16} />
                        <Bar dataKey="Pending" fill="#f43f5e" radius={[0, 4, 4, 0]} barSize={16} />
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  {/* 5. Cross-Platform Category Distribution */}
                  <ChartCard
                    title="Top Categories — Cross Platform"
                    sub="Category product count distribution across all marketplaces"
                    badge="Stacked Bar"
                    span2
                    hasData={crossCatData.length > 0}
                  >
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={crossCatData} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-30} textAnchor="end" interval={0} />
                        <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                        {mpNames.map((mp, i) => (
                          <Bar key={mp} dataKey={mp} stackId="a" fill={PLATFORMS[mp]?.accent || PLATFORMS.All.palette[i]} radius={i === mpNames.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]} barSize={32} />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  {/* 6. Mapped vs Unmapped Products Donut */}
                  <ChartCard
                    title="Mapped vs Unmapped Products"
                    sub="Data quality health across the catalog"
                    badge="Donut"
                    hasData={roster.length > 0 && roster.some(r => r.mapped_products > 0)}
                  >
                    <ResponsiveContainer width="100%" height={280}>
                      <PieChart>
                        <Pie
                          data={roster.filter(r => r.total_products > 0).map(r => ([
                            { name: `${r.marketplace_name} Mapped`, value: r.mapped_products, fill: PLATFORMS[r.marketplace_name]?.accent || "#6366f1" },
                            { name: `${r.marketplace_name} Unmapped`, value: r.unmapped_products, fill: "#e2e8f0" },
                          ])).flat()}
                          cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={2} dataKey="value"
                        >
                          {roster.filter(r => r.total_products > 0).map((r, i) => [
                            <Cell key={`m${i}`} fill={PLATFORMS[r.marketplace_name]?.accent || "#6366f1"} />,
                            <Cell key={`u${i}`} fill="#e2e8f0" />,
                          ])}
                        </Pie>
                        <Tooltip content={<ChartTooltip />} />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  {/* 7. Brand Coverage by Marketplace */}
                  <ChartCard
                    title="Brand Coverage by Marketplace"
                    sub="Unique brand counts comparison across all platforms"
                    badge="Bar"
                    hasData={roster.length > 0 && roster.some(r => r.total_brands > 0)}
                  >
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={roster.filter(r => r.total_products > 0).map(r => ({ name: r.marketplace_name, value: r.total_brands }))} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                        <XAxis dataKey="name" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                        <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v} />
                        <Tooltip content={<ChartTooltip />} />
                        <Bar dataKey="value" name="Brands" radius={[6, 6, 0, 0]} barSize={34}>
                          {roster.filter(r => r.total_products > 0).map((r, i) => <Cell key={i} fill={PLATFORMS[r.marketplace_name]?.accent || "#6366f1"} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                </div>
              )}


              {/* AMAZON: 7 Charts from /chart-data endpoint */}
              {platform === "Amazon" && (() => {
                const cats = chartData.amazon_categories || [];
                const prices = chartData.amazon_price_range || [];
                const ratings = chartData.amazon_ratings || [];
                const brands = chartData.amazon_brands || [];
                const reviews = chartData.amazon_reviews || [];
                const bestsellers = chartData.amazon_bestsellers || [];
                const priceMrp = chartData.amazon_price_vs_mrp || [];
                return (
                  <div className="pdr-charts-grid">
                    <ChartCard title="Top Category Distribution" sub="Product volume across Amazon top categories (full 1.6M catalog)" badge="Bar" hasData={cats.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={cats} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-35} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="value" name="Products" radius={[6, 6, 0, 0]} barSize={28}>{cats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Price Range Distribution" sub="Amazon product count across INR price brackets" badge="Histogram" hasData={prices.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={prices} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" fill={pt.accent} radius={[6, 6, 0, 0]} barSize={36} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Customer Rating Distribution" sub="Star-rating buckets across Amazon top sellers" badge="Histogram" hasData={ratings.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={ratings} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" radius={[6, 6, 0, 0]} barSize={36}>{ratings.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Top Brand Catalog Coverage" sub="Top Amazon brands by product listing count" badge="Horizontal Bar" hasData={brands.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={brands} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" radius={[0, 6, 6, 0]} barSize={14}>{brands.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Reviews by Category" sub="Cumulative customer review volume per category" badge="Bar" hasData={reviews.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={reviews} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-30} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="Reviews" fill={pt.accent} radius={[6, 6, 0, 0]} barSize={28} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Best Sellers by Category" sub="Amazon best-seller tagged products per category" badge="Donut" hasData={bestsellers.length > 0}>
                      <div style={{ position: "relative" }}>
                        <ResponsiveContainer width="100%" height={280}>
                          <PieChart>
                            <Pie data={bestsellers.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }))} cx="50%" cy="50%" innerRadius={65} outerRadius={105} paddingAngle={3} dataKey="value">
                              {bestsellers.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}
                            </Pie>
                            <Tooltip content={<ChartTooltip />} />
                            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </ChartCard>

                    <ChartCard title="Sale Price vs MRP by Category" sub="Average selling price vs list price gap across Amazon categories" badge="Dual Area" hasData={priceMrp.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={priceMrp} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <defs><linearGradient id="amzSaleFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `Rs.${(v/1000).toFixed(0)}K`} />
                          <Tooltip content={<ChartTooltip prefix="Rs." />} />
                          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          <Area type="monotone" dataKey="Sale Price" stroke={pt.accent} strokeWidth={2.5} fill="url(#amzSaleFill)" />
                          <Area type="monotone" dataKey="Market Price" stroke="#94a3b8" strokeWidth={2} fill="none" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>
                  </div>
                );
              })()}

              {/* BLINKIT: 7 Charts (11,519 grocery delivery products) */}
              {platform === "Blinkit" && (() => {
                const cats = chartData.blinkit_categories || [];
                const subcats = chartData.blinkit_subcategories || [];
                const prices = chartData.blinkit_price_range || [];
                const stock = chartData.blinkit_stock || [];
                const discount = chartData.blinkit_discount || [];
                const brands = chartData.blinkit_brands || [];
                const priceMrp = chartData.blinkit_price_vs_mrp || [];
                return (
                  <div className="pdr-charts-grid">
                    <ChartCard title="Category-wise Product Count" sub="Product distribution across Blinkit grocery categories (11,519 products)" badge="Bar" hasData={cats.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={cats} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-35} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="value" name="Products" radius={[6, 6, 0, 0]} barSize={26}>{cats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sub-Category Distribution" sub="Blinkit product spread across sub-categories" badge="Donut" hasData={subcats.length > 0}>
                      <div style={{ position: "relative" }}>
                        <ResponsiveContainer width="100%" height={280}>
                          <PieChart>
                            <Pie data={subcats.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }))} cx="50%" cy="50%" innerRadius={65} outerRadius={105} paddingAngle={3} dataKey="value">
                              {subcats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}
                            </Pie>
                            <Tooltip content={<ChartTooltip />} />
                            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </ChartCard>

                    <ChartCard title="Price Range Distribution" sub="Blinkit product count across price segments" badge="Histogram" hasData={prices.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={prices} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" fill={pt.accent} radius={[6, 6, 0, 0]} barSize={34} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="In-Stock vs Out-of-Stock by Category" sub="Real-time inventory availability breakdown per category" badge="Stacked Bar" hasData={stock.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={stock} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={130} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          <Bar dataKey="In Stock" stackId="a" fill="#22c55e" barSize={14} />
                          <Bar dataKey="Out of Stock" stackId="a" fill="#f43f5e" radius={[0, 4, 4, 0]} barSize={14} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Discount Analysis by Category" sub="Average discount percentage per Blinkit grocery category" badge="Area" hasData={discount.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={discount} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
                          <defs><linearGradient id="blkDiscFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-30} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                          <Tooltip content={<ChartTooltip suffix="%" />} />
                          <Area type="monotone" dataKey="Avg Discount %" stroke={pt.accent} strokeWidth={2.5} fill="url(#blkDiscFill)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Brand-wise Product Count" sub="Top Blinkit brands by number of product listings" badge="Horizontal Bar" hasData={brands.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={brands} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" radius={[0, 6, 6, 0]} barSize={14}>{brands.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sale Price vs MRP by Category" sub="Average selling price vs market price comparison per category" badge="Dual Area" hasData={priceMrp.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={priceMrp} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <defs><linearGradient id="blkSaleFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `Rs.${v}`} />
                          <Tooltip content={<ChartTooltip prefix="Rs." />} />
                          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          <Area type="monotone" dataKey="Sale Price" stroke={pt.accent} strokeWidth={2.5} fill="url(#blkSaleFill)" />
                          <Area type="monotone" dataKey="Market Price" stroke="#94a3b8" strokeWidth={2} fill="none" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>
                  </div>
                );
              })()}

              {/* BIGBASKET: 7 Charts (34,559 grocery & FMCG products) */}
              {platform === "BigBasket" && (() => {
                const cats = chartData.bigbasket_categories || [];
                const subcats = chartData.bigbasket_subcategories || [];
                const prices = chartData.bigbasket_price_range || [];
                const priceMrp = chartData.bigbasket_price_vs_mrp || [];
                const ratings = chartData.bigbasket_ratings || [];
                const discount = chartData.bigbasket_discount || [];
                const topRated = chartData.bigbasket_top_rated || [];
                return (
                  <div className="pdr-charts-grid">
                    <ChartCard title="Main Category Distribution" sub="Product count across BigBasket primary grocery categories (34,559 products)" badge="Bar" hasData={cats.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={cats} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-35} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="value" name="Products" radius={[6, 6, 0, 0]} barSize={28}>{cats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sub-Category Distribution" sub="Product volume breakdown across BigBasket sub-departments" badge="Donut" hasData={subcats.length > 0}>
                      <div style={{ position: "relative" }}>
                        <ResponsiveContainer width="100%" height={280}>
                          <PieChart>
                            <Pie data={subcats.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }))} cx="50%" cy="50%" innerRadius={65} outerRadius={105} paddingAngle={3} dataKey="value">
                              {subcats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}
                            </Pie>
                            <Tooltip content={<ChartTooltip />} />
                            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </ChartCard>

                    <ChartCard title="Price Range Distribution" sub="BigBasket product count across selling price segments" badge="Histogram" hasData={prices.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={prices} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" fill={pt.accent} radius={[6, 6, 0, 0]} barSize={36} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sale Price vs MRP by Category" sub="Selling price vs maximum retail price gap per category" badge="Dual Area" hasData={priceMrp.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={priceMrp} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <defs><linearGradient id="bbSaleFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `Rs.${v}`} />
                          <Tooltip content={<ChartTooltip prefix="Rs." />} />
                          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          <Area type="monotone" dataKey="Sale Price" stroke={pt.accent} strokeWidth={2.5} fill="url(#bbSaleFill)" />
                          <Area type="monotone" dataKey="Market Price" stroke="#94a3b8" strokeWidth={2} fill="none" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Customer Rating Distribution" sub="BigBasket product count by customer star rating buckets" badge="Histogram" hasData={ratings.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={ratings} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" radius={[6, 6, 0, 0]} barSize={36}>{ratings.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Discount Analysis by Category" sub="Average discount offered vs MRP across BigBasket categories" badge="Area" hasData={discount.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={discount} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
                          <defs><linearGradient id="bbDiscFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-30} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                          <Tooltip content={<ChartTooltip suffix="%" />} />
                          <Area type="monotone" dataKey="Avg Discount %" stroke={pt.accent} strokeWidth={2.5} fill="url(#bbDiscFill)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Top Rated Categories" sub="Categories with highest average customer ratings on BigBasket" badge="Horizontal Bar" hasData={topRated.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={topRated} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" domain={[0, 5]} tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="Avg Rating" name="Avg Rating" radius={[0, 6, 6, 0]} barSize={14}>{topRated.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>
                  </div>
                );
              })()}

              {/* DMART: 7 Charts (10,825 retail hypermarket products) */}
              {platform === "DMart" && (() => {
                const cats = chartData.dmart_categories || [];
                const brands = chartData.dmart_brands || [];
                const prices = chartData.dmart_price_range || [];
                const priceMrp = chartData.dmart_price_vs_mrp || [];
                const stock = chartData.dmart_stock || [];
                const discount = chartData.dmart_discount || [];
                const brandsPerCat = chartData.dmart_brands_per_cat || [];
                return (
                  <div className="pdr-charts-grid">
                    <ChartCard title="Category-wise Product Count" sub="DMart product distribution across retail categories (10,825 products)" badge="Bar" hasData={cats.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={cats} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-35} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="value" name="Products" radius={[6, 6, 0, 0]} barSize={28}>{cats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Top Brand Catalog Coverage" sub="Top 10 brands with highest DMart product listings" badge="Horizontal Bar" hasData={brands.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={brands} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={120} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" radius={[0, 6, 6, 0]} barSize={14}>{brands.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Price Range Distribution" sub="DMart product count across price brackets" badge="Histogram" hasData={prices.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={prices} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" fill={pt.accent} radius={[6, 6, 0, 0]} barSize={34} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sale Price vs MRP by Category" sub="Average selling price vs list price comparison across DMart categories" badge="Dual Area" hasData={priceMrp.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={priceMrp} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <defs><linearGradient id="dmSaleFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `Rs.${v}`} />
                          <Tooltip content={<ChartTooltip prefix="Rs." />} />
                          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          <Area type="monotone" dataKey="Sale Price" stroke={pt.accent} strokeWidth={2.5} fill="url(#dmSaleFill)" />
                          <Area type="monotone" dataKey="Market Price" stroke="#94a3b8" strokeWidth={2} fill="none" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Stock Availability" sub="In-stock vs Out-of-stock split across DMart catalog" badge="Pie" hasData={stock.length > 0}>
                      <div style={{ position: "relative" }}>
                        <ResponsiveContainer width="100%" height={280}>
                          <PieChart>
                            <Pie data={stock.map((d, i) => ({ ...d, fill: i === 0 ? "#22c55e" : "#f43f5e" }))} cx="50%" cy="50%" outerRadius={105} dataKey="value" startAngle={90} endAngle={-270}>
                              {stock.map((_, i) => <Cell key={i} fill={i === 0 ? "#22c55e" : "#f43f5e"} />)}
                            </Pie>
                            <Tooltip content={<ChartTooltip />} />
                            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </ChartCard>

                    <ChartCard title="Discount Analysis by Category" sub="Average discount percentage across DMart product categories" badge="Area" hasData={discount.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={discount} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
                          <defs><linearGradient id="dmDiscFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-30} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                          <Tooltip content={<ChartTooltip suffix="%" />} />
                          <Area type="monotone" dataKey="Avg Discount %" stroke={pt.accent} strokeWidth={2.5} fill="url(#dmDiscFill)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Brand Diversity by Category" sub="Unique brands vs product count per DMart category" badge="Grouped Bar" hasData={brandsPerCat.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={brandsPerCat} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-35} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          <Bar dataKey="Brands" fill={pt.accent} radius={[4, 4, 0, 0]} barSize={18} />
                          <Bar dataKey="Products" fill={pt.palette[1] || "#f97316"} radius={[4, 4, 0, 0]} barSize={18} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>
                  </div>
                );
              })()}

              {/* INDIAMART: 7 Charts (46,116 B2B products) */}
              {platform === "IndiaMart" && (() => {
                const cats = chartData.indiamart_categories || [];
                const subcats = chartData.indiamart_subcategories || [];
                const prices = chartData.indiamart_price_range || [];
                const ratings = chartData.indiamart_ratings || [];
                const manufacturers = chartData.indiamart_manufacturers || [];
                const avgPrice = chartData.indiamart_avg_price || [];
                const locations = chartData.indiamart_locations || [];
                return (
                  <div className="pdr-charts-grid">
                    <ChartCard title="B2B Category Distribution" sub="IndiaMart product spread across B2B industry categories (46,116 products)" badge="Bar" hasData={cats.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={cats} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-35} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="value" name="Products" radius={[6, 6, 0, 0]} barSize={26}>{cats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sub-Category Distribution" sub="Product volume breakdown across IndiaMart B2B sub-sectors" badge="Donut" hasData={subcats.length > 0}>
                      <div style={{ position: "relative" }}>
                        <ResponsiveContainer width="100%" height={280}>
                          <PieChart>
                            <Pie data={subcats.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }))} cx="50%" cy="50%" innerRadius={65} outerRadius={105} paddingAngle={3} dataKey="value">
                              {subcats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}
                            </Pie>
                            <Tooltip content={<ChartTooltip />} />
                            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </ChartCard>

                    <ChartCard title="Price Range Distribution (B2B)" sub="IndiaMart product count across B2B price segments (INR)" badge="Histogram" hasData={prices.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={prices} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" fill={pt.accent} radius={[6, 6, 0, 0]} barSize={34} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Supplier Rating Distribution" sub="Supplier star rating distribution on IndiaMart (1-5)" badge="Histogram" hasData={ratings.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={ratings} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" radius={[6, 6, 0, 0]} barSize={36}>{ratings.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Top Manufacturers / Suppliers" sub="IndiaMart manufacturers with highest product listing count" badge="Horizontal Bar" hasData={manufacturers.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={manufacturers} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={130} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Listings" radius={[0, 6, 6, 0]} barSize={14}>{manufacturers.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Avg Price by Category" sub="Average B2B product price per IndiaMart industry category" badge="Bar" hasData={avgPrice.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={avgPrice} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => v >= 100000 ? `${(v/100000).toFixed(1)}L` : v >= 1000 ? `${(v/1000).toFixed(0)}K` : v} />
                          <YAxis type="category" dataKey="name" width={130} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip prefix="Rs." />} />
                          <Bar dataKey="Avg Price" name="Avg Price (Rs.)" radius={[0, 6, 6, 0]} barSize={14}>{avgPrice.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Supplier Location Distribution" sub="Top cities/states with highest IndiaMart supplier presence" badge="Horizontal Bar" hasData={locations.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={locations} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Suppliers" radius={[0, 6, 6, 0]} barSize={14}>{locations.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>
                  </div>
                );
              })()}

              {/* ZEPTO: 7 Charts (8,253 quick commerce products) */}
              {platform === "Zepto" && (() => {
                const cats = chartData.zepto_categories || [];
                const subcats = chartData.zepto_subcategories || [];
                const prices = chartData.zepto_price_range || [];
                const ratings = chartData.zepto_ratings || [];
                const discount = chartData.zepto_discount || [];
                const topRated = chartData.zepto_top_rated || [];
                const priceMrp = chartData.zepto_price_vs_mrp || [];
                return (
                  <div className="pdr-charts-grid">
                    <ChartCard title="Category-wise Product Count" sub="Product distribution across Zepto quick commerce categories (8,253 products)" badge="Bar" hasData={cats.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={cats} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-35} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="value" name="Products" radius={[6, 6, 0, 0]} barSize={26}>{cats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sub-Category Distribution" sub="Zepto product spread across sub-categories" badge="Donut" hasData={subcats.length > 0}>
                      <div style={{ position: "relative" }}>
                        <ResponsiveContainer width="100%" height={280}>
                          <PieChart>
                            <Pie data={subcats.map((d, i) => ({ ...d, fill: pt.palette[i % pt.palette.length] }))} cx="50%" cy="50%" innerRadius={65} outerRadius={105} paddingAngle={3} dataKey="value">
                              {subcats.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}
                            </Pie>
                            <Tooltip content={<ChartTooltip />} />
                            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </ChartCard>

                    <ChartCard title="Price Range Distribution" sub="Zepto product count across price segments" badge="Histogram" hasData={prices.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={prices} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" fill={pt.accent} radius={[6, 6, 0, 0]} barSize={34} />
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Customer Rating Distribution" sub="Customer star rating distribution on Zepto (1-5)" badge="Histogram" hasData={ratings.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={ratings} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="count" name="Products" radius={[6, 6, 0, 0]} barSize={36}>{ratings.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Discount Analysis by Category" sub="Average discount percentage per Zepto grocery category" badge="Area" hasData={discount.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={discount} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
                          <defs><linearGradient id="zepDiscFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} angle={-30} textAnchor="end" interval={0} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
                          <Tooltip content={<ChartTooltip suffix="%" />} />
                          <Area type="monotone" dataKey="Avg Discount %" stroke={pt.accent} strokeWidth={2.5} fill="url(#zepDiscFill)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Top Rated Categories" sub="Categories with highest average customer ratings on Zepto" badge="Horizontal Bar" hasData={topRated.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={topRated} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                          <XAxis type="number" domain={[0, 5]} tick={TICK_STYLE} tickLine={false} axisLine={false} />
                          <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#94a3b8", fontSize: 10, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="Avg Rating" name="Avg Rating" radius={[0, 6, 6, 0]} barSize={14}>{topRated.map((_, i) => <Cell key={i} fill={pt.palette[i % pt.palette.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </ChartCard>

                    <ChartCard title="Sale Price vs MRP by Category" sub="Average selling price vs market price comparison per category" badge="Dual Area" hasData={priceMrp.length > 0}>
                      <ResponsiveContainer width="100%" height={280}>
                        <AreaChart data={priceMrp} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                          <defs><linearGradient id="zepSaleFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={pt.accent} stopOpacity={0.3} /><stop offset="95%" stopColor={pt.accent} stopOpacity={0} /></linearGradient></defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9, fontWeight: 600 }} tickLine={false} axisLine={false} />
                          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} tickFormatter={v => `Rs.${v}`} />
                          <Tooltip content={<ChartTooltip prefix="Rs." />} />
                          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                          <Area type="monotone" dataKey="Sale Price" stroke={pt.accent} strokeWidth={2.5} fill="url(#zepSaleFill)" />
                          <Area type="monotone" dataKey="Market Price" stroke="#94a3b8" strokeWidth={2} fill="none" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </ChartCard>
                  </div>
                );
              })()}

              {/* No chart data fallback */}
              {Object.keys(chartData).length === 0 && !loading && platform !== "All" && (
                <div style={{ background: "#fff", borderRadius: 20, padding: "60px 0", textAlign: "center", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>Chart data loading...</div>
                  <button className="pdr-btn pdr-btn-primary" onClick={handleRefresh}>Sync Data Now</button>
                </div>
              )}
            </div>
          )}



          {/* ================================================================
              TAB: PRODUCTS
              ================================================================ */}
          {activeTab === "products" && (
            <>
              <div className="pdr-controls" style={{ padding: "0 36px 16px", marginTop: 20 }}>
                <div>
                  <span style={{ fontSize: 13, color: "#64748b", fontWeight: 700 }}>
                    Showing {filteredProducts.length.toLocaleString()} products matching active slicer criteria
                  </span>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <button className="pdr-btn pdr-btn-ghost" onClick={exportCSV} disabled={csvExporting} style={{ opacity: csvExporting ? 0.6 : 1 }}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 15V3M8 11l4 4 4-4M5 21h14"/></svg>
                    {csvExporting ? "Preparing CSV…" : "Export All Records (CSV)"}
                  </button>
                </div>
              </div>

              {loading ? (
                <div className="pdr-spinner-wrap"><div className="pdr-spinner" /><span className="pdr-spinner-text">Loading products…</span></div>
              ) : filteredProducts.length === 0 ? (
                <div style={{ padding: "0 36px 32px" }}>
                  <div className="pdr-empty" style={{ background: "#fff", borderRadius: 20, padding: "60px 0" }}>
                    <div className="pdr-empty-icon">🔍</div>
                    <div className="pdr-empty-text">No products found</div>
                    <div className="pdr-empty-sub">Try a different search or click Refresh to sync data</div>
                    <button className="pdr-btn pdr-btn-primary" onClick={handleRefresh} style={{ marginTop: 16 }}>Sync Data</button>
                  </div>
                </div>
              ) : (
                <div className="pdr-product-grid">
                  {filteredProducts.map((p, i) => (
                    <div key={p.product_id || i} className="pdr-product-card" onClick={() => openDrawer(p)}>
                      <div className="pc-img">
                        <span className="pc-rank">#{i + 1}</span>
                        {p.img_url
                          ? <img src={p.img_url} alt="" onError={e => { e.target.style.display = "none"; }} />
                          : <span style={{ fontSize: 36 }}>{PLATFORMS[p.marketplace_name]?.emoji || "📦"}</span>
                        }
                      </div>
                      <div className="pc-body">
                        <div className="pc-cat">{p.category_name || p.marketplace_name || "Product"}</div>
                        <div className="pc-name" title={p.product_name}>{p.product_name}</div>
                        <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                          <span className="pc-price">{p.price ? `₹${Number(p.price).toLocaleString("en-IN")}` : "—"}</span>
                          {p.list_price && p.list_price > p.price && <span className="pc-mrp">₹{Number(p.list_price).toLocaleString("en-IN")}</span>}
                        </div>
                        <div className="pc-footer">
                          <Stars val={p.stars} />
                          <span style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8" }}>{p.reviews ? `${Number(p.reviews).toLocaleString()} rev` : ""}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ================================================================
              TAB: MAPPED CATEGORIES
              ================================================================ */}
          {activeTab === "mapped" && (
            <div className="pdr-table-wrap" style={{ marginTop: 20 }}>
              {/* Per-Marketplace Mapping Summary Cards */}
              {Object.keys(mappingReport).length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14, marginBottom: 24 }}>
                  {Object.entries(mappingReport).map(([mp, info]) => {
                    const pct = info.mapping_pct || 0;
                    const mpColor = PLATFORMS[mp.charAt(0).toUpperCase() + mp.slice(1)]?.accent || "#6366f1";
                    return (
                      <div key={mp} style={{ background: "#fff", borderRadius: 16, padding: "18px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", borderLeft: `4px solid ${mpColor}` }}>
                        <div style={{ fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.8px", color: "#94a3b8", marginBottom: 6 }}>{mp.charAt(0).toUpperCase() + mp.slice(1)}</div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                          <div style={{ fontSize: 22, fontWeight: 900, color: "#1a1d2e" }}>{Number(info.total_products).toLocaleString("en-IN")}</div>
                          <div style={{ fontSize: 12, fontWeight: 800, color: pct >= 90 ? "#22c55e" : pct >= 60 ? "#f59e0b" : "#ef4444" }}>{pct}%</div>
                        </div>
                        <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>total products</div>
                        <div style={{ marginTop: 10, background: "#f1f5f9", borderRadius: 99, height: 6, overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${pct}%`, background: pct >= 90 ? "#22c55e" : pct >= 60 ? "#f59e0b" : "#ef4444", borderRadius: 99, transition: "width 0.8s" }} />
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 10, fontWeight: 600 }}>
                          <span style={{ color: "#22c55e" }}>✓ {Number(info.mapped_products).toLocaleString("en-IN")} mapped</span>
                          <span style={{ color: "#ef4444" }}>✗ {Number(info.unmapped_products).toLocaleString("en-IN")} unmapped</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Category breakdown table per marketplace */}
              {Object.keys(mappingReport).length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 20, marginBottom: 24 }}>
                  {Object.entries(mappingReport).filter(([, info]) => info.categories?.length > 0).map(([mp, info]) => {
                    const mpLabel = mp.charAt(0).toUpperCase() + mp.slice(1);
                    const mpColor = PLATFORMS[mpLabel]?.accent || "#6366f1";
                    return (
                      <div key={mp} className="pdr-table-card">
                        <div className="pdr-table-header">
                          <span className="th-title" style={{ color: mpColor }}>{PLATFORMS[mpLabel]?.emoji || "📦"} {mpLabel} Categories ({info.categories.length})</span>
                          <span className="th-count" style={{ color: info.mapping_pct >= 90 ? "#22c55e" : "#f59e0b" }}>{info.mapping_pct}% mapped</span>
                        </div>
                        <div style={{ overflowX: "auto" }}>
                          <table className="pdr-table">
                            <thead><tr><th>#</th><th>Category Name</th>{info.categories[0]?.sub_count !== undefined && <th>Sub-categories</th>}<th>Products Mapped</th></tr></thead>
                            <tbody>
                              {info.categories.map((cat, idx) => (
                                <tr key={idx}>
                                  <td style={{ color: "#94a3b8", fontSize: 11 }}>{idx + 1}</td>
                                  <td style={{ fontWeight: 700, color: "#1a1d2e" }}>{cat.main_category}</td>
                                  {cat.sub_count !== undefined && <td><span style={{ background: "#ede9fe", color: "#7c3aed", padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700 }}>{cat.sub_count} sub</span></td>}
                                  <td style={{ fontWeight: 600 }}>{cat.products !== undefined ? Number(cat.products).toLocaleString("en-IN") : "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Original all-categories view */}
              <div className="pdr-controls" style={{ padding: "0 0 16px" }}>
                <div className="pdr-search" style={{ maxWidth: 320 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                  <input value={search} onChange={e => { setSearch(e.target.value); setAppliedSearch(e.target.value); }} placeholder="Search categories…" />
                </div>
                <Badge label={`${mappedCats.length} entries`} cls="badge-green" />
              </div>
              <div className="pdr-table-card">
                <div className="pdr-table-header">
                  <span className="th-title">✅ All Mapped Categories (DB Union View)</span>
                  <span className="th-count">{mappedCats.length} records</span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="pdr-table">
                    <thead><tr><th>#</th><th>Platform</th><th>Level</th><th>Category</th><th>Subcategory</th><th>Path</th></tr></thead>
                    <tbody>
                      {mappedCats.length === 0
                        ? <tr><td colSpan={6}><div className="pdr-empty"><span className="pdr-empty-icon">📭</span><span className="pdr-empty-text">No mapped categories</span></div></td></tr>
                        : mappedCats.map(c => (
                          <tr key={c.id}>
                            <td style={{ color: "#94a3b8", fontSize: 11 }}>#{c.id}</td>
                            <td><Badge label={c.marketplace_name} cls="badge-purple" /></td>
                            <td><span style={{ background: "#ede9fe", color: "#7c3aed", padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 800 }}>L{c.category_level}</span></td>
                            <td style={{ fontWeight: 700, color: "#1a1d2e" }}>{c.category_name}</td>
                            <td style={{ color: "#64748b" }}>{c.subcategory_name}</td>
                            <td style={{ color: "#374151", maxWidth: 280 }}><span title={c.category_path} style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.category_path}</span></td>
                          </tr>
                        ))
                      }
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================
              TAB: UNMAPPED CATEGORIES
              ================================================================ */}
          {activeTab === "unmapped" && (
            <div className="pdr-table-wrap" style={{ marginTop: 20 }}>
              <div className="pdr-controls" style={{ padding: "0 0 16px" }}>
                <div className="pdr-search" style={{ maxWidth: 320 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                  <input value={search} onChange={e => { setSearch(e.target.value); setAppliedSearch(e.target.value); }} placeholder="Search unmapped…" />
                </div>
                <Badge label={`${unmappedCats.length} pending`} cls="badge-amber" />
              </div>
              <div className="pdr-table-card">
                <div className="pdr-table-header">
                  <span className="th-title">⚠️ Unmapped Categories</span>
                  <span className="th-count">{unmappedCats.length} issues</span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="pdr-table">
                    <thead><tr><th>#</th><th>Platform</th><th>Level</th><th>Category Path</th><th>Reason</th></tr></thead>
                    <tbody>
                      {unmappedCats.length === 0
                        ? <tr><td colSpan={5}><div className="pdr-empty"><span className="pdr-empty-icon">✨</span><span className="pdr-empty-text">All categories mapped!</span></div></td></tr>
                        : unmappedCats.map(c => (
                          <tr key={c.id}>
                            <td style={{ color: "#94a3b8", fontSize: 11 }}>#{c.id}</td>
                            <td><Badge label={c.marketplace_name} cls="badge-purple" /></td>
                            <td><span style={{ background: "#fff7ed", color: "#c2410c", padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 800 }}>L{c.category_level}</span></td>
                            <td style={{ fontWeight: 600, color: "#1a1d2e", maxWidth: 300 }}><span title={c.category_path} style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.category_path}</span></td>
                            <td><Badge label={c.reason || "Unknown"} cls="badge-red" /></td>
                          </tr>
                        ))
                      }
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================
              TAB: UNMAPPED PRODUCTS
              ================================================================ */}
          {activeTab === "pending" && (
            <div className="pdr-table-wrap" style={{ marginTop: 20 }}>
              <div className="pdr-controls" style={{ padding: "0 0 16px" }}>
                <div className="pdr-search" style={{ maxWidth: 320 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                  <input value={search} onChange={e => { setSearch(e.target.value); setAppliedSearch(e.target.value); }} placeholder="Search SKUs, brands…" />
                </div>
                <Badge label={`${unmappedProds.length} items`} cls="badge-red" />
              </div>
              <div className="pdr-table-card">
                <div className="pdr-table-header">
                  <span className="th-title">🔴 Unmapped Products</span>
                  <span className="th-count">{unmappedProds.length} items</span>
                </div>
                <div style={{ overflowX: "auto" }}>
                  <table className="pdr-table">
                    <thead><tr><th>ID/ASIN</th><th>Platform</th><th>Product</th><th>Brand</th><th>Price</th><th>Reason</th></tr></thead>
                    <tbody>
                      {unmappedProds.length === 0
                        ? <tr><td colSpan={6}><div className="pdr-empty"><span className="pdr-empty-icon">✅</span><span className="pdr-empty-text">All products mapped!</span></div></td></tr>
                        : unmappedProds.map(p => (
                          <tr key={p.id}>
                            <td style={{ fontFamily: "monospace", fontSize: 11, color: "#6366f1", fontWeight: 700 }}>{p.asin || `#${p.product_id}`}</td>
                            <td><Badge label={p.marketplace_name} cls="badge-blue" /></td>
                            <td style={{ maxWidth: 260 }}>
                              <span style={{ fontWeight: 700, color: "#1a1d2e", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.product_name}>{p.product_name}</span>
                              <span style={{ fontSize: 10, color: "#94a3b8" }}>{p.category_name}</span>
                            </td>
                            <td style={{ fontWeight: 600 }}>{p.brand || "—"}</td>
                            <td style={{ fontWeight: 800 }}>{p.price ? `₹${Number(p.price).toLocaleString("en-IN")}` : "—"}</td>
                            <td><Badge label={p.reason || "No category"} cls="badge-red" /></td>
                          </tr>
                        ))
                      }
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ================================================================
          PRODUCT DETAIL DRAWER
          ================================================================ */}
      {drawerOpen && (
        <>
          <div className="pdr-drawer-overlay" onClick={() => setDrawerOpen(false)} />
          <div className="pdr-drawer">
            <div className="pdr-drawer-head">
              <div>
                <div style={{ fontSize: 15, fontWeight: 800, color: "#1a1d2e" }}>Product Details</div>
                <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2, textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: 600 }}>Technical Specifications</div>
              </div>
              <button className="pdr-btn-icon" onClick={() => setDrawerOpen(false)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div className="pdr-drawer-body">
              {drawerLoading ? (
                <div className="pdr-spinner-wrap"><div className="pdr-spinner" /><span className="pdr-spinner-text">Loading specs…</span></div>
              ) : drawerProduct ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                  <div style={{ height: 200, background: "#f8fafc", borderRadius: 16, display: "flex", alignItems: "center", justifyContent: "center", position: "relative", overflow: "hidden", border: "1px solid #f0f2f7" }}>
                    {drawerProduct.imgUrl || drawerProduct.img_url
                      ? <img src={drawerProduct.imgUrl || drawerProduct.img_url} alt="" style={{ maxHeight: "100%", maxWidth: "100%", objectFit: "contain", padding: 16 }} onError={e => { e.target.style.display = "none"; }} />
                      : <span style={{ fontSize: 64 }}>{PLATFORMS[drawerProduct.marketplace_name]?.emoji || "📦"}</span>
                    }
                    <span style={{ position: "absolute", bottom: 8, left: 8, background: "#0f172a", color: "#fff", fontSize: 9, fontWeight: 800, padding: "3px 8px", borderRadius: 6, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      {drawerProduct.marketplace_name || "Unknown"}
                    </span>
                  </div>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 800, color: "#1a1d2e", lineHeight: 1.4 }}>{drawerProduct.title || drawerProduct.product_name}</div>
                    {drawerProduct.brand && <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>by <strong style={{ color: "#374151" }}>{drawerProduct.brand}</strong></div>}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    {[
                      { label: "ASIN / ID", value: drawerProduct.asin || `#${drawerProduct.id}` },
                      { label: "Price", value: drawerProduct.price ? `₹${Number(drawerProduct.price).toLocaleString("en-IN")}` : "—" },
                      { label: "MRP", value: drawerProduct.listPrice || drawerProduct.list_price ? `₹${Number(drawerProduct.listPrice || drawerProduct.list_price).toLocaleString("en-IN")}` : "—" },
                      { label: "Rating", value: drawerProduct.stars ? `${Number(drawerProduct.stars).toFixed(1)} ★` : "—" },
                      { label: "Reviews", value: Number(drawerProduct.reviews || 0).toLocaleString("en-IN") },
                      { label: "Bought Last Month", value: drawerProduct.boughtInLastMonth ? `${Number(drawerProduct.boughtInLastMonth).toLocaleString()}+` : "—" },
                    ].map(({ label, value }) => (
                      <div key={label} style={{ background: "#f8fafc", borderRadius: 12, padding: "12px 14px", border: "1px solid #f0f2f7" }}>
                        <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.8px", color: "#94a3b8" }}>{label}</div>
                        <div style={{ fontSize: 14, fontWeight: 800, color: "#1a1d2e", marginTop: 4 }}>{value}</div>
                      </div>
                    ))}
                  </div>
                  {(drawerProduct.categoryName || drawerProduct.category_name) && (
                    <div style={{ background: "#ede9fe", borderRadius: 12, padding: "12px 14px" }}>
                      <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.8px", color: "#7c3aed", marginBottom: 4 }}>Category</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "#4c1d95" }}>{drawerProduct.categoryName || drawerProduct.category_name}</div>
                    </div>
                  )}
                  {drawerProduct.availability && (
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>Availability:</span>
                      <Badge label={drawerProduct.availability} cls={String(drawerProduct.availability).toLowerCase().includes("out") ? "badge-red" : "badge-green"} />
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {drawerProduct.isBestSeller && <Badge label="🔥 Best Seller" cls="badge-amber" />}
                    {drawerProduct.is_prime && <Badge label="⚡ Prime" cls="badge-blue" />}
                    {drawerProduct.deal_type && <Badge label={drawerProduct.deal_type} cls="badge-purple" />}
                  </div>
                  {drawerProduct.description && (
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.8px", color: "#94a3b8", marginBottom: 8 }}>Description</div>
                      <div style={{ fontSize: 12, color: "#374151", lineHeight: 1.6, maxHeight: 120, overflowY: "auto", background: "#f8fafc", borderRadius: 12, padding: "12px 14px", border: "1px solid #f0f2f7" }}>
                        {drawerProduct.description}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="pdr-empty"><div className="pdr-empty-icon">📭</div><div className="pdr-empty-text">No data available</div></div>
              )}
            </div>
            <div className="pdr-drawer-footer">
              <button className="pdr-btn pdr-btn-ghost" style={{ flex: 1, justifyContent: "center" }} onClick={() => setDrawerOpen(false)}>Close</button>
              {drawerProduct?.productUrl && (
                <button className="pdr-btn pdr-btn-primary" style={{ flex: 1, justifyContent: "center" }} onClick={() => window.open(drawerProduct.productUrl, "_blank")}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                  View on Site
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
