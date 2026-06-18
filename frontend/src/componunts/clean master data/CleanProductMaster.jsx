import React, { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Typography,
  Input,
  Spinner,
} from "@material-tailwind/react";
import { ChevronUpDownIcon } from "@heroicons/react/24/solid";
import * as XLSX from "xlsx/dist/xlsx.full.min.js";
import api from "../../utils/Api";

/* -------------------- Constants -------------------- */

const LIMIT = 20;

const COLUMNS = [
  { key: "asin", label: "ASIN", width: 140 },
  { key: "product_name", label: "Product Title", width: 350 },
  { key: "price", label: "Price", width: 100 },
  { key: "stars", label: "Rating", width: 90 },
  { key: "reviews", label: "Reviews", width: 110 },
  { key: "is_best_seller", label: "Best Seller", width: 120 },
  { key: "brand", label: "Brand", width: 130 },
  { key: "availability", label: "Stock Status", width: 120 },
  { key: "category_name", label: "Main Category", width: 180 },
  { key: "product_url", label: "Product Link", width: 250 },
  { key: "img_url", label: "Image Link", width: 200 },
  { key: "manufacturer", label: "Manufacturer", width: 180 },
  { key: "marketplace_name", label: "Source", width: 120 },
];

/* -------------------- Utils -------------------- */

const safeLower = (v) => String(v ?? "").toLowerCase();

const convertToCSV = (rows) => {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  const body = rows.map((r) =>
    headers.map((h) => `"${String(r[h] ?? "").replace(/"/g, "'")}"`).join(",")
  );
  return [headers.join(","), ...body].join("\n");
};

/* -------------------- Component -------------------- */

const CleanProductMaster = () => {
  const [loading, setLoading] = useState(true);
  const [pageData, setPageData] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const [search, setSearch] = useState("");
  const [categorySearch, setCategorySearch] = useState("");
  const [source, setSource] = useState("");

  const [sortField, setSortField] = useState(null);
  const [sortOrder, setSortOrder] = useState("asc");

  /* -------------------- Load Data -------------------- */

  const fetchProducts = async (page, nameQuery, categoryQuery, sourceQuery) => {
    setLoading(true);
    try {
      const response = await api.get("/product-master/fetch-data", {
        params: {
          page: page,
          limit: LIMIT,
          name: nameQuery,
          category: categoryQuery,
          source: sourceQuery
        }
      });

      const result = response.data;
      setPageData(result.data || []);
      setTotalRecords(result.total_count || 0);
      setTotalPages(result.total_pages || 1);
    } catch (err) {
      console.error("Fetch Products Error:", err);
      if (err.response?.status === 401) {
        window.location.href = "/auth/sign-in";
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts(currentPage, search, categorySearch, source);
  }, [currentPage, search, categorySearch, source]);

  // Reset to page 1 on search / filter updates
  useEffect(() => {
    setCurrentPage(1);
  }, [search, categorySearch, source]);

  /* -------------------- Sorting (Page-Level) -------------------- */

  const sortedPageData = useMemo(() => {
    if (!sortField) return pageData;

    return [...pageData].sort((a, b) => {
      // Numerical sort for specific fields
      if (sortField === "price" || sortField === "stars" || sortField === "reviews") {
        const valA = Number(a[sortField]) || 0;
        const valB = Number(b[sortField]) || 0;
        return sortOrder === "asc" ? valA - valB : valB - valA;
      }
      
      const A = safeLower(a[sortField]);
      const B = safeLower(b[sortField]);
      if (A === B) return 0;
      return sortOrder === "asc" ? (A > B ? 1 : -1) : A < B ? 1 : -1;
    });
  }, [pageData, sortField, sortOrder]);

  /* -------------------- Actions -------------------- */

  const toggleSort = (field) => {
    if (field === sortField) {
      setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  const downloadCSV = () => {
    if (!pageData.length) return;
    const csv = convertToCSV(pageData);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "product_page.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadExcel = () => {
    if (!pageData.length) return;
    const ws = XLSX.utils.json_to_sheet(pageData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Products");
    XLSX.writeFile(wb, "product_page.xlsx");
  };

  /* -------------------- UI -------------------- */

  return (
    <div className="min-h-screen mt-8 mb-12 px-4 bg-white text-black">
      <div className="flex justify-between items-center mb-4">
        <div>
          <Typography variant="h4" className="pb-1 text-gray-800">
            Clean Product Master Data
          </Typography>
          <Typography variant="small" className="text-gray-500 font-normal">
            Viewing records directly from the database `product_master` ({totalRecords.toLocaleString()} total rows).
          </Typography>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={downloadCSV}>CSV Page</Button>
          <Button size="sm" onClick={downloadExcel}>Excel Page</Button>
        </div>
      </div>

      <Card className="border border-gray-250 shadow-sm rounded-xl overflow-hidden bg-white">
        <CardHeader className="flex flex-wrap justify-between items-center gap-3 p-4 bg-gray-50 border-b border-gray-200">
          <div className="flex flex-wrap gap-2 w-full md:w-auto">
            <div className="w-64">
              <Input
                label="Search Name"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="w-64">
              <Input
                label="Search Category"
                value={categorySearch}
                onChange={(e) => setCategorySearch(e.target.value)}
              />
            </div>
            <div>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 bg-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">All Sources</option>
                <option value="amazon">Amazon</option>
                <option value="flipkart">Flipkart</option>
                <option value="bigbasket">BigBasket</option>
                <option value="jio-mart">Jio Mart</option>
                <option value="d-mart">D-Mart</option>
              </select>
            </div>
          </div>

          <div className="flex gap-2 items-center ml-auto">
            <Button size="sm" disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}>Prev</Button>
            <span className="text-sm font-medium text-gray-600">Page {currentPage} of {totalPages}</span>
            <Button size="sm" disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}>Next</Button>
          </div>
        </CardHeader>

        <CardBody className="p-0 overflow-x-auto">
          {loading ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : (
            <table className="w-full min-w-[1500px] table-fixed">
              <thead className="bg-gray-100 border-b border-gray-250 text-left">
                <tr>
                  {COLUMNS.map((c) => (
                    <th
                      key={c.key}
                      style={{ width: c.width }}
                      className="px-4 py-3 text-xs font-bold text-gray-600 uppercase"
                    >
                      <div
                        className="flex gap-2 items-center cursor-pointer select-none"
                        onClick={() => toggleSort(c.key)}
                      >
                        {c.label}
                        <ChevronUpDownIcon className="h-4 w-4 text-gray-400" />
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {sortedPageData.length === 0 ? (
                  <tr>
                    <td
                      colSpan={COLUMNS.length}
                      className="text-center p-10 text-gray-500"
                    >
                      No product data found.
                    </td>
                  </tr>
                ) : (
                  sortedPageData.map((row, index) => (
                    <tr
                      key={index}
                      className="border-b hover:bg-gray-50"
                    >
                      {COLUMNS.map((col) => (
                        <td
                          key={col.key}
                          className="px-4 py-3 text-sm break-words border-b border-gray-100 truncate"
                        >
                          {col.key === "product_url" || col.key === "img_url" ? (
                            row[col.key] ? (
                              <a
                                href={row[col.key]}
                                target="_blank"
                                rel="noreferrer"
                                className="text-blue-600 font-medium hover:underline"
                              >
                                View Link
                              </a>
                            ) : (
                              "-"
                            )
                          ) : col.key === "price" ? (
                            <span className="font-bold text-green-700">
                              ₹{row[col.key] != null ? Number(row[col.key]).toFixed(2) : "0.00"}
                            </span>
                          ) : col.key === "is_best_seller" ? (
                            <span>{row[col.key] ? "Yes" : "No"}</span>
                          ) : (
                            String(row[col.key] ?? "-")
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
    </div>
  );
};

export default CleanProductMaster;
