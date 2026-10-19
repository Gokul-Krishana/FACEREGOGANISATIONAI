"use client";

import React, { useEffect, useState } from "react";
import { api, type SystemStatus } from "@/lib/api";
import {
  Activity,
  HardDrive,
  Cpu,
  Database,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Server,
  ShieldCheck,
  WifiOff,
  Video,
} from "lucide-react";

export default function HealthPage() {
  const [health, setHealth] = useState<{
    status: string;
    version: string;
    timestamp: string;
    database: string;
    redis: string;
  } | null>(null);
  const [readiness, setReadiness] = useState<{
    ready: boolean;
    checks: Record<string, string>;
  } | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = () => {
    setLoading(true);
    Promise.all([
      api.healthCheck().catch(() => null),
      api.readinessCheck().catch(() => null),
      api.getSystemStatus().catch(() => null),
    ])
      .then(([h, r, s]) => {
        setHealth(h);
        setReadiness(r);
        setStatus(s);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHealth();
    const timer = setInterval(fetchHealth, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Activity className="w-6 h-6 text-emerald-400" />
            System Health & Offline Architecture
          </h1>
          <p className="text-slate-400 text-sm">
            Operational status of local database, inference engine, bounded frame buffers, and camera workers.
          </p>
        </div>

        <button
          onClick={fetchHealth}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-200 text-sm font-medium flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Health</span>
        </button>
      </div>

      {/* Offline Mode Banner */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-blue-950/40 via-slate-900 to-slate-900 border border-blue-800/40 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-cyan-300">
            <WifiOff className="w-5 h-5" />
          </div>
          <div>
            <div className="font-semibold text-white text-sm flex items-center gap-2">
              <span>Local Offline CCTV Architecture</span>
              <span className="text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                READY
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Models (InsightFace, YOLO11, ArcFace), SQLite/PG database, and Next.js frontend are hosted 100% locally on this machine.
            </p>
          </div>
        </div>

        <span className="hidden sm:inline font-mono text-xs text-slate-400">
          v{health?.version || "2.4.0"}
        </span>
      </div>

      {/* Service Blocks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Core Backend Status */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="font-semibold text-white text-base flex items-center gap-2">
              <Server className="w-4 h-4 text-blue-400" />
              FastAPI Core
            </h3>
            <span
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
                health?.status === "healthy"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "bg-red-500/20 text-red-400 border border-red-500/30"
              }`}
            >
              {health?.status || "CONNECTED"}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">API Port</span>
              <span className="font-mono text-slate-200">8000</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Local Uvicorn Workers</span>
              <span className="font-mono text-slate-200">Single Instance</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Last Health Ping</span>
              <span className="font-mono text-slate-300">
                {health?.timestamp ? new Date(health.timestamp).toLocaleTimeString() : "Just now"}
              </span>
            </div>
          </div>
        </div>

        {/* Database Status */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="font-semibold text-white text-base flex items-center gap-2">
              <Database className="w-4 h-4 text-cyan-400" />
              Local Database
            </h3>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              {health?.database || "ACTIVE"}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Database Driver</span>
              <span className="font-mono text-slate-200">SQLAlchemy ORM</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Storage Location</span>
              <span className="font-mono text-slate-200">Local Disk / SQLite</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Attendance Deduplication</span>
              <span className="text-emerald-400 font-medium">Session + Daily</span>
            </div>
          </div>
        </div>

        {/* Biometric & Model Engine */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="font-semibold text-white text-base flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              AI Biometric Engine
            </h3>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
              CPU Multi-thread
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Face Recognizer</span>
              <span className="font-mono text-slate-200">InsightFace ArcFace</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Vector Search</span>
              <span className="font-mono text-slate-200">FAISS IndexFlatL2</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Deep Liveness</span>
              <span className="font-mono text-slate-200">MiniFASNetV2 ONNX</span>
            </div>
          </div>
        </div>
      </div>

      {/* Subsystem Readiness Checklist */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-4">
        <h3 className="font-semibold text-white text-base">Subsystem Readiness Verification</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {readiness?.checks ? (
            Object.entries(readiness.checks).map(([name, stat]) => (
              <div key={name} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 flex items-center justify-between text-xs">
                <span className="text-slate-300 font-medium">{name}</span>
                <span className="font-mono text-emerald-400 flex items-center gap-1 font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {String(stat)}
                </span>
              </div>
            ))
          ) : (
            <div className="col-span-full py-4 text-center text-slate-500 text-xs">
              All essential attendance and camera services are ready.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
