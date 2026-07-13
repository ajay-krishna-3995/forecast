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
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------------------------------------
# 1. STREAMLIT PAGE SETUP
# -------------------------------------------------------------------------------
st.set_page_config(
    page_title="Weather, Air Quality & Monsoon",
    page_icon="⛈️",
    layout="wide"
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
    "Kochi, India" : (9.9312,76.2673),
    "London, UK": (51.507, -0.128),
    "New York, USA": (40.713, -74.006),
    "Tokyo, Japan": (35.689, 139.692),
    "Paris, France": (48.857, 2.352),
    "Sydney, Australia": (-33.869, 151.209),
    "São Paulo, Brazil": (-23.551, -46.633),
    "Cape Town, South Africa": (-33.925, 18.424)
    
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
    
    # 5 low levels natively supported by the Open-Meteo models
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
        
        # Convert wind speed from km/h to m/s
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
                    st.error(f"🔴 **CRITICAL RAINFALL ALERT:** Torrential output expected inside 24hrs ({total_24h_rain:.1f} mm total). High probability of extreme runoff or flash urban water collection.")
                elif total_24h_rain > 25 or peak_24h_rate > 8:
                    st.warning(f"🟡 **ADVISORY RAINFALL ALERT:** Moderately intense precipitation steps tracking nearby. Total 24h volume estimated near {total_24h_rain:.1f} mm.")
                elif total_24h_rain > 0.2:
                    st.info(f"🔵 **ROUTINE PRECIPITATION:** Light convective activity or intermittent monsoonal showers tracked. Expected footprint: {total_24h_rain:.1f} mm.")
                else:
                    st.success("🟢 **ZERO RAIN ALERT:** Clear pathing. No active measurable precipitation signals within the standard 24-hour diagnostic track.")
            else:
                st.info("Unable to parse predictive 24h precipitation profiles.")

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

            # PANEL 1: Sea Level Pressure
            axs[0].plot(df["time"], df["pressure_msl"], color="blue")
            axs[0].set_ylabel("SLP\n(hPa)", color="blue")

            # PANEL 2: CAPE
            axs[1].bar(df["time"], df["cape"], width=0.03, color="purple", alpha=0.6)
            axs[1].set_ylabel("CAPE\n(J/kg)", color="purple")

            # PANEL 3: 5-LEVEL WIND PROFILE BARBS
            ax_wind = axs[2]
            api_levels = ["10m", "100m", "1000hPa", "180m", "200m"]
            display_labels = ["10m (Surface)", "100m", "1000 hPa (~110m)", "180m", "200m"]
            
            time_numbers = mdates.date2num(df["time"])
            skip = 3  # Thins wind barbs every 3 hours to prevent overcrowding
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

            #ax_cloud.text(time_numbers[0] - 0.2, 1.0, "Low", fontsize=8, color="dimgray", weight="bold", ha="right", va="center")
            #ax_cloud.text(time_numbers[0] - 0.2, 4.5, "Mid", fontsize=8, color="dimgray", weight="bold", ha="right", va="center")
            #ax_cloud.text(time_numbers[0] - 0.2, 9.5, "High", fontsize=8, color="dimgray", weight="bold", ha="right", va="center")
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

            # PANEL 7: Precipitation
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
# C. TAB LAYOUT: MONSOON DIAGNOSTIC (HYDRO-CLIMATOLOGY MATRIX)
# ===============================================================================
with tab_monsoon:
    st.subheader(f"🌧️ Monsoon  (❌Page yet to update❌)")
    st.markdown(f"**Target Geography Context:** {location_name}")
    
    monsoon_df = fetch_weather_data(st.session_state.lat, st.session_state.lon, DAYS, "ecmwf_ifs025")
    
    if monsoon_df is not None:
        total_rain = monsoon_df["precipitation"].sum()
        max_hourly_intensity = monsoon_df["precipitation"].max()
        rainy_hours = (monsoon_df["precipitation"] > 0.1).sum()
        avg_cape = monsoon_df["cape"].mean()
        avg_rh = monsoon_df["relative_humidity_2m"].mean()
        
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Cumulative Mass Footprint", f"{total_rain:.1f} mm")
        m_col2.metric("Peak Precipitation Surge", f"{max_hourly_intensity:.1f} mm/h")
        m_col3.metric("Rain Event Intersections", f"{rainy_hours} hrs")
        m_col4.metric("Convective Base Instability", f"{avg_cape:.0f} J/kg")
        
        st.markdown("---")
        
        v_col1, v_col2 = st.columns([2, 1])
        
        with v_col1:
            st.markdown("##### 📈 Mass Accumulation Profile Curve")
            monsoon_df["accumulated_precip"] = monsoon_df["precipitation"].cumsum()
            
            fig_acc, ax_acc = plt.subplots(figsize=(10, 4.2))
            ax_acc.plot(monsoon_df["time"], monsoon_df["accumulated_precip"], color="teal", linewidth=2.5)
            ax_acc.fill_between(monsoon_df["time"], monsoon_df["accumulated_precip"], color="teal", alpha=0.15)
            ax_acc.set_ylabel("Accumulated Rain Mass (mm)", weight="bold")
            ax_acc.grid(True, linestyle=":", alpha=0.6)
            ax_acc.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
            plt.xticks(rotation=15)
            st.pyplot(fig_acc)
            
        with v_col2:
            st.markdown("##### ⛈️ Hydrologic Threat Status")
            if total_rain > 120 or max_hourly_intensity > 25:
                st.error("🚨 **High Runoff Alert:** Flash flood signals mapped via multi-hour high accumulation vectors. Local soil saturation threshold surpassed.")
            elif total_rain > 40 or max_hourly_intensity > 12:
                st.warning("⚠️ **Active Monsoonal Surcharge:** Active wet cycle with heavy individual convective bursts. Standard drainage networks will reach capacity.")
            elif total_rain > 5:
                st.info("ℹ️ **Standard Low-Intensity Showers:** Normal moisture movement. No extreme structural threat matrices present.")
            else:
                st.success("☀️ **Suppressed Moisture Feed:** Atmospheric air block or dry-slot tracking. Monsoonal convective cells completely suppressed.")
                
            st.markdown("##### 🌐 Instability Metrics")
            if avg_rh > 78 and avg_cape > 400:
                st.info("High low-level moisture tracking along active thermodynamic triggers; convective column is highly favorable for rapid cloud growth.")
            else:
                st.text("Atmospheric profile demonstrates structural stability or dry slotting limits.")
