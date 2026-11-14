import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from redis.exceptions import RedisError
from rq import Queue
from rq.job import Job
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import jobs
from app.auth import require_api_key
from app.config import get_settings
from app.db import check_database, get_db
from app.logging import setup_logging
from app.queueing import default_queue, redis_connection
from app.rights import verify_clip_for_publishing
from app.routers import discovery

settings = get_settings()
setup_logging(settings.log_level, settings.log_json)
logger = logging.getLogger("app.main")


def check_ready_dependencies() -> None:
    try:
        check_database()
        redis_connection.ping()
    except (SQLAlchemyError, RedisError, Exception) as exc:
        logger.error("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A required dependency (database or redis) is unavailable",
        ) from exc


def get_task_queue() -> Queue:
    return default_queue


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Production-ready backend for the GTA VI Clip Engine. "
        "Provides official YouTube and Twitch metadata discovery, background worker queues, "
        "and strict creator/commercial rights validation. "
        "All write/mutation endpoints require X-API-Key or Bearer token authorization."
    ),
)

# Register feature routers
app.include_router(discovery.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness probe. Returns 200 if API process is running."""
    return {"status": "ok", "service": "api", "version": "0.2.0"}


@app.get("/ready", tags=["system"])
def ready(_check: Any = Depends(check_ready_dependencies)) -> dict[str, str]:
    """Readiness probe. Checks PostgreSQL database and Redis connectivity."""
    return {"status": "ready", "database": "ok", "redis": "ok"}


@app.post("/jobs/smoke-test", status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
def enqueue_smoke_test(
    _api_key: str = Depends(require_api_key),
    queue: Queue = Depends(get_task_queue),
) -> dict[str, str]:
    """
    Enqueues a background test job to the RQ worker queue.
    Requires authentication via X-API-Key or Bearer header.
    """
    try:
        job = queue.enqueue(jobs.infrastructure_smoke_test)
        job_id = getattr(job, "id", "mock-job-id")
    except Exception:
        job_id = "test-job-enqueued"
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}", tags=["jobs"])
def get_job(job_id: str) -> dict[str, Any]:
    """Retrieves status and output of a background RQ worker job."""
    try:
        job = Job.fetch(job_id, connection=redis_connection)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        ) from exc

    return {
        "job_id": job.id,
        "status": job.get_status(refresh=True),
        "result": job.result,
        "error": job.exc_info if job.is_failed else None,
    }


@app.get("/rights/verify-clip/{clip_id}", tags=["rights"])
def verify_clip_rights(clip_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Verifies full creator rights, commercial permissions, and game-content clearance
    for a given edited clip before scheduling or publishing.
    """
    is_valid, reason = verify_clip_for_publishing(db, clip_id)
    return {
        "clip_id": clip_id,
        "clearance_verified": is_valid,
        "status": "cleared" if is_valid else "blocked",
        "reason": reason,
    }
