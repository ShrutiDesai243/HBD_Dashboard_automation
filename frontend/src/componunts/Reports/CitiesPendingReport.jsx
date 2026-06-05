import React, { useEffect, useMemo, useState } from "react";
import {
  Card,
  CardBody,
  Typography,
  Spinner,
} from "@material-tailwind/react";
import { MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import api from "../../utils/Api";

export function CitiesPendingReport() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [citySearch, setCitySearch] = useState("");

  useEffect(() => {
    setLoading(true);
    api.get("/report/aggregate")
      .then((res) => {
        setData(res.data?.cities || []);
      })
      .catch((err) => console.error("Error fetching cities:", err))
      .finally(() => setLoading(false));
  }, []);

  // Filter only cities that have pending items (total_count > match_count)
  const pendingCities = useMemo(() => {
    return data.map((city) => {
      const total = city.total_count || 0;
      const matched = city.match_count || 0;
      const pending = total - matched;
      return {
        name: city.name,
        pending_count: pending >= 0 ? pending : 0,
      };
    }).filter((city) => city.pending_count > 0);
  }, [data]);

  // Process Rows: Filter based on search input
  const tableRows = useMemo(() => {
    let list = pendingCities;
    if (citySearch) {
      list = list.filter((city) =>
        (city.name || "").toLowerCase().includes(citySearch.toLowerCase())
      );
    }
    return list;
  }, [pendingCities, citySearch]);

  const headerInputClass = "w-full bg-white text-gray-700 placeholder-gray-400 border border-gray-300 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-gray-100 focus:border-blue-gray-300 transition-all shadow-sm";

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20 gap-3">
        <Spinner className="h-10 w-10 text-blue-500" />
        <Typography className="animate-pulse text-gray-600 font-medium">Loading Pending Cities...</Typography>
      </div>
    );
  }

  return (
    <div className="mt-8 mb-12 px-4 max-w-5xl mx-auto">
      <div className="mb-4">
        <Typography variant="h4" color="blue-gray" className="font-bold">
          Cities Pending Report
        </Typography>
        <Typography variant="small" className="text-gray-500">
          Professional view of cities that still require mapping.
        </Typography>
      </div>

      <Card className="border border-gray-300 shadow-sm overflow-hidden rounded-lg">
        <CardBody className="p-0 overflow-visible">
          <table className="w-full text-left table-fixed border-collapse">
            <thead className="bg-gradient-to-b from-white to-gray-100 border-b border-gray-300">
              <tr>
                {/* COL 1: CITY FILTER */}
                <th className="px-4 py-3 w-2/3 align-top border-r border-gray-200">
                  <div className="flex flex-col gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1">
                      Filter by City
                    </span>
                    <div className="relative">
                      <MagnifyingGlassIcon className="absolute left-2 top-2 h-3.5 w-3.5 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search..."
                        value={citySearch}
                        onChange={(e) => setCitySearch(e.target.value)}
                        className={`${headerInputClass} pl-8`}
                      />
                    </div>
                  </div>
                </th>

                {/* COL 2: PENDING DATA */}
                <th className="px-4 py-3 w-1/3 align-middle text-center">
                  <div className="flex flex-col items-center justify-center h-full">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                      Pending Listings
                    </span>
                    <span className="text-[10px] text-gray-400 font-normal mt-0.5">
                      (Unmapped)
                    </span>
                  </div>
                </th>
              </tr>
            </thead>

            <tbody className="text-sm text-gray-700 bg-white">
              {tableRows.length === 0 ? (
                <tr>
                  <td colSpan={2} className="px-6 py-12 text-center text-gray-400 italic bg-gray-50">
                    No pending cities found matching "{citySearch}"
                  </td>
                </tr>
              ) : (
                tableRows.map((row) => (
                  <tr
                    key={row.name}
                    className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                  >
                    {/* City Name */}
                    <td className="px-4 py-3 font-semibold text-gray-900 border-r border-gray-100">
                      {row.name}
                    </td>

                    {/* Pending Count */}
                    <td className="px-4 py-3 text-center">
                      <span className="inline-block px-3 py-1 bg-amber-50 text-amber-800 rounded-full font-bold text-xs border border-amber-200">
                        {row.pending_count}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>

            <tfoot className="bg-gray-50 font-bold text-gray-800 border-t border-gray-300">
              <tr>
                <td className="px-4 py-2.5 text-xs uppercase text-gray-500 border-r border-gray-200">
                  Total Rows: {tableRows.length}
                </td>
                <td className="px-4 py-2.5 text-center text-blue-gray-900">
                  {tableRows.reduce((sum, row) => sum + row.pending_count, 0)}
                </td>
              </tr>
            </tfoot>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

export default CitiesPendingReport;