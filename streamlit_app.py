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
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime as dt, timedelta
from scipy.ndimage import gaussian_filter
from mpl_toolkits.basemap import Basemap

import streamlit as st
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
# --- IMPORT HTML FOR THE JAVASCRIPT HACK ---
from streamlit.components.v1 import html
# -------------------------------------------------------------------------------
# 1. STREAMLIT PAGE SETUP & AUTO-ADAPTIVE DUAL THEME (CORRECTED WIDGETS)
# -------------------------------------------------------------------------------
# LOAD CONFIGURATION FROM YAML
@st.cache_data
def load_config():
    with open("config.yaml", "r") as file:
        return yaml.safe_load(file)

CONFIG = load_config()

LOCAL_IMAGE_PATH = CONFIG["paths"]["background_image"]
SHAPEFILE_PATH = CONFIG["paths"]["india_shapefile"]
GRIB_FILE_PATH = CONFIG["paths"]["grib_file"]
MAJOR_CITIES = CONFIG["major_cities"]
REFRESH_MS = CONFIG["refresh_interval_ms"]

st.set_page_config(
    page_title="Weather, Air Quality & Monsoon",
    page_icon="⛈️",
    layout="wide"
)
html('''
<script>
    function hideViewerBadge() {
        // Target the parent document structure containing the sharing container
        const parentDoc = window.top.document;
        
        // Target the hosting redirect links
        parentDoc.querySelectorAll('[href*="streamlit.io/cloud"], [href*="sharing-badge"]').forEach(el => {
            el.style.display = 'none';
            el.style.visibility = 'hidden';
            el.style.width = '0px';
            el.style.height = '0px';
        });
        
        // Target the profile avatar wrappers and custom container classes
        parentDoc.querySelectorAll('[class*="viewerBadge"], [class*="profile"], [class*="avatar"]').forEach(el => {
            el.style.display = 'none';
            el.style.visibility = 'hidden';
            el.style.width = '0px';
            el.style.height = '0px';
        });
    }

    // Fire immediately upon initialization
    hideViewerBadge();
    
    // Periodically run a DOM sweep to prevent the badge from reappearing
    setInterval(hideViewerBadge, 500);
</script>
''', height=0, width=0)
# Define the path to your local image (change 'monsoon_bg.jpg' to your filename)
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return f"data:image/jpeg;base64,{base64.b64encode(image_file.read()).decode()}"
    except FileNotFoundError:
        return None

img_base64 = get_base64_image(LOCAL_IMAGE_PATH)

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
        .stApp {{ background-image: url("{img_base64}"); background-attachment: fixed; background-size: cover; background-position: center; }}
        @media (prefers-color-scheme: light) {{
            .stApp {{ background-color: rgba(255, 255, 255, {light_alpha}) !important; background-blend-mode: overlay; }}
            .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label, .stApp span, .stApp li {{ color: #111827 !important; }}
            [data-testid="stSidebar"] {{ background-color: rgba(243, 244, 246, 0.95) !important; }}
            [data-testid="stSidebar"] * {{ color: #111827 !important; }}
            div[data-baseweb="select"], div[data-baseweb="input"], .stNumberInput input, .stSelectbox div {{ background-color: #ffffff !important; color: #111827 !important; border: 1px solid #cbd5e1 !important; }}
            div[data-baseweb="select"] *, .stSelectbox span, .stSelectbox div {{ color: #111827 !important; }}
            .stNumberInput button {{ background-color: #f1f5f9 !important; color: #111827 !important; border: 1px solid #cbd5e1 !important; }}
            .stNumberInput button:hover {{ background-color: #e2e8f0 !important; }}
        }}
        [data-theme="light"] .stApp {{ background-color: rgba(255, 255, 255, {light_alpha}) !important; background-blend-mode: overlay; }}
        [data-theme="light"] .stApp, [data-theme="light"] p, [data-theme="light"] h1, [data-theme="light"] h2, [data-theme="light"] h3, [data-theme="light"] h4, [data-theme="light"] h5, [data-theme="light"] h6, [data-theme="light"] label, [data-theme="light"] span {{ color: #111827 !important; }}
        [data-theme="light"] div[data-baseweb="select"], [data-theme="light"] div[data-baseweb="input"], [data-theme="light"] .stNumberInput input, [data-theme="light"] .stSelectbox div {{ background-color: #ffffff !important; color: #111827 !important; border: 1px solid #cbd5e1 !important; }}
        [data-theme="light"] div[data-baseweb="select"] *, [data-theme="light"] .stSelectbox span, [data-theme="light"] .stSelectbox div {{ color: #111827 !important; }}
        [data-theme="light"] .stNumberInput button {{ background-color: #f1f5f9 !important; color: #111827 !important; border: 1px solid #cbd5e1 !important; }}

        @media (prefers-color-scheme: dark) {{
            .stApp {{ background-color: rgba(15, 23, 42, {dark_alpha}) !important; background-blend-mode: overlay; }}
            .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label, .stApp span, .stApp li {{ color: #f3f4f6 !important; }}
            [data-testid="stSidebar"] {{ background-color: rgba(17, 24, 39, 0.95) !important; }}
            [data-testid="stSidebar"] * {{ color: #f3f4f6 !important; }}
            div[data-baseweb="select"], div[data-baseweb="input"], .stNumberInput input, .stSelectbox div {{ background-color: #1e293b !important; color: #ffffff !important; border: 1px solid #475569 !important; }}
            div[data-baseweb="select"] *, .stSelectbox span, .stSelectbox div {{ color: #ffffff !important; }}
            .stNumberInput button {{ background-color: #334155 !important; color: #ffffff !important; border: 1px solid #475569 !important; }}
            .stNumberInput button:hover {{ background-color: #475569 !important; }}
        }}
        [data-theme="dark"] .stApp {{ background-color: rgba(15, 23, 42, {dark_alpha}) !important; background-blend-mode: overlay; }}
        [data-theme="dark"] .stApp, [data-theme="dark"] p, [data-theme="dark"] h1, [data-theme="dark"] h2, [data-theme="dark"] h3, [data-theme="dark"] h4, [data-theme="dark"] h5, [data-theme="dark"] h6, [data-theme="dark"] label, [data-theme="dark"] span {{ color: #f3f4f6 !important; }}
        [data-theme="dark"] div[data-baseweb="select"], [data-theme="dark"] div[data-baseweb="input"], [data-theme="dark"] .stNumberInput input, [data-theme="dark"] .stSelectbox div {{ background-color: #1e293b !important; color: #ffffff !important; border: 1px solid #475569 !important; }}
        [data-theme="dark"] div[data-baseweb="select"] *, [data-theme="dark"] .stSelectbox span, [data-theme="dark"] .stSelectbox div {{ color: #ffffff !important; }}
        [data-theme="dark"] .stNumberInput button {{ background-color: #334155 !important; color: #ffffff !important; border: 1px solid #475569 !important; }}
        </style>
        """,
        unsafe_allow_html=True
    )
else:
    st.sidebar.warning(f"⚠️ Local background image not found at `{LOCAL_IMAGE_PATH}`.")

# -------------------------------------------------------------------------------
# STATE MANAGER & ACTIONS
# -------------------------------------------------------------------------------
st_autorefresh(interval=REFRESH_MS, key="weather_hub_refresh")

st.title("⛈️ Weather, Air Quality & GRIB Analysis")
st.markdown("Plan Better with Smarter Weather ☔")

if "lat" not in st.session_state: st.session_state.lat = 19.076
if "lon" not in st.session_state: st.session_state.lon = 72.878
if "city_select" not in st.session_state: st.session_state.city_select = "Kochi, India"

def on_city_change():
    chosen = st.session_state.city_select
    if chosen != "Custom Location":
        st.session_state.lat, st.session_state.lon = MAJOR_CITIES[chosen]

def sync_city_dropdown():
    st.session_state.city_select = "Custom Location"
    for city, coords in MAJOR_CITIES.items():
        if coords and round(coords[0], 3) == round(st.session_state.lat, 3) and round(coords[1], 3) == round(st.session_state.lon, 3):
            st.session_state.city_select = city
            break

# -------------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------------------------
st.sidebar.header("📍 Location Navigator")
st.sidebar.selectbox("🌆 Quick Select Station", options=list(MAJOR_CITIES.keys()), key="city_select", on_change=on_city_change)

col1, col2 = st.sidebar.columns(2)
with col1: lat_input = st.number_input("Lat (°N)", min_value=-90.0, max_value=90.0, step=0.001, format="%.3f", value=st.session_state.lat)
with col2: lon_input = st.number_input("Lon (°E)", min_value=-180.0, max_value=180.0, step=0.001, format="%.3f", value=st.session_state.lon)

if lat_input != st.session_state.lat or lon_input != st.session_state.lon:
    st.session_state.lat, st.session_state.lon = lat_input, lon_input
    sync_city_dropdown()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🗺️ Map Target Picker")

m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=5)
folium.Marker([st.session_state.lat, st.session_state.lon], popup="Monitored Station", tooltip="Active Target Node").add_to(m)

map_data = st_folium(m, height=220, width=None, key="sidebar_map_selector", returned_objects=["last_clicked"])

if map_data and map_data.get("last_clicked"):
    clicked_lat = round(map_data["last_clicked"]["lat"], 3)
    clicked_lon = round(map_data["last_clicked"]["lng"], 3)
    if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
        st.session_state.lat, st.session_state.lon = clicked_lat, clicked_lon
        sync_city_dropdown()
        st.rerun()

DAYS = st.sidebar.slider("Forecast Lookahead Horizon", min_value=1, max_value=10, value=7)

# -------------------------------------------------------------------------------
# DATA PROCESSING PIPELINES (API FETCHERS)
# -------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_location_name(lat, lon):
    try:
        if st.session_state.city_select != "Custom Location":
            return st.session_state.city_select
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

@st.cache_data(show_spinner="Parsing Primary GRIB2 Data Matrix...")
def process_grib_data_pure(file_path):
    with xr.open_dataset(file_path, engine="cfgrib") as ds:
        var_name = str(list(ds.data_vars)[0])
        
        def clean_date(t):
            try:
                v = pd.to_datetime(t)
                return v.item().strftime("%Y-%m-%d %H:%M UTC") if hasattr(v, 'item') else v.strftime("%Y-%m-%d %H:%M UTC")
            except:
                return str(t)
                
        forecast_time_str = clean_date(ds.time.values)
        valid_time_str = clean_date(ds.valid_time.values)
        
        region = ds.sel(latitude=slice(38, 5), longitude=slice(65, 98))
        
        raw_values = np.array(region[var_name].values, dtype=np.float64)
        lats = np.array(region.latitude.values, dtype=np.float64)
        lons = np.array(region.longitude.values, dtype=np.float64)
        
        if var_name == "tp":
            raw_values = raw_values * 1000.0
            units = "mm"
        else:
            units = str(region[var_name].attrs.get("units", ""))

    lon2d, lat2d = np.meshgrid(lons, lats)
    
    return {
        "lon2d": lon2d,
        "lat2d": lat2d,
        "data_vals": raw_values,
        "units": units,
        "f_time": forecast_time_str,
        "v_time": valid_time_str
    }

location_name = get_location_name(st.session_state.lat, st.session_state.lon)

# -------------------------------------------------------------------------------
# WORKSPACE LAYOUT & GRAPHICS RENDERING
# -------------------------------------------------------------------------------
tab_home, tab_meteogram, tab_grib_analysis = st.tabs(["🏡 Home", "📈 Meteogram", "Rainfall"])

# --- 1. HOME TAB ---
with tab_home:
    st.subheader(f"📍 {location_name}")
    st.write(f"Coordinates: `{st.session_state.lat}°N, {st.session_state.lon}°E` | Updated at: {datetime.datetime.now().strftime('%H:%M:%S Local')}")
    
    live_weather, live_aqi = fetch_live_metrics(st.session_state.lat, st.session_state.lon), fetch_air_quality(st.session_state.lat, st.session_state.lon)
    forecast_alert_df = fetch_weather_data(st.session_state.lat, st.session_state.lon, 1, "ecmwf_ifs025")

    if live_weather and live_aqi:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("🌡️ Surface Temperature", f"{live_weather['temperature_2m']} °C")
        with c2: st.metric("💧 Relative Humidity", f"{live_weather['relative_humidity_2m']} %")
        with c3: st.metric("💨 Wind Velocity", f"{live_weather['wind_speed_10m'] / 3.6:.1f} m/s")
        with c4: st.metric("🌧️ Current Gauge Rainfall", f"{live_weather['precipitation']} mm")

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

# --- 2. METEOGRAM TAB (UPDATED & WORKING) ---
with tab_meteogram:
    st.subheader(f"📈 High-Resolution Meteogram — {location_name}")
    
tab_ecmwf, tab_gfs = st.tabs(["EU ECMWF IFS (0.25°)", "US GFS Seamless"])

models_config = {
    "ECMWF": {"api_id": "ecmwf_ifs025", "title": "ECMWF IFS", "tab": tab_ecmwf},
    "GFS": {"api_id": "gfs_seamless", "title": "GFS Seamless", "tab": tab_gfs}
}

# Generate charts inside their respective tabs
for model_key, config in models_config.items():
    with config["tab"]:
        st.subheader(f"📈 High-Resolution Meteogram ({config['title']}) — {location_name}")
        
        with st.spinner(f"Extracting time-series arrays and generating {config['title']} charts..."):
            df_hourly = fetch_weather_data(st.session_state.lat, st.session_state.lon, DAYS, config["api_id"])
            
            if df_hourly is not None and not df_hourly.empty:
                try:
                    fig_meteo, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
                    
                    # Enforce total dark-app theme transparency
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

                    # Chart 1: Temperature & Dew Point
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

                    # Chart 2: Precipitation
                    ax2.bar(df_hourly["time"], df_hourly["precipitation"], color="#2563eb", width=0.03, label="Hourly Rain (mm)")
                    ax2.set_ylabel("Precipitation (mm)", weight='bold')
                    ax2.legend(loc="upper right", framealpha=0.1, labelcolor="white")

                    # Chart 3: Wind Vectors (Converted from km/h to m/s)
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
    st.subheader("Rainfall Forecast")
    
    if not os.path.exists(GRIB_FILE_PATH):
        st.error(f"GRIB dataset targets missing at destination: `{GRIB_FILE_PATH}`")
    elif not os.path.exists(SHAPEFILE_PATH):
        st.error(f"State boundary metrics missing at destination: `{SHAPEFILE_PATH}`")
    else:
        with st.spinner("Extracting parameters and plotting grid coordinates via Basemap..."):
            try:
                grib_payload = process_grib_data_pure(GRIB_FILE_PATH)
                
                lon2d = grib_payload["lon2d"]
                lat2d = grib_payload["lat2d"]
                data_vals = grib_payload["data_vals"]
                units = grib_payload["units"]
                f_time = grib_payload["f_time"]
                v_time = grib_payload["v_time"]
                
                india_gdf = gpd.read_file(SHAPEFILE_PATH)
                if india_gdf.crs is not None:
                    india_gdf = india_gdf.to_crs(epsg=4326)
                
                fig_grib, ax = plt.subplots(figsize=(12, 10))

                # Transparent background layout matching
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
                
                levels = [0, 0.1, 1, 2.5, 5, 10, 20, 35, 50, 75]
                
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*collections attribute was deprecated.*")
                    cf = m.contourf(
                        lon2d, lat2d, data_vals,
                        levels=levels, cmap="Greens", extend="max", latlon=True
                    )
                
                india_gdf.boundary.plot(ax=ax, edgecolor='black', linewidth=0.8, zorder=100, alpha=0.6)
  
                cbar = plt.colorbar(cf, pad=0.04, shrink=0.8)
                cbar.set_label(units, color='white', weight='bold', fontsize=11)
                cbar.ax.yaxis.set_tick_params(color='white', labelcolor='white', labelsize=10)
                cbar.outline.set_edgecolor('white')
                cbar.outline.set_linewidth(1.0)
                
                plt.title(
                    f"ECMWF Total Precipitation\nForecast Run: {f_time}  |  Valid Time: {v_time}",
                    fontsize=13, weight="bold", color="white", pad=15
                )
                plt.tight_layout()
                
                st.pyplot(fig_grib, clear_figure=True)
                
            except Exception as e:
                st.error(f"Failed to process target files. Error trace: {str(e)}")
