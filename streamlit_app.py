import base64
import datetime
import io
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
    page_title="Map Popup Weather Meteogram",
    page_icon="⛈️",
    layout="wide"
)

# Keep app updated every 1 minute
st_autorefresh(interval=60000, key="meteogram_popup_refresh")

st.title("⛈️ Interactive Map Meteograms")
st.markdown("Click on the map or markers to generate and display the embedded weather forecast meteograms.")

# -------------------------------------------------------------------------------
# 2. STATE MANAGEMENT & CONTROLS
# -------------------------------------------------------------------------------
if "lat" not in st.session_state:
    st.session_state.lat = 9.605
if "lon" not in st.session_state:
    st.session_state.lon = 77.170

st.sidebar.header("Forecast Configurations")
DAYS = st.sidebar.slider("Forecast Days", min_value=1, max_value=10, value=7) # Defaulting to 7 for cleaner popups
st.sidebar.info(f"📍 **Active Center:** {st.session_state.lat}°N, {st.session_state.lon}°E")

# -------------------------------------------------------------------------------
# 3. CACHED DATA FETCHING
# -------------------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
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
    try:
        response = requests.get(base_url, params=params).json()
        if "hourly" not in response:
            return None
        df = pd.DataFrame(response["hourly"])
        df["time"] = pd.to_datetime(df["time"])
        return df
    except Exception:
        return None

# -------------------------------------------------------------------------------
# 4. PLOT ENGINE & CONVERSION UTILITIES
# -------------------------------------------------------------------------------
def fig_to_base64(fig):
    """Converts a matplotlib figure into a base64 string for HTML injection."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    base64_string = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig) # Avoid memory leakage
    return base64_string

def generate_meteogram_figure(df, model_title, lat, lon):
    """Builds the exact matplotlib figure and returns it object-oriented."""
    fig, axs = plt.subplots(
        7, 1, figsize=(11, 13), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1, 1, 1, 2.5, 1.2]}
    )
    plt.subplots_adjust(left=0.15, right=0.90, top=0.94, bottom=0.06, hspace=0.4)

    axs[0].set_title(f"{model_title} ({lon}E, {lat}N)", fontsize=12, weight="bold")

    # PANEL 1: Sea Level Pressure
    axs[0].plot(df["time"], df["pressure_msl"], color="blue")
    axs[0].set_ylabel("SLP\n(hPa)", color="blue", fontsize=9)

    # PANEL 2: CAPE
    axs[1].bar(df["time"], df["cape"], width=0.03, color="purple", alpha=0.6)
    axs[1].set_ylabel("CAPE\n(J/kg)", color="purple", fontsize=9)

    # PANEL 3: Wind
    axs[2].plot(df["time"], df["wind_speed_10m"] / 3.6, color="orange", label="Wind")
    axs[2].plot(df["time"], df["wind_gusts_10m"] / 3.6, color="crimson", linestyle=":", label="Gust")
    axs[2].set_ylabel("Wind\n(m/s)", fontsize=9)
    axs[2].legend(loc="upper right", fontsize=7)

    # PANEL 4: Humidity
    axs[3].plot(df["time"], df["relative_humidity_2m"], color="green")
    axs[3].fill_between(df["time"], df["relative_humidity_2m"], 0, color="limegreen", alpha=0.3)
    axs[3].set_ylabel("2m RH\n (%)", fontsize=9)
    axs[3].set_ylim(0, 100)

    # PANEL 5: Temperature
    axs[4].plot(df["time"], df["temperature_2m"], color="red", linewidth=2)
    axs[4].set_ylabel("Temp\n(°C)", color="red", weight="bold", fontsize=9)

    # PANEL 6: Cloud Cover Profile
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
    ax_cloud.set_ylim(0, 14)
    ax_cloud.set_ylabel("Altitude\n(km)", color="black", fontsize=9)

    for height in [1.5, 3.5, 6.0, 9.0]:
        ax_cloud.axhline(height, color="dimgray", linestyle=":", linewidth=0.8, alpha=0.6)
    
    ax_cloud.text(time_numbers[0], 1.0, "Low", fontsize=7, color="black", weight="bold")
    ax_cloud.text(time_numbers[0], 4.5, "Mid", fontsize=7, color="black", weight="bold")
    ax_cloud.text(time_numbers[0], 9.5, "High", fontsize=7, color="black", weight="bold")

    # PANEL 7: Precipitation
    axs[6].bar(df["time"], df["precipitation"], width=0.04, color="lightgreen")
    axs[6].set_ylabel("Precip\n(mm)", fontsize=9)

    # Date formatting layout
    axs[-1].xaxis.set_major_locator(mdates.DayLocator())
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d\n%b"))

    for ax in axs:
        ax.tick_params(axis='both', which='major', labelsize=8)
        ax.grid(True, which="major", axis="x", color="grey", linestyle="--", alpha=0.3)
        if ax != ax_cloud:
            ax.grid(True, which="major", axis="y", color="lightgrey", linestyle=":", alpha=0.4)

    return fig

# -------------------------------------------------------------------------------
# 5. CORE MAP PROCESSING LOOP
# -------------------------------------------------------------------------------
models_config = {
    "ECMWF": {"api_id": "ecmwf_ifs025", "title": "ECMWF IFS", "color": "blue"},
    "GFS": {"api_id": "gfs_seamless", "title": "GFS Seamless", "color": "green"}
}

# Base Folium setup
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=4)

with st.spinner("Processing local meteogram frames..."):
    for model_key, cfg in models_config.items():
        # Fetch the dataframe 
        df = fetch_weather_data(st.session_state.lat, st.session_state.lon, DAYS, cfg["api_id"])
        
        if df is not None:
            # 1. Compile chart graphics
            fig = generate_meteogram_figure(df, cfg["title"], st.session_state.lat, st.session_state.lon)
            b64_img = fig_to_base64(fig)
            
            # 2. Build HTML construction payload 
            html_popup = f"""
            <div style="width:720px; font-family: sans-serif;">
                <h4 style="margin-bottom:2px; color:#333;">{cfg["title"]} Forecast Frame</h4>
                <p style="font-size:11px; color:#666; margin-top:0px;">Auto-generated interactive view via Open-Meteo</p>
                <img src="data:image/png;base64,{b64_img}" width="100%" style="border-radius:4px; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">
            </div>
            """
            
            # 3. Bind popup properties directly into explicit location marker
            iframe = folium.IFrame(html_popup, width=750, height=550)
            popup = folium.Popup(iframe, max_width=750)
            
            # Shift coordinates slightly if plotting both models so they don't hide each other
            offset = 0.15 if model_key == "GFS" else 0.0
            
            folium.Marker(
                location=[st.session_state.lat, st.session_state.lon + offset],
                popup=popup,
                tooltip=f"Click to open {cfg['title']} Meteogram",
                icon=folium.Icon(color=cfg["color"], icon="cloud")
            ).add_to(m)

# -------------------------------------------------------------------------------
# 6. RENDER INTERACTIVE MAP IN STREAMLIT
# -------------------------------------------------------------------------------
map_data = st_folium(m, height=600, width=None, key="main_map_selector")

# Capture map click coordinate re-routing actions
if map_data and map_data.get("last_clicked"):
    clicked_lat = round(map_data["last_clicked"]["lat"], 3)
    clicked_lon = round(map_data["last_clicked"]["lng"], 3)
    
    if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
        st.session_state.lat = clicked_lat
        st.session_state.lon = clicked_lon
        st.rerun()
