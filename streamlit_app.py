import os
import datetime
import requests
import folium
import base64
import yaml
import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime as dt, timedelta
from scipy.ndimage import gaussian_filter
from mpl_toolkits.basemap import Basemap
import streamlit.components.v1 as components
import streamlit as st
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
from streamlit.components.v1 import html
from uploader import render_custom_dataset_uploader
# 1. Page Config (MUST BE FIRST STREAMLIT COMMAND)
# 1. Page Config (MUST BE FIRST STREAMLIT COMMAND)
st.set_page_config(
    page_title="Weather, Air Quality & Monsoon",
    page_icon="⛈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Hide Header & Viewer Badges Immediately
html('''
<script>
function hideViewerBadge() {
    const parentDoc = window.top.document;
    parentDoc.querySelectorAll('[href*="streamlit.io/cloud"], [href*="sharing-badge"]').forEach(el => {
        el.style.display = 'none'; el.style.visibility = 'hidden'; el.style.width = '0px'; el.style.height = '0px';
    });
    parentDoc.querySelectorAll('[class*="viewerBadge"], [class*="profile"], [class*="avatar"]').forEach(el => {
        el.style.display = 'none'; el.style.visibility = 'hidden'; el.style.width = '0px'; el.style.height = '0px';
    });
}
hideViewerBadge();
setInterval(hideViewerBadge, 500);
</script>
''', height=0, width=0)

st.markdown("""
    <style>
    /* Completely eliminate top header bar and actions */
    header, .stAppHeader, [data-testid="stHeader"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }

    /* Pin sidebar by hiding the collapse/expand controls */
    [data-testid="stSidebarCollapseButton"], 
    [data-testid="collapsedControl"],
    button[kind="headerNoPadding"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* Optional: Lock a fixed width so it cannot be resized by dragging */
    section[data-testid="stSidebar"] {
        min-width: 320px !important;
        max-width: 320px !important;
    }

    /* Adjust top padding so content doesn't get cut off */
    .block-container {
        padding-top: 1rem !important;
    }
    </style>
""", unsafe_allow_html=True)
# -------------------------------------------------------------------------------
# ECMWF DATA RETRIEVAL API (3 DAYS EXTENSION)
# -------------------------------------------------------------------------------
from ecmwf.opendata import Client

try:
    client = Client(source="ecmwf")
    result = client.retrieve(
        time=12,
        type="fc",
        param=["tp", "2t", "100u", "100v"],
        step=[24, 48, 72],
        target="data.grib2",
    )
    print(f"ECMWF Download Success - Valid Run Base Time: {result.datetime}")
except Exception as e:
    print(f"ECMWF OpenData Client Error: {e}")


# -------------------------------------------------------------------------------
# LOAD CONFIGURATION FROM YAML
# -------------------------------------------------------------------------------
@st.cache_data
def load_config():
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)

CONFIG = load_config()

LOCAL_IMAGE_PATH = CONFIG["paths"]["background_image"]
SHAPEFILE_PATH = CONFIG["paths"]["india_shapefile"]
GRIB_FILE_PATH = "data.grib2"
MAJOR_CITIES = CONFIG["major_cities"]
REFRESH_MS = CONFIG["refresh_interval_ms"]


@st.cache_data
def get_base64_image(image_path, mtime):
    try:
        with open(image_path, "rb") as image_file:
            return f"data:image/jpeg;base64,{base64.b64encode(image_file.read()).decode()}"
    except FileNotFoundError:
        return None

# Call it with os.path.getmtime:
img_mtime = os.path.getmtime(LOCAL_IMAGE_PATH) if os.path.exists(LOCAL_IMAGE_PATH) else 0
img_base64 = get_base64_image(LOCAL_IMAGE_PATH, img_mtime)

st.sidebar.markdown("### 🎨 Theme Customizer")
bg_opacity = st.sidebar.slider(
    "Background Image Opacity", 
    min_value=0.0, max_value=1.0, value=0.30, step=0.05,
    help="Adjust image visibility. Keep low (0.15 - 0.35) for maximum data readability."
)

light_alpha = round(1.0 - (bg_opacity * 0.95), 2)
dark_alpha = round(1.0 - (bg_opacity * 0.70), 2)

if img_base64:
    st.markdown(
        f"""
        <style>
        /* Apply background image */
        .stApp {{
            background-image: url("{img_base64}");
            background-attachment: fixed;
            background-size: cover;
            background-position: center;
        }}
        /* Hide default Streamlit multi-page navigation link list */
                [data-testid="stSidebarNav"] {{
                    display: none !important;
                    visibility: hidden !important;
                }}
        /* Completely eliminate the top header bar and its actions */
                header, .stAppHeader, [data-testid="stHeader"] {{
                    display: none !important; 
                    visibility: hidden !important; 
                    height: 0px !important; 
                }}

        /* Completely eliminate the footer, "Made with Streamlit" brand, and any profile links */
        footer, .stAppDeployButton, [data-testid="stStatusWidget"], [data-testid="stDecoration"], .stStatusWidget, #connection-status {{
            display: none !important; 
            visibility: hidden !important; 
        }}
        
        /* Strict target for the viewer footer container to block interaction */
        [data-testid="stViewerFooter"] {{
            display: none !important;
            visibility: hidden !important;
        }}

        /* Target the Streamlit Cloud "Viewer Badge" containing your profile name and link */
        .viewerBadge_container__1QSob, 
        .styles_viewerBadge__1yB5_, 
        .viewerBadge_link__1S137, 
        .viewerBadge_text__1JaDK,
        [class^="viewerBadge_"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        /* Adjust top padding so your title doesn't look cut off */
        .block-container {{
            padding-top: 2rem !important; 
        }}

        /* Create an iron-clad click barrier along the entire bottom of the app window */
        .stApp::after {{
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
        }}

        /* Light mode overlays & typography */
        @media (prefers-color-scheme: light) {{
            .stApp {{
                background-color: rgba(255, 255, 255, {light_alpha}) !important;
                background-blend-mode: overlay;
            }}
            .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label, .stApp span, .stApp li {{
                color: #111827 !important;
            }}
            [data-testid="stSidebar"] {{
                background-color: rgba(243, 244, 246, 0.95) !important;
            }}
            [data-testid="stSidebar"] * {{
                color: #111827 !important;
            }}
            div[data-baseweb="select"], div[data-baseweb="input"], .stNumberInput input, .stSelectbox div {{
                background-color: #ffffff !important;
                color: #111827 !important;
                border: 1px solid #cbd5e1 !important;
            }}
            div[data-baseweb="select"] *, .stSelectbox span, .stSelectbox div {{
                color: #111827 !important;
            }}
            .stNumberInput button {{
                background-color: #f1f5f9 !important;
                color: #111827 !important;
                border: 1px solid #cbd5e1 !important;
            }}
            .stNumberInput button:hover {{
                background-color: #e2e8f0 !important;
            }}
        }}

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

        /* Dark mode overlays & typography */
        @media (prefers-color-scheme: dark) {{
            .stApp {{
                background-color: rgba(15, 23, 42, {dark_alpha}) !important;
                background-blend-mode: overlay;
            }}
            .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label, .stApp span, .stApp li {{
                color: #f3f4f6 !important;
            }}
            [data-testid="stSidebar"] {{
                background-color: rgba(17, 24, 39, 0.95) !important;
            }}
            [data-testid="stSidebar"] * {{
                color: #f3f4f6 !important;
            }}
            div[data-baseweb="select"], div[data-baseweb="input"], .stNumberInput input, .stSelectbox div {{
                background-color: #1e293b !important;
                color: #ffffff !important;
                border: 1px solid #475569 !important;
            }}
            div[data-baseweb="select"] *, .stSelectbox span, .stSelectbox div {{
                color: #ffffff !important;
            }}
            .stNumberInput button {{
                background-color: #334155 !important;
                color: #ffffff !important;
                border: 1px solid #475569 !important;
            }}
            .stNumberInput button:hover {{
                background-color: #475569 !important;
            }}
        }}

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
        unsafe_allow_html=True,
    )
else:
    st.sidebar.warning(f"⚠️ Local background image not found at `{LOCAL_IMAGE_PATH}`.")
    #------------------------------------------------------------------------
# STATE MANAGER & ACTIONS
# -------------------------------------------------------------------------------
st.title("⛈️ Weather, AQI & Rainfall Forecasting")
st.markdown("Plan Better with Smarter Weather ☔")

# Initialize coordinates
if "lat" not in st.session_state: st.session_state.lat = 19.076
if "lon" not in st.session_state: st.session_state.lon = 72.878

def find_matched_city(lat, lon):
    for city, coords in MAJOR_CITIES.items():
        if coords and round(coords[0], 3) == round(lat, 3) and round(coords[1], 3) == round(lon, 3):
            return city
    return "Custom Location"

# -------------------------------------------------------------------------------
# SIDEBAR NAVIGATION & SAFE STATE SYNCHRONIZATION
# -------------------------------------------------------------------------------
st.sidebar.header("📍 Location Navigator")

cities_keys = list(MAJOR_CITIES.keys())

# Pre-determine current city label based on active lat/lon
matched_city = find_matched_city(st.session_state.lat, st.session_state.lon)
default_idx = cities_keys.index(matched_city) if matched_city in cities_keys else cities_keys.index("Custom Location")

# Render selectboxWITHOUT key="city_select" to avoid state locking
selected_city = st.sidebar.selectbox("🌆 Quick Select Station", options=cities_keys, index=default_idx)

# If dropdown choice changes manually, update target coordinates
if selected_city != matched_city and selected_city != "Custom Location":
    coords = MAJOR_CITIES[selected_city]
    if coords:
        st.session_state.lat, st.session_state.lon = coords
        st.rerun()

# Coordinate manual input fields
col1, col2 = st.sidebar.columns(2)
with col1: 
    lat_input = st.number_input("Lat (°N)", min_value=-90.0, max_value=90.0, step=0.001, format="%.3f", value=st.session_state.lat)
with col2: 
    lon_input = st.number_input("Lon (°E)", min_value=-180.0, max_value=180.0, step=0.001, format="%.3f", value=st.session_state.lon)

if lat_input != st.session_state.lat or lon_input != st.session_state.lon:
    st.session_state.lat, st.session_state.lon = lat_input, lon_input
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🗺️ Map Target Picker")

# Folium Map Target Picker
m = folium.Map(
    location=[st.session_state.lat, st.session_state.lon], 
    zoom_start=7,
    tiles="OpenStreetMap"
)
folium.Marker(
    [st.session_state.lat, st.session_state.lon], 
    popup=f"Target: {selected_city}", 
    tooltip="Active Station Target"
).add_to(m)

map_data = st_folium(m, height=220, width=None, key="sidebar_map_selector", returned_objects=["last_clicked"])

# Process map clicks safely without session state key locks
if map_data and map_data.get("last_clicked"):
    clicked_lat = round(map_data["last_clicked"]["lat"], 3)
    clicked_lon = round(map_data["last_clicked"]["lng"], 3)
    if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
        st.session_state.lat, st.session_state.lon = clicked_lat, clicked_lon
        st.rerun()

DAYS = st.sidebar.slider("Forecast Lookahead Horizon", min_value=1, max_value=10, value=7)

# -------------------------------------------------------------------------------
# DATA PROCESSING PIPELINES (API FETCHERS)
# -------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_location_name(lat, lon, current_city_label):
    try:
        if current_city_label != "Custom Location":
            return current_city_label
        geo_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=10"
        res = requests.get(geo_url, headers={'User-Agent': 'WeatherHubApp/2.0'}, timeout=3).json()
        if "display_name" in res:
            parts = res["display_name"].split(",")
            return f"{parts[0].strip()}, {parts[-1].strip()}"
    except Exception: pass
    return f"Node ({lat}°N, {lon}°E)"

@st.cache_data(show_spinner="Accessing Live Atmospheric Metrics...")
def fetch_live_metrics(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "current": ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation"], "timezone": "auto"}
    try: return requests.get(url, params=params).json().get("current", None)
    except Exception: return None

@st.cache_data(show_spinner="Accessing Chemical Dispersion Model...")
def fetch_air_quality(lat, lon):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {"latitude": lat, "longitude": lon, "current": ["european_aqi", "pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide"], "timezone": "auto"}
    try: return requests.get(url, params=params).json().get("current", None)
    except Exception: return None

@st.cache_data(show_spinner="Fetching Light Forecast Alerts...")
def fetch_alert_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "hourly": ["precipitation"], "forecast_days": 1, "timezone": "auto"}
    try:
        response = requests.get(url, params=params).json()
        df = pd.DataFrame(response["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        return df
    except Exception: return None

@st.cache_data(show_spinner="Compiling Multi-Model Core Vectors...")
def fetch_weather_data(lat, lon, days, model_id):
    base_url = "https://api.open-meteo.com/v1/forecast"
    hourly_vars = ["temperature_2m", "dew_point_2m", "relative_humidity_2m", "pressure_msl", "cape", "wind_gusts_10m", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "precipitation"]
    for lvl in ["10m", "100m", "1000hPa", "180m", "200m"]:
        hourly_vars.extend([f"wind_speed_{lvl}", f"wind_direction_{lvl}"])
    params = {"latitude": lat, "longitude": lon, "models": model_id, "hourly": hourly_vars, "forecast_days": days, "timezone": "auto"}
    try:
        response = requests.get(base_url, params=params).json()
        df = pd.DataFrame(response["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        return df
    except Exception: return None
@st.cache_data(show_spinner="Fetching ECMWF ensemble data from Open-Meteo...")
def fetch_ecmwf_ensemble_51(lat, lon, days=10, model="ecmwf_ifs025"):
    url = "https://ensemble-api.open-meteo.com/v1/ensemble"
    params = {
        "latitude": lat,
        "longitude": lon,
        "models": model,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "dew_point_2m",
            "precipitation",
        ],
        "forecast_days": days,
        "timezone": "auto",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()

        if response.status_code != 200 or "hourly" not in data:
            reason = data.get("reason", data.get("error", response.text))
            st.error(f"Open-Meteo Ensemble API error: {reason}")
            return None

        df_ens = pd.DataFrame(data["hourly"])
        if "time" not in df_ens.columns:
            st.error(f"Ensemble API response has no time column. Returned: {list(df_ens.columns)}")
            return None

        df_ens["time"] = pd.to_datetime(df_ens["time"])
        return df_ens

    except (requests.RequestException, ValueError) as exc:
        st.error(f"Could not fetch or parse ensemble data: {exc}")
        return None


def get_member_cols(df, variable):
    """Find columns such as temperature_2m_member01 in the API response."""
    member_cols = [
        col for col in df.columns
        if col.startswith(f"{variable}_member")
    ]

    # Support responses that provide the variable without member suffixes.
    return member_cols or ([variable] if variable in df.columns else [])
@st.cache_data(show_spinner="Parsing Primary GRIB2 Data Matrix...")
def process_grib_data_pure(file_path, selected_step_hours, param_key="tp"):
    def clean_date(t):
        try:
            v = pd.to_datetime(t)
            return v.item().strftime("%Y-%m-%d %H:%M UTC") if hasattr(v, 'item') else v.strftime("%Y-%m-%d %H:%M UTC")
        except: return str(t)

    if param_key == "100ws":
        backend_u = {"filter_by_keys": {"step": selected_step_hours, "shortName": "100u"}}
        backend_v = {"filter_by_keys": {"step": selected_step_hours, "shortName": "100v"}}
        
        with xr.open_dataset(file_path, engine="cfgrib", backend_kwargs=backend_u) as ds_u, \
             xr.open_dataset(file_path, engine="cfgrib", backend_kwargs=backend_v) as ds_v:
            
            f_time = clean_date(ds_u.time.values)
            v_time = clean_date(ds_u.valid_time.values)
            
            reg_u = ds_u.sel(latitude=slice(38, 5), longitude=slice(65, 98))["u100"].values
            reg_v = ds_v.sel(latitude=slice(38, 5), longitude=slice(65, 98))["v100"].values
            
            raw_values = np.sqrt(reg_u**2 + reg_v**2)
            lats = np.array(ds_u.sel(latitude=slice(38, 5)).latitude.values, dtype=np.float64)
            lons = np.array(ds_u.sel(longitude=slice(65, 98)).longitude.values, dtype=np.float64)
            units = "m/s"
    else:
        backend_kwargs = {"filter_by_keys": {"step": selected_step_hours, "shortName": param_key}}
        with xr.open_dataset(file_path, engine="cfgrib", backend_kwargs=backend_kwargs) as ds:
            var_name = str(list(ds.data_vars)[0])
            f_time = clean_date(ds.time.values)
            v_time = clean_date(ds.valid_time.values)
            region = ds.sel(latitude=slice(38, 5), longitude=slice(65, 98))
            
            raw_values = np.array(region[var_name].values, dtype=np.float64)
            lats = np.array(region.latitude.values, dtype=np.float64)
            lons = np.array(region.longitude.values, dtype=np.float64)
            
            if param_key == "tp":
                raw_values = raw_values * 1000.0
                units = "mm"
            elif param_key == "2t":
                raw_values = raw_values - 273.15
                units = "°C"
            else:
                units = str(region[var_name].attrs.get("units", ""))

    lon2d, lat2d = np.meshgrid(lons, lats)
    return {
        "lon2d": lon2d, "lat2d": lat2d, "data_vals": raw_values,
        "units": units, "f_time": f_time, "v_time": v_time
    }
    
location_name = get_location_name(st.session_state.lat, st.session_state.lon, selected_city)
# -------------------------------------------------------------------------------
# HELPER FUNCTIONS FOR IMD CLASSIFICATIONS
# -------------------------------------------------------------------------------
def categorize_imd_rainfall(val_mm):
    if val_mm < 0.1: return "No Rainfall"
    elif 0.1 <= val_mm <= 15.5: return "Very Light to Light Rainfall"
    elif 15.6 <= val_mm <= 64.4: return "Moderate Rainfall"
    elif 64.5 <= val_mm <= 115.5: return "Heavy Rainfall"
    elif 115.6 <= val_mm <= 204.4: return "Very Heavy Rainfall"
    else: return "Extremely Heavy Rainfall"

def categorize_imd_wind(speed_kmh):
    if speed_kmh < 20: return "Light Surface Winds"
    elif 20 <= speed_kmh < 52: return "Moderate / Strong Gusty Winds"
    elif 52 <= speed_kmh <= 61: return "Moderate Squall"
    elif 62 <= speed_kmh <= 87: return "Severe Squall"
    else: return "Very Severe Squall (>87 km/h)"

def check_thunderstorm_conditions(max_cape=0, min_li=0, precip=0):
    if max_cape > 1000 or precip > 5.0 or min_li < -3:
        return "Thunderstorm with sudden electrical discharges & lightning likely"
    return "Unlikely"

location_name = get_location_name(st.session_state.lat, st.session_state.lon, selected_city)

# -------------------------------------------------------------------------------
# WORKSPACE LAYOUT & GRAPHICS RENDERING
# -------------------------------------------------------------------------------
tab_home, tab_meteogram, tab_grib_analysis, tab_weather_update, tab_fog = st.tabs(
    ["🏡 Home", "📈 Meteogram", "Rainfall","Weather update","Fog"]
)

# --- 1. HOME TAB ---
with tab_home:
    st.subheader(f"📍 {location_name}")
    st.caption(f"Coordinates: `{st.session_state.lat}°N, {st.session_state.lon}°E` | Updated at: {datetime.datetime.now().strftime('%H:%M:%S Local')}")
    
    live_weather = fetch_live_metrics(st.session_state.lat, st.session_state.lon)
    live_aqi = fetch_air_quality(st.session_state.lat, st.session_state.lon)
    forecast_alert_df = fetch_alert_data(st.session_state.lat, st.session_state.lon)

    if live_weather and live_aqi:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("🌡️ Surface Temperature", f"{live_weather['temperature_2m']} °C")
        with c2: st.metric("💧 Relative Humidity", f"{live_weather['relative_humidity_2m']} %")
        with c3: st.metric("💨 Wind Velocity", f"{live_weather['wind_speed_10m'] / 3.6:.1f} m/s")
        with c4: st.metric("🌧️ Gauge Rainfall", f"{live_weather['precipitation']} mm")

        st.markdown("---")
        dash_col1, dash_col2 = st.columns(2)
        with dash_col1:
            st.markdown("#### 🌧️ Meteorological Alerts (Next 24 Hours)")
            if forecast_alert_df is not None:
                total_rain = forecast_alert_df["precipitation"].sum()
                peak_rate = forecast_alert_df["precipitation"].max()
                if total_rain > 75 or peak_rate > 20: st.error(f"🔴 **Heavy Rain Warning** ({total_rain:.1f} mm expected). Flash flooding risks.")
                elif total_rain > 25 or peak_rate > 8: st.warning(f"🟡 **Rain Advisory** ({total_rain:.1f} mm expected). Be cautious while traveling.")
                elif total_rain > 0.2: st.info(f"🔵 **Light Rain Expected** ({total_rain:.1f} mm expected).")
                else: st.success("🟢 **No Significant Rain Expected** over the next 24 hours.")

        with dash_col2:
            st.markdown("#### 🍃 Live Air Quality Index (AQI)")
            eaqi_val = live_aqi["european_aqi"]
            status, emoji = ("Excellent", "🟢") if eaqi_val <= 20 else ("Fair", "🟡") if eaqi_val <= 40 else ("Moderate", "🟠") if eaqi_val <= 60 else ("Poor", "🔴") if eaqi_val <= 80 else ("Extremely Poor", "☠️")
            st.markdown(f"##### Assessment: {emoji} **{status}** (Score: {eaqi_val})")
            st.table(pd.DataFrame({
                "Component": ["PM2.5", "PM10", "NO₂", "O₃", "SO₂"],
                "Density": [f"{live_aqi['pm2_5']} µg/m³", f"{live_aqi['pm10']} µg/m³", f"{live_aqi['nitrogen_dioxide']} µg/m³", f"{live_aqi['ozone']} µg/m³", f"{live_aqi['sulphur_dioxide']} µg/m³"]
            }))

# --- 2. METEOGRAM TAB ---
with tab_meteogram:
    st.subheader(f"📈 Meteogram — {location_name}")
    
    tab_ecmwf, tab_gfs = st.tabs(["EU ECMWF IFS (9km)", "US GFS Seamless"])

    models_config = {
        "ECMWF": {"api_id": "ecmwf_ifs", "title": "ECMWF IFS", "tab": tab_ecmwf},
        "GFS": {"api_id": "gfs_seamless", "title": "GFS Seamless", "tab": tab_gfs}
    }

    for model_key, config in models_config.items():
        with config["tab"]:
            with st.spinner(f"Extracting time-series arrays and generating {config['title']} charts..."):
                df_hourly = fetch_weather_data(st.session_state.lat, st.session_state.lon, DAYS, config["api_id"])
                
                if df_hourly is not None and not df_hourly.empty:
                    try:
                        fig_meteo, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
                        
                        fig_meteo.patch.set_alpha(0)
                        for ax in [ax1, ax2, ax3]:
                            ax.patch.set_alpha(0)
                            ax.set_facecolor('none')
                            ax.tick_params(colors='white', which='both', labelsize=10)
                            ax.xaxis.label.set_color('white')
                            ax.yaxis.label.set_color('white')
                            ax.grid(True, color='white', alpha=0.1, linestyle='--')
                            for spine in ax.spines.values():
                                spine.set_edgecolor('white')
                                spine.set_alpha(0.3)

                        ax1.plot(df_hourly["time"], df_hourly["temperature_2m"], color="#f97316", linewidth=2.0, label="Air Temp (°C)")
                        ax1.plot(df_hourly["time"], df_hourly["dew_point_2m"], color="#38bdf8", linewidth=1.5, linestyle=":", label="Dew Point (°C)")
                        ax1.set_ylabel("Temperature (°C)", weight='bold')
                        ax1.legend(loc="upper right", framealpha=0.1, labelcolor="white")
                        
                        ax1_rh = ax1.twinx()
                        ax1_rh.patch.set_alpha(0)
                        ax1_rh.plot(df_hourly["time"], df_hourly["relative_humidity_2m"], color="#10b981", linewidth=1.0, alpha=0.4, label="RH (%)")
                        ax1_rh.set_ylabel("Humidity (%)", color="#10b981", alpha=0.7)
                        ax1_rh.tick_params(colors='#10b981', which='both', labelcolor='#10b981')
                        ax1_rh.spines['right'].set_edgecolor('#10b981')
                        ax1_rh.spines['right'].set_alpha(0.4)

                        ax2.bar(df_hourly["time"], df_hourly["precipitation"], color="#2563eb", width=0.03, label="Hourly Rain (mm)")
                        ax2.set_ylabel("Precipitation (mm)", weight='bold')
                        ax2.legend(loc="upper right", framealpha=0.1, labelcolor="white")

                        wind_ms = df_hourly["wind_speed_10m"] / 3.6
                        gust_ms = df_hourly["wind_gusts_10m"] / 3.6
                        
                        ax3.plot(df_hourly["time"], wind_ms, color="#eab308", linewidth=1.8, label="Wind Speed (m/s)")
                        ax3.fill_between(df_hourly["time"], wind_ms, gust_ms, color="#eab308", alpha=0.15, label="Wind Gust Range")
                        ax3.set_ylabel("Wind Velocity (m/s)", weight='bold')
                        ax3.legend(loc="upper right", framealpha=0.1, labelcolor="white")

                        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))
                        ax3.xaxis.set_major_locator(mdates.AutoDateLocator())
                        
                        plt.tight_layout()
                        st.pyplot(fig_meteo, clear_figure=True)
                        
                    except Exception as plot_err:
                        st.error(f"Failed to assemble the {config['title']} time-series charts: {str(plot_err)}")
                else:
                    st.error(f"Unable to compile {config['title']} model timeline matrices from forecast APIs.")

# --- 3. RAINFALL MAP TAB ---
with tab_grib_analysis:
    st.subheader("Forecast Analysis for Indian region")
    
    grib_target_day = min(DAYS, 3) 
    target_step_hours = grib_target_day * 24
    
    st.info(f"📅 **Active Horizon:** Rendering **Day {grib_target_day} ({target_step_hours} Hour Forecast)** linked directly to your sidebar Lookahead Horizon slider.")
    
    if not os.path.exists(GRIB_FILE_PATH):
        st.error(f"GRIB dataset targets missing at destination: `{GRIB_FILE_PATH}`")
    elif not os.path.exists(SHAPEFILE_PATH):
        st.error(f"State boundary metrics missing at destination: `{SHAPEFILE_PATH}`")
    else:
        p_tab_precip, p_tab_temp, p_tab_wind = st.tabs(["🌧️ Total Precipitation", "🌡️ 2m Temperature", "💨 100m Wind Speed"])
        
        param_settings = [
            (p_tab_precip, "tp", "Greens", [0, 0.1, 1, 2.5, 5, 10, 20, 35, 50, 75], "ECMWF Total Precipitation"),
            (p_tab_temp, "2t", "coolwarm", None, "ECMWF 2m Air Temperature"),
            (p_tab_wind, "100ws", "YlGnBu", None, "ECMWF 100m Wind Speed")
        ]
        
        india_gdf = gpd.read_file(SHAPEFILE_PATH)
        if india_gdf.crs is not None:
            india_gdf = india_gdf.to_crs(epsg=4326)

        for tab, short_name, cmap, levels, title_prefix in param_settings:
            with tab:
                with st.spinner(f"Extracting {title_prefix} for step {target_step_hours}h..."):
                    try:
                        grib_payload = process_grib_data_pure(GRIB_FILE_PATH, target_step_hours, param_key=short_name)
                        
                        lon2d = grib_payload["lon2d"]
                        lat2d = grib_payload["lat2d"]
                        data_vals = grib_payload["data_vals"]
                        units = grib_payload["units"]
                        f_time = grib_payload["f_time"]
                        v_time = grib_payload["v_time"]
                        
                        fig_grib, ax = plt.subplots(figsize=(12, 10))

                        fig_grib.patch.set_alpha(0)
                        ax.patch.set_alpha(0)
                        ax.set_facecolor('none')
                        ax.axis('off') 
                        for spine in ax.spines.values():
                            spine.set_visible(False)
                        
                        m = Basemap(
                            projection='cyl',
                            llcrnrlon=65, urcrnrlon=98, llcrnrlat=5, urcrnrlat=38,
                            resolution='i', ax=ax
                        )
                        
                        parallels = m.drawparallels(np.arange(5, 41, 5), labels=[1, 0, 0, 0], fontsize=10, color='white', alpha=0.15, linewidth=0.6)
                        for p in parallels:
                            for txt in parallels[p][1]:
                                txt.set_color('white')
                                txt.set_alpha(0.9)

                        meridians = m.drawmeridians(np.arange(65, 101, 5), labels=[0, 0, 0, 1], fontsize=10, color='white', alpha=0.15, linewidth=0.6)
                        for m_val in meridians:
                            for txt in meridians[m_val][1]:
                                txt.set_color('white')
                                txt.set_alpha(0.9)
                        
                        m.drawmapboundary(color=(1, 1, 1, 0.3), linewidth=0.5, fill_color='none')
                        
                        import warnings
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", category=UserWarning)
                            if levels:
                                cf = m.contourf(lon2d, lat2d, data_vals, levels=levels, cmap=cmap, extend="max", latlon=True)
                            else:
                                cf = m.contourf(lon2d, lat2d, data_vals, levels=15, cmap=cmap, extend="both", latlon=True)
                        
                        india_gdf.boundary.plot(ax=ax, edgecolor='black', linewidth=0.8, zorder=100, alpha=0.6)

                        cbar = plt.colorbar(cf, pad=0.04, shrink=0.8)
                        cbar.set_label(f"({units})", color='white', weight='bold', fontsize=11)
                        cbar.ax.yaxis.set_tick_params(color='white', labelcolor='white', labelsize=10)
                        cbar.outline.set_edgecolor('white')
                        cbar.outline.set_linewidth(1.0)
                        
                        plt.title(
                            f"{title_prefix} ({target_step_hours}h Forecast Horizon)\nForecast Run: {f_time}  |  Valid Time: {v_time}",
                            fontsize=13, weight="bold", color="white", pad=15
                        )
                        plt.tight_layout()
                        st.pyplot(fig_grib, clear_figure=True)
                        
                    except Exception as e:
                        st.error(f"Failed to process parameter {short_name}. Error: {str(e)}")

# --- 5. WEATHER UPDATE TAB ---
with tab_weather_update:
    st.subheader(f"2-Day Weather Forecast Summary — {location_name}")
    
    # Fetch 2-day ECMWF forecast data
    df_ecmwf = fetch_weather_data(st.session_state.lat, st.session_state.lon, 2, "ecmwf_ifs025")
    
    if df_ecmwf is not None and not df_ecmwf.empty:
        today = datetime.datetime.now().date()
        day1 = today
        day2 = today + timedelta(days=1)
        
        df_day1 = df_ecmwf[df_ecmwf['time'].dt.date == day1]
        df_day2 = df_ecmwf[df_ecmwf['time'].dt.date == day2]
        
        if not df_day1.empty and not df_day2.empty:
            # Day 1 Metrics
            t_max_1 = df_day1['temperature_2m'].max()
            t_min_1 = df_day1['temperature_2m'].min()
            rh_avg_1 = df_day1['relative_humidity_2m'].mean() if 'relative_humidity_2m' in df_day1 else 0
            rain_1 = df_day1['precipitation'].sum()
            wind_1_kmh = (df_day1['wind_speed_10m'].max() * 3.6) if 'wind_speed_10m' in df_day1 else 0
            cape_1 = df_day1['cape'].max() if 'cape' in df_day1 else 0
            li_1 = df_day1['lifted_index'].min() if 'lifted_index' in df_day1 else 0
            ts_1 = check_thunderstorm_conditions(max_cape=cape_1, min_li=li_1, precip=rain_1)
            
            # Day 2 Metrics
            t_max_2 = df_day2['temperature_2m'].max()
            t_min_2 = df_day2['temperature_2m'].min()
            rh_avg_2 = df_day2['relative_humidity_2m'].mean() if 'relative_humidity_2m' in df_day2 else 0
            rain_2 = df_day2['precipitation'].sum()
            wind_2_kmh = (df_day2['wind_speed_10m'].max() * 3.6) if 'wind_speed_10m' in df_day2 else 0
            cape_2 = df_day2['cape'].max() if 'cape' in df_day2 else 0
            li_2 = df_day2['lifted_index'].min() if 'lifted_index' in df_day2 else 0
            ts_2 = check_thunderstorm_conditions(max_cape=cape_2, min_li=li_2, precip=rain_2)
            
            st.markdown(f"""
            **📅 Today ({day1.strftime('%A, %b %d')})**
            * **Rainfall Category:** {categorize_imd_rainfall(rain_1)} ({rain_1:.1f} mm)
            * **Temperature:** High of **{t_max_1:.1f}°C** | Low of **{t_min_1:.1f}°C**
            * **Relative Humidity:** Average around **{rh_avg_1:.0f}%**
            * **Surface Wind:** {categorize_imd_wind(wind_1_kmh)} (Peak gust: **{wind_1_kmh:.1f} km/h**)
            * **Thunderstorm / Lightning Activity:** {ts_1}
            
            ---
            
            **📅 Tomorrow ({day2.strftime('%A, %b %d')})**
            * **Rainfall Category:** {categorize_imd_rainfall(rain_2)} ({rain_2:.1f} mm)
            * **Temperature:** High of **{t_max_2:.1f}°C** | Low of **{t_min_2:.1f}°C**
            * **Relative Humidity:** Average around **{rh_avg_2:.0f}%**
            * **Surface Wind:** {categorize_imd_wind(wind_2_kmh)} (Peak gust: **{wind_2_kmh:.1f} km/h**)
            * **Thunderstorm / Lightning Activity:** {ts_2}
            """)
        else:
            st.info("ECMWF forecast details for the next 2 days are currently compiling.")
    else:
        st.warning("Unable to fetch ECMWF forecast data from Open-Meteo. Please check connection.")
        # --- 6. CUSTOM VISUALIZER TAB ---
with tab_fog:
    st.subheader(f"📈 Ensemble Forecast — {location_name}")

    tab_ecmwf = st.tabs(["EU ECMWF_ENS"])[0]
    models_config = {
        "ECMWF": {
            "api_id": "ecmwf_ifs025",
            "title": "ECMWF IFS Ensemble",
            "tab": tab_ecmwf,
        },
    }

    def style_ax(ax):
        ax.patch.set_alpha(0)
        ax.set_facecolor("none")
        ax.tick_params(colors="white", which="both", labelsize=10)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.grid(True, color="white", alpha=0.1, linestyle="--")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        for spine in ax.spines.values():
            spine.set_edgecolor("white")
            spine.set_alpha(0.3)

    for model_key, config in models_config.items():
        with config["tab"]:
            with st.spinner(f"Aggregating ensemble members and generating {config['title']} charts..."):
                df_ens = fetch_ecmwf_ensemble_51(
                    st.session_state.lat,
                    st.session_state.lon,
                    DAYS,
                    config["api_id"],
                )

                if df_ens is not None and not df_ens.empty:
                    try:
                        t_cols = get_member_cols(df_ens, "temperature_2m")
                        td_cols = get_member_cols(df_ens, "dew_point_2m")
                        rh_cols = get_member_cols(df_ens, "relative_humidity_2m")
                        pr_cols = get_member_cols(df_ens, "precipitation")
                        ws_cols = get_member_cols(df_ens, "wind_speed_10m")

                        t_mean = df_ens[t_cols].mean(axis=1)
                        t_p10 = df_ens[t_cols].quantile(0.10, axis=1)
                        t_p90 = df_ens[t_cols].quantile(0.90, axis=1)

                        td_mean = df_ens[td_cols].mean(axis=1)

                        rh_mean = df_ens[rh_cols].mean(axis=1)
                        rh_p10 = df_ens[rh_cols].quantile(0.10, axis=1)
                        rh_p90 = df_ens[rh_cols].quantile(0.90, axis=1)

                        pr_mean = df_ens[pr_cols].mean(axis=1)

                        # Convert wind speed from km/h to m/s
                        ws_ms_df = df_ens[ws_cols] / 3.6
                        ws_mean = ws_ms_df.mean(axis=1)
                        ws_p10 = ws_ms_df.quantile(0.10, axis=1)
                        ws_p90 = ws_ms_df.quantile(0.90, axis=1)

                        # 1. Temperature & Dew Point
                        st.markdown("#### 🌡️ Temperature & Dew Point")
                        fig_temp, ax_temp = plt.subplots(figsize=(12, 4))
                        fig_temp.patch.set_alpha(0)
                        style_ax(ax_temp)
                        ax_temp.fill_between(
                            df_ens["time"], t_p10, t_p90,
                            color="#f97316", alpha=0.18, label="Temp P10–P90 Spread"
                        )
                        ax_temp.plot(
                            df_ens["time"], t_mean,
                            color="#f97316", linewidth=2.0, label="Ensemble Mean Temp (°C)"
                        )
                        ax_temp.plot(
                            df_ens["time"], td_mean,
                            color="#38bdf8", linewidth=1.5, linestyle=":", label="Mean Dew Point (°C)"
                        )
                        ax_temp.set_ylabel("Temperature (°C)", weight="bold")
                        ax_temp.legend(loc="upper right", framealpha=0.1, labelcolor="white")
                        plt.tight_layout()
                        st.pyplot(fig_temp, clear_figure=True)

                        # 2. Relative Humidity
                        st.markdown("#### 💧 Relative Humidity")
                        fig_rh, ax_rh = plt.subplots(figsize=(12, 4))
                        fig_rh.patch.set_alpha(0)
                        style_ax(ax_rh)
                        ax_rh.fill_between(
                            df_ens["time"], rh_p10, rh_p90,
                            color="#10b981", alpha=0.18, label="RH P10–P90 Spread"
                        )
                        ax_rh.plot(
                            df_ens["time"], rh_mean,
                            color="#10b981", linewidth=2.0, label="Ensemble Mean RH (%)"
                        )
                        ax_rh.set_ylabel("Relative Humidity (%)", weight="bold")
                        ax_rh.set_ylim(0, 105)
                        ax_rh.legend(loc="upper right", framealpha=0.1, labelcolor="white")
                        plt.tight_layout()
                        st.pyplot(fig_rh, clear_figure=True)

                        # 3. Precipitation
                        st.markdown("#### 🌧️ Precipitation")
                        fig_pr, ax_pr = plt.subplots(figsize=(12, 4))
                        fig_pr.patch.set_alpha(0)
                        style_ax(ax_pr)
                        for col in pr_cols:
                            ax_pr.plot(
                                df_ens["time"], df_ens[col],
                                color="#60a5fa", linewidth=0.5, alpha=0.15
                            )
                        ax_pr.bar(
                            df_ens["time"], pr_mean,
                            color="#2563eb", width=0.03, label="Ensemble Mean Rain (mm)"
                        )
                        ax_pr.set_ylabel("Precipitation (mm)", weight="bold")
                        ax_pr.legend(loc="upper right", framealpha=0.1, labelcolor="white")
                        plt.tight_layout()
                        st.pyplot(fig_pr, clear_figure=True)

                        # 4. Wind Speed
                        st.markdown("#### 💨 Wind Velocity")
                        fig_ws, ax_ws = plt.subplots(figsize=(12, 4))
                        fig_ws.patch.set_alpha(0)
                        style_ax(ax_ws)
                        ax_ws.fill_between(
                            df_ens["time"], ws_p10, ws_p90,
                            color="#eab308", alpha=0.18, label="Wind P10–P90 Spread"
                        )
                        ax_ws.plot(
                            df_ens["time"], ws_mean,
                            color="#eab308", linewidth=1.8, label="Ensemble Mean Wind (m/s)"
                        )
                        ax_ws.set_ylabel("Wind Velocity (m/s)", weight="bold")
                        ax_ws.legend(loc="upper right", framealpha=0.1, labelcolor="white")
                        plt.tight_layout()
                        st.pyplot(fig_ws, clear_figure=True)

                    except Exception as plot_err:
                        st.error(f"Failed to assemble the {config['title']} time-series charts: {str(plot_err)}")
                else:
                    st.error(f"Unable to compile {config['title']} timeline matrices from ensemble API.")
