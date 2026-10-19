"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  api,
  type CameraSummary,
  type VideoSession,
} from "@/lib/api";
import {
  Video,
  Play,
  Square,
  RefreshCw,
  Maximize2,
  Minimize2,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Zap,
  Activity,
  Layers,
  CheckCircle2,
  UserX,
  Volume2,
  VolumeX,
} from "lucide-react";

interface RecognitionEvent {
  id: string;
  camera_key: string;
  track_id: string | number;
  student_name?: string;
  amfr_decision: string;
  confidence: number;
  liveness_score?: number;
  quality_score?: number;
  attendance_marked: boolean;
  latency_ms: number;
  timestamp: string;
}

// ── ISOLATED VIDEO ELEMENT ───────────────────────────────────────────
// Kept strictly isolated from recognition state updates to prevent stream remounting
const StreamViewer = React.memo(function StreamViewer({
  mjpegUrl,
  cameraName,
  isFullscreen,
}: {
  mjpegUrl: string;
  cameraName: string;
  isFullscreen: boolean;
}) {
  return (
    <div className={`relative w-full h-full flex items-center justify-center bg-black overflow-hidden ${isFullscreen ? "fixed inset-0 z-50 p-4" : "rounded-2xl"}`}>
      {/* Native img tag delivers the multipart/x-mixed-replace stream */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={mjpegUrl}
        alt={`Live Feed: ${cameraName}`}
        className="max-w-full max-h-full object-contain"
        loading="eager"
      />
      <div className="absolute top-4 left-4 flex items-center gap-2 bg-slate-950/70 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/50 text-xs font-mono">
        <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
        <span className="font-semibold text-white">LIVE</span>
        <span className="text-slate-400">|</span>
        <span className="text-cyan-300">{cameraName}</span>
      </div>
    </div>
  );
});

export default function LiveMonitorPage() {
  const [cameras, setCameras] = useState<CameraSummary[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null);
  const [session, setSession] = useState<VideoSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [annotate, setAnnotate] = useState(true);
  const [targetFps, setTargetFps] = useState(20);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [events, setEvents] = useState<RecognitionEvent[]>([]);
  const [soundEnabled, setSoundEnabled] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const activeSessionKeyRef = useRef<string | null>(null);

  // Load registered cameras
  const loadCameras = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.listCameras();
      setCameras(res.items);
      if (res.items.length > 0 && selectedCameraId === null) {
        setSelectedCameraId(res.items[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cameras");
    } finally {
      setLoading(false);
    }
  }, [selectedCameraId]);

  useEffect(() => {
    loadCameras();
  }, [loadCameras]);

  // Start live session
  const handleStartStream = async () => {
    if (!selectedCameraId) return;
    setStarting(true);
    setError(null);
    try {
      const sess = await api.startVideoSession(selectedCameraId);
      setSession(sess);
      activeSessionKeyRef.current = sess.key;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start camera feed");
    } finally {
      setStarting(false);
    }
  };

  // Stop live session
  const handleStopStream = async () => {
    if (!session) return;
    try {
      await api.stopVideoSession(session.key);
    } catch (err) {
      console.warn("Stop stream error:", err);
    } finally {
      setSession(null);
      activeSessionKeyRef.current = null;
    }
  };

  // Poll session diagnostics every 2 seconds without touching the video img
  useEffect(() => {
    if (!session?.key) return;
    const sessionKey = session.key;
    const interval = setInterval(() => {
      api.getVideoSessionStatus(sessionKey)
        .then((s) => {
          setSession(s);
        })
        .catch(() => undefined);
    }, 2000);

    return () => clearInterval(interval);
  }, [session?.key]);

  // WebSocket for real-time recognition events (out of band from video feed)
  useEffect(() => {
    if (!selectedCameraId) return;
    const ws = api.createWebSocket(selectedCameraId);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "recognition") {
          const newEvt: RecognitionEvent = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            ...data,
          };
          setEvents((prev) => [newEvt, ...prev.slice(0, 49)]); // keep last 50
        }
      } catch (err) {
        console.error("WS parse error", err);
      }
    };

    return () => {
      ws.close();
    };
  }, [selectedCameraId]);

  // Cleanup session on unmount
  useEffect(() => {
    return () => {
      if (activeSessionKeyRef.current) {
        api.stopVideoSession(activeSessionKeyRef.current).catch(() => undefined);
      }
    };
  }, []);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const selectedCam = cameras.find((c) => c.id === selectedCameraId);
  const mjpegUrl = session ? api.getMjpegUrl(session.key, annotate, targetFps) : "";

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Video className="w-6 h-6 text-blue-400" />
            Live CCTV Monitor
          </h1>
          <p className="text-slate-400 text-sm">
            High-performance real-time video stream with biometric identity overlays and offline attendance verification.
          </p>
        </div>

        {/* Controls Bar */}
        <div className="flex items-center gap-3">
          <select
            value={selectedCameraId ?? ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setSelectedCameraId(id);
              if (session) {
                handleStopStream();
              }
            }}
            disabled={starting}
            className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-blue-500 font-medium"
          >
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.camera_id})
              </option>
            ))}
          </select>

          {!session ? (
            <button
              onClick={handleStartStream}
              disabled={starting || !selectedCameraId}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-sm flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-all"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>{starting ? "Connecting..." : "Start Feed"}</span>
            </button>
          ) : (
            <button
              onClick={handleStopStream}
              className="px-4 py-2 rounded-xl bg-red-600/80 hover:bg-red-600 text-white font-medium text-sm flex items-center gap-2 shadow-lg shadow-red-600/20 transition-all"
            >
              <Square className="w-4 h-4 fill-current" />
              <span>Stop Feed</span>
            </button>
          )}

          <button
            onClick={() => setAnnotate(!annotate)}
            className={`px-3 py-2 rounded-xl border text-sm font-medium transition-all flex items-center gap-1.5 ${
              annotate
                ? "bg-cyan-950/60 border-cyan-700/60 text-cyan-300"
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white"
            }`}
            title="Toggle biometric bounding box & identity overlays"
          >
            <Layers className="w-4 h-4" />
            <span>Overlays</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-sm flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Monitoring Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Video Display (2 columns) */}
        <div className="lg:col-span-2 space-y-4">
          <div
            ref={containerRef}
            className="w-full aspect-[4/3] md:aspect-video rounded-2xl bg-slate-950 border border-slate-800 flex items-center justify-center relative overflow-hidden shadow-2xl"
          >
            {session && mjpegUrl ? (
              <StreamViewer
                mjpegUrl={mjpegUrl}
                cameraName={selectedCam?.name ?? "CCTV Feed"}
                isFullscreen={isFullscreen}
              />
            ) : (
              <div className="text-center p-8 space-y-4">
                <div className="w-16 h-16 mx-auto rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-600">
                  <Video className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-white font-semibold text-base">Camera Feed Inactive</h3>
                  <p className="text-slate-400 text-sm max-w-sm mx-auto mt-1">
                    Select a CCTV camera and click &quot;Start Feed&quot; to initiate real-time RTSP/Webcam stream capture.
                  </p>
                </div>
                {selectedCameraId && (
                  <button
                    onClick={handleStartStream}
                    disabled={starting}
                    className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm inline-flex items-center gap-2"
                  >
                    <Play className="w-4 h-4 fill-current" />
                    <span>Connect Camera</span>
                  </button>
                )}
              </div>
            )}

            {/* Video Controls Overlay */}
            {session && (
              <div className="absolute bottom-4 right-4 flex items-center gap-2 z-10">
                <button
                  onClick={toggleFullscreen}
                  className="p-2 rounded-lg bg-slate-950/70 hover:bg-slate-900 text-slate-300 hover:text-white border border-slate-700/60 backdrop-blur-md transition-all"
                  title="Fullscreen"
                >
                  {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                </button>
              </div>
            )}
          </div>

          {/* Real-time Diagnostics HUD */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-blue-400" />
                  Capture Rate
                </span>
                <span className="font-mono text-slate-300">Target 30</span>
              </div>
              <div className="text-xl font-bold font-mono text-white">
                {session?.capture_fps ? `${session.capture_fps.toFixed(1)} FPS` : "0.0 FPS"}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-cyan-400" />
                  AI Cadence
                </span>
                <span className="font-mono text-slate-300">YOLO+ArcFace</span>
              </div>
              <div className="text-xl font-bold font-mono text-cyan-300">
                {session?.ai_fps ? `${session.ai_fps.toFixed(1)} FPS` : "0.0 FPS"}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-emerald-400" />
                  Frame Age
                </span>
                <span className="text-emerald-400 text-[10px] font-mono">FRESH</span>
              </div>
              <div className="text-xl font-bold font-mono text-emerald-400">
                {session?.frame_age_ms !== undefined ? `${session.frame_age_ms.toFixed(1)} ms` : "< 15 ms"}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                  AI Latency
                </span>
                <span className="font-mono text-slate-300">P50</span>
              </div>
              <div className="text-xl font-bold font-mono text-amber-300">
                {session?.last_latency_ms ? `${session.last_latency_ms.toFixed(1)} ms` : "0.0 ms"}
              </div>
            </div>
          </div>
        </div>

        {/* Real-time Recognition Events Sidebar (1 column) */}
        <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800/80 flex flex-col h-full min-h-[500px]">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-cyan-400" />
              <h2 className="text-base font-semibold text-white">Live Detections</h2>
            </div>
            <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
              {events.length} events
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
            {events.length === 0 ? (
              <div className="text-center py-16 text-slate-500 space-y-2">
                <UserX className="w-8 h-8 mx-auto opacity-50" />
                <p className="text-sm">Awaiting biometric detections...</p>
                <p className="text-xs text-slate-600">Events appear here automatically as faces are recognized.</p>
              </div>
            ) : (
              events.map((evt) => {
                const isAccept = evt.amfr_decision === "ACCEPT";
                const isBorderline = evt.amfr_decision === "BORDERLINE";
                const isSpoof = evt.amfr_decision === "REJECT_SPOOF";

                return (
                  <div
                    key={evt.id}
                    className={`p-3.5 rounded-xl border text-sm transition-all ${
                      isAccept
                        ? "bg-emerald-950/20 border-emerald-800/40 text-emerald-200"
                        : isSpoof
                        ? "bg-red-950/20 border-red-800/40 text-red-200"
                        : "bg-amber-950/20 border-amber-800/40 text-amber-200"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-white">
                        {evt.student_name || `Track #${evt.track_id}`}
                      </span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase ${
                          isAccept
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : isSpoof
                            ? "bg-red-500/20 text-red-400 border border-red-500/30"
                            : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                        }`}
                      >
                        {evt.amfr_decision}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-400 mt-2">
                      <div className="flex items-center gap-2">
                        <span>Score: {(evt.confidence * 100).toFixed(0)}%</span>
                        {evt.liveness_score !== undefined && (
                          <span>Live: {(evt.liveness_score * 100).toFixed(0)}%</span>
                        )}
                      </div>
                      <span className="font-mono text-[10px]">
                        {new Date(evt.timestamp).toLocaleTimeString([], { hour12: false })}
                      </span>
                    </div>

                    {evt.attendance_marked && (
                      <div className="mt-2 pt-2 border-t border-emerald-800/30 flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Attendance Recorded Locally</span>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
