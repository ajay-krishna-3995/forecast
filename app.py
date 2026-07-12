import streamlit as st
import requests

st.set_page_config(page_title="Weather Forecast", layout="wide")

st.title("🌤️ Weather Forecast")

# Your API logic here
col1, col2 = st.columns(2)

with col1:
    location = st.text_input("Enter your location:", "New York")

if location:
    st.write(f"Loading weather forecast for {location}...")
    # Add your API calls here