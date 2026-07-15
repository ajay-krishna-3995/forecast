import os
import datetime
import requests
import folium
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime as dt, timedelta
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter

import streamlit as st
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
import base64

# -------------------------------------------------------------------------------
# 1. STREAMLIT PAGE SETUP & AUTO-ADAPTIVE DUAL THEME (CORRECTED WIDGETS)
# -------------------------------------------------------------------------------
st.set_page_config(
    page_title="Weather, Air Quality & Monsoon",
    page_icon="⛈️",
    layout="wide"
)

# Define the path to your local image (change 'monsoon_bg.jpg' to your filename)
LOCAL_IMAGE_PATH = "D:\\ajay\\Background.jpg"

def get_base64_image(image_path):
    """Reads a local image file and converts it to a base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/jpeg;base64,{encoded_string}"
    except FileNotFoundError:
        return None

# Convert the image to base64
img_base64 = get_base64_image(LOCAL_IMAGE_PATH)

# Add theme controller to the sidebar
st.sidebar.markdown("### 🎨 Theme Customizer")

# Slider to adjust the background image opacity
bg_opacity = st.sidebar.slider(
    "Background Image Opacity", 
    min_value=0.0, 
    max_value=1.0, 
    value=0.30, 
    step=0.05,
    help="Adjust image visibility. Keep low (0.15 - 0.35) for maximum data readability."
)

# Calculate dynamic alpha transparencies for both modes
light_alpha = round(1.0 - (bg_opacity * 0.95), 2)  # White overlay
dark_alpha = round(1.0 - (bg_opacity * 0.70), 2)   # Dark overlay

if img_base64:
    st.markdown(
        f"""
        <style>
        /* =====================================================================
           GLOBAL BASE STYLES
           ===================================================================== */
        .stApp {{
            background-image: url("{img_base64}");
            background-attachment: fixed;
            background-size: cover;
            background-position: center;
        }}

        /* =====================================================================
           ☀️ LIGHT THEME STYLES (Supports system and manual Streamlit light mode)
           ===================================================================== */
        @media (prefers-color-scheme: light) {{
            .stApp {{
                background-color: rgba(255, 255, 255, {light_alpha}) !important;
                background-blend-mode: overlay;
            }}
            /* High contrast dark text for light backgrounds */
            .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label, .stApp span, .stApp li {{
                color: #111827 !important;
            }}
            /* Soft light sidebar styling */
            [data-testid="stSidebar"] {{
                background-color: rgba(243, 244, 246, 0.95) !important;
            }}
            [data-testid="stSidebar"] * {{
                color: #111827 !important;
            }}
            
            /* Input Widgets (Selectbox and Number Inputs) */
            div[data-baseweb="select"], div[data-baseweb="input"], .stNumberInput input, .stSelectbox div {{
                background-color: #ffffff !important;
                color: #111827 !important;
                border: 1px solid #cbd5e1 !important;
            }}
            /* Force dropdown search & select values to be dark */
            div[data-baseweb="select"] *, .stSelectbox span, .stSelectbox div {{
                color: #111827 !important;
            }}
            /* Coordinate plus/minus control buttons */
            .stNumberInput button {{
                background-color: #f1f5f9 !important;
                color: #111827 !important;
                border: 1px solid #cbd5e1 !important;
            }}
            .stNumberInput button:hover {{
                background-color: #e2e8f0 !important;
            }}
        }}

        /* Force overrides when light theme is explicitly selected in settings */
        [data-theme="light"] .stApp {{
            background-color: rgba(255, 255, 255, {light_alpha}) !important;
            background-blend-mode: overlay;
        }}
        [data-theme="light"] .stApp, [data-theme="light"] p, [data-theme="light"] h1, [data-theme="light"] h2, [data-theme="light"] h3, [data-theme="light"] h4, [data-theme="light"] h5, [data-theme="light"] h6, [data-theme="light"] label, [data-theme="light"] span {{
            color: #111827 !important;
        }}
        [data-theme="light"] div[data-baseweb="select"], [data-theme="light"] div[data-baseweb="input"], [data-theme="light"] .stNumberInput input, [data-theme="light"] .stSelectbox div {{
            background-color: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #cbd5e1 !important;
        }}
        [data-theme="light"] div[data-baseweb="select"] *, [data-theme="light"] .stSelectbox span, [data-theme="light"] .stSelectbox div {{
            color: #111827 !important;
        }}
        [data-theme="light"] .stNumberInput button {{
            background-color: #f1f5f9 !important;
            color: #111827 !important;
            border: 1px solid #cbd5e1 !important;
        }}

        /* =====================================================================
           🌙 DARK THEME STYLES (Supports system and manual Streamlit dark mode)
           ===================================================================== */
        @media (prefers-color-scheme: dark) {{
            .stApp {{
                background-color: rgba(15, 23, 42, {dark_alpha}) !important; /* Rich deep navy/slate overlay */
                background-blend-mode: overlay;
            }}
            /* Clean off-white text for dark mode elements */
            .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label, .stApp span, .stApp li {{
                color: #f3f4f6 !important;
            }}
            /* Translucent dark sidebar */
            [data-testid="stSidebar"] {{
                background-color: rgba(17, 24, 39, 0.95) !important;
            }}
            [data-testid="stSidebar"] * {{
                color: #f3f4f6 !important;
            }}
            
            /* Input Widgets (Selectbox and Number Inputs) */
            div[data-baseweb="select"], div[data-baseweb="input"], .stNumberInput input, .stSelectbox div {{
                background-color: #1e293b !important;
                color: #ffffff !important;
                border: 1px solid #475569 !important;
            }}
            div[data-baseweb="select"] *, .stSelectbox span, .stSelectbox div {{
                color: #ffffff !important;
            }}
            /* Coordinate plus/minus control buttons */
            .stNumberInput button {{
                background-color: #334155 !important;
                color: #ffffff !important;
                border: 1px solid #475569 !important;
            }}
            .stNumberInput button:hover {{
                background-color: #475569 !important;
            }}
        }}

        /* Force overrides when dark theme is explicitly selected in settings */
        [data-theme="dark"] .stApp {{
            background-color: rgba(15, 23, 42, {dark_alpha}) !important;
            background-blend-mode: overlay;
        }}
        [data-theme="dark"] .stApp, [data-theme="dark"] p, [data-theme="dark"] h1, [data-theme="dark"] h2, [data-theme="dark"] h3, [data-theme="dark"] h4, [data-theme="dark"] h5, [data-theme="dark"] h6, [data-theme="dark"] label, [data-theme="dark"] span {{
            color: #f3f4f6 !important;
        }}
        [data-theme="dark"] div[data-baseweb="select"], [data-theme="dark"] div[data-baseweb="input"], [data-theme="dark"] .stNumberInput input, [data-theme="dark"] .stSelectbox div {{
            background-color: #1e293b !important;
            color: #ffffff !important;
            border: 1px solid #475569 !important;
        }}
        [data-theme="dark"] div[data-baseweb="select"] *, [data-theme="dark"] .stSelectbox span, [data-theme="dark"] .stSelectbox div {{
            color: #ffffff !important;
        }}
        [data-theme="dark"] .stNumberInput button {{
            background-color: #334155 !important;
            color: #ffffff !important;
            border: 1px solid #475569 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
else:
    st.sidebar.warning(f"⚠️ Local background image not found at `{LOCAL_IMAGE_PATH}`. Please check the file path.")
# -------------------------------------------------------------------------------
# 2. UNIVERSAL CSS OVERRIDE (Hides top header, github, deploy, footer, and locks out viewer profile badge)
st.markdown("""
    <style>
    /* Completely eliminate the top header bar and its actions */
    header, .stAppHeader, [data-testid="stHeader"] {
        display: none !important; 
        visibility: hidden !important; 
        height: 0px !important; 
    }
    
    /* Completely eliminate the footer, "Made with Streamlit" brand, and any profile links */
    footer, .stAppDeployButton, [data-testid="stStatusWidget"], [data-testid="stDecoration"], .stStatusWidget, #connection-status {
        display: none !important; 
        visibility: hidden !important; 
    }
    
    /* Strict target for the viewer footer container to block interaction */
    [data-testid="stViewerFooter"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* Target the Streamlit Cloud "Viewer Badge" containing your profile name and link */
    .viewerBadge_container__1QSob, 
    .styles_viewerBadge__1yB5_, 
    .viewerBadge_link__1S137, 
    .viewerBadge_text__1JaDK,
    [class^="viewerBadge_"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* Adjust top padding so your title doesn't look cut off */
    .block-container {
        padding-top: 2rem !important; 
    }

    /* Create an iron-clad click barrier along the entire bottom of the app window */
    .stApp::after {
        content: "";
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important;
        height: 70px !important;
        z-index: 9999999 !important;
        background: transparent !important;
        pointer-events: auto !important;
    }
    </style>
    """, unsafe_allow_html=True
)
# Global 1-minute auto-refresh to keep API queries fresh
st_autorefresh(interval=60000, key="weather_hub_refresh")

st.title("⛈️ Weather, Air Quality & Monsoon")
st.markdown("Plan Better with Smarter Weather ☔")

# Master database of preloaded global coordinate nodes
MAJOR_CITIES = {
    "Custom Location": None,
    "Mumbai, India": (19.076, 72.878),
    "New Delhi, India": (28.614, 77.209),
    "Kochi, India" : (9.9312, 76.2673),
    "London, UK": (51.507, -0.128),
    "New York, USA": (40.713, -74.006),
    "Tokyo, Japan": (35.689, 139.692),
    "Paris, France": (48.857, 2.352),
    "Sydney, Australia": (-33.869, 151.209),
    "São Paulo, Brazil": (-23.551, -46.633),
    "Cape Town, South Africa": (-33.925, 18.424)
}

# Configurable Path Constants for India Spatial Modeling
SHAPEFILE_PATH = "D:\\ajay\\India-State-and-Country-Shapefile-Updated-Jan-2020-master\\India_Country_Boundary.shp"
IMD_LEVELS = [0, 0.1, 2.4, 7.5, 15.5, 35.5, 64.4, 115.5, 204.4, 300]
IMD_COLORS = ['#ffffff', '#e3f2fd', '#90caf9', '#4caf50', '#2e7d32', '#fff59d', '#fbc02d', '#ff9800', '#b71c1c']
MAP_CITIES = {
    'Delhi': (77.2090, 28.6139), 'Mumbai': (72.8777, 19.0760),
    'Bengaluru': (77.5946, 12.9716), 'Chennai': (80.2707, 13.0827),
    'Kolkata': (88.3639, 22.5726), 'Hyderabad': (78.4867, 17.3850),
    'Guwahati': (91.7362, 26.1445), 'Nagpur': (79.0882, 21.1458)
}

# -------------------------------------------------------------------------------
# 2. STATE MANAGER & BI-DIRECTIONAL LOCATION SYNCHRONIZATION
# -------------------------------------------------------------------------------
if "lat" not in st.session_state:
    st.session_state.lat = 19.076  # Defaulting to Mumbai
if "lon" not in st.session_state:
    st.session_state.lon = 72.878
if "city_select" not in st.session_state:
    st.session_state.city_select = "Mumbai, India"

def on_city_change():
    chosen = st.session_state.city_select
    if chosen != "Custom Location":
        st.session_state.lat, st.session_state.lon = MAJOR_CITIES[chosen]

def sync_city_dropdown():
    """Matches coordinates back to a city choice or sets it to Custom."""
    st.session_state.city_select = "Custom Location"
    for city, coords in MAJOR_CITIES.items():
        if coords and round(coords[0], 3) == round(st.session_state.lat, 3) and round(coords[1], 3) == round(st.session_state.lon, 3):
            st.session_state.city_select = city
            break

# -------------------------------------------------------------------------------
# 3. GLOBAL SIDEBAR CONTROLS (UNIVERSAL TARGET SELECTOR)
# -------------------------------------------------------------------------------
st.sidebar.header("📍 Location Navigator")

st.sidebar.selectbox(
    "🌆 Quick Select Station",
    options=list(MAJOR_CITIES.keys()),
    key="city_select",
    on_change=on_city_change
)

col1, col2 = st.sidebar.columns(2)
with col1:
    lat_input = st.number_input("Lat (°N)", min_value=-90.0, max_value=90.0, step=0.001, format="%.3f", value=st.session_state.lat)
with col2:
    lon_input = st.number_input("Lon (°E)", min_value=-180.0, max_value=180.0, step=0.001, format="%.3f", value=st.session_state.lon)

# Detect if the user manually typed into the number boxes
if lat_input != st.session_state.lat or lon_input != st.session_state.lon:
    st.session_state.lat = lat_input
    st.session_state.lon = lon_input
    sync_city_dropdown()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🗺️ Map Target Picker")

# Build map layer
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=5)
folium.Marker(
    [st.session_state.lat, st.session_state.lon],
    popup="Monitored Station",
    tooltip="Active Target Node"
).add_to(m)

map_data = st_folium(
    m,
    height=220,
    width=None,
    key="sidebar_map_selector",
    returned_objects=["last_clicked"]
)

# Process map interaction securely without state conflicts
if map_data and map_data.get("last_clicked"):
    clicked_lat = round(map_data["last_clicked"]["lat"], 3)
    clicked_lon = round(map_data["last_clicked"]["lng"], 3)
    
    if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
        st.session_state.lat = clicked_lat
        st.session_state.lon = clicked_lon
        sync_city_dropdown()
        st.rerun()

DAYS = st.sidebar.slider("Forecast Lookahead Horizon", min_value=1, max_value=10, value=7)

# -------------------------------------------------------------------------------
# 4. DATA RETRIEVAL PIPELINES (WEATHER, FORECAST & AIR QUALITY)
# -------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_location_name(lat, lon):
    try:
        if st.session_state.city_select != "Custom Location":
            return st.session_state.city_select
        geo_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=10"
        headers = {'User-Agent': 'WeatherMeteogramApp/2.0'}
        res = requests.get(geo_url, headers=headers, timeout=3).json()
        if "display_name" in res:
            parts = res["display_name"].split(",")
            return f"{parts[0].strip()}, {parts[-1].strip()}"
    except Exception:
        pass
    return f"Node ({lat}°N, {lon}°E)"

@st.cache_data(show_spinner="Accessing Live Atmospheric Metrics...")
def fetch_live_metrics(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation"],
        "timezone": "auto"
    }
    try:
        res = requests.get(url, params=params).json()
        return res.get("current", None)
    except Exception:
        return None

@st.cache_data(show_spinner="Accessing Chemical Dispersion Model...")
def fetch_air_quality(lat, lon):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["european_aqi", "pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide"],
        "timezone": "auto"
    }
    try:
        res = requests.get(url, params=params).json()
        return res.get("current", None)
    except Exception:
        return None

@st.cache_data(show_spinner="Compiling Multi-Model Core Vectors...")
def fetch_weather_data(lat, lon, days, model_id):
    base_url = "https://api.open-meteo.com/v1/forecast"
    low_levels = ["10m", "100m", "1000hPa", "180m", "200m"]
    hourly_vars = [
        "temperature_2m", "dew_point_2m", "relative_humidity_2m",
        "pressure_msl", "cape", "wind_gusts_10m",
        "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "precipitation",
    ]
    for lvl in low_levels:
        hourly_vars.append(f"wind_speed_{lvl}")
        hourly_vars.append(f"wind_direction_{lvl}")

    params = {
        "latitude": lat,
        "longitude": lon,
        "models": model_id,
        "hourly": hourly_vars,
        "forecast_days": days,
        "timezone": "auto",
    }
    try:
        response = requests.get(base_url, params=params).json()
        if "hourly" not in response:
            return None
        df = pd.DataFrame(response["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        return df
    except Exception:
        return None

# Monsoon Specific Grid Retrieval Pipeline
@st.cache_data(show_spinner="Extracting National Synoptic Grid Matrix via Open-Meteo POST...")
def fetch_india_grid_forecast():
    lats = np.linspace(6.0, 38.0, 25)
    lons = np.linspace(68.0, 98.0, 25)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    flat_lats, flat_lons = lat_grid.flatten(), lon_grid.flatten()
    
    lat_string = ",".join(map(str, np.round(flat_lats, 3)))
    lon_string = ",".join(map(str, np.round(flat_lons, 3)))
    
    url = "https://api.open-meteo.com/v1/forecast"
    payload = {
        "latitude": lat_string,
        "longitude": lon_string,
        "hourly": "precipitation",
        "models": "ecmwf_ifs",
        "forecast_days": 1,
        "timezone": "Asia/Kolkata"
    }
    
    response = requests.post(url, data=payload, timeout=45)
    if response.status_code != 200:
        return None
        
    data = response.json()
    if isinstance(data, dict):
        data = [data]
        
    records = []
    for item in data:
        rain_array = item["hourly"]["precipitation"]
        records.append({
            "lat": item["latitude"],
            "lon": item["longitude"],
            "precip": sum(rain_array[:24])
        })
    return pd.DataFrame(records)

location_name = get_location_name(st.session_state.lat, st.session_state.lon)

# -------------------------------------------------------------------------------
# 5. WORKSPACE TAB COMPOSITIONS
# -------------------------------------------------------------------------------
tab_home, tab_meteogram, tab_monsoon = st.tabs([
    "🏡 Home",
    "📈 Meteogram",
    "🌧️ Monsoon"
])

# ===============================================================================
# A. TAB LAYOUT: HOME (LIVE TELEMETRY & CHEMICAL AIR MONITORING)
# ===============================================================================
with tab_home:
    st.subheader(f"📍 {location_name}")
    st.write(f"Coordinates: `{st.session_state.lat}°N, {st.session_state.lon}°E` | Updated at: {datetime.datetime.now().strftime('%H:%M:%S Local')}")
    
    live_weather = fetch_live_metrics(st.session_state.lat, st.session_state.lon)
    live_aqi = fetch_air_quality(st.session_state.lat, st.session_state.lon)
    forecast_alert_df = fetch_weather_data(st.session_state.lat, st.session_state.lon, 1, "ecmwf_ifs025")

    if live_weather and live_aqi:
        met_col1, met_col2, met_col3, met_col4 = st.columns(4)
        wind_speed_ms = live_weather['wind_speed_10m'] / 3.6
        
        with met_col1:
            with st.container(border=True):
                st.metric("🌡️ Surface Temperature", f"{live_weather['temperature_2m']} °C")
                st.caption("Standard 2-meter air sensor")
        with met_col2:
            with st.container(border=True):
                st.metric("💧 Relative Humidity", f"{live_weather['relative_humidity_2m']} %")
                st.caption("Water vapor mass ratio")
        with met_col3:
            with st.container(border=True):
                st.metric("💨 Wind Velocity", f"{wind_speed_ms:.1f} m/s")
                st.caption("Standard 10-meter anemometer")
        with met_col4:
            with st.container(border=True):
                st.metric("🌧️ Current Gauge Rainfall", f"{live_weather['precipitation']} mm")
                st.caption("Instantaneous rain rate")

        st.markdown("---")
        dash_col1, dash_col2 = st.columns([1, 1])
        
        with dash_col1:
            st.markdown("#### 🌧️ Meteorological Alerts (Next 24 Hours)")
            if forecast_alert_df is not None:
                total_24h_rain = forecast_alert_df["precipitation"].sum()
                peak_24h_rate = forecast_alert_df["precipitation"].max()
                
            if total_24h_rain > 75 or peak_24h_rate > 20:
                st.error(
                    f"🔴 **Heavy Rain Warning**\n\n"
                    f"Widespread heavy to very heavy rainfall is expected over the next 24 hours "
                    f"({total_24h_rain:.1f} mm). There is a risk of waterlogging, flash flooding, "
                    f"and travel disruptions. Stay updated with local weather advisories."
                )
            elif total_24h_rain > 25 or peak_24h_rate > 8:
                st.warning(
                    f"🟡 **Rain Advisory**\n\n"
                    f"Moderate to heavy rainfall is likely during the next 24 hours "
                    f"(around {total_24h_rain:.1f} mm). Keep an umbrella handy and be cautious "
                    f"while travelling, especially in low-lying areas."
                )
            elif total_24h_rain > 0.2:
                st.info(
                    f"🔵 **Light Rain Expected**\n\n"
                    f"Light to moderate showers are expected over the next 24 hours "
                    f"(around {total_24h_rain:.1f} mm). Outdoor activities may be briefly affected."
                )
            else:
                st.success(
                    "🟢 **No Significant Rain Expected**\n\n"
                    "Dry weather is expected over the next 24 hours, with no significant rainfall forecast."
                )

        with dash_col2:
            st.markdown("#### 🍃 Live Air Quality Index (AQI)")
            eaqi_val = live_aqi["european_aqi"]
            pm25_val = live_aqi["pm2_5"]
            pm10_val = live_aqi["pm10"]
            
            if eaqi_val <= 20:
                aqi_status, aqi_color = "Excellent", "🟢"
            elif eaqi_val <= 40:
                aqi_status, aqi_color = "Fair", "🟡"
            elif eaqi_val <= 60:
                aqi_status, aqi_color = "Moderate", "🟠"
            elif eaqi_val <= 80:
                aqi_status, aqi_color = "Poor", "🔴"
            else:
                aqi_status, aqi_color = "Extremely Poor", "☠️"
                
            st.markdown(f"##### Overall Assessment: {aqi_color} **{aqi_status}** (Index Score: {eaqi_val})")
            
            aqi_table_df = pd.DataFrame({
                "Aerosol Mass Component": ["Fine Particulates (PM2.5)", "Coarse Particulates (PM10)", "Nitrogen Dioxide (NO₂)", "Ozone (O₃)", "Sulfur Dioxide (SO₂)"],
                "Concentration Density": [f"{pm25_val} µg/m³", f"{pm10_val} µg/m³", f"{live_aqi['nitrogen_dioxide']} µg/m³", f"{live_aqi['ozone']} µg/m³", f"{live_aqi['sulphur_dioxide']} µg/m³"]
            })
            st.table(aqi_table_df)
    else:
        st.error("Live metrics data pipeline returned empty blocks. Re-check telemetry routing status or verify connectivity.")

# ===============================================================================
# B. TAB LAYOUT: METEOGRAM ANALYTICS (DEEP VERTICAL ATMOSPHERIC PLOT)
# ===============================================================================
with tab_meteogram:
    tab_ecmwf, tab_gfs = st.tabs(["🇪🇺 ECMWF IFS (0.25°)", "🇺🇸 GFS Seamless"])

    models_config = {
        "ECMWF": {"api_id": "ecmwf_ifs025", "title": "ECMWF IFS", "tab": tab_ecmwf},
        "GFS": {"api_id": "gfs_seamless", "title": "GFS Seamless", "tab": tab_gfs}
    }

    def render_meteogram(df, model_title):
        if df is None:
            st.error("Data tracking failure on core vector frame.")
            return

        with st.spinner(f"Generating {model_title} Meteogram Plot..."):
            fig, axs = plt.subplots(
                7, 1, figsize=(14, 18), sharex=True, gridspec_kw={"height_ratios": [1, 1, 2.5, 1, 1, 2.8, 1.2]}
            )
            plt.subplots_adjust(left=0.18, right=0.92, top=0.94, bottom=0.05, hspace=0.35)

            axs[0].set_title(
                f"{model_title} {DAYS}-Day Forecast Meteogram\n📍 Location: {location_name}",
                fontsize=14, weight="bold", pad=12
            )

            axs[0].plot(df["time"], df["pressure_msl"], color="blue")
            axs[0].set_ylabel("SLP\n(hPa)", color="blue")

            axs[1].bar(df["time"], df["cape"], width=0.03, color="purple", alpha=0.6)
            axs[1].set_ylabel("CAPE\n(J/kg)", color="purple")

            ax_wind = axs[2]
            api_levels = ["10m", "100m", "1000hPa", "180m", "200m"]
            display_labels = ["10m (Surface)", "100m", "1000 hPa (~110m)", "180m", "200m"]
            
            time_numbers = mdates.date2num(df["time"])
            skip = 3
            barb_times = time_numbers[::skip]

            for idx, lvl_str in enumerate(api_levels):
                speed_col = f"wind_speed_{lvl_str}"
                dir_col = f"wind_direction_{lvl_str}"
                if speed_col in df.columns and dir_col in df.columns:
                    speeds_ms = df[speed_col].fillna(0).astype(float).iloc[::skip] / 3.6
                    dirs = df[dir_col].fillna(0).astype(float).iloc[::skip]
                else:
                    continue
                rad = np.deg2rad(dirs)
                u_vec = -speeds_ms * np.sin(rad)
                v_vec = -speeds_ms * np.cos(rad)
                y_pos = np.full_like(barb_times, idx)
                ax_wind.barbs(barb_times, y_pos, u_vec, v_vec, length=6.0, color="#2c3e50", linewidth=0.9)

            ax_wind.set_yticks(range(len(api_levels)))
            ax_wind.set_yticklabels(display_labels, fontsize=9)
            ax_wind.set_ylabel("Wind Profile\n(Low Levels)", color="#ff7700", weight="bold")
            ax_wind.set_ylim(-0.5, len(api_levels) - 0.5)

            axs[3].plot(df["time"], df["relative_humidity_2m"], color="green")
            axs[3].fill_between(df["time"], df["relative_humidity_2m"], 0, color="limegreen", alpha=0.3)
            axs[3].set_ylabel("2m RH\n (%)")
            axs[3].set_ylim(0, 100)

            axs[4].plot(df["time"], df["temperature_2m"], color="red", linewidth=2)
            axs[4].set_ylabel("Temp\n(°C)", color="red", weight="bold")

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

            ax_cloud.text(time_numbers[0], 1.2, " Low-Level", fontsize=9, color="#111827", weight="bold", va="center")
            ax_cloud.text(time_numbers[0], 5.0, " Mid-Level", fontsize=9, color="#111827", weight="bold", va="center")
            ax_cloud.text(time_numbers[0], 10.0, " High-Level", fontsize=9, color="#111827", weight="bold", va="center")
            ax_cloud.set_ylabel("Altitude\n(km)", color="black")

            fig.canvas.draw()
            pos = ax_cloud.get_position()

            cax = fig.add_axes([pos.x0 - 0.10, pos.y0 + (pos.height * 0.1), 0.015, pos.height * 0.8])
            cbar = fig.colorbar(cloud_contour, cax=cax, orientation="vertical", ticks=cloud_bounds, extendfrac=0)
            cbar.ax.yaxis.set_label_position('left')
            cbar.ax.yaxis.set_ticks_position('left')
            cbar.set_label("Cloud cover (%)", fontsize=10, weight="bold", labelpad=10)

            axs[6].bar(df["time"], df["precipitation"], width=0.04, color="lightgreen", label="Precip")
            axs[6].set_ylabel("Precip\n(mm)")
            total_precip = df["precipitation"].sum()
            axs[6].text(0.95, 0.85, f"{DAYS}-Day Total = {total_precip:.2f} mm", transform=axs[6].transAxes, ha="right", weight="bold")

            axs[-1].xaxis.set_major_locator(mdates.DayLocator())
            axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d\n%b"))

            for ax in axs:
                ax.grid(True, which="major", axis="x", color="grey", linestyle="--", alpha=0.4)
                if ax != ax_cloud and ax != ax_wind:
                    ax.grid(True, which="major", axis="y", color="lightgrey", linestyle=":", alpha=0.5)

            st.pyplot(fig)
            with st.expander(f"🔍 View Raw Forecast Array ({model_title})"):
                st.dataframe(df)

    for model_key, cfg in models_config.items():
        with cfg["tab"]:
            model_df = fetch_weather_data(st.session_state.lat, st.session_state.lon, DAYS, cfg["api_id"])
            if model_df is not None:
                render_meteogram(model_df, cfg["title"])

# ===============================================================================
# C. TAB LAYOUT: MONSOON DIAGNOSTIC (INTEGRATED HIGH-RES SPATIAL INTERPOLATION)
# ===============================================================================
with tab_monsoon:
    st.subheader("🌧️ India National Monsoon Precipitation Analysis")
    st.markdown(f"**Target Local Reference:** {location_name}")
    st.markdown("---")
    
    st.markdown("##### 🌐 24-Hour National Spatial Interpolation (ECMWF IFS 9km)")
    
    if not os.path.exists(SHAPEFILE_PATH):
        st.error(f"Shapefile not found at target directory: `{SHAPEFILE_PATH}`. Please check file routing paths.")
    else:
        with st.spinner("Processing geospatial alignment matrix... This takes 2-3 seconds."):
            grid_data_df = fetch_india_grid_forecast()
            
            if grid_data_df is not None and not grid_data_df.empty:
                # Load shape files natively
                gdf = gpd.read_file(SHAPEFILE_PATH)
                if gdf.crs is None or gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs(epsg=4326)
                    
                # Create linear space surface grid (300 x 300)
                x_arr, y_arr, z_arr = grid_data_df['lon'].values, grid_data_df['lat'].values, grid_data_df['precip'].values
                xi_mesh = np.linspace(x_arr.min(), x_arr.max(), 300)
                yi_mesh = np.linspace(y_arr.min(), y_arr.max(), 300)
                xi_mesh, yi_mesh = np.meshgrid(xi_mesh, yi_mesh)
                
                # Run cubic grid surface spline
                zi_mesh = griddata((x_arr, y_arr), z_arr, (xi_mesh, yi_mesh), method='cubic')
                
                # Optimized Vector Deduplicated Masking Routine
                grid_df = pd.DataFrame({'lon': xi_mesh.flatten(), 'lat': yi_mesh.flatten()})
                grid_gdf = gpd.GeoDataFrame(grid_df, geometry=gpd.points_from_xy(grid_df.lon, grid_df.lat), crs="EPSG:4326")
                
                inside_points = gpd.sjoin(grid_gdf, gdf, how='left', predicate='within')
                inside_points = inside_points.groupby(inside_points.index).first()
                
                mask_matrix = inside_points['index_right'].notna().values.reshape(xi_mesh.shape)
                zi_masked = np.where(mask_matrix, zi_mesh, np.nan)
                
                # Generate Map Figure using pure matplotlib (removing Cartopy)
                fig_map, ax_map = plt.subplots(figsize=(11, 10), facecolor='#ffffff')
                
                # Simulate water bodies with background color
                ax_map.set_facecolor('#edf1f7')
                
                # Enforce coordinate extents
                bounds = gdf.total_bounds
                ax_map.set_xlim(bounds[0] - 0.5, bounds[2] + 0.5)
                ax_map.set_ylim(bounds[1] - 0.5, bounds[3] + 0.5)
                
                # Draw country outline with land background
                gdf.plot(ax=ax_map, facecolor='#fdfdfd', edgecolor='#37474f', linewidth=0.8, alpha=0.8, zorder=1)
                
                # Render IMD Colors
                cmap_imd = ListedColormap(IMD_COLORS)
                norm_imd = BoundaryNorm(IMD_LEVELS, cmap_imd.N)
                
                contour_plot = ax_map.contourf(
                    xi_mesh, yi_mesh, zi_masked, levels=IMD_LEVELS, cmap=cmap_imd, norm=norm_imd,
                    alpha=0.85, extend='max', zorder=2
                )
                
                # Draw boundaries again on top to keep them crisp
                gdf.plot(ax=ax_map, facecolor='none', edgecolor='#37474f', linewidth=1.0, zorder=3)
                
                # Reference Station Plot Markers
                for city, coords in MAP_CITIES.items():
                    if bounds[0] <= coords[0] <= bounds[2] and bounds[1] <= coords[1] <= bounds[3]:
                        ax_map.plot(coords[0], coords[1], marker='o', color='#212121', markersize=4, zorder=5)
                        ax_map.text(coords[0] + 0.2, coords[1] + 0.2, city, fontsize=8, weight='bold', zorder=5)
                        
                # Native Matplotlib Grid lines
                ax_map.grid(True, which="both", color='#b0bec5', alpha=0.4, linestyle='--')
                ax_map.set_xlabel('Longitude (°E)', fontsize=9)
                ax_map.set_ylabel('Latitude (°N)', fontsize=9)
                
                cb = plt.colorbar(contour_plot, orientation='horizontal', pad=0.05, shrink=0.85, aspect=30)
                cb.set_label('Accumulated Rainfall Over Next 24 Hours (mm)', weight='bold', size=9)
                cb.ax.tick_params(labelsize=8)
                
                st.pyplot(fig_map, clear_figure=True)
            else:
                st.error("Meteorological API connection timed out. Could not fetch map data.")
