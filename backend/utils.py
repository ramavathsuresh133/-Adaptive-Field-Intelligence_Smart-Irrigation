"""
utils.py — Shared Utilities & Weather API Client
=================================================
Loads API credentials from .env and provides:
  - fetch_weather()    → OpenWeatherMap current weather data
  - fetch_forecast()   → OpenWeatherMap 5-day forecast data
  - derive_uv_proxy()  → UV index estimate from cloud cover

Usage:
    from utils import fetch_weather, fetch_forecast, derive_uv_proxy
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from fastapi import HTTPException
from deep_translator import GoogleTranslator

# Load .env from the project root (one level above backend/)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
BASE_WEATHER_URL: str = "https://api.openweathermap.org/data/2.5/weather"
BASE_FORECAST_URL: str = "https://api.openweathermap.org/data/2.5/forecast"


def fetch_weather(city: str) -> dict:
    """
    Fetch current weather conditions from the OpenWeatherMap API.

    SENSOR REPLACEMENT:
        Replaces a physical weather station (thermometer, hygrometer,
        rain gauge, anemometer, pyranometer) with real-time API data.

    Args:
        city: Name of the city/location to query (e.g. "Hyderabad").

    Returns:
        Dictionary with weather metrics.
    """
    if not OPENWEATHER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENWEATHER_API_KEY is not configured.",
        )

    params = {
        "q":     city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(BASE_WEATHER_URL, params=params, timeout=10)
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"City not found: '{city}'.")
        if not response.ok:
            raise HTTPException(status_code=500, detail="Weather API error.")

        data = response.json()
        rainfall_mm: float = 0.0
        if "rain" in data and isinstance(data["rain"], dict):
            rainfall_mm = float(data["rain"].get("1h", 0.0))

        return {
            "temperature":          round(float(data["main"]["temp"]),     2),
            "humidity":             round(float(data["main"]["humidity"]), 2),
            "rainfall":             round(rainfall_mm,                     2),
            "wind_speed":           round(float(data["wind"]["speed"]),    2),
            "cloud_cover":          round(float(data["clouds"]["all"]),    2),
            "weather_description":  data["weather"][0].get("description", "clear") if data.get("weather") else "clear",
        }
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Weather API connection failed: {exc}")


def fetch_forecast(city: str) -> list[dict]:
    """
    Fetch 5-day weather forecast from OpenWeatherMap API and group by day.
    
    Args:
        city: Name of the city to query.

    Returns:
        List of 5 dicts, one per day, each containing weather metrics for ~12:00:00.
    """
    if not OPENWEATHER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENWEATHER_API_KEY is not configured.")

    params = {
        "q":     city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(BASE_FORECAST_URL, params=params, timeout=10)
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"City '{city}' not found.")
        if not response.ok:
            raise HTTPException(status_code=500, detail="Forecast API error.")

        data = response.json()
        forecast_list = data.get("list", [])
        
        # Group by date and pick the midday entry (or closest)
        daily_data = {}
        for entry in forecast_list:
            dt_txt = entry.get("dt_txt", "") # "YYYY-MM-DD HH:MM:SS"
            date_str = dt_txt.split(" ")[0]
            time_str = dt_txt.split(" ")[1]
            
            if date_str not in daily_data:
                daily_data[date_str] = {"entries": [], "rain_sum": 0.0}
            
            daily_data[date_str]["entries"].append(entry)
            
            # Accumulate rain
            if "rain" in entry and "3h" in entry["rain"]:
                daily_data[date_str]["rain_sum"] += float(entry["rain"]["3h"])

        # Process to 5 days, picking the 12:00:00 entry or the one closest to midday
        result = []
        # Sort dates to ensure ascending order
        sorted_dates = sorted(daily_data.keys())
        
        # Skip the first day if it's already past midday (OpenWeather often provides partial first day)
        # We want the next 5 full days if possible, or just the next 5 available
        for d_str in sorted_dates[:6]: # Look at first 6 to ensure we get 5 if today is partial
            day_entries = daily_data[d_str]["entries"]
            
            # Find entry closest to 12:00:00
            midday_entry = day_entries[0]
            min_diff = 24
            for e in day_entries:
                hour = int(e["dt_txt"].split(" ")[1].split(":")[0])
                diff = abs(hour - 12)
                if diff < min_diff:
                    min_diff = diff
                    midday_entry = e
            
            dt_obj = datetime.strptime(d_str, "%Y-%m-%d")
            
            result.append({
                "date":         d_str,
                "day_name":     dt_obj.strftime("%a"),
                "temp":         round(float(midday_entry["main"]["temp"]), 2),
                "humidity":     round(float(midday_entry["main"]["humidity"]), 2),
                "rainfall":     round(daily_data[d_str]["rain_sum"], 2),
                "description":  midday_entry["weather"][0]["description"] if midday_entry.get("weather") else "clear",
                "icon_code":    midday_entry["weather"][0]["icon"] if midday_entry.get("weather") else "01d",
                # Include cloud cover and wind speed for soil moisture model prediction
                "wind_speed":   round(float(midday_entry["wind"]["speed"]), 2),
                "cloud_cover":  round(float(midday_entry["clouds"]["all"]), 2)
            })

        # Return exactly 5 days (excluding today if possible, or just the first 5)
        # If we have 6, usually the first one is the remainder of today. 
        # Typically users want the outlook starting tomorrow or including today.
        # The prompt asks for "next 5 days". We'll return the first 5 records.
        return result[:5]

    except Exception as exc:
        if isinstance(exc, HTTPException): raise exc
        raise HTTPException(status_code=500, detail=f"Forecast process failed: {exc}")


def derive_uv_proxy(cloud_cover: float) -> float:
    """
    Derive a UV light intensity proxy index from cloud cover percentage.
    Formula: uv_proxy = max(0, 10 - cloud_cover × 0.08)
    """
    try:
        uv_proxy = max(0.0, 10.0 - float(cloud_cover) * 0.08)
        return round(uv_proxy, 2)
    except (TypeError, ValueError):
        return 0.0



# ── Translation System ────────────────────────────────────────────────────────
_TRANSLATIONS_PATH = Path(__file__).parent / "translations.json"
_translations: dict = {}

try:
    if _TRANSLATIONS_PATH.exists():
        with open(_TRANSLATIONS_PATH, "r", encoding="utf-8") as f:
            _translations = json.load(f)
except Exception as e:
    print(f"[utils] [ERROR] Failed to load translations: {e}")

def get_message(key: str, lang: str = "en", **kwargs) -> str:
    """
    Retrieve a translated message for a given key and language.
    Supports hybrid translation via Google Translate if key/language is missing.

    Args:
        key: The translation key (e.g., 'irrigate_yes').
        lang: Target language code (e.g., 'te', 'hi').
        **kwargs: Values to inject into template strings (e.g., amount=4.5).

    Returns:
        Translated string.
    """
    # 1. Check local translations.json
    msg_entry = _translations.get(key, {})
    message = msg_entry.get(lang)

    # 2. Fallback to English if target language missing in local file
    if not message and lang != "en":
        message = msg_entry.get("en")
        # If we have an English message, try to translate it dynamically (Hybrid)
        if message:
            try:
                message = GoogleTranslator(source='en', target=lang).translate(message)
            except Exception as e:
                print(f"[utils] [HYBRID] Translation failed for {key} to {lang}: {e}")
                # Fallback to the English version if Google Translate fails
    
    # 3. If still no message, use the key itself as a last resort
    if not message:
        message = key

    # 4. Inject template variables if present
    try:
        return message.format(**kwargs)
    except Exception:
        return message
