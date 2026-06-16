import React, { useEffect, useState } from "react";
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

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

const defaultColumns = [
  { key: "business_name", label: "Business Name", width: 220 },
  { key: "address", label: "Address", width: 320 },
  { key: "website_url", label: "Website", width: 180 },
  { key: "primary_phone", label: "Contact", width: 140 },
  { key: "reviews", label: "Review Count", width: 120 },
  { key: "reviews_avg", label: "Review Avg", width: 120 },
  { key: "business_category", label: "Category", width: 140 },
  { key: "business_subcategory", label: "Sub-Category", width: 140 },
  { key: "data_source", label: "Source", width: 120 },
  { key: "city", label: "City", width: 140 },
  { key: "state", label: "State", width: 140 },
  { key: "area", label: "Area", width: 140 },
];

const convertToCSV = (arr) => {
  if (!arr?.length) return "";
  const headers = Object.keys(arr[0]);
  const rows = arr.map((r) =>
    headers.map((h) => `"${String(r[h] ?? "").replace(/"/g, "'")}"`).join(",")
  );
  return [headers.join(","), ...rows].join("\n");
};

const CleanListingMaster = () => {
  const [loading, setLoading] = useState(true);
  const [pageData, setPageData] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const limit = 20;

  const [search, setSearch] = useState("");

  // Load Data from Backend master_table
  useEffect(() => {
    fetchListings(currentPage, search);
  }, [currentPage, search]);

  const fetchListings = async (page, querySearch) => {
    setLoading(true);
    try {
      const queryParams = new URLSearchParams({
        page: page,
        limit: limit,
        search: querySearch
      });

      const response = await fetch(`${API_BASE}/master_table/list?${queryParams}`, {
        method: "GET",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        }
      });

      if (response.status === 401) {
        window.location.href = "/auth/sign-in";
        return;
      }

      if (!response.ok) {
        throw new Error("Failed to fetch listings");
      }

      const result = await response.json();
      setPageData(result.data || []);
      setTotalRecords(result.total_count || 0);
      setTotalPages(result.total_pages || 1);
    } catch (err) {
      console.error("Fetch Listings Error:", err);
    } finally {
      setLoading(false);
    }
  };

  // CSV Page Download
  const downloadCSV = () => {
    const csv = convertToCSV(pageData);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "listing_page.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  // Excel Page Download
  const downloadExcel = () => {
    if (!pageData.length) return;
    const ws = XLSX.utils.json_to_sheet(pageData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Listings");
    XLSX.writeFile(wb, "listing_page.xlsx");
  };

  return (
    <div className="min-h-screen mt-8 mb-12 px-4 rounded bg-white text-black">
      <div className="flex justify-between items-center mb-4">
        <div>
          <Typography variant="h4" className="pb-1 text-gray-800">Clean Listing Master Data</Typography>
          <Typography variant="small" className="text-gray-500 font-normal">
            Viewing records directly from the database `master_table` ({totalRecords.toLocaleString()} total rows).
          </Typography>
        </div>

        <div className="flex gap-2">
          <Button size="sm" onClick={downloadCSV}>CSV Page</Button>
          <Button size="sm" onClick={downloadExcel}>Excel Page</Button>
        </div>
      </div>

      <Card className="border border-gray-250 shadow-sm rounded-xl overflow-hidden bg-white">
        <CardHeader className="flex flex-wrap justify-between items-center gap-3 p-4 bg-gray-50 border-b border-gray-200">
          <div className="w-72">
            <Input 
              label="Search keyword..." 
              value={search} 
              onChange={(e) => {
                setCurrentPage(1);
                setSearch(e.target.value);
              }} 
            />
          </div>

          <div className="flex gap-2 items-center">
            <Button size="sm" disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}>Prev</Button>
            <span className="text-sm font-medium text-gray-600">Page {currentPage} of {totalPages}</span>
            <Button size="sm" disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}>Next</Button>
          </div>
        </CardHeader>

        <CardBody className="p-0 overflow-x-auto">
          {loading ? (
            <div className="flex justify-center py-10"><Spinner /></div>
          ) : (
            <table className="w-full min-w-[1500px] table-fixed">
              <thead className="bg-gray-100 border-b border-gray-250 text-left">
                <tr>
                  {defaultColumns.map((col) => (
                    <th key={col.key} style={{ width: col.width }} className="px-4 py-3 text-xs font-bold text-gray-600 uppercase">
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageData.length === 0 ? (
                  <tr>
                    <td colSpan={defaultColumns.length} className="text-center p-10 text-gray-500">
                      No listings found.
                    </td>
                  </tr>
                ) : (
                  pageData.map((row, idx) => (
                    <tr key={idx} className="border-b hover:bg-gray-50">
                      {defaultColumns.map((col) => (
                        <td key={col.key} className="px-4 py-3 text-sm break-words border-b border-gray-100 truncate">
                          {col.key === "website_url" && row[col.key] ? (
                            <a href={row[col.key]} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                              {row[col.key]}
                            </a>
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

export default CleanListingMaster;
