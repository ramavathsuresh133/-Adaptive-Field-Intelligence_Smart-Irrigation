"""
train_models.py — Model Training Script
========================================
Trains and saves two machine learning models:
  1. RandomForestRegressor → Replaces physical soil moisture sensors
  2. IsolationForest        → Replaces pressure/flow sensors for anomaly detection

Run this script once before starting the FastAPI backend.
Usage: cd backend && python train_models.py
"""

import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

# Resolve models directory relative to this script
MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def train_soil_moisture_model() -> None:
    """
    Train MODEL 1: Soil Moisture Predictor (RandomForestRegressor)

    SENSOR REPLACEMENT:
        Physical soil moisture probes → ML model predicts soil moisture
        from weather API inputs (temperature, humidity, rainfall, wind, clouds).

    Dataset: 2000 synthetic rows generated using agronomic domain knowledge.
    Features: [temperature_c, humidity_pct, rainfall_mm, wind_speed_ms, cloud_cover_pct]
    Target:   soil_moisture_score (0–100 scale)
    """
    print("\n" + "=" * 55)
    print("  Training MODEL 1: Soil Moisture Predictor")
    print("  Sensor replaced: Physical soil moisture probe")
    print("=" * 55)

    np.random.seed(42)
    n_samples = 2000

    # Generate realistic weather feature distributions
    temperature_c     = np.random.uniform(10.0, 45.0, n_samples)
    humidity_pct      = np.random.uniform(20.0, 100.0, n_samples)
    rainfall_mm       = np.random.exponential(scale=3.5, size=n_samples).clip(0, 50)
    wind_speed_ms     = np.random.uniform(0.0, 15.0, n_samples)
    cloud_cover_pct   = np.random.uniform(0.0, 100.0, n_samples)

    # Agronomically-grounded target formula
    base = np.full(n_samples, 50.0)
    base += humidity_pct    * 0.25
    base -= temperature_c   * 0.35
    base += rainfall_mm     * 1.8
    base -= wind_speed_ms   * 0.5
    base += cloud_cover_pct * 0.05
    base += np.random.normal(0, 3, n_samples)
    soil_moisture_score = np.clip(base, 5, 98)

    X = np.column_stack([
        temperature_c,
        humidity_pct,
        rainfall_mm,
        wind_speed_ms,
        cloud_cover_pct,
    ])
    y = soil_moisture_score

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    print(f"  ✓ Training complete — R² score on test set: {r2:.4f}")

    save_path = MODELS_DIR / "soil_rf_model.pkl"
    joblib.dump(model, save_path)
    print(f"  ✓ Model saved → {save_path}")


def train_drip_anomaly_model() -> None:
    """
    Train MODEL 2: Drip System Anomaly Detector (IsolationForest)

    SENSOR REPLACEMENT:
        Pressure transducers + flow meters → IsolationForest detects
        anomalies in simulated telemetry [pressure_psi, flow_rate_lph, uniformity_pct].

    Dataset: 1500 synthetic rows (85% normal, 15% injected anomalies).
    """
    print("\n" + "=" * 55)
    print("  Training MODEL 2: Drip System Anomaly Detector")
    print("  Sensors replaced: Pressure & flow sensors")
    print("=" * 55)

    np.random.seed(123)
    n_total    = 1500
    n_normal   = int(n_total * 0.85)   # 1275 normal samples
    n_anomaly  = n_total - n_normal    # 225 anomaly samples

    # ── Normal operating ranges ──────────────────────────────────────────────
    pressure_normal     = np.random.uniform(18.0, 42.0, n_normal)
    flow_normal         = np.random.uniform(2.0,   8.5, n_normal)
    uniformity_normal   = np.random.uniform(72.0, 98.0, n_normal)

    # ── Anomaly ranges — deliberately outside spec ───────────────────────────
    half_anom = n_anomaly // 2

    # Pressure anomalies: too low (clog) or too high (surge)
    pressure_low  = np.random.uniform(1.0,  10.0, half_anom)
    pressure_high = np.random.uniform(50.0, 70.0, n_anomaly - half_anom)
    pressure_anom = np.concatenate([pressure_low, pressure_high])

    # Flow anomalies: too low (restriction) or too high (pipe burst)
    flow_low  = np.random.uniform(0.1,  1.2, half_anom)
    flow_high = np.random.uniform(10.0, 15.0, n_anomaly - half_anom)
    flow_anom = np.concatenate([flow_low, flow_high])

    # Uniformity anomalies: emitter blockage
    uniformity_anom = np.random.uniform(20.0, 55.0, n_anomaly)

    # ── Combine datasets ─────────────────────────────────────────────────────
    pressure_all    = np.concatenate([pressure_normal,   pressure_anom])
    flow_all        = np.concatenate([flow_normal,       flow_anom])
    uniformity_all  = np.concatenate([uniformity_normal, uniformity_anom])

    X = np.column_stack([pressure_all, flow_all, uniformity_all])

    # Shuffle to prevent ordering bias
    shuffle_idx = np.random.permutation(n_total)
    X = X[shuffle_idx]

    model = IsolationForest(
        n_estimators=100,
        contamination=0.15,
        random_state=42
    )
    model.fit(X)

    predictions   = model.predict(X)
    n_detected    = np.sum(predictions == -1)
    detection_pct = (n_detected / n_total) * 100

    print(f"  ✓ Training complete")
    print(f"  ✓ Anomalies detected on training data: {n_detected} / {n_total} ({detection_pct:.1f}%)")

    save_path = MODELS_DIR / "drip_iso_model.pkl"
    joblib.dump(model, save_path)
    print(f"  ✓ Model saved → {save_path}")


def main() -> None:
    """Entry point — trains both models sequentially."""
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   Sensor-Free Adaptive Irrigation — Model Training  ║")
    print("╚══════════════════════════════════════════════════════╝")

    try:
        train_soil_moisture_model()
    except Exception as exc:
        print(f"\n  ✗ Error training soil moisture model: {exc}")
        raise

    try:
        train_drip_anomaly_model()
    except Exception as exc:
        print(f"\n  ✗ Error training drip anomaly model: {exc}")
        raise

    print("\n" + "=" * 55)
    print("  ✓ All models trained and saved successfully!")
    print(f"  ✓ Models directory: {MODELS_DIR.resolve()}")
    print("  ✓ Ready to start backend: uvicorn main:app --reload")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
