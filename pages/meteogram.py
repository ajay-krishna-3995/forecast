import datetime
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from matplotlib.colors import BoundaryNorm, ListedColormap
from scipy.ndimage import gaussian_filter


def fetch_weather_data(lat, lon, days):
    """
    Fetch hourly forecast data from Open-Meteo ECMWF IFS model.
    Uses exactly 5 low-level wind profiles natively supported by the API.
    """
    base_url = "https://api.open-meteo.com/v1/forecast"
    
    # Exactly 5 native low levels from surface up to the lower atmosphere
    low_levels = ["10m", "100m", "1000hPa", "180m", "200m"]
    
    hourly_vars = [
        "temperature_2m",
        "dew_point_2m",
        "relative_humidity_2m",
        "pressure_msl",
        "cape",
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "precipitation",
    ]
    
    # Dynamically bundle the speed and direction for each requested level
    for lvl in low_levels:
        hourly_vars.append(f"wind_speed_{lvl}")
        hourly_vars.append(f"wind_direction_{lvl}")

    params = {
        "latitude": lat,
        "longitude": lon,
        "models": "ecmwf_ifs025",
        "hourly": hourly_vars,
        "forecast_days": days,
        "timezone": "auto",
    }

    response = requests.get(base_url, params=params)
    response.raise_for_status()
    j = response.json()
    if "hourly" not in j:
        raise ValueError("Could not find 'hourly' data block in API response.")

    df = pd.DataFrame(j["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df


def generate_meteogram_fig(df, lat, lon, days):
    """
    Generates a production-grade forecast meteogram featuring a clean 
    5-level low wind profile chart.
    """
    fig, axs = plt.subplots(
        7, 1, figsize=(15, 20), sharex=True, 
        gridspec_kw={"height_ratios": [1, 1, 2.5, 1, 1.2, 2.5, 1]}
    )
    plt.subplots_adjust(left=0.18, right=0.95, top=0.94, bottom=0.06, hspace=0.22)

    fig.suptitle(
        f"ECMWF IFS Model {days}-Day Forecast Meteogram\nLocation: ({lon}°E, {lat}°N)", 
        fontsize=16, weight="bold", color="#1a1a1a"
    )

    time_nums = mdates.date2num(df["time"])
    label_font = {"weight": "bold", "fontsize": 12}

    # ----------------------------------------------------
    # PANEL 1: Sea Level Pressure (SLP)
    # ----------------------------------------------------
    axs[0].plot(df["time"], df["pressure_msl"], color="#0055ff", linewidth=2.5)
    axs[0].set_ylabel("SLP\n(hPa)", color="#0055ff", **label_font)
    axs[0].tick_params(axis='y', labelcolor="#0055ff", labelsize=10)

    # ----------------------------------------------------
    # PANEL 2: CAPE
    # ----------------------------------------------------
    axs[1].bar(df["time"], df["cape"], width=0.03, color="#993399", alpha=0.7)
    axs[1].set_ylabel("CAPE\n(J/kg)", color="#993399", **label_font)
    axs[1].tick_params(axis='y', labelcolor="#993399", labelsize=10)

    # ----------------------------------------------------
    # PANEL 3: 5 LOW-LEVEL WIND PROFILE BARBS
    # ----------------------------------------------------
    ax_wind = axs[2]
    
    # Target levels matched precisely with what was fetched in API
    api_levels = ["10m", "100m", "1000hPa", "180m", "200m"]
    display_labels = ["10m (Surface)", "100m", "1000 hPa (~110m)", "180m", "200m"]
    
    # Skips every 3 hours to prevent overlapping crowded barbs
    skip = 3
    barb_times = time_nums[::skip]

    for idx, lvl_str in enumerate(api_levels):
        speed_col = f"wind_speed_{lvl_str}"
        dir_col = f"wind_direction_{lvl_str}"
        
        if speed_col in df.columns and dir_col in df.columns:
            # Convert km/h to m/s for plotting standard meteorological barbs
            speeds_ms = df[speed_col].fillna(0).astype(float).iloc[::skip] / 3.6
            dirs = df[dir_col].fillna(0).astype(float).iloc[::skip]
        else:
            continue
        
        rad = np.deg2rad(dirs)
        u_vec = -speeds_ms * np.sin(rad)
        v_vec = -speeds_ms * np.cos(rad)
        
        y_pos = np.full_like(barb_times, idx)
        ax_wind.barbs(barb_times, y_pos, u_vec, v_vec, length=6.5, color="#2c3e50", linewidth=1.0)

    ax_wind.set_yticks(range(len(api_levels)))
    ax_wind.set_yticklabels(display_labels, fontsize=10)
    ax_wind.set_ylabel("Wind Profile\n(Low Levels)", color="#ff7700", **label_font)
    ax_wind.tick_params(axis='y', labelcolor="#2c3e50")
    ax_wind.set_ylim(-0.5, len(api_levels) - 0.5)

    # ----------------------------------------------------
    # PANEL 4: 2m Relative Humidity
    # ----------------------------------------------------
    axs[3].plot(df["time"], df["relative_humidity_2m"], color="#00aa00", linewidth=2)
    axs[3].fill_between(df["time"], df["relative_humidity_2m"], 50, where=(df["relative_humidity_2m"] >= 50),
                        color="#00cc00", alpha=0.5, interpolate=True)
    axs[3].fill_between(df["time"], df["relative_humidity_2m"], 50, where=(df["relative_humidity_2m"] < 50),
                        color="#aaffaa", alpha=0.3, interpolate=True)
    axs[3].set_ylabel("2m RH\n(%)", color="#00aa00", **label_font)
    axs[3].set_ylim(0, 100)
    axs[3].tick_params(axis='y', labelsize=10)

    # ----------------------------------------------------
    # PANEL 5: 2m Temperature & Dew Point
    # ----------------------------------------------------
    axs[4].plot(df["time"], df["temperature_2m"], color="#d32f2f", linewidth=2.5, label="2m Temp")
    axs[4].plot(df["time"], df["dew_point_2m"], color="#1976d2", linewidth=1.5, linestyle="-.", label="Dew Pt")
    axs[4].fill_between(df["time"], df["temperature_2m"], df["temperature_2m"].min() - 2, color="#ff9800", alpha=0.25)
    axs[4].set_ylabel("Temp / DewPt\n(°C)", color="#d32f2f", **label_font)
    axs[4].legend(loc="upper right", fontsize=10, framealpha=0.7)
    axs[4].tick_params(axis='y', labelsize=10)

    # ----------------------------------------------------
    # PANEL 6: CLOUD COVER METRIC PROFILE
    # ----------------------------------------------------
    ax_cloud = axs[5]
    num_time_steps = len(df["time"])
    alt_grid = np.linspace(0, 14, 100)
    cloud_matrix = np.zeros((len(alt_grid), num_time_steps))

    for t in range(num_time_steps):
        low = df["cloud_cover_low"].iloc[t]
        mid = df["cloud_cover_mid"].iloc[t]
        high = df["cloud_cover_high"].iloc[t]

        layer_profile = (
            low * np.exp(-((alt_grid - 1.2) / 1.2) ** 2)
            + mid * np.exp(-((alt_grid - 5.0) / 2.5) ** 2)
            + high * np.exp(-((alt_grid - 10.0) / 3.0) ** 2)
        )
        cloud_matrix[:, t] = np.clip(layer_profile, 0, 100)

    cloud_matrix_smooth = gaussian_filter(cloud_matrix, sigma=(1.2, 0.8))

    cloud_colors = ["#ffffff", "#f0f2f5", "#d1d5db", "#9ca3af", "#6b7280", "#374151"]
    cloud_bounds = [0, 10, 30, 50, 70, 90, 100]
    cmap_cloud = ListedColormap(cloud_colors)
    norm_cloud = BoundaryNorm(cloud_bounds, cmap_cloud.N)

    cloud_contour = ax_cloud.contourf(
        time_nums, alt_grid, cloud_matrix_smooth,
        levels=cloud_bounds, cmap=cmap_cloud, norm=norm_cloud, extend='max'
    )

    ax_cloud.set_ylim(0, 14)
    ax_cloud.set_ylabel("Altitude\n(km)", **label_font)
    ax_cloud.tick_params(axis='y', labelsize=10)
    
    cbar_ax = fig.add_axes([0.04, 0.20, 0.02, 0.10])
    cbar = fig.colorbar(cloud_contour, cax=cbar_ax, orientation='vertical', ticks=cloud_bounds)
    cbar.ax.set_title("Cloud %", fontsize=9, weight="bold", pad=8)
    cbar.ax.tick_params(labelsize=8)

    ax_cloud.text(time_nums[0], 1.2, " Low-Level", fontsize=9, color="#111827", weight="bold", va="center")
    ax_cloud.text(time_nums[0], 5.0, " Mid-Level", fontsize=9, color="#111827", weight="bold", va="center")
    ax_cloud.text(time_nums[0], 10.0, " High-Level", fontsize=9, color="#111827", weight="bold", va="center")

    # ----------------------------------------------------
    # PANEL 7: Precipitation
    # ----------------------------------------------------
    axs[6].bar(df["time"], df["precipitation"], width=0.03, color="#00b0ff", edgecolor="#0091ea")
    axs[6].set_ylabel("Precip\n(mm)", color="#0091ea", **label_font)
    axs[6].tick_params(axis='y', labelsize=10)
    
    total_precip = df["precipitation"].sum()
    axs[6].text(0.98, 0.70, f"{days}-Day Total = {total_precip:.1f} mm", 
                transform=axs[6].transAxes, ha="right", weight="bold", color="#0077c2", fontsize=11)

    # ----------------------------------------------------
    # GLOBAL TIMELINE FORMATTING
    # ----------------------------------------------------
    axs[-1].xaxis.set_major_locator(mdates.DayLocator())
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n(%a)"))

    for ax in axs:
        ax.grid(True, which="major", axis="x", color="#aaaaaa", linestyle="--", linewidth=0.8, alpha=0.6)
        if ax != ax_cloud and ax != ax_wind:
            ax.grid(True, which="major", axis="y", color="#e0e0e0", linestyle=":", alpha=0.5)
        
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis='x', labelsize=11)

    return fig


if __name__ == "__main__":
    lat, lon, days = 9.605, 77.17, 3
    print(f"Fetching 5 low-level wind variables for location ({lat}, {lon})...")
    df = fetch_weather_data(lat, lon, days)
    fig = generate_meteogram_fig(df, lat, lon, days)
    fig.savefig("meteogram_multi_level.png", dpi=200)
    print("Successfully generated plot with actual wind barbs!")
