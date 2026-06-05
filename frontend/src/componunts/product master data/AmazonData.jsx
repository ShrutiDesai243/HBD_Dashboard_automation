import React, { useEffect, useState, useCallback } from "react";
import api from "../../utils/Api";
import * as XLSX from "xlsx/dist/xlsx.full.min.js";

const COLUMNS = [
  { key: "id",                 label: "ID",           width: 80 },
  { key: "asin",               label: "ASIN",         width: 110 },
  { key: "name",               label: "Product Name", width: 300 },
  { key: "category",           label: "Category",     width: 160 },
  { key: "price",              label: "Price (₹)",    width: 100 },
  { key: "list_price",         label: "MRP (₹)",      width: 100 },
  { key: "stars",              label: "Stars",        width: 90 },
  { key: "reviews",            label: "Reviews",      width: 100 },
  { key: "is_best_seller",     label: "Best Seller",  width: 110 },
  { key: "bought_in_last_month",label: "Bought/Mo",   width: 110 },
  { key: "product_url",        label: "Link",         width: 80 },
];

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  .amz-root { font-family: 'Inter', sans-serif; background: #f0f2f7; min-height: 100vh; padding: 28px 24px; }
  .amz-header { background: linear-gradient(135deg,#f59e0b 0%,#ef4444 100%); border-radius: 20px; padding: 28px 32px; margin-bottom: 24px; color: #fff; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
  .amz-header h1 { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }
  .amz-header p { font-size: 13px; opacity: 0.75; margin-top: 4px; }
  .amz-badge { background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.3); border-radius: 99px; padding: 4px 14px; font-size: 11px; font-weight: 700; }
  .amz-controls { background: #fff; border-radius: 16px; padding: 18px 24px; margin-bottom: 18px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
  .amz-search { flex: 1; min-width: 200px; display: flex; align-items: center; gap: 8px; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 8px 12px; transition: border-color 0.2s; }
  .amz-search:focus-within { border-color: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,0.08); }
  .amz-search input { border: none; outline: none; font-size: 13px; width: 100%; font-family: inherit; }
  .amz-select { padding: 8px 12px; border-radius: 10px; border: 1.5px solid #e2e8f0; font-size: 12px; font-weight: 600; color: #374151; outline: none; font-family: inherit; background: #fff; }
  .amz-select:focus { border-color: #f59e0b; }
  .amz-btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 10px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; font-family: inherit; transition: all 0.2s; white-space: nowrap; }
  .amz-btn-orange { background: linear-gradient(135deg,#f59e0b,#ef4444); color: #fff; box-shadow: 0 4px 12px rgba(245,158,11,0.25); }
  .amz-btn-orange:hover { transform: translateY(-1px); }
  .amz-btn-ghost { background: #fff; border: 1.5px solid #e2e8f0; color: #374151; }
  .amz-btn-ghost:hover { background: #f8fafc; }
  .amz-table-card { background: #fff; border-radius: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); overflow: hidden; }
  .amz-table-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 22px; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }
  .amz-table-header .title { font-size: 14px; font-weight: 800; color: #1a1d2e; }
  .amz-table-header .sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }
  .amz-table-wrap { overflow-x: auto; }
  .amz-table { width: 100%; border-collapse: collapse; min-width: 1100px; }
  .amz-table thead th { padding: 11px 16px; text-align: left; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.7px; color: #94a3b8; background: #f8fafc; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
  .amz-table tbody tr { border-bottom: 1px solid #f8fafc; transition: background 0.15s; }
  .amz-table tbody tr:hover { background: #fffbeb; }
  .amz-table tbody td { padding: 11px 16px; font-size: 12px; color: #374151; vertical-align: middle; }
  .amz-table tbody td.name-cell { max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600; }
  .badge-best { background: #ffedd5; color: #ea580c; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 700; }
  .amz-pagination { display: flex; align-items: center; justify-content: space-between; padding: 14px 22px; border-top: 1px solid #f1f5f9; }
  .amz-pagination .info { font-size: 12px; color: #64748b; }
  .amz-pagination .btns { display: flex; gap: 6px; }
  .amz-pagination button { padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; border: 1.5px solid #e2e8f0; background: #fff; cursor: pointer; transition: all 0.15s; }
  .amz-pagination button:hover:not(:disabled) { background: #f59e0b; color: #fff; border-color: #f59e0b; }
  .amz-pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
  .amz-pagination .page-info { font-size: 12px; font-weight: 700; color: #1a1d2e; padding: 6px 14px; }
  .amz-spinner { display: flex; align-items: center; justify-content: center; padding: 60px; gap: 12px; color: #94a3b8; font-size: 13px; font-weight: 600; }
  .amz-spinner-icon { width: 36px; height: 36px; border-radius: 50%; border: 3px solid #e2e8f0; border-top-color: #f59e0b; animation: amz-spin 0.7s linear infinite; }
  @keyframes amz-spin { to { transform: rotate(360deg); } }
  .amz-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; gap: 8px; }
  .amz-empty .icon { font-size: 40px; opacity: 0.3; }
  .amz-empty .msg { font-size: 14px; font-weight: 600; color: #64748b; }
  .amz-kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 20px; }
  .amz-kpi { background: #fff; border-radius: 14px; padding: 18px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #f59e0b; }
  .amz-kpi .kpi-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #94a3b8; }
  .amz-kpi .kpi-value { font-size: 26px; font-weight: 900; color: #1a1d2e; margin-top: 4px; letter-spacing: -0.5px; }
  .amz-kpi .kpi-sub { font-size: 11px; color: #64748b; margin-top: 4px; }
  .amz-stars { display: flex; gap: 2px; align-items: center; }
  .amz-star { font-size: 11px; }
`;

const LIMIT = 50;

export default function AmazonData() {
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
      const res = await api.get(`/product-report/amazon/data?${params}`);
      const d = res.data;
      setData(d.data || []);
      setTotal(d.total_count || 0);
      setTotalPages(d.total_pages || 1);
      setPage(pg);
    } catch (e) {
      console.error("Amazon fetch error", e);
    } finally {
      setLoading(false);
    }
  }, [search, category]);

  useEffect(() => { fetchData(1, "", ""); }, []);

  // Load summary stats & categories
  useEffect(() => {
    api.get("/product-report/summary?marketplace=Amazon")
      .then(r => setStats(r.data?.data))
      .catch(() => {});
    api.get("/product-report/mapping/amazon")
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
      const response = await fetch('/api/product-report/export-csv?marketplace=Amazon');
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `Amazon_Products_Full_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      alert('Export failed: ' + e.message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="amz-root">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      {/* Header */}
      <div className="amz-header">
        <div>
          <h1>📦 Amazon Product Master</h1>
          <p>Local database · {total.toLocaleString("en-IN")} total products</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span className="amz-badge">📦 Local DB</span>
          <button className="amz-btn amz-btn-ghost" style={{ background: "rgba(255,255,255,0.15)", color: "#fff", border: "1px solid rgba(255,255,255,0.3)" }} onClick={exportExcel} disabled={exporting}>
            {exporting ? '⏳ Exporting…' : '📥 Export All (CSV)'}
          </button>
        </div>
      </div>

      {/* KPI Row */}
      {stats && stats.total_products > 0 && (
        <div className="amz-kpi-row">
          {[
            { label: "Total Products", value: stats.total_products.toLocaleString("en-IN"), sub: "in database" },
            { label: "Categories", value: stats.total_categories.toLocaleString(), sub: "unique categories" },
            { label: "Brands", value: stats.total_brands.toLocaleString(), sub: "unique brands" },
            { label: "Avg Price", value: `₹${Number(stats.avg_selling_price || 0).toFixed(0)}`, sub: "average selling price" },
          ].map((k, i) => (
            <div key={i} className="amz-kpi">
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-sub">{k.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="amz-controls">
        <div className="amz-search" style={{ flex: 2 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleSearch(); }}
            placeholder="Search by product name or ASIN…"
          />
        </div>
        <select className="amz-select" value={category} onChange={handleCategoryChange}>
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="amz-btn amz-btn-orange" onClick={handleSearch}>Search</button>
        <button className="amz-btn amz-btn-ghost" onClick={() => { setSearchInput(""); setSearch(""); setCategory(""); fetchData(1, "", ""); }}>Reset</button>
      </div>

      {/* Table */}
      <div className="amz-table-card">
        <div className="amz-table-header">
          <div>
            <div className="title">Product Data</div>
            <div className="sub">Showing {((page - 1) * LIMIT) + 1}–{Math.min(page * LIMIT, total)} of {total.toLocaleString("en-IN")} results</div>
          </div>
          <button className="amz-btn amz-btn-ghost" onClick={exportExcel} disabled={exporting}>📥 {exporting ? 'Exporting…' : 'Export All'}</button>
        </div>

        <div className="amz-table-wrap">
          {loading ? (
            <div className="amz-spinner"><div className="amz-spinner-icon" /><span>Loading Amazon data…</span></div>
          ) : data.length === 0 ? (
            <div className="amz-empty">
              <div className="icon">📦</div>
              <div className="msg">No products found. Try adjusting your filters.</div>
            </div>
          ) : (
            <table className="amz-table">
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
                  <tr key={row.id || i}>
                    <td style={{ color: "#94a3b8", fontWeight: 600 }}>{row.id}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 11 }}>{row.asin || "—"}</td>
                    <td className="name-cell" title={row.name}>{row.name || "—"}</td>
                    <td>
                      <span style={{ background: "#f1f5f9", padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>
                        {row.category || "—"}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700, color: "#ea580c" }}>
                      {row.price ? `₹${parseFloat(row.price).toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td style={{ color: "#94a3b8", textDecoration: "line-through", fontSize: 11 }}>
                      {row.list_price ? `₹${parseFloat(row.list_price).toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td>
                      {row.stars ? (
                        <div className="amz-stars">
                          {[1,2,3,4,5].map(x => (
                            <span key={x} className="amz-star" style={{ color: x <= Math.round(row.stars) ? "#f59e0b" : "#e2e8f0" }}>★</span>
                          ))}
                          <span style={{ marginLeft: 4, fontWeight: 700, fontSize: 11 }}>{row.stars}</span>
                        </div>
                      ) : "—"}
                    </td>
                    <td>{row.reviews ? parseFloat(row.reviews).toLocaleString("en-IN") : "0"}</td>
                    <td>
                      {row.is_best_seller ? <span className="badge-best">🔥 Best Seller</span> : "—"}
                    </td>
                    <td>{row.bought_in_last_month ? parseFloat(row.bought_in_last_month).toLocaleString("en-IN") : "—"}</td>
                    <td>
                      {row.product_url
                        ? <a href={row.product_url} target="_blank" rel="noreferrer" style={{ color: "#ea580c", fontWeight: 600, fontSize: 11 }}>View ↗</a>
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div className="amz-pagination">
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