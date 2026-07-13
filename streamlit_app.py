import datetime
import folium
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from matplotlib.colors import BoundaryNorm, ListedColormap
from scipy.ndimage import gaussian_filter
from streamlit_folium import st_folium
# IMPORT THE AUTOREFRESH UTILITY
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------------------------------------
# 1. STREAMLIT PAGE SETUP
# -------------------------------------------------------------------------------
st.set_page_config(
    page_title="Weather Meteogram",
    page_icon="⛈️",
    layout="wide"
)

# Run an auto-refresh every 60,000 milliseconds (1 minute).
st_autorefresh(interval=60000, key="meteogram_peer_refresh")

st.title("⛈️ Weather Meteogram")
st.markdown("by Open-Meteo API.")

# Predefined dictionary of major global cities
MAJOR_CITIES = {
    "Custom Location": None,
    "New York, USA": (40.713, -74.006),
    "London, UK": (51.507, -0.128),
    "Tokyo, Japan": (35.689, 139.692),
    "Paris, France": (48.857, 2.352),
    "Mumbai, India": (19.076, 72.878),
    "Sydney, Australia": (-33.869, 151.209),
    "Cairo, Egypt": (30.044, 31.236),
    "São Paulo, Brazil": (-23.551, -46.633),
    "Cape Town, South Africa": (-33.925, 18.424)
}

# -------------------------------------------------------------------------------
# 2. SESSION STATE SYNCHRONIZATION
# -------------------------------------------------------------------------------
if "lat" not in st.session_state:
    st.session_state.lat = 9.605
if "lon" not in st.session_state:
    st.session_state.lon = 77.170
if "city_select" not in st.session_state:
    st.session_state.city_select = "Custom Location"

# Callback functions to sync controls when changed manually
def on_city_change():
    chosen = st.session_state.city_select
    if chosen != "Custom Location":
        st.session_state.lat, st.session_state.lon = MAJOR_CITIES[chosen]

def on_coordinate_change():
    # If manual coords match a major city exactly, select it, otherwise set to Custom
    st.session_state.city_select = "Custom Location"
    for city, coords in MAJOR_CITIES.items():
        if coords and round(coords[0], 3) == round(st.session_state.lat, 3) and round(coords[1], 3) == round(st.session_state.lon, 3):
            st.session_state.city_select = city
            break

# -------------------------------------------------------------------------------
# 3. SIDEBAR CONTROLS & INTERACTIVE MAP SELECTOR
# -------------------------------------------------------------------------------
st.sidebar.header("Location & Forecast Settings")

# Feature 1: Major Cities Dropdown Selector
st.sidebar.selectbox(
    "🌆 Select a Major City", 
    options=list(MAJOR_CITIES.keys()), 
    key="city_select",
    on_change=on_city_change
)

# Feature 2: Manual Latitude and Longitude Entry
col1, col2 = st.sidebar.columns(2)
with col1:
    st.number_input("Latitude (°N)", min_value=-90.0, max_value=90.0, step=0.001, format="%.3f", key="lat", on_change=on_coordinate_change)
with col2:
    st.number_input("Longitude (°E)", min_value=-180.0, max_value=180.0, step=0.001, format="%.3f", key="lon", on_change=on_coordinate_change)

# Interactive Map Section
st.sidebar.markdown("### 🗺️ Click on the Map to Select Location")

# Dynamic centering on active coordinates
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=4)
folium.Marker(
    [st.session_state.lat, st.session_state.lon], 
    popup="Selected Coordinates", 
    tooltip="Active Location"
).add_to(m)

map_data = st_folium(m, height=250, width=None, key="map_selector")

# Handle Map click interactions
if map_data and map_data.get("last_clicked"):
    clicked_lat = round(map_data["last_clicked"]["lat"], 3)
    clicked_lon = round(map_data["last_clicked"]["lng"], 3)
    
    if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
        st.session_state.lat = clicked_lat
        st.session_state.lon = clicked_lon
        on_coordinate_change()  # Sync dropdown selection status
        st.rerun()

DAYS = st.sidebar.slider("Forecast Days", min_value=1, max_value=10, value=10)

# -------------------------------------------------------------------------------
# 4. CACHED DATA & REVERSE GEOCODING FETCHING
# -------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_location_name(lat, lon):
    """Fetches human-readable place name using Open-Meteo's Geocoding API."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=is_day&timezone=auto"
        # Using open-meteo fallback naming technique or just manual label if it's explicitly chosen
        if st.session_state.city_select != "Custom Location":
            return st.session_state.city_select
        
        # Simple lookup fallback to give context
        geo_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=10"
        headers = {'User-Agent': 'WeatherMeteogramApp/1.0'}
        res = requests.get(geo_url, headers=headers, timeout=3).json()
        if "display_name" in res:
            parts = res["display_name"].split(",")
            # Extract city/town and country
            return f"{parts[0].strip()}, {parts[-1].strip()}"
    except Exception:
        pass
    return f"Custom Coordinates ({lat}°N, {lon}°E)"

@st.cache_data(show_spinner="Fetching data from Open-Meteo API...")
def fetch_weather_data(lat, lon, days, model_id):
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "models": model_id,
        "hourly": [
            "temperature_2m",
            "dew_point_2m",
            "relative_humidity_2m",
            "pressure_msl",
            "cape",
            "wind_speed_10m",
            "wind_gusts_10m",
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "precipitation",
        ],
        "forecast_days": days,
        "timezone": "auto",
    }
    
    response = requests.get(base_url, params=params).json()
    if "hourly" not in response:
        st.error(f"Could not find 'hourly' data block for {model_id}. Check the API coordinates or parameters.")
        return None
        
    df = pd.DataFrame(response["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df

# -------------------------------------------------------------------------------
# 5. TAB SELECTION & CORE PLOT RENDER LOGIC
# -------------------------------------------------------------------------------
tab_ecmwf, tab_gfs = st.tabs(["🇪🇺 ECMWF IFS (0.25°)", "🇺🇸 GFS Seamless"])

models_config = {
    "ECMWF": {"api_id": "ecmwf_ifs025", "title": "ECMWF IFS", "tab": tab_ecmwf},
    "GFS": {"api_id": "gfs_seamless", "title": "GFS Seamless", "tab": tab_gfs}
}

def render_meteogram(df, model_title):
    if df is None:
        return
        
    # Feature 3: Dynamic Location Name Extraction
    location_name = get_location_name(st.session_state.lat, st.session_state.lon)

    with st.spinner(f"Generating {model_title} Meteogram Plot..."):
        fig, axs = plt.subplots(
            7, 1, figsize=(14, 18), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1, 1, 1, 2.8, 1.2]}
        )

        plt.subplots_adjust(left=0.18, right=0.92, top=0.93, bottom=0.05, hspace=0.35)

        # Embedded location title over the Meteogram Plot
        axs[0].set_title(
            f"{model_title} {DAYS}-Day Meteogram\n📍 Location: {location_name}", 
            fontsize=15, weight="bold", pad=15
        )

        # PANEL 1: Sea Level Pressure
        axs[0].plot(df["time"], df["pressure_msl"], color="blue")
        axs[0].set_ylabel("SLP\n(hPa)", color="blue")

        # PANEL 2: CAPE
        axs[1].bar(df["time"], df["cape"], width=0.03, color="purple", alpha=0.6)
        axs[1].set_ylabel("CAPE\n(J/kg)", color="purple")

        # PANEL 3: 10m Wind Speed & Gusts
        axs[2].plot(df["time"], df["wind_speed_10m"] / 3.6, color="orange", label="Wind")
        axs[2].plot(df["time"], df["wind_gusts_10m"] / 3.6, color="crimson", linestyle=":", label="Gust")
        axs[2].set_ylabel("Wind\n(m/s)")
        axs[2].legend(loc="upper right", fontsize=8)

        # PANEL 4: 2m Relative Humidity
        axs[3].plot(df["time"], df["relative_humidity_2m"], color="green")
        axs[3].fill_between(df["time"], df["relative_humidity_2m"], 0, color="limegreen", alpha=0.3)
        axs[3].set_ylabel("2m RH\n (%)")
        axs[3].set_ylim(0, 100)

        # PANEL 5: 2m Temperature
        axs[4].plot(df["time"], df["temperature_2m"], color="red", linewidth=2)
        axs[4].set_ylabel("Temp\n(°C)", color="red", weight="bold")

        # PANEL 6: CLOUD COVER MATRIX
        ax_cloud = axs[5]
        num_time_steps = len(df["time"])
        alt_grid = np.linspace(0, 14, 100)
        cloud_matrix = np.zeros((len(alt_grid), num_time_steps))

        for t in range(num_time_steps):
            low = df["cloud_cover_low"].iloc[t]
            mid = df["cloud_cover_mid"].iloc[t]
            high = df["cloud_cover_high"].iloc[t]
            
            layer_profile = (
                low * np.exp(-((alt_grid - 1.0) / 1.2) ** 2) +
                mid * np.exp(-((alt_grid - 4.5) / 2.5) ** 2) +
                high * np.exp(-((alt_grid - 9.5) / 3.0) ** 2)
            )
            cloud_matrix[:, t] = np.clip(layer_profile, 0, 100)

        cloud_matrix_smooth = gaussian_filter(cloud_matrix, sigma=(1.5, 1.0))
        time_numbers = mdates.date2num(df["time"])

        cloud_colors = ["#ffffff", "#e0e0e0", "#b8b8b8", "#8c8c8c", "#686868", "#444444"]
        cloud_bounds = [0, 10, 25, 50, 75, 90, 100]
        cmap_cloud = ListedColormap(cloud_colors)
        norm_cloud = BoundaryNorm(cloud_bounds, cmap_cloud.N)

        cloud_contour = ax_cloud.contourf(
            time_numbers, alt_grid, cloud_matrix_smooth,
            levels=cloud_bounds, cmap=cmap_cloud, norm=norm_cloud, extend='max'
        )

        ax_cloud.contour(
            time_numbers, alt_grid, cloud_matrix_smooth,
            levels=[15, 50, 85], colors="#555555", linewidths=0.5, alpha=0.6
        )

        ax_cloud.set_ylim(0, 14)
        ax_cloud.tick_params(axis='y', labelleft=True)

        for height in [1.5, 3.5, 6.0, 9.0]:
            ax_cloud.axhline(height, color="dimgray", linestyle=":", linewidth=0.8, alpha=0.6)
            ax_cloud.text(time_numbers[-1], height + 0.1, f"{height}", fontsize=8, color="black", ha="left")

        ax_cloud.text(time_numbers[0] - 0.2, 1.0, "Low", fontsize=8, color="dimgray", weight="bold", ha="right", va="center")
        ax_cloud.text(time_numbers[0] - 0.2, 4.5, "Mid", fontsize=8, color="dimgray", weight="bold", ha="right", va="center")
        ax_cloud.text(time_numbers[0] - 0.2, 9.5, "High", fontsize=8, color="dimgray", weight="bold", ha="right", va="center")
        ax_cloud.set_ylabel("Altitude\n(km)", color="black")

        fig.canvas.draw()
        pos = ax_cloud.get_position()

        cax = fig.add_axes([pos.x0 - 0.10, pos.y0 + (pos.height * 0.1), 0.015, pos.height * 0.8])
        cbar = fig.colorbar(cloud_contour, cax=cax, orientation="vertical", ticks=cloud_bounds, extendfrac=0)
        cbar.ax.yaxis.set_label_position('left')
        cbar.ax.yaxis.set_ticks_position('left')
        cbar.set_label("Cloud cover (%)", fontsize=10, weight="bold", labelpad=10)

        # PANEL 7: Precipitation
        axs[6].bar(df["time"], df["precipitation"], width=0.04, color="lightgreen", label="Precip")
        axs[6].set_ylabel("Precip\n(mm)")
        total_precip = df["precipitation"].sum()
        axs[6].text(0.95, 0.85, f"{DAYS}-Day Total = {total_precip:.2f} mm", transform=axs[6].transAxes, ha="right", weight="bold")

        # Global Axis Setup
        axs[-1].xaxis.set_major_locator(mdates.DayLocator())
        axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d\n%b"))

        for ax in axs:
            ax.grid(True, which="major", axis="x", color="grey", linestyle="--", alpha=0.4)
            if ax != ax_cloud:
                ax.grid(True, which="major", axis="y", color="lightgrey", linestyle=":", alpha=0.5)

        st.pyplot(fig)
        
        with st.expander(f"🔍 View Raw {model_title} Forecast Data"):
            st.dataframe(df)

# Loop through our configurations and assign plots to their respective tabs
for model_key, cfg in models_config.items():
    with cfg["tab"]:
        model_df = fetch_weather_data(st.session_state.lat, st.session_state.lon, DAYS, cfg["api_id"])
        if model_df is not None:
            render_meteogram(model_df, cfg["title"])
