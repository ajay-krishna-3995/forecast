#!/usr/bin/env python3
"""
pages/home.py
Lightweight CLI worker for the "Home" view. Fetches a small subset of forecast data and
writes a JSON summary to the provided output path.

Usage:
    python pages/home.py <lat> <lon> <days> <out_json>

This script intentionally keeps dependencies minimal (only requests and stdlib).
"""
import sys
import requests
import json
from pathlib import Path


def fetch_summary(lat, lon, days):
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "forecast_days": days,
        "hourly": ["temperature_2m", "precipitation"],
        "timezone": "auto",
    }
    r = requests.get(base_url, params=params)
    r.raise_for_status()
    j = r.json()
    if "hourly" not in j:
        raise RuntimeError("No hourly data in API response")

    times = j["hourly"].get("time", [])
    temps = j["hourly"].get("temperature_2m", [])
    prec = j["hourly"].get("precipitation", [])

    summary = {
        "lat": lat,
        "lon": lon,
        "days": days,
        "data_points": len(times),
        "temperature_mean": None,
        "temperature_min": None,
        "temperature_max": None,
        "precip_total": None,
        "first_time": times[0] if times else None,
        "last_time": times[-1] if times else None,
    }

    if temps:
        summary["temperature_mean"] = sum(temps) / len(temps)
        summary["temperature_min"] = min(temps)
        summary["temperature_max"] = max(temps)
    if prec:
        try:
            summary["precip_total"] = sum(prec)
        except Exception:
            summary["precip_total"] = None

    return summary


def main(argv):
    if len(argv) < 5:
        print("Usage: python pages/home.py <lat> <lon> <days> <out_json>")
        return 2

    lat = float(argv[1])
    lon = float(argv[2])
    days = int(argv[3])
    out_path = Path(argv[4])

    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        summary = fetch_summary(lat, lon, days)
    except Exception as e:
        print(f"ERROR: Failed to fetch summary: {e}", file=sys.stderr)
        return 3

    out_path.write_text(json.dumps(summary, indent=2))
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
