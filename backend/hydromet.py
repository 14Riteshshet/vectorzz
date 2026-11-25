"""
SookshmaJal – Hydro-meteorological module.
Fetches data from Open-Meteo (free, no API key) and computes:
  • FAO-56 Penman-Monteith Reference ET₀ (mm/day)
  • 7-day cumulative precipitation
  • 0–7 cm volumetric soil moisture (%)
  • V_surv: minimum survival water volume (litres) for the plot
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# ── FAO-56 constants ───────────────────────────────────────────────────────────
STEFAN_BOLTZMANN = 4.903e-9  # MJ m⁻² K⁻⁴ day⁻¹
PSYCHROMETRIC_CONST = 0.067   # kPa °C⁻¹ (γ at sea level ~300 m)
ALBEDO = 0.23                  # reference crop albedo
# Crop coefficients (Kc) for common Tumakuru crops – simplified mid-season values
CROP_KC: dict[str, float] = {
    "ragi": 1.05,
    "finger millet": 1.05,
    "tomato": 1.15,
    "groundnut": 1.10,
    "sunflower": 1.10,
    "maize": 1.20,
    "sorghum": 1.05,
    "cotton": 1.20,
    "rice": 1.20,
    "default": 1.00,
}


def _get_kc(crop_type: str) -> float:
    return CROP_KC.get(crop_type.lower(), CROP_KC["default"])


# ── Open-Meteo fetch ───────────────────────────────────────────────────────────

def fetch_open_meteo(lat: float, lon: float) -> dict:
    """
    Fetch 7-day hourly data from Open-Meteo required for FAO-56 ET₀.
    Returns raw JSON response.
    """
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=7)).isoformat()
    end = today.isoformat()

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "windspeed_10m_max",
            "shortwave_radiation_sum",
            "relative_humidity_2m_max",
            "relative_humidity_2m_min",
        ],
        "hourly": ["soil_moisture_0_to_7cm"],
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── FAO-56 Penman-Monteith ET₀ ─────────────────────────────────────────────────

def _saturation_vapor_pressure(temp_c: float) -> float:
    """e°(T) in kPa."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def _actual_vapor_pressure(rh_max: float, rh_min: float, t_max: float, t_min: float) -> float:
    """ea in kPa using RH mean method."""
    ea = (
        _saturation_vapor_pressure(t_min) * (rh_max / 100.0)
        + _saturation_vapor_pressure(t_max) * (rh_min / 100.0)
    ) / 2.0
    return ea


def _slope_svp_curve(temp_mean: float) -> float:
    """Δ (slope of SVP curve) in kPa °C⁻¹."""
    return (4098.0 * _saturation_vapor_pressure(temp_mean)) / ((temp_mean + 237.3) ** 2)


def _net_radiation(
    rs_mj_m2: float,
    t_max_k: float,
    t_min_k: float,
    ea: float,
    rh_mean: float,
) -> float:
    """
    Net radiation Rn (MJ m⁻² day⁻¹) using FAO-56 simplified formula.
    Rs is incoming shortwave (MJ m⁻² day⁻¹).
    """
    rns = (1.0 - ALBEDO) * rs_mj_m2  # net shortwave
    # Net longwave: simplified (uses actual vapor pressure)
    rnl = (
        STEFAN_BOLTZMANN
        * ((t_max_k**4 + t_min_k**4) / 2.0)
        * (0.34 - 0.14 * math.sqrt(max(ea, 0.001)))
        * (1.35 * min(rs_mj_m2 / max(0.75 * rs_mj_m2, 0.01), 1.0) - 0.35)
    )
    return rns - rnl


def fao56_et0(
    t_max: float,
    t_min: float,
    rh_max: float,
    rh_min: float,
    wind_speed_m_s: float,
    rs_mj_m2: float,
    elevation_m: float = 820.0,  # Tumakuru ~820 m MSL
) -> float:
    """
    FAO-56 Penman-Monteith Reference ET₀ (mm day⁻¹).
    wind_speed converted from 10 m to 2 m using log law.
    """
    t_mean = (t_max + t_min) / 2.0
    t_max_k = t_max + 273.16
    t_min_k = t_min + 273.16

    # Wind speed at 2 m
    u2 = wind_speed_m_s * (4.87 / math.log(67.8 * 10.0 - 5.42))

    es_max = _saturation_vapor_pressure(t_max)
    es_min = _saturation_vapor_pressure(t_min)
    es = (es_max + es_min) / 2.0
    ea = _actual_vapor_pressure(rh_max, rh_min, t_max, t_min)

    delta = _slope_svp_curve(t_mean)
    # Psychrometric constant adjusted for elevation
    gamma = 0.000665 * (101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26)

    rn = _net_radiation(rs_mj_m2, t_max_k, t_min_k, ea, (rh_max + rh_min) / 2.0)
    g = 0.0  # soil heat flux ≈ 0 on daily basis

    numerator = (0.408 * delta * (rn - g)) + (gamma * (900.0 / (t_mean + 273.0)) * u2 * (es - ea))
    denominator = delta + gamma * (1.0 + 0.34 * u2)

    et0 = numerator / max(denominator, 0.001)
    return max(round(et0, 3), 0.0)


# ── Survival litres V_surv ─────────────────────────────────────────────────────

def survival_litres(
    et0_mm_day: float,
    area_acres: float,
    crop_type: str,
    days: int = 7,
    precip_mm: float = 0.0,
    efficiency: float = 0.70,
) -> float:
    """
    V_surv = max(0, (Kc × ET₀ × days - precip_mm) × area_m² / efficiency) in litres.

    Parameters
    ----------
    et0_mm_day  : FAO-56 ET₀ in mm/day
    area_acres  : plot area
    crop_type   : for Kc lookup
    days        : planning horizon (default 7 days)
    precip_mm   : expected/observed precipitation over `days`
    efficiency  : irrigation efficiency (0–1)
    """
    kc = _get_kc(crop_type)
    etc_mm = kc * et0_mm_day * days            # crop ET over horizon (mm)
    deficit_mm = max(0.0, etc_mm - precip_mm)  # mm deficit
    area_m2 = area_acres * 4046.856            # 1 acre = 4046.856 m²
    volume_m3 = (deficit_mm / 1000.0) * area_m2 / efficiency
    volume_litres = volume_m3 * 1000.0
    return round(volume_litres, 1)


# ── Main hydro-met entry point ─────────────────────────────────────────────────

def get_hydromet_data(lat: float, lon: float, area_acres: float, crop_type: str) -> dict:
    """
    Fetch Open-Meteo data and compute FAO-56 ET₀, precip, soil moisture,
    and survival litres. Returns a dict with all hydromet fields.
    Falls back to Tumakuru climatological averages if API fails.
    """
    try:
        raw = fetch_open_meteo(lat, lon)
        daily = raw.get("daily", {})

        # Average last 7 days
        t_max_list = daily.get("temperature_2m_max", [35.0])
        t_min_list = daily.get("temperature_2m_min", [22.0])
        rh_max_list = daily.get("relative_humidity_2m_max", [65.0])
        rh_min_list = daily.get("relative_humidity_2m_min", [30.0])
        wind_list = daily.get("windspeed_10m_max", [3.0])
        rs_list = daily.get("shortwave_radiation_sum", [22.0])
        precip_list = daily.get("precipitation_sum", [0.0])

        def _avg(lst, default):
            vals = [v for v in lst if v is not None]
            return sum(vals) / len(vals) if vals else default

        t_max = _avg(t_max_list, 35.0)
        t_min = _avg(t_min_list, 22.0)
        rh_max = _avg(rh_max_list, 65.0)
        rh_min = _avg(rh_min_list, 30.0)
        wind_speed_ms = _avg(wind_list, 3.0) / 3.6  # km/h → m/s
        rs_mj_m2 = _avg(rs_list, 22.0)
        precip_7day = sum(v for v in precip_list if v is not None)

        et0 = fao56_et0(t_max, t_min, rh_max, rh_min, wind_speed_ms, rs_mj_m2)

        # Soil moisture: average last 48 hourly values of 0–7 cm
        hourly_sm = raw.get("hourly", {}).get("soil_moisture_0_to_7cm", [])
        valid_sm = [v for v in hourly_sm[-48:] if v is not None]
        soil_moisture = round(sum(valid_sm) / len(valid_sm) * 100.0, 2) if valid_sm else 18.0

        v_surv = survival_litres(et0, area_acres, crop_type, precip_mm=precip_7day)
        deficit = round(max(0.0, et0 - precip_7day / 7.0), 3)

        return {
            "et0_mm_day": et0,
            "precipitation_mm": round(precip_7day, 2),
            "soil_moisture_0_7cm_pct": min(soil_moisture, 100.0),
            "survival_liters": v_surv,
            "deficit_mm": deficit,
            "open_meteo_timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "open_meteo",
        }

    except Exception as exc:
        logger.warning("Open-Meteo fetch failed (%s). Using Tumakuru climatological defaults.", exc)
        # Tumakuru post-monsoon October climatological defaults
        et0 = 4.8  # mm/day typical
        precip = 12.0  # mm/7-day typical dry spell
        soil_m = 22.0  # % typical
        return {
            "et0_mm_day": et0,
            "precipitation_mm": precip,
            "soil_moisture_0_7cm_pct": soil_m,
            "survival_liters": survival_litres(et0, area_acres, crop_type, precip_mm=precip),
            "deficit_mm": round(max(0.0, et0 - precip / 7.0), 3),
            "open_meteo_timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "climatological_fallback",
        }
