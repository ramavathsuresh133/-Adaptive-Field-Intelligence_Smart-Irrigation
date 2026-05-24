"""
reposition_planner.py — Smart Equipment Repositioning Planner
==============================================================
SENSOR REPLACEMENT:
    Physical field inspector     → Rule-based priority scoring from crop stage,
                                   days since last irrigation, and field condition.
    Manual scheduling            → Algorithmic priority sorting + date recommendation.

This module uses agronomic rules and weighted crop-stage coefficients to
determine which irrigation zones need equipment repositioning most urgently,
replacing the need for a field technician to manually assess each zone.

Usage:
    from reposition_planner import get_reposition_plan
"""

from datetime import datetime, timedelta, timezone
from database import save_reposition

# ── Crop-stage irrigation demand weights ─────────────────────────────────────
# Higher weight = greater water demand at that crop development stage.
# Values are grounded in FAO-56 crop coefficient (Kc) relative demand patterns.
CROP_STAGE_WEIGHTS: dict[str, float] = {
    "seedling":   2.2,   # High vulnerability — establishment phase
    "vegetative": 1.6,   # Moderate demand — foliage growth
    "flowering":  2.8,   # Critical peak — water stress causes yield loss
    "fruiting":   2.4,   # High demand — fruit fill and sizing
    "maturity":   1.0,   # Low demand — crop drying / ripening
}

# ── Default 4-zone field configuration ───────────────────────────────────────
# In a sensor-equipped system these values would come from IoT telemetry.
# Here they represent agronomist-assessed field status (replicable from records).
_DEFAULT_FIELD_CONFIG: list[dict] = [
    {
        "zone":                   "North",
        "crop_stage":             "flowering",
        "days_since_irrigation":  4,
        "field_condition_score":  62.0,  # 0–100; higher = better condition
        "area_hectares":          2.5,
    },
    {
        "zone":                   "South",
        "crop_stage":             "vegetative",
        "days_since_irrigation":  2,
        "field_condition_score":  75.0,
        "area_hectares":          1.8,
    },
    {
        "zone":                   "East",
        "crop_stage":             "seedling",
        "days_since_irrigation":  6,
        "field_condition_score":  45.0,
        "area_hectares":          3.1,
    },
    {
        "zone":                   "West",
        "crop_stage":             "maturity",
        "days_since_irrigation":  8,
        "field_condition_score":  88.0,
        "area_hectares":          2.0,
    },
]


def get_reposition_plan(
    field_config: list[dict] | None = None
) -> list[dict]:
    """
    Compute an equipment repositioning schedule for all irrigation zones.

    SENSOR REPLACEMENT:
        Replaces manual field inspector assessment with algorithmic priority
        scoring. The priority score integrates:
            - Crop water demand (crop stage weight)
            - Time since last irrigation (days elapsed)
            - Current field condition (normalised score)

    Priority formula:
        priority_score = (crop_stage_weight × days_since_irrigation)
                         ÷ (field_condition_score ÷ 100)

    A lower field_condition_score (poor field state) or a critical crop stage
    combined with many days without irrigation yields a higher priority score,
    triggering earlier repositioning dates.

    Labor formula:
        labor_hours = 0.4 + area_hectares × 0.35
        (0.4 h base overhead + 0.35 h per hectare)

    Date logic:
        priority > 15 → Today (immediate action)
        priority > 8  → Tomorrow
        else          → 3 days from today

    Args:
        field_config: Optional list of zone dicts; uses default 4-zone config
                      if None. Each dict must contain:
                          zone, crop_stage, days_since_irrigation,
                          field_condition_score, area_hectares

    Returns:
        List of zone repositioning dicts, sorted by priority_score descending.

    Raises:
        KeyError: If a zone's crop_stage is not in CROP_STAGE_WEIGHTS.
        ZeroDivisionError: If field_condition_score is 0 (guarded internally).
    """
    zones = field_config if field_config is not None else _DEFAULT_FIELD_CONFIG
    today = datetime.now(timezone.utc).date()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    results: list[dict] = []

    for zone_info in zones:
        try:
            zone:                  str   = zone_info["zone"]
            crop_stage:            str   = zone_info["crop_stage"]
            days_since_irrigation: int   = int(zone_info["days_since_irrigation"])
            field_condition_score: float = float(zone_info["field_condition_score"])
            area_hectares:         float = float(zone_info["area_hectares"])

            stage_weight: float = CROP_STAGE_WEIGHTS.get(crop_stage.lower(), 1.5)

            # Guard against division by zero (degenerate field condition value)
            safe_condition = max(field_condition_score, 0.1)

            priority_score: float = round(
                (stage_weight * days_since_irrigation) / (safe_condition / 100.0),
                2,
            )

            labor_hours: float = round(0.4 + area_hectares * 0.35, 1)

            # Determine repositioning date offset by urgency
            if priority_score > 15:
                offset_days = 0
            elif priority_score > 8:
                offset_days = 1
            else:
                offset_days = 3

            recommended_date: str = (
                today + timedelta(days=offset_days)
            ).strftime("%Y-%m-%d")

            record: dict = {
                "zone":                   zone,
                "crop_stage":             crop_stage,
                "days_since_irrigation":  days_since_irrigation,
                "field_condition_score":  field_condition_score,
                "area_hectares":          area_hectares,
                "stage_weight":           stage_weight,
                "priority_score":         priority_score,
                "labor_hours":            labor_hours,
                "recommended_date":       recommended_date,
                "timestamp":              timestamp,
            }

            # Persist to reposition_log table
            try:
                save_reposition(record)
            except Exception as db_exc:
                print(f"[reposition_planner] ✗ DB write failed for zone {zone}: {db_exc}")

            results.append(record)

        except KeyError as exc:
            print(f"[reposition_planner] ✗ Missing key in zone config: {exc}")
        except Exception as exc:
            print(f"[reposition_planner] ✗ Error processing zone {zone_info.get('zone', '?')}: {exc}")

    # Sort by priority_score descending (highest urgency first)
    results.sort(key=lambda z: z["priority_score"], reverse=True)
    return results
