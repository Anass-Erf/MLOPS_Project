"""Run with make ui from the project root."""

import os
from datetime import date, timedelta

import streamlit as st

from src.utils.config import load_config
from ui.utils import (
    CROPS,
    SITES,
    UIError,
    check_health,
    history_frame,
    load_example,
    parse_request,
    predict,
    request_from_frame,
)
from ui.weather import get_weather_history, supported_sites

st.set_page_config(page_title="Crop Water Stress Prediction", page_icon="🌾", layout="wide")
API_URL = os.environ.get("CWS_API_URL", "http://localhost:8000")


def set_request(payload: dict) -> None:
    st.session_state.request = payload
    st.session_state.crop = payload["crop"]
    st.session_state.site = payload["site_id"]
    st.session_state.revision = st.session_state.get("revision", 0) + 1
    st.session_state.pop("result", None)


st.title("Crop Water Stress Prediction")
st.write("Predict modeled crop water stress using historical meteorological conditions.")
status, refresh = st.columns([5, 1])
refresh.button("Refresh status")
with status:
    try:
        health = check_health(API_URL)
        st.caption(f"🟢 API: Available · Model: {health.get('model_version', 'Not reported')}")
    except UIError as exc:
        st.caption("🔴 API: Unavailable")
        st.warning(str(exc))
st.caption(
    "This project uses a modeled stress proxy and not a directly measured field stress label."
)

mode = st.radio("Input Mode", ["Manual / File", "Automatic Weather"], horizontal=True)
if st.session_state.get("result_mode") != mode:
    st.session_state.pop("result", None)

if mode == "Automatic Weather":
    try:
        cfg = load_config()
        sites = supported_sites(cfg)
        if not sites:
            raise UIError("No configured sites match the API contract. Use Manual / File.")
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Cannot load weather configuration: {exc}")
        st.stop()
    st.caption(
        f"NASA POWER daily observations · Project weather period: "
        f"{cfg['data']['start']} to {cfg['data']['end']}. "
        "Dates outside this period have no established evaluation results. "
        "FastAPI checks the configured wheat season."
    )
    try:
        example = load_example()
        default_date = date.fromisoformat(example["history"][-1]["date"]) + timedelta(days=1)
        default_site = example["site_id"]
    except UIError:
        default_date = date.fromisoformat(cfg["data"]["end"])
        default_site = next(iter(sites))
    a, b, c = st.columns(3)
    auto_crop = a.selectbox("Crop", CROPS, format_func=str.title, key="auto_crop")
    auto_site = b.selectbox(
        "Site",
        list(sites),
        format_func=str.title,
        key="auto_site",
        index=list(sites).index(default_site) if default_site in sites else 0,
    )
    forecast_date = c.date_input(
        "Prediction date",
        value=min(default_date, date.today()),
        max_value=date.today(),
        key="auto_date",
    )
    prefer_live = st.checkbox(
        "Try NASA POWER first",
        help="Otherwise verified local snapshots are preferred. A failed live request falls back "
        "to a matching verified snapshot. Exact saved requests are always reused.",
    )
    context = (auto_crop, auto_site, forecast_date, prefer_live)
    if st.session_state.get("auto_context") != context:
        st.session_state.pop("auto_weather", None)
        st.session_state.pop("result", None)
    if st.button("Fetch Weather Data", type="primary"):
        st.session_state.pop("auto_weather", None)
        st.session_state.pop("result", None)
        try:
            with st.spinner("Retrieving and validating NASA POWER weather…"):
                st.session_state.auto_weather = get_weather_history(
                    auto_site, forecast_date, auto_crop, cfg, prefer_live=prefer_live
                )
                st.session_state.auto_context = context
        except UIError as exc:
            st.error(str(exc))
    if "auto_weather" not in st.session_state:
        st.info("Choose a site and prediction date, then click Fetch Weather Data.")
        st.stop()
    weather = st.session_state.auto_weather
    request = weather.request
    edited = history_frame(request)
    st.success(f"Weather source: NASA POWER · Mode: {weather.mode}")
    if weather.notice:
        st.info(weather.notice)
    st.caption(
        f"Crop: {request['crop'].title()} · Site: {request['site_id'].title()} · "
        f"History: {len(edited)} days · "
        f"Period: {edited.date.iloc[0]:%d %b %Y} → {edited.date.iloc[-1]:%d %b %Y}"
    )
    with st.expander("View Historical Weather"):
        st.caption("Provider observations normalized to project units; read-only.")
        st.dataframe(edited, hide_index=True, width="stretch", height=310)
        st.caption(f"Verified snapshot: {weather.snapshot}")
else:
    load, upload = st.columns([1, 3])
    with load:
        if st.button("Load Example", type="primary", width="stretch"):
            try:
                set_request(load_example())
                # Clear an earlier upload so it cannot replace the example on the next rerun.
                st.session_state.upload_revision = st.session_state.get("upload_revision", 0) + 1
            except UIError as exc:
                st.error(str(exc))
    with upload:
        with st.expander("Upload JSON"):
            uploaded = st.file_uploader(
                "Upload a prediction request",
                type=["json"],
                key=f"upload_{st.session_state.get('upload_revision', 0)}",
            )
            if uploaded is not None and st.button("Use uploaded request"):
                try:
                    set_request(parse_request(uploaded.getvalue()))
                except UIError as exc:
                    st.error(str(exc))

    if "request" not in st.session_state:
        st.info(
            "Click Load Example to try the saved weather history. No internet connection is needed."
        )
        st.stop()

    crop_col, site_col, period_col = st.columns([1, 1, 2])
    crop = crop_col.selectbox("Crop", CROPS, format_func=str.title, key="crop")
    site = site_col.selectbox("Site", SITES, format_func=str.title, key="site")

    with st.expander("View / Edit Historical Weather"):
        st.caption("One row per day, oldest first. The complete history is sent to the API.")
        edited = st.data_editor(
            history_frame(st.session_state.request),
            hide_index=True,
            width="stretch",
            height=310,
            num_rows="fixed",
            key=f"weather_{st.session_state.revision}",
            column_config={
                "date": st.column_config.DateColumn("Date", format="DD MMM YYYY", required=True),
                "temperature": st.column_config.NumberColumn("Mean temp (°C)", required=True),
                "temperature_min": st.column_config.NumberColumn("Min temp (°C)", required=True),
                "temperature_max": st.column_config.NumberColumn("Max temp (°C)", required=True),
                "humidity": st.column_config.NumberColumn("Humidity (%)", required=True),
                "precipitation": st.column_config.NumberColumn("Rain (mm/day)", required=True),
                "solar_radiation": st.column_config.NumberColumn(
                    "Solar (MJ/m²/day)", required=True
                ),
                "wind_speed": st.column_config.NumberColumn("Wind (m/s)", required=True),
            },
        )

    try:
        request = request_from_frame(crop, site, edited)
    except UIError as exc:
        st.session_state.pop("result", None)
        st.error(str(exc))
        st.button("Predict Water Stress", type="primary", disabled=True)
        st.stop()

    with period_col:
        st.caption(f"History: {len(edited)} days")
        st.write(f"{edited.date.iloc[0]:%d %b %Y} → {edited.date.iloc[-1]:%d %b %Y}")

with st.expander("Weather Summary", expanded=True):
    metrics = [
        ("Historical days", str(len(edited))),
        ("Average temperature", f"{edited.temperature.mean():.1f} °C"),
        ("Minimum temperature", f"{edited.temperature_min.min():.1f} °C"),
        ("Maximum temperature", f"{edited.temperature_max.max():.1f} °C"),
        ("Average humidity", f"{edited.humidity.mean():.1f} %"),
        ("Total precipitation", f"{edited.precipitation.sum():.2f} mm"),
        ("Average solar radiation", f"{edited.solar_radiation.mean():.1f} MJ/m²/day"),
        ("Average wind speed", f"{edited.wind_speed.mean():.2f} m/s"),
    ]
    for offset in (0, 4):
        for column, (label, value) in zip(st.columns(4), metrics[offset : offset + 4], strict=True):
            column.metric(label, value)

# Never show an old prediction as if it describes edited inputs.
if st.session_state.get("result_request") != request:
    st.session_state.pop("result", None)

if st.button("Predict Water Stress", type="primary", width="stretch"):
    st.session_state.pop("result", None)
    try:
        with st.spinner("Requesting prediction from FastAPI…"):
            st.session_state.result = predict(API_URL, request)
            st.session_state.result_request = request
            st.session_state.result_mode = mode
    except UIError as exc:
        st.error(str(exc))

if "result" in st.session_state:
    result = st.session_state.result
    with st.container(border=True):
        st.subheader("Water Stress Prediction")
        score, forecast, model = st.columns([1, 1, 2])
        score.metric("Stress score", f"{result.prediction:.3f}")
        forecast.metric("Forecast date", result.forecast_date.strftime("%d %B %Y"))
        model.markdown("**Model**")
        model.write(result.model_version)
        display, interpretation = {
            "low": (st.success, "Modeled conditions indicate relatively low crop water stress."),
            "medium": (st.warning, "Modeled conditions indicate moderate crop water stress."),
            "high": (st.error, "Modeled conditions indicate substantial crop water stress."),
        }[result.stress_level]
        display(f"**{result.stress_level.upper()}** — {interpretation}")
        st.caption(f"Unit: {result.unit} · Target: {result.target}")
        st.caption(
            "This prediction uses a modeled stress proxy and should not be interpreted "
            "as a direct field measurement."
        )

with st.expander("Advanced — View API Request"):
    st.caption(f"POST {API_URL.rstrip('/')}/predict · Complete history, without aggregation")
    st.json(request)
