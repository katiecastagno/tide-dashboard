import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from suncalc import get_illumination, get_times

# --- Configured Locations ---
STATIONS = {
    "Wellfleet, MA": {
        "id": "8446613",
        "lat": 41.9300,
        "lon": -70.0417,
    },
    "Chatham, MA": {
        "id": "8447435",
        "lat": 41.6811,
        "lon": -69.9511,
    },
    "Bass River (Dennis/Yarmouth), MA": {
        "id": "8447504",
        "lat": 41.6500,
        "lon": -70.1917,
    },
    "Provincetown, MA": {
        "id": "8446121",
        "lat": 42.0480,
        "lon": -70.1856,
    },
    "Boston, MA": {
        "id": "8443970",
        "lat": 42.3539,
        "lon": -71.0503,
    },
    "Acadia National Park (Bar Harbor), ME": {
        "id": "8413320",
        "lat": 44.3917,
        "lon": -68.2050,
    },
}


# --- API Functions ---
@st.cache_data(ttl=86400)
def fetch_month_hilo(station_id, start_date, end_date):
    url = (
        f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
        f"begin_date={start_date.strftime('%Y%m%d')}&end_date={end_date.strftime('%Y%m%d')}"
        f"&station={station_id}&product=predictions&interval=hilo&datum=MLLW"
        f"&units=english&time_zone=lst_ldt&format=json"
    )
    res = requests.get(url).json()
    if "predictions" in res:
        df = pd.DataFrame(res["predictions"])
        df["t"] = pd.to_datetime(df["t"])
        df["v"] = df["v"].astype(float)
        return df
    return pd.DataFrame()


@st.cache_data(ttl=86400)
def fetch_continuous_tides(station_id, start_date, end_date):
    url = (
        f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
        f"begin_date={start_date.strftime('%Y%m%d')}&end_date={end_date.strftime('%Y%m%d')}"
        f"&station={station_id}&product=predictions&datum=MLLW"
        f"&units=english&time_zone=lst_ldt&format=json"
    )
    res = requests.get(url).json()
    if "predictions" in res:
        df = pd.DataFrame(res["predictions"])
        df["t"] = pd.to_datetime(df["t"])
        df["v"] = df["v"].astype(float)
        return df
    return pd.DataFrame()


def get_moon_phase_name(phase_val):
    if phase_val < 0.03 or phase_val > 0.97:
        return "New 🌑"
    elif phase_val < 0.22:
        return "Waxing Cres. 🌒"
    elif phase_val < 0.28:
        return "1st Qtr 🌓"
    elif phase_val < 0.47:
        return "Waxing Gibb. 🌔"
    elif phase_val < 0.53:
        return "Full 🌕"
    elif phase_val < 0.72:
        return "Waning Gibb. 🌖"
    elif phase_val < 0.78:
        return "Last Qtr 🌗"
    else:
        return "Waning Cres. 🌘"


# --- Page Config for Mobile Screen ---
st.set_page_config(
    page_title="Tide Dashboard",
    page_icon="🌊",
    layout="centered",
    initial_sidebar_state="collapsed",  # Collapses sidebar on mobile load
)

# State Management
if "selected_station" not in st.session_state:
    st.session_state.selected_station = "Wellfleet, MA"

# Main App Header
st.title("🌊 Tide Dashboard")

# Mobile Controls (In an Expander at top for easy touch access)
with st.expander("⚙️ Select Location & Date", expanded=False):
    selected_location = st.selectbox(
        "Choose Station",
        list(STATIONS.keys()),
        index=list(STATIONS.keys()).index(st.session_state.selected_station),
    )
    st.session_state.selected_station = selected_location

    today = datetime.date.today()
    selected_year = st.number_input(
        "Year", min_value=2020, max_value=2030, value=today.year
    )
    selected_month = st.selectbox(
        "Month",
        range(1, 13),
        index=today.month - 1,
        format_func=lambda m: datetime.date(2000, m, 1).strftime("%B"),
    )

# Date Setup
start_date = datetime.date(selected_year, selected_month, 1)
if selected_month == 12:
    end_date = datetime.date(selected_year + 1, 1, 1) - datetime.timedelta(
        days=1
    )
else:
    end_date = datetime.date(
        selected_year, selected_month + 1, 1
    ) - datetime.timedelta(days=1)

# --- Interactive Map View ---
map_data = []
for name, info in STATIONS.items():
    map_data.append({
        "Station": name,
        "lat": info["lat"],
        "lon": info["lon"],
        "Size": 16 if name == st.session_state.selected_station else 10,
        "Status": (
            "Selected"
            if name == st.session_state.selected_station
            else "Available"
        ),
    })
map_df = pd.DataFrame(map_data)

fig_map = px.scatter_mapbox(
    map_df,
    lat="lat",
    lon="lon",
    hover_name="Station",
    color="Status",
    size="Size",
    size_max=14,
    zoom=5.5,  # Adjusted zoom for mobile vertical viewports
    center={"lat": 43.0, "lon": -69.5},
    color_discrete_map={"Selected": "#d90429", "Available": "#0077b6"},
    mapbox_style="carto-positron",
)
fig_map.update_layout(
    margin=dict(l=0, r=0, t=0, b=0), height=260, showlegend=False
)

# Map Selection Capture
selected_point = st.plotly_chart(
    fig_map, use_container_width=True, on_select="rerun"
)

if selected_point and "selection" in selected_point:
    points = selected_point["selection"].get("points", [])
    if points:
        clicked_index = points[0]["point_index"]
        clicked_station = map_df.iloc[clicked_index]["Station"]
        if clicked_station != st.session_state.selected_station:
            st.session_state.selected_station = clicked_station
            st.rerun()

station_info = STATIONS[st.session_state.selected_station]

st.subheader(f"📍 {st.session_state.selected_station}")
st.caption(f"Showing data for **{start_date.strftime('%B %Y')}**")

# --- Tabs for Mobile Navigation ---
tab_month, tab_daily = st.tabs(["🗓️ Monthly Table", "📈 Daily Graph"])

# --- TAB 1: MONTHLY TABLE VIEW ---
with tab_month:
    raw_hilo = fetch_month_hilo(station_info["id"], start_date, end_date)

    if not raw_hilo.empty:
        records = []
        current_day = start_date

        while current_day <= end_date:
            dt_noon = datetime.datetime.combine(
                current_day, datetime.time(12, 0)
            )

            # Astronomical details
            s_times = get_times(
                dt_noon, station_info["lat"], station_info["lon"]
            )
            m_info = get_illumination(dt_noon)

            # Filter high/low for current day
            day_tides = raw_hilo[raw_hilo["t"].dt.date == current_day]
            high_tides = day_tides[day_tides["type"] == "H"]
            low_tides = day_tides[day_tides["type"] == "L"]

            # Concise formatting for mobile tables
            h1 = (
                f"{high_tides.iloc[0]['t'].strftime('%I:%M%p').lstrip('0')} ({high_tides.iloc[0]['v']:.1f}')"
                if len(high_tides) > 0
                else "-"
            )
            h2 = (
                f"{high_tides.iloc[1]['t'].strftime('%I:%M%p').lstrip('0')} ({high_tides.iloc[1]['v']:.1f}')"
                if len(high_tides) > 1
                else "-"
            )
            l1 = (
                f"{low_tides.iloc[0]['t'].strftime('%I:%M%p').lstrip('0')} ({low_tides.iloc[0]['v']:.1f}')"
                if len(low_tides) > 0
                else "-"
            )
            l2 = (
                f"{low_tides.iloc[1]['t'].strftime('%I:%M%p').lstrip('0')} ({low_tides.iloc[1]['v']:.1f}')"
                if len(low_tides) > 1
                else "-"
            )

            records.append({
                "Date": current_day.strftime("%a %b %d"),
                "High 1": h1,
                "High 2": h2,
                "Low 1": l1,
                "Low 2": l2,
                "Sun": f"🌅{s_times['sunrise'].strftime('%I:%M%p').lstrip('0')} 🌇{s_times['sunset'].strftime('%I:%M%p').lstrip('0')}",
                "Moon": get_moon_phase_name(m_info["phase"]),
            })
            current_day += datetime.timedelta(days=1)

        month_df = pd.DataFrame(records)
        st.dataframe(month_df, use_container_width=True, hide_index=True)
    else:
        st.error("Unable to load NOAA data.")

# --- TAB 2: DAILY GRAPH VIEW ---
with tab_daily:
    selected_day = st.date_input(
        "Select Date",
        value=start_date,
        min_value=start_date,
        max_value=end_date,
    )

    c_df = fetch_continuous_tides(
        station_info["id"], selected_day, selected_day + datetime.timedelta(days=1)
    )

    if not c_df.empty:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=c_df["t"],
                y=c_df["v"],
                mode="lines",
                name="Tide (ft)",
                line=dict(color="#0077b6", width=3),
            )
        )
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Height (ft)",
            hovermode="x unified",
            margin=dict(l=10, r=10, t=10, b=10),
            height=300,  # Compact graph height for vertical phone screens
        )
        st.plotly_chart(fig, use_container_width=True)
