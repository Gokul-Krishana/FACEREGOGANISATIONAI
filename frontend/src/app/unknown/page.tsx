"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  api,
  type UnknownFaceItem,
  type EmployeeSummary,
} from "@/lib/api";
import {
  UserX,
  CheckCircle2,
  Trash2,
  Eye,
  RefreshCw,
  AlertCircle,
  Calendar,
  Camera,
  UserCheck,
} from "lucide-react";

export default function UnknownFacesPage() {
  const [faces, setFaces] = useState<UnknownFaceItem[]>([]);
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFace, setSelectedFace] = useState<UnknownFaceItem | null>(null);
  const [assignEmployeeId, setAssignEmployeeId] = useState<number | "">("");
  const [processing, setProcessing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [faceRes, empRes] = await Promise.all([
        api.listUnknownFaces(0, 100),
        api.listEmployees(0, 200).catch(() => ({ items: [] })),
      ]);
      setFaces(faceRes.items);
      setEmployees(empRes.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load unknown faces");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleReview = async (faceId: number, action: "approve" | "dismiss" | "delete", empId?: number) => {
    setProcessing(true);
    try {
      await api.reviewUnknownFace(faceId, action, empId);
      // Remove or update the reviewed face locally
      setFaces((prev) => prev.filter((f) => f.id !== faceId));
      setSelectedFace(null);
      setAssignEmployeeId("");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Action failed");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <UserX className="w-6 h-6 text-amber-400" />
            Unknown Faces Review
          </h1>
          <p className="text-slate-400 text-sm">
            Review unassigned or low-confidence CCTV detections. Prevent false attendance by manual inspection and approval.
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-200 text-sm font-medium flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Grid of Unknown Faces */}
      {loading ? (
        <div className="p-12 text-center text-slate-500">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2 text-blue-500" />
          <p>Loading detections for review...</p>
        </div>
      ) : faces.length === 0 ? (
        <div className="p-16 text-center rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-white">No Pending Unknown Faces</h3>
          <p className="text-sm text-slate-400 max-w-md mx-auto">
            All detected faces are either confidently recognized or have already been reviewed. The system is operating cleanly.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {faces.map((f) => (
            <div
              key={f.id}
              className="rounded-2xl bg-slate-900/60 border border-slate-800/80 overflow-hidden flex flex-col justify-between p-4 space-y-3 hover:border-slate-700 transition-all"
            >
              <div className="space-y-3">
                <div className="aspect-square rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center overflow-hidden">
                  {f.image_path ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={f.image_path} alt={`Unknown Face #${f.id}`} className="w-full h-full object-cover" />
                  ) : (
                    <UserX className="w-12 h-12 text-slate-700" />
                  )}
                </div>

                <div className="space-y-1 text-xs">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="flex items-center gap-1">
                      <Camera className="w-3.5 h-3.5 text-blue-400" />
                      Camera:
                    </span>
                    <span className="font-medium text-slate-200">{f.camera_name || f.camera_id || "Main CCTV"}</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-cyan-400" />
                      Recorded:
                    </span>
                    <span className="font-mono text-slate-300">
                      {f.timestamp ? new Date(f.timestamp).toLocaleTimeString() : "Recent"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Review Buttons */}
              <div className="pt-2 border-t border-slate-800 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedFace(f)}
                  className="flex-1 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-300 text-xs font-semibold flex items-center justify-center gap-1"
                >
                  <UserCheck className="w-3.5 h-3.5" />
                  <span>Assign</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleReview(f.id, "dismiss")}
                  disabled={processing}
                  className="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
                >
                  Dismiss
                </button>
                <button
                  type="button"
                  onClick={() => handleReview(f.id, "delete")}
                  disabled={processing}
                  className="py-1.5 px-2 rounded-lg bg-red-950/40 hover:bg-red-900/60 text-red-400 text-xs"
                  title="Delete record"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Assignment Modal */}
      {selectedFace && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-md w-full rounded-2xl bg-slate-900 border border-slate-700 p-6 space-y-5 shadow-2xl">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-blue-400" />
              Assign Detection to Person
            </h3>
            <p className="text-xs text-slate-400">
              Select an enrolled employee or student to link this observation and confirm their attendance.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-2">Select Enrolled Person</label>
              <select
                value={assignEmployeeId}
                onChange={(e) => setAssignEmployeeId(Number(e.target.value) || "")}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value="">-- Choose individual --</option>
                {employees.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} ({e.employee_id}) - {e.department || "General"}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setSelectedFace(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  if (assignEmployeeId) {
                    handleReview(selectedFace.id, "approve", Number(assignEmployeeId));
                  }
                }}
                disabled={!assignEmployeeId || processing}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold flex items-center gap-2"
              >
                Confirm Assignment
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
