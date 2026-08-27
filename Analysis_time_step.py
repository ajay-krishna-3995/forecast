import numpy as np
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
from scipy.interpolate import PchipInterpolator

# 1. API Client Setup
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# 2. API Call (Fixed model identifier: "ecmwf_ifs")
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": 24,
    "longitude": 69,
    "hourly": ["wind_speed_80m", "wind_direction_80m"],
    "models": "ecmwf_ifs",  # FIXED: Correct ECMWF model name
    "forecast_days": 1,
    "wind_speed_unit": "ms"
}

responses = openmeteo.weather_api(url, params=params)
response = responses[0]

# 3. Extract Hourly Time Series
hourly = response.Hourly()
speed_h = hourly.Variables(0).ValuesAsNumpy()
dir_h = hourly.Variables(1).ValuesAsNumpy()

# Generate hourly timestamps
time_start = pd.to_datetime(hourly.Time(), unit="s", utc=True)
time_end = pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True)
times_h = pd.date_range(start=time_start, end=time_end, freq="1h", inclusive="left")

# 4. Decompose into U and V components
rad = np.radians(dir_h)
u_h = -speed_h * np.sin(rad)
v_h = -speed_h * np.cos(rad)

# 5. Direct Scipy PCHIP Downscaling to 15-Minute Grid
times_15m = pd.date_range(start=time_start, end=times_h[-1], freq="15min")

# Convert timestamps to numeric hours for interpolation
x_h = (times_h - time_start).total_seconds() / 3600.0
x_15m = (times_15m - time_start).total_seconds() / 3600.0

# Fit PCHIP models directly on numeric arrays
pchip_u = PchipInterpolator(x_h, u_h)
pchip_v = PchipInterpolator(x_h, v_h)

u_15m = pchip_u(x_15m)
v_15m = pchip_v(x_15m)

# 6. Reconstruct Speed & Direction
speed_15m = np.round(np.sqrt(u_15m**2 + v_15m**2), 2)
dir_15m = np.round((np.degrees(np.arctan2(-u_15m, -v_15m)) + 360) % 360, 2)

# Build Final Clean DataFrame
df_15m = pd.DataFrame({
    'time': times_15m,
    'u': np.round(u_15m, 3),
    'v': np.round(v_15m, 3),
    'wind_speed_80m': speed_15m,
    'wind_direction_80m': dir_15m
})

# Save to CSV
df_15m.to_csv("downscaled_wind_15min.csv", index=False)

print("Data successfully generated without NaNs!")
print(df_15m.head(10))