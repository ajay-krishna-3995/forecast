# Weather Forecast

This is a Streamlit app that shows a weather forecast for a location.

## Run locally

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Add your OpenWeatherMap API key locally:

- Create `.streamlit/secrets.toml` with:

```toml
OPENWEATHER_API_KEY = "your_api_key_here"
```

- Or set environment variables and update the app to read them.

3. Run:

```bash
streamlit run streamlit_app.py
```

## Deploy to Streamlit Cloud

1. Push your repo to GitHub.
2. Go to https://share.streamlit.io and connect your GitHub account.
3. Select this repository and the file `streamlit_app.py` as the entrypoint.
4. In the Streamlit app settings, add a secret named `OPENWEATHER_API_KEY` with your API key.
5. Deploy.

Notes
- Do NOT commit API keys to the repo. Use Streamlit Cloud secrets.
- Adjust `fetch_forecast` if you prefer another weather provider or to request lat/lon instead.
