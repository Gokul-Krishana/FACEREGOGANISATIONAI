# User Manual — Face Recognition AI

**Version:** 2.0.0
**Date:** 2026-08-02
**Audience:** Operators (faculty, security staff, lab assistants) using the
dashboard day to day.

---

## 1. What This System Does

Face Recognition AI automatically marks **attendance** when a registered person
walks in front of a connected camera:

```
Person walks into camera view
        ▼
Green box + name + PRESENT        ← identified, attendance marked
Yellow box + "COLLECTING FRAMES"  ← almost sure, gathering more evidence
Grey box + "UNKNOWN"              ← not enrolled
Red box + "SPOOF DETECTED"        ← photo/screen attempt, rejected
```

**You do not need to do anything for attendance to be recorded.** The system
recognises people, verifies they are live (anti-spoofing), and marks attendance
automatically.

---

## 2. Getting Started

1. Start the dashboard:
   ```bash
   streamlit run dashboard/app.py
   ```
2. Open your browser → **http://localhost:8501**
3. You will see the **Dashboard** (home page) with system overview.

> 🎥 **First live session:** go to **📹 Live Recognition**, select your camera,
> click **START**. A person must be **enrolled** first (see §4) to be recognised
> by name.

---

## 3. The Pages

| Page | What it's for |
|:-----|:--------------|
| 🏠 **Dashboard** | Overview: stats, recognition status, recent attendance, system health at a glance |
| 👥 **Employees** | Search, add, edit, delete people; view their attendance history |
| 📸 **Enroll** | Capture a face so someone can be recognised (one-time setup per person) |
| 📹 **Live Recognition** | Watch the camera feed with live boxes; start/stop; per-camera controls |
| 📋 **Attendance** | Today's / historical attendance records with camera view |
| 🔴 **Unknown Faces** | People the system could not identify; review and decide what to do |
| 📈 **Analytics** | Charts: attendance by day, hour, week, department |
| ⚙️ **Settings** | Tune recognition thresholds, camera defaults, retention |
| 🩺 **System Health** | Live health of database, models, cameras, disk |
| ℹ️ **About** | Version info and credits |

---

## 4. Enrolling a Person (Important!)

For someone to be recognised, their face must be **enrolled** once:

1. Go to **📸 Enroll**.
2. Select the camera and click **Capture**.
3. ⚠️ **Allow camera permission** in the browser when prompted.
4. Face the camera in good light, looking straight ahead.
5. Enter the person's **name** (and optionally an ID/department).
6. Click **Enroll**.

The system extracts a face "fingerprint" (512-D embedding), stores it in the
FAISS index, and creates the person's record. From then on, when they appear in
front of any connected camera, they will be recognised and their attendance
auto-marked.

> **Tip:** capture 1–2 clear frontal photos. If recognition is unreliable,
> lower `recognition_threshold` in Settings (1.0–1.5 is the typical range).

---

## 5. Using Live Recognition

1. Go to **📹 Live Recognition**.
2. **Select camera type**:
   - **PC Camera** (default) — built-in / USB webcam
   - **Android Phone** — enter the IP Webcam URL (e.g. `http://192.168.1.100:8080/video`)
   - **iPhone** — EpocCam
   - **IP / RTSP** — enter the RTSP URL with credentials
3. Click **Scan Cameras** to auto-discover local/network cameras (optional).
4. Click **START**.

**While running:**
- **Green box + name + ID + PRESENT** → attendance marked ✓
- **Yellow box + COLLECTING FRAMES** → system is confirming identity
- **Grey box + UNKNOWN** → person not enrolled
- **Red box + SPOOF DETECTED** → a printed photo/screen was detected; rejected
- The sidebar shows camera info, FPS, people count, and last recognition.

**To switch cameras:** click **STOP**, choose another camera, click **START** —
no restart needed.

**If the camera disconnects:** the status shows DISCONNECTED and the system
auto-reconnects (up to 5 attempts). No action needed.

> Multiple people are tracked independently — each gets their own box, even if
> they walk across each other.

---

## 6. Attendance

- **Today's Attendance** is shown on the Live page and the **📋 Attendance**
  page (auto-refreshes).
- A person is marked **once per day** — repeat appearances show as already
  present and do not create duplicate records.
- Cooldown between re-marks is 60 seconds (configurable in Settings).
- If someone needs a manual correction, use the API
  (`POST /attendance`) — contact your administrator.

---

## 7. Unknown Faces

When someone not enrolled appears, the system saves a snapshot to the
**🔴 Unknown Faces** page.

You can:
- **Review** the image (mark as reviewed)
- **Convert to employee** — the face becomes an enrollment; after that, the
  person is recognised automatically
- **Delete** — remove the record and its image (single or **bulk**)

**Retention:** unknown faces older than the configured retention period
(default 30 days) are deleted automatically (see Settings).

---

## 8. Employees

Use **👥 Employees** to manage people:

- **Search** by name, ID, or department
- **Add** a new employee record (enroll their face separately in Enroll)
- **Edit** — renaming a person keeps recognition working (the FAISS label is
  renamed in sync)
- **Delete** — removes the record **and** their face embedding; they will no
  longer be recognised

> ⚠️ Deleting an employee is permanent. Consider re-enrolling rather than
> deleting if the person will return.

---

## 9. Analytics

The **📈 Analytics** page provides charts:
- Attendance over time (daily, hourly, weekly)
- Per-department breakdowns
- Recognition / unknown-face statistics

These help departments track lecture attendance patterns.

---

## 10. Settings (Operator-Safe Adjustments)

| Setting | Effect |
|:--------|:-------|
| `recognition_threshold` | FAISS L2 distance. **Lower = stricter** (fewer false matches), **higher = more tolerant**. 1.0–1.5 typical |
| `yolo_confidence` | Person-detection threshold (0.5–0.7) |
| `frame_skip` | Higher = faster but recognition runs on fewer frames |
| `cooldown_seconds` | Min time between re-marking attendance for the same person |
| `identity_ttl` | How often verified people are re-checked (seconds) |
| `unknown_faces.retention_days` | Auto-delete unknown faces older than N days (0 = never) |

> Most users should leave Settings alone. If recognition feels wrong, ask your
> administrator.

---

## 11. Common Questions

**Q: I'm in front of the camera but no green box appears.**
A: Check that the camera is actually streaming (STOP→START). Make sure you are
enrolled (📸 Enroll). Check lighting — the system needs a reasonably lit,
frontal view.

**Q: It says UNKNOWN for someone who is enrolled.**
A: Their face may have changed (glasses, haircut) or the threshold is too
strict. Try re-enrolling, or ask the admin to raise `recognition_threshold`.

**Q: Can people cheat with a photo?**
A: No — the system runs multi-factor liveness detection (texture, blink,
motion, screen reflection, and a deep CNN). Print/screen attacks are shown as
**SPOOF DETECTED** and logged.

**Q: Does attendance mark more than once?**
A: No. Duplicate marking is blocked by a session cache, a cooldown, and a
database check.

**Q: Do I need to restart anything to add a camera?**
A: No — pick another camera in Live Recognition and click START.

---

## 12. Getting Help

- Your **administrator** handles camera setup, enrollments at scale, user
  accounts, and backups (see `ADMIN_MANUAL.md`).
- Common technical issues: `docs/TROUBLESHOOTING.md`
- Architecture & design: `docs/ARCHITECTURE.md`
