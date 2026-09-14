import datetime
import math
import pandas as pd
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


# --- Built-in Solar & Lunar Calculations ---
def get_sun_times_dt(date_obj, lat, lon):
    """Returns sunrise and sunset as datetime.time objects for accurate filtering."""
    day_of_year = date_obj.timetuple().tm_yday
    declination = 23.45 * math.sin(
        math.radians((360 / 365) * (day_of_year - 81))
    )

    lat_rad = math.radians(lat)
    dec_rad = math.radians(declination)

    try:
        cos_ha = -math.tan(lat_rad) * math.tan(dec_rad)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        ha = math.degrees(math.acos(cos_ha))
    except ValueError:
        ha = 90

    solar_noon = 12.0 - (lon / 15.0)
    sunrise_decimal = solar_noon - (ha / 15.0)
    sunset_decimal = solar_noon + (ha / 15.0)

    time_offset = 4 if date_obj.month in range(3, 11) else 5
    sunrise_utc = (sunrise_decimal + time_offset) % 24
    sunset_utc = (sunset_decimal + time_offset) % 24

    sr_h, sr_m = int(sunrise_utc), int((sunrise_utc % 1) * 60)
    ss_h, ss_m = int(sunset_utc), int((sunset_utc % 1) * 60)

    return datetime.time(sr_h, sr_m), datetime.time(ss_h, ss_m)


def get_moon_phase(date_obj):
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

st.title("🌊 Tide Dashboard")

# --- Top Controls ---
today_date = datetime.date.today()

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    selected_location = st.selectbox(
        "Location",
        list(STATIONS.keys()),
        index=0,
    )
with col2:
    selected_month = st.selectbox(
        "Month",
        range(1, 13),
        index=today_date.month - 1,
        format_func=lambda m: datetime.date(2000, m, 1).strftime("%b"),
    )
with col3:
    selected_year = st.selectbox(
        "Year",
        range(2020, 2031),
        index=range(2020, 2031).index(today_date.year),
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

station_info = STATIONS[selected_location]

# --- Display Filters ---
with st.expander("⚙️ View Options & Filters", expanded=True):
    tide_view = st.radio(
        "Tide View Mode",
        ["All Tides", "High Tides Only", "Low Tides Only"],
        horizontal=True,
    )

    daylight_only = st.checkbox("☀️ Show daylight tides only")

tab_month, tab_daily = st.tabs(["🗓️ Monthly Table", "📈 Daily Graph"])

# --- Monthly Table View ---
with tab_month:
    raw_hilo = fetch_month_hilo(station_info["id"], start_date, end_date)

    if not raw_hilo.empty:
        records = []
        current_day = start_date

        while current_day <= end_date:
            sr_time, ss_time = get_sun_times_dt(
                current_day, station_info["lat"], station_info["lon"]
            )
            moon_phase_str = get_moon_phase(current_day)

            day_tides = raw_hilo[raw_hilo["t"].dt.date == current_day].copy()

            # Filter for Daylight Hours if enabled
            if daylight_only:
                day_tides = day_tides[
                    (day_tides["t"].dt.time >= sr_time)
                    & (day_tides["t"].dt.time <= ss_time)
                ]

            high_tides = day_tides[day_tides["type"] == "H"]
            low_tides = day_tides[day_tides["type"] == "L"]

            def format_tide(tide_row):
                time_str = (
                    tide_row["t"].strftime("%I:%M%p").lstrip("0").lower()
                )
                height_str = f"({tide_row['v']:.1f} ft)"
                # HTML bold tag for rendered tables
                return f"<b>{time_str}</b> {height_str}"

            h1 = (
                format_tide(high_tides.iloc[0])
                if len(high_tides) > 0
                else "-"
            )
            h2 = (
                format_tide(high_tides.iloc[1])
                if len(high_tides) > 1
                else "-"
            )
            l1 = (
                format_tide(low_tides.iloc[0]) if len(low_tides) > 0 else "-"
            )
            l2 = (
                format_tide(low_tides.iloc[1]) if len(low_tides) > 1 else "-"
            )

            sr_fmt = sr_time.strftime("%I:%M%p").lstrip("0").lower()
            ss_fmt = ss_time.strftime("%I:%M%p").lstrip("0").lower()

            row_data = {
                "Date": current_day.strftime("%a %b %d"),
                "is_today": current_day == today_date,
            }

            if tide_view in ["All Tides", "High Tides Only"]:
                row_data["High 1"] = h1
                row_data["High 2"] = h2

            if tide_view in ["All Tides", "Low Tides Only"]:
                row_data["Low 1"] = l1
                row_data["Low 2"] = l2

            row_data["Sun"] = f"🌅<b>{sr_fmt}</b> 🌇<b>{ss_fmt}</b>"
            row_data["Moon"] = moon_phase_str

            records.append(row_data)
            current_day += datetime.timedelta(days=1)

        month_df = pd.DataFrame(records)

        # Translucent highlight (rgba) so text remains crisp in dark mode
        def highlight_today(row):
            if row["is_today"]:
                return ["background-color: rgba(0, 119, 182, 0.25);"] * len(row)
            return [""] * len(row)

        display_df = month_df.drop(columns=["is_today"])
        styled_df = month_df.drop(columns=["is_today"]).style.apply(
            highlight_today, axis=1
        )

        # Custom CSS for dark/light mode compatibility
        table_html = styled_df.to_html(escape=False, index=False)
        custom_css = """
        <style>
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 8px 12px !important;
                text-align: left;
            }
        </style>
        """

        st.markdown(custom_css + table_html, unsafe_allow_html=True)

    else:
        st.error("Unable to load NOAA tide data.")

# --- Daily Graph View ---
with tab_daily:
    selected_day = st.date_input(
        "Select Date",
        value=today_date if start_date <= today_date <= end_date else start_date,
        min_value=start_date,
        max_value=end_date,
        format="MM/DD/YYYY",
    )

    c_df = fetch_continuous_tides(
        station_info["id"],
        selected_day,
        selected_day + datetime.timedelta(days=1),
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
