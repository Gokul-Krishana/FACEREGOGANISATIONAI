# Live Camera Root Cause Report

Date: 2026-10-11

## Findings

### Camera-only baseline

`python camera_only_test.py --duration 8 --no-display` completed successfully on
camera 0 using DirectShow:

- Capture: 28.4 FPS average; final EMA 30.6 FPS
- Failed reads: 0
- Freeze events: 0
- Longest frame gap: 162 ms
- Read latency: P50 32.0 ms, P95 47.7 ms

The camera, driver, and USB capture path are not the primary cause of the
reported freeze on this machine.

### Full AI baseline

`python tools/live_pipeline_test.py --duration 20 --index 0` did not complete
and exited with code 1. The run logged repeated ONNX Runtime CUDA provider
errors because `cublasLt64_13.dll` was unavailable. The camera subsequently
opened through DirectShow and the liveness model loaded, but the diagnostic
did not produce a valid AI FPS or latency summary. AI throughput and browser
frame age therefore remain unmeasured until the inference runtime is repaired
or a CPU-only run is explicitly selected.

## Transport and implementation audit

The backend transport is MJPEG at
`/video/sessions/{session_key}/mjpeg`, with recognition events on `/ws/live`.
The API-side camera manager already uses a capture thread, a single-slot
latest-frame buffer, and a separate AI worker.

The Next.js cameras page did not consume the MJPEG endpoint or start a video
session; it displayed a static “Live Feed” placeholder. This made the
frontend live-camera path incomplete, independent of backend frame rate.

## Changes made

- Added typed Next.js API methods for starting, stopping, and polling video
  sessions and for building the authenticated MJPEG URL.
- Replaced the cameras-page placeholder with a stable `<img>` MJPEG element.
- Kept recognition work out of React frame updates; only 2-second status polling
  updates React state.
- Added explicit start/stop controls and cleanup for camera sessions.

## Validation

- Targeted Python tests: 56 passed.
- Python syntax compilation for camera/API modules: passed.
- Camera-only hardware test: passed as reported above.
- Full AI hardware diagnostic: blocked by the ONNX Runtime CUDA DLL error.
- Next.js build and browser FPS measurement: still required after the local API
  and frontend are started with a valid authenticated camera session.

## Remaining limitation

This report does not claim the full application is fixed on the current machine:
AI FPS, P50/P95 inference latency, browser-rendered FPS, displayed frame age,
CPU/GPU/RAM usage during recognition, and attendance correctness could not be
established because the full AI diagnostic failed during inference-runtime
initialization. Do not change recognition thresholds or remove liveness checks
to mask this failure.
