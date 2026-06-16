import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Button,
  Spinner
} from "@material-tailwind/react";
import React, { useState, useEffect } from "react";
import api from "../../utils/Api"; 

/* ---------------- CONFIG ---------------- */
const TABLE_HEADERS = [
  "id",
  "marketplace_name",
  "asin",
  "product_name",
  "brand",
  "price",
  "list_price",
  "stars",
  "reviews",
  "availability",
  "category_name",
  "manufacturer",
  "is_best_seller",
  "product_url",
  "img_url"
];

/* ---------------- COMPONENT ---------------- */

const ProductCategory = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Search States aligning with product_master params
  const [searchName, setSearchName] = useState("");
  const [searchCategory, setSearchCategory] = useState("");
  const [searchSource, setSearchSource] = useState("");
  
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const [error, setError] = useState(null);

  const limit = 15; 

  /* ---------------- API FETCH ---------------- */
  useEffect(() => {
    fetchData();
  }, [currentPage, searchName, searchCategory, searchSource]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get("/product-master/fetch-data", {
        params: {
          page: currentPage,
          limit: limit,
          name: searchName,
          category: searchCategory,
          source: searchSource,
        },
      });

      const result = response.data;
      setData(result.data || []);
      setTotalPages(result.total_pages || 1);
      setTotalRecords(result.total_count || 0);
    } catch (err) {
      console.error("Fetch Error:", err);
      setError("Failed to fetch product master data.");
    } finally {
      setLoading(false);
    }
  };

  /* ---------------- CSV EXPORT ---------------- */
  const exportCSV = () => {
    if (!data.length) return;
    const rows = [
      TABLE_HEADERS,
      ...data.map((row) => TABLE_HEADERS.map((h) => `"${String(row[h] ?? "").replace(/"/g, "'")}"`)),
    ];

    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "product_master.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mt-8 px-4">
      <Card className="border border-gray-200 shadow-sm rounded-xl bg-white">
        
        {/* ---------- HEADER ---------- */}
        <CardHeader
          floated={false}
          shadow={false}
          className="bg-gray-100 border-b border-gray-300 px-6 py-4 rounded-t-xl"
        >
          <div className="flex flex-col md:flex-row gap-4 md:items-center md:justify-between mb-4">
            <div>
              <Typography variant="h5" className="text-gray-800 font-semibold leading-tight">
                Product Master Data
              </Typography>
              <Typography color="gray" className="mt-1 font-normal text-sm">
                Showing {data.length} of {totalRecords.toLocaleString()} records
              </Typography>
            </div>
            
            <Button onClick={exportCSV} color="green" size="sm" className="whitespace-nowrap">
              Export CSV Page
            </Button>
          </div>

          {/* ---------- MULTI-SEARCH BARS ---------- */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
              type="text"
              placeholder="Search by Product Name..."
              className="border rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={searchName}
              onChange={(e) => {
                setSearchName(e.target.value);
                setCurrentPage(1); 
              }}
            />
            <input
              type="text"
              placeholder="Search by Category..."
              className="border rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={searchCategory}
              onChange={(e) => {
                setSearchCategory(e.target.value);
                setCurrentPage(1);
              }}
            />
            <select
              value={searchSource}
              onChange={(e) => {
                setSearchSource(e.target.value);
                setCurrentPage(1);
              }}
              className="border border-gray-300 rounded-lg px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Sources</option>
              <option value="amazon">Amazon</option>
              <option value="flipkart">Flipkart</option>
              <option value="bigbasket">BigBasket</option>
              <option value="jio-mart">Jio Mart</option>
              <option value="d-mart">D-Mart</option>
            </select>
          </div>
        </CardHeader>

        {/* ---------- ERROR STATE ---------- */}
        {error && <div className="p-4 text-red-500 font-medium text-center">{error}</div>}

        {/* ---------- TABLE ---------- */}
        <CardBody className="px-0 pt-0 pb-2 overflow-x-auto">
          {loading ? (
            <div className="flex flex-col justify-center py-20 items-center gap-3">
              <Spinner className="h-10 w-10 text-blue-500" />
              <Typography className="animate-pulse text-gray-600 font-medium">
                Loading Data...
              </Typography>
            </div>
          ) : (
            <table className="w-full min-w-max table-auto text-left">
              <thead className="sticky top-0 bg-gray-50 z-10">
                <tr>
                  {TABLE_HEADERS.map((head) => (
                    <th
                      key={head}
                      className="px-4 py-3 border-b text-xs font-semibold uppercase text-gray-600 bg-gray-100"
                    >
                      {head.replace(/_/g, " ")} 
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {data.length === 0 ? (
                  <tr>
                    <td colSpan={TABLE_HEADERS.length} className="text-center py-10 text-gray-400">
                      No records found
                    </td>
                  </tr>
                ) : (
                  data.map((item, idx) => (
                    <tr key={item.id || idx} className="hover:bg-gray-50 transition border-b">
                      {TABLE_HEADERS.map((key) => (
                        <td
                          key={key}
                          title={item[key]}
                          className="px-4 py-3 text-sm text-gray-700 max-w-[220px] truncate"
                        >
                          {key === "product_url" || key === "img_url" ? (
                            item[key] ? (
                              <a
                                href={item[key]}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-500 font-semibold underline hover:text-blue-700"
                              >
                                View Link
                              </a>
                            ) : (
                              "-"
                            )
                          ) : key === "price" || key === "list_price" ? (
                            item[key] != null ? `₹${Number(item[key]).toFixed(2)}` : "-"
                          ) : key === "is_best_seller" ? (
                            item[key] ? "Yes" : "No"
                          ) : (
                            item[key] !== null && item[key] !== undefined ? String(item[key]) : "-"
                          )}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      {/* ---------- SERVER-SIDE PAGINATION ---------- */}
      {!loading && totalPages > 0 && (
        <div className="flex justify-center items-center gap-2 mt-6 flex-wrap pb-6">
          <Button
            size="sm"
            variant="outlined"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => p - 1)}
          >
            Prev
          </Button>

          <span className="text-sm text-gray-600 px-4 font-medium">
            Page {currentPage} of {totalPages}
          </span>

          <Button
            size="sm"
            variant="outlined"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
};

export default ProductCategory;