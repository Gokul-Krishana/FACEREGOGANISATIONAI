# Section 10 — Next.js Frontend

**Run:** `cd frontend && npm run dev` → usually http://localhost:3000
**Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Lucide React, Recharts, Zustand.
**Backend:** FastAPI at `/api` (REST + WebSockets + MJPEG), documented at `/docs`.

## 10.1 Architecture

The frontend is a standalone Next.js app in `frontend/`. It talks to the
backend through a typed API client in `frontend/src/lib/api.ts` and keeps
lightweight auth/session state in a Zustand store in
`frontend/src/lib/store.ts`.

Key design points:

- Auth is session-based JWT. Tokens are stored in `localStorage` and
  refreshed automatically on 401 when a refresh token is available.
- API URLs are configurable via `NEXT_PUBLIC_API_URL` and
  `NEXT_PUBLIC_DISABLE_AUTH`. The example file is `frontend/.env.local`.
- Recognition events are received over WebSocket where supported; the live
  video itself is delivered as MJPEG through a started camera session.
- The live video element is kept independent of high-frequency recognition
  events so the stream does not remount or reconnect on every event.

## 10.2 Pages

| Page | Purpose |
|------|---------|
| `/auth/login` | Sign in with username/password; supports MFA redirect. |
| `/auth/mfa` | MFA verification step when required. |
| `/auth/signin` | Alternative sign-in entry point. |
| `/dashboard` | Overview stats, recent recognition events, connection status. |
| `/cameras` | Camera inventory and per-camera live session controls. |
| `/health` | Backend health and readiness display. |
| `/students` | Student search, table, and pagination. |
| `/attendance` | Attendance records with date-range filters. |
| `/analytics` | Attendance trend summary. |
| `/settings` | Account info, system info, and sign-out. |

The frontend no longer includes Streamlit pages. The old Streamlit dashboard
was removed from the repository; reusable Python helpers that used to support
it now live in `pipeline/`.

## 10.3 Live Video

Live video works through these backend endpoints:

- `POST /video/sessions/start` — start or reuse a camera session.
- `POST /video/sessions/{session_key}/stop` — stop a session.
- `GET /video/sessions/{session_key}/status` — session status and stats.
- `GET /video/sessions/{session_key}/mjpeg?token=...&annotate=...&fps=...`
  — MJPEG stream of the latest frame.
- `WS /ws/live?token=...&camera_id=...` — recognition events.

The frontend starts a session, then renders the MJPEG URL in a stable image
element. Session status is polled at a low cadence for UI updates, while the
video element itself is not recreated on every status change.

## 10.4 API Client

`frontend/src/lib/api.ts` exports a single `api` client with methods for:

- Auth: `login`, `verifyMfa`, `getMe`, `logout`.
- Students: `listStudents`, `getStudent`.
- Employees: `listEmployees`.
- Cameras: `listCameras`, `startVideoSession`, `stopVideoSession`,
  `getVideoSessionStatus`, `getMjpegUrl`.
- Attendance: `listAttendance`.
- Analytics: `getAttendanceSummary`.
- Health: `healthCheck`, `readinessCheck`.
- Jobs: `createJob`, `listJobs`.
- WebSockets: `createWebSocket`.

The same file also defines the shared TypeScript response types, including
`StudentSummary`, `EmployeeSummary`, `CameraSummary`, `VideoSession`, and
`AttendanceSummary`.

## 10.5 Environment

Copy `frontend/.env.local` from the example and adjust:

- `NEXT_PUBLIC_API_URL` — backend base URL.
- `NEXT_PUBLIC_DISABLE_AUTH` — set to `"true"` only for local development
  without authentication.

Do not commit real credentials or tokens into `frontend/.env.local`.

## 10.6 Build and Development

Development server:

```bash
cd frontend
npm install
npm run dev
```

Production build:

```bash
cd frontend
npm run build
npm run start
```

TypeScript checks run as part of the build. The repository’s CI is configured
to ignore `frontend/**` by default because it has its own Node toolchain.

## 10.7 Relation to the Old Streamlit Dashboard

The repository previously used a Streamlit dashboard at
`streamlit run dashboard/app.py`. That dashboard has been removed. The
operator UI is now the Next.js frontend described in this section.
