"""
SmartRoute — Forecasting Prediction API
=========================================
Serves LSTM traffic predictions on port 8001.
Integrates with the main backend — the dashboard polls /predict
to show "expected congestion in 15 min".

Endpoints:
  GET  /predict/{intersection_id}   → next predicted vehicle count
  GET  /predict/{intersection_id}/horizon?steps=N → N-step forecast
  GET  /health

Usage:
  python predict_api.py
"""

import os
import json
import numpy as np
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BACKEND_URL     = os.getenv("BACKEND_URL",     "http://localhost:8000")
MODEL_PATH      = os.getenv("MODEL_PATH",      "lstm_traffic_model.h5")
NORM_PARAMS     = os.getenv("NORM_PARAMS",     "norm_params.npy")
SEQ_LEN         = int(os.getenv("SEQ_LEN",     "20"))
STEP_SECONDS    = 2    # backend sends data every 2s
STEPS_15_MIN    = 450  # 15min / 2s

app = FastAPI(
    title="SmartRoute Forecast API",
    description="LSTM-based traffic volume prediction",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load model lazily ────────────────────────────────────────────
_model      = None
_norm_mn    = 0.0
_norm_mx    = 120.0


def load_model_once():
    global _model, _norm_mn, _norm_mx
    if _model is not None:
        return True
    try:
        from tensorflow.keras.models import load_model as keras_load
        _model = keras_load(MODEL_PATH)
        params = np.load(NORM_PARAMS)
        _norm_mn, _norm_mx = float(params[0]), float(params[1])
        print(f"✓ Model loaded from {MODEL_PATH}")
        return True
    except Exception as e:
        print(f"⚠  Model not loaded: {e}")
        return False


def _norm(x):   return (x - _norm_mn) / max(_norm_mx - _norm_mn, 1e-6)
def _denorm(x): return x * (_norm_mx - _norm_mn) + _norm_mn


def fetch_recent_counts(intersection_id: str, n: int = SEQ_LEN) -> list[float]:
    """Get last N vehicle counts from the main backend."""
    try:
        url = f"{BACKEND_URL}/traffic/{intersection_id}/history"
        r   = requests.get(url, timeout=3)
        r.raise_for_status()
        history = r.json().get("history", [])
        counts  = [h["count"] for h in history if "count" in h]
        return counts[-n:]
    except Exception:
        return []


def fallback_heuristic(counts: list[float], steps: int = 1) -> list[float]:
    """Simple moving-average fallback when model isn't available."""
    if not counts:
        return [0.0] * steps
    avg = float(np.mean(counts[-5:]))
    return [round(avg, 1)] * steps


# ── Endpoints ───────────────────────────────────────────────────

@app.get("/health")
def health():
    model_ready = load_model_once()
    return {
        "status": "healthy",
        "model_loaded": model_ready,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/predict/{intersection_id}")
def predict_next(intersection_id: str):
    """Predict the vehicle count for the next reading (~2 seconds ahead)."""
    counts = fetch_recent_counts(intersection_id, SEQ_LEN)

    if not load_model_once() or len(counts) < SEQ_LEN:
        # Fallback
        pred = fallback_heuristic(counts, 1)[0]
        return {
            "intersection_id": intersection_id,
            "predicted_count": pred,
            "confidence": "low",
            "method": "heuristic",
            "timestamp": datetime.now().isoformat(),
        }

    seq = np.array([_norm(c) for c in counts[-SEQ_LEN:]], dtype=float)
    seq = seq.reshape(1, SEQ_LEN, 1)
    norm_pred = float(_model.predict(seq, verbose=0)[0][0])
    pred = round(max(0, _denorm(norm_pred)), 1)

    return {
        "intersection_id": intersection_id,
        "predicted_count": pred,
        "confidence": "high",
        "method": "lstm",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/predict/{intersection_id}/horizon")
def predict_horizon(intersection_id: str, steps: int = STEPS_15_MIN):
    """
    Multi-step autoregressive forecast.
    Default: 450 steps ≈ 15 minutes (at 2s interval).
    Returns list of (timestamp, predicted_count) pairs.
    """
    steps = min(steps, 1000)   # cap to prevent abuse
    counts = fetch_recent_counts(intersection_id, SEQ_LEN)

    if not load_model_once() or len(counts) < SEQ_LEN:
        preds = fallback_heuristic(counts, steps)
        method = "heuristic"
    else:
        # Autoregressive roll-out
        window = [_norm(c) for c in counts[-SEQ_LEN:]]
        preds  = []
        for _ in range(steps):
            seq = np.array(window[-SEQ_LEN:]).reshape(1, SEQ_LEN, 1)
            nxt = float(_model.predict(seq, verbose=0)[0][0])
            preds.append(round(max(0, _denorm(nxt)), 1))
            window.append(nxt)
        method = "lstm"

    now = datetime.now()
    forecast = [
        {
            "t": (now + timedelta(seconds=i * STEP_SECONDS)).isoformat(),
            "count": p,
        }
        for i, p in enumerate(preds)
    ]

    peak_idx   = int(np.argmax(preds))
    peak_count = preds[peak_idx]
    peak_time  = (now + timedelta(seconds=peak_idx * STEP_SECONDS)).strftime("%H:%M:%S")

    return {
        "intersection_id" : intersection_id,
        "horizon_steps"   : steps,
        "horizon_minutes" : round(steps * STEP_SECONDS / 60, 1),
        "method"          : method,
        "forecast"        : forecast,
        "summary": {
            "peak_predicted_count": peak_count,
            "peak_at":              peak_time,
            "avg_predicted":        round(float(np.mean(preds)), 1),
        },
    }


@app.get("/predict/{intersection_id}/congestion")
def congestion_alert(intersection_id: str):
    """
    Returns a congestion risk level for the next 15 minutes.
    Thresholds: LOW < 15, MEDIUM < 30, HIGH >= 30 vehicles.
    """
    result  = predict_horizon(intersection_id, steps=STEPS_15_MIN)
    avg     = result["summary"]["avg_predicted"]
    peak    = result["summary"]["peak_predicted_count"]

    if peak >= 30:
        level, color = "HIGH",   "#ef4444"
    elif peak >= 15:
        level, color = "MEDIUM", "#f59e0b"
    else:
        level, color = "LOW",    "#10b981"

    return {
        "intersection_id"   : intersection_id,
        "congestion_level"  : level,
        "color"             : color,
        "peak_in_15min"     : peak,
        "avg_in_15min"      : avg,
        "recommendation"    : {
            "HIGH":   "Extend NS green phase by 15s. Consider rerouting.",
            "MEDIUM": "Monitor queue. Consider extending green by 5–10s.",
            "LOW":    "Current signal plan is sufficient.",
        }[level],
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("predict_api:app", host="0.0.0.0", port=8001, reload=True)
