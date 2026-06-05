import React, { useEffect, useMemo, useState } from "react";
import {
  Card,
  CardBody,
  Typography,
  Spinner,
} from "@material-tailwind/react";
import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import api from "../../utils/Api";

export function CategoriesReports() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categorySearch, setCategorySearch] = useState("");

  useEffect(() => {
    setLoading(true);
    api.get("/report/aggregate")
      .then((res) => {
        setData(res.data?.categories || []);
      })
      .catch((err) => console.error("Error fetching categories:", err))
      .finally(() => setLoading(false));
  }, []);

  // Process Rows: Filter Categories based on search input
  const tableRows = useMemo(() => {
    let list = data;
    if (categorySearch) {
      list = list.filter((cat) =>
        (cat.name || "").toLowerCase().includes(categorySearch.toLowerCase())
      );
    }
    return list;
  }, [data, categorySearch]);

  const headerInputClass = "w-full bg-white text-gray-700 placeholder-gray-400 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-gray-100 focus:border-blue-gray-300 transition-all shadow-sm";

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20 gap-3">
        <Spinner className="h-10 w-10 text-blue-500" />
        <Typography className="animate-pulse text-gray-600 font-medium">Loading Category Report...</Typography>
      </div>
    );
  }

  return (
    <div className="mt-8 mb-12 px-4 max-w-5xl mx-auto">
      <div className="mb-4">
        <Typography variant="h4" color="blue-gray" className="font-bold">
          Category Data Grid
        </Typography>
        <Typography variant="small" className="text-gray-500">
          Analyze listing distribution by industry category.
        </Typography>
      </div>

      <Card className="border border-gray-300 shadow-sm overflow-hidden rounded-lg">
        <CardBody className="p-0 overflow-visible">
          <table className="w-full text-left table-fixed border-collapse">
            <thead className="bg-gradient-to-b from-white to-gray-100 border-b border-gray-300">
              <tr>
                {/* COL 1: CATEGORY FILTER (Search) */}
                <th className="px-4 py-3 w-1/2 align-top border-r border-gray-200">
                  <div className="flex flex-col gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1">
                      Filter Category
                    </span>
                    <div className="relative">
                      <MagnifyingGlassIcon className="absolute left-2 top-2 h-3.5 w-3.5 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search..."
                        value={categorySearch}
                        onChange={(e) => setCategorySearch(e.target.value)}
                        className={`${headerInputClass} pl-8`}
                      />
                    </div>
                  </div>
                </th>

                {/* COL 2: MATCHED LISTINGS */}
                <th className="px-4 py-3 w-1/4 align-middle border-r border-gray-200 bg-gray-50/50 text-center">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-blue-gray-600">
                    Matched Listings
                  </span>
                </th>

                {/* COL 3: TOTAL LISTINGS */}
                <th className="px-4 py-3 w-1/4 align-middle text-center">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                    Total Listings
                  </span>
                </th>
              </tr>
            </thead>

            <tbody className="text-sm text-gray-700 bg-white">
              {tableRows.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-6 py-12 text-center text-gray-400 italic bg-gray-50">
                    No categories found matching "{categorySearch}"
                  </td>
                </tr>
              ) : (
                tableRows.map((row) => (
                  <tr
                    key={row.name}
                    className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                  >
                    {/* Category Name */}
                    <td className="px-4 py-3 font-semibold text-gray-900 border-r border-gray-100">
                      {row.name}
                    </td>

                    {/* Matched Listings */}
                    <td className="px-4 py-3 text-center border-r border-gray-100 bg-gray-50/30">
                      <span className={`inline-block px-3 py-1 rounded-full font-bold text-xs border ${
                        row.match_count > 0
                          ? "bg-green-50 text-green-800 border-green-200"
                          : "bg-transparent text-gray-300 border-transparent"
                      }`}>
                        {row.match_count || 0}
                      </span>
                    </td>

                    {/* Total Listings */}
                    <td className="px-4 py-3 text-center">
                      <span className="inline-block px-3 py-1 bg-gray-100 text-gray-800 rounded-full font-bold text-xs border border-gray-200">
                        {row.total_count || 0}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>

            <tfoot className="bg-gray-50 font-bold text-gray-800 border-t border-gray-300">
              <tr>
                <td className="px-4 py-2.5 text-xs uppercase text-gray-500">
                  Total Categories: {tableRows.length}
                </td>
                <td className="px-4 py-2.5 text-center border-r border-gray-200 text-blue-gray-900 bg-gray-50/30">
                  {tableRows.reduce((sum, row) => sum + (row.match_count || 0), 0)}
                </td>
                <td className="px-4 py-2.5 text-center text-blue-gray-900">
                  {tableRows.reduce((sum, row) => sum + (row.total_count || 0), 0)}
                </td>
              </tr>
            </tfoot>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

export default CategoriesReports;