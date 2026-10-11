"""
Inference Device Resolver — GPU/CPU provider selection
======================================================

The app previously hard-coded ``CPUExecutionProvider`` for InsightFace and
the deep-liveness ONNX model, silently ignoring an available GPU (verified
on an RTX 3050 Laptop: ``torch.cuda.is_available()`` was True while both
ONNX sessions ran on CPU).

This module resolves the execution providers once, from configuration,
and keeps a working CPU fallback:

- ``INFERENCE_DEVICE=auto`` (default) → use CUDA when both onnxruntime
  reports ``CUDAExecutionProvider`` and a CUDA device is visible to torch;
  otherwise CPU.
- ``INFERENCE_DEVICE=cpu``            → force CPU.
- ``INFERENCE_DEVICE=gpu``            → request CUDA; callers should still
  fall back to CPU if session creation raises.

Usage::

    from utils.inference_device import onnx_providers, torch_ctx_id

    session = ort.InferenceSession(path, providers=onnx_providers())
    app.prepare(ctx_id=torch_ctx_id(), det_size=(640, 640))
"""

from __future__ import annotations

import threading
from typing import List, Optional, Tuple

import config.config as cfg

_lock = threading.Lock()
_resolved: Optional[Tuple[List[str], int]] = None  # (providers, torch ctx_id)

_CPU = (["CPUExecutionProvider"], -1)


def _cuda_usable() -> bool:
    """True when CUDA can realistically be used for inference."""
    try:
        import onnxruntime as ort

        if "CUDAExecutionProvider" not in ort.get_available_providers():
            return False
    except Exception:
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        # onnxruntime says CUDA is available; torch may not be installed
        # (e.g. minimal ONNX-only deployments) — trust onnxruntime.
        return True


def resolve(force: Optional[str] = None) -> Tuple[List[str], int]:
    """Resolve ``(onnx_providers, torch_ctx_id)`` once and cache it.

    Args:
        force: Override the configured device (``"cpu"`` / ``"gpu"`` /
            ``"auto"``). Used by tests and by runtime fallback logic.
    """
    global _resolved
    with _lock:
        if force is None and _resolved is not None:
            return _resolved

        want = str(force if force is not None else getattr(cfg, "INFERENCE_DEVICE", "auto")).strip().lower()

        if want == "cpu":
            result = _CPU
        elif want == "gpu":
            # Caller is expected to fall back to CPU if session creation fails.
            result = (["CUDAExecutionProvider", "CPUExecutionProvider"], 0)
        else:  # auto
            result = (["CUDAExecutionProvider", "CPUExecutionProvider"], 0) if _cuda_usable() else _CPU

        if force is None:
            _resolved = result
        return result


def onnx_providers() -> List[str]:
    """Ordered onnxruntime provider list for the configured device."""
    return list(resolve()[0])


def torch_ctx_id() -> int:
    """Ultralytics/InsightFace ctx id: 0 = first GPU, -1 = CPU."""
    return resolve()[1]


def device_name() -> str:
    """Human-readable resolved device, for health/diagnostics output."""
    providers, _ = resolve()
    return providers[0].replace("ExecutionProvider", "")


def reset_cache() -> None:
    """Drop the cached resolution (tests / after config changes)."""
    global _resolved
    with _lock:
        _resolved = None
