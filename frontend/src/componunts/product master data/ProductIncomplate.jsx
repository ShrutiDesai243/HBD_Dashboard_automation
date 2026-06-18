import React, { useEffect, useState, useCallback } from "react";
import api from "../../utils/Api";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Typography,
  Input,
  Spinner,
} from "@material-tailwind/react";
import {
  MagnifyingGlassIcon,
  ChevronUpDownIcon,
  ChevronDownIcon,
} from "@heroicons/react/24/solid";
import * as XLSX from "xlsx/dist/xlsx.full.min.js";

const defaultColumns = [
  { key: "marketplace_name", label: "Marketplace", width: 120 },
  { key: "product_id", label: "ID", width: 150 },
  { key: "product_name", label: "Product Name", width: 300 },
  { key: "brand", label: "Brand", width: 150 },
  { key: "category_name", label: "Category", width: 180 },
  { key: "reason", label: "Unmapped Reason", width: 220 },
  { key: "price", label: "Price (₹)", width: 100 },
  { key: "product_url", label: "Link", width: 120 },
];

const convertToCSV = (arr) => {
  if (!arr.length) return "";
  const headers = Object.keys(arr[0]);
  const rows = arr.map((r) =>
    headers.map((h) => `"${String(r[h] ?? "").replace(/"/g, "'")}"`).join(",")
  );
  return [headers.join(","), ...rows].join("\n");
};

const ProductIncomplete = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [marketplace, setMarketplace] = useState("all");

  const [sortField, setSortField] = useState(null);
  const [sortOrder, setSortOrder] = useState("asc");

  const [columns, setColumns] = useState(defaultColumns);
  const [page, setPage] = useState(1);
  const limit = 50;
  
  const fetchData = useCallback(async (pg = 1, sq = appliedSearch, mp = marketplace) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: limit, page: pg });
      if (sq) params.append("search", sq);
      
      const res = await api.get(`/cleaning/uncleaned-products?${params}`);
      const d = res.data;
      setData(d.data || []);
      setTotal(d.total_count || (d.data ? d.data.length : 0));
      setPage(pg);
    } catch (e) {
      console.error("ProductIncomplete fetch error", e);
    } finally {
      setLoading(false);
    }
  }, [appliedSearch, marketplace]);

  useEffect(() => {
    fetchData(1, appliedSearch, marketplace);
  }, [appliedSearch, marketplace, fetchData]);

  const handleSearch = () => {
    setAppliedSearch(search);
  };

  const totalPages = Math.max(1, Math.ceil(total / limit));

  const sortedData = [...data].sort((a, b) => {
    if (!sortField) return 0;
    const A = String(a[sortField] ?? "").toLowerCase();
    const B = String(b[sortField] ?? "").toLowerCase();
    if (A === B) return 0;
    return sortOrder === "asc" ? (A > B ? 1 : -1) : (A < B ? 1 : -1);
  });

  const toggleSort = (field) => {
    if (sortField === field) setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
    else { setSortField(field); setSortOrder("asc"); }
  };

  const downloadCSV = () => {
    const csv = convertToCSV(data);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "unmapped_products.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadExcel = () => {
    if (!data.length) return;
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "UnmappedProducts");
    XLSX.writeFile(wb, "unmapped_products.xlsx");
  };

  const startResize = (colKey, e) => {
    e.preventDefault();
    const startX = e.clientX;
    const col = columns.find((c) => c.key === colKey);
    const startWidth = col.width;

    const onMouseMove = (ev) => {
      const delta = ev.clientX - startX;
      const newWidth = Math.max(80, startWidth + delta);
      setColumns((cols) =>
        cols.map((c) => (c.key === colKey ? { ...c, width: newWidth } : c))
      );
    };

    const stop = () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", stop);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", stop);
  };

  return (
    <div className="min-h-screen mt-8 mb-12 px-4 bg-white text-black">
      <div className="flex justify-between items-center mb-4">
        <Typography variant="h4">Unmapped Products</Typography>

        <div className="flex items-center gap-2">
          <Button size="sm" onClick={downloadCSV}>CSV Export</Button>
          <Button size="sm" onClick={downloadExcel}>Excel Export</Button>
        </div>
      </div>

      <Card className="bg-white border text-black">
        <CardHeader className="flex flex-wrap items-center justify-between gap-3 p-4 bg-gray-100">
          <div className="flex gap-3 items-center flex-wrap">
            <Input
              label="Search Product Name/Brand..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
              icon={<MagnifyingGlassIcon className="h-5 w-5 cursor-pointer" onClick={handleSearch} />}
            />
            <select
              className="px-3 py-2 border rounded-md text-sm"
              value={marketplace}
              onChange={(e) => setMarketplace(e.target.value)}
            >
              <option value="all">All Marketplaces</option>
              <option value="amazon">Amazon</option>
              <option value="blinkit">Blinkit</option>
              <option value="bigbasket">BigBasket</option>
              <option value="dmart">DMart</option>
              <option value="indiamart">IndiaMart</option>
              <option value="zepto">Zepto</option>
            </select>
          </div>

          <div className="flex gap-2 items-center">
            <div className="text-sm text-gray-600 font-semibold mr-2">Total: {total.toLocaleString()}</div>
            <div>Page {page} / {totalPages}</div>
            <Button size="sm" onClick={() => fetchData(Math.max(1, page - 1))} disabled={page === 1}>
              Prev
            </Button>
            <Button size="sm" onClick={() => fetchData(Math.min(totalPages, page + 1))} disabled={page === totalPages}>
              Next
            </Button>
          </div>
        </CardHeader>

        <CardBody className="p-0 overflow-x-auto">
          {loading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-10 w-10" />
            </div>
          ) : (
            <table className="w-full table-fixed border-collapse min-w-[1500px]">
              <thead className="sticky top-0 z-20 border-b bg-gray-200">
                <tr>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      style={{ width: col.width }}
                      className="px-3 py-2 text-left relative select-none"
                    >
                      <div className="flex items-center justify-between">
                        <div
                          className="flex items-center gap-2 cursor-pointer"
                          onClick={() => toggleSort(col.key)}
                        >
                          <span className="capitalize text-sm font-semibold">
                            {col.label}
                          </span>
                          {sortField === col.key ? (
                            sortOrder === "asc" ? <ChevronUpDownIcon className="h-4" /> : <ChevronDownIcon className="h-4" />
                          ) : (
                            <ChevronUpDownIcon className="h-4 opacity-40" />
                          )}
                        </div>
                        <div
                          onMouseDown={(e) => startResize(col.key, e)}
                          className="absolute right-0 top-0 h-full w-2 cursor-col-resize hover:bg-blue-200"
                        ></div>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {sortedData.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length} className="text-center p-6 text-gray-500">
                      No records found
                    </td>
                  </tr>
                ) : (
                  sortedData.map((row, i) => (
                    <tr key={row.product_id || row.id || i} className="border-b hover:bg-gray-50">
                      {columns.map((col) => (
                        <td
                          key={col.key}
                          style={{ width: col.width, maxWidth: col.width }}
                          className="px-3 py-3 break-words text-sm"
                        >
                          {col.key === "product_url" && row[col.key] ? (
                            <a href={row[col.key]} target="_blank" rel="noopener noreferrer" className="text-blue-500 underline">
                              View Link
                            </a>
                          ) : col.key === "price" || col.key === "list_price" ? (
                            row[col.key] ? `₹${row[col.key]}` : "-"
                          ) : col.key === "reason" ? (
                             <span className="px-2 py-1 bg-red-100 text-red-800 rounded font-bold text-xs">{row[col.key]}</span>
                          ) : col.key === "marketplace_name" ? (
                             <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded font-bold text-xs">{row[col.key]}</span>
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

      <div className="mt-4 flex justify-center items-center gap-2">
        <Button size="sm" onClick={() => fetchData(1)} disabled={page === 1}>First</Button>
        <Button size="sm" onClick={() => fetchData(Math.max(1, page - 1))} disabled={page === 1}>Prev</Button>
        <div className="px-3 py-1 border rounded">Page {page} / {totalPages}</div>
        <Button size="sm" onClick={() => fetchData(Math.min(totalPages, page + 1))} disabled={page === totalPages}>Next</Button>
        <Button size="sm" onClick={() => fetchData(totalPages)} disabled={page === totalPages}>Last</Button>
      </div>
    </div>
  );
};

export default ProductIncomplete;
