#!/usr/bin/env python
"""
Camera Diagnostics — Test All Phone Camera Types
=================================================

Probes every camera source type the system supports and reports
which ones are available on your machine and network.

Tests performed:

    ┌────────────────────────────────┬────────────┬──────────────────┐
    │ Camera Type                   │ Method      │ Port / Index     │
    ├────────────────────────────────┼────────────┼──────────────────┤
    │ 💻 Laptop Webcam              │ OpenCV      │ device 0..4      │
    │ 📱 Android (USB) — DroidCam   │ OpenCV      │ device 1..3      │
    │ 📱 iPhone (USB) — EpocCam     │ OpenCV      │ device 2..4      │
    │ 📱 Android (Wi-Fi) — IP Webcam│ HTTP probe  │ port 8080        │
    │ 📱 Android (Wi-Fi) — DroidCam │ HTTP probe  │ port 4747        │
    │ 📱 iPhone (Wi-Fi) — EpocCam   │ HTTP probe  │ port 8080        │
    └────────────────────────────────┴────────────┴──────────────────┘

Usage::

    python tools/diagnose_cameras.py
    python tools/diagnose_cameras.py --network-scan   # includes full subnet scan
    python tools/diagnose_cameras.py --quick          # skip network scan, USB only
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List

# Ensure project root is on path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2  # noqa: E402
import requests  # noqa: E402

from camera.discovery import scan_network  # noqa: E402
from camera.webcam import list_webcams  # noqa: E402


# ═══════════════════════════════════════════════════════════════
#  ANSI helpers
# ═══════════════════════════════════════════════════════════════


class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    GRAY = "\033[90m"


def ok(text: str) -> str:
    return f"{Color.GREEN}✅ {text}{Color.RESET}"


def warn(text: str) -> str:
    return f"{Color.YELLOW}⚠️  {text}{Color.RESET}"


def fail(text: str) -> str:
    return f"{Color.RED}❌ {text}{Color.RESET}"


def info(text: str) -> str:
    return f"{Color.CYAN}{text}{Color.RESET}"


def dim(text: str) -> str:
    return f"{Color.GRAY}{text}{Color.RESET}"


def heading(text: str) -> str:
    return f"\n{Color.BOLD}{'=' * 60}\n  {text}\n{'=' * 60}{Color.RESET}"


# ═══════════════════════════════════════════════════════════════
#  Diagnostic Tests
# ═══════════════════════════════════════════════════════════════


def test_opencv_version() -> bool:
    """Check OpenCV is available and print its version."""
    try:
        ver = cv2.__version__
        print(f"  OpenCV        : {ver}")
        return True
    except Exception as e:
        print(f"  OpenCV        : {fail(str(e))}")
        return False


def test_webcams() -> List[int]:
    """Probe OpenCV device indices 0–4 for available webcams.

    Returns:
        List of available device indices.
    """
    print(f"\n{heading('💻 Local Webcams')}")
    print(dim("  Probing OpenCV device indices 0..4 with DirectShow backend..."))
    print()

    available = list_webcams(max_devices=5)
    tried_indices = list(range(5))

    for idx in tried_indices:
        if idx in available:
            print(f"  Device #{idx}    : {ok('Available')}")
        else:
            print(f"  Device #{idx}    : {fail('Not found')}")

    if available:
        print(f"\n  {ok(f'Found {len(available)} webcam(s) at index {available}')}")
    else:
        print(f"\n  {warn('No webcam detected')}")
        print(dim("  Tip: If you have a USB webcam, try a different USB port."))

    return available


def test_usb_cameras() -> Dict[str, List[int]]:
    """Test USB-based phone cameras (DroidCam, EpocCam) using actual source classes.

    Uses the ``AndroidUSBSource`` and ``iPhoneUSBSource`` classes (which have their
    own open logic — multiple backends, Wi-Fi fallback, etc.) rather than raw
    ``cv2.VideoCapture``, giving more accurate diagnostics of what the system
    will actually use.

    Tests a range of device indices since phone cameras typically appear at
    higher indices (1+) than built-in webcams (0).

    Returns:
        Dict mapping source_type → list of available device indices.
    """
    results: Dict[str, List[int]] = {}

    # Android USB (DroidCam) — typically device 1+, also tries Wi-Fi fallback
    print(f"\n{heading('📱 Android (USB) — DroidCam')}")
    print(dim("  Install DroidCam on phone + PC, connect via USB, select USB mode."))
    print(dim("  Tests using AndroidUSBSource class (USB first, then Wi-Fi fallback)."))
    print(dim("  Probes device indices 1..3..."))
    print()

    android_usb_available = []
    for dev_id in range(1, 4):
        try:
            from camera.phone import AndroidUSBSource

            cam = AndroidUSBSource(device_id=dev_id)
            if cam.open():
                info = cam.info()
                res = info.get("resolution", "?")
                mode = info.get("mode", "?")
                print(f"  Device #{dev_id}  : {ok(f'{mode.upper()} — {res}')}")
                android_usb_available.append(dev_id)
                cam.release()
            else:
                print(f"  Device #{dev_id}  : {fail('Not found')}")
        except Exception as e:
            print(f"  Device #{dev_id}  : {fail(str(e))}")

    results["android_usb"] = android_usb_available
    if android_usb_available:
        print(f"\n  {ok(f'DroidCam found at device {android_usb_available}')}")
    else:
        print(f"\n  {warn('DroidCam not detected')}")
        print(dim("  Tip: Connect phone via USB, enable USB debugging, start DroidCam."))

    # iPhone USB (EpocCam) — typically device 2+
    print(f"\n{heading('📱 iPhone (USB) — EpocCam')}")
    print(dim("  Install EpocCam on iPhone + PC, connect via USB."))
    print(dim("  Tests using iPhoneUSBSource class with multiple backends."))
    print(dim("  Probes device indices 2..4..."))
    print()

    iphone_usb_available = []
    for dev_id in range(2, 5):
        try:
            from camera.phone import iPhoneUSBSource

            cam = iPhoneUSBSource(device_id=dev_id)
            if cam.open():
                info = cam.info()
                res = info.get("resolution", "?")
                print(f"  Device #{dev_id}  : {ok(f'Opened — {res}')}")
                iphone_usb_available.append(dev_id)
                cam.release()
            else:
                print(f"  Device #{dev_id}  : {fail('Not found')}")
        except Exception as e:
            print(f"  Device #{dev_id}  : {fail(str(e))}")

    results["iphone_usb"] = iphone_usb_available
    if iphone_usb_available:
        print(f"\n  {ok(f'EpocCam found at device {iphone_usb_available}')}")
    else:
        print(f"\n  {warn('EpocCam not detected')}")
        print(dim("  Tip: Connect iPhone via USB, open EpocCam on the phone."))

    return results


def test_single_url(url: str, label: str, port: int) -> bool:
    """Test a single HTTP endpoint for camera service availability.

    Connects to the given URL, checks HTTP status, and reports
    whether the camera web server is reachable.

    Args:
        url:   Full URL to test.
        label: Human-readable service name.
        port:  TCP port (for display).

    Returns:
        True if the endpoint is reachable and responds with 200.
    """
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            server = resp.headers.get("Server", "")
            title_hint = ""
            if "ip webcam" in resp.text.lower():
                title_hint = " — IP Webcam detected"
            elif "epoccam" in resp.text.lower() or "elgato" in resp.text.lower():
                title_hint = " — EpocCam detected"
            elif "droidcam" in resp.text.lower():
                title_hint = " — DroidCam detected"
            print(f"  {url:<42} : {ok(f'Reachable (HTTP 200){title_hint}')}")
            if server:
                print(f"  {'':>42}   {dim(f'Server: {server}')}")
            return True
        else:
            print(f"  {url:<42} : {warn(f'HTTP {resp.status_code}')}")
            return False
    except requests.ConnectionError:
        print(f"  {url:<42} : {fail('Connection refused')}")
        return False
    except requests.Timeout:
        print(f"  {url:<42} : {fail('Timed out')}")
        return False
    except Exception as e:
        print(f"  {url:<42} : {fail(str(e))}")
        return False


def test_wifi_cameras() -> Dict[str, bool]:
    """Test Wi-Fi phone cameras on common default IPs and ports.

    Probes:
    - 192.168.1.100:8080 (IP Webcam default)
    - 192.168.1.101:8080 (EpocCam default)
    - 192.168.1.100:4747 (DroidCam Wi-Fi)

    Returns:
        Dict mapping source_type → available (bool).
    """
    results: Dict[str, bool] = {}

    print(f"\n{heading('📱 Android (Wi-Fi) — IP Webcam')}")
    print(dim("  Default address: http://192.168.1.100:8080"))
    print(dim("  Install IP Webcam from Play Store, start server, check the URL."))
    print()
    ipwc_ok = test_single_url("http://192.168.1.100:8080", "IP Webcam", 8080)
    results["android_wifi"] = ipwc_ok

    print(f"\n{heading('📱 Android (Wi-Fi) — DroidCam')}")
    print(dim("  Default address: http://192.168.1.100:4747"))
    print(dim("  DroidCam also has a Wi-Fi mode (fallback from USB)."))
    print()
    droid_wifi_ok = test_single_url("http://192.168.1.100:4747", "DroidCam Wi-Fi", 4747)
    # If DroidCam found, also note it provides android_usb source type
    if droid_wifi_ok:
        results["android_usb"] = True  # DroidCam Wi-Fi mode

    print(f"\n{heading('📱 iPhone (Wi-Fi) — EpocCam')}")
    print(dim("  Default address: http://192.168.1.101:8080"))
    print(dim("  Install EpocCam on iPhone, connect to same Wi-Fi, open the app."))
    print()
    epoc_ok = test_single_url("http://192.168.1.101:8080", "EpocCam", 8080)
    results["iphone_wifi"] = epoc_ok

    return results


def test_custom_urls() -> None:
    """Prompt the user to enter custom URLs for testing."""
    print(f"\n{heading('🔧 Custom URL Test')}")
    print(dim("  Enter IP addresses to test if your phone cameras are on a"))
    print(dim("  different subnet or use non-default ports."))
    print()

    while True:
        try:
            ip = input("  Enter IP to test (or press Enter to skip): ").strip()
            if not ip:
                break

            ports = [8080, 4747]
            for port in ports:
                url = f"http://{ip}:{port}"
                label = f"{ip}:{port}"
                test_single_url(url, label, port)
            print()
        except (EOFError, KeyboardInterrupt):
            print()
            break


def run_network_scan() -> None:
    """Run the full network discovery scan."""
    print(f"\n{heading('🔍 Network Scan — Auto-Discovery')}")
    print(dim("  Scanning the local /24 subnet for phone cameras..."))
    print(dim("  This takes ~10 seconds with 50 parallel threads."))
    print()

    try:
        start = time.time()
        devices = scan_network(timeout=1.5)
        elapsed = time.time() - start

        print(f"\n  Scan completed in {elapsed:.1f}s")
        print(f"  Found {len(devices)} device(s)")
        print()

        if devices:
            for i, d in enumerate(devices, 1):
                icon = "📱"
                print(f"  [{i}] {icon} {d.display_name}")
                print(f"       URL  : {d.stream_url}")
                print(f"       Type : {d.source_type}")
                print()
        else:
            print(f"  {warn('No phone cameras discovered on the local network')}")
            print(dim("  Make sure your phone is on the same Wi-Fi and the camera app is running."))
    except Exception as e:
        print(f"  {fail(f'Scan failed: {e}')}")


# ═══════════════════════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════════════════════


def print_summary(
    webcams: List[int],
    usb_results: Dict[str, List[int]],
    wifi_results: Dict[str, bool],
) -> None:
    """Print a clean summary table of all camera availability."""
    print(f"\n{heading('📊 Summary')}")
    print(f"  {'Source':<28} {'Status':<12} {'Details'}")
    print(f"  {'─' * 28} {'─' * 12} {'─' * 36}")

    # Webcam
    if webcams:
        print(f"  {'💻 Laptop Webcam':<28} {ok('Available'):<12} {f'Device index(es): {webcams}'}")
    else:
        print(f"  {'💻 Laptop Webcam':<28} {fail('Not found'):<12} {'Try a different USB port'}")

    # Android USB (DroidCam)
    usb_android = usb_results.get("android_usb", [])
    if usb_android:
        print(
            f"  {'📱 Android (USB) DroidCam':<28} {ok('Available'):<12} {f'Device index(es): {usb_android}'}"
        )
    else:
        print(
            f"  {'📱 Android (USB) DroidCam':<28} {warn('Not tested'):<12} {'Connect phone via USB, start DroidCam'}"
        )

    # iPhone USB (EpocCam)
    usb_iphone = usb_results.get("iphone_usb", [])
    if usb_iphone:
        print(f"  {'📱 iPhone (USB) EpocCam':<28} {ok('Available'):<12} {f'Device index(es): {usb_iphone}'}")
    else:
        print(
            f"  {'📱 iPhone (USB) EpocCam':<28} {warn('Not tested'):<12} {'Connect iPhone via USB, start EpocCam'}"
        )

    # Android Wi-Fi (IP Webcam)
    if wifi_results.get("android_wifi"):
        print(
            f"  {'📱 Android (Wi-Fi) IP Webcam':<28} {ok('Available'):<12} {'http://192.168.1.100:8080/video'}"
        )
    else:
        print(
            f"  {'📱 Android (Wi-Fi) IP Webcam':<28} {warn('Not found'):<12} {'Start IP Webcam on Android'}"
        )

    # Android Wi-Fi (DroidCam)
    if wifi_results.get("android_usb"):
        print(
            f"  {'📱 Android Wi-Fi DroidCam':<28} {ok('Available'):<12} {'http://192.168.1.100:4747/video'}"
        )
    else:
        print(f"  {'📱 Android Wi-Fi DroidCam':<28} {warn('Not found'):<12} {'Start DroidCam in Wi-Fi mode'}")

    # iPhone Wi-Fi (EpocCam)
    if wifi_results.get("iphone_wifi"):
        print(
            f"  {'📱 iPhone (Wi-Fi) EpocCam':<28} {ok('Available'):<12} {'http://192.168.1.101:8080/video'}"
        )
    else:
        print(f"  {'📱 iPhone (Wi-Fi) EpocCam':<28} {warn('Not found'):<12} {'Start EpocCam on iPhone'}")

    print()
    print(f"  {dim('─' * 76)}")
    print()

    # Count available
    available_count = (
        len(webcams)
        + len(usb_results.get("android_usb", []))
        + len(usb_results.get("iphone_usb", []))
        + sum(1 for v in wifi_results.values() if v)
    )
    if available_count > 0:
        print(f"  {ok(f'{available_count} camera source(s) available')}")
    else:
        print(f"  {warn('No camera sources found — check connections and try again')}")
    print()


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose all phone camera types for the Face Recognition AI system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--network-scan",
        "-n",
        action="store_true",
        help="Perform a full /24 subnet scan (takes ~10 seconds)",
    )
    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Skip network tests — USB / webcam only",
    )
    parser.add_argument(
        "--custom",
        "-c",
        action="store_true",
        help="Prompt for custom IP addresses to test",
    )

    args = parser.parse_args()

    print()
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}")
    print(f"{Color.BOLD}  Face Recognition AI — Camera Diagnostics{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 60}{Color.RESET}")
    print()
    print(f"  Started at : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python     : {sys.version.split()[0]}")
    print(f"  Platform   : {sys.platform}")

    # Step 1 — Environment
    print(f"\n{heading('🔧 Environment')}")
    test_opencv_version()

    # Step 2 — USB / local cameras
    webcams = test_webcams()
    usb_results = test_usb_cameras()

    # Step 3 — Wi-Fi cameras (default IPs)
    wifi_results: Dict[str, bool] = {}
    if not args.quick:
        wifi_results = test_wifi_cameras()
    else:
        print(f"\n{heading('📱 Wi-Fi Cameras')}")
        print(f"  {dim('Skipped (--quick)')}")

    # Step 4 — Network scan
    if args.network_scan:
        run_network_scan()

    # Step 5 — Custom URLs
    if args.custom:
        test_custom_urls()

    # Step 6 — Summary
    print_summary(webcams, usb_results, wifi_results)

    print(f"  {dim('For detailed setup instructions, see the README or visit:')}")
    print(f"  {dim('  📱 IP Webcam : https://play.google.com/store/apps/details?id=com.pas.webcam')}")
    print(f"  {dim('  📱 DroidCam  : https://www.dev47apps.com/')}")
    print(f"  {dim('  📱 EpocCam   : https://www.elgato.com/us/en/s/epoccam')}")
    print()


if __name__ == "__main__":
    main()
