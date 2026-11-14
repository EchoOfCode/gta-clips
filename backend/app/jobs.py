from datetime import UTC, datetime


def infrastructure_smoke_test() -> dict[str, str]:
    """A harmless queued job used to verify the worker/Redis pipeline."""
    return {
        "status": "completed",
        "message": "Background worker is connected and processing jobs.",
        "completed_at": datetime.now(UTC).isoformat(),
    }
