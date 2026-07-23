"""
Camera Discovery — Auto-detect Phone Cameras on the Local Network
===================================================================

Scans the local subnet for active hosts, probes known ports (8080, 4747),
and identifies camera services by their HTTP response signatures.

Supported services:

    +------------------+-------+----------------------------------+
    | Service          | Port  | HTTP Signature                   |
    +------------------+-------+----------------------------------+
    | IP Webcam        |  8080 | ``<title>IP Webcam</title>``     |
    | (Android Wi-Fi)  |       | or ``Server: IP Webcam Server``  |
    +------------------+-------+----------------------------------+
    | DroidCam Wi-Fi   |  4747 | ``DroidCam`` in response body    |
    | (Android Wi-Fi)  |       | or in ``Server`` header           |
    +------------------+-------+----------------------------------+
    | EpocCam          |  8080 | ``EpocCam`` in response body     |
    | (iPhone Wi-Fi)   |       | or ``Elgato`` in response body   |
    +------------------+-------+----------------------------------+

Usage::

    from camera.discovery import scan_network

    devices = scan_network(timeout=1.5)
    for d in devices:
        print(f"{d.display_name} → {d.stream_url}")
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
import socket
from dataclasses import dataclass
from typing import Callable, List, Optional

import requests

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Data Model
# ═══════════════════════════════════════════════════════════════


@dataclass
class DiscoveredCamera:
    """A phone camera discovered on the local network.

    Attributes:
        source_type:  ``"android_wifi"`` or ``"iphone_wifi"``
        display_name: Human-readable label (e.g. ``"IP Webcam (192.168.1.100)"``)
        stream_url:   Full URL to the video stream (e.g. ``http://192.168.1.100:8080/video``)
        ip:           IP address string
        port:         Probe port
    """

    source_type: str
    display_name: str
    stream_url: str
    ip: str
    port: int


# ═══════════════════════════════════════════════════════════════
#  Detection Signatures
# ═══════════════════════════════════════════════════════════════

# Each signature describes how to detect a particular phone camera service.
# ``check`` receives a ``requests.Response`` and should return ``True``
# if the response matches the expected service.

_CAMERA_SIGNATURES: List[dict] = [
    {
        "source_type": "android_wifi",
        "display_template": "IP Webcam ({ip})",
        "url_template": "http://{ip}:8080/video",
        "port": 8080,
        "path": "/",
        "check": lambda resp: (
            "ip webcam" in resp.text.lower()
            or "ip webcam" in resp.headers.get("Server", "").lower()
            or "mjpg" in resp.text.lower()
        ),
    },
    {
        "source_type": "android_wifi",  # DroidCam Wi-Fi fallback
        "display_template": "DroidCam Wi-Fi ({ip})",
        "url_template": "http://{ip}:4747/video",
        "port": 4747,
        "path": "/",
        "check": lambda resp: (
            "droidcam" in resp.text.lower()
            or "droidcam" in resp.headers.get("Server", "").lower()
        ),
    },
    {
        "source_type": "iphone_wifi",
        "display_template": "EpocCam ({ip})",
        "url_template": "http://{ip}:8080/video",
        "port": 8080,
        "path": "/",
        "check": lambda resp: (
            "epoccam" in resp.text.lower()
            or "elgato" in resp.text.lower()
        ),
    },
]


# ═══════════════════════════════════════════════════════════════
#  Network Helpers
# ═══════════════════════════════════════════════════════════════


def _get_local_subnet() -> str:
    """Detect the local subnet prefix (first three octets).

    Connects to a well-known external IP to determine the local
    network interface, then returns the ``/24`` prefix.

    Falls back to ``"192.168.1"`` on failure.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        prefix = ".".join(local_ip.split(".")[:3])
        logger.debug(f"Detected local subnet: {prefix}.0/24")
        return prefix
    except Exception as exc:
        logger.warning(f"Could not detect subnet ({exc}); falling back to 192.168.1")
        return "192.168.1"


def _probe_ip(ip: str, timeout: float = 2.0) -> List[DiscoveredCamera]:
    """Probe a single IP address for known camera services.

    For each known signature, a TCP connect is attempted first.
    If the port is open, an HTTP GET is sent and the response
    is checked against the signature's check function.

    Args:
        ip: IP address string.
        timeout: Per-probe timeout in seconds.

    Returns:
        List of ``DiscoveredCamera`` instances found at this IP.
    """
    found: List[DiscoveredCamera] = []

    for sig in _CAMERA_SIGNATURES:
        port = sig["port"]
        try:
            # ── Fast TCP connect check ──────────────────────
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()

            if result != 0:
                continue  # port not open → skip

            # ── Port open — probe with HTTP GET ─────────────
            url = f"http://{ip}:{port}{sig['path']}"
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()

            if sig["check"](resp):
                stream_url = sig["url_template"].format(ip=ip)
                display_name = sig["display_template"].format(ip=ip)
                found.append(DiscoveredCamera(
                    source_type=sig["source_type"],
                    display_name=display_name,
                    stream_url=stream_url,
                    ip=ip,
                    port=port,
                ))

        except (socket.timeout, ConnectionRefusedError, OSError):
            continue
        except requests.RequestException:
            continue
        except Exception as exc:
            logger.debug(f"Error probing {ip}:{port} — {exc}")
            continue

    return found


# ═══════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════


def scan_network(timeout: float = 1.5, max_workers: int = 50) -> List[DiscoveredCamera]:
    """Scan the local network for phone camera services.

    Scans IPs ``1..254`` in the detected ``/24`` subnet using a
    thread pool.  Each IP is probed on port 8080 (IP Webcam / EpocCam)
    and port 4747 (DroidCam).  Matching services are returned sorted by IP.

    Args:
        timeout: Per-probe timeout in seconds.
        max_workers: Thread pool size (default 50 — scans a /24 in ~8 s).

    Returns:
        A sorted (by IP) list of discovered phone cameras.
    """
    subnet = _get_local_subnet()
    logger.info(f"🔍 Scanning {subnet}.0/24 for phone cameras...")

    ip_range = [f"{subnet}.{i}" for i in range(1, 255)]
    all_found: List[DiscoveredCamera] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(_probe_ip, ip, timeout): ip for ip in ip_range}
        for future in concurrent.futures.as_completed(future_map):
            try:
                results = future.result()
                all_found.extend(results)
            except Exception:
                continue

    # ── Deduplicate ──────────────────────────────────────────
    # It's possible for the same service to match multiple signatures
    # on the same IP:port (e.g. IP Webcam and EpocCam both on 8080).
    # Keep only the most specific match.  Since we check IP Webcam
    # before EpocCam in the signature list, the first match wins.
    seen: set = set()
    deduped: List[DiscoveredCamera] = []
    for cam in sorted(all_found, key=lambda c: [int(x) for x in c.ip.split(".")]):
        key = (cam.ip, cam.port, cam.source_type)
        if key not in seen:
            seen.add(key)
            deduped.append(cam)

    logger.info(f"🔍 Scan complete — found {len(deduped)} device(s)")
    for d in deduped:
        logger.info(f"   {d.display_name} → {d.stream_url}")

    return deduped


# ═══════════════════════════════════════════════════════════════
#  CLI Entry Point (for testing)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    import time

    print("=" * 60)
    print("  Phone Camera Auto-Discovery")
    print("=" * 60)
    print()
    print("  Scanning local network... This takes ~10 seconds.")
    print()

    start = time.time()
    devices = scan_network(timeout=1.5)
    elapsed = time.time() - start

    print()
    print(f"  Scan completed in {elapsed:.1f} s — found {len(devices)} device(s)")
    print()

    if devices:
        for i, d in enumerate(devices, 1):
            typ = "Android (IP Webcam)" if d.source_type == "android_wifi" else "iPhone (EpocCam)"
            print(f"  [{i}] {d.display_name}")
            print(f"       Type: {typ}")
            print(f"       URL:  {d.stream_url}")
            print()
    else:
        print("  No phone cameras found on the local network.")
        print()
        print("  Troubleshooting:")
        print("  1. Make sure your phone is connected to the same Wi-Fi network")
        print("  2. Start the camera app (IP Webcam / DroidCam / EpocCam)")
        print("  3. Check your firewall isn't blocking these ports")
        print("  4. Try entering the IP manually in the dashboard")
