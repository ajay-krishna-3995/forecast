# uploader.py
import tempfile
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import xarray as xr


def format_coord_value(val):
    if pd.isna(val):
        return "N/A"

    if isinstance(val, (np.timedelta64, pd.Timedelta)):
        total_seconds = pd.Timedelta(val).total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        return f"+{hours}h {minutes}m" if minutes > 0 else f"+{hours}h (Step {hours})"

    if isinstance(val, (int, float, np.integer, np.floating)):
        if abs(val) > 1e9:
            total_seconds = val / 1e9
            hours = int(total_seconds // 3600)
            return f"+{hours}h"
        return f"{val:.2f}" if isinstance(val, float) else str(val)

    try:
        ts = pd.to_datetime(val)
        return ts.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(val)


def render_custom_dataset_uploader():
    st.subheader("📂 Interactive NetCDF / GRIB Spatial Data Visualizer")

    uploaded_file = st.file_uploader(
        "Upload a .nc, .nc4, or .grib2 file", type=["nc", "nc4", "grib", "grib2"]
    )

    if uploaded_file is not None:
        suffix = f".{uploaded_file.name.split('.')[-1]}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            engine = "cfgrib" if "grib" in suffix.lower() else "netcdf4"
            ds = xr.open_dataset(tmp_path, engine=engine)

            st.success(f"Successfully loaded `{uploaded_file.name}`")

            with st.expander("🔍 Dataset Metadata & Structure"):
                st.text(str(ds))

            data_vars = list(ds.data_vars.keys())
            if not data_vars:
                st.error("No data variables found in the dataset.")
                return

            c1, c2, c3 = st.columns(3)
            with c1:
                selected_var = st.selectbox("Select Variable", options=data_vars)
            with c2:
                cmap_choice = st.selectbox(
                    "Colormap",
                    options=["viridis", "coolwarm", "plasma", "Blues", "YlGnBu", "Spectral_r"],
                )
            with c3:
                use_robust = st.checkbox("Robust Scaling (Ignore Outliers)", value=True)

            da = ds[selected_var]

            lat_names = [d for d in da.dims if any(k in d.lower() for k in ["lat", "latitude", "y"])]
            lon_names = [d for d in da.dims if any(k in d.lower() for k in ["lon", "longitude", "x"])]

            lat_dim = lat_names[0] if lat_names else None
            lon_dim = lon_names[0] if lon_names else None
            is_spatial = lat_dim is not None and lon_dim is not None

            slice_dict = {}
            non_spatial_dims = [d for d in da.dims if d not in [lat_dim, lon_dim]]

            if non_spatial_dims:
                st.markdown("##### 🎛️ Select Data Slice / Lead Time")
                dim_cols = st.columns(len(non_spatial_dims))

                for i, dim in enumerate(non_spatial_dims):
                    dim_coords = da[dim].values
                    formatted_labels = [format_coord_value(val) for val in dim_coords]

                    with dim_cols[i]:
                        if len(formatted_labels) <= 15:
                            selected_label = st.selectbox(
                                f"Select {dim.capitalize()}",
                                options=formatted_labels,
                                key=f"select_{dim}",
                            )
                            selected_idx = formatted_labels.index(selected_label)
                        else:
                            selected_idx = st.slider(
                                f"Select {dim.capitalize()}",
                                min_value=0,
                                max_value=len(formatted_labels) - 1,
                                value=0,
                                format="",
                                key=f"slider_{dim}",
                            )
                            st.caption(f"**Selected {dim}:** `{formatted_labels[selected_idx]}`")

                        slice_dict[dim] = selected_idx

            da_2d = da.isel(slice_dict) if slice_dict else da

            while len(da_2d.shape) > 2:
                da_2d = da_2d.isel({da_2d.dims[0]: 0})

            fig = plt.figure(figsize=(11, 7))
            fig.patch.set_alpha(0)

            if is_spatial:
                ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
                ax.patch.set_alpha(0)

                lats = da_2d[lat_dim].values
                lons = da_2d[lon_dim].values

                plot_obj = da_2d.plot.contourf(
                    ax=ax,
                    transform=ccrs.PlateCarree(),
                    cmap=cmap_choice,
                    robust=use_robust,
                    levels=20,
                    add_colorbar=True,
                    cbar_kwargs={
                        "shrink": 0.8,
                        "pad": 0.03,
                        "label": f"{selected_var} ({da.attrs.get('units', '')})",
                    },
                )

                ax.add_feature(cfeature.COASTLINE, edgecolor="white", linewidth=0.8)
                ax.add_feature(cfeature.BORDERS, edgecolor="white", linewidth=0.5)

                gl = ax.gridlines(draw_labels=True, linewidth=0.5, color="white", alpha=0.3, linestyle="--")
                gl.top_labels = False
                gl.right_labels = False
                gl.xlabel_style = {"color": "white"}
                gl.ylabel_style = {"color": "white"}

                ax.set_extent(
                    [float(np.min(lons)), float(np.max(lons)), float(np.min(lats)), float(np.max(lats))],
                    crs=ccrs.PlateCarree(),
                )

                cbar = plot_obj.colorbar
                cbar.ax.yaxis.set_tick_params(color="white", labelcolor="white")
                cbar.ax.yaxis.label.set_color("white")
                cbar.outline.set_edgecolor("white")
            else:
                ax = fig.add_subplot(1, 1, 1)
                ax.patch.set_alpha(0)
                da_2d.plot(ax=ax, cmap=cmap_choice, robust=use_robust, cbar_kwargs={"shrink": 0.8})
                ax.tick_params(colors="white")
                ax.xaxis.label.set_color("white")
                ax.yaxis.label.set_color("white")

            title_suffix = ""
            if slice_dict:
                selected_labels = [
                    f"{dim}: {format_coord_value(da[dim].values[slice_dict[dim]])}"
                    for dim in slice_dict
                ]
                title_suffix = f"\n({', '.join(selected_labels)})"

            plt.title(f"Field Visualization: {selected_var}{title_suffix}", color="white", pad=15)
            st.pyplot(fig, clear_figure=True)

        except Exception as e:
            st.error(f"Failed to process file: {str(e)}")