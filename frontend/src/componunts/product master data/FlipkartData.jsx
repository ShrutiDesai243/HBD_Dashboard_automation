import React, { useState, useEffect, useCallback } from 'react';
import api from '../../utils/Api';

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  
  .fk-root {
    font-family: 'Inter', sans-serif;
    background: #f0f4f8;
    min-height: 100vh;
    padding: 24px;
    color: #1a202c;
  }

  .fk-header {
    background: linear-gradient(135deg, #2874f0 0%, #1e56b3 100%);
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    box-shadow: 0 4px 20px rgba(40, 116, 240, 0.15);
  }

  .fk-header h1 {
    font-size: 24px;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .fk-header p {
    font-size: 13px;
    opacity: 0.85;
    margin: 4px 0 0 0;
  }

  .fk-badge {
    background: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 99px;
    padding: 4px 14px;
    font-size: 11px;
    font-weight: 700;
  }

  .fk-controls {
    background: #fff;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 24px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    align-items: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
    border: 1px solid #e2e8f0;
  }

  .fk-search-group {
    flex: 1;
    min-width: 260px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .fk-search-group label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: #718096;
    letter-spacing: 0.5px;
  }

  .fk-input-wrapper {
    display: flex;
    align-items: center;
    border: 1.5px solid #cbd5e0;
    border-radius: 10px;
    padding: 8px 14px;
    transition: all 0.2s;
    background: #fff;
  }

  .fk-input-wrapper:focus-within {
    border-color: #2874f0;
    box-shadow: 0 0 0 3px rgba(40, 116, 240, 0.12);
  }

  .fk-input-wrapper input {
    border: none;
    outline: none;
    font-size: 13px;
    width: 100%;
    font-family: inherit;
    color: #2d3748;
  }

  .fk-select {
    padding: 10px 14px;
    border-radius: 10px;
    border: 1.5px solid #cbd5e0;
    font-size: 13px;
    font-weight: 600;
    color: #4a5568;
    outline: none;
    font-family: inherit;
    background: #fff;
    cursor: pointer;
    min-width: 100px;
  }

  .fk-select:focus {
    border-color: #2874f0;
  }

  .fk-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 20px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    border: none;
    font-family: inherit;
    transition: all 0.2s;
    white-space: nowrap;
    align-self: flex-end;
    margin-bottom: 2px;
  }

  .fk-btn-blue {
    background: linear-gradient(135deg, #2874f0, #1e56b3);
    color: #fff;
    box-shadow: 0 4px 12px rgba(40, 116, 240, 0.2);
  }

  .fk-btn-blue:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(40, 116, 240, 0.3);
  }

  .fk-btn-ghost {
    background: #edf2f7;
    color: #4a5568;
  }

  .fk-btn-ghost:hover {
    background: #e2e8f0;
  }

  .fk-table-card {
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.03);
    overflow: hidden;
    border: 1px solid #e2e8f0;
  }

  .fk-table-wrap {
    overflow-x: auto;
  }

  .fk-table {
    width: 100%;
    border-collapse: collapse;
    min-width: 900px;
  }

  .fk-table thead th {
    padding: 14px 20px;
    text-align: left;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #718096;
    background: #f7fafc;
    border-bottom: 1px solid #edf2f7;
    white-space: nowrap;
  }

  .fk-table tbody tr {
    border-bottom: 1px solid #f7fafc;
    transition: background 0.15s;
  }

  .fk-table tbody tr:hover {
    background: #f0f7ff;
  }

  .fk-table tbody td {
    padding: 14px 20px;
    font-size: 13px;
    color: #2d3748;
    vertical-align: middle;
  }

  .fk-img-cell {
    width: 50px;
    height: 50px;
    object-fit: contain;
    border-radius: 8px;
    background: #f7fafc;
    border: 1px solid #edf2f7;
    padding: 2px;
  }

  .fk-name-cell {
    max-width: 320px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 600;
    color: #2d3748;
  }

  .fk-price-bold {
    font-weight: 800;
    color: #1a202c;
  }

  .fk-mrp-strike {
    text-decoration: line-through;
    color: #a0aec0;
    font-size: 11px;
    margin-left: 4px;
  }

  .fk-discount-badge {
    background: #e6fffa;
    color: #319795;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 11px;
    font-weight: 700;
    border: 1px solid #b2f5ea;
  }

  .fk-rating-badge {
    background: #fefcbf;
    color: #b7791f;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 11px;
    font-weight: 700;
    border: 1px solid #fef08a;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .fk-action-link {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    background: #ffe11b;
    color: #212121;
    font-size: 12px;
    font-weight: 700;
    border-radius: 6px;
    text-decoration: none;
    transition: background 0.2s;
    box-shadow: 0 2px 4px rgba(255,225,27,0.25);
  }

  .fk-action-link:hover {
    background: #fdd835;
  }

  .fk-pagination {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    border-top: 1px solid #edf2f7;
    background: #f7fafc;
  }

  .fk-pagination .info {
    font-size: 13px;
    color: #4a5568;
  }

  .fk-pagination .btns {
    display: flex;
    gap: 8px;
  }

  .fk-pagination button {
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    border: 1.5px solid #e2e8f0;
    background: #fff;
    cursor: pointer;
    transition: all 0.15s;
    color: #4a5568;
  }

  .fk-pagination button:hover:not(:disabled) {
    background: #2874f0;
    color: #fff;
    border-color: #2874f0;
  }

  .fk-pagination button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .fk-pagination .page-info {
    font-size: 13px;
    font-weight: 700;
    color: #1a202c;
    padding: 8px 12px;
  }

  .fk-spinner {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 80px;
    gap: 12px;
    color: #718096;
    font-size: 14px;
    font-weight: 600;
  }

  .fk-spinner-icon {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 3px solid #cbd5e0;
    border-top-color: #2874f0;
    animation: fk-spin 0.8s linear infinite;
  }

  @keyframes fk-spin {
    to { transform: rotate(360deg); }
  }

  .fk-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px;
    gap: 12px;
    color: #718096;
  }

  .fk-empty .icon {
    font-size: 48px;
    opacity: 0.3;
  }

  .fk-empty .msg {
    font-size: 14px;
    font-weight: 600;
  }
`;

export default function FlipkartData() {
  // ==== State ====
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  
  // Search parameters
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);
  
  const [searchInput, setSearchInput] = useState("");
  const [categoryInput, setCategoryInput] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("");

  // ==== Fetch Data Callback ====
  const fetchData = useCallback(async (pg = 1, lim = limit, searchVal = activeSearch, catVal = activeCategory) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: pg,
        limit: lim
      });
      if (searchVal.trim()) {
        params.append("search", searchVal.trim());
      }
      if (catVal.trim()) {
        params.append("category", catVal.trim());
      }
      
      const res = await api.get(`/flipkart/fetch-data?${params.toString()}`);
      if (res.data && res.data.status === "success") {
        setData(res.data.data || []);
        setTotalPages(res.data.total_pages || 1);
        setTotalCount(res.data.total_count || 0);
        setPage(pg);
      }
    } catch (err) {
      console.error("Error fetching Flipkart products:", err);
    } finally {
      setLoading(false);
    }
  }, [limit, activeSearch, activeCategory]);

  // Initial load
  useEffect(() => {
    fetchData(1);
    fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8001"}/api/flipkart-products`) // CHANGE THIS URL to your specific API endpoint
      .then((response) => response.json())
      .then((data) => {
        setProducts(data);
        setLoading(false);
      })
      .catch((error) => {
        console.error("Error fetching data:", error);
        setLoading(false);
      });
  }, []);

  // ==== Event Handlers ====
  const handleSearch = () => {
    setActiveSearch(searchInput);
    setActiveCategory(categoryInput);
    fetchData(1, limit, searchInput, categoryInput);
  };

  const handleReset = () => {
    setSearchInput("");
    setCategoryInput("");
    setActiveSearch("");
    setActiveCategory("");
    fetchData(1, limit, "", "");
  };

  const handleLimitChange = (e) => {
    const nextLimit = parseInt(e.target.value);
    setLimit(nextLimit);
    fetchData(1, nextLimit, activeSearch, activeCategory);
  };

  // Pagination bounds
  const startIdx = (page - 1) * limit + 1;
  const endIdx = Math.min(page * limit, totalCount);

  return (
    <div className="fk-root">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      {/* Header Banner */}
      <div className="fk-header">
        <div>
          <h1>📦 Flipkart Product Master</h1>
          <p>Local database · {totalCount.toLocaleString("en-IN")} products matched</p>
        </div>
        <span className="fk-badge">⚡ Live Sync Enabled</span>
      </div>

      {/* Control / Filter Bar */}
      <div className="fk-controls">
        <div className="fk-search-group">
          <label>Product Name</label>
          <div className="fk-input-wrapper">
            <input 
              type="text" 
              placeholder="Search by product name..." 
              value={searchInput} 
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
        </div>

        <div className="fk-search-group">
          <label>Category (Leaf)</label>
          <div className="fk-input-wrapper">
            <input 
              type="text" 
              placeholder="Search by leaf category (e.g. headphones)..." 
              value={categoryInput} 
              onChange={(e) => setCategoryInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
        </div>

        <div className="fk-search-group" style={{ flex: '0 0 auto', minWidth: '100px' }}>
          <label>Page Size</label>
          <select className="fk-select" value={limit} onChange={handleLimitChange}>
            <option value={10}>10 rows</option>
            <option value={25}>25 rows</option>
            <option value={50}>50 rows</option>
            <option value={100}>100 rows</option>
          </select>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignSelf: 'flex-end', height: '40px' }}>
          <button className="fk-btn fk-btn-blue" onClick={handleSearch}>
            🔍 Search
          </button>
          <button className="fk-btn fk-btn-ghost" onClick={handleReset}>
            🔄 Reset
          </button>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="fk-table-card">
        {loading ? (
          <div className="fk-spinner">
            <div className="fk-spinner-icon"></div>
            <span>Loading Flipkart products...</span>
          </div>
        ) : data.length === 0 ? (
          <div className="fk-empty">
            <div className="fk-icon">📭</div>
            <div className="fk-msg">No products found matching your search.</div>
          </div>
        ) : (
          <>
            <div className="fk-table-wrap">
              <table className="fk-table">
                <thead>
                  <tr>
                    <th>Image</th>
                    <th>Product Details</th>
                    <th>Brand</th>
                    <th>Category</th>
                    <th>Price &amp; MRP</th>
                    <th>Discount</th>
                    <th>Rating</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <img 
                          className="fk-img-cell" 
                          src={item.image_url || 'https://via.placeholder.com/50?text=No+Img'} 
                          alt={item.name} 
                          onError={(e) => {
                            e.target.onerror = null; 
                            e.target.src = 'https://via.placeholder.com/50?text=No+Img';
                          }}
                        />
                      </td>
                      <td>
                        <div className="fk-name-cell" title={item.name}>
                          {item.name}
                        </div>
                        <div style={{ fontSize: '11px', color: '#718096', marginTop: '3px' }}>
                          ID: <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{item.asin}</span>
                        </div>
                      </td>
                      <td>
                        <span style={{ fontWeight: 600, color: '#4a5568' }}>
                          {item.brand || 'N/A'}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: '12px', background: '#edf2f7', padding: '3px 8px', borderRadius: '4px', color: '#4a5568' }}>
                          {item.category || 'Uncategorized'}
                        </span>
                      </td>
                      <td>
                        <span className="fk-price-bold">
                          {item.price ? `₹${parseFloat(item.price).toLocaleString("en-IN")}` : 'N/A'}
                        </span>
                        {item.list_price && (
                          <span className="fk-mrp-strike">
                            ₹{parseFloat(item.list_price).toLocaleString("en-IN")}
                          </span>
                        )}
                      </td>
                      <td>
                        {item.discount ? (
                          <span className="fk-discount-badge">{item.discount} OFF</span>
                        ) : (
                          <span style={{ color: '#a0aec0' }}>N/A</span>
                        )}
                      </td>
                      <td>
                        {item.stars ? (
                          <span className="fk-rating-badge">
                            {item.stars} ★
                          </span>
                        ) : (
                          <span style={{ color: '#a0aec0' }}>N/A</span>
                        )}
                      </td>
                      <td>
                        {item.link ? (
                          <a 
                            className="fk-action-link" 
                            href={item.link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                          >
                            Buy On Flipkart
                          </a>
                        ) : (
                          <span style={{ color: '#a0aec0' }}>No Link</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="fk-pagination">
              <div className="info">
                Showing <span style={{ fontWeight: 600 }}>{startIdx}</span> to{' '}
                <span style={{ fontWeight: 600 }}>{endIdx}</span> of{' '}
                <span style={{ fontWeight: 600 }}>{totalCount.toLocaleString("en-IN")}</span> products
              </div>
              <div className="btns">
                <button 
                  onClick={() => fetchData(1, limit, activeSearch, activeCategory)} 
                  disabled={page === 1}
                >
                  ⏮ First
                </button>
                <button 
                  onClick={() => fetchData(page - 1, limit, activeSearch, activeCategory)} 
                  disabled={page === 1}
                >
                  ◀ Prev
                </button>
                <span className="page-info">
                  Page {page} of {totalPages}
                </span>
                <button 
                  onClick={() => fetchData(page + 1, limit, activeSearch, activeCategory)} 
                  disabled={page === totalPages}
                >
                  Next ▶
                </button>
                <button 
                  onClick={() => fetchData(totalPages, limit, activeSearch, activeCategory)} 
                  disabled={page === totalPages}
                >
                  Last ⏭
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}