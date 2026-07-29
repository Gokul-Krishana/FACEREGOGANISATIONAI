"""
Background Job Queue Service
=============================

Lightweight in-process job queue for background tasks such as:
    - Batch face enrollment
    - Bulk attendance import/export
    - Embedding index rebuild
    - Unknown face cleanup
    - Report generation

Uses asyncio.Queue for simplicity. For production at scale,
swap to Celery + Redis/RabbitMQ.

Usage::

    from api.job_queue import job_queue, JobStatus

    # Enqueue a job
    job_id = await job_queue.enqueue("batch_enroll", {"csv_path": "..."})

    # Check status
    status = await job_queue.status(job_id)

    # List all jobs
    jobs = await job_queue.list_jobs()
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job:
    """Represents a background job."""

    def __init__(
        self,
        job_type: str,
        params: Dict[str, Any],
        created_by: Optional[str] = None,
    ):
        self.id: str = uuid.uuid4().hex[:12]
        self.job_type = job_type
        self.params = params
        self.created_by = created_by
        self.status: JobStatus = JobStatus.PENDING
        self.progress: float = 0.0  # 0.0 to 1.0
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at: float = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.cancelled: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "params": self.params,
            "created_by": self.created_by,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": datetime.fromtimestamp(
                self.created_at, tz=timezone.utc
            ).isoformat(),
            "started_at": (
                datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat()
                if self.started_at
                else None
            ),
            "completed_at": (
                datetime.fromtimestamp(self.completed_at, tz=timezone.utc).isoformat()
                if self.completed_at
                else None
            ),
        }


# Type for job handler functions
JobHandler = Callable[[Job, asyncio.Event], Coroutine[Any, Any, Any]]


class JobQueue:
    """In-process async job queue with worker pool."""

    def __init__(self, max_workers: int = 3, max_queue_size: int = 100):
        self._queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=max_queue_size)
        self._jobs: Dict[str, Job] = {}
        self._handlers: Dict[str, JobHandler] = {}
        self._workers: List[asyncio.Task] = []
        self._max_workers = max_workers
        self._running = False

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """Register a handler function for a job type."""
        self._handlers[job_type] = handler
        logger.info("Registered handler for job type: %s", job_type)

    async def start(self) -> None:
        """Start the worker pool."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(task)
        logger.info("Job queue started with %d workers", self._max_workers)

    async def stop(self) -> None:
        """Stop all workers gracefully."""
        self._running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Job queue stopped")

    async def enqueue(
        self,
        job_type: str,
        params: Dict[str, Any] = None,
        created_by: Optional[str] = None,
    ) -> str:
        """
        Enqueue a new job.

        Args:
            job_type: Type of job (must have a registered handler).
            params: Job parameters.
            created_by: Username of the user who created the job.

        Returns:
            Job ID string.
        """
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job type: {job_type}")

        job = Job(job_type=job_type, params=params or {}, created_by=created_by)
        self._jobs[job.id] = job
        await self._queue.put(job)

        logger.info(
            "Job enqueued: %s (type=%s, by=%s)",
            job.id, job_type, created_by
        )
        return job.id

    async def status(self, job_id: str) -> Optional[dict]:
        """Get the status of a job."""
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    async def cancel(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        job.cancelled = True
        job.status = JobStatus.CANCELLED
        job.completed_at = time.time()
        return True

    async def list_jobs(
        self,
        status_filter: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> List[dict]:
        """List jobs, optionally filtered by status."""
        jobs = list(self._jobs.values())
        if status_filter:
            jobs = [j for j in jobs if j.status == status_filter]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    async def _worker(self, name: str) -> None:
        """Worker loop that processes jobs from the queue."""
        logger.info("Worker %s started", name)
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if job.cancelled:
                continue

            handler = self._handlers.get(job.job_type)
            if not handler:
                job.status = JobStatus.FAILED
                job.error = f"No handler for job type: {job.job_type}"
                job.completed_at = time.time()
                continue

            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            cancel_event = asyncio.Event()

            try:
                result = await handler(job, cancel_event)
                if job.cancelled:
                    job.status = JobStatus.CANCELLED
                else:
                    job.status = JobStatus.COMPLETED
                    job.result = result
                    job.progress = 1.0
            except Exception as exc:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                logger.error("Job %s failed: %s", job.id, exc)
            finally:
                job.completed_at = time.time()
                self._queue.task_done()

            logger.info(
                "Job %s completed: status=%s",
                job.id, job.status.value
            )

    def stats(self) -> dict:
        """Return queue statistics."""
        status_counts = {}
        for job in self._jobs.values():
            status_counts[job.status.value] = status_counts.get(job.status.value, 0) + 1
        return {
            "total_jobs": len(self._jobs),
            "queue_size": self._queue.qsize(),
            "workers": len(self._workers),
            "running": self._running,
            "status_counts": status_counts,
        }


# ── Built-in Job Handlers ───────────────────────────────────────────


async def _batch_enroll_handler(job: Job, cancel: asyncio.Event) -> dict:
    """Handler for batch face enrollment from CSV."""
    csv_path = job.params.get("csv_path", "")
    # Placeholder: in production, iterate CSV, enroll each face
    total = job.params.get("total_records", 10)
    enrolled = 0
    for i in range(total):
        if cancel.is_set():
            break
        job.progress = (i + 1) / total
        enrolled += 1
        await asyncio.sleep(0.1)  # Simulate work

    return {"enrolled": enrolled, "total": total}


async def _rebuild_index_handler(job: Job, cancel: asyncio.Event) -> dict:
    """Handler for rebuilding the FAISS embedding index."""
    job.progress = 0.5
    await asyncio.sleep(1.0)  # Simulate work
    job.progress = 1.0
    return {"rebuilt": True}


async def _cleanup_unknown_handler(job: Job, cancel: asyncio.Event) -> dict:
    """Handler for cleaning up old unknown face snapshots."""
    days = job.params.get("retention_days", 30)
    job.progress = 0.5
    await asyncio.sleep(0.5)
    job.progress = 1.0
    return {"cleaned_days": days, "deleted": 0}


# Global instance
job_queue = JobQueue()


def register_default_handlers() -> None:
    """Register built-in job handlers."""
    job_queue.register_handler("batch_enroll", _batch_enroll_handler)
    job_queue.register_handler("rebuild_index", _rebuild_index_handler)
    job_queue.register_handler("cleanup_unknown", _cleanup_unknown_handler)
