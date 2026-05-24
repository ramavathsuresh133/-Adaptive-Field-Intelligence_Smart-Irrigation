"""
main.py — FastAPI Application Entry Point
==========================================
Adaptive Field Intelligence & Smart Irrigation System
Sensor-Free Mode: all field data derived from OpenWeatherMap API + ML models.
"""

import asyncio
import io
import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from database import (
    init_db, get_history, create_alert, get_active_alerts, 
    resolve_alert, save_forecast_event, _get_connection
)
from env_intelligence import get_field_status, soil_model
from drip_monitor import check_drip_health
from reposition_planner import get_reposition_plan
from utils import fetch_forecast, fetch_weather, get_message

import numpy as np

# ── Application instance ──────────────────────────────────────────────────────
app = FastAPI(
    title="Adaptive Field Intelligence & Smart Irrigation System",
    description="Sensor-free precision agriculture platform.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # Changed from True to avoid issues with some browsers & wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

ZONES: list[str] = ["North", "South", "East", "West"]
_executor = ThreadPoolExecutor(max_workers=15)

@app.on_event("startup")
async def startup_event() -> None:
    init_db()

# ═══════════════════════════════════════════════════════════════════════════════
# Existing Routes (Modified for Feature 3: Alerts)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["System"])
async def health_check():
    return {"status": "ok", "sensor_mode": "sensor-free", "version": "1.1.0"}

@app.get("/field-status", tags=["Field Intelligence"])
async def field_status_endpoint(city: str = "Hyderabad", lang: str = "en"):
    loop = asyncio.get_event_loop()
    
    async def fetch_and_alert(zone: str):
        res = await loop.run_in_executor(_executor, get_field_status, city, zone)
        # FEATURE 3 Logic:
        sm = res["soil_moisture_score"]
        if sm < 30:
            msg = get_message("alert_low_moisture", lang, zone=zone)
            create_alert(zone, "LOW_MOISTURE", msg, "critical")
        elif sm < 40:
            msg = get_message("alert_moisture_warning", lang, zone=zone)
            create_alert(zone, "MOISTURE_WARNING", msg, "warning")
        res["urgency"] = get_message(f"urgency_{res['urgency']}", lang)
        res["weather_description"] = get_message(res["weather_description"], lang)
        return res

    results = await asyncio.gather(*[fetch_and_alert(z) for z in ZONES])
    return list(results)

@app.get("/drip-health", tags=["Drip Monitoring"])
async def drip_health_endpoint(lang: str = "en"):
    loop = asyncio.get_event_loop()
    
    async def check_and_alert(zone: str):
        res = await loop.run_in_executor(_executor, check_drip_health, zone)
        # FEATURE 3 Logic:
        health = res["health_score"]
        fault = res["fault_type"]
        if health < 70:
            msg = get_message("alert_drip_fault", lang, zone=zone, fault=fault)
            create_alert(zone, "DRIP_FAULT", msg, "critical")
        elif health < 85:
            msg = get_message("alert_drip_warning", lang, zone=zone)
            create_alert(zone, "DRIP_WARNING", msg, "warning")
        return res

    results = await asyncio.gather(*[check_and_alert(z) for z in ZONES])
    return list(results)

@app.get("/reposition-plan", tags=["Repositioning"])
async def reposition_plan_endpoint():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_reposition_plan)

@app.get("/dashboard-summary", tags=["Dashboard"])
async def dashboard_summary_endpoint(city: str = "Hyderabad", lang: str = "en"):
    field_status, drip_health, reposition_plan = await asyncio.gather(
        field_status_endpoint(city, lang),
        drip_health_endpoint(lang),
        reposition_plan_endpoint(),
    )
    return {
        "field_status": field_status,
        "drip_health": drip_health,
        "reposition_plan": reposition_plan,
        "city": city,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 1: Weather Forecast
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/forecast", tags=["Feature 1"])
async def get_forecast_endpoint(city: str = "Hyderabad"):
    try:
        forecast = fetch_forecast(city)
        # Predict soil moisture for each day
        for day in forecast:
            # Features: [temperature, humidity, rainfall, wind_speed, cloud_cover]
            features = np.array([[day["temp"], day["humidity"], day["rainfall"], day["wind_speed"], day["cloud_cover"]]])
            pred = float(soil_model.predict(features)[0])
            day["predicted_soil_moisture"] = round(max(5.0, min(98.0, pred)), 1)
        
        save_forecast_event(city, forecast)
        return forecast
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 2 & 5: Crop Recommendation & Water Savings
# ═══════════════════════════════════════════════════════════════════════════════

CROP_WATER_NEEDS = {
    "Rice":       {"base_litres": 8.0, "optimal_soil_moisture": 70, "drought_sensitive": True},
    "Wheat":      {"base_litres": 4.5, "optimal_soil_moisture": 55, "drought_sensitive": False},
    "Maize":      {"base_litres": 5.5, "optimal_soil_moisture": 60, "drought_sensitive": True},
    "Sugarcane":  {"base_litres": 9.0, "optimal_soil_moisture": 75, "drought_sensitive": True},
    "Cotton":     {"base_litres": 5.0, "optimal_soil_moisture": 50, "drought_sensitive": False},
    "Vegetables": {"base_litres": 6.0, "optimal_soil_moisture": 65, "drought_sensitive": True}
}

@app.get("/crop-recommendation", tags=["Feature 2"])
async def crop_recommendation(city: str, crop: str, lang: str = "en"):
    if crop not in CROP_WATER_NEEDS:
        raise HTTPException(status_code=400, detail="Unsupported crop")
    
    weather = fetch_weather(city)
    features = np.array([[weather["temperature"], weather["humidity"], weather["rainfall"], weather["wind_speed"], weather["cloud_cover"]]])
    soil_moisture = round(max(5.0, min(98.0, float(soil_model.predict(features)[0]))), 1)
    
    profile = CROP_WATER_NEEDS[crop]
    optimal = profile["optimal_soil_moisture"]
    deficit = max(0, optimal - soil_moisture)
    
    # Smart Logic: If moisture is adequate, zero water needed.
    if soil_moisture >= optimal:
        adjusted = 0.0
    else:
        # Increase water use proportional to moisture deficit
        adjusted = profile["base_litres"] * (1 + deficit / 100)
    if weather["rainfall"] > 3:
        adjusted = max(0, adjusted - (weather["rainfall"] * 0.3))
    adjusted = round(adjusted, 2)
    
    if soil_moisture >= optimal:
        text = get_message("rec_adequate", lang, crop=crop)
    elif deficit < 15:
        text = get_message("rec_slight_deficit", lang, amount=adjusted)
    elif deficit < 30:
        text = get_message("rec_moderate_deficit", lang, amount=adjusted)
    else:
        text = get_message("rec_critical_deficit", lang, crop=crop, amount=adjusted)
        
    return {
        "city": city, "crop": crop, "soil_moisture_score": soil_moisture,
        "optimal_soil_moisture": optimal, "adjusted_water_litres": adjusted,
        "recommendation_text": text, "weather": weather,
        "irrigate_now": deficit > 10
    }

@app.get("/water-savings", tags=["Feature 5"])
async def water_savings(city: str, area_hectares: float = 1.0, crop: str = "Rice", lang: str = "en"):
    rec = await crop_recommendation(city, crop, lang)
    base = CROP_WATER_NEEDS[crop]["base_litres"]
    
    # Area in m2 = hectares * 10000
    m2 = area_hectares * 10000
    # Traditional systems are typically ~40-50% less efficient than smart systems
    traditional_water = (base * 1.5) * m2
    smart_water = rec["adjusted_water_litres"] * m2
    
    savings_litres = max(0, traditional_water - smart_water)
    savings_percent = round((savings_litres / traditional_water) * 100, 1) if traditional_water > 0 else 0
    cost_saved_inr = round(savings_litres * 0.004, 2)
    
    return {
        "traditional_water": round(traditional_water, 2),
        "smart_water": round(smart_water, 2),
        "savings_litres": round(savings_litres, 2),
        "savings_percent": savings_percent,
        "cost_saved_inr": cost_saved_inr,
        "area_hectares": area_hectares,
        "crop": crop,
        "city": city
    }

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 3: Alerts System Routes
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/alerts", tags=["Feature 3"])
async def get_alerts():
    return get_active_alerts()

@app.post("/alerts/{alert_id}/resolve", tags=["Feature 3"])
async def resolve_alert_route(alert_id: int):
    resolve_alert(alert_id)
    return {"success": True, "alert_id": alert_id}

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 4: Irrigation History Chart
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/history-chart", tags=["Feature 4"])
async def history_chart(days: int = 7):
    conn = _get_connection()
    cursor = conn.cursor()
    
    date_limit = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Get overall average per day
    cursor.execute("""
        SELECT date(timestamp) as dt, avg(soil_moisture_score) as avg_sm
        FROM field_readings
        WHERE timestamp >= ?
        GROUP BY dt ORDER BY dt ASC
    """, (date_limit,))
    avg_rows = cursor.fetchall()
    
    dates = [r["dt"] for r in avg_rows]
    avg_vals = [round(r["avg_sm"], 1) for r in avg_rows]
    
    # Get per-zone values
    zones_data = {z: [] for z in ZONES}
    for date in dates:
        for zone in ZONES:
            cursor.execute("""
                SELECT avg(soil_moisture_score) as val FROM field_readings
                WHERE date(timestamp) = ? AND zone = ?
            """, (date, zone))
            val = cursor.fetchone()["val"]
            zones_data[zone].append(round(val, 1) if val else None)
            
    conn.close()
    return {"dates": dates, "avg_moisture": avg_vals, "zones": zones_data}

# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 6: Export CSV & Text Report
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/export/csv", tags=["Feature 6"])
async def export_csv(table: str):
    if table not in ["field_readings", "drip_health", "reposition_log"]:
        raise HTTPException(status_code=400, detail="Invalid table")
    
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No data found")
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows([dict(r) for r in rows])
    
    now = datetime.now().strftime("%Y%m%d_%H%M")
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}_{now}.csv"}
    )

@app.get("/export/report", tags=["Feature 6"])
async def export_report(city: str = "Hyderabad"):
    summary = await dashboard_summary_endpoint(city)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    report = [
        f"ADAPTIVE FIELD INTELLIGENCE REPORT — {city.upper()}",
        f"Generated: {date_str}",
        "=" * 50,
        "\nSECTION 1: ZONE STATUS",
        "-" * 25
    ]
    for z in summary["field_status"]:
        report.append(f"• {z['zone']}: Soil Moisture {z['soil_moisture_score']}/100 | Urgency: {z['urgency'].upper()}")
        
    report.append("\nSECTION 2: DRIP HEALTH SUMMARY")
    report.append("-" * 25)
    for d in summary["drip_health"]:
        report.append(f"• {d['zone']}: Health {d['health_score']}/100 | Fault: {d['fault_type']}")
        
    report.append("\nSECTION 3: REPOSITIONING SCHEDULE")
    report.append("-" * 25)
    for p in summary["reposition_plan"][:4]:
        report.append(f"• {p['zone']}: Priority {p['priority_score']} | Recommended: {p['recommended_date']}")
        
    report.append("\nSECTION 4: SYSTEM RECOMMENDATIONS")
    report.append("-" * 25)
    # Simple logic for overall recommendation
    avg_sm = sum(z["soil_moisture_score"] for z in summary["field_status"]) / 4
    if avg_sm < 40:
        report.append("CRITICAL: Overall field moisture is low. Immediate irrigation sweep advised.")
    else:
        report.append("Status: All parameters within acceptable agricultural ranges.")
        
    report_text = "\n".join(report)
    now = datetime.now().strftime("%Y%m%d_%H%M")
    
    return Response(
        content=report_text,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=irrigation_report_{now}.txt"}
    )
