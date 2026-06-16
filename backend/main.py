"""
SmartRoute — Backend API Server
=================================
Runs on http://localhost:8000

Features:
  - SQLite persistence via database.py (survives restarts)
  - All endpoints defined BEFORE if __name__ == "__main__"
  - Emergency Vehicle Priority override
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db


# ── Emergency state (in-memory — intentionally transient) ─────────
# Structure: {intersection_id: {active, lane, phase, expires_at}}
_emergency: Dict[str, dict] = {}

LANE_TO_PHASE = {
    "north": "NS_GREEN", "south": "NS_GREEN",
    "east":  "EW_GREEN", "west":  "EW_GREEN",
}


def _get_emergency(intersection_id: str) -> dict:
    """Return emergency status, expiring stale entries automatically."""
    entry = _emergency.get(intersection_id)
    if entry and datetime.fromisoformat(entry["expires_at"]) < datetime.now():
        del _emergency[intersection_id]
        return {"active": False}
    return entry if entry else {"active": False}


# ── Startup / Shutdown ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="SmartRoute API",
    description="Decentralized Adaptive Traffic Control System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Data Models ───────────────────────────────────────────────────
class TrafficUpdate(BaseModel):
    vehicle_count: int
    breakdown: Optional[Dict[str, int]] = {}


class EmergencyRequest(BaseModel):
    lane: str       # "north" | "south" | "east" | "west"
    duration: int = 30  # seconds to hold the green phase


# ── Helpers ───────────────────────────────────────────────────────
def determine_signal_state(count: int) -> str:
    if count < 5:   return "GREEN"
    if count < 15:  return "YELLOW"
    return "RED"


def _state_with_emergency(state: dict, intersection_id: str) -> dict:
    """Attach current emergency status to any state dict before returning."""
    state["emergency"] = _get_emergency(intersection_id)
    return state


# ── Endpoints ─────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "🚦 SmartRoute API is running!",
        "status":  "online",
        "docs":    "http://localhost:8000/docs",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    return {
        "status":    "healthy",
        "timestamp": datetime.now().isoformat(),
        "db":        "sqlite",
    }


@app.get("/intersections")
def list_intersections():
    intersections = db.list_all_intersections()
    return {"total": len(intersections), "intersections": intersections}


@app.get("/traffic/{intersection_id}")
def get_traffic(intersection_id: str):
    state = db.get_intersection_state(intersection_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return _state_with_emergency(state, intersection_id)


@app.get("/traffic/{intersection_id}/history")
def get_history(intersection_id: str, limit: int = 100):
    limit = min(limit, 500)
    if db.get_intersection_state(intersection_id) is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    history = db.get_history(intersection_id, limit=limit)
    return {"intersection_id": intersection_id, "count": len(history), "history": history}


@app.post("/traffic/{intersection_id}/update")
def update_traffic(intersection_id: str, vehicle_count: int):
    signal = determine_signal_state(vehicle_count)
    db.upsert_intersection_state(intersection_id, vehicle_count, signal, {})
    db.insert_reading(intersection_id, vehicle_count, signal, {})
    state = db.get_intersection_state(intersection_id)
    return _state_with_emergency(state, intersection_id)


@app.post("/traffic/{intersection_id}/detailed")
def update_detailed(intersection_id: str, data: dict):
    total     = data.get("total_vehicles_now", 0)
    signal    = determine_signal_state(total)
    lanes     = data.get("lanes", {})
    unique    = data.get("total_unique_seen", 0)
    algorithm = data.get("algorithm", "adaptive")

    db.upsert_intersection_state(
        intersection_id, vehicle_count=total, signal_state=signal,
        lanes=lanes, algorithm=algorithm, unique_total=unique,
    )
    db.insert_reading(intersection_id, total, signal, lanes)
    state = db.get_intersection_state(intersection_id)
    return _state_with_emergency(state, intersection_id)


@app.post("/traffic/{intersection_id}/signal")
def update_signal(intersection_id: str, signal: str, algorithm: str = "adaptive"):
    state = db.get_intersection_state(intersection_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    db.upsert_intersection_state(
        intersection_id, vehicle_count=state["vehicle_count"],
        signal_state=signal, lanes=state["lanes"], algorithm=algorithm,
    )
    state = db.get_intersection_state(intersection_id)
    return _state_with_emergency(state, intersection_id)


@app.delete("/traffic/{intersection_id}/reset")
def reset_intersection(intersection_id: str):
    if db.get_intersection_state(intersection_id) is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    db.reset_intersection(intersection_id)
    return {"message": f"✅ Reset {intersection_id}", "status": "cleared"}


# ── Emergency Vehicle Priority ────────────────────────────────────

@app.post("/emergency/{intersection_id}")
def trigger_emergency(intersection_id: str, req: EmergencyRequest):
    """
    Force an intersection to green for the emergency vehicle's lane.
    Automatically expires after `duration` seconds.
    """
    lane = req.lane.lower()
    if lane not in LANE_TO_PHASE:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lane '{lane}'. Must be: north, south, east, west"
        )

    phase      = LANE_TO_PHASE[lane]
    expires_at = (datetime.now() + timedelta(seconds=req.duration)).isoformat()

    _emergency[intersection_id] = {
        "active":     True,
        "lane":       lane,
        "phase":      phase,
        "duration":   req.duration,
        "expires_at": expires_at,
        "triggered_at": datetime.now().isoformat(),
    }

    # Also push the signal state to DB so simulation can pick it up
    state = db.get_intersection_state(intersection_id)
    if state:
        db.upsert_intersection_state(
            intersection_id,
            vehicle_count=state["vehicle_count"],
            signal_state=phase,
            lanes=state["lanes"],
            algorithm="emergency",
        )

    print(f"🚨 EMERGENCY: {intersection_id} → {phase} for {req.duration}s (lane: {lane})")
    return _emergency[intersection_id]


@app.delete("/emergency/{intersection_id}")
def clear_emergency(intersection_id: str):
    """Manually cancel an active emergency override."""
    _emergency.pop(intersection_id, None)
    return {"active": False, "message": f"Emergency cleared for {intersection_id}"}


@app.get("/emergency/{intersection_id}")
def get_emergency_status(intersection_id: str):
    """Check if an emergency is currently active."""
    return _get_emergency(intersection_id)


# ── Entry Point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn   # pyrefly: ignore [missing-import]
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)