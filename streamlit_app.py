import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Weather Forecast", layout="centered")

API_KEY = st.secrets.get("OPENWEATHER_API_KEY")  # set this in Streamlit Cloud secrets

@st.cache_data(ttl=600)
def fetch_forecast(city: str, api_key: str):
    if not api_key:
        raise ValueError("API key not set. Add OPENWEATHER_API_KEY to st.secrets.")
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": api_key, "units": "metric"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def json_to_df(j):
    rows = []
    for item in j.get("list", []):
        dt = datetime.fromtimestamp(item["dt"])
        rows.append({
            "dt": dt,
            "temp_C": item["main"]["temp"],
            "feels_like_C": item["main"]["feels_like"],
            "description": item["weather"][0]["description"],
            "wind_m_s": item["wind"]["speed"],
        })
    return pd.DataFrame(rows)

st.title("Weather Forecast")
st.write("Enter a city name (e.g., London, New York) to get a 5-day forecast.")

city = st.text_input("City", value="San Francisco")
if st.button("Get forecast"):
    try:
        with st.spinner("Fetching forecast..."):
            j = fetch_forecast(city.strip(), API_KEY)
        if j.get("cod") not in ("200", 200):
            st.error(f"API error: {j.get('message', j)}")
        else:
            df = json_to_df(j)
            st.subheader(f"Forecast for {j['city']['name']}, {j['city']['country']}")
            st.dataframe(df.set_index("dt"))
            # Simple plot
            st.line_chart(df.set_index("dt")["temp_C"])
    except requests.HTTPError as e:
        st.error(f"HTTP error: {e}")
    except ValueError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Unexpected error: {e}")
