import React, { useEffect, useState, useCallback } from "react";
import api from "../../utils/Api";
import * as XLSX from "xlsx/dist/xlsx.full.min.js";

const COLUMNS = [
  { key: "sku_id",       label: "ID / SKU",     width: 100 },
  { key: "image_url",    label: "Image",        width: 80 },
  { key: "product_name", label: "Product Name", width: 300 },
  { key: "category",     label: "Category",     width: 150 },
  { key: "subcategory",  label: "Sub Category", width: 150 },
  { key: "price",        label: "Price (₹)",    width: 100 },
  { key: "mrp",          label: "MRP (₹)",      width: 100 },
  { key: "discount",     label: "Discount",     width: 95 },
  { key: "rating",       label: "Rating",       width: 90 },
  { key: "review",       label: "Reviews",      width: 90 },
  { key: "quantity",     label: "Quantity",     width: 100 },
  { key: "product_url",  label: "Link",         width: 80 },
];

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  .zep-root { font-family: 'Inter', sans-serif; background: #f0f2f7; min-height: 100vh; padding: 28px 24px; }
  .zep-header { background: linear-gradient(135deg,#db2777 0%,#701a75 100%); border-radius: 20px; padding: 28px 32px; margin-bottom: 24px; color: #fff; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
  .zep-header h1 { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }
  .zep-header p { font-size: 13px; opacity: 0.85; margin-top: 4px; }
  .zep-badge { background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.3); border-radius: 99px; padding: 4px 14px; font-size: 11px; font-weight: 700; }
  .zep-controls { background: #fff; border-radius: 16px; padding: 18px 24px; margin-bottom: 18px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
  .zep-search { flex: 1; min-width: 200px; display: flex; align-items: center; gap: 8px; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 8px 12px; transition: border-color 0.2s; }
  .zep-search:focus-within { border-color: #db2777; box-shadow: 0 0 0 3px rgba(219,39,119,0.08); }
  .zep-search input { border: none; outline: none; font-size: 13px; width: 100%; font-family: inherit; }
  .zep-select { padding: 8px 12px; border-radius: 10px; border: 1.5px solid #e2e8f0; font-size: 12px; font-weight: 600; color: #374151; outline: none; font-family: inherit; background: #fff; }
  .zep-select:focus { border-color: #db2777; }
  .zep-btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 10px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; font-family: inherit; transition: all 0.2s; white-space: nowrap; }
  .zep-btn-pink { background: linear-gradient(135deg,#db2777,#701a75); color: #fff; box-shadow: 0 4px 12px rgba(219,39,119,0.25); }
  .zep-btn-pink:hover { transform: translateY(-1px); }
  .zep-btn-ghost { background: #fff; border: 1.5px solid #e2e8f0; color: #374151; }
  .zep-btn-ghost:hover { background: #f8fafc; }
  .zep-table-card { background: #fff; border-radius: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); overflow: hidden; }
  .zep-table-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 22px; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }
  .zep-table-header .title { font-size: 14px; font-weight: 800; color: #1a1d2e; }
  .zep-table-header .sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }
  .zep-table-wrap { overflow-x: auto; }
  .zep-table { width: 100%; border-collapse: collapse; min-width: 1100px; }
  .zep-table thead th { padding: 11px 16px; text-align: left; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.7px; color: #94a3b8; background: #f8fafc; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
  .zep-table tbody tr { border-bottom: 1px solid #f8fafc; transition: background 0.15s; }
  .zep-table tbody tr:hover { background: #fdf2f8; }
  .zep-table tbody td { padding: 11px 16px; font-size: 12px; color: #374151; vertical-align: middle; }
  .zep-table tbody td.name-cell { max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600; }
  .badge-in { background: #dcfce7; color: #16a34a; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 700; }
  .badge-out { background: #fee2e2; color: #dc2626; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 700; }
  .zep-pagination { display: flex; align-items: center; justify-content: space-between; padding: 14px 22px; border-top: 1px solid #f1f5f9; }
  .zep-pagination .info { font-size: 12px; color: #64748b; }
  .zep-pagination .btns { display: flex; gap: 6px; }
  .zep-pagination button { padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; border: 1.5px solid #e2e8f0; background: #fff; cursor: pointer; transition: all 0.15s; }
  .zep-pagination button:hover:not(:disabled) { background: #db2777; color: #fff; border-color: #db2777; }
  .zep-pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
  .zep-pagination .page-info { font-size: 12px; font-weight: 700; color: #1a1d2e; padding: 6px 14px; }
  .zep-spinner { display: flex; align-items: center; justify-content: center; padding: 60px; gap: 12px; color: #94a3b8; font-size: 13px; font-weight: 600; }
  .zep-spinner-icon { width: 36px; height: 36px; border-radius: 50%; border: 3px solid #e2e8f0; border-top-color: #db2777; animation: zep-spin 0.7s linear infinite; }
  @keyframes zep-spin { to { transform: rotate(360deg); } }
  .zep-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; gap: 8px; }
  .zep-empty .icon { font-size: 40px; opacity: 0.3; }
  .zep-empty .msg { font-size: 14px; font-weight: 600; color: #64748b; }
  .zep-kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 20px; }
  .zep-kpi { background: #fff; border-radius: 14px; padding: 18px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #db2777; }
  .zep-kpi .kpi-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #94a3b8; }
  .zep-kpi .kpi-value { font-size: 26px; font-weight: 900; color: #1a1d2e; margin-top: 4px; letter-spacing: -0.5px; }
  .zep-kpi .kpi-sub { font-size: 11px; color: #64748b; margin-top: 4px; }
  .zep-stars { display: flex; gap: 2px; align-items: center; }
  .zep-star { font-size: 11px; }
`;

const LIMIT = 50;

export default function ZeptoData() {
  const [data, setData]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [total, setTotal]         = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage]           = useState(1);
  const [search, setSearch]       = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [category, setCategory]   = useState("");
  const [categories, setCategories] = useState([]);
  const [sortField, setSortField] = useState("");
  const [sortDir, setSortDir]     = useState("asc");
  const [stats, setStats]         = useState(null);

  const fetchData = useCallback(async (pg = 1, q = search, cat = category) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: pg, limit: LIMIT });
      if (q) params.append("search", q);
      if (cat && cat !== "All") params.append("category", cat);
      const res = await api.get(`/product-report/zepto/data?${params}`);
      const d = res.data;
      setData(d.data || []);
      setTotal(d.total_count || 0);
      setTotalPages(d.total_pages || 1);
      setPage(pg);
    } catch (e) {
      console.error("Zepto fetch error", e);
    } finally {
      setLoading(false);
    }
  }, [search, category]);

  useEffect(() => { fetchData(1, "", ""); }, []);

  // Load summary stats & categories
  useEffect(() => {
    api.get("/product-report/summary?marketplace=Zepto")
      .then(r => setStats(r.data?.data))
      .catch(() => {});
    api.get("/product-report/mapping/zepto")
      .then(r => {
        const cats = [...new Set((r.data?.data || []).map(x => x.category_name))].filter(Boolean).sort();
        setCategories(cats);
      })
      .catch(() => {});
  }, []);

  const handleSearch = () => { setSearch(searchInput); fetchData(1, searchInput, category); };
  const handleCategoryChange = (e) => { setCategory(e.target.value); fetchData(1, search, e.target.value); };

  const sortedData = [...data].sort((a, b) => {
    if (!sortField) return 0;
    const A = a[sortField] ?? "";
    const B = b[sortField] ?? "";
    const numA = parseFloat(A), numB = parseFloat(B);
    if (!isNaN(numA) && !isNaN(numB)) return sortDir === "asc" ? numA - numB : numB - numA;
    return sortDir === "asc"
      ? String(A).localeCompare(String(B))
      : String(B).localeCompare(String(A));
  });

  const toggleSort = (key) => {
    if (sortField === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortField(key); setSortDir("asc"); }
  };

  const [exporting, setExporting] = useState(false);

  const exportExcel = async () => {
    setExporting(true);
    try {
      const response = await fetch('/api/product-report/export-csv?marketplace=Zepto');
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `Zepto_Products_Full_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      alert('Export failed: ' + e.message);
    } finally {
      setExporting(false);
    }
  };

  const discount = (r) => {
    const p = parseFloat(r.price), lp = parseFloat(r.mrp);
    if (lp > 0 && p > 0 && lp > p) return `${((lp - p) / lp * 100).toFixed(0)}%`;
    return "—";
  };

  return (
    <div className="zep-root">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      {/* Header */}
      <div className="zep-header">
        <div>
          <h1>🛒 Zepto Product Master</h1>
          <p>Local database · {total.toLocaleString("en-IN")} total products</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span className="zep-badge">🟣 Local DB</span>
          <button className="zep-btn zep-btn-ghost" style={{ background: "rgba(255,255,255,0.15)", color: "#fff", border: "1px solid rgba(255,255,255,0.3)" }} onClick={exportExcel} disabled={exporting}>
            {exporting ? '⏳ Exporting…' : '📥 Export All (CSV)'}
          </button>
        </div>
      </div>

      {/* KPI Row */}
      {stats && stats.total_products > 0 && (
        <div className="zep-kpi-row">
          {[
            { label: "Total Products", value: stats.total_products.toLocaleString("en-IN"), sub: "in database" },
            { label: "Categories", value: stats.total_categories.toLocaleString(), sub: "unique categories" },
            { label: "Brands", value: stats.total_brands.toLocaleString(), sub: "unique brands" },
            { label: "In Stock", value: stats.available_products.toLocaleString("en-IN"), sub: `${stats.total_products > 0 ? ((stats.available_products / stats.total_products) * 100).toFixed(1) : 0}% available` },
            { label: "Avg Price", value: `₹${Number(stats.avg_selling_price || 0).toFixed(0)}`, sub: "average selling price" },
          ].map((k, i) => (
            <div key={i} className="zep-kpi">
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-sub">{k.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="zep-controls">
        <div className="zep-search" style={{ flex: 2 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleSearch(); }}
            placeholder="Search by product name or SKU/ID…"
          />
        </div>
        <select className="zep-select" value={category} onChange={handleCategoryChange}>
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="zep-btn zep-btn-pink" onClick={handleSearch}>Search</button>
        <button className="zep-btn zep-btn-ghost" onClick={() => { setSearchInput(""); setSearch(""); setCategory(""); fetchData(1, "", ""); }}>Reset</button>
      </div>

      {/* Table */}
      <div className="zep-table-card">
        <div className="zep-table-header">
          <div>
            <div className="title">Product Data</div>
            <div className="sub">Showing {((page - 1) * LIMIT) + 1}–{Math.min(page * LIMIT, total)} of {total.toLocaleString("en-IN")} results</div>
          </div>
          <button className="zep-btn zep-btn-ghost" onClick={exportExcel}>📥 Export</button>
        </div>

        <div className="zep-table-wrap">
          {loading ? (
            <div className="zep-spinner"><div className="zep-spinner-icon" /><span>Loading Zepto data…</span></div>
          ) : data.length === 0 ? (
            <div className="zep-empty">
              <div className="icon">🛒</div>
              <div className="msg">No products found. Try adjusting your filters.</div>
            </div>
          ) : (
            <table className="zep-table">
              <thead>
                <tr>
                  {COLUMNS.map(col => (
                    <th key={col.key} style={{ minWidth: col.width, cursor: "pointer" }} onClick={() => toggleSort(col.key)}>
                      {col.label} {sortField === col.key ? (sortDir === "asc" ? "↑" : "↓") : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedData.map((row, i) => (
                  <tr key={row.sku_id || i}>
                    <td style={{ color: "#94a3b8", fontWeight: 600 }}>{row.sku_id}</td>
                    <td>
                      {row.image_url ? (
                        <img src={row.image_url} alt="" style={{ height: 32, width: 32, objectFit: "contain" }} />
                      ) : "—"}
                    </td>
                    <td className="name-cell" title={row.name}>{row.name || "—"}</td>
                    <td>
                      <span style={{ background: "#f1f5f9", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>
                        {row.category || "—"}
                      </span>
                    </td>
                    <td>{row.subcategory || "—"}</td>
                    <td style={{ fontWeight: 700, color: "#db2777" }}>
                      {row.price ? `₹${parseFloat(row.price).toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td style={{ color: "#94a3b8", textDecoration: "line-through", fontSize: 11 }}>
                      {row.mrp ? `₹${parseFloat(row.mrp).toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td>
                      {(() => { const d = discount(row); return d !== "—" ? <span style={{ background: "#fce7f3", color: "#db2777", padding: "2px 7px", borderRadius: 99, fontSize: 10, fontWeight: 700 }}>{d} OFF</span> : "—"; })()}
                    </td>
                    <td>
                      {row.rating ? (
                        <div className="zep-stars">
                          {[1,2,3,4,5].map(x => (
                            <span key={x} className="zep-star" style={{ color: x <= Math.round(row.rating) ? "#f59e0b" : "#e2e8f0" }}>★</span>
                          ))}
                          <span style={{ marginLeft: 4, fontWeight: 700, fontSize: 11 }}>{row.rating}</span>
                        </div>
                      ) : "—"}
                    </td>
                    <td>{row.review ? parseFloat(row.review).toLocaleString("en-IN") : "0"}</td>
                    <td style={{ fontSize: 11 }}>{row.quantity || "—"}</td>
                    <td>
                      {row.product_url
                        ? <a href={row.product_url} target="_blank" rel="noreferrer" style={{ color: "#db2777", fontWeight: 600, fontSize: 11 }}>View ↗</a>
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div className="zep-pagination">
          <div className="info">Page {page} of {totalPages} · {total.toLocaleString("en-IN")} total products</div>
          <div className="btns">
            <button onClick={() => fetchData(1)} disabled={page === 1}>First</button>
            <button onClick={() => fetchData(page - 1)} disabled={page === 1}>Prev</button>
            <span className="page-info">{page} / {totalPages}</span>
            <button onClick={() => fetchData(page + 1)} disabled={page >= totalPages}>Next</button>
            <button onClick={() => fetchData(totalPages)} disabled={page >= totalPages}>Last</button>
          </div>
        </div>
      </div>
    </div>
  );
}