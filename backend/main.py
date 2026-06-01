"""
SMART_ROUTE - Backend API Server
Runs on http://localhost:8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Optional

app = FastAPI(
    title="SMART_ROUTE API",
    description="Decentralized Adaptive Traffic Control System",
    version="0.1.0"
)

# CORS - allow dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ DATA MODELS ============
class TrafficUpdate(BaseModel):
    vehicle_count: int
    breakdown: Optional[Dict[str, int]] = {}


# ============ IN-MEMORY STORAGE ============
traffic_data: Dict[str, dict] = {
    "intersection_1": {
        "intersection_id": "intersection_1",
        "vehicle_count": 0,
        "breakdown": {},
        "signal_state": "GREEN",
        "last_updated": None,
        "history": []
    }
}


# ============ HELPER FUNCTIONS ============
def determine_signal_state(count: int) -> str:
    """Adaptive signal logic"""
    if count < 5:
        return "GREEN"
    elif count < 15:
        return "YELLOW"
    else:
        return "RED"


# ============ API ENDPOINTS ============
@app.get("/")
def root():
    return {
        "message": "🚦 SMART_ROUTE API is running!",
        "status": "online",
        "docs": "http://localhost:8000/docs"
    }


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/traffic/{intersection_id}")
def get_traffic(intersection_id: str):
    """Get current traffic data for an intersection"""
    if intersection_id in traffic_data:
        return traffic_data[intersection_id]
    return {"error": "Intersection not found"}


@app.post("/traffic/{intersection_id}/update")
def update_traffic(intersection_id: str, vehicle_count: int):
    """Update traffic data (called by edge-ai detector)"""
    signal = determine_signal_state(vehicle_count)
    timestamp = datetime.now().isoformat()
    
    # Initialize if new intersection
    if intersection_id not in traffic_data:
        traffic_data[intersection_id] = {
            "intersection_id": intersection_id,
            "history": []
        }
    
    # Update current state
    traffic_data[intersection_id].update({
        "vehicle_count": vehicle_count,
        "signal_state": signal,
        "last_updated": timestamp
    })
    
    # Keep last 50 readings as history
    history = traffic_data[intersection_id].get("history", [])
    history.append({
        "timestamp": timestamp,
        "count": vehicle_count,
        "signal": signal
    })
    traffic_data[intersection_id]["history"] = history[-50:]
    
    return traffic_data[intersection_id]


@app.get("/traffic/{intersection_id}/history")
def get_history(intersection_id: str):
    """Get historical readings"""
    if intersection_id in traffic_data:
        return {
            "intersection_id": intersection_id,
            "history": traffic_data[intersection_id].get("history", [])
        }
    return {"error": "Intersection not found"}


@app.get("/intersections")
def list_intersections():
    """List all monitored intersections"""
    return {
        "intersections": list(traffic_data.keys()),
        "total": len(traffic_data),
        "data": traffic_data
    }


@app.delete("/traffic/{intersection_id}/reset")
def reset_intersection(intersection_id: str):
    """Reset an intersection's data"""
    if intersection_id in traffic_data:
        traffic_data[intersection_id] = {
            "intersection_id": intersection_id,
            "vehicle_count": 0,
            "breakdown": {},
            "signal_state": "GREEN",
            "last_updated": None,
            "history": []
        }
        return {"message": f"Reset {intersection_id}"}
    return {"error": "Not found"}


if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)