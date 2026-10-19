"use client";

import React, { useState } from "react";
import { useAppStore } from "@/lib/store";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  Settings,
  ShieldCheck,
  Video,
  Database,
  Sliders,
  Save,
  CheckCircle2,
  LogOut,
  User,
  Key,
} from "lucide-react";

export default function SettingsPage() {
  const { user, logout } = useAppStore();
  const router = useRouter();

  const [recogThreshold, setRecogThreshold] = useState("0.60");
  const [livenessThreshold, setLivenessThreshold] = useState("0.50");
  const [cooldownSecs, setCooldownSecs] = useState("60");
  const [rtspTransport, setRtspTransport] = useState("tcp");
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {}
    logout();
    router.push("/auth/login");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <Settings className="w-6 h-6 text-blue-400" />
          System Settings & AMFR Policy
        </h1>
        <p className="text-slate-400 text-sm">
          Tune ArcFace recognition thresholds, liveness sensitivities, CCTV RTSP transports, and local data retention.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* AMFR Recognition Engine Settings */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-5">
          <div className="flex items-center gap-2 text-base font-semibold text-white pb-3 border-b border-slate-800">
            <ShieldCheck className="w-5 h-5 text-blue-400" />
            <span>Biometric Recognition & Anti-Spoofing Thresholds</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-xs">
            <div>
              <label className="block font-semibold text-slate-300 mb-1.5">
                ArcFace Similarity Threshold
              </label>
              <input
                type="number"
                step="0.05"
                min="0.30"
                max="0.95"
                value={recogThreshold}
                onChange={(e) => setRecogThreshold(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 text-sm focus:outline-none focus:border-blue-500 font-mono"
              />
              <span className="text-slate-500 text-[11px] mt-1 block">
                Higher = stricter identity verification; 0.60 balances glasses/hair changes with false rejection.
              </span>
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1.5">
                Liveness Sensitivity (Anti-Spoof)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.20"
                max="0.90"
                value={livenessThreshold}
                onChange={(e) => setLivenessThreshold(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 text-sm focus:outline-none focus:border-blue-500 font-mono"
              />
              <span className="text-slate-500 text-[11px] mt-1 block">
                MiniFASNetV2 cut-off score. Rejects printed photos and screens held in front of cameras.
              </span>
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1.5">
                Attendance Cooldown (Seconds)
              </label>
              <input
                type="number"
                step="5"
                min="10"
                max="3600"
                value={cooldownSecs}
                onChange={(e) => setCooldownSecs(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 text-sm focus:outline-none focus:border-blue-500 font-mono"
              />
              <span className="text-slate-500 text-[11px] mt-1 block">
                Prevents repeated database attendance writes while a person lingers in front of the camera.
              </span>
            </div>
          </div>
        </div>

        {/* CCTV Streaming & RTSP Settings */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-5">
          <div className="flex items-center gap-2 text-base font-semibold text-white pb-3 border-b border-slate-800">
            <Video className="w-5 h-5 text-cyan-400" />
            <span>CCTV Camera & Real-Time Buffer Architecture</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
            <div>
              <label className="block font-semibold text-slate-300 mb-1.5">RTSP Transport Protocol</label>
              <select
                value={rtspTransport}
                onChange={(e) => setRtspTransport(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="tcp">TCP (Recommended — Zero packet drop, no frame tearing)</option>
                <option value="udp">UDP (Lowest latency, prone to network packet loss)</option>
              </select>
              <span className="text-slate-500 text-[11px] mt-1 block">
                FFmpeg uses TCP packets to guarantee frame completeness over campus networks.
              </span>
            </div>

            <div>
              <label className="block font-semibold text-slate-300 mb-1.5">Latest-Frame Buffer Capacity</label>
              <input
                type="text"
                disabled
                value="1 Frame (Newest Wins — Stale Drops)"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-slate-400 text-sm font-mono cursor-not-allowed"
              />
              <span className="text-slate-500 text-[11px] mt-1 block">
                Thread-safe buffer guarantees browser displays fresh frames (&lt;15ms age) without accumulated delay.
              </span>
            </div>
          </div>
        </div>

        {/* Account & Session */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2 text-base font-semibold text-white pb-3 border-b border-slate-800">
            <User className="w-5 h-5 text-purple-400" />
            <span>Administrator Identity & Local Session</span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Current User</span>
              <span className="font-mono text-slate-200">{user?.username || "admin"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Role</span>
              <span className="text-emerald-400 font-mono">SUPERADMIN</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">API Endpoint</span>
              <span className="font-mono text-slate-300">{process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</span>
            </div>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-all"
            >
              <Save className="w-4 h-4" />
              <span>Save Policy Settings</span>
            </button>
            {saved && (
              <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium">
                <CheckCircle2 className="w-4 h-4" />
                Saved successfully!
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="px-4 py-2.5 rounded-xl bg-red-950/40 hover:bg-red-900/60 border border-red-800/50 text-red-300 text-xs font-semibold flex items-center gap-1.5 transition-all"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out Session</span>
          </button>
        </div>
      </form>
    </div>
  );
}
