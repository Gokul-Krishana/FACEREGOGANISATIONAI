"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { api, type CameraSummary, type VideoSession } from "@/lib/api";
import {
  Camera,
  Plus,
  Play,
  Square,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Video,
  ExternalLink,
  MapPin,
  Server,
  Zap,
} from "lucide-react";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<CameraSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState<Record<number, VideoSession>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [newCamera, setNewCamera] = useState({
    name: "",
    camera_id: "",
    stream_url: "",
    building: "",
    room: "",
    location: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;

  const loadCameras = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.listCameras();
      setCameras(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCameras();
    return () => {
      Object.values(sessionsRef.current).forEach((session) => {
        void api.stopVideoSession(session.key).catch(() => undefined);
      });
    };
  }, [loadCameras]);

  useEffect(() => {
    const activeKeys = Object.entries(sessions);
    if (activeKeys.length === 0) return;
    const timer = window.setInterval(() => {
      activeKeys.forEach(([cameraId, session]) => {
        void api
          .getVideoSessionStatus(session.key)
          .then((status) => setSessions((current) => ({ ...current, [cameraId]: status })))
          .catch(() => undefined);
      });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [sessions]);

  const startCamera = async (cameraId: number) => {
    setErrors((current) => {
      const next = { ...current };
      delete next[cameraId];
      return next;
    });
    try {
      const session = await api.startVideoSession(cameraId);
      setSessions((current) => ({ ...current, [cameraId]: session }));
    } catch (error) {
      setErrors((current) => ({
        ...current,
        [cameraId]: error instanceof Error ? error.message : "Unable to start camera stream",
      }));
    }
  };

  const stopCamera = async (cameraId: number) => {
    const session = sessions[cameraId];
    if (!session) return;
    await api.stopVideoSession(session.key).catch(() => undefined);
    setSessions((current) => {
      const next = { ...current };
      delete next[cameraId];
      return next;
    });
  };

  const handleAddCamera = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCamera.name || !newCamera.camera_id) return;
    setSubmitting(true);
    try {
      await api.createCamera(newCamera);
      setAddModalOpen(false);
      setNewCamera({ name: "", camera_id: "", stream_url: "", building: "", room: "", location: "" });
      loadCameras();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add camera");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Camera className="w-6 h-6 text-blue-400" />
            Camera Management
          </h1>
          <p className="text-slate-400 text-sm">
            Register and manage CCTV streams, RTSP feeds, USB devices, and campus surveillance nodes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setAddModalOpen(true)}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Add CCTV / IP Camera</span>
          </button>
        </div>
      </div>

      {/* Grid of registered cameras */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          <div className="col-span-full py-16 text-center text-slate-500">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-blue-500" />
            <p>Loading registered CCTV cameras...</p>
          </div>
        ) : cameras.length === 0 ? (
          <div className="col-span-full py-16 text-center rounded-2xl bg-slate-900/40 border border-slate-800 p-8 space-y-3">
            <Camera className="w-12 h-12 text-slate-600 mx-auto" />
            <h3 className="text-white font-semibold text-base">No Cameras Registered Yet</h3>
            <p className="text-slate-400 text-sm max-w-sm mx-auto">
              Add your first RTSP stream or local camera device to begin monitoring.
            </p>
            <button
              onClick={() => setAddModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              <span>Register Camera</span>
            </button>
          </div>
        ) : (
          cameras.map((cam) => {
            const isOnline = cam.status === "ONLINE";
            const session = sessions[cam.id];

            return (
              <div
                key={cam.id}
                className="bg-slate-900/60 backdrop-blur-sm rounded-2xl p-5 border border-slate-800 hover:border-slate-700/80 transition-all flex flex-col justify-between space-y-4"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-white font-bold text-base flex items-center gap-2">
                      <span>{cam.name}</span>
                    </h3>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                        isOnline ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
                      }`}
                    >
                      {cam.status}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-400">
                    <p className="flex items-center justify-between">
                      <span>Camera ID:</span>
                      <span className="text-slate-200 font-mono font-semibold">{cam.camera_id}</span>
                    </p>
                    {cam.building && (
                      <p className="flex items-center justify-between">
                        <span>Location:</span>
                        <span className="text-slate-300">
                          {cam.building} {cam.room ? `· ${cam.room}` : ""}
                        </span>
                      </p>
                    )}
                    {cam.stream_url && (
                      <p className="flex items-center justify-between truncate">
                        <span>RTSP Stream:</span>
                        <span className="text-cyan-400 font-mono truncate max-w-[180px]">{cam.stream_url}</span>
                      </p>
                    )}
                  </div>
                </div>

                {/* Video Preview or Connect Controls */}
                <div className="space-y-3 pt-2 border-t border-slate-800/80">
                  {session ? (
                    <div className="space-y-2">
                      <div className="overflow-hidden rounded-xl bg-slate-950 aspect-video relative">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={api.getMjpegUrl(session.key, true, 15)}
                          alt={`Live preview for ${cam.name}`}
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 text-[10px] font-mono text-emerald-400">
                          {session.capture_fps.toFixed(1)} FPS
                        </div>
                      </div>

                      <div className="flex items-center justify-between gap-2">
                        <button
                          type="button"
                          onClick={() => stopCamera(cam.id)}
                          className="flex-1 py-1.5 px-3 rounded-lg bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 text-red-400 text-xs font-semibold flex items-center justify-center gap-1.5"
                        >
                          <Square className="w-3.5 h-3.5 fill-current" />
                          <span>Stop Stream</span>
                        </button>
                        <Link
                          href="/monitor"
                          className="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-medium flex items-center gap-1"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          <span>Live Monitor</span>
                        </Link>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="h-28 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-center justify-center text-slate-600 text-xs font-medium gap-2">
                        <Camera className="w-5 h-5 opacity-40" />
                        <span>Stream Inactive</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => startCamera(cam.id)}
                        className="w-full py-2 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-300 text-xs font-semibold flex items-center justify-center gap-1.5"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Start Camera Feed</span>
                      </button>
                    </div>
                  )}

                  {errors[cam.id] && (
                    <p className="text-xs text-red-400 bg-red-950/30 p-2 rounded-lg border border-red-800/40">
                      {errors[cam.id]}
                    </p>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add Camera Modal */}
      {addModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-lg w-full rounded-2xl bg-slate-900 border border-slate-700 p-6 space-y-5 shadow-2xl">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Camera className="w-5 h-5 text-blue-400" />
              Register CCTV / RTSP Camera
            </h3>
            <p className="text-xs text-slate-400">
              Configure an IP camera with RTSP or HTTP video stream for offline classroom/corridor attendance capture.
            </p>

            <form onSubmit={handleAddCamera} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-300 mb-1">Camera Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Main Entrance CCTV #1"
                  value={newCamera.name}
                  onChange={(e) => setNewCamera({ ...newCamera, name: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-blue-500 text-sm"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">Camera Identifier (Code) *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CAM-ENTRANCE-01"
                  value={newCamera.camera_id}
                  onChange={(e) => setNewCamera({ ...newCamera, camera_id: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-blue-500 font-mono text-sm"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">RTSP / Stream URL</label>
                <input
                  type="text"
                  placeholder="rtsp://admin:pass@192.168.1.100:554/stream1 or 0 for local webcam"
                  value={newCamera.stream_url}
                  onChange={(e) => setNewCamera({ ...newCamera, stream_url: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-blue-500 font-mono text-sm"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Supports Hikvision, Dahua, Uniview, generic RTSP over TCP, and local UVC cameras.
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Building</label>
                  <input
                    type="text"
                    placeholder="e.g. Science Block"
                    value={newCamera.building}
                    onChange={(e) => setNewCamera({ ...newCamera, building: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-blue-500 text-sm"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Room / Zone</label>
                  <input
                    type="text"
                    placeholder="e.g. Hallway 102"
                    value={newCamera.room}
                    onChange={(e) => setNewCamera({ ...newCamera, room: e.target.value })}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-blue-500 text-sm"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setAddModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold flex items-center gap-2"
                >
                  {submitting ? "Saving..." : "Save Camera"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
