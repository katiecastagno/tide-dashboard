import datetime
import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

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


# --- Built-in Solar & Lunar Calculations (No suncalc needed) ---
def get_sun_times(date_obj, lat, lon):
    """Approximate sunrise/sunset times using standard solar declination geometry."""
    day_of_year = date_obj.timetuple().tm_yday
    # Solar declination angle
    declination = 23.45 * math.sin(
        math.radians((360 / 365) * (day_of_year - 81))
    )

    lat_rad = math.radians(lat)
    dec_rad = math.radians(declination)

    # Hour angle
    try:
        cos_ha = -math.tan(lat_rad) * math.tan(dec_rad)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        ha = math.degrees(math.acos(cos_ha))
    except ValueError:
        ha = 90

    solar_noon = 12.0 - (lon / 15.0)  # Basic longitude correction
    sunrise_decimal = solar_noon - (ha / 15.0)
    sunset_decimal = solar_noon + (ha / 15.0)

    # Approximate local time (EDT/EST shift offset)
    time_offset = 4 if date_obj.month in range(3, 11) else 5
    sunrise_utc = (sunrise_decimal + time_offset) % 24
    sunset_utc = (sunset_decimal + time_offset) % 24

    sr_h, sr_m = int(sunrise_utc), int((sunrise_utc % 1) * 60)
    ss_h, ss_m = int(sunset_utc), int((sunset_utc % 1) * 60)

    sunrise_str = datetime.time(sr_h, sr_m).strftime("%I:%M%p").lstrip("0")
    sunset_str = datetime.time(ss_h, ss_m).strftime("%I:%M%p").lstrip("0")

    return sunrise_str, sunset_str


def get_moon_phase(date_obj):
    """Conway's method for calculating approximate moon phase."""
    year = date_obj.year
    month = date_obj.month
    day = date_obj.day

    r = year % 100
    r %= 19
    if r > 9:
        r -= 19
    r = ((r * 11) % 30) + month + day
    if month < 3:
        r += 2
    r -= 8.3 if year >= 2000 else 4.3
    phase_age = math.floor(r) % 30

    if phase_age < 2 or phase_age > 28:
        return "New 🌑"
    elif phase_age < 7:
        return "Waxing Cres. 🌒"
    elif phase_age < 9:
        return "1st Qtr 🌓"
    elif phase_age < 14:
        return "Waxing Gibb. 🌔"
    elif phase_age < 16:
        return "Full 🌕"
    elif phase_age < 22:
        return "Waning Gibb. 🌖"
    elif phase_age < 24:
        return "Last Qtr 🌗"
    else:
        return "Waning Cres. 🌘"


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


# --- Page Config ---
st.set_page_config(
    page_title="Tide Dashboard",
    page_icon="🌊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if "selected_station" not in st.session_state:
    st.session_state.selected_station = "Wellfleet, MA"

st.title("🌊 Tide Dashboard")

# Mobile Controls
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

start_date = datetime.date(selected_year, selected_month, 1)
if selected_month == 12:
    end_date = datetime.date(selected_year + 1, 1, 1) - datetime.timedelta(
        days=1
    )
else:
    end_date = datetime.date(
        selected_year, selected_month + 1, 1
    ) - datetime.timedelta(days=1)

# Interactive Map
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
    zoom=5.5,
    center={"lat": 43.0, "lon": -69.5},
    color_discrete_map={"Selected": "#d90429", "Available": "#0077b6"},
    mapbox_style="carto-positron",
)
fig_map.update_layout(
    margin=dict(l=0, r=0, t=0, b=0), height=260, showlegend=False
)

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

tab_month, tab_daily = st.tabs(["🗓️ Monthly Table", "📈 Daily Graph"])

# Monthly Table View
with tab_month:
    raw_hilo = fetch_month_hilo(station_info["id"], start_date, end_date)

    if not raw_hilo.empty:
        records = []
        current_day = start_date

        while current_day <= end_date:
            sunrise_str, sunset_str = get_sun_times(
                current_day, station_info["lat"], station_info["lon"]
            )
            moon_phase_str = get_moon_phase(current_day)

            day_tides = raw_hilo[raw_hilo["t"].dt.date == current_day]
            high_tides = day_tides[day_tides["type"] == "H"]
            low_tides = day_tides[day_tides["type"] == "L"]

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
                "Sun": f"🌅{sunrise_str} 🌇{sunset_str}",
                "Moon": moon_phase_str,
            })
            current_day += datetime.timedelta(days=1)

        month_df = pd.DataFrame(records)
        st.dataframe(month_df, use_container_width=True, hide_index=True)
    else:
        st.error("Unable to load NOAA tide data.")

# Daily Graph View
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
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)
