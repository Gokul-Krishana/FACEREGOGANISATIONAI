
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AUTH_DISABLED = process.env.NEXT_PUBLIC_DISABLE_AUTH === "true";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

export interface StudentSummary {
  id: number;
  student_id: string;
  name: string;
  email?: string;
  department_id?: number | null;
  is_active: boolean;
}

export interface EmployeeSummary {
  id: number;
  employee_id: string;
  name: string;
  department?: string | null;
  photo_path?: string | null;
  faiss_id?: number | null;
  created_at?: string;
  updated_at?: string | null;
}

export interface CameraSummary {
  id: number;
  name: string;
  camera_id: string;
  stream_url?: string | null;
  location?: string | null;
  building?: string | null;
  room?: string | null;
  status: string;
  is_active: boolean;
}

export interface VideoSession {
  key: string;
  source_type: string;
  camera_kwargs: Record<string, unknown>;
  status: string;
  error?: string | null;
  capture_fps: number;
  ai_fps: number;
  last_latency_ms: number;
  frame_count: number;
  frame_seq?: number;
  frame_age_ms?: number;
  dropped_frames: number;
}

export interface AttendanceSummary {
  id: number;
  student_id: number;
  student_name: string;
  timestamp: string;
  confidence: number;
  method: string;
  status: string;
  section_id?: number | null;
  course_id?: number | null;
  classroom_id?: number | null;
}

export interface AuditLogItem {
  id: number;
  action: string;
  actor: string;
  actor_type?: string;
  actor_id?: number | null;
  timestamp: string;
  resource_type?: string | null;
  resource_id?: number | null;
  description?: string | null;
  ip_address?: string | null;
  severity?: string;
  details?: Record<string, unknown>;
}

export interface UnknownFaceItem {
  id: number;
  image_path?: string | null;
  timestamp: string;
  camera_id?: number | null;
  camera_name?: string | null;
  confidence?: number;
  reviewed: boolean;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  converted_to_employee?: boolean;
}

export interface SystemStatus {
  status: string;
  version: string;
  timestamp: string;
  database: string;
  redis: string;
  active_cameras?: number;
  total_enrolled?: number;
  today_attendance?: number;
  offline_mode?: boolean;
  device?: string;
}

class ApiClient {
  private baseUrl: string;
  private accessToken: string | null = null;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
    if (typeof window !== "undefined") {
      this.accessToken = localStorage.getItem("access_token");
    }
  }

  setToken(token: string) {
    this.accessToken = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", token);
    }
  }

  clearToken() {
    this.accessToken = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    retried = false
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }

    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    // ── Auto-refresh on 401 if we have a refresh token ─────
    if (res.status === 401 && !retried) {
      const refreshed = await this._tryRefresh();
      if (refreshed) {
        // Retry with the new token — guards against infinite loop via _retried
        headers["Authorization"] = `Bearer ${this.accessToken}`;
        const retryRes = await fetch(`${this.baseUrl}${path}`, {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
        });
        if (retryRes.ok) {
          return retryRes.json();
        }
      }
      // Refresh failed — force logout unless local development auth is disabled.
      this.clearToken();
      if (typeof window !== "undefined" && !AUTH_DISABLED) {
        window.location.href = "/auth/login";
      }
      throw new Error("Session expired. Please login again.");
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
  }

  /** Attempt to refresh the access token using the stored refresh token. */
  private async _tryRefresh(): Promise<boolean> {
    const refreshToken =
      typeof window !== "undefined"
        ? localStorage.getItem("refresh_token")
        : null;
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        // Refresh token invalid/expired — clear everything
        this.clearToken();
        return false;
      }

      const data = await res.json();
      this.setToken(data.access_token);
      if (data.refresh_token) {
        if (typeof window !== "undefined") {
          localStorage.setItem("refresh_token", data.refresh_token);
        }
      }
      return true;
    } catch {
      this.clearToken();
      return false;
    }
  }

  // ── Auth ─────────────────────────────────────────────────────
  async logout() {
    try {
      await this.request<{ message: string }>("POST", "/auth/logout");
    } catch (err) {
      console.warn("Logout API call failed, clearing local session:", err);
    }
    this.clearToken();
  }

  async login(username: string, password: string) {
    return this.request<{ access_token: string; refresh_token?: string; requires_mfa?: boolean; mfa_token?: string }>(
      "POST",
      "/auth/login",
      { username, password }
    );
  }

  async verifyMfa(code: string, mfaToken: string) {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${mfaToken}`,
    };
    const res = await fetch(`${this.baseUrl}/auth/mfa/verify`, {
      method: "POST",
      headers,
      body: JSON.stringify({ code, use_backup: false }),
    });
    if (!res.ok) throw new Error("MFA verification failed");
    return res.json();
  }

  async getMe() {
    return this.request<{ id: number; username: string; email: string; roles: string[] }>("GET", "/auth/me");
  }

  // ── Students ─────────────────────────────────────────────────
  async listStudents(skip = 0, limit = 100, q?: string) {
    const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (q) query.set("q", q);
    return this.request<PaginatedResponse<StudentSummary>>("GET", `/students?${query.toString()}`);
  }

  async getStudent(id: number) {
    return this.request<StudentSummary>(
      "GET",
      `/students/${id}`
    );
  }

  // ── Employees ────────────────────────────────────────────────
  async listEmployees(skip = 0, limit = 100, q?: string) {
    const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (q) query.set("q", q);
    return this.request<PaginatedResponse<EmployeeSummary>>("GET", `/employees?${query.toString()}`);
  }

  // ── Cameras ──────────────────────────────────────────────────
  async listCameras(skip = 0, limit = 100, q?: string) {
    const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (q) query.set("q", q);
    return this.request<PaginatedResponse<CameraSummary>>("GET", `/cameras?${query.toString()}`);
  }

  async startVideoSession(cameraId: number) {
    return this.request<VideoSession>("POST", "/video/sessions/start", { camera_id: cameraId });
  }

  async stopVideoSession(sessionKey: string) {
    return this.request<{ key: string; status: string }>(
      "POST",
      `/video/sessions/${encodeURIComponent(sessionKey)}/stop`
    );
  }

  async getVideoSessionStatus(sessionKey: string) {
    return this.request<VideoSession>(
      "GET",
      `/video/sessions/${encodeURIComponent(sessionKey)}/status`
    );
  }

  getMjpegUrl(sessionKey: string, annotate = true, fps = 20) {
    const params = new URLSearchParams({
      token: this.accessToken || "",
      annotate: String(annotate),
      fps: String(fps),
    });
    return `${this.baseUrl}/video/sessions/${encodeURIComponent(sessionKey)}/mjpeg?${params.toString()}`;
  }

  // ── Attendance ───────────────────────────────────────────────
  async listAttendance(params: { student_id?: number; section_id?: number; course_id?: number; date_from?: string; date_to?: string; limit?: number; skip?: number } = {}) {
    const query = new URLSearchParams();
    if (params.student_id) query.set("student_id", String(params.student_id));
    if (params.section_id) query.set("section_id", String(params.section_id));
    if (params.course_id) query.set("course_id", String(params.course_id));
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.limit) query.set("limit", String(params.limit));
    if (params.skip) query.set("skip", String(params.skip));
    return this.request<PaginatedResponse<AttendanceSummary>>("GET", `/attendance?${query.toString()}`);
  }

  // ── Analytics ────────────────────────────────────────────────
  async getAttendanceSummary(dateFrom?: string, dateTo?: string) {
    const query = new URLSearchParams();
    if (dateFrom) query.set("date_from", dateFrom);
    if (dateTo) query.set("date_to", dateTo);
    return this.request<{ date: string; total_attendance: number; unique_students: number }[]>(
      "GET",
      `/analytics/attendance-summary?${query.toString()}`
    );
  }

  // ── Health ───────────────────────────────────────────────────
  async healthCheck() {
    return this.request<{ status: string; version: string; timestamp: string; database: string; redis: string }>(
      "GET",
      "/health"
    );
  }

  async readinessCheck() {
    return this.request<{ ready: boolean; checks: Record<string, string> }>("GET", "/health/ready");
  }

  // ── Jobs ─────────────────────────────────────────────────────
  async createJob(jobType: string, params: Record<string, unknown> = {}) {
    return this.request<{ job_id: string; status: string }>("POST", "/jobs", { job_type: jobType, params });
  }

  async listJobs() {
    return this.request<{ jobs: unknown[]; stats: Record<string, unknown> }>("GET", "/jobs");
  }

  // ── Audit Logs ──────────────────────────────────────────────
  async listAuditLogs(skip = 0, limit = 50, action?: string, severity?: string) {
    const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (action) query.set("action", action);
    if (severity) query.set("severity", severity);
    return this.request<PaginatedResponse<AuditLogItem>>("GET", `/audit-logs?${query.toString()}`);
  }

  // ── Unknown Faces ────────────────────────────────────────────
  async listUnknownFaces(skip = 0, limit = 50) {
    const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    return this.request<PaginatedResponse<UnknownFaceItem>>("GET", `/unknown-faces?${query.toString()}`);
  }

  async reviewUnknownFace(faceId: number, action: "approve" | "dismiss" | "delete", employeeId?: number) {
    const query = new URLSearchParams({ action });
    if (employeeId) query.set("employee_id", String(employeeId));
    return this.request<{ message: string }>("POST", `/unknown-faces/${faceId}/review?${query.toString()}`);
  }

  // ── Enrollment ───────────────────────────────────────────────
  async uploadEnrollmentImage(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    const headers: Record<string, string> = {};
    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }
    const res = await fetch(`${this.baseUrl}/enroll/upload`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail || "Upload failed");
    }
    return res.json() as Promise<{ filename: string; size_bytes: number; message: string }>;
  }

  // ── Camera Management ────────────────────────────────────────
  async createCamera(payload: { name: string; camera_id: string; stream_url?: string; location?: string; building?: string; room?: string }) {
    return this.request<CameraSummary>("POST", "/cameras", payload);
  }

  async updateCameraStatus(cameraId: string, status: "ONLINE" | "OFFLINE" | "ERROR") {
    return this.request<CameraSummary>("PATCH", `/cameras/${encodeURIComponent(cameraId)}/status`, { status });
  }

  getAttendanceExportUrl() {
    return `${this.baseUrl}/bulk/attendance/export?token=${encodeURIComponent(this.accessToken || "")}`;
  }

  // ── System Status ────────────────────────────────────────────
  async getSystemStatus() {
    return this.request<SystemStatus>("GET", "/system/status");
  }

  // ── WebSocket ────────────────────────────────────────────────
  createWebSocket(cameraId?: number) {
    const wsUrl = this.baseUrl.replace("http", "ws");
    const params = new URLSearchParams({ token: this.accessToken || "" });
    if (cameraId) params.set("camera_id", String(cameraId));
    return new WebSocket(`${wsUrl}/ws/live?${params.toString()}`);
  }
}

export const api = new ApiClient();
