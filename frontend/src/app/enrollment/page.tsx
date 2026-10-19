"use client";

import React, { useState, useEffect } from "react";
import {
  api,
  type StudentSummary,
  type EmployeeSummary,
} from "@/lib/api";
import {
  UserPlus,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Camera,
  Glasses,
  SunMedium,
  Smile,
  ShieldCheck,
  FileImage,
  RefreshCw,
} from "lucide-react";

export default function FaceEnrollmentPage() {
  const [students, setStudents] = useState<StudentSummary[]>([]);
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [personType, setPersonType] = useState<"student" | "employee">("student");
  const [selectedPersonId, setSelectedPersonId] = useState<string>("");
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<{ filename: string; success: boolean; message: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listStudents(0, 200).then((res) => setStudents(res.items)).catch(() => undefined);
    api.listEmployees(0, 200).then((res) => setEmployees(res.items)).catch(() => undefined);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    setFiles((prev) => [...prev, ...selected]);

    const newPreviews = selected.map((file) => URL.createObjectURL(file));
    setPreviews((prev) => [...prev, ...newPreviews]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setPreviews((prev) => prev.filter((_, i) => i !== index));
  };

  const handleEnroll = async () => {
    if (files.length === 0) {
      setError("Please select at least one face photo for enrollment.");
      return;
    }
    setUploading(true);
    setError(null);
    setResults([]);

    const uploadResults: { filename: string; success: boolean; message: string }[] = [];

    for (const file of files) {
      try {
        const res = await api.uploadEnrollmentImage(file);
        uploadResults.push({
          filename: file.name,
          success: true,
          message: res.message || "Face image processed and stored locally",
        });
      } catch (err) {
        uploadResults.push({
          filename: file.name,
          success: false,
          message: err instanceof Error ? err.message : "Enrollment failed",
        });
      }
    }

    setResults(uploadResults);
    setUploading(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <UserPlus className="w-6 h-6 text-blue-400" />
          Face Enrollment Studio
        </h1>
        <p className="text-slate-400 text-sm">
          Register robust biometric face signatures for offline CCTV recognition across appearance changes (glasses, hairstyles, lighting).
        </p>
      </div>

      {/* Recommended Practice Alert */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-sm space-y-2">
          <div className="flex items-center gap-2 text-cyan-400 font-semibold">
            <Glasses className="w-4 h-4" />
            <span>Glasses & Hairstyle</span>
          </div>
          <p className="text-xs text-slate-400">
            For individuals who wear glasses, enroll both with and without glasses to ensure high ArcFace cosine similarity under all conditions.
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-sm space-y-2">
          <div className="flex items-center gap-2 text-blue-400 font-semibold">
            <SunMedium className="w-4 h-4" />
            <span>Varied Lighting</span>
          </div>
          <p className="text-xs text-slate-400">
            Include photos in indoor lighting, hallway lighting, and natural illumination to make detection invariant to CCTV light shifts.
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-sm space-y-2">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold">
            <Smile className="w-4 h-4" />
            <span>Multi-Angle Observations</span>
          </div>
          <p className="text-xs text-slate-400">
            Upload frontal face, slight left turn, and slight right turn (within 30 degrees) for optimal CCTV camera matching.
          </p>
        </div>
      </div>

      {/* Enrollment Card */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
              Identity Type
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setPersonType("student")}
                className={`flex-1 py-2.5 rounded-xl border text-sm font-semibold transition-all ${
                  personType === "student"
                    ? "bg-blue-600/20 border-blue-500/50 text-blue-300"
                    : "bg-slate-800/40 border-slate-700 text-slate-400"
                }`}
              >
                Student
              </button>
              <button
                type="button"
                onClick={() => setPersonType("employee")}
                className={`flex-1 py-2.5 rounded-xl border text-sm font-semibold transition-all ${
                  personType === "employee"
                    ? "bg-blue-600/20 border-blue-500/50 text-blue-300"
                    : "bg-slate-800/40 border-slate-700 text-slate-400"
                }`}
              >
                Staff / Employee
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
              Select Enrollee
            </label>
            <select
              value={selectedPersonId}
              onChange={(e) => setSelectedPersonId(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">-- Choose individual from database --</option>
              {personType === "student"
                ? students.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.student_id})
                    </option>
                  ))
                : employees.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name} ({e.employee_id})
                    </option>
                  ))}
            </select>
          </div>
        </div>

        {/* Upload Zone */}
        <div>
          <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
            Biometric Face Photos (Multiple Recommended)
          </label>
          <div className="border-2 border-dashed border-slate-700 hover:border-blue-500 rounded-2xl p-8 text-center transition-all bg-slate-950/40 cursor-pointer relative">
            <input
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileSelect}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
            <div className="space-y-3 pointer-events-none">
              <div className="w-12 h-12 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 mx-auto">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <p className="text-white text-sm font-semibold">Click to upload or drag and drop images</p>
                <p className="text-xs text-slate-500 mt-1">JPEG, PNG, or WebP up to 10MB per image</p>
              </div>
            </div>
          </div>
        </div>

        {/* Selected Photos Preview */}
        {previews.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
              <span>Selected Images ({previews.length})</span>
              <button
                type="button"
                onClick={() => {
                  setFiles([]);
                  setPreviews([]);
                }}
                className="text-red-400 hover:text-red-300"
              >
                Clear all
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
              {previews.map((src, idx) => (
                <div key={idx} className="relative group rounded-xl overflow-hidden aspect-square border border-slate-700 bg-slate-950">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={src} alt="Preview" className="w-full h-full object-cover" />
                  <button
                    type="button"
                    onClick={() => removeFile(idx)}
                    className="absolute top-1 right-1 bg-red-600/80 hover:bg-red-600 text-white rounded-md p-1 opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Submit */}
        <div className="pt-2 flex justify-end">
          <button
            type="button"
            onClick={handleEnroll}
            disabled={uploading || files.length === 0}
            className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-all"
          >
            {uploading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Processing Biometric Signatures...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                <span>Enroll into Local FAISS Database</span>
              </>
            )}
          </button>
        </div>

        {/* Results */}
        {results.length > 0 && (
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <h4 className="text-sm font-semibold text-white">Enrollment Processing Results</h4>
            <div className="space-y-1.5 text-xs">
              {results.map((r, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-slate-900 border border-slate-800">
                  <span className="font-mono text-slate-300">{r.filename}</span>
                  <span className={r.success ? "text-emerald-400 flex items-center gap-1" : "text-red-400 flex items-center gap-1"}>
                    {r.success ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                    {r.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
