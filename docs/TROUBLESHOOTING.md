# Troubleshooting Guide

## Camera Issues

### Camera Not Opening
**Symptom:** Clicking START shows "Could not open camera"

**Causes & Solutions:**
1. **Camera in use by another app** — Close Zoom, Teams, OBS, or any app using the camera
2. **Wrong camera index** — Click "🔍 Scan Cameras" to discover available cameras
3. **No camera driver** — Ensure camera drivers are installed (Windows: check Device Manager)
4. **Permission denied** — On Linux: `sudo chmod 666 /dev/video0`

### Camera Disconnects During Use
**Symptom:** Feed freezes, status shows DISCONNECTED

**Solution:** The system auto-reconnects (up to 5 attempts). If it doesn't recover:
- Click STOP, then START
- Check USB cable connections
- Try a different USB port

### Wrong Camera Opens
**Symptom:** Window shows wrong camera (e.g., an external USB instead of built-in)

**Solution:** Select the correct camera index from the dropdown. Use "🔍 Scan Cameras" to detect all available devices.

## Recognition Issues

### Person Remains UNKNOWN
**Symptom:** Green box never appears for enrolled person

**Checklist:**
1. **Is the person enrolled?** — Check the Employees page
2. **Lighting** — Ensure face is well-lit, not backlit
3. **Distance** — Face should fill ~30% of the frame
4. **Angle** — Look directly at the camera, not profile
5. **Glasses/mask** — Remove if enrollment didn't include them

### Attendance Not Marking
**Symptom:** Face is recognized (green box) but PRESENT doesn't show

**Check:**
1. Verify the employee record exists with correct ID
2. Check if attendance was already marked today (duplicate prevention)
3. Check database connection: `python tools/validate_startup.py`
4. Check server logs for database errors

### Too Many UNKNOWN Faces Saved
**Symptom:** Unknown faces directory has thousands of files

**Solution:** The system has a 3-second cooldown between saves. If this is still too many, increase `unknown_faces.retention_days` in `config/settings.yaml`.

### SPOOF Rejection
**Symptom:** Red box with "SPOOF DETECTED" for a real person

**Causes:**
1. **Poor lighting** — Shadows or extreme lighting can trigger liveness
2. **Screen reflection** — If wearing glasses, try without
3. **Camera quality** — Very low-quality cameras may fail liveness
4. **Threshold too strict** — Adjust `liveness.spoof_threshold` in settings (advanced)

## Database Issues

### Database Connection Failed
**Symptom:** Errors about database connection

**Solutions:**
- **SQLite**: Check `data/` directory exists and is writable
- **PostgreSQL**: Run `python tools/validate_startup.py` for details
- **Migrations**: Run `alembic upgrade head`

### Attendance Records Missing
**Symptom:** Attendance page shows no records

**Check:**
1. Verify camera is recognizing (green box with PRESENT)
2. Check database file: `data/face_recognition.db` (SQLite) or PostgreSQL status
3. Check server logs for "Failed to log attendance" messages

## Performance Issues

### Low FPS
**Symptom:** Feed is choppy (< 5 FPS)

**Solutions:**
1. **Reduce frame processing** — Increase `frame_skip` in settings (default: 2)
2. **Lower resolution** — The system uses 640×480 by default
3. **Close other apps** — Free up CPU/GPU resources
4. **GPU acceleration** — If available, enable CUDA in config

### High CPU Usage
**Symptom:** Fan noise, system slowdown

**Note:** AI models require significant CPU. This is expected.

**Optimizations:**
1. Increase `frame_skip` to process fewer frames per second
2. Use a simpler FAISS index (`flat` instead of `hnsw`)
3. Disable deep liveness if not needed (set `deep_liveness.enabled: false`)

## Known Limitations

1. **Single-stream camera** — One camera at a time through the UI
2. **CPU-only inference** — GPU support available but not default
3. **No cloud sync** — All data stored locally
4. **Redis optional** — Cooldown/cache degrades gracefully without Redis
