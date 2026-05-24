"""
env_intelligence.py — Field Environment Intelligence
=====================================================
SENSOR REPLACEMENT:
    Soil moisture sensor → RandomForestRegressor predicted from weather inputs
    ET (evapotranspiration) rate → simplified Hargreaves formula from API data

This module fetches live weather data and uses the trained ML model to produce
a complete field status report for a given city and irrigation zone.

Usage:
    from env_intelligence import get_field_status
"""

import joblib
import numpy as np
from pathlib import Path
from datetime import datetime, timezone

from utils import fetch_weather, derive_uv_proxy
from database import save_field_reading

# ── Load model at module import (avoids reloading on every API call) ─────────
_MODEL_PATH = Path(__file__).parent.parent / "models" / "soil_rf_model.pkl"

try:
    soil_model = joblib.load(_MODEL_PATH)
    print(f"[env_intelligence] [OK] Soil RF model loaded from: {_MODEL_PATH}")
except FileNotFoundError:
    soil_model = None
    print(
        f"[env_intelligence] [ERROR] Model not found at {_MODEL_PATH}. "
        "Run: cd backend && python train_models.py"
    )
except Exception as exc:
    soil_model = None
    print(f"[env_intelligence] [ERROR] Failed to load soil model: {exc}")


def get_field_status(city: str, zone: str) -> dict:
    """
    Produce a complete field intelligence report for a single irrigation zone.

    SENSOR REPLACEMENTS:
        • Soil moisture probe   → RandomForestRegressor prediction from weather
        • Weather station       → OpenWeatherMap real-time API
        • UV / sunlight sensor  → derive_uv_proxy() from cloud cover %
        • ET calculation        → Hargreaves-simplified formula

    Pipeline:
        1. Fetch live weather data for the given city
        2. Derive UV proxy from cloud cover
        3. Predict soil moisture using RandomForest
        4. Calculate Evapotranspiration rate
        5. Classify irrigation urgency
        6. Persist result to database

    Args:
        city: City name used to query OpenWeatherMap (e.g. "Hyderabad").
        zone: Irrigation zone label (e.g. "North", "South", "East", "West").

    Returns:
        Dictionary with full field status including weather, prediction,
        ET rate, urgency level, and ISO timestamp.

    Raises:
        HTTPException: Propagated from fetch_weather() on API errors.
        RuntimeError: If the ML model was not loaded successfully.
    """
    if soil_model is None:
        raise RuntimeError(
            "Soil moisture model is not loaded. "
            "Run 'python train_models.py' to generate the model file."
        )

    # ── Step 1: Live weather from OpenWeatherMap API ─────────────────────────
    weather = fetch_weather(city)
    temperature:  float = weather["temperature"]
    humidity:     float = weather["humidity"]
    rainfall:     float = weather["rainfall"]
    wind_speed:   float = weather["wind_speed"]
    cloud_cover:  float = weather["cloud_cover"]
    description:  str   = weather["weather_description"]

    # ── Step 2: Derive UV proxy (replaces physical UV sensor) ─────────────────
    uv_proxy: float = derive_uv_proxy(cloud_cover)

    # ── Step 3: Predict soil moisture (replaces physical soil probe) ──────────
    feature_array = np.array([[temperature, humidity, rainfall, wind_speed, cloud_cover]])
    raw_prediction: float = float(soil_model.predict(feature_array)[0])
    soil_moisture_score: float = round(max(5.0, min(98.0, raw_prediction)), 1)

    # ── Step 4: Estimate Evapotranspiration via Hargreaves formula ───────────
    # Simplified Hargreaves-Samani ET₀ derived from available weather variables
    # et_rate approximates litres/m²/hour lost through transpiration + evaporation
    et_rate: float = round(
        0.0023
        * (temperature + 17.8)
        * (humidity ** 0.5)
        * max(wind_speed, 0.5),
        2,
    )

    # ── Step 5: Classify irrigation urgency ──────────────────────────────────
    if soil_moisture_score < 20 or et_rate > 7.0:
        urgency = "critical"
    elif soil_moisture_score < 38 or et_rate > 5.0:
        urgency = "high"
    elif soil_moisture_score < 55:
        urgency = "medium"
    else:
        urgency = "low"

    # ── Step 6: Build result dictionary ──────────────────────────────────────
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result: dict = {
        # Identity
        "city":                 city,
        "zone":                 zone,
        # Weather (from OpenWeatherMap API — replaces physical weather station)
        "temperature":          temperature,
        "humidity":             humidity,
        "rainfall":             rainfall,
        "wind_speed":           wind_speed,
        "cloud_cover":          cloud_cover,
        "weather_description":  description,
        # Derived sensor replacements
        "uv_proxy":             uv_proxy,
        "soil_moisture_score":  soil_moisture_score,   # ML predicted
        "et_rate":              et_rate,               # Hargreaves derived
        # Intelligence outputs
        "urgency":              urgency,
        "timestamp":            timestamp,
        # Metadata
        "sensor_mode":          "sensor-free-ml-predicted",
    }

    # ── Step 7: Persist to database ───────────────────────────────────────────
    try:
        save_field_reading(result)
    except Exception as exc:
        # Log but don't raise — reading was successful, DB write is non-critical
        print(f"[env_intelligence] [ERROR] DB write failed for zone {zone}: {exc}")

    return result
