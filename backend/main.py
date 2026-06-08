"""
SmartRoute — Backend API Server
=================================
Runs on http://localhost:8000

Key fixes applied:
  1. All endpoints are defined BEFORE if __name__ == "__main__"
  2. Traffic data is persisted to SQLite (backend/smartroute.db)
     so history survives server restarts.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Optional

import database as db


# ── Startup / Shutdown ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the SQLite database on startup."""
    db.init_db()
    yield
    # (teardown goes here if needed)


app = FastAPI(
    title="SmartRoute API",
    description="Decentralized Adaptive Traffic Control System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow dashboard & forecasting API to connect
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


# ── Helper ────────────────────────────────────────────────────────
def determine_signal_state(count: int) -> str:
    """Simple threshold-based signal logic (overridden by simulation phases)."""
    if count < 5:
        return "GREEN"
    elif count < 15:
        return "YELLOW"
    else:
        return "RED"


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
    """List all monitored intersections from the database."""
    intersections = db.list_all_intersections()
    return {
        "total":         len(intersections),
        "intersections": intersections,
    }


@app.get("/traffic/{intersection_id}")
def get_traffic(intersection_id: str):
    """Get current traffic state for an intersection."""
    state = db.get_intersection_state(intersection_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return state


@app.get("/traffic/{intersection_id}/history")
def get_history(intersection_id: str, limit: int = 100):
    """Get the last N traffic readings (default 100, max 500)."""
    limit = min(limit, 500)
    state = db.get_intersection_state(intersection_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    history = db.get_history(intersection_id, limit=limit)
    return {
        "intersection_id": intersection_id,
        "count":           len(history),
        "history":         history,
    }


@app.post("/traffic/{intersection_id}/update")
def update_traffic(intersection_id: str, vehicle_count: int):
    """Simple update — called by edge-ai detector (HTTP fallback)."""
    signal    = determine_signal_state(vehicle_count)
    timestamp = datetime.now().isoformat()

    db.upsert_intersection_state(
        intersection_id, vehicle_count, signal, {}
    )
    db.insert_reading(intersection_id, vehicle_count, signal, {})

    state = db.get_intersection_state(intersection_id)
    return state


@app.post("/traffic/{intersection_id}/detailed")
def update_detailed(intersection_id: str, data: dict):
    """
    Receive full lane-level data from the YOLOv8 detector or SUMO simulation.
    Persists to SQLite and keeps an in-DB history.
    """
    total     = data.get("total_vehicles_now", 0)
    signal    = determine_signal_state(total)
    lanes     = data.get("lanes", {})
    unique    = data.get("total_unique_seen", 0)
    algorithm = data.get("algorithm", "adaptive")

    db.upsert_intersection_state(
        intersection_id,
        vehicle_count=total,
        signal_state=signal,
        lanes=lanes,
        algorithm=algorithm,
        unique_total=unique,
    )
    db.insert_reading(intersection_id, total, signal, lanes)

    state = db.get_intersection_state(intersection_id)
    return state


@app.post("/traffic/{intersection_id}/signal")
def update_signal(intersection_id: str, signal: str, algorithm: str = "adaptive"):
    """
    Update just the signal phase (called by adaptive_controller.py
    to report real SUMO phase names like NS_GREEN, EW_GREEN).
    """
    state = db.get_intersection_state(intersection_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Intersection not found")

    db.upsert_intersection_state(
        intersection_id,
        vehicle_count=state["vehicle_count"],
        signal_state=signal,
        lanes=state["lanes"],
        algorithm=algorithm,
    )
    return db.get_intersection_state(intersection_id)


@app.delete("/traffic/{intersection_id}/reset")
def reset_intersection(intersection_id: str):
    """Clear all readings and reset state for an intersection."""
    state = db.get_intersection_state(intersection_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Intersection not found")
    db.reset_intersection(intersection_id)
    return {"message": f"✅ Reset {intersection_id}", "status": "cleared"}


# ── Entry Point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn   # pyrefly: ignore [missing-import]
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)