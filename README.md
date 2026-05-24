# Sensor-Free Adaptive Field Intelligence & Smart Irrigation System

A precision agriculture platform that **eliminates all physical sensors** by combining real-time weather data from the OpenWeatherMap API with trained machine learning models to predict what sensors would measure — delivering intelligent irrigation intelligence at zero hardware cost.

---

## 2. How Sensors Are Replaced

| Physical Sensor | Replacement Method | Module |
|---|---|---|
| Soil moisture probe | `RandomForestRegressor` trained on weather features (temp, humidity, rainfall, wind, cloud) | `env_intelligence.py` |
| Weather station (thermometer, hygrometer, rain gauge, anemometer) | OpenWeatherMap Current Weather API (real-time, live data) | `utils.py` |
| Pressure transducer | Zone-hash-seeded NumPy simulation + `IsolationForest` anomaly detection | `drip_monitor.py` |
| Flow meter | Zone-hash-seeded NumPy simulation + `IsolationForest` anomaly detection | `drip_monitor.py` |
| UV / pyranometer sensor | `derive_uv_proxy()` = `max(0, 10 - cloud_cover × 0.08)` derived from API cloud cover % | `utils.py` |
| Field inspector | Rule-based priority scoring: crop stage weight × days ÷ field condition score | `reposition_planner.py` |

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   SENSOR-FREE INTELLIGENCE STACK                 │
└──────────────────────────────────────────────────────────────────┘

  ┌─────────────────────┐
  │  OpenWeatherMap API │  ← Real-time weather (replaces all field
  │  api.openweather... │    weather instruments)
  └──────────┬──────────┘
             │  JSON: temp, humidity, rainfall, wind, cloud cover
             ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                     ML Engine (backend/)                    │
  │                                                             │
  │  ┌────────────────────────┐  ┌────────────────────────────┐ │
  │  │  soil_rf_model.pkl     │  │  drip_iso_model.pkl        │ │
  │  │  RandomForestRegressor │  │  IsolationForest           │ │
  │  │  Predicts: soil        │  │  Detects: pressure/flow    │ │
  │  │  moisture score 0-100  │  │  anomalies in drip system  │ │
  │  └────────────┬───────────┘  └──────────────┬─────────────┘ │
  │               │                              │               │
  │       env_intelligence.py             drip_monitor.py        │
  │       + reposition_planner.py         + database.py          │
  └─────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────┐
  │   FastAPI Backend  (main.py)         │
  │   localhost:8000                     │
  │                                      │
  │   GET /field-status?city=...         │
  │   GET /drip-health                   │
  │   GET /reposition-plan               │
  │   GET /dashboard-summary?city=...    │
  │   GET /history/{table}               │
  └──────────────────────┬───────────────┘
                          │  JSON responses
                          ▼
  ┌──────────────────────────────────────┐
  │   Frontend Dashboard (frontend/)     │
  │   index.html + style.css +           │
  │   dashboard.js + Chart.js            │
  │                                      │
  │   • 4 Zone Cards                     │
  │   • Summary Metrics                  │
  │   • Alert Panel                      │
  │   • Soil Moisture Chart              │
  │   • Water Requirement Chart          │
  │   • Repositioning Schedule Table     │
  └──────────────────────────────────────┘
```

---

## 4. Setup & Run

### Prerequisites
- Python 3.10 or higher
- A free [OpenWeatherMap API key](https://openweathermap.org/api)
- Modern web browser

### Step-by-Step

**Step 1 — Get the project**
```bash
# Unzip the project folder, or clone if hosted:
# git clone <repo-url>
cd "Sensor-Free Adaptive Irrigation"
```

**Step 2 — Install Python dependencies**
```bash
pip install -r requirements.txt
```

**Step 3 — Configure your API key**
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```
Open `.env` and replace `your_openweathermap_api_key_here` with your actual key:
```
OPENWEATHER_API_KEY=abc123yourkeyhere
```

**Step 4 — Train the ML models** *(run once)*
```bash
cd backend
python train_models.py
```
Expected output:
```
✓ Soil RF model — R² score: ~0.97
✓ Drip anomaly model — anomalies detected: ~225 / 1500
✓ Models saved to ../models/
```

**Step 5 — Start the API server**
```bash
# From the backend/ directory:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
if it upone not work use this :uvicorn main:app --reload --host
```
API docs available at: http://localhost:8000/docs

**Step 6 — Open the dashboard**
```
Open frontend/index.html in any web browser.
Type a city name (default: Hyderabad) and click "Refresh Data".
```

---

## 5. API Endpoint Reference

| Method | Path | Query Params | Response Shape |
|---|---|---|---|
| `GET` | `/` | — | `{status, system, sensor_mode, version, timestamp}` |
| `GET` | `/field-status` | `city` (str) | `[{city, zone, temperature, humidity, rainfall, wind_speed, cloud_cover, soil_moisture_score, et_rate, urgency, timestamp}, ...]` × 4 |
| `GET` | `/drip-health` | — | `[{zone, pressure_psi, flow_rate_lph, uniformity_pct, health_score, fault_type, recommended_action, anomaly_detected, timestamp}, ...]` × 4 |
| `GET` | `/reposition-plan` | — | `[{zone, crop_stage, priority_score, labor_hours, recommended_date, timestamp}, ...]` sorted desc |
| `GET` | `/dashboard-summary` | `city` (str) | `{field_status, drip_health, reposition_plan, city, generated_at}` |
| `GET` | `/history/{table}` | `limit` (int, 1–200) | `[row dicts]` newest first; `table` ∈ `{field_readings, drip_health, reposition_log}` |

---

## 6. ML Model Explanation

### Model 1 — Soil Moisture Predictor (`soil_rf_model.pkl`)

| Attribute | Detail |
|---|---|
| **Algorithm** | `RandomForestRegressor(n_estimators=150, random_state=42)` |
| **Why RF?** | Handles non-linear relationships between weather variables and soil moisture; robust to outliers; interpretable via feature importance |
| **Training data** | 2,000 synthetic samples generated with agronomically-grounded formula |
| **Features** | `[temperature_c, humidity_pct, rainfall_mm, wind_speed_ms, cloud_cover_pct]` |
| **Target** | `soil_moisture_score` (0–100 scale; 50 = field capacity baseline) |
| **Replaces** | Physical soil moisture probes (capacitance, TDR, or tensiometer sensors) |
| **Typical R²** | ~0.97 on held-out test set |

### Model 2 — Drip Anomaly Detector (`drip_iso_model.pkl`)

| Attribute | Detail |
|---|---|
| **Algorithm** | `IsolationForest(n_estimators=100, contamination=0.15, random_state=42)` |
| **Why IsolationForest?** | Unsupervised; ideal when anomaly labels are unavailable in real deployments; scales well; isolates anomalies via random feature splits |
| **Training data** | 1,500 synthetic samples: 85% normal operation, 15% injected faults |
| **Features** | `[pressure_psi, flow_rate_lph, uniformity_pct]` |
| **Output** | `-1` = anomaly detected, `1` = normal operation |
| **Replaces** | Pressure transducers, pulse-count flow meters, distribution uniformity field tests |

---

## 7. Problem Statement Sub-Problem Alignment

| PS-1 Sub-Problem | Solving Module | Method |
|---|---|---|
| Soil moisture monitoring without sensors | `env_intelligence.py` | RandomForestRegressor predicts from weather API |
| Real-time weather data collection | `utils.py` | OpenWeatherMap API replaces weather station |
| Irrigation system health monitoring | `drip_monitor.py` | IsolationForest on simulated telemetry |
| Optimal irrigation scheduling | `reposition_planner.py` | Rule-based priority scoring by crop stage |
| UV / solar radiation sensing | `utils.py → derive_uv_proxy()` | Cloud-cover-based mathematical derivation |
| Data persistence & history | `database.py` | SQLite stores all predictions & health logs |
| Remote monitoring interface | `frontend/` | Browser dashboard with live API polling |
| Parallel multi-zone processing | `main.py → /dashboard-summary` | `asyncio.gather` + ThreadPoolExecutor |

---

## 8. Future Roadmap

### Phase 1 — Real Sensor Integration Path
When physical sensors become available, replace simulated data sources incrementally:
- Swap `drip_monitor.py` telemetry generation with MQTT messages from real pressure/flow sensors
- Replace `fetch_weather()` for local microclimate with on-site weather station REST API
- Retrain soil moisture model with actual sensor readings to improve regional accuracy

### Phase 2 — Mobile Application
- Wrap FastAPI backend with authentication (JWT + OAuth2)
- Build React Native or Flutter mobile app consuming the same REST endpoints
- Push notifications for critical urgency alerts via Firebase Cloud Messaging

### Phase 3 — Edge Deployment
- Package backend with Docker for Raspberry Pi / Jetson Nano edge deployment
- Run IsolationForest inference locally on-device to reduce API latency
- Implement LoRaWAN gateway integration for low-power wide-area sensor mesh
- Offline-capable PWA frontend using Service Workers + IndexedDB cache

### Phase 4 — Advanced ML
- Time-series forecasting (LSTM / Prophet) for 7-day irrigation demand prediction
- Reinforcement learning agent for autonomous valve control decisions
- Transfer learning to adapt soil moisture model to new crop types / soil profiles
- Federated learning across multiple farms without sharing raw data

---

*This project is part of Smart Agriculture PS-1 — demonstrating that sensor-free intelligence is achievable through the combination of public weather APIs and trained machine learning models.*
