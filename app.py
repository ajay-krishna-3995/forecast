import streamlit as st
import subprocess
import sys
import tempfile
from pathlib import Path

st.set_page_config(page_title="Forecast App", page_icon="⛈️", layout="wide")
st.title("⛈️ Forecast - Select a view")

# Controls
lat = st.sidebar.number_input("Latitude", min_value=-90.0, max_value=90.0, value=9.605, step=0.001, format="%.3f")
lon = st.sidebar.number_input("Longitude", min_value=-180.0, max_value=180.0, value=77.17, step=0.001, format="%.3f")
days = st.sidebar.slider("Forecast Days", min_value=1, max_value=10, value=3)
view = st.sidebar.selectbox("Choose page", ["Home", "Meteogram", "Monsoon"])

# Prepare output directory for workers
out_dir = Path(tempfile.gettempdir()) / "forecast_app"
out_dir.mkdir(parents=True, exist_ok=True)

PY = sys.executable


def run_worker(cmd):
    """Run a worker subprocess and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


if view == "Home":
    out_file = out_dir / "home_summary.json"
    cmd = [PY, "pages/home.py", str(lat), str(lon), str(days), str(out_file)]
    with st.spinner("Loading Home..."):
        rc, out, err = run_worker(cmd)
    if rc != 0:
        st.error("Home worker failed:\n" + err)
    else:
        st.success("Home loaded")
        # Try to display file content if it exists
        try:
            import json
            text = Path(out_file).read_text()
            data = json.loads(text)
            st.json(data)
        except Exception:
            st.text(out)

elif view == "Meteogram":
    out_png = out_dir / "meteogram_preview.png"
    cmd = [PY, "pages/meteogram.py", str(lat), str(lon), str(days), str(out_png)]
    with st.spinner("Generating Meteogram... This may take a moment."):
        rc, out, err = run_worker(cmd)
    if rc != 0:
        st.error("Meteogram worker failed:\n" + err)
    else:
        if out_png.exists():
            st.image(str(out_png), caption="Meteogram", use_column_width=True)
            st.success("Meteogram generated")
        else:
            st.warning("Meteogram script completed but output PNG not found. stdout:\n" + out)

elif view == "Monsoon":
    out_file = out_dir / "monsoon_summary.txt"
    cmd = [PY, "pages/monsoon.py", str(lat), str(lon), str(days), str(out_file)]
    with st.spinner("Running Monsoon analysis..."):
        rc, out, err = run_worker(cmd)
    if rc != 0:
        st.error("Monsoon worker failed:\n" + err)
    else:
        st.success("Monsoon analysis completed")
        try:
            st.text(Path(out_file).read_text())
        except Exception:
            st.text(out)
