# app.py — Silent Skies: Multi-Airport Aircraft Noise Dashboard

import streamlit as st
import pandas as pd
import requests
import os
from datetime import date
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import seaborn as sns
import pydeck as pdk

# === Set Mapbox Token for PyDeck ===

from dotenv import load_dotenv
load_dotenv()

pdk.settings.mapbox_api_key = os.getenv("MAPBOX_API_KEY", "your_mapbox_token_here")

# === Static fallback airport info ===
AIRPORTS = {
    "EDDB": {"lat": 52.3667, "lon": 13.5033, "city": "Berlin", "pop_m": 3.7},
    "LFPG": {"lat": 49.0097, "lon": 2.5479, "city": "Paris", "pop_m": 11.0},
    "EGLL": {"lat": 51.4700, "lon": -0.4543, "city": "London", "pop_m": 9.0},
}

# === Streamlit Config ===
load_dotenv()
st.set_page_config(page_title="Silent Skies", layout="wide")
st.title("🌃 Silent Skies: Noise, Flight Arrivals & Weather Dashboard")
st.sidebar.header("🔧 Settings")

# Sidebar Inputs
api_key = st.sidebar.text_input("🔑 AeroDataBox API Key", type="password")
weather_key = st.sidebar.text_input("🔑 OpenWeatherMap API Key", type="password")
icao_list = st.sidebar.multiselect("🛬 Select Airports", options=list(AIRPORTS.keys()), default=["EDDB"])
selected_date = st.sidebar.date_input("📅 Select Date", value=date.today(), min_value=date(2020, 1, 1), max_value=date.today())

noise_file = st.sidebar.file_uploader("📄 Upload Noise Data CSV", type="csv")
st.sidebar.download_button(
    label="Download Sample Noise CSV",
    data="timestamp,noise_db,max_slow,icao\n2025-07-01T12:00:00+02:00,65,72,EDDB\n2025-07-01T12:15:00+02:00,68,74,EDDB\n",
    file_name="sample_noise.csv",
    mime="text/csv"
)

# Set environment variables
if api_key:
    os.environ["AERODATABOX_API_KEY"] = api_key
if weather_key:
    os.environ["OPENWEATHER_API_KEY"] = weather_key

# === Load Noise CSV ===
if noise_file:
    df_noise = pd.read_csv(noise_file)
    if 'timestamp' not in df_noise.columns or 'icao' not in df_noise.columns:
        st.error("Noise data must include 'timestamp' and 'icao' columns.")
        st.stop()
    df_noise['timestamp'] = pd.to_datetime(df_noise['timestamp'], errors='coerce')
    df_noise.dropna(subset=['timestamp'], inplace=True)
    df_noise['timestamp'] = df_noise['timestamp'].apply(lambda x: x.tz_localize('Europe/Berlin') if x.tzinfo is None else x)
    df_noise['timestamp'] = df_noise['timestamp'].dt.tz_convert('UTC')
    st.subheader("🔊 Noise Data Preview")
    st.dataframe(df_noise.head())
else:
    st.warning("Please upload a noise CSV to proceed.")
    st.stop()

# === Get Flight Arrivals ===
def get_arrivals(icao, api_key, target_day):
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "aerodatabox.p.rapidapi.com"
    }
    base_url = f"https://aerodatabox.p.rapidapi.com/flights/airports/icao/{icao}"
    ranges = [(f"{target_day}T00:00", f"{target_day}T12:00"), (f"{target_day}T12:00", f"{target_day}T23:59")]
    flights = []
    for start, end in ranges:
        url = f"{base_url}/{start}/{end}"
        params = {
            "withLeg": "true", "direction": "Arrival", "withCancelled": "false",
            "withCodeshared": "false", "withCargo": "false", "withPrivate": "false",
            "withLocation": "true"
        }
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            res.raise_for_status()
            for flight in res.json().get("arrivals", []):
                arrival_info = flight.get("arrival", {}).get("airport", {})
                loc = arrival_info.get("location", {})
                lat = loc.get("latitude") or AIRPORTS.get(icao, {}).get("lat")
                lon = loc.get("longitude") or AIRPORTS.get(icao, {}).get("lon")
                departure_info = flight.get("departure", {}).get("airport", {})
                origin_airport_name = departure_info.get("name", "Unknown")
                flights.append({
                    "flight_number": flight.get("number"),
                    "arrival_scheduled_utc": flight.get("arrival", {}).get("scheduledTime", {}).get("utc"),
                    "arrival_latitude": lat,
                    "arrival_longitude": lon,
                    "model": flight.get("aircraft", {}).get("model"),
                    "icao": icao,
                    "origin_airport_name": origin_airport_name
                })
        except Exception as e:
            st.warning(f"Error fetching arrivals for {icao}: {e}")
    return pd.DataFrame(flights)

# Fetch Arrivals
df_arrivals = pd.DataFrame()
if api_key and icao_list:
    st.subheader(f"🛬 Arrivals on {selected_date}")
    all_arrivals = []
    for icao in icao_list:
        df = get_arrivals(icao, api_key, selected_date.isoformat())
        if not df.empty:
            df['arrival_scheduled_utc'] = pd.to_datetime(df['arrival_scheduled_utc'], utc=True, errors='coerce')
            all_arrivals.append(df)
            st.write(f"{icao} Sample Arrivals", df.head())
    if all_arrivals:
        df_arrivals = pd.concat(all_arrivals)
else:
    st.info("Enter your API key and select airports to fetch data.")

# Weather Info
def get_weather(lat, lon, key):
    try:
        res = requests.get(f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}&units=metric")
        res.raise_for_status()
        d = res.json()
        return {
            "desc": d['weather'][0]['description'].title(),
            "temp": d['main']['temp'],
            "wind": d['wind']['speed'],
            "humidity": d['main'].get('humidity', 'N/A'),
        }
    except Exception:
        return None

# Merge
def merge_by_time(df_noise, df_arrivals):
    df_arrivals = df_arrivals.dropna(subset=["arrival_scheduled_utc"]).sort_values("arrival_scheduled_utc")
    df_noise = df_noise.sort_values("timestamp")
    return pd.merge_asof(df_noise, df_arrivals, left_on="timestamp", right_on="arrival_scheduled_utc", direction="nearest", tolerance=pd.Timedelta("15m"))

# === Visualizations ===
def plot_map(df):
    if df[['arrival_latitude', 'arrival_longitude']].notnull().all(axis=1).any():
        df_map = df.dropna(subset=['arrival_latitude', 'arrival_longitude']).copy()

        def map_color(icao):
            colors = {"EDDB": [255, 0, 0, 160], "LFPG": [0, 255, 0, 160], "EGLL": [0, 0, 255, 160]}
            return colors.get(icao, [0, 100, 255, 160])

        df_map['color'] = df_map['icao'].apply(map_color)

        heat_layer = pdk.Layer(
            "HeatmapLayer",
            data=df_map,
            get_position='[arrival_longitude, arrival_latitude]',
            get_weight=1,
            radiusPixels=60,
        )
        view_state = pdk.ViewState(
            latitude=df_map['arrival_latitude'].mean(),
            longitude=df_map['arrival_longitude'].mean(),
            zoom=6
        )
        st.pydeck_chart(pdk.Deck(
            layers=[heat_layer],
            initial_view_state=view_state,
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
        ))
    else:
        fallback_df = pd.DataFrame([{
            "icao": code,
            "arrival_latitude": AIRPORTS[code]['lat'],
            "arrival_longitude": AIRPORTS[code]['lon']
        } for code in icao_list if code in AIRPORTS])
        st.warning("No coordinates found in flight data. Showing airport fallback locations.")
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=fallback_df,
            get_position='[arrival_longitude, arrival_latitude]',
            get_color='[255, 165, 0]',
            get_radius=1000,
        )
        view_state = pdk.ViewState(
            latitude=fallback_df['arrival_latitude'].mean(),
            longitude=fallback_df['arrival_longitude'].mean(),
            zoom=6
        )
        st.pydeck_chart(pdk.Deck(
            layers=[scatter_layer],
            initial_view_state=view_state,
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
        ))

def plot_noise_subplots(df):
    st.write("### 📈 Noise Levels Over Time by Airport")
    fig, axes = plt.subplots(len(icao_list), 1, figsize=(10, 3 * len(icao_list)), sharex=True)
    if len(icao_list) == 1:
        axes = [axes]
    for ax, icao in zip(axes, icao_list):
        sns.lineplot(data=df[df['icao'] == icao], x='timestamp', y='noise_db', ax=ax)
        ax.set_title(icao)
        ax.set_ylabel("Noise (dB)")
    plt.tight_layout()
    st.pyplot(fig)

def plot_arrival_histograms(df):
    st.write("### ✈️ Arrivals per Hour by Airport")
    fig, ax = plt.subplots(figsize=(10, 4))
    for icao in df['icao'].unique():
        subset = df[df['icao'] == icao].copy()
        subset['hour'] = subset['arrival_scheduled_utc'].dt.hour
        sns.histplot(subset['hour'], label=icao, bins=24, alpha=0.5, ax=ax)
    ax.set_xlabel("Hour (UTC)")
    ax.set_ylabel("Arrivals")
    ax.legend()
    st.pyplot(fig)

def plot_combined_hourly(df_noise, df_arrivals):
    st.write("### ⏱️ Noise vs Arrivals per Hour")
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()  # Create just once outside the loop

    for icao in icao_list:
        n = df_noise[df_noise['icao'] == icao].copy()
        a = df_arrivals[df_arrivals['icao'] == icao].copy()
        if n.empty or a.empty:
            continue
        n['hour'] = n['timestamp'].dt.hour
        a['hour'] = a['arrival_scheduled_utc'].dt.hour

        # Group by hour
        noise_avg = n.groupby('hour')['noise_db'].mean()
        arr_count = a.groupby('hour').size()

        # Bar chart for arrivals on ax1
        ax1.bar(arr_count.index, arr_count.values, alpha=0.3, label=f"{icao} Arrivals")

        # Line chart for noise on ax2
        ax2.plot(noise_avg.index, noise_avg.values, marker='o', linestyle='--', label=f"{icao} Noise")

    ax1.set_xlabel("Hour (UTC)")
    ax1.set_ylabel("Arrivals", color='tab:blue')
    ax2.set_ylabel("Avg Noise (dB)", color='tab:red')

    # Combine both legends
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    st.pyplot(fig)

# === Main Display ===
if not df_arrivals.empty and not df_noise.empty:
    merged_df = merge_by_time(df_noise, df_arrivals)
    plot_map(df_arrivals)
    plot_noise_subplots(df_noise)
    plot_arrival_histograms(df_arrivals)
    plot_combined_hourly(df_noise, df_arrivals)

# === Weather Summary ===
weather_records = []

for icao in icao_list:
    info = AIRPORTS.get(icao)
    if weather_key and info:
        w = get_weather(info['lat'], info['lon'], weather_key)
        if w:
            weather_records.append({
                "ICAO": icao,
                "City": info.get("city", "Unknown"),
                "Weather": w.get("desc", "Unknown"),
                "Temperature (°C)": w.get("temp"),
                "Wind (m/s)": w.get("wind"),
                "Humidity (%)": w.get("humidity")
            })

if weather_records:
    st.subheader("🌤️ Weather and City Info for Selected Airports")
    df_weather = pd.DataFrame(weather_records).set_index("ICAO")
    
    st.dataframe(df_weather[["City", "Weather"]])
    st.bar_chart(df_weather[["Temperature (°C)", "Wind (m/s)", "Humidity (%)"]])























































