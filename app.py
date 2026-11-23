import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Forecast App", page_icon="⛈️", layout="wide")
st.title("⛈️ Forecast - Select a view")

# Controls
lat = st.sidebar.number_input("Latitude", min_value=-90.0, max_value=90.0, value=9.605, step=0.001, format="%.3f")
lon = st.sidebar.number_input("Longitude", min_value=-180.0, max_value=180.0, value=77.17, step=0.001, format="%.3f")
days = st.sidebar.slider("Forecast Days", min_value=1, max_value=10, value=3)
view = st.sidebar.selectbox("Choose page", ["Home", "Meteogram", "Monsoon", "Temperature"])

# Prepare output directory for workers
out_dir = Path(tempfile.gettempdir()) / "forecast_app"
out_dir.mkdir(parents=True, exist_ok=True)

PY = sys.executable
TEMPERATURE_LOCATIONS_FILE = Path(__file__).resolve().parent / "data" / "temperature_locations.json"
TEMPERATURE_MODEL_ID = "ecmwf_ifs"


@st.cache_data(show_spinner=False)
def load_temperature_locations(path):
    with Path(path).open(encoding="utf-8") as file:
        locations = json.load(file)
    if not locations:
        raise ValueError("The locations file contains no cities.")
    return locations


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_temperature_daily(locations, forecast_days, model_id):
    """Fetch daily minimum and maximum temperatures for the configured cities."""
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": ",".join(str(location["latitude"]) for location in locations),
            "longitude": ",".join(str(location["longitude"]) for location in locations),
            "daily": ["temperature_2m_min", "temperature_2m_max"],
            "models": model_id,
            "forecast_days": forecast_days,
            "timezone": "Asia/Kolkata",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    results = payload if isinstance(payload, list) else [payload]
    if len(results) != len(locations):
        raise ValueError(
            f"Expected data for {len(locations)} cities, received {len(results)}."
        )
    return results


def build_temperature_table(locations, results, table_days):
    dates = results[0].get("daily", {}).get("time", [])[:table_days]
    if not dates:
        raise ValueError("The API response did not contain daily forecast dates.")

    rows = []
    for location, result in zip(locations, results):
        daily = result.get("daily", {})
        lows = daily.get("temperature_2m_min", [])[:table_days]
        highs = daily.get("temperature_2m_max", [])[:table_days]
        if len(lows) != len(dates) or len(highs) != len(dates):
            raise ValueError(f"Incomplete temperature data for {location['name']}.")

        row = {"Region": location["name"]}
        for date, low, high in zip(dates, lows, highs):
            label = pd.to_datetime(date).strftime("%d %b")
            row[f"{label} Tmin (°C)"] = low
            row[f"{label} Tmax (°C)"] = high
        rows.append(row)

    return pd.DataFrame(rows).set_index("Region").round(1), dates


def run_worker(cmd):
    """Run a worker subprocess and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


if view == "Home":
    out_file = out_dir / "home_summary.json"
    cmd = [PY, "pages/home.py", str(lat), str(lon), str(days), str(out_file)]
    with st.spinner("Loading Home..."):
        rc, out, err = run_worker(cmd)
    if rc != 0:
        st.error("Home worker failed:\n" + err)
    else:
        st.success("Home loaded")
        try:
            text = Path(out_file).read_text()
            data = json.loads(text)
            st.json(data)
        except Exception:
            st.text(out)

elif view == "Meteogram":
    out_png = out_dir / "meteogram_preview.png"
    cmd = [PY, "pages/meteogram.py", str(lat), str(lon), str(days), str(out_png)]
    with st.spinner("Generating Meteogram... This may take a moment."):
        rc, out, err = run_worker(cmd)
    if rc != 0:
        st.error("Meteogram worker failed:\n" + err)
    else:
        if out_png.exists():
            st.image(str(out_png), caption="Meteogram", use_container_width=True)
            st.success("Meteogram generated")
        else:
            st.warning("Meteogram script completed but output PNG not found. stdout:\n" + out)

elif view == "Monsoon":
    out_file = out_dir / "monsoon_summary.txt"
    cmd = [PY, "pages/monsoon.py", str(lat), str(lon), str(days), str(out_file)]
    with st.spinner("Running Monsoon analysis..."):
        rc, out, err = run_worker(cmd)
    if rc != 0:
        st.error("Monsoon worker failed:\n" + err)
    else:
        st.success("Monsoon analysis completed")
        try:
            st.text(Path(out_file).read_text())
        except Exception:
            st.text(out)

elif view == "Temperature":
    st.header("🌡️ Temperature")
    st.caption(
        "Daily ECMWF IFS minimum and maximum temperature forecast for configured cities."
    )

    try:
        locations = load_temperature_locations(str(TEMPERATURE_LOCATIONS_FILE))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        st.error(f"Could not load city coordinates from `{TEMPERATURE_LOCATIONS_FILE}`: {exc}")
        st.stop()

    table_days = st.selectbox(
        "Number of forecast days",
        options=range(1, 8),
        index=5,
        format_func=lambda forecast_days: f"{forecast_days} days",
    )

    if st.button("Fetch / refresh temperature table", type="primary"):
        try:
            with st.spinner("Fetching the temperature forecast..."):
                results = fetch_temperature_daily(
                    tuple(locations), 7, TEMPERATURE_MODEL_ID
                )
                table, dates = build_temperature_table(locations, results, table_days)
            st.session_state["temperature_table"] = table
            st.session_state["temperature_dates"] = dates
        except (requests.RequestException, ValueError, KeyError) as exc:
            st.error(f"Could not build the temperature table: {exc}")

    temperature_table = st.session_state.get("temperature_table")
    temperature_dates = st.session_state.get("temperature_dates")
    if temperature_table is not None and temperature_dates:
        st.dataframe(temperature_table, use_container_width=True)
        first_date = pd.to_datetime(temperature_dates[0])
        st.caption(
            f"Temperature Pattern, Week {first_date.isocalendar().week} "
            f"(Basis {first_date.strftime('%A, %d %B')})"
        )
        st.download_button(
            label="Download CSV",
            data=temperature_table.to_csv(index=True).encode("utf-8"),
            file_name=f"temp_pattern_week{first_date.isocalendar().week}.csv",
            mime="text/csv",
        )
    else:
        st.info("Select the forecast length and fetch the table to get started.")
