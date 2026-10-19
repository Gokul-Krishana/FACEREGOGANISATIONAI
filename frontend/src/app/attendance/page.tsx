"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api, type AttendanceSummary } from "@/lib/api";
import {
  CalendarCheck,
  Download,
  Filter,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
  User,
  ShieldCheck,
  FileSpreadsheet,
} from "lucide-react";

export default function AttendancePage() {
  const [records, setRecords] = useState<AttendanceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const limit = 50;

  const loadAttendance = useCallback(async () => {
    setLoading(true);
    try {
      const params: {
        limit: number;
        skip: number;
        date_from?: string;
        date_to?: string;
      } = {
        limit,
        skip: page * limit,
      };
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const data = await api.listAttendance(params);
      setRecords(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, limit, dateFrom, dateTo]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const filteredRecords = records.filter((r) => {
    const matchesSearch = !search || r.student_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || r.status.toUpperCase() === statusFilter.toUpperCase();
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <CalendarCheck className="w-6 h-6 text-blue-400" />
            Attendance Records
          </h1>
          <p className="text-slate-400 text-sm">
            Verified biometric attendance logs recorded automatically from CCTV cameras with AMFR deduplication.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <a
            href={api.getAttendanceExportUrl()}
            target="_blank"
            rel="noreferrer"
            className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-200 text-sm font-semibold flex items-center gap-2 shadow-sm transition-all"
          >
            <Download className="w-4 h-4 text-cyan-400" />
            <span>Export CSV / Excel</span>
          </a>

          <button
            onClick={loadAttendance}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-300"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by student or staff name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-700/80 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">From:</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-3 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-white text-xs focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">To:</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-3 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-white text-xs focus:outline-none focus:border-blue-500"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-white text-xs focus:outline-none focus:border-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="PRESENT">Present</option>
          <option value="LATE">Late</option>
          <option value="UNCERTAIN">Uncertain</option>
        </select>
      </div>

      {/* Records Table */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/80 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-5">Student / Enrollee</th>
                <th className="py-3 px-5">Timestamp</th>
                <th className="py-3 px-5">Confidence</th>
                <th className="py-3 px-5">Verification Engine</th>
                <th className="py-3 px-5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                    <span>Loading attendance records...</span>
                  </td>
                </tr>
              ) : filteredRecords.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    No attendance events recorded for this selection.
                  </td>
                </tr>
              ) : (
                filteredRecords.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-5 font-semibold text-white">
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-blue-400" />
                        <span>{r.student_name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-5 font-mono text-xs text-slate-400">
                      {new Date(r.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-5 font-mono text-xs text-slate-200">
                      <span className="text-emerald-400 font-bold">{(r.confidence * 100).toFixed(1)}%</span>
                    </td>
                    <td className="py-3 px-5 text-xs text-slate-400 font-mono">
                      <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700/60">
                        {r.method || "AMFR-ArcFace"}
                      </span>
                    </td>
                    <td className="py-3 px-5">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="w-3 h-3" />
                        {r.status || "PRESENT"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer pagination */}
        <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>
            Showing {filteredRecords.length} of {total} records
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
              className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-40 text-slate-200"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= total || loading}
              className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 disabled:opacity-40 text-slate-200"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
