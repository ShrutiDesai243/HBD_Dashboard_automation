import React, { useEffect, useState, useCallback } from "react";
import api from "../../utils/Api";
import * as XLSX from "xlsx/dist/xlsx.full.min.js";

const COLUMNS = [
  { key: "id",                   label: "ID",               width: 70 },
  { key: "asin",                 label: "Product Code",     width: 130 },
  { key: "name",                 label: "Product Name",     width: 280 },
  { key: "category",             label: "Category",         width: 180 },
  { key: "sub_category",         label: "Sub-Category",     width: 180 },
  { key: "price",                label: "Price",            width: 120 },
  { key: "stars",                label: "Rating",           width: 80 },
  { key: "reviews",              label: "Reviews",          width: 80 },
  { key: "manufacturer",         label: "Manufacturer",     width: 160 },
  { key: "location",             label: "Location",         width: 130 },
  { key: "contact_number",       label: "Contact",          width: 130 },
  { key: "badges",               label: "Badges",           width: 150 },
  { key: "link",                 label: "Link",             width: 80 },
];

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  .imt-root { font-family: 'Inter', sans-serif; background: #f0f2f7; min-height: 100vh; padding: 28px 24px; }
  .imt-header { background: linear-gradient(135deg,#0084ff 0%,#0060cc 100%); border-radius: 20px; padding: 28px 32px; margin-bottom: 24px; color: #fff; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
  .imt-header h1 { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }
  .imt-header p { font-size: 13px; opacity: 0.75; margin-top: 4px; }
  .imt-badge { background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.3); border-radius: 99px; padding: 4px 14px; font-size: 11px; font-weight: 700; }
  .imt-controls { background: #fff; border-radius: 16px; padding: 18px 24px; margin-bottom: 18px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
  .imt-search { flex: 1; min-width: 200px; display: flex; align-items: center; gap: 8px; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 8px 12px; transition: border-color 0.2s; }
  .imt-search:focus-within { border-color: #0084ff; box-shadow: 0 0 0 3px rgba(0,132,255,0.08); }
  .imt-search input { border: none; outline: none; font-size: 13px; width: 100%; font-family: inherit; }
  .imt-select { padding: 8px 12px; border-radius: 10px; border: 1.5px solid #e2e8f0; font-size: 12px; font-weight: 600; color: #374151; outline: none; font-family: inherit; background: #fff; }
  .imt-select:focus { border-color: #0084ff; }
  .imt-btn { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 10px; font-size: 12px; font-weight: 700; cursor: pointer; border: none; font-family: inherit; transition: all 0.2s; white-space: nowrap; }
  .imt-btn-blue { background: linear-gradient(135deg,#0084ff,#0060cc); color: #fff; box-shadow: 0 4px 12px rgba(0,132,255,0.25); }
  .imt-btn-blue:hover { transform: translateY(-1px); }
  .imt-btn-ghost { background: #fff; border: 1.5px solid #e2e8f0; color: #374151; }
  .imt-btn-ghost:hover { background: #f8fafc; }
  .imt-table-card { background: #fff; border-radius: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); overflow: hidden; }
  .imt-table-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 22px; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }
  .imt-table-header .title { font-size: 14px; font-weight: 800; color: #1a1d2e; }
  .imt-table-header .sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }
  .imt-table-wrap { overflow-x: auto; }
  .imt-table { width: 100%; border-collapse: collapse; min-width: 1600px; }
  .imt-table thead th { padding: 11px 14px; text-align: left; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.7px; color: #94a3b8; background: #f8fafc; border-bottom: 1px solid #f1f5f9; white-space: nowrap; cursor: pointer; user-select: none; }
  .imt-table thead th:hover { color: #0084ff; }
  .imt-table tbody tr { border-bottom: 1px solid #f8fafc; transition: background 0.15s; }
  .imt-table tbody tr:hover { background: #f0f8ff; }
  .imt-table tbody td { padding: 10px 14px; font-size: 12px; color: #374151; vertical-align: middle; }
  .imt-table tbody td.name-cell { max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600; }
  .stars-display { display: flex; gap: 2px; align-items: center; }
  .imt-pagination { display: flex; align-items: center; justify-content: space-between; padding: 14px 22px; border-top: 1px solid #f1f5f9; }
  .imt-pagination .info { font-size: 12px; color: #64748b; }
  .imt-pagination .btns { display: flex; gap: 6px; align-items: center; }
  .imt-pagination button { padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; border: 1.5px solid #e2e8f0; background: #fff; cursor: pointer; transition: all 0.15s; }
  .imt-pagination button:hover:not(:disabled) { background: #0084ff; color: #fff; border-color: #0084ff; }
  .imt-pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
  .imt-pagination .page-info { font-size: 12px; font-weight: 700; color: #1a1d2e; padding: 6px 14px; }
  .imt-spinner { display: flex; align-items: center; justify-content: center; padding: 60px; gap: 12px; color: #94a3b8; font-size: 13px; font-weight: 600; }
  .imt-spinner-icon { width: 36px; height: 36px; border-radius: 50%; border: 3px solid #e2e8f0; border-top-color: #0084ff; animation: imt-spin 0.7s linear infinite; }
  @keyframes imt-spin { to { transform: rotate(360deg); } }
  .imt-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; gap: 8px; }
  .imt-kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 20px; }
  .imt-kpi { background: #fff; border-radius: 14px; padding: 18px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #0084ff; }
  .imt-kpi .kpi-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #94a3b8; }
  .imt-kpi .kpi-value { font-size: 26px; font-weight: 900; color: #1a1d2e; margin-top: 4px; letter-spacing: -0.5px; }
  .imt-kpi .kpi-sub { font-size: 11px; color: #64748b; margin-top: 4px; }
  .badge-pill { background: #dbeafe; color: #1d4ed8; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 600; }
  .price-tag { font-weight: 700; color: #0084ff; }
  .no-data { color: #94a3b8; font-size: 11px; }
`;

const LIMIT = 50;

const Stars = ({ val }) => {
  if (!val || val === 0) return <span className="no-data">—</span>;
  return (
    <div className="stars-display">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} style={{ fontSize: 11, color: i <= Math.round(val) ? "#f59e0b" : "#e2e8f0" }}>★</span>
      ))}
      <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginLeft: 3 }}>{Number(val).toFixed(1)}</span>
    </div>
  );
};

export default function IndiaMartData() {
  const [data, setData]               = useState([]);
  const [loading, setLoading]         = useState(true);
  const [total, setTotal]             = useState(0);
  const [totalPages, setTotalPages]   = useState(1);
  const [page, setPage]               = useState(1);
  const [search, setSearch]           = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [category, setCategory]       = useState("");
  const [categories, setCategories]   = useState([]);
  const [sortField, setSortField]     = useState("");
  const [sortDir, setSortDir]         = useState("asc");
  const [stats, setStats]             = useState(null);

  const fetchData = useCallback(async (pg = 1, q = search, cat = category) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: pg, limit: LIMIT });
      if (q) params.append("search", q);
      if (cat && cat !== "All") params.append("category", cat);
      const res = await api.get(`/product-report/indiamart/data?${params}`);
      const d = res.data;
      setData(d.data || []);
      setTotal(d.total_count || 0);
      setTotalPages(d.total_pages || 1);
      setPage(pg);
    } catch (e) {
      console.error("IndiaMart fetch error", e);
    } finally {
      setLoading(false);
    }
  }, [search, category]);

  useEffect(() => { fetchData(1, "", ""); }, []);

  useEffect(() => {
    api.get("/product-report/summary?marketplace=IndiaMart")
      .then(r => setStats(r.data?.data))
      .catch(() => {});
    api.get("/product-report/mapping/indiamart")
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
    return sortDir === "asc" ? String(A).localeCompare(String(B)) : String(B).localeCompare(String(A));
  });

  const toggleSort = (key) => {
    if (sortField === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortField(key); setSortDir("asc"); }
  };

  const [exporting, setExporting] = useState(false);

  const exportExcel = async () => {
    setExporting(true);
    try {
      const response = await fetch('/api/product-report/export-csv?marketplace=IndiaMart');
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `IndiaMart_Products_Full_${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      alert('Export failed: ' + e.message);
    } finally {
      setExporting(false);
    }
  };

  const fmtPrice = (row) => {
    if (row.price_str && row.price_str.trim()) return row.price_str;
    if (row.price > 0) return `₹${Number(row.price).toLocaleString("en-IN")}`;
    return "—";
  };

  return (
    <div className="imt-root">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      {/* Header */}
      <div className="imt-header">
        <div>
          <h1>🏭 IndiaMart Product Catalog</h1>
          <p>Local database · {total.toLocaleString("en-IN")} total products</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span className="imt-badge">🏭 Local DB</span>
          <button
            className="imt-btn imt-btn-ghost"
            style={{ background: "rgba(255,255,255,0.15)", color: "#fff", border: "1px solid rgba(255,255,255,0.3)" }}
            onClick={exportExcel} disabled={exporting}
          >{exporting ? '⏳ Exporting…' : '📥 Export All (CSV)'}</button>
        </div>
      </div>

      {/* KPI Row */}
      {stats && stats.total_products > 0 && (
        <div className="imt-kpi-row">
          {[
            { label: "Total Products",   value: stats.total_products.toLocaleString("en-IN"), sub: "from indiamart_products" },
            { label: "Categories",       value: stats.total_categories.toLocaleString(),       sub: "unique categories" },
            { label: "Manufacturers",    value: stats.total_brands.toLocaleString(),            sub: "unique manufacturers" },
            { label: "Mapped",           value: stats.mapped_products.toLocaleString("en-IN"), sub: `${stats.total_products > 0 ? ((stats.mapped_products/stats.total_products)*100).toFixed(1) : 0}% mapped` },
            { label: "Avg Price",        value: `₹${Number(stats.avg_selling_price || 0).toFixed(0)}`, sub: "average selling price" },
          ].map((k, i) => (
            <div key={i} className="imt-kpi">
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-sub">{k.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="imt-controls">
        <div className="imt-search" style={{ flex: 2 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleSearch(); }}
            placeholder="Search by product name, manufacturer, location or code…"
          />
        </div>
        <select className="imt-select" value={category} onChange={handleCategoryChange}>
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="imt-btn imt-btn-blue" onClick={handleSearch}>Search</button>
        <button className="imt-btn imt-btn-ghost" onClick={() => { setSearchInput(""); setSearch(""); setCategory(""); fetchData(1, "", ""); }}>Reset</button>
      </div>

      {/* Table */}
      <div className="imt-table-card">
        <div className="imt-table-header">
          <div>
            <div className="title">IndiaMart B2B Products</div>
            <div className="sub">Showing {((page - 1) * LIMIT) + 1}–{Math.min(page * LIMIT, total)} of {total.toLocaleString("en-IN")} results</div>
          </div>
          <button className="imt-btn imt-btn-ghost" onClick={exportExcel}>📥 Export</button>
        </div>

        <div className="imt-table-wrap">
          {loading ? (
            <div className="imt-spinner"><div className="imt-spinner-icon" /><span>Loading IndiaMart data…</span></div>
          ) : data.length === 0 ? (
            <div className="imt-empty">
              <div style={{ fontSize: 40, opacity: 0.3 }}>🏭</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#64748b" }}>No products found. Adjust your search or filters.</div>
            </div>
          ) : (
            <table className="imt-table">
              <thead>
                <tr>
                  {COLUMNS.map(col => (
                    <th key={col.key} style={{ minWidth: col.width }} onClick={() => toggleSort(col.key)}>
                      {col.label} {sortField === col.key ? (sortDir === "asc" ? "↑" : "↓") : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedData.map((row, i) => (
                  <tr key={row.id || i}>
                    <td style={{ color: "#94a3b8", fontWeight: 600, fontSize: 11 }}>{row.id}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 10, color: "#64748b" }}>{row.asin || <span className="no-data">—</span>}</td>
                    <td className="name-cell" title={row.name}>{row.name || <span className="no-data">—</span>}</td>
                    <td>
                      <span style={{ background: "#dbeafe", color: "#1d4ed8", padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 600, whiteSpace: "nowrap" }}>
                        {row.category || <span className="no-data">—</span>}
                      </span>
                    </td>
                    <td style={{ fontSize: 11, color: "#64748b" }}>{row.sub_category || <span className="no-data">—</span>}</td>
                    <td className="price-tag">{fmtPrice(row)}</td>
                    <td><Stars val={row.stars} /></td>
                    <td style={{ fontWeight: 600 }}>{row.reviews > 0 ? row.reviews.toLocaleString() : <span className="no-data">—</span>}</td>
                    <td style={{ fontWeight: 600 }}>{row.manufacturer || <span className="no-data">—</span>}</td>
                    <td style={{ fontSize: 11 }}>
                      {row.location
                        ? <span style={{ background: "#f0fdf4", color: "#16a34a", padding: "2px 7px", borderRadius: 99, fontSize: 10, fontWeight: 600 }}>{row.location}</span>
                        : <span className="no-data">—</span>}
                    </td>
                    <td style={{ fontSize: 11, color: "#64748b" }}>{row.contact_number || <span className="no-data">—</span>}</td>
                    <td>
                      {row.badges
                        ? <span style={{ fontSize: 10, color: "#7c3aed", background: "#ede9fe", padding: "2px 7px", borderRadius: 99 }}>{row.badges.split(",")[0]}</span>
                        : <span className="no-data">—</span>}
                    </td>
                    <td>
                      {row.link
                        ? <a href={row.link} target="_blank" rel="noreferrer" style={{ color: "#0084ff", fontWeight: 600, fontSize: 11 }}>View ↗</a>
                        : <span className="no-data">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div className="imt-pagination">
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