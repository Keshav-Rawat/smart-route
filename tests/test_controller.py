"""
SmartRoute — Adaptive Controller Unit Tests
============================================
Tests the signal phase decision logic WITHOUT running SUMO.
traci is replaced with a MagicMock before import.

Run:  pytest tests/test_controller.py -v
"""

import sys
import pytest
from unittest.mock import MagicMock

# ── Mock SUMO/traci BEFORE importing the module ───────────────────
_mock_traci = MagicMock()
sys.modules["traci"] = _mock_traci
sys.modules["requests"] = MagicMock()

# Also mock SUMO_HOME so the env-check doesn't call sys.exit()
import os
os.environ.setdefault("SUMO_HOME", "/usr/share/sumo")

# conftest already added simulation/ to sys.path
from adaptive_controller import (  # noqa: E402
    AdaptiveSignalController,
    MIN_GREEN_TIME,
    MAX_GREEN_TIME,
    YELLOW_TIME,
)


# ── Fixture ───────────────────────────────────────────────────────
@pytest.fixture
def ctrl():
    """Fresh controller for every test."""
    c = AdaptiveSignalController()
    c.phase_start_time = 0
    return c


# ── Helpers ───────────────────────────────────────────────────────
def counts(ns=0, ew=0):
    return {"ns_total": ns, "ew_total": ew, "total": ns + ew}


# ── Phase stability ───────────────────────────────────────────────

def test_stays_in_phase_before_min_green(ctrl):
    """Before MIN_GREEN_TIME, phase must not change even with heavy EW queue."""
    ctrl.current_phase = 0
    phase = ctrl.decide_phase(counts(ns=0, ew=20), MIN_GREEN_TIME - 1)
    assert phase == 0, "Should not switch before MIN_GREEN_TIME"


def test_stays_if_queue_diff_is_small(ctrl):
    """Does NOT switch when EW - NS <= 3 (threshold)."""
    ctrl.current_phase = 0
    phase = ctrl.decide_phase(counts(ns=5, ew=7), MIN_GREEN_TIME + 5)
    assert phase == 0


# ── NS → EW transition ────────────────────────────────────────────

def test_ns_green_switches_to_yellow_when_ew_heavy(ctrl):
    """EW queue > NS + 3 after MIN_GREEN_TIME triggers yellow."""
    ctrl.current_phase = 0
    phase = ctrl.decide_phase(counts(ns=2, ew=10), MIN_GREEN_TIME + 1)
    assert phase == 1, "Should move to NS yellow"


def test_force_yellow_at_max_green_time(ctrl):
    """Phase 0 must become yellow at MAX_GREEN_TIME regardless of queue."""
    ctrl.current_phase = 0
    phase = ctrl.decide_phase(counts(ns=15, ew=0), MAX_GREEN_TIME + 1)
    assert phase == 1


# ── Yellow → Green transitions ────────────────────────────────────

def test_ns_yellow_advances_to_ew_green(ctrl):
    """After YELLOW_TIME in phase 1, should move to phase 2 (EW green)."""
    ctrl.current_phase = 1
    phase = ctrl.decide_phase(counts(), YELLOW_TIME + 0.1)
    assert phase == 2


def test_ew_yellow_wraps_back_to_ns_green(ctrl):
    """After YELLOW_TIME in phase 3, should wrap to phase 0 (NS green)."""
    ctrl.current_phase = 3
    phase = ctrl.decide_phase(counts(), YELLOW_TIME + 0.1)
    assert phase == 0


def test_yellow_does_not_advance_before_yellow_time(ctrl):
    """Yellow phase must hold until YELLOW_TIME elapses."""
    ctrl.current_phase = 1
    phase = ctrl.decide_phase(counts(), YELLOW_TIME - 0.5)
    assert phase == 1


# ── EW phase ─────────────────────────────────────────────────────

def test_ew_green_switches_to_yellow_when_ns_heavy(ctrl):
    """Phase 2 (EW green) should yellow when NS > EW + 3."""
    ctrl.current_phase = 2
    phase = ctrl.decide_phase(counts(ns=12, ew=2), MIN_GREEN_TIME + 1)
    assert phase == 3


def test_ew_green_stays_when_ew_balanced(ctrl):
    """Phase 2 should not switch if NS ≤ EW + 3."""
    ctrl.current_phase = 2
    phase = ctrl.decide_phase(counts(ns=4, ew=4), MIN_GREEN_TIME + 1)
    assert phase == 2


# ── Full cycle ────────────────────────────────────────────────────

def test_full_four_phase_cycle(ctrl):
    """
    Simulate a complete cycle:
    0 (NS green) → 1 (NS yellow) → 2 (EW green) → 3 (EW yellow) → 0
    """
    ew_heavy = counts(ns=0, ew=10)
    ns_heavy = counts(ns=10, ew=0)

    # Phase 0 → 1: EW heavy after min time
    ctrl.current_phase = 0; ctrl.phase_start_time = 0
    p = ctrl.decide_phase(ew_heavy, MIN_GREEN_TIME + 1)
    assert p == 1

    # Phase 1 → 2: yellow done
    ctrl.phase_start_time = 0
    p = ctrl.decide_phase(ew_heavy, YELLOW_TIME + 1)
    assert p == 2

    # Phase 2 → 3: NS heavy after min time
    ctrl.phase_start_time = 0
    p = ctrl.decide_phase(ns_heavy, MIN_GREEN_TIME + 1)
    assert p == 3

    # Phase 3 → 0: yellow done
    ctrl.phase_start_time = 0
    p = ctrl.decide_phase(ns_heavy, YELLOW_TIME + 1)
    assert p == 0


# ── Stats tracking ────────────────────────────────────────────────

def test_decisions_made_counter_increments(ctrl):
    """decisions_made should increment on every phase change."""
    before = ctrl.stats["decisions_made"]

    ctrl.current_phase = 0; ctrl.phase_start_time = 0
    ctrl.decide_phase(counts(ns=0, ew=10), MIN_GREEN_TIME + 1)
    after = ctrl.stats["decisions_made"]

    assert after == before + 1
