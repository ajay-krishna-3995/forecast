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
    Returns a pandas DataFrame with a parsed 'time' column or raises ValueError on failure.
    """
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "models": "ecmwf_ifs025",
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
    Generate a matplotlib Figure containing the meteogram from a dataframe.
    Returns (fig, axs).
    """
    fig, axs = plt.subplots(
        7, 1, figsize=(14, 18), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1, 1, 1, 2.8, 1.2]}
    )

    # Layout adjustments
    plt.subplots_adjust(left=0.18, right=0.92, top=0.95, bottom=0.05, hspace=0.35)

    axs[0].set_title(
        f"ECMWF IFS {days}-day Forecast Meteogram for ({lon}E, {lat}N)", fontsize=14, weight="bold"
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
            low * np.exp(-((alt_grid - 1.0) / 1.2) ** 2)
            + mid * np.exp(-((alt_grid - 4.5) / 2.5) ** 2)
            + high * np.exp(-((alt_grid - 9.5) / 3.0) ** 2)
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

    # PANEL 7: 3hr Precipitation
    axs[6].bar(df["time"], df["precipitation"], width=0.04, color="lightgreen", label="Precip")
    axs[6].set_ylabel("Precip\n(mm)")
    total_precip = df["precipitation"].sum()
    axs[6].text(0.95, 0.85, f"{days}-Day Total = {total_precip:.2f} mm", transform=axs[6].transAxes, ha="right", weight="bold")

    # Global Axis Setup
    axs[-1].xaxis.set_major_locator(mdates.DayLocator())
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d\n%b"))

    for ax in axs:
        ax.grid(True, which="major", axis="x", color="grey", linestyle="--", alpha=0.4)
        if ax != ax_cloud:
            ax.grid(True, which="major", axis="y", color="lightgrey", linestyle=":", alpha=0.5)

    return fig


if __name__ == "__main__":
    # Simple CLI test when running as a script
    import sys
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 9.605
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 77.17
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    print(f"Fetching data for {lat}, {lon} for {days} days...")
    df = fetch_weather_data(lat, lon, days)
    fig = generate_meteogram_fig(df, lat, lon, days)
    fig.savefig("meteogram_preview.png")
    print("Saved meteogram_preview.png")
