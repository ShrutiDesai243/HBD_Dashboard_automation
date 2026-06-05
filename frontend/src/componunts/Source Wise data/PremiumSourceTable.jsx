import React from "react";

/**
 * PremiumSourceTable component
 * Renders a premium, responsive data table with search, filters, pagination,
 * and database export hooks matching the Japanese Zen-inspired design.
 */
export function PremiumSourceTable({
  title,
  subtitle,
  columns,
  pageData = [],
  loading = false,
  currentPage = 1,
  pageSize = 10,
  totalPages = 1,
  totalRecords = 0,
  error = null,
  onPageChange,
  onPageSizeChange,
  search = "",
  onSearchChange,
  city = "",
  onCityChange,
  state = "",
  onStateChange,
  category = "",
  onCategoryChange,
  status = "",
  onStatusChange,
  activeSourceId,
  onActiveSourceChange,
  allSources = [],
  onExportCSV,
  onExportExcel,
  onExportPDF,
  onRefresh,
}) {
  // Determine if specific fields are present in the columns to conditionally show filters
  const hasStateCol = columns.some((col) => col.key.toLowerCase().includes("state"));
  const hasCategoryCol = columns.some((col) => col.key.toLowerCase().includes("category"));
  const hasStatusCol = columns.some((col) => col.key.toLowerCase().includes("status"));

  return (
    <div className="rd-matrix-card" style={{ transition: "background 0.3s, border-color 0.3s" }}>
      {/* 1. Header Bar */}
      <div
        style={{
          padding: "24px 28px",
          borderBottom: "1.5px solid var(--card-border)",
          background: "var(--matrix-header)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div>
          <h2 style={{ fontFamily: "'Outfit', sans-serif", fontSize: 18, fontWeight: 900, color: "var(--text-primary)" }}>
            {title}
          </h2>
          <p style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 500, marginTop: 4 }}>
            {subtitle}
          </p>
        </div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {onRefresh && (
            <button className="rd-btn rd-btn-ghost" onClick={onRefresh} disabled={loading} style={{ border: "1px solid var(--card-border)" }}>
              🔄 Refresh
            </button>
          )}
          {onExportExcel && (
            <button className="rd-btn rd-btn-green" onClick={onExportExcel} disabled={loading || !pageData.length}>
              📊 Export Excel
            </button>
          )}
          {onExportCSV && (
            <button className="rd-btn rd-btn-green" onClick={onExportCSV} disabled={loading || !pageData.length}>
              📋 Export CSV
            </button>
          )}
          {onExportPDF && (
            <button className="rd-btn rd-btn-primary" onClick={onExportPDF} disabled={loading || !pageData.length}>
              📄 PDF Print
            </button>
          )}
        </div>
      </div>

      {/* 2. Slicers & Filters Row */}
      <div
        style={{
          padding: "18px 28px",
          borderBottom: "1.5px solid var(--card-border)",
          background: "var(--bg-secondary)",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
        }}
      >
        {/* Source Selector */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase", color: "var(--text-secondary)", letterSpacing: 0.5 }}>
            Select Source Table
          </label>
          <select
            value={activeSourceId}
            onChange={(e) => onActiveSourceChange(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              border: "1.5px solid var(--card-border)",
              background: "var(--bg-primary)",
              color: "var(--text-primary)",
              fontSize: 11,
              fontWeight: 700,
              outline: "none",
              cursor: "pointer",
            }}
          >
            {allSources.map((src) => (
              <option key={src.id} value={src.id}>
                {src.icon} {src.name}
              </option>
            ))}
          </select>
        </div>

        {/* Global Search Input */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase", color: "var(--text-secondary)", letterSpacing: 0.5 }}>
            Search Key Fields
          </label>
          <input
            type="text"
            placeholder="Search name, phone, etc..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              border: "1.5px solid var(--card-border)",
              background: "var(--bg-primary)",
              color: "var(--text-primary)",
              fontSize: 11,
              fontWeight: 600,
              outline: "none",
            }}
          />
        </div>

        {/* City Filter */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase", color: "var(--text-secondary)", letterSpacing: 0.5 }}>
            Filter by City
          </label>
          <input
            type="text"
            placeholder="e.g. Mumbai, Delhi..."
            value={city}
            onChange={(e) => onCityChange(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              border: "1.5px solid var(--card-border)",
              background: "var(--bg-primary)",
              color: "var(--text-primary)",
              fontSize: 11,
              fontWeight: 600,
              outline: "none",
            }}
          />
        </div>

        {/* State Filter (Conditional) */}
        {hasStateCol && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase", color: "var(--text-secondary)", letterSpacing: 0.5 }}>
              Filter by State
            </label>
            <input
              type="text"
              placeholder="e.g. Maharashtra..."
              value={state}
              onChange={(e) => onStateChange(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                border: "1.5px solid var(--card-border)",
                background: "var(--bg-primary)",
                color: "var(--text-primary)",
                fontSize: 11,
                fontWeight: 600,
                outline: "none",
              }}
            />
          </div>
        )}

        {/* Category Filter (Conditional) */}
        {hasCategoryCol && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase", color: "var(--text-secondary)", letterSpacing: 0.5 }}>
              Filter by Category
            </label>
            <input
              type="text"
              placeholder="e.g. ATM, School..."
              value={category}
              onChange={(e) => onCategoryChange(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                border: "1.5px solid var(--card-border)",
                background: "var(--bg-primary)",
                color: "var(--text-primary)",
                fontSize: 11,
                fontWeight: 600,
                outline: "none",
              }}
            />
          </div>
        )}

        {/* Status Filter (Conditional) */}
        {hasStatusCol && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase", color: "var(--text-secondary)", letterSpacing: 0.5 }}>
              Filter by Status
            </label>
            <select
              value={status}
              onChange={(e) => onStatusChange(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                border: "1.5px solid var(--card-border)",
                background: "var(--bg-primary)",
                color: "var(--text-primary)",
                fontSize: 11,
                fontWeight: 700,
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="">All Status</option>
              <option value="completed">Completed</option>
              <option value="pending">Pending</option>
              <option value="critical">Critical</option>
              <option value="processing">Processing</option>
            </select>
          </div>
        )}
      </div>

      {/* 3. Table Content */}
      <div style={{ position: "relative", overflowX: "auto" }}>
        {loading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(255,255,255,0.7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              gap: 12,
              zIndex: 10,
              transition: "background 0.3s",
            }}
            className="dark-mode-overlay"
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "50%",
                border: "3px solid #e2e8f0",
                borderTopColor: "var(--accent)",
                animation: "spin 0.75s linear infinite",
              }}
            />
            <span style={{ fontSize: 11, fontWeight: 800, color: "var(--text-primary)", letterSpacing: 0.5 }}>
              FETCHING LIVE MASTER RECORDS...
            </span>
            <style>{`
              @keyframes spin { to { transform: rotate(360deg); } }
              .rd-root.dark-mode .dark-mode-overlay { background: rgba(20,26,34,0.7) !important; }
            `}</style>
          </div>
        )}

        <table className="rd-matrix-table">
          <thead>
            <tr>
              <th style={{ width: "5%" }}>#</th>
              {columns.map((col) => (
                <th key={col.key} style={{ width: col.width || "auto" }}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {error ? (
              <tr>
                <td colSpan={columns.length + 1} style={{ textAlign: "center", padding: 48, color: "#f43f5e", fontWeight: 700 }}>
                  ⚠️ {error}
                </td>
              </tr>
            ) : pageData.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 1} style={{ textAlign: "center", padding: 48, color: "var(--text-secondary)", fontWeight: 750 }}>
                  No matching database records found for this query.
                </td>
              </tr>
            ) : (
              pageData.map((row, idx) => {
                const globalIdx = (currentPage - 1) * pageSize + idx + 1;
                return (
                  <tr key={idx}>
                    <td style={{ fontWeight: 800, color: "var(--text-secondary)" }}>{globalIdx}</td>
                    {columns.map((col) => (
                      <td key={col.key} style={{ color: "var(--text-primary)" }}>
                        {row[col.key] !== undefined && row[col.key] !== null ? String(row[col.key]) : "—"}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 4. Footer & Pagination Bar */}
      {!error && pageData.length > 0 && (
        <div
          style={{
            padding: "16px 28px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderTop: "1.5px solid var(--card-border)",
            background: "var(--matrix-header)",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          {/* Page size & entries count */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)" }}>
              Showing {Math.min(totalRecords, (currentPage - 1) * pageSize + 1)} to {Math.min(totalRecords, currentPage * pageSize)} of {totalRecords.toLocaleString()} records
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)" }}>Show:</span>
              <select
                value={pageSize}
                onChange={(e) => onPageSizeChange(Number(e.target.value))}
                style={{
                  padding: "4px 8px",
                  borderRadius: 8,
                  border: "1.5px solid var(--card-border)",
                  background: "var(--bg-secondary)",
                  color: "var(--text-primary)",
                  fontSize: 11,
                  fontWeight: 700,
                  outline: "none",
                  cursor: "pointer",
                }}
              >
                <option value={10}>10 entries</option>
                <option value={20}>20 entries</option>
                <option value={50}>50 entries</option>
                <option value={100}>100 entries</option>
              </select>
            </div>
          </div>

          {/* Pagination buttons */}
          {totalPages > 1 && (
            <div style={{ display: "flex", gap: 6 }}>
              <button
                onClick={() => onPageChange(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1 || loading}
                style={{
                  padding: "6px 12px",
                  border: "1.5px solid var(--card-border)",
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: currentPage === 1 ? "not-allowed" : "pointer",
                  background: currentPage === 1 ? "var(--bg-primary)" : "var(--bg-secondary)",
                  color: currentPage === 1 ? "var(--text-secondary)" : "var(--text-primary)",
                }}
              >
                Previous
              </button>
              {(() => {
                // Render limited page numbers for sleek display
                const pages = [];
                const range = 2; // numbers before and after current
                for (let i = 1; i <= totalPages; i++) {
                  if (i === 1 || i === totalPages || (i >= currentPage - range && i <= currentPage + range)) {
                    pages.push(i);
                  } else if (pages[pages.length - 1] !== "...") {
                    pages.push("...");
                  }
                }
                return pages.map((page, index) => {
                  if (page === "...") {
                    return (
                      <span key={`ellipsis-${index}`} style={{ padding: "6px 8px", color: "var(--text-secondary)", fontSize: 11, fontWeight: 700 }}>
                        ...
                      </span>
                    );
                  }
                  return (
                    <button
                      key={page}
                      onClick={() => onPageChange(page)}
                      disabled={loading}
                      style={{
                        padding: "6px 12px",
                        border: "1.5px solid",
                        borderRadius: 8,
                        fontSize: 11,
                        fontWeight: 700,
                        cursor: "pointer",
                        borderColor: currentPage === page ? "var(--accent)" : "var(--card-border)",
                        background: currentPage === page ? "var(--accent)" : "var(--bg-secondary)",
                        color: currentPage === page ? "#fff" : "var(--text-primary)",
                      }}
                    >
                      {page}
                    </button>
                  );
                });
              })()}
              <button
                onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage === totalPages || loading}
                style={{
                  padding: "6px 12px",
                  border: "1.5px solid var(--card-border)",
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: currentPage === totalPages ? "not-allowed" : "pointer",
                  background: currentPage === totalPages ? "var(--bg-primary)" : "var(--bg-secondary)",
                  color: currentPage === totalPages ? "var(--text-secondary)" : "var(--text-primary)",
                }}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default PremiumSourceTable;
