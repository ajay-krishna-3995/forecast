import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


MODEL_ID = "ecmwf_ifs"
LOCATIONS_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "temperature_locations.json"
)


@st.cache_data(show_spinner=False)
def load_locations():
    with LOCATIONS_FILE.open(encoding="utf-8") as file:
        locations = json.load(file)

    if not locations:
        raise ValueError("The locations file contains no cities.")

    return locations


@st.cache_data(ttl=30 * 60, show_spinner=False)
def fetch_daily(locations, days, model_id):
    """Fetch daily minimum and maximum temperatures for all configured cities."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": ",".join(str(location["latitude"]) for location in locations),
        "longitude": ",".join(str(location["longitude"]) for location in locations),
        "daily": ["temperature_2m_min", "temperature_2m_max"],
        "models": model_id,
        "forecast_days": days,
        "timezone": "Asia/Kolkata",
    }

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    # Open-Meteo returns a list for multi-location requests.
    results = payload if isinstance(payload, list) else [payload]

    if len(results) != len(locations):
        raise ValueError(
            f"Expected data for {len(locations)} cities, received {len(results)}."
        )

    return results


def build_table(locations, results, table_days):
    first_daily = results[0].get("daily", {})
    dates = first_daily.get("time", [])[:table_days]

    if not dates:
        raise ValueError("The API response did not contain daily forecast dates.")

    rows = []
    for location, result in zip(locations, results):
        daily = result.get("daily", {})
        tmin = daily.get("temperature_2m_min", [])[:table_days]
        tmax = daily.get("temperature_2m_max", [])[:table_days]

        if len(tmin) != len(dates) or len(tmax) != len(dates):
            raise ValueError(f"Incomplete temperature data for {location['name']}.")

        row = {"Region": location["name"]}
        for date, low, high in zip(dates, tmin, tmax):
            label = pd.to_datetime(date).strftime("%d %b")
            row[f"{label} Tmin (°C)"] = low
            row[f"{label} Tmax (°C)"] = high
        rows.append(row)

    return pd.DataFrame(rows).set_index("Region").round(1), dates


st.title("🌡️ Temperature")
st.caption(
    "Daily ECMWF IFS minimum and maximum temperature forecast for configured cities."
)

try:
    locations = load_locations()
except (OSError, json.JSONDecodeError, ValueError) as exc:
    st.error(f"Could not load city coordinates from `{LOCATIONS_FILE}`: {exc}")
    st.stop()

table_days = st.selectbox(
    "Number of forecast days",
    options=range(1, 8),
    index=5,
    format_func=lambda days: f"{days} days",
)

if st.button("Fetch / refresh temperature table", type="primary"):
    try:
        with st.spinner("Fetching the temperature forecast..."):
            results = fetch_daily(tuple(locations), 7, MODEL_ID)

        st.session_state["temperature_results"] = results
        st.session_state["temperature_locations"] = locations
    except (requests.RequestException, ValueError, KeyError) as exc:
        st.error(f"Could not fetch the temperature forecast: {exc}")

results = st.session_state.get("temperature_results")
if results is not None:
    try:
        table, dates = build_table(
            st.session_state["temperature_locations"], results, table_days
        )
        st.dataframe(table, use_container_width=True)

        first_date = pd.to_datetime(dates[0])
        title = (
            f"Temperature Pattern, Week {first_date.isocalendar().week} "
            f"(Basis {first_date.strftime('%A, %d %B')})"
        )
        st.caption(title)

        csv_bytes = table.to_csv(index=True).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name=f"temp_pattern_week{first_date.isocalendar().week}.csv",
            mime="text/csv",
        )
    except (ValueError, KeyError) as exc:
        st.error(f"Could not build the temperature table: {exc}")
else:
    st.info("Select the forecast length and fetch the table to get started.")
