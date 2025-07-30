import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import pydeck as pdk
from datetime import datetime, timedelta
import requests

# ================================
# Load API keys from Streamlit Cloud secrets
# ================================
aero_key = st.secrets["AERODATABOX_API_KEY"]
weather_key = st.secrets["OPENWEATHER_API_KEY"]

# ================================
# Function to fetch arrivals from AeroDataBox API
# ================================
def fetch_arrivals(airport_code, hours=24):
    """Fetch recent flight arrivals for the given airport."""
    try:
        url = f"https://aerodatabox.p.rapidapi.com/flights/airports/icao/{airport_code}/{(datetime.utcnow()-timedelta(hours=hours)).isoformat()}Z/{datetime.utcnow().isoformat()}Z"
        headers = {
            "X-RapidAPI-Key": aero_key,
            "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        flights = []
        for flight in data.get("arrivals", []):
            flights.append({
                "icao24": flight.get("icao24"),
                "callsign": flight.get("callsign"),
                "arrivalTime": flight.get("arrival", {}).get("scheduledTimeLocal"),
                "origin": flight.get("origin", {}).get("airport", {}).get("name"),
                "aircraftModel": flight.get("aircraft", {}).get("model"),
            })
        return pd.DataFrame(flights)
    except Exception as e:
        st.error(f"Error fetching arrivals: {e}")
        return pd.DataFrame()

# ================================
# Function to fetch weather from OpenWeatherMap API
# ================================
def fetch_weather(lat, lon):
    """Fetch current weather for a given location."""
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_key}&units=metric"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching weather: {e}")
        return None

# ================================
# Function to plot noise trends
# ================================
def plot_noise_trends(noise_df):
    """Plot noise level trends over time."""
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.lineplot(data=noise_df, x="timestamp", y="noise_level", ax=ax)
    ax.set_title("Noise Levels Over Time")
    ax.set_xlabel("Time")
    ax.set_ylabel("Noise Level (dB)")
    plt.xticks(rotation=45)
    st.pyplot(fig)

# ================================
# Main Streamlit app
# ================================
st.set_page_config(page_title="Silent Skies Dashboard", layout="wide")
st.title("Silent Skies Dashboard")
st.write("Integrating Aircraft Noise, Flight Arrivals, and Weather Data")

# File uploader
noise_file = st.file_uploader("Upload Aircraft Noise Data CSV", type=["csv"])

# Airport selection
airport_code = st.text_input("Enter ICAO Airport Code (e.g., EGLL for Heathrow)", "EGLL")

if st.button("Fetch Data"):
    with st.spinner("Fetching flight arrivals..."):
        arrivals_df = fetch_arrivals(airport_code)

    if not arrivals_df.empty:
        st.subheader("Flight Arrivals")
        st.dataframe(arrivals_df)

        # Weather info (using airport's approximate lat/lon)
        # You can replace this with actual geocoding
        airport_lat, airport_lon = 51.4700, -0.4543  # Example: Heathrow
        weather = fetch_weather(airport_lat, airport_lon)
        if weather:
            st.subheader("Current Weather")
            st.write(f"Temperature: {weather['main']['temp']}°C")
            st.write(f"Conditions: {weather['weather'][0]['description']}")

    # Process noise file if uploaded
    if noise_file is not None:
        noise_df = pd.read_csv(noise_file, parse_dates=["timestamp"])
        st.subheader("Noise Data")
        st.dataframe(noise_df.head())

        plot_noise_trends(noise_df)

        # Example PyDeck map
        st.subheader("Noise Event Locations")
        if {"lat", "lon"}.issubset(noise_df.columns):
            noise_layer = pdk.Layer(
                "ScatterplotLayer",
                data=noise_df,
                get_position="[lon, lat]",
                get_color="[200, 30, 0, 160]",
                get_radius=100,
            )
            view_state = pdk.ViewState(latitude=noise_df["lat"].mean(),
                                       longitude=noise_df["lon"].mean(),
                                       zoom=10)
            st.pydeck_chart(pdk.Deck(layers=[noise_layer], initial_view_state=view_state))
else:
    st.info("Enter an airport code and click **Fetch Data** to begin.")













































