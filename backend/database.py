"""
database.py — SQLite Database Layer
=====================================
Manages all persistent storage for the Adaptive Irrigation System.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

# Database file lives alongside the backend scripts
DB_PATH = Path(__file__).parent / "adaptive_irrigation.db"


def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create all database tables if they do not already exist.
    Called once at FastAPI application startup.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # ── Table 1: field_readings ───────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS field_readings (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                city                TEXT NOT NULL,
                zone                TEXT NOT NULL,
                temperature         REAL,
                humidity            REAL,
                rainfall            REAL,
                wind_speed          REAL,
                cloud_cover         REAL,
                soil_moisture_score REAL,
                et_rate             REAL,
                urgency             TEXT,
                timestamp           TEXT NOT NULL
            )
        """)

        # ── Table 2: drip_health ──────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drip_health (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                zone                TEXT NOT NULL,
                pressure_psi        REAL,
                flow_rate_lph       REAL,
                uniformity_pct      REAL,
                health_score        REAL,
                fault_type          TEXT,
                recommended_action  TEXT,
                timestamp           TEXT NOT NULL
            )
        """)

        # ── Table 3: reposition_log ───────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reposition_log (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                zone                    TEXT NOT NULL,
                crop_stage              TEXT,
                days_since_irrigation   INTEGER,
                field_condition_score   REAL,
                priority_score          REAL,
                labor_hours             REAL,
                recommended_date        TEXT,
                timestamp               TEXT NOT NULL
            )
        """)

        # ── Table 4: alerts (NEW) ────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                zone        TEXT NOT NULL,
                alert_type  TEXT NOT NULL,
                message     TEXT NOT NULL,
                severity    TEXT NOT NULL, -- critical, warning, info
                resolved    INTEGER DEFAULT 0,
                timestamp   TEXT NOT NULL
            )
        """)

        # ── Table 5: forecast_cache (NEW) ────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecast_cache (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                city            TEXT NOT NULL,
                forecast_json   TEXT NOT NULL,
                timestamp       TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()
        print(f"[database] [OK] Database initialised at: {DB_PATH}")

    except Exception as exc:
        print(f"[database] [ERROR] Failed to initialise database: {exc}")
        raise


def save_field_reading(data: dict) -> None:
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO field_readings
                (city, zone, temperature, humidity, rainfall, wind_speed,
                 cloud_cover, soil_moisture_score, et_rate, urgency, timestamp)
            VALUES
                (:city, :zone, :temperature, :humidity, :rainfall, :wind_speed,
                 :cloud_cover, :soil_moisture_score, :et_rate, :urgency, :timestamp)
        """, data)
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[database] [ERROR] save_field_reading failed: {exc}")


def save_drip_health(data: dict) -> None:
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO drip_health
                (zone, pressure_psi, flow_rate_lph, uniformity_pct,
                 health_score, fault_type, recommended_action, timestamp)
            VALUES
                (:zone, :pressure_psi, :flow_rate_lph, :uniformity_pct,
                 :health_score, :fault_type, :recommended_action, :timestamp)
        """, data)
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[database] [ERROR] save_drip_health failed: {exc}")


def save_reposition(data: dict) -> None:
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reposition_log
                (zone, crop_stage, days_since_irrigation, field_condition_score,
                 priority_score, labor_hours, recommended_date, timestamp)
            VALUES
                (:zone, :crop_stage, :days_since_irrigation, :field_condition_score,
                 :priority_score, :labor_hours, :recommended_date, :timestamp)
        """, data)
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[database] [ERROR] save_reposition failed: {exc}")


def get_history(table: str, limit: int = 20) -> list[dict]:
    VALID_TABLES = {"field_readings", "drip_health", "reposition_log"}
    if table not in VALID_TABLES: return []
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception: return []


# ── Alert Functions (NEW) ────────────────────────────────────────────────────

def create_alert(zone: str, alert_type: str, message: str, severity: str) -> None:
    """Auto-create a new system alert."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor.execute("""
            INSERT INTO alerts (zone, alert_type, message, severity, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (zone, alert_type, message, severity, timestamp))
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[database] [ERROR] create_alert failed: {exc}")


def get_active_alerts() -> list[dict]:
    """Retrieve all unresolved alerts, newest first."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE resolved = 0 ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception: return []


def resolve_alert(alert_id: int) -> None:
    """Mark a specific alert as resolved."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[database] [ERROR] resolve_alert failed: {exc}")


# ── Forecast Cache Functions (NEW) ───────────────────────────────────────────

def save_forecast_event(city: str, forecast_data: list) -> None:
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor.execute("""
            INSERT INTO forecast_cache (city, forecast_json, timestamp)
            VALUES (?, ?, ?)
        """, (city, json.dumps(forecast_data), timestamp))
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[database] [ERROR] save_forecast_event failed: {exc}")
