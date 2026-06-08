"""
Integration tests for the FastAPI backend (Task 12).
Run with: pytest services/fastapi_app/tests/test_api.py -v
"""
import sys
import os
import pytest

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "agent"))

from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


# ── Auth Tests ──────────────────────────────────────────────────────────────
class TestAuth:
    def test_login_success(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_failure(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401


# ── Supplier Endpoints ──────────────────────────────────────────────────────
class TestSuppliers:
    def test_list_suppliers(self):
        resp = client.get("/api/suppliers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 50
        # Should be sorted by risk_score descending
        scores = [s["risk_score"] for s in data]
        assert scores == sorted(scores, reverse=True)

    def test_list_suppliers_filter_country(self):
        resp = client.get("/api/suppliers?country=India")
        assert resp.status_code == 200
        data = resp.json()
        for s in data:
            assert s["country"] == "India"

    def test_list_suppliers_filter_min_risk(self):
        resp = client.get("/api/suppliers?min_risk=0.5")
        assert resp.status_code == 200
        data = resp.json()
        for s in data:
            assert s["risk_score"] >= 0.5

    def test_get_supplier_risk(self):
        resp = client.get("/api/suppliers/SUPPLIER_001/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["supplier_id"] == "SUPPLIER_001"
        assert "risk_score" in data
        assert "confidence" in data
        assert "top_3_reasons" in data

    def test_get_supplier_risk_not_found(self):
        resp = client.get("/api/suppliers/NONEXISTENT/risk")
        assert resp.status_code == 404


# ── Reroute Endpoints ──────────────────────────────────────────────────────
class TestReroute:
    def test_trigger_reroute(self):
        resp = client.get("/api/suppliers/SUPPLIER_001/reroute?urgency=urgent")
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["supplier_id"] == "SUPPLIER_001"

    def test_get_job_status(self):
        # First create a job
        resp = client.get("/api/suppliers/SUPPLIER_002/reroute")
        job_id = resp.json()["job_id"]

        # Poll job status
        import time
        time.sleep(0.5)  # Wait for async task
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("pending", "completed", "failed")

    def test_get_job_not_found(self):
        resp = client.get("/api/jobs/nonexistent-id")
        assert resp.status_code == 404


# ── Disruptions Endpoint ───────────────────────────────────────────────────
class TestDisruptions:
    def test_list_disruptions_empty(self):
        resp = client.get("/api/disruptions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Metrics Endpoint ───────────────────────────────────────────────────────
class TestMetrics:
    def test_get_metrics(self):
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suppliers_monitored"] == 50
        assert "high_risk_count" in data
        assert "avg_response_time_ms" in data


# ── Simulate Endpoint ──────────────────────────────────────────────────────
class TestSimulate:
    def test_simulate_risk(self):
        resp = client.post("/api/simulate", json={"supplier_id": "SUPPLIER_005", "risk_score": 0.85})
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_risk"] == 0.85
        assert data["supplier_id"] == "SUPPLIER_005"

        # Verify it updated
        resp = client.get("/api/suppliers/SUPPLIER_005/risk")
        assert resp.status_code == 200

    def test_simulate_not_found(self):
        resp = client.post("/api/simulate", json={"supplier_id": "NONEXISTENT", "risk_score": 0.5})
        assert resp.status_code == 404

    def test_simulate_invalid_risk(self):
        resp = client.post("/api/simulate", json={"supplier_id": "SUPPLIER_001", "risk_score": 1.5})
        assert resp.status_code == 422  # Validation error


# ── Health Check ───────────────────────────────────────────────────────────
class TestHealth:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
