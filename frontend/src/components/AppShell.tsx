"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Video,
  Camera,
  GraduationCap,
  Users,
  UserPlus,
  CalendarCheck,
  UserX,
  BarChart3,
  Activity,
  ShieldCheck,
  Settings,
  HardDrive,
  LogOut,
  Bell,
  CheckCircle2,
  AlertTriangle,
  WifiOff,
  Menu,
  X,
} from "lucide-react";
import { api, type SystemStatus } from "@/lib/api";

const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/monitor", label: "Live CCTV Monitor", icon: Video, badge: "LIVE" },
  { href: "/cameras", label: "Camera Management", icon: Camera },
  { href: "/students", label: "Students", icon: GraduationCap },
  { href: "/employees", label: "Employees", icon: Users },
  { href: "/enrollment", label: "Face Enrollment", icon: UserPlus },
  { href: "/attendance", label: "Attendance Records", icon: CalendarCheck },
  { href: "/unknown", label: "Unknown Faces", icon: UserX },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/health", label: "System Health", icon: Activity },
  { href: "/audit", label: "Audit Logs", icon: ShieldCheck },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString("en-US", { hour12: false }));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let mounted = true;
    const fetchStatus = () => {
      api.getSystemStatus()
        .then((s) => {
          if (mounted) setStatus(s);
        })
        .catch(() => {
          // Fallback to basic health check if /system/status fails
          api.healthCheck()
            .then((h) => {
              if (mounted) {
                setStatus({
                  status: h.status,
                  version: h.version,
                  timestamp: h.timestamp,
                  database: h.database,
                  redis: h.redis,
                  offline_mode: true,
                });
              }
            })
            .catch(() => undefined);
        });
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Exclude auth pages from sidebar shell
  if (pathname.startsWith("/auth")) {
    return <main className="min-h-screen bg-slate-950 text-slate-100">{children}</main>;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row antialiased">
      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between p-4 bg-slate-900/90 border-b border-slate-800 sticky top-0 z-50 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-600/30 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <Video className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold text-sm tracking-wide text-white">FaceRecognitionAI</span>
            <span className="text-[10px] text-cyan-400 block -mt-1 font-mono">OFFLINE CCTV</span>
          </div>
        </div>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white"
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Sidebar Navigation */}
      <aside
        className={`fixed md:sticky top-0 left-0 h-screen w-72 bg-slate-900/95 border-r border-slate-800/80 z-40 flex flex-col justify-between transition-transform duration-200 backdrop-blur-xl ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex flex-col h-full overflow-hidden">
          {/* Logo & Header */}
          <div className="p-5 border-b border-slate-800/80 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
              <Video className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-base tracking-tight text-white flex items-center gap-1.5">
                <span>FaceRecognition</span>
                <span className="text-cyan-400 font-mono text-xs px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/60">
                  AI
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Offline CCTV Attendance</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 p-3 space-y-1 overflow-y-auto custom-scrollbar">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                    isActive
                      ? "bg-blue-600/20 text-cyan-300 border border-blue-500/30 shadow-sm shadow-blue-500/10 font-semibold"
                      : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/50"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={`w-4 h-4 transition-colors ${
                        isActive ? "text-cyan-400" : "text-slate-400 group-hover:text-blue-400"
                      }`}
                    />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* System Mode Footer */}
          <div className="p-4 border-t border-slate-800/80 bg-slate-950/40">
            <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/40 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <WifiOff className="w-3.5 h-3.5 text-cyan-400" />
                  Mode
                </span>
                <span className="text-cyan-300 font-mono font-medium">100% Local / Offline</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
                  Engine
                </span>
                <span className="text-emerald-400 font-mono">ArcFace + FAISS</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="hidden md:flex h-16 bg-slate-900/60 border-b border-slate-800/80 items-center justify-between px-8 sticky top-0 z-30 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/60 border border-slate-700/50 text-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-300 font-medium">Local Recognition Node</span>
              <span className="text-slate-500">|</span>
              <span className="font-mono text-cyan-400 font-semibold">{timeStr}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs text-slate-300 px-3 py-1.5 rounded-lg bg-slate-800/40 border border-slate-700/40">
              <Activity className="w-3.5 h-3.5 text-blue-400" />
              <span>Database:</span>
              <span className="text-emerald-400 font-medium">
                {status?.database === "connected" ? "Connected" : "Local SQLite/PG"}
              </span>
            </div>

            <Link
              href="/monitor"
              className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-blue-600/20"
            >
              <Video className="w-3.5 h-3.5" />
              <span>Live Monitor</span>
            </Link>
          </div>
        </header>

        {/* Page Body */}
        <main className="flex-1 p-4 md:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
