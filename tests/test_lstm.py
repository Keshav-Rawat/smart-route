"""
SmartRoute — LSTM Model Unit Tests
====================================
Tests model utilities: make_sequences, normalize, denormalize, build_model.
Automatically skipped if TensorFlow is not installed.

Run:  pytest tests/test_lstm.py -v
"""

import pytest
import numpy as np

# conftest already added forecasting/ to sys.path
try:
    from lstm_model import (
        make_sequences, normalize, denormalize,
        build_model, generate_synthetic_data,
        SEQ_LEN, TF_AVAILABLE,
    )
    _import_ok = True
except Exception:
    _import_ok = False
    TF_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _import_ok,
    reason="lstm_model could not be imported"
)


# ── make_sequences ────────────────────────────────────────────────

def test_make_sequences_output_shape():
    data = np.arange(100, dtype=float)
    X, y = make_sequences(data, seq_len=10)
    assert X.shape == (90, 10, 1), f"Expected (90,10,1), got {X.shape}"
    assert y.shape == (90,)


def test_make_sequences_correct_values():
    data = np.arange(20, dtype=float)
    X, y = make_sequences(data, seq_len=5)
    # First window: [0,1,2,3,4] → target 5
    np.testing.assert_array_equal(X[0, :, 0], np.arange(5))
    assert y[0] == 5.0
    # Last window: [14,15,16,17,18] → target 19
    np.testing.assert_array_equal(X[-1, :, 0], np.arange(14, 19))
    assert y[-1] == 19.0


def test_make_sequences_returns_empty_when_too_short():
    """If series shorter than seq_len, return empty arrays."""
    data = np.arange(5, dtype=float)
    X, y = make_sequences(data, seq_len=10)
    assert len(X) == 0
    assert len(y) == 0


def test_make_sequences_uses_default_seq_len():
    """Default seq_len should be SEQ_LEN from the module."""
    data = np.arange(SEQ_LEN + 10, dtype=float)
    X, y = make_sequences(data)
    assert X.shape[1] == SEQ_LEN


# ── normalize ─────────────────────────────────────────────────────

def test_normalize_output_range():
    data = np.array([0.0, 25.0, 50.0, 75.0, 100.0])
    norm, mn, mx = normalize(data)
    assert pytest.approx(float(norm.min()), abs=1e-6) == 0.0
    assert pytest.approx(float(norm.max()), abs=1e-6) == 1.0


def test_normalize_returns_min_max():
    data = np.array([10.0, 50.0, 90.0])
    _, mn, mx = normalize(data)
    assert mn == 10.0
    assert mx == 90.0


def test_normalize_constant_series_no_nan():
    """Constant series must not produce NaN (division by zero guard)."""
    data = np.full(50, 42.0)
    norm, mn, mx = normalize(data)
    assert not np.any(np.isnan(norm))
    assert mn == mx == 42.0


# ── denormalize ───────────────────────────────────────────────────

def test_denormalize_roundtrip():
    original = np.array([10.0, 40.0, 70.0, 100.0])
    norm, mn, mx = normalize(original)
    recovered = denormalize(norm, mn, mx)
    np.testing.assert_allclose(recovered, original, atol=1e-5)


def test_denormalize_zero_gives_min():
    mn, mx = 20.0, 80.0
    result = denormalize(np.array([0.0]), mn, mx)
    assert pytest.approx(float(result[0])) == 20.0


def test_denormalize_one_gives_max():
    mn, mx = 20.0, 80.0
    result = denormalize(np.array([1.0]), mn, mx)
    assert pytest.approx(float(result[0])) == 80.0


# ── generate_synthetic_data ───────────────────────────────────────

def test_synthetic_data_shape():
    data = generate_synthetic_data(n=500)
    assert len(data) == 500


def test_synthetic_data_in_valid_range():
    data = generate_synthetic_data(n=1000)
    assert float(data.min()) >= 0.0
    assert float(data.max()) <= 120.0


# ── build_model (requires TensorFlow) ────────────────────────────

@pytest.mark.skipif(not TF_AVAILABLE, reason="TensorFlow not installed")
def test_build_model_output_shape():
    model = build_model(seq_len=10, features=1)
    assert model.output_shape == (None, 1)


@pytest.mark.skipif(not TF_AVAILABLE, reason="TensorFlow not installed")
def test_build_model_contains_lstm_layers():
    model = build_model(seq_len=10, features=1)
    layer_names = [type(l).__name__ for l in model.layers]
    assert "LSTM" in layer_names
    assert "Dense" in layer_names
    assert "Dropout" in layer_names


@pytest.mark.skipif(not TF_AVAILABLE, reason="TensorFlow not installed")
def test_build_model_is_compiled():
    model = build_model(seq_len=10, features=1)
    # A compiled model has an optimizer
    assert model.optimizer is not None


@pytest.mark.skipif(not TF_AVAILABLE, reason="TensorFlow not installed")
def test_model_forward_pass():
    """Smoke test: model should accept correct input shape without errors."""
    model = build_model(seq_len=10, features=1)
    dummy_input = np.zeros((4, 10, 1), dtype=np.float32)  # batch of 4
    output = model.predict(dummy_input, verbose=0)
    assert output.shape == (4, 1)
