"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, type StudentSummary } from "@/lib/api";
import {
  GraduationCap,
  Search,
  RefreshCw,
  UserPlus,
  ShieldCheck,
  Mail,
} from "lucide-react";

export default function StudentsPage() {
  const [students, setStudents] = useState<StudentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const loadStudents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listStudents(page * pageSize, pageSize, search || undefined);
      setStudents(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search]);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <GraduationCap className="w-6 h-6 text-blue-400" />
            Enrolled Students
          </h1>
          <p className="text-slate-400 text-sm">
            Biometrically indexed students verified against local ArcFace 512-d FAISS database.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/enrollment"
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-all"
          >
            <UserPlus className="w-4 h-4" />
            <span>Enroll Student Photo</span>
          </Link>
        </div>
      </div>

      {/* Search Toolbar */}
      <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by student ID, name, email..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-700/80 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        <button
          onClick={loadStudents}
          disabled={loading}
          className="p-2 rounded-xl bg-slate-950 border border-slate-700 text-slate-300 hover:text-white"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Students Table */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950/80 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 px-5">Student ID</th>
                <th className="py-3 px-5">Full Name</th>
                <th className="py-3 px-5">Email Address</th>
                <th className="py-3 px-5">Biometric Status</th>
                <th className="py-3 px-5">Account State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                    <span>Loading student records...</span>
                  </td>
                </tr>
              ) : students.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    No student records found.
                  </td>
                </tr>
              ) : (
                students.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-5 font-mono text-xs text-cyan-400 font-semibold">
                      {s.student_id}
                    </td>
                    <td className="py-3 px-5 font-semibold text-white">
                      {s.name}
                    </td>
                    <td className="py-3 px-5 text-slate-400 text-xs flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5 text-slate-500" />
                      <span>{s.email || "—"}</span>
                    </td>
                    <td className="py-3 px-5 text-xs">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-mono text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                        <ShieldCheck className="w-3 h-3" />
                        ArcFace Enrolled
                      </span>
                    </td>
                    <td className="py-3 px-5">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          s.is_active
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-red-500/10 text-red-400 border border-red-500/20"
                        }`}
                      >
                        {s.is_active ? "Active" : "Disabled"}
                      </span>
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
            Showing {students.length} of {total} students
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
