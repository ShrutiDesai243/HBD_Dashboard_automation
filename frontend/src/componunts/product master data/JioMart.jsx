import React, { useEffect, useMemo, useState, useCallback } from "react";
import api from "../../utils/Api";
import * as XLSX from "xlsx/dist/xlsx.full.min.js";

const COLUMNS = [
  { key: "sku_id", label: "SKU ID", width: 130 },
  { key: "name", label: "Product Name", width: 320 },
  { key: "brand", label: "Brand", width: 120 },
  { key: "category", label: "Category", width: 160 },
  { key: "price", label: "Price (₹)", width: 100 },
  { key: "mrp", label: "MRP (₹)", width: 100 },
  { key: "discount", label: "Discount", width: 90 },
  { key: "quantity", label: "Quantity", width: 100 },
  { key: "size", label: "Size", width: 90 },
  { key: "availability", label: "Stock", width: 90 },
  { key: "product_url", label: "Product URL", width: 200 },
];

const JioMartData = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState([]);
  const [categories, setCategories] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sortField, setSortField] = useState(null);
  const [sortOrder, setSortOrder] = useState("asc");
  const [error, setError] = useState(null);
  const limit = 50;

  // Fetch categories
  useEffect(() => {
    api.get("/product-report/mapping/jiomart")
      .then(r => {
        const cats = (r.data?.data || []).map(c => c.category_name).filter(Boolean).sort();
        setCategories(cats);
      })
      .catch(() => setCategories([]));
  }, []);

  // Fetch data from live API
  const fetchData = useCallback((page = 1, search = "", category = "") => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page, limit });
    if (search) params.set("search", search);
    if (category) params.set("category", category);
    api.get(`/product-report/jiomart/data?${params.toString()}`)
      .then(r => {
        if (r.data?.status === "success") {
          setData(r.data.data || []);
          setTotalPages(r.data.total_pages || 1);
          setTotalCount(r.data.total_count || 0);
        } else {
          setError(r.data?.message || "Failed to load data");
        }
      })
      .catch(e => {
        setError(e.message || "Network error");
      })
      .finally(() => setLoading(false));
  }, [limit]);

  useEffect(() => {
    fetchData(currentPage, appliedSearch, categoryFilter);
  }, [currentPage, appliedSearch, categoryFilter, fetchData]);

  const handleSearch = () => {
    setCurrentPage(1);
    setAppliedSearch(search);
  };

  const handleCategoryChange = (cat) => {
    setCategoryFilter(cat);
    setCurrentPage(1);
  };

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(o => o === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  const sortedData = useMemo(() => {
    if (!sortField) return data;
    return [...data].sort((a, b) => {
      const A = a[sortField] ?? "";
      const B = b[sortField] ?? "";
      if (!isNaN(A) && !isNaN(B) && A !== "" && B !== "") {
        return sortOrder === "asc" ? A - B : B - A;
      }
      const strA = String(A).toLowerCase();
      const strB = String(B).toLowerCase();
      if (strA === strB) return 0;
      return sortOrder === "asc" ? (strA > strB ? 1 : -1) : (strA < strB ? 1 : -1);
    });
  }, [data, sortField, sortOrder]);

  const exportCSV = () => {
    const csv = sortedData.map(row => COLUMNS.map(c => `"${String(row[c.key] ?? "").replace(/"/g, "'")}"`).join(","));
    const csvContent = [COLUMNS.map(c => c.label).join(","), ...csv].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "jiomart_products.csv";
    a.click();
  };

  const exportExcel = () => {
    const wsData = [
      COLUMNS.map(c => c.label),
      ...sortedData.map(row => COLUMNS.map(c => row[c.key] ?? ""))
    ];
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "JioMart Products");
    XLSX.writeFile(wb, "jiomart_products.xlsx");
  };

  return (
    <div style={{ fontFamily: "'Inter', sans-serif", padding: "24px", background: "#f0f2f7", minHeight: "100vh" }}>
      {/* Header */}
      <div style={{
        background: "linear-gradient(135deg, #0f9d58 0%, #085c35 100%)",
        borderRadius: 20, padding: "28px 32px", marginBottom: 24,
        display: "flex", alignItems: "center", gap: 20, boxShadow: "0 8px 32px rgba(15,157,88,0.25)"
      }}>
        <div style={{ width: 52, height: 52, background: "rgba(255,255,255,0.2)", borderRadius: 16, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>🏬</div>
        <div>
          <h1 style={{ color: "#fff", fontSize: 24, fontWeight: 800, margin: 0 }}>JioMart Product Master</h1>
          <p style={{ color: "rgba(255,255,255,0.75)", margin: "4px 0 0", fontSize: 13 }}>
            Live data from database · {totalCount.toLocaleString("en-IN")} total products
          </p>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
          <button onClick={exportCSV} style={{ background: "rgba(255,255,255,0.2)", color: "#fff", border: "1px solid rgba(255,255,255,0.3)", borderRadius: 12, padding: "10px 18px", cursor: "pointer", fontWeight: 700, fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            ⬇ CSV
          </button>
          <button onClick={exportExcel} style={{ background: "rgba(255,255,255,0.25)", color: "#fff", border: "1px solid rgba(255,255,255,0.3)", borderRadius: 12, padding: "10px 18px", cursor: "pointer", fontWeight: 700, fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            📊 Excel
          </button>
        </div>
      </div>

      {/* Stats KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 14, marginBottom: 24 }}>
        {[
          { label: "Total Products", value: totalCount.toLocaleString("en-IN"), icon: "📦", color: "#0f9d58" },
          { label: "Categories", value: categories.length, icon: "🗂️", color: "#22c55e" },
          { label: "Current Page", value: `${currentPage} / ${totalPages}`, icon: "📄", color: "#16a34a" },
          { label: "Showing", value: sortedData.length, icon: "👁️", color: "#059669" },
        ].map((kpi, i) => (
          <div key={i} style={{ background: "#fff", borderRadius: 16, padding: "18px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)", borderLeft: `4px solid ${kpi.color}`, position: "relative", overflow: "hidden" }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "#94a3b8" }}>{kpi.label}</div>
            <div style={{ fontSize: 26, fontWeight: 900, color: "#1a1d2e", marginTop: 4 }}>{kpi.value}</div>
            <span style={{ position: "absolute", right: 16, top: 14, fontSize: 28, opacity: 0.1 }}>{kpi.icon}</span>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div style={{ background: "#fff", borderRadius: 16, padding: "18px 22px", marginBottom: 20, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f8fafc", border: "1.5px solid #e2e8f0", borderRadius: 10, padding: "9px 14px", flex: 1, minWidth: 220 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleSearch(); }}
            placeholder="Search products, brands, SKU..."
            style={{ border: "none", outline: "none", background: "transparent", fontSize: 12, fontWeight: 500, color: "#1a1d2e", width: "100%", fontFamily: "inherit" }}
          />
        </div>
        <button onClick={handleSearch} style={{ background: "linear-gradient(135deg, #0f9d58 0%, #085c35 100%)", color: "#fff", border: "none", borderRadius: 10, padding: "10px 20px", cursor: "pointer", fontWeight: 700, fontSize: 12 }}>
          Search
        </button>
        <select
          value={categoryFilter}
          onChange={e => handleCategoryChange(e.target.value)}
          style={{ padding: "9px 14px", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#fff", fontSize: 12, fontWeight: 600, color: "#374151", cursor: "pointer", outline: "none", fontFamily: "inherit" }}
        >
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button onClick={() => { setSearch(""); setAppliedSearch(""); setCategoryFilter(""); setCurrentPage(1); }} style={{ padding: "9px 16px", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#fff", color: "#64748b", cursor: "pointer", fontWeight: 600, fontSize: 12 }}>
          Reset
        </button>
        <button onClick={() => fetchData(currentPage, appliedSearch, categoryFilter)} style={{ padding: "9px 14px", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#fff", color: "#374151", cursor: "pointer", fontWeight: 600, fontSize: 12 }}>
          🔄 Refresh
        </button>
      </div>

      {/* Table */}
      <div style={{ background: "#fff", borderRadius: 20, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", overflow: "hidden" }}>
        <div style={{ padding: "16px 22px", borderBottom: "1px solid #f1f5f9", display: "flex", alignItems: "center", justifyContent: "space-between", background: "#fafbfc" }}>
          <span style={{ fontSize: 14, fontWeight: 800, color: "#1a1d2e" }}>🏬 JioMart Products — Live Database</span>
          <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>{totalCount.toLocaleString()} records · Page {currentPage} of {totalPages}</span>
        </div>

        {error ? (
          <div style={{ padding: "60px 0", textAlign: "center" }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>⚠️</div>
            <div style={{ fontWeight: 700, color: "#dc2626", marginBottom: 8 }}>{error}</div>
            <button onClick={() => fetchData(currentPage, appliedSearch, categoryFilter)} style={{ background: "#0f9d58", color: "#fff", border: "none", borderRadius: 10, padding: "10px 20px", cursor: "pointer", fontWeight: 700 }}>Retry</button>
          </div>
        ) : loading ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: 14 }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", border: "3px solid #e2e8f0", borderTopColor: "#0f9d58", animation: "spin 0.75s linear infinite" }} />
            <span style={{ fontSize: 13, color: "#94a3b8", fontWeight: 500 }}>Loading JioMart products…</span>
          </div>
        ) : sortedData.length === 0 ? (
          <div style={{ padding: "60px 0", textAlign: "center" }}>
            <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>🔍</div>
            <div style={{ fontWeight: 700, color: "#64748b" }}>No products found</div>
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>Try different search or reset filters</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  <th style={{ padding: "12px 18px", textAlign: "left", fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.8px", color: "#94a3b8", borderBottom: "1px solid #f1f5f9", whiteSpace: "nowrap" }}>#</th>
                  {COLUMNS.map(col => (
                    <th key={col.key} onClick={() => handleSort(col.key)} style={{
                      padding: "12px 18px", textAlign: "left", fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.8px", color: sortField === col.key ? "#0f9d58" : "#94a3b8",
                      borderBottom: "1px solid #f1f5f9", whiteSpace: "nowrap", cursor: "pointer", userSelect: "none",
                      minWidth: col.width
                    }}>
                      {col.label} {sortField === col.key ? (sortOrder === "asc" ? " ↑" : " ↓") : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedData.map((row, idx) => (
                  <tr key={row.id || idx} style={{ borderBottom: "1px solid #f8fafc", transition: "background 0.15s", cursor: "default" }}
                    onMouseEnter={e => e.currentTarget.style.background = "#f8fafc"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                  >
                    <td style={{ padding: "13px 18px", fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>{(currentPage - 1) * limit + idx + 1}</td>
                    {COLUMNS.map(col => (
                      <td key={col.key} style={{ padding: "13px 18px", fontSize: 12, fontWeight: 500, color: "#374151", verticalAlign: "middle", maxWidth: col.width, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: col.key === "name" ? "normal" : "nowrap" }}>
                        {col.key === "price" || col.key === "mrp" ? (
                          row[col.key] != null ? (
                            <span style={{ fontWeight: 700, color: "#1a1d2e" }}>
                              ₹{Number(row[col.key]).toLocaleString("en-IN")}
                            </span>
                          ) : <span style={{ color: "#94a3b8" }}>—</span>
                        ) : col.key === "discount" ? (
                          row[col.key] ? (
                            <span style={{ background: "#dcfce7", color: "#16a34a", padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 800 }}>{row[col.key]}</span>
                          ) : <span style={{ color: "#94a3b8" }}>—</span>
                        ) : col.key === "availability" ? (
                          <span style={{ background: "#dcfce7", color: "#16a34a", padding: "2px 8px", borderRadius: 6, fontSize: 9, fontWeight: 800, textTransform: "uppercase" }}>In Stock</span>
                        ) : col.key === "product_url" ? (
                          row[col.key] ? (
                            <a href={row[col.key]} target="_blank" rel="noreferrer" style={{ color: "#0f9d58", fontWeight: 600, fontSize: 11, textDecoration: "none" }}>View ↗</a>
                          ) : <span style={{ color: "#94a3b8" }}>—</span>
                        ) : col.key === "category" ? (
                          row[col.key] ? (
                            <span style={{ background: "#dcfce7", color: "#15803d", padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700 }}>{row[col.key]}</span>
                          ) : <span style={{ color: "#94a3b8" }}>—</span>
                        ) : (
                          <span title={row[col.key]}>{row[col.key] ?? "—"}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 22px", borderTop: "1px solid #f1f5f9" }}>
            <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>
              Showing {sortedData.length} of {totalCount.toLocaleString()} products
            </span>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} style={{ padding: "7px 14px", borderRadius: 8, border: "1.5px solid #e2e8f0", background: currentPage === 1 ? "#f8fafc" : "#fff", cursor: currentPage === 1 ? "not-allowed" : "pointer", fontWeight: 700, fontSize: 12, color: currentPage === 1 ? "#94a3b8" : "#374151" }}>← Prev</button>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const page = currentPage <= 3 ? i + 1 : currentPage - 2 + i;
                if (page < 1 || page > totalPages) return null;
                return (
                  <button key={page} onClick={() => setCurrentPage(page)} style={{ width: 32, height: 32, borderRadius: 8, border: "1.5px solid", borderColor: page === currentPage ? "#0f9d58" : "#e2e8f0", background: page === currentPage ? "#0f9d58" : "#fff", color: page === currentPage ? "#fff" : "#374151", fontWeight: 700, fontSize: 12, cursor: "pointer" }}>
                    {page}
                  </button>
                );
              })}
              <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} style={{ padding: "7px 14px", borderRadius: 8, border: "1.5px solid #e2e8f0", background: currentPage === totalPages ? "#f8fafc" : "#fff", cursor: currentPage === totalPages ? "not-allowed" : "pointer", fontWeight: 700, fontSize: 12, color: currentPage === totalPages ? "#94a3b8" : "#374151" }}>Next →</button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default JioMartData;