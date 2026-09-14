import datetime
import math
import zoneinfo
import numpy as np
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
    res = requests.get(url, timeout=10).json()
    if "predictions" in res:
        df = pd.DataFrame(res["predictions"])
        df["t"] = pd.to_datetime(df["t"])
        df["v"] = df["v"].astype(float)
        return df
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_daily_tide_data(station_id, selected_date):
    start_buffer = selected_date - datetime.timedelta(days=1)
    end_buffer = selected_date + datetime.timedelta(days=1)

    hilo_url = (
        f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
        f"begin_date={start_buffer.strftime('%Y%m%d')}&end_date={end_buffer.strftime('%Y%m%d')}"
        f"&station={station_id}&product=predictions&interval=hilo&datum=MLLW"
        f"&units=english&time_zone=lst_ldt&format=json"
    )
    hilo_res = requests.get(hilo_url, timeout=10).json()

    pred_df = pd.DataFrame()
    if "predictions" in hilo_res:
        h_df = pd.DataFrame(hilo_res["predictions"])
        h_df["t"] = pd.to_datetime(h_df["t"])
        h_df["v"] = h_df["v"].astype(float)

        times = []
        vals = []

        for i in range(len(h_df) - 1):
            t1, v1 = h_df.iloc[i]["t"], h_df.iloc[i]["v"]
            t2, v2 = h_df.iloc[i + 1]["t"], h_df.iloc[i + 1]["v"]

            dt_sec = (t2 - t1).total_seconds()
            num_steps = int(dt_sec / 300)

            for s in range(num_steps):
                curr_t = t1 + datetime.timedelta(seconds=s * 300)
                phase = (s / num_steps) * math.pi
                curr_v = (v1 + v2) / 2 + ((v1 - v2) / 2) * math.cos(phase)

                if curr_t.date() == selected_date:
                    times.append(curr_t)
                    vals.append(curr_v)

        pred_df = pd.DataFrame({"t": times, "v": vals})

    obs_df = pd.DataFrame()
    try:
        date_str = selected_date.strftime("%Y%m%d")
        obs_url = (
            f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
            f"begin_date={date_str}&end_date={date_str}"
            f"&station={station_id}&product=water_level&datum=MLLW"
            f"&units=english&time_zone=lst_ldt&format=json"
        )
        obs_res = requests.get(obs_url, timeout=10).json()
        if "data" in obs_res:
            obs_df = pd.DataFrame(obs_res["data"])
            obs_df["t"] = pd.to_datetime(obs_df["t"])
            obs_df["v"] = obs_df["v"].astype(float)
    except Exception:
        pass

    return pred_df, obs_df


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
col1, col2, col3, col4 = st.columns([2, 1, 1, 1], vertical_alignment="bottom")
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
                height_str = f"<span style='font-size: 0.82em; color: #475569;'>({tide_row['v']:.1f} ft)</span>"

                is_daylight = sr_time <= time_obj <= ss_time

                should_highlight = (
                    is_daylight and is_high_tide and highlight_daylight_highs
                ) or (
                    is_daylight
                    and not is_high_tide
                    and highlight_daylight_lows
                )

                if should_highlight:
                    return f"<mark style='background-color: #fef08a; color: #854d0e; padding: 2px 4px; border-radius: 4px; display: inline-block;'><b>{time_str}</b><br>{height_str}</mark>"
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

            row_data["Rise (AM)"] = sr_fmt
            row_data["Set (PM)"] = ss_fmt
            row_data["Moon"] = moon_emoji

            records.append(row_data)
            current_day += datetime.timedelta(days=1)

        month_df = pd.DataFrame(records)
        headers = [col for col in month_df.columns if col != "is_today"]

        def get_header_class(header_name):
            if header_name == "Date":
                return "divider-col"
            elif header_name == "High 2" and "Low 1" in headers:
                return "divider-col"
            elif header_name in ["High 2", "Low 2"]:
                return "divider-col"
            elif header_name == "Set (PM)":
                return "divider-col"
            return ""

        # Global CSS block targeting native markdown table elements directly
        # Force high specificity overrides directly onto td elements
        table_style = """
        <style>
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper table {
                width: 100% !important;
                border-collapse: separate !important;
                border-spacing: 0 !important;
                margin-top: 12px !important;
                font-size: 0.90rem !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 8px !important;
            }
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper th {
                background-color: #f1f5f9 !important;
                color: #0f172a !important;
                font-weight: 700 !important;
                padding: 10px 8px !important;
                text-align: center !important;
                vertical-align: middle !important;
                border-bottom: 2px solid #94a3b8 !important;
            }
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper td {
                padding: 8px 6px !important;
                text-align: center !important;
                vertical-align: middle !important;
                border-bottom: 1px solid #e2e8f0 !important;
                line-height: 1.35 !important;
            }
            
            /* Zebra Striping: Target TD cells in alternating TR rows */
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper tr:nth-child(odd) td {
                background-color: #ffffff !important;
            }
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper tr:nth-child(even) td {
                background-color: #f8fafc !important; /* Soft Slate/Gray Zebra Tint */
            }
            
            /* Hover state override on cells */
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper tr:hover td {
                background-color: #e0f2fe !important; /* Soft Blue Hover */
            }
            
            /* Today Row Highlight override on cells */
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper tr.today-row td {
                background-color: #bae6fd !important;
                font-weight: 600 !important;
                border-top: 2px solid #0284c7 !important;
                border-bottom: 2px solid #0284c7 !important;
            }
            
            /* Vertical Divider Columns */
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper th.divider-col, 
            div[data-testid="stMarkdownContainer"] .tide-table-wrapper td.divider-col {
                border-right: 2px solid #94a3b8 !important;
            }
        </style>
        """

        table_html = "<div class='tide-table-wrapper'><table>"
        table_html += "<thead><tr>"
        for h in headers:
            cls = get_header_class(h)
            cls_attr = f" class='{cls}'" if cls else ""
            table_html += f"<th{cls_attr}>{h}</th>"
        table_html += "</tr></thead><tbody>"

        for idx, row in month_df.iterrows():
            tr_class = " class='today-row'" if row["is_today"] else ""
            table_html += f"<tr{tr_class}>"
            for col in headers:
                cls = get_header_class(col)
                cls_attr = f" class='{cls}'" if cls else ""
                table_html += f"<td{cls_attr}>{row[col]}</td>"
            table_html += "</tr>"

        table_html += "</tbody></table></div>"

        st.markdown(table_style + table_html, unsafe_allow_html=True)

    else:
        st.error("Unable to load tide data.")

# --- Daily Graph View ---
with tab_daily:
    selected_day = st.date_input(
        "Select Date",
        value=today_date if start_date <= today_date <= end_date else start_date,
        min_value=start_date,
        max_value=end_date,
        format="MM/DD/YYYY",
    )

    pred_df, obs_df = fetch_daily_tide_data(station_info["id"], selected_day)

    if not pred_df.empty:
        fig = go.Figure()

        # Predicted Tide Curve
        fig.add_trace(
            go.Scatter(
                x=pred_df["t"],
                y=pred_df["v"],
                mode="lines",
                name="Predicted",
                line=dict(color="#0077b6", width=2.5),
            )
        )

        # Observed Tide Curve
        if not obs_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=obs_df["t"],
                    y=obs_df["v"],
                    mode="lines",
                    name="Observed",
                    line=dict(color="#d97706", width=2, dash="dot"),
                )
            )

        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Height (ft MLLW)",
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Unable to load tide data for this date.")
