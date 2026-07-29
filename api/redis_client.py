"""
Redis integration for temporary state management in Face Recognition AI.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import redis


class RedisClient:
    """Redis client for state management."""

    def __init__(self, url: str = None):
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    # ── Student State ──────────────────────────────────────────────

    def set_student_last_seen(self, student_id: int, camera_id: int) -> None:
        """Track when a student was last seen."""
        key = f"student:last_seen:{student_id}"
        self.client.hset(key, mapping={
            "camera_id": camera_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.client.expire(key, 86400)  # 24 hours

    def get_student_last_seen(self, student_id: int) -> Optional[dict]:
        """Get student's last seen info."""
        key = f"student:last_seen:{student_id}"
        data = self.client.hgetall(key)
        return data if data else None

    def is_attendance_marked(self, student_id: int, section_id: int, date_str: str) -> bool:
        """Check if attendance already marked for student in section today."""
        key = f"attendance:marked:{student_id}:{section_id}:{date_str}"
        return self.client.exists(key) > 0

    def mark_attendance(self, student_id: int, section_id: int, date_str: str, ttl: int = 86400) -> None:
        """Mark attendance in Redis to prevent duplicates."""
        key = f"attendance:marked:{student_id}:{section_id}:{date_str}"
        self.client.setex(key, ttl, "1")

    # ── Camera State ───────────────────────────────────────────────

    def set_camera_status(self, camera_id: int, status: str, metadata: dict = None) -> None:
        """Update camera status."""
        key = f"camera:status:{camera_id}"
        data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
        if metadata:
            data["metadata"] = json.dumps(metadata)
        self.client.hset(key, mapping=data)
        self.client.expire(key, 300)  # 5 minutes

    def get_camera_status(self, camera_id: int) -> Optional[dict]:
        """Get camera status."""
        key = f"camera:status:{camera_id}"
        return self.client.hgetall(key) or None

    def get_all_camera_statuses(self) -> dict:
        """Get all camera statuses."""
        pattern = "camera:status:*"
        keys = self.client.keys(pattern)
        result = {}
        for key in keys:
            cam_id = key.split(":")[-1]
            result[cam_id] = self.client.hgetall(key)
        return result

    # ── Recognition Cooldown ───────────────────────────────────────

    def is_in_cooldown(self, track_id: str, camera_id: int) -> bool:
        """Check if recognition is in cooldown for this track."""
        key = f"recognition:cooldown:{camera_id}:{track_id}"
        return self.client.exists(key) > 0

    def set_cooldown(self, track_id: str, camera_id: int, ttl: int = 60) -> None:
        """Set recognition cooldown."""
        key = f"recognition:cooldown:{camera_id}:{track_id}"
        self.client.setex(key, ttl, "1")

    # ── Track Identity ──────────────────────────────────────────────

    def set_track_identity(self, track_id: str, student_id: int, confidence: float) -> None:
        """Cache track identity for smoothing."""
        key = f"track:identity:{track_id}"
        self.client.hset(key, mapping={
            "student_id": student_id,
            "confidence": confidence,
            "updated_at": datetime.utcnow().isoformat()
        })
        self.client.expire(key, 300)  # 5 minutes

    def get_track_identity(self, track_id: str) -> Optional[dict]:
        """Get cached track identity."""
        key = f"track:identity:{track_id}"
        return self.client.hgetall(key) or None

    # ── Session/Request Caching ────────────────────────────────────

    def cache_get(self, key: str) -> Optional[str]:
        """Get cached value."""
        return self.client.get(key)

    def cache_set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set cached value."""
        if not isinstance(value, str):
            value = json.dumps(value)
        self.client.setex(key, ttl, value)

    def cache_delete(self, key: str) -> None:
        """Delete cached value."""
        self.client.delete(key)


# Global instance
_redis_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    """Get global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def close_redis():
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        _redis_client.close()
        _redis_client = None