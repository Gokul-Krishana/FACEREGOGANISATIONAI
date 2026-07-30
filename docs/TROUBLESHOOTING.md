# Troubleshooting Guide — Face Recognition AI

## Camera Issues

### Camera Not Opening

**Symptom:** Clicking START shows "Could not open camera"

**Causes & Solutions:**

1. **Camera in use by another app**
   - Close Zoom, Teams, OBS, or any app using the camera
   - Check `lsof /dev/video*` (Linux) or Camera settings (Windows)

2. **Wrong camera index**
   - Click **🔍 Scan Cameras** to discover available cameras
   - Try indices 0, 1, 2, 3

3. **No camera driver**
   - Windows: Check Device Manager → Cameras
   - Linux: `v4l2-ctl --list-devices`
   - macOS: System Information → Camera

4. **Permission denied (Linux)**
   ```bash
   sudo usermod -a -G video $USER
   # Log out and back in
   ```

### Camera Disconnects During Use

**Symptom:** Feed freezes, status shows DISCONNECTED

**Solutions:**
- System auto-reconnects (up to 5 attempts, 2s intervals)
- Click **STOP** → **START** to force reconnect
- Check USB cable connections
- Try a different USB port (USB 3.0 recommended)
- Disable USB power saving: Device Manager → USB Root Hub → Power Management

### Camera Feed is Black/Blank

**Symptom:** Camera opens but shows black screen

**Solutions:**
- Check camera privacy shutter (physical)
- Check OS camera privacy settings
- Windows: Settings → Privacy & security → Camera → Allow apps
- macOS: System Preferences → Security & Privacy → Camera
- Try a different camera index

## Recognition Issues

### Person Remains UNKNOWN

**Symptom:** Grey box with "? UNKNOWN" never changes to name

**Checklist:**

1. **Is the person enrolled?** — Check 👥 Employees page
2. **Lighting** — Ensure face is well-lit (not backlit, no harsh shadows)
3. **Distance** — Face should fill ~30% of frame (about arm's length)
4. **Angle** — Look directly at camera, not profile
5. **Glasses/mask** — Remove if enrollment didn't include them
6. **Recognition threshold** — Try lowering in ⚙️ Settings (e.g., 1.0 → 1.5)
7. **Quality score** — Check face quality in Recognition Details expander

### Attendance Not Marking

**Symptom:** Green box with name shows but "PRESENT" doesn't appear

**Check:**
1. Verify employee record exists with correct ID in 👥 Employees
2. Check if already marked today (duplicate prevention — once per day)
3. Check database: `python tools/validate_startup.py`
4. Check logs for "Failed to log attendance" messages
5. Verify `recognition.cooldown_seconds` in settings

### Low Recognition Accuracy

**Symptom:** Wrong name appears, or frequent UNKNOWN for enrolled people

**Solutions:**
1. **Reduce threshold** — Lower `recognition.recognition_threshold` in ⚙️ Settings
   - 1.2 → default (good balance)
   - 1.5 → more tolerant (fewer unknowns)
   - 2.0 → very tolerant (may get false matches)
2. **Re-enroll with better lighting** — Well-lit, front-facing
3. **Enroll multiple angles** — Slight left/right/tilt variations
4. **Enroll different expressions** — Neutral, smiling

### SPOOF Rejection (False Positive)

**Symptom:** Red box with "SPOOF DETECTED" for a real person

**Causes:**
1. **Poor lighting** — Shadows or extreme lighting can trigger liveness
2. **Screen reflection** — Glasses with anti-reflective coating helps
3. **Camera quality** — Very low-quality webcams (< 720p) may fail liveness checks
4. **Threshold too strict** — Adjust in ⚙️ Settings (advanced):
   - `amfr.liveness_spoof_threshold`: 0.15 → 0.10 (less strict)
   - `deep_liveness.threshold`: 0.50 → 0.40 (less strict)

## Performance Issues

### Low FPS (< 10)

**Symptom:** Feed is choppy, latency > 200ms

**Solutions:**

1. **Increase frame_skip** — ⚙️ Settings → Frame skip: 4 → 6
   - This processes every 6th frame instead of every 4th
   - Reduces AI load by 33%

2. **Reduce resolution** — Set camera width/height lower
   - Currently 640×480 by default
   - 320×240 is faster but lower display quality

3. **Close other apps** — Free up CPU resources
   - AI models use significant CPU
   - Close browsers with many tabs, video editors, games

4. **Disable deep liveness** — ⚙️ Settings → `deep_liveness.enabled: false`
   - Removes the CNN anti-spoofing model
   - Still uses lightweight 5-factor liveness

### High CPU Usage

**Symptom:** Fan noise, system slowdown

**Note:** AI inference is CPU-intensive by nature. This is expected behavior.

**Optimizations (in order of impact):**
1. Increase `frame_skip` (4 → 6)
2. Use FAISS `flat` index instead of `hnsw` (less memory)
3. Disable `deep_liveness.enabled`
4. Reduce YOLO model size (yolo11n → smaller custom model)

### Memory Usage

**Symptom:** High RAM usage (~1-2 GB)

**Breakdown:**
- YOLO11n: ~150 MB
- InsightFace buffalo_l: ~500 MB
- FAISS HNSW index: ~50 MB + embeddings
- Deep Liveness CNN: ~100 MB
- Python runtime + dependencies: ~300 MB

**Total: ~1.1-2 GB is normal**

## Database Issues

### Database Connection Failed

**Symptom:** Errors about database connection

**Solutions:**
- **SQLite**: Check `data/` directory exists and is writable
- **PostgreSQL**: 
  ```bash
  # Check if PostgreSQL is running
  systemctl status postgresql
  
  # Test connection
  psql -U faceai -d face_recognition -c "SELECT 1"
  ```
- **Migrations**: Run `alembic upgrade head`

### SQLite Database Locked

**Symptom:** "database is locked" errors

**Solutions:**
1. Ensure only one instance of the app is running
2. Check for leftover processes: `ps aux | grep streamlit`
3. Kill stale processes and restart
4. If corrupted: backup and recreate
   ```bash
   cp data/face_recognition.db data/face_recognition.db.bak
   rm data/face_recognition.db
   alembic upgrade head
   ```

### Attendance Records Missing

**Symptom:** Attendance page shows no records despite recognition working

**Check:**
1. Verify camera is recognizing (green box with PRESENT)
2. Check database: `data/face_recognition.db` exists and has content
3. Check server logs: `grep "Attendance" logs/app.log`
4. Check employee has correct `employee_id` field (used for lookup)

## FAISS Issues

### FAISS Index Error

**Symptom:** "FAISS error" or "Index not found"

**Solutions:**
```bash
# Delete corrupted index and re-enroll
rm embeddings/faiss.index embeddings/metadata.json
# Restart app, then re-enroll all faces
```

### Poor FAISS Search Results

**Symptom:** Wrong matches or no matches when expected

**Tuning:**
- **HNSW**: Increase `ef_search` (default: 128) for better recall
- **IVF**: Increase `nprobe` (default: 256) for better recall
- **Flat**: Exact search (best recall, slowest at scale)

See `scripts/benchmarks/` for tuning scripts.

## Streamlit Dashboard Issues

### Page Shows White Screen

**Symptom:** Dashboard loads but shows blank content

**Solutions:**
1. Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
2. Clear browser cache
3. Check browser console (F12) for errors
4. Restart Streamlit: Ctrl+C, then `streamlit run dashboard/app.py`

### Dashboard Slow to Update

**Symptom:** Recognition results lag behind real-time

**Solutions:**
- The dashboard updates at ~20 FPS (via `st.rerun()`)
- Recognition runs in a background thread — UI never blocks
- If results are lagging, the AI pipeline is bottlenecked on CPU
- Increase `frame_skip` to reduce AI load

### "Session State" Errors

**Symptom:** Streamlit errors about missing session state

**Solutions:**
1. Click **Rerun** in Streamlit toolbar
2. If persists, restart Streamlit
3. Clear browser cookies for localhost:8501

## Known Limitations

1. **Single camera stream** — One camera at a time through the UI
2. **CPU-only inference** — GPU support available via CUDA but not default
3. **No cloud sync** — All data stored locally (privacy feature)
4. **Redis optional** — Cooldown/cache degrades gracefully without Redis
5. **Cold start** — First recognition takes ~3-5s (model loading)
6. **Browser camera permission** — User must Allow camera access

## Getting Help

1. **Check System Health** — 🩺 System Health page at http://localhost:8501/Health
2. **View logs** — `logs/app.log` for detailed error traces
3. **Run diagnostics** — `python tools/validate_startup.py`
4. **Run tests** — `python -m pytest tests/ -v` to verify no regressions

## Common Error Messages

| Error | Likely Cause | Solution |
|:------|:-------------|:---------|
| `Could not create camera source` | Invalid source type | Check CAMERA_OPTIONS in dashboard |
| `No face detected` | Poor lighting/angle | Improve lighting, face front |
| `FAISS index error` | Corrupted index | Delete and re-enroll |
| `Database is locked` | Multiple instances | Kill other processes |
| `Module not found` | Missing dependency | `pip install -r requirements.txt` |
| `Permission denied` | Camera not accessible | Check OS permissions |
| `Streamlit connection error` | Dashboard crashed | Restart dashboard |
