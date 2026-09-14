import datetime
import math
import zoneinfo
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
        "tz": "America/New_York",
    },
    "Chatham, MA": {
        "id": "8447435",
        "lat": 41.6811,
        "lon": -69.9511,
        "tz": "America/New_York",
    },
    "Bass River (Dennis/Yarmouth), MA": {
        "id": "8447504",
        "lat": 41.6500,
        "lon": -70.1917,
        "tz": "America/New_York",
    },
    "Provincetown, MA": {
        "id": "8446121",
        "lat": 42.0480,
        "lon": -70.1856,
        "tz": "America/New_York",
    },
    "Boston, MA": {
        "id": "8443970",
        "lat": 42.3539,
        "lon": -71.0503,
        "tz": "America/New_York",
    },
    "Acadia National Park (Bar Harbor), ME": {
        "id": "8413320",
        "lat": 44.3917,
        "lon": -68.2050,
        "tz": "America/New_York",
    },
}


# --- Solar & Lunar Calculations ---
def get_sun_times_dt(date_obj, lat, lon, tz_name="America/New_York"):
    """Calculates local Sunrise and Sunset times for a given date and location."""
    day_of_year = date_obj.timetuple().tm_yday

    declination = 23.45 * math.sin(
        math.radians((360 / 365.25) * (day_of_year - 81))
    )

    lat_rad = math.radians(lat)
    dec_rad = math.radians(declination)

    try:
        cos_ha = -math.tan(lat_rad) * math.tan(dec_rad)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        ha = math.degrees(math.acos(cos_ha))
    except ValueError:
        ha = 90.0

    solar_noon_utc = 12.0 - (lon / 15.0)

    b = math.radians((360 / 365) * (day_of_year - 81))
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

    solar_noon_utc -= eot / 60.0

    sunrise_utc = solar_noon_utc - (ha / 15.0)
    sunset_utc = solar_noon_utc + (ha / 15.0)

    tz = zoneinfo.ZoneInfo(tz_name)

    def decimal_hours_to_dt(dec_hours):
        hrs = int(dec_hours % 24)
        mins = int((dec_hours % 1) * 60)
        dt_utc = datetime.datetime(
            date_obj.year,
            date_obj.month,
            date_obj.day,
            hrs,
            mins,
            tzinfo=datetime.timezone.utc,
        )
        return dt_utc.astimezone(tz).time()

    return decimal_hours_to_dt(sunrise_utc), decimal_hours_to_dt(sunset_utc)


def get_moon_phase_emoji(date_obj):
    """Returns strictly the moon phase emoji."""
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
        return "🌑"
    elif phase_age < 7:
        return "🌒"
    elif phase_age < 9:
        return "🌓"
    elif phase_age < 14:
        return "🌔"
    elif phase_age < 16:
        return "🌕"
    elif phase_age < 22:
        return "🌖"
    elif phase_age < 24:
        return "🌗"
    else:
        return "🌘"


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

# --- Session State for Date Navigation ---
today_date = datetime.date.today()

if "selected_month" not in st.session_state:
    st.session_state.selected_month = today_date.month
if "selected_year" not in st.session_state:
    st.session_state.selected_year = today_date.year


def reset_to_today():
    st.session_state.selected_month = today_date.month
    st.session_state.selected_year = today_date.year


# --- Top Controls ---
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
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
        key="selected_month",
        format_func=lambda m: datetime.date(2000, m, 1).strftime("%b"),
    )
with col3:
    selected_year = st.selectbox(
        "Year",
        range(2020, 2031),
        key="selected_year",
    )
with col4:
    st.write(" ")
    st.button("📅 Today", on_click=reset_to_today, use_container_width=True)

start_date = datetime.date(
    st.session_state.selected_year, st.session_state.selected_month, 1
)
if st.session_state.selected_month == 12:
    end_date = datetime.date(
        st.session_state.selected_year + 1, 1, 1
    ) - datetime.timedelta(days=1)
else:
    end_date = datetime.date(
        st.session_state.selected_year, st.session_state.selected_month + 1, 1
    ) - datetime.timedelta(days=1)

station_info = STATIONS[selected_location]

# --- Display Filters ---
with st.expander("⚙️ View Options & Highlights", expanded=True):
    tide_view = st.radio(
        "Tide View Mode",
        ["All Tides", "High Tides Only", "Low Tides Only"],
        horizontal=True,
    )

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        highlight_daylight_highs = st.checkbox("☀️ Highlight Daylight Highs")
    with col_h2:
        highlight_daylight_lows = st.checkbox("☀️ Highlight Daylight Lows")

tab_month, tab_daily = st.tabs(["🗓️ Monthly Table", "📈 Daily Graph"])

# --- Monthly Table View ---
with tab_month:
    raw_hilo = fetch_month_hilo(station_info["id"], start_date, end_date)

    if not raw_hilo.empty:
        records = []
        current_day = start_date

        while current_day <= end_date:
            sr_time, ss_time = get_sun_times_dt(
                current_day,
                station_info["lat"],
                station_info["lon"],
                station_info.get("tz", "America/New_York"),
            )
            moon_emoji = get_moon_phase_emoji(current_day)

            day_tides = raw_hilo[raw_hilo["t"].dt.date == current_day].copy()

            high_tides = day_tides[day_tides["type"] == "H"]
            low_tides = day_tides[day_tides["type"] == "L"]

            def format_tide(tide_row, is_high_tide):
                time_obj = tide_row["t"].time()
                time_str = (
                    tide_row["t"].strftime("%I:%M%p").lstrip("0").lower()
                )
                height_str = f"({tide_row['v']:.1f} ft)"

                is_daylight = sr_time <= time_obj <= ss_time

                should_highlight = (
                    is_daylight and is_high_tide and highlight_daylight_highs
                ) or (
                    is_daylight
                    and not is_high_tide
                    and highlight_daylight_lows
                )

                # Line break (<br>) forces height onto a separate line below the time
                if should_highlight:
                    return f"<mark style='background-color: #fef08a; color: #854d0e; padding: 2px 4px; border-radius: 4px;'><b>{time_str}</b><br>{height_str}</mark>"
                return f"<b>{time_str}</b><br>{height_str}"

            h1 = (
                format_tide(high_tides.iloc[0], is_high_tide=True)
                if len(high_tides) > 0
                else "-"
            )
            h2 = (
                format_tide(high_tides.iloc[1], is_high_tide=True)
                if len(high_tides) > 1
                else "-"
            )
            l1 = (
                format_tide(low_tides.iloc[0], is_high_tide=False)
                if len(low_tides) > 0
                else "-"
            )
            l2 = (
                format_tide(low_tides.iloc[1], is_high_tide=False)
                if len(low_tides) > 1
                else "-"
            )

            sr_fmt = sr_time.strftime("%I:%M").lstrip("0")
            ss_fmt = ss_time.strftime("%I:%M").lstrip("0")

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

            row_data["Sunrise (am)"] = sr_fmt
            row_data["Sunset (pm)"] = ss_fmt
            row_data["Moon"] = moon_emoji

            records.append(row_data)
            current_day += datetime.timedelta(days=1)

        month_df = pd.DataFrame(records)

        # Single HTML Table Construction
        headers = [col for col in month_df.columns if col != "is_today"]
        table_html = "<table class='custom-tide-table'><thead><tr>"
        for h in headers:
            table_html += f"<th>{h}</th>"
        table_html += "</tr></thead><tbody>"

        for idx, row in month_df.iterrows():
            row_class = "today-row" if row["is_today"] else ""
            table_html += f"<tr class='{row_class}'>"
            for col in headers:
                table_html += f"<td>{row[col]}</td>"
            table_html += "</tr>"

        table_html += "</tbody></table>"

        custom_css = """
        <style>
            .custom-tide-table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                margin-top: 12px;
                font-size: 0.88rem;
                border: 1px solid #d0d7de;
                border-radius: 8px;
                overflow: hidden;
            }
            .custom-tide-table th {
                background-color: #f6f8fa;
                color: #1f2328;
                font-weight: 600;
                padding: 10px 12px;
                text-align: left;
                border-bottom: 2px solid #d0d7de;
                vertical-align: middle;
            }
            .custom-tide-table td {
                padding: 8px 12px;
                text-align: left;
                border-bottom: 1px solid #e1e4e8;
                vertical-align: top;
                line-height: 1.35;
            }
            /* Explicit Light Zebra Striping */
            .custom-tide-table tbody tr:nth-child(odd) {
                background-color: #ffffff;
            }
            .custom-tide-table tbody tr:nth-child(even) {
                background-color: #f8f9fa;
            }
            /* Row Hover */
            .custom-tide-table tbody tr:hover {
                background-color: #eef6fc !important;
            }
            /* Today Highlight */
            .custom-tide-table tbody tr.today-row {
                background-color: #e0f2fe !important;
                font-weight: 600;
            }
            .custom-tide-table tbody tr.today-row td {
                border-top: 1px solid #0284c7;
                border-bottom: 1px solid #0284c7;
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
