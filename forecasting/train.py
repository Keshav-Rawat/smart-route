"""
SmartRoute — LSTM Training Script
===================================
Fetches historical traffic data from the backend and trains
the LSTM model. Falls back to synthetic data if backend is offline.

Usage:
  python train.py
  python train.py --synthetic      # force synthetic data
  python train.py --epochs 50
"""

import argparse
import json
import os
import numpy as np
import requests

# pyrefly: ignore [missing-import]
from lstm_model import (
    build_model, make_sequences, normalize, denormalize,
    generate_synthetic_data, MODEL_PATH, SEQ_LEN
)

BACKEND_URL     = os.getenv("BACKEND_URL", "http://localhost:8000")
INTERSECTION_ID = os.getenv("INTERSECTION_ID", "intersection_1")


def fetch_history_from_backend() -> list[float]:
    """Pull traffic history from the FastAPI backend."""
    try:
        url = f"{BACKEND_URL}/traffic/{INTERSECTION_ID}/history"
        r   = requests.get(url, timeout=5)
        r.raise_for_status()
        history = r.json().get("history", [])
        counts  = [h["count"] for h in history if "count" in h]
        print(f"  ✓ Fetched {len(counts)} readings from backend")
        return counts
    except Exception as e:
        print(f"  ⚠  Backend unavailable ({e}). Using synthetic data.")
        return []


def load_simulation_results() -> list[float]:
    """Load queue totals from adaptive_controller's JSON output."""
    sim_json = os.path.join(
        os.path.dirname(__file__), "..", "simulation", "results.json"
    )
    try:
        with open(sim_json) as f:
            data = json.load(f)
        # Use the fixed-time queue history as training signal
        counts = data.get("fixed", {}).get("q_total", [])
        print(f"  ✓ Loaded {len(counts)} steps from simulation results.json")
        return [float(c) for c in counts]
    except Exception as e:
        print(f"  ⚠  Could not load simulation results ({e}).")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true",
                        help="Force use of synthetic training data")
    parser.add_argument("--epochs",   type=int, default=30)
    parser.add_argument("--batch",    type=int, default=32)
    args = parser.parse_args()

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  SmartRoute — LSTM Traffic Forecasting — Training")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # ── 1. Gather data ─────────────────────────────────────────
    raw = []
    if not args.synthetic:
        raw = fetch_history_from_backend()
        if len(raw) < SEQ_LEN + 10:
            raw = load_simulation_results()

    if len(raw) < SEQ_LEN + 10:
        print("  → Generating synthetic traffic data (2000 steps)…")
        raw = generate_synthetic_data(2000).tolist()

    series = np.array(raw, dtype=float)
    print(f"  Data points : {len(series)}")
    print(f"  Range       : [{series.min():.1f}, {series.max():.1f}]")
    print(f"  Mean        : {series.mean():.1f}\n")

    # ── 2. Normalise & create sequences ────────────────────────
    norm_series, mn, mx = normalize(series)
    X, y = make_sequences(norm_series, SEQ_LEN)

    split    = int(0.8 * len(X))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    print(f"  Train samples : {len(X_train)}")
    print(f"  Val   samples : {len(X_val)}\n")

    # Save normalisation params alongside the model
    np.save("norm_params.npy", np.array([mn, mx]))

    # ── 3. Build & train ───────────────────────────────────────
    try:
        # pyrefly: ignore [missing-import]
        import tensorflow as tf
    except ImportError:
        print("  ✗ TensorFlow not installed.")
        print("    Run: pip install tensorflow")
        return

    model = build_model(SEQ_LEN)
    model.summary()
    print()

    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ModelCheckpoint(MODEL_PATH, save_best_only=True, verbose=0),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=4, verbose=1),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch,
        callbacks=callbacks,
        verbose=1,
    )

    # ── 4. Evaluate ────────────────────────────────────────────
    val_pred  = model.predict(X_val, verbose=0).flatten()
    val_true  = y_val

    pred_real = denormalize(val_pred, mn, mx)
    true_real = denormalize(val_true, mn, mx)
    mae       = np.mean(np.abs(pred_real - true_real))
    rmse      = np.sqrt(np.mean((pred_real - true_real) ** 2))

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Validation MAE  : {mae:.2f} vehicles")
    print(f"  Validation RMSE : {rmse:.2f} vehicles")
    print(f"  Model saved to  : {MODEL_PATH}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


if __name__ == "__main__":
    main()
