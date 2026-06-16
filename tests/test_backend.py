"""
SmartRoute — Backend API Tests
================================
Tests every REST endpoint in backend/main.py using FastAPI's TestClient.

Run:  pytest tests/test_backend.py -v
"""

import pytest
from fastapi.testclient import TestClient

# conftest.py already set SMARTROUTE_DB env var and patched database.DB_PATH
import main  # from backend/

# ── Shared client ─────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    """Spin up the full app including lifespan (DB init) for the module."""
    with TestClient(main.app) as c:
        yield c


# ── Root & Health ──────────────────────────────────────────────────

def test_root_returns_online(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "online"
    assert "docs" in r.json()


def test_health_returns_healthy(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["db"] == "sqlite"


# ── Intersections ──────────────────────────────────────────────────

def test_list_intersections(client):
    r = client.get("/intersections")
    assert r.status_code == 200
    data = r.json()
    assert "intersections" in data
    assert isinstance(data["intersections"], list)
    assert data["total"] >= 1


def test_get_seeded_intersection(client):
    """intersection_1 is seeded by init_db()."""
    r = client.get("/traffic/intersection_1")
    assert r.status_code == 200
    data = r.json()
    assert data["intersection_id"] == "intersection_1"
    assert "vehicle_count" in data
    assert "signal_state" in data
    assert "last_updated" in data


def test_get_unknown_intersection_is_404(client):
    r = client.get("/traffic/does_not_exist_xyz")
    assert r.status_code == 404


# ── Simple Update ──────────────────────────────────────────────────

def test_update_green_signal(client):
    """vehicle_count < 5 → GREEN"""
    r = client.post("/traffic/intersection_1/update?vehicle_count=3")
    assert r.status_code == 200
    assert r.json()["signal_state"] == "GREEN"
    assert r.json()["vehicle_count"] == 3


def test_update_yellow_signal(client):
    """5 ≤ vehicle_count < 15 → YELLOW"""
    r = client.post("/traffic/intersection_1/update?vehicle_count=10")
    assert r.status_code == 200
    assert r.json()["signal_state"] == "YELLOW"


def test_update_red_signal(client):
    """vehicle_count ≥ 15 → RED"""
    r = client.post("/traffic/intersection_1/update?vehicle_count=20")
    assert r.status_code == 200
    assert r.json()["signal_state"] == "RED"


def test_update_creates_new_intersection(client):
    """Posting to an unknown ID should auto-create it."""
    r = client.post("/traffic/new_junction_99/update?vehicle_count=5")
    assert r.status_code == 200
    assert r.json()["intersection_id"] == "new_junction_99"


# ── Detailed Update ────────────────────────────────────────────────

def test_detailed_update_with_lanes(client):
    payload = {
        "total_vehicles_now": 14,
        "total_unique_seen": 50,
        "algorithm": "adaptive",
        "lanes": {
            "north_in": {"current": 4, "cumulative": 20, "direction": "south"},
            "south_in": {"current": 3, "cumulative": 18, "direction": "north"},
            "east_in":  {"current": 4, "cumulative": 15, "direction": "west"},
            "west_in":  {"current": 3, "cumulative": 12, "direction": "east"},
        },
    }
    r = client.post("/traffic/intersection_1/detailed", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["vehicle_count"] == 14
    assert "north_in" in data["lanes"]
    assert data["lanes"]["north_in"]["current"] == 4


# ── Signal Endpoint ────────────────────────────────────────────────

def test_signal_update_ns_green(client):
    r = client.post("/traffic/intersection_1/signal?signal=NS_GREEN&algorithm=webster")
    assert r.status_code == 200
    assert r.json()["signal_state"] == "NS_GREEN"


def test_signal_update_ew_green(client):
    r = client.post("/traffic/intersection_1/signal?signal=EW_GREEN")
    assert r.status_code == 200
    assert r.json()["signal_state"] == "EW_GREEN"


def test_signal_update_unknown_intersection_is_404(client):
    r = client.post("/traffic/ghost_abc/signal?signal=NS_GREEN")
    assert r.status_code == 404


# ── History ────────────────────────────────────────────────────────

def test_history_returns_list(client):
    # Generate several readings
    for i in range(6):
        client.post(f"/traffic/intersection_1/update?vehicle_count={i * 4}")

    r = client.get("/traffic/intersection_1/history")
    assert r.status_code == 200
    data = r.json()
    assert "history" in data
    assert isinstance(data["history"], list)
    assert len(data["history"]) >= 6


def test_history_limit_param(client):
    r = client.get("/traffic/intersection_1/history?limit=2")
    assert r.status_code == 200
    assert len(r.json()["history"]) <= 2


def test_history_has_expected_fields(client):
    r = client.get("/traffic/intersection_1/history?limit=1")
    assert r.status_code == 200
    row = r.json()["history"][0]
    assert "timestamp" in row
    assert "count" in row
    assert "signal" in row


def test_history_unknown_intersection_is_404(client):
    r = client.get("/traffic/does_not_exist_abc/history")
    assert r.status_code == 404


# ── Emergency ──────────────────────────────────────────────────────

def test_emergency_north_activates_ns_green(client):
    r = client.post(
        "/emergency/intersection_1",
        json={"lane": "north", "duration": 30}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["active"] is True
    assert data["lane"] == "north"
    assert "NS" in data["phase"]
    assert "expires_at" in data


def test_emergency_east_activates_ew_green(client):
    r = client.post(
        "/emergency/intersection_1",
        json={"lane": "east", "duration": 30}
    )
    assert r.status_code == 200
    assert "EW" in r.json()["phase"]


def test_emergency_visible_in_traffic_state(client):
    client.post("/emergency/intersection_1", json={"lane": "south", "duration": 30})
    state = client.get("/traffic/intersection_1").json()
    assert "emergency" in state
    assert state["emergency"]["active"] is True


def test_emergency_clear(client):
    client.post("/emergency/intersection_1", json={"lane": "north", "duration": 30})
    r = client.delete("/emergency/intersection_1")
    assert r.status_code == 200
    state = client.get("/traffic/intersection_1").json()
    assert state["emergency"]["active"] is False


# ── Reset ──────────────────────────────────────────────────────────

def test_reset_clears_vehicle_count(client):
    client.post("/traffic/intersection_1/update?vehicle_count=25")
    r = client.delete("/traffic/intersection_1/reset")
    assert r.status_code == 200
    state = client.get("/traffic/intersection_1").json()
    assert state["vehicle_count"] == 0
    assert state["signal_state"] == "GREEN"


def test_reset_unknown_is_404(client):
    r = client.delete("/traffic/unknown_reset_test/reset")
    assert r.status_code == 404
