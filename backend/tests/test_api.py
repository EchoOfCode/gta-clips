from fastapi.testclient import TestClient


def test_health_and_ready_endpoints(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp_ready = client.get("/ready")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "ready"


def test_discovery_status_endpoint(client: TestClient):
    resp = client.get("/discovery/status")
    assert resp.status_code == 200
    statuses = resp.json()
    assert isinstance(statuses, list)
    providers = {s["provider"] for s in statuses}
    assert "youtube" in providers
    assert "twitch" in providers


def test_discovery_write_endpoint_authentication_rejections(client: TestClient):
    payload = {"provider": "youtube", "query": "GTA VI"}

    # 1. No credentials provided
    resp_no_auth = client.post("/discovery/run", json=payload)
    assert resp_no_auth.status_code == 401
    assert "Invalid or missing API credentials" in resp_no_auth.json()["detail"]

    # 2. Invalid credentials in X-API-Key
    resp_bad_key = client.post(
        "/discovery/run",
        json=payload,
        headers={"X-API-Key": "completely-wrong-key"},
    )
    assert resp_bad_key.status_code == 401

    # 3. Invalid credentials in Authorization Bearer
    resp_bad_bearer = client.post(
        "/discovery/run",
        json=payload,
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp_bad_bearer.status_code == 401


def test_smoke_test_authentication_rejection(client: TestClient):
    # Smoke test enqueues background worker job, must be authenticated
    resp_no_auth = client.post("/jobs/smoke-test")
    assert resp_no_auth.status_code == 401

    resp_valid = client.post(
        "/jobs/smoke-test",
        headers={"X-API-Key": "test-secret-key-12345"},
    )
    assert resp_valid.status_code == 202
    assert "job_id" in resp_valid.json()


def test_paginated_discovery_listings(client: TestClient):
    # Test empty listing endpoints
    for endpoint in (
        "/discovery/videos",
        "/discovery/streams",
        "/discovery/channels",
        "/discovery/runs",
    ):
        resp = client.get(endpoint)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["page"] == 1
        assert data["total"] == 0


def test_rights_verification_endpoint(client: TestClient):
    resp = client.get("/rights/verify-clip/99999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["clip_id"] == 99999
    assert data["clearance_verified"] is False
    assert data["status"] == "blocked"
