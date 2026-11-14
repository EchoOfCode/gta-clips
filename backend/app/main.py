from fastapi import FastAPI, HTTPException
from redis.exceptions import RedisError
from rq.job import Job
from sqlalchemy.exc import SQLAlchemyError

from app import jobs
from app.config import get_settings
from app.db import check_database
from app.queueing import default_queue, redis_connection

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api", "version": "0.1.0"}


@app.get("/ready", tags=["system"])
def ready() -> dict[str, str]:
    try:
        check_database()
        redis_connection.ping()
    except (SQLAlchemyError, RedisError) as exc:
        raise HTTPException(status_code=503, detail="A required dependency is unavailable") from exc
    return {"status": "ready", "database": "ok", "redis": "ok"}


@app.post("/jobs/smoke-test", status_code=202, tags=["jobs"])
def enqueue_smoke_test() -> dict[str, str]:
    job = default_queue.enqueue(jobs.infrastructure_smoke_test)
    return {"job_id": job.id, "status": "queued"}


@app.get("/jobs/{job_id}", tags=["jobs"])
def get_job(job_id: str) -> dict:
    try:
        job = Job.fetch(job_id, connection=redis_connection)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    return {
        "job_id": job.id,
        "status": job.get_status(refresh=True),
        "result": job.result,
        "error": job.exc_info if job.is_failed else None,
    }
