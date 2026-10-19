"""Reusable live-camera pipeline helpers.

These are generic Python concurrency primitives, not Streamlit UI code.
They were historically housed under ``dashboard/`` because that was where
the live page lived; they are now regrouped under ``pipeline/`` as the app's
primary UI moves to the Next.js frontend.

Public helpers::

    pipeline.frame_buffer   FrameBuffer / ResultsBuffer / module singletons
    pipeline.camera_owner   CameraOwner singleton
    pipeline.latency_logger LatencyLogger
"""
