"""
SmartRoute — LSTM Traffic Forecasting Model
============================================
Predicts vehicle counts 15 minutes ahead using a stacked LSTM
trained on historical traffic readings from the backend.

Architecture:
  Input  → sequence of last N readings (vehicle_count)
  LSTM 1 → 64 units, return_sequences=True
  LSTM 2 → 32 units
  Dense  → 1 (next count prediction)

Usage:
  python train.py       # train from backend history
  python predict_api.py # serve predictions on :8001
"""

import numpy as np

try:
    # pyrefly: ignore [missing-import]
    import tensorflow as tf
    # pyrefly: ignore [missing-import]
    from tensorflow.keras.models import Sequential, load_model
    # pyrefly: ignore [missing-import]
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
    # pyrefly: ignore [missing-import]
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False


SEQ_LEN    = 20      # use last 20 readings as context
PRED_STEPS = 1       # predict 1 step ahead (≈ 2s interval → ~15min = 450 steps)
MODEL_PATH = "lstm_traffic_model.h5"


def build_model(seq_len: int = SEQ_LEN, features: int = 1) -> "tf.keras.Model":
    """
    Stacked LSTM for univariate time-series forecasting.
    """
    if not TF_AVAILABLE:
        raise RuntimeError("TensorFlow not installed. Run: pip install tensorflow")

    model = Sequential([
        Input(shape=(seq_len, features)),
        LSTM(64, return_sequences=True),
        Dropout(0.2),
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        Dense(16, activation="relu"),
        Dense(PRED_STEPS),
    ], name="SmartRoute_LSTM")

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
        metrics=["mae"],
    )
    return model


def make_sequences(series: np.ndarray, seq_len: int = SEQ_LEN):
    """
    Slide a window over the series to create (X, y) pairs.
    X shape: (samples, seq_len, 1)
    y shape: (samples,)
    """
    X, y = [], []
    for i in range(len(series) - seq_len):
        X.append(series[i : i + seq_len])
        y.append(series[i + seq_len])
    return np.array(X)[..., np.newaxis], np.array(y)


def normalize(series: np.ndarray):
    """Min-max normalise to [0, 1]. Returns (norm_series, min, max)."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return np.zeros_like(series, dtype=float), mn, mx
    return (series - mn) / (mx - mn), mn, mx


def denormalize(values: np.ndarray, mn: float, mx: float) -> np.ndarray:
    return values * (mx - mn) + mn


def generate_synthetic_data(n: int = 2000) -> np.ndarray:
    """
    Generate synthetic traffic data for demo / cold-start training.
    Simulates a realistic daily pattern: rush hours at 8am and 5pm.
    """
    t = np.linspace(0, 4 * np.pi, n)
    base = (
        30 * np.sin(t * 0.8) +          # slow wave
        15 * np.sin(t * 3.0 + 1.0) +    # rush-hour bumps
        10 * np.random.randn(n)          # noise
    )
    return np.clip(base + 40, 0, 120).astype(float)


if __name__ == "__main__":
    model = build_model()
    model.summary()
    print("\nModel built successfully. Run train.py to train on real data.")
