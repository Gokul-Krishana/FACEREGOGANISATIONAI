"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, type EmployeeSummary } from "@/lib/api";
import {
  Users,
  Search,
  Plus,
  RefreshCw,
  UserCheck,
  ShieldCheck,
  Building,
  UserPlus,
} from "lucide-react";

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const loadEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listEmployees(page * pageSize, pageSize, search || undefined);
      setEmployees(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search]);

  useEffect(() => {
    loadEmployees();
  }, [loadEmployees]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Users className="w-6 h-6 text-blue-400" />
            Faculty & Employees
          </h1>
          <p className="text-slate-400 text-sm">
            Manage university staff, faculty members, and campus administrative personnel with biometric FAISS embeddings.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/enrollment"
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-all"
          >
            <UserPlus className="w-4 h-4" />
            <span>Enroll Face Photo</span>
          </Link>
        </div>
      </div>

      {/* Search Toolbar */}
      <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by name, employee code, department..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-700/80 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        <button
          onClick={loadEmployees}
          disabled={loading}
          className="p-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-300 hover:text-white"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Employees Table */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/80 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-5">Employee ID</th>
                <th className="py-3 px-5">Full Name</th>
                <th className="py-3 px-5">Department</th>
                <th className="py-3 px-5">FAISS Biometric Index</th>
                <th className="py-3 px-5">Enrolled Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                    <span>Loading faculty records...</span>
                  </td>
                </tr>
              ) : employees.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    No employee records found.
                  </td>
                </tr>
              ) : (
                employees.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-5 font-mono text-xs text-cyan-400 font-semibold">
                      {e.employee_id}
                    </td>
                    <td className="py-3 px-5 font-semibold text-white">
                      {e.name}
                    </td>
                    <td className="py-3 px-5 text-slate-300 text-xs flex items-center gap-1.5">
                      <Building className="w-3.5 h-3.5 text-slate-500" />
                      <span>{e.department || "General Campus"}</span>
                    </td>
                    <td className="py-3 px-5 text-xs">
                      {e.faiss_id !== null && e.faiss_id !== undefined ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-mono text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                          <ShieldCheck className="w-3 h-3" />
                          Index #{e.faiss_id}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">Pending Photo</span>
                      )}
                    </td>
                    <td className="py-3 px-5 font-mono text-xs text-slate-400">
                      {e.created_at ? new Date(e.created_at).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>
            Showing {employees.length} of {total} employees
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
              disabled={(page + 1) * pageSize >= total || loading}
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
