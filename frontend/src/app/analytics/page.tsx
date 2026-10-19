"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { TrendingUp, Users, Calendar, ShieldCheck, Clock, Activity } from "lucide-react";

interface Summary {
  date: string;
  total_attendance: number;
  unique_students: number;
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    api.getAttendanceSummary()
      .then((data) => {
        // Sort chronologically if needed
        const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
        setSummary(sorted);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const totalRecognitions = summary.reduce((acc, curr) => acc + curr.total_attendance, 0);
  const totalUnique = summary.reduce((acc, curr) => acc + curr.unique_students, 0);
  const avgDaily = summary.length ? Math.round(totalRecognitions / summary.length) : 0;

  // Chart data formatting
  const chartData = summary.map((s) => ({
    date: s.date,
    Total: s.total_attendance,
    Unique: s.unique_students,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Analytics & Intelligence</h1>
        <p className="text-slate-400 text-sm mt-1">
          Historical attendance volumes, biometric deduplication metrics, and camera throughput trends
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-[#0f172a]/70 border border-slate-800 rounded-xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium tracking-wider">Total Records</span>
            <TrendingUp className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white">{totalRecognitions.toLocaleString()}</div>
          <div className="text-xs text-slate-500 mt-1">Confirmed identity logs</div>
        </div>

        <div className="bg-[#0f172a]/70 border border-slate-800 rounded-xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium tracking-wider">Unique Individuals</span>
            <Users className="h-4 w-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white">{totalUnique.toLocaleString()}</div>
          <div className="text-xs text-slate-500 mt-1">Deduplicated identities</div>
        </div>

        <div className="bg-[#0f172a]/70 border border-slate-800 rounded-xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium tracking-wider">Daily Average</span>
            <Activity className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white">{avgDaily.toLocaleString()}</div>
          <div className="text-xs text-slate-500 mt-1">Verifications per day</div>
        </div>

        <div className="bg-[#0f172a]/70 border border-slate-800 rounded-xl p-5 backdrop-blur">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs uppercase font-medium tracking-wider">AMFR Deduplication</span>
            <ShieldCheck className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {totalRecognitions > 0 ? `${Math.round(((totalRecognitions - totalUnique) / totalRecognitions) * 100)}%` : "0%"}
          </div>
          <div className="text-xs text-slate-500 mt-1">Repetitive detections suppressed</div>
        </div>
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Attendance Trend Chart */}
        <div className="bg-[#0f172a]/70 border border-slate-800 rounded-xl p-6 backdrop-blur">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-base font-semibold text-white">Attendance Inflow Volume</h2>
              <p className="text-xs text-slate-400">Total vs Unique biometric hits per day</p>
            </div>
            <Calendar className="h-4 w-4 text-slate-500" />
          </div>

          <div className="h-72 w-full">
            {loading ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                Loading analytics data...
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                No attendance trend records found
              </div>
            ) : mounted ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="uniqueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0b1329",
                      borderColor: "#1e293b",
                      borderRadius: "0.5rem",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }} />
                  <Area
                    type="monotone"
                    dataKey="Total"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#totalGrad)"
                  />
                  <Area
                    type="monotone"
                    dataKey="Unique"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#uniqueGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : null}
          </div>
        </div>

        {/* Verification Distribution */}
        <div className="bg-[#0f172a]/70 border border-slate-800 rounded-xl p-6 backdrop-blur">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-base font-semibold text-white">Daily Unique Breakdown</h2>
              <p className="text-xs text-slate-400">Comparison of daily individual throughput</p>
            </div>
            <Clock className="h-4 w-4 text-slate-500" />
          </div>

          <div className="h-72 w-full">
            {loading ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                Loading breakdown data...
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                No breakdown records found
              </div>
            ) : mounted ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0b1329",
                      borderColor: "#1e293b",
                      borderRadius: "0.5rem",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }} />
                  <Bar dataKey="Unique" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Total" fill="#0ea5e9" radius={[4, 4, 0, 0]} opacity={0.6} />
                </BarChart>
              </ResponsiveContainer>
            ) : null}
          </div>
        </div>
      </div>

      {/* Offline Intelligence & Biometric Integrity Notice */}
      <div className="bg-[#0b1329] border border-cyan-950/60 rounded-xl p-5 flex items-start gap-4">
        <div className="p-2.5 bg-cyan-950/40 rounded-lg text-cyan-400 shrink-0">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Local Biometric Decision Integrity</h3>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed">
            All analytics calculations, ArcFace vector comparisons (512-d embeddings), and AMFR cooldown rules execute locally on the edge recognition node. No facial embeddings or biometric profiles are transferred to external telemetry or third-party cloud services.
          </p>
        </div>
      </div>
    </div>
  );
}
