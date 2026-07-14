#!/usr/bin/env python3
"""
pages/monsoon.py
Lightweight CLI worker for the "Monsoon" view. Performs monsoon-specific analysis.

Usage:
    python pages/monsoon.py <lat> <lon> <days> <out_file>
"""
import sys
import json
import requests
from pathlib import Path


def fetch_monsoon_analysis(lat, lon, days):
    """
    Fetch monsoon-specific weather data and perform basic analysis.
    """
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "forecast_days": days,
        "hourly": ["precipitation", "relative_humidity_2m", "wind_speed_10m"],
        "timezone": "auto",
    }
    
    try:
        r = requests.get(base_url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        
        if "hourly" not in j:
            raise RuntimeError("No hourly data in API response")
        
        times = j["hourly"].get("time", [])
        precip = j["hourly"].get("precipitation", [])
        humidity = j["hourly"].get("relative_humidity_2m", [])
        wind = j["hourly"].get("wind_speed_10m", [])
        
        analysis = {
            "lat": lat,
            "lon": lon,
            "days": days,
            "data_points": len(times),
            "total_precipitation_mm": sum(precip) if precip else 0,
            "max_precipitation_hourly_mm": max(precip) if precip else 0,
            "avg_humidity_percent": sum(humidity) / len(humidity) if humidity else 0,
            "avg_wind_speed_kmh": sum(wind) / len(wind) if wind else 0,
            "monsoon_status": "Analysis complete",
            "first_time": times[0] if times else None,
            "last_time": times[-1] if times else None,
        }
        
        return analysis
    
    except Exception as e:
        raise RuntimeError(f"Failed to fetch monsoon analysis: {e}")


def main(argv):
    if len(argv) < 5:
        print("Usage: python pages/monsoon.py <lat> <lon> <days> <out_file>")
        return 2
    
    try:
        lat = float(argv[1])
        lon = float(argv[2])
        days = int(argv[3])
        out_path = Path(argv[4])
    except (ValueError, IndexError) as e:
        print(f"ERROR: Invalid arguments: {e}", file=sys.stderr)
        return 2
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        analysis = fetch_monsoon_analysis(lat, lon, days)
    except Exception as e:
        print(f"ERROR: Monsoon analysis failed: {e}", file=sys.stderr)
        return 3
    
    out_path.write_text(json.dumps(analysis, indent=2))
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
