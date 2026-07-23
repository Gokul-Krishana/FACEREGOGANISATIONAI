"""
Face Recognition AI - Main Entry Point
=======================================

Usage:
    python main.py                  # Live webcam recognition
    python main.py --image path     # Process a single image
    python main.py --enroll NAME    # Enroll a face from webcam
    python main.py --test           # Run pipeline test on test images
    python main.py --debug          # Diagnostic mode (check camera, models, etc.)
    python main.py --camera-id 1    # Use a different camera
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Workaround for PyTorch JIT on Windows (virtual memory fragmentation)
os.environ.setdefault("PYTORCH_JIT", "0")

# Ensure project root is on path
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2
import numpy as np

import config.config as cfg
from app.live_detection import LiveDetection


def cmd_webcam(args: argparse.Namespace) -> None:
    """Run live webcam recognition."""
    pipeline = LiveDetection()
    pipeline.run(camera_id=args.camera_id, source_type=args.source_type, camera_url=args.camera_url)


def cmd_image(args: argparse.Namespace) -> None:
    """Process a single image and save the result."""
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[FAIL] Image not found: {image_path}")
        sys.exit(1)

    pipeline = LiveDetection()
    print(f"[INFO] Processing image: {image_path}")
    annotated = pipeline.process_image(str(image_path))

    output_path = cfg.OUTPUTS_DIR / f"annotated_{image_path.name}"
    cv2.imwrite(str(output_path), annotated)
    print(f"[OK] Result saved to: {output_path}")

    # Also show in a window (if display is available)
    try:
        cv2.imshow("Result", annotated)
        print("[INFO] Press any key to close the result window")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except cv2.error:
        pass  # No display available


def cmd_enroll(args: argparse.Namespace) -> None:
    """Enroll a face from webcam with the given name."""
    name = args.enroll
    if not name:
        print("[FAIL] Name cannot be empty")
        sys.exit(1)

    print(f"[INFO] Enrolling face for: {name}")
    print("[INFO] Looking at the camera...")

    cap = LiveDetection.open_camera(args.camera_id, source_type=args.source_type, camera_url=args.camera_url)
    if cap is None:
        print("[FAIL] Could not open camera")
        sys.exit(1)

    # Use the shared pipeline components
    pipeline = LiveDetection()

    print("[INFO] Press SPACE to capture, Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Show preview with instructions
        cv2.putText(frame, f"Enrolling: {name}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, "SPACE = Capture   Q = Quit", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Draw YOLO detections
        detections = pipeline.detector.detect(frame)
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        cv2.imshow("Enroll Face", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            print("[INFO] Enrollment cancelled")
            break
        elif key == ord(" "):  # Space
            detections = pipeline.detector.detect(frame)
            if not detections:
                print("[WARN] No person detected. Try again.")
                continue

            largest = max(detections, key=lambda d:
                          (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1]))
            person_crop = pipeline.detector.crop_person(frame, largest["bbox"])

            embedding = pipeline.recognizer.extract_embedding(person_crop)
            if embedding is None:
                print("[WARN] No face found. Try again.")
                continue

            matches = pipeline.enrollment.search(embedding, k=1, threshold=cfg.RECOGNITION_THRESHOLD)
            if matches:
                print(f"[WARN] Face already enrolled as: {matches[0]['name']}")
                continue

            pipeline.enrollment.enroll(name, embedding)
            print(f"[OK] Enrolled '{name}' successfully")
            print(f"     Total embeddings: {pipeline.enrollment.count()}")
            break

    cap.release()
    cv2.destroyAllWindows()


def cmd_test(args: argparse.Namespace) -> None:
    """Run full pipeline test on test images."""
    print("=" * 60)
    print("Face Recognition AI - Pipeline Test")
    print("=" * 60)

    # Find test images
    test_images = list(cfg.DATASET_DIR.glob("*.jpg")) + list(cfg.DATASET_DIR.glob("*.png"))
    if not test_images:
        print("[FAIL] No test images found in dataset/")
        print("       Download one: python main.py --debug")
        sys.exit(1)

    # Use a single pipeline instance to avoid loading models twice
    pipeline = LiveDetection()

    print(f"[INFO] Found {len(test_images)} test image(s)")
    print()

    for img_path in test_images:
        print(f"--- Processing: {img_path.name} ---")
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  [FAIL] Could not read image")
            continue

        print(f"  Shape: {img.shape}")

        # Step 1: YOLO
        detections = pipeline.detector.detect(img)
        print(f"  YOLO detections: {len(detections)}")
        for d in detections:
            print(f"    Person at {d['bbox']}, conf={d['confidence']:.3f}")

        if not detections:
            print("  [SKIP] No person detected")
            print()
            continue

        # Step 2: Face embedding
        largest = max(detections, key=lambda d:
                      (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1]))
        person_crop = pipeline.detector.crop_person(img, largest["bbox"])
        print(f"  Person crop: {person_crop.shape}")

        embedding = pipeline.recognizer.extract_embedding(person_crop)
        if embedding is None:
            print("  [SKIP] No face found in person crop")
            print()
            continue

        print(f"  ArcFace embedding: {embedding.shape}")
        print(f"  Embedding norm: {np.linalg.norm(embedding):.4f}")

        # Step 3: FAISS search
        matches = pipeline.enrollment.search(embedding, k=1, threshold=cfg.RECOGNITION_THRESHOLD)
        if matches:
            print(f"  FAISS match: {matches[0]['name']} (conf={matches[0]['confidence']:.2f})")
        else:
            print(f"  FAISS: No match (enrolled: {pipeline.enrollment.count()})")

        print()

    # Save annotated results using the same pipeline
    for img_path in test_images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        annotated = pipeline.process_frame(img)
        out_path = cfg.OUTPUTS_DIR / f"result_{img_path.name}"
        cv2.imwrite(str(out_path), annotated)
        print(f"[OK] Saved annotated result: {out_path}")

    print(f"[INFO] Attendance today: {len(pipeline.attendance.today())} records")
    print(f"[INFO] Enrolled: {pipeline.enrollment.count()} embeddings / "
          f"{pipeline.enrollment.unique_count()} persons")
    print("=" * 60)
    print("[OK] Pipeline test complete")


def cmd_debug(args: argparse.Namespace) -> None:
    """Run diagnostics: camera, model loading, etc."""
    print("=" * 60)
    print("Face Recognition AI - Diagnostic Mode")
    print("=" * 60)

    # Python version
    print(f"\n[1/6] Python: {sys.version.split()[0]}")

    # OpenCV
    print(f"[2/6] OpenCV: {cv2.__version__}")

    # Camera test — use the configured/CLI-provided source type
    print(f"\n[3/6] Camera test:")
    source_type = args.source_type
    camera_url = args.camera_url
    camera_id = args.camera_id
    print(f"  Source type: {source_type}")
    if source_type in ("android_wifi", "iphone_wifi", "ip_camera"):
        print(f"  URL: {camera_url}")
    if source_type in ("webcam", "usb_auto", "android_usb", "iphone_usb"):
        print(f"  Device index: {camera_id}")
    print()

    # Attempt to open the configured camera source
    cap = LiveDetection.open_camera(camera_id=camera_id, source_type=source_type, camera_url=camera_url)
    if cap is not None:
        ret, frame = cap.read()
        print(f"  ✅ Camera opened successfully!")
        if ret and frame is not None:
            print(f"     Frame shape: {frame.shape}")
            snap_path = cfg.OUTPUTS_DIR / f"camera_test_{source_type}.jpg"
            cv2.imwrite(str(snap_path), frame)
            print(f"     Snapshot saved: {snap_path}")
        else:
            print(f"  ⚠️  Camera opened but could not read frame")
        cap.release()
    else:
        print(f"  ❌ Could not open {source_type} camera")

    # Also do a quick index scan (for diagnostic reference)
    print(f"\n  --- Quick index scan (DirectShow) ---")
    found_indices = []
    for idx in range(5):
        test_cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if test_cap.isOpened():
            found_indices.append(idx)
            test_cap.release()
    if found_indices:
        print(f"  Available DirectShow device(s): {found_indices}")
    else:
        print(f"  No DirectShow cameras found on indices 0-4")

    # YOLO model
    print(f"\n[4/6] YOLO model:")
    if Path(cfg.YOLO_MODEL_PATH).exists():
        size = Path(cfg.YOLO_MODEL_PATH).stat().st_size
        print(f"  Model: {cfg.YOLO_MODEL_PATH} ({size / 1024 / 1024:.1f} MB)")
        from app.face_detector import FaceDetector
        det = FaceDetector()
        print(f"  YOLO: LOADED")
        # Quick test with Lena
        if Path("dataset/lena.jpg").exists():
            img = cv2.imread("dataset/lena.jpg")
            results = det.detect(img)
            print(f"  Test detection: {len(results)} person(s) found")
    else:
        print(f"  [FAIL] Model not found: {cfg.YOLO_MODEL_PATH}")

    # InsightFace
    print(f"\n[5/6] InsightFace:")
    try:
        from app.recognizer import FaceRecognizer
        recognizer = FaceRecognizer()
        print(f"  Model: {recognizer.model_name}")
        print(f"  Embedding dim: {recognizer.embedding_dim()}")
        print(f"  InsightFace: LOADED")

        # Test with a simple image
        if Path("dataset/lena.jpg").exists():
            img = cv2.imread("dataset/lena.jpg")
            emb = recognizer.extract_embedding(img)
            if emb is not None:
                print(f"  Test embedding: shape={emb.shape}, norm={np.linalg.norm(emb):.2f}")
            else:
                print(f"  [WARN] No face detected in lena.jpg")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # FAISS
    print(f"\n[6/6] FAISS database:")
    try:
        from app.enrollment import FaceEnrollment
        enrollment = FaceEnrollment()
        print(f"  Embeddings: {enrollment.count()}")
        print(f"  Persons: {enrollment.all_persons()}")
        print(f"  Index path: {cfg.FAISS_INDEX_PATH}")
        print(f"  Metadata path: {cfg.METADATA_PATH}")
        print(f"  FAISS: LOADED")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # Download Lena if not present
    if not Path("dataset/lena.jpg").exists():
        print(f"\n[EXTRA] Downloading test image...")
        import urllib.request
        url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg"
        urllib.request.urlretrieve(url, "dataset/lena.jpg")
        print(f"  Downloaded: dataset/lena.jpg")

    print("\n" + "=" * 60)
    print("Diagnostic complete")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Face Recognition AI - Real-time face recognition system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                      Live webcam recognition
  python main.py --debug                              Run diagnostics
  python main.py --test                               Test pipeline with test images
  python main.py --image photo.jpg                    Process a single image
  python main.py --enroll John                        Enroll face from webcam
  python main.py --camera-id 1                        Use camera 1 instead of 0
  python main.py --source-type android_wifi           Use Android IP Webcam
  python main.py --source-type ip_camera --camera-url rtsp://admin:pass@192.168.1.200:554/stream1
        """,
    )

    parser.add_argument("--camera-id", type=int, default=cfg.CAMERA_ID,
                        help="Camera device ID (default: 0)")
    parser.add_argument("--source-type", type=str, default=cfg.CAMERA_SOURCE_TYPE,
                        choices=["webcam", "usb_auto", "android_usb", "android_wifi",
                                 "iphone_usb", "iphone_wifi", "ip_camera"],
                        help="Camera source type (default: from settings)")
    parser.add_argument("--camera-url", type=str, default=cfg.CAMERA_URL,
                        help="Camera URL for phone/IP cameras (e.g. http://192.168.1.100:8080/video)")
    parser.add_argument("--image", type=str, default=None,
                        help="Path to an image file to process")
    parser.add_argument("--enroll", type=str, default=None,
                        help="Enroll a face from webcam with this name")
    parser.add_argument("--test", action="store_true",
                        help="Run pipeline test on test images")
    parser.add_argument("--debug", action="store_true",
                        help="Run diagnostic checks")

    args = parser.parse_args()

    # Route to the appropriate command
    if args.debug:
        cmd_debug(args)
    elif args.test:
        cmd_test(args)
    elif args.image:
        cmd_image(args)
    elif args.enroll:
        cmd_enroll(args)
    else:
        cmd_webcam(args)


if __name__ == "__main__":
    main()
