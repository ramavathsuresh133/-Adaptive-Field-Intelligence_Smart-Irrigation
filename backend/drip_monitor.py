"""
drip_monitor.py — Drip System Health Monitor
=============================================
SENSOR REPLACEMENT:
    Physical pressure transducers → simulated telemetry seeded by zone hash
    Physical flow meters          → simulated telemetry seeded by zone hash
    Field inspection              → IsolationForest anomaly detection model

This module simulates realistic drip irrigation telemetry and applies
the trained IsolationForest model to detect operational anomalies.
Zone-seeded simulation ensures reproducible, zone-specific results
without requiring any physical hardware.

Usage:
    from drip_monitor import check_drip_health
"""

import joblib
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

from database import save_drip_health

# ── Load IsolationForest model at module import ───────────────────────────────
_MODEL_PATH = Path(__file__).parent.parent / "models" / "drip_iso_model.pkl"

try:
    _drip_model = joblib.load(_MODEL_PATH)
    print(f"[drip_monitor] [OK] Drip anomaly model loaded from: {_MODEL_PATH}")
except FileNotFoundError:
    _drip_model = None
    print(
        f"[drip_monitor] [ERROR] Model not found at {_MODEL_PATH}. "
        "Run: cd backend && python train_models.py"
    )
except Exception as exc:
    _drip_model = None
    print(f"[drip_monitor] [ERROR] Failed to load drip model: {exc}")


# ── Fault → Action mapping ────────────────────────────────────────────────────
_FAULT_ACTION_MAP: dict[str, str] = {
    "clogging suspected — low pressure": (
        "Flush mainline filters immediately. Inspect and clean emitter inlets. "
        "Check for sediment build-up in supply lines."
    ),
    "pressure surge — check regulator": (
        "Reduce inlet pressure at main valve. Inspect pressure regulator for "
        "wear or malfunction. Check for water hammer events."
    ),
    "supply restriction — low flow": (
        "Inspect supply pipe for kinks, partial closures, or blockages. "
        "Verify pump pressure output and check valve positions."
    ),
    "emitter blockage — uneven distribution": (
        "Carry out emitter flushing using clean water. Replace blocked emitters "
        "and perform uniformity test after servicing."
    ),
    "unknown anomaly — inspect system": (
        "Schedule technician site visit within 4 hours. Document pressure and "
        "flow readings at each zone manifold for diagnosis."
    ),
    "none": "System operating normally. Next scheduled check in 24 hours.",
}


def _zone_seed(zone: str) -> int:
    """
    Convert a zone name string to a deterministic integer seed.

    Using a hash-based seed means the same zone always produces the same
    simulated readings within a session, making results comparable across
    multiple API calls without introducing random drift.

    Args:
        zone: Zone label string (e.g. "North").

    Returns:
        Non-negative integer seed derived from zone name hash.
    """
    return abs(hash(zone)) % (2 ** 31)


def check_drip_health(zone: str) -> dict:
    """
    Simulate drip system telemetry and classify operational health.

    SENSOR REPLACEMENT:
        • Pressure transducers → simulated pressure_psi (zone-seeded numpy RNG)
        • Flow meters          → simulated flow_rate_lph (zone-seeded numpy RNG)
        • Uniformity sensors   → simulated uniformity_pct (zone-seeded numpy RNG)
        • Field inspection     → IsolationForest anomaly classification

    Pipeline:
        1. Seed numpy RNG with zone hash for reproducible simulation
        2. Generate realistic telemetry values within normal operating ranges
        3. Run IsolationForest predict on the telemetry vector
        4. Classify fault type based on out-of-spec readings (if anomaly)
        5. Calculate health score
        6. Map fault to recommended maintenance action
        7. Persist result and return full dict

    Args:
        zone: Irrigation zone label (e.g. "North", "South", "East", "West").

    Returns:
        Dictionary with zone, simulated telemetry, health score, fault type,
        recommended action, and timestamp.

    Raises:
        RuntimeError: If the anomaly detection model was not loaded.
    """
    if _drip_model is None:
        raise RuntimeError(
            "Drip anomaly model is not loaded. "
            "Run 'python train_models.py' to generate the model file."
        )

    # ── Step 1: Seed RNG with zone hash (reproducible per zone) ──────────────
    rng = np.random.default_rng(seed=_zone_seed(zone))

    # ── Step 2: Simulate realistic drip telemetry ─────────────────────────────
    # Ranges chosen to match normal irrigation infrastructure specifications.
    # SENSOR REPLACEMENT: these values are synthesised; in production they would
    # come from physical pressure transducers and pulse-count flow meters.
    pressure_psi:   float = round(float(rng.uniform(15.0, 45.0)), 2)
    flow_rate_lph:  float = round(float(rng.uniform(1.5,  10.0)), 2)
    uniformity_pct: float = round(float(rng.uniform(60.0, 99.0)), 1)

    # ── Step 3: Anomaly detection via IsolationForest ─────────────────────────
    telemetry_vector = np.array([[pressure_psi, flow_rate_lph, uniformity_pct]])
    prediction: int = int(_drip_model.predict(telemetry_vector)[0])
    # prediction == -1 → anomaly detected
    # prediction ==  1 → normal operation

    # ── Step 4 & 5: Classify fault and compute health score ───────────────────
    if prediction == -1:
        # ── ANOMALY PATH ──────────────────────────────────────────────────────
        # Determine fault category from out-of-spec reading(s)
        if pressure_psi < 12:
            fault_type = "clogging suspected — low pressure"
        elif pressure_psi > 48:
            fault_type = "pressure surge — check regulator"
        elif flow_rate_lph < 1.8:
            fault_type = "supply restriction — low flow"
        elif uniformity_pct < 62:
            fault_type = "emitter blockage — uneven distribution"
        else:
            fault_type = "unknown anomaly — inspect system"

        # Health score penalises both pressure deviation and non-uniformity
        pressure_deviation  = abs(pressure_psi - 30.0) * 1.5
        uniformity_penalty  = (100.0 - uniformity_pct) * 0.8
        health_score: float = max(
            10.0,
            round(100.0 - pressure_deviation - uniformity_penalty, 1)
        )

    else:
        # ── NORMAL OPERATION PATH ─────────────────────────────────────────────
        fault_type   = "none"
        # Health score is anchored to distribution uniformity when system is OK
        health_score = round(min(100.0, 70.0 + uniformity_pct * 0.3), 1)

    # ── Step 6: Map fault to actionable maintenance recommendation ────────────
    recommended_action: str = _FAULT_ACTION_MAP.get(
        fault_type,
        "System operating normally. Next scheduled check in 24 hours.",
    )

    # ── Step 7: Build result ──────────────────────────────────────────────────
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result: dict = {
        "zone":               zone,
        "pressure_psi":       pressure_psi,
        "flow_rate_lph":      flow_rate_lph,
        "uniformity_pct":     uniformity_pct,
        "health_score":       health_score,
        "fault_type":         fault_type,
        "recommended_action": recommended_action,
        "anomaly_detected":   prediction == -1,
        "timestamp":          timestamp,
        "sensor_mode":        "sensor-free-ml-simulated",
    }

    # ── Persist to database ───────────────────────────────────────────────────
    try:
        save_drip_health(result)
    except Exception as exc:
        print(f"[drip_monitor] [ERROR] DB write failed for zone {zone}: {exc}")

    return result
