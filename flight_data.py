import streamlit as st
from data_fetch import load_noise_data, enrich_with_weather, merge_by_time
from flight_data import get_arrivals
import os
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Load API keys
load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
AERODATABOX_API_KEY = os.getenv("AERODATABOX_API_KEY")

# Streamlit UI
st.title("Silent Skies: Aircraft Noise and Flight Arrivals Dashboard")

uploaded_file = st.file_uploader("Upload Noise Data CSV or XLSX", type=["csv", "xlsx"])

if uploaded_file is not None:
    noise_df = None
    try:
        noise_df = load_noise_data(uploaded_file)
        st.success(f"Loaded noise data with {len(noise_df)} records.")
    except Exception as e:
        st.error(f"Error loading noise data: {e}")

    if noise_df is not None:
        icao_code = st.text_input("Enter ICAO Airport Code (e.g., EDDB, EGLL, LFPG):").upper().strip()
        lat = st.text_input("Airport Latitude (decimal degrees):")
        lon = st.text_input("Airport Longitude (decimal degrees):")

        if icao_code and lat and lon:
            try:
                lat = float(lat.replace(',', '.'))
                lon = float(lon.replace(',', '.'))
            except ValueError:
                st.error("Invalid latitude or longitude. Use decimal numbers (e.g., 52.362250).")
                st.stop()

            try:
                arrivals_df = get_arrivals(icao_code, AERODATABOX_API_KEY)
                st.success(f"Fetched {len(arrivals_df)} upcoming arrival flights for {icao_code}.")
            except Exception as e:
                st.error(f"Error fetching arrivals: {e}")
                arrivals_df = None

            if OPENWEATHER_API_KEY:
                try:
                    noise_df = enrich_with_weather(noise_df, lat, lon, OPENWEATHER_API_KEY)
                    st.success("Enriched noise data with current weather conditions.")
                except Exception as e:
                    st.error(f"Error fetching weather: {e}")
            else:
                st.warning("OpenWeather API key not found. Skipping weather enrichment.")

            if arrivals_df is not None:
                try:
                    merged_df = merge_by_time(noise_df, arrivals_df)
                    st.success(f"Merged datasets with {len(merged_df.dropna())} matching records.")
                    st.dataframe(merged_df)

                    # Rename and clean columns
                    merged_df = merged_df.rename(columns={
                        'noise_db': 'dB',
                        'icao': 'airport'
                    })

                    required_cols = {'timestamp', 'dB', 'airport'}
                    if not required_cols.issubset(merged_df.columns):
                        st.error(f"Missing required columns: {required_cols - set(merged_df.columns)}")
                        st.stop()

                    merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'], errors='coerce')
                    merged_df.dropna(subset=['timestamp', 'dB', 'airport'], inplace=True)

                    merged_df['hour'] = merged_df['timestamp'].dt.hour
                    avg_db_hourly = merged_df.groupby(['airport', 'hour'])['dB'].mean().reset_index()

                    # Plotting
                    fig, ax = plt.subplots(figsize=(14, 7))
                    sns.set_style("whitegrid")

                    # Histogram bars
                    sns.barplot(
                        data=avg_db_hourly,
                        x='hour',
                        y='dB',
                        hue='airport',
                        palette='Set2',
                        ci=None,
                        dodge=True,
                        ax=ax
                    )

                    # Overlay trend lines
                    for airport in avg_db_hourly['airport'].unique():
                        airport_data = avg_db_hourly[avg_db_hourly['airport'] == airport]
                        ax.plot(
                            airport_data['hour'],
                            airport_data['dB'],
                            marker='o',
                            linewidth=2,
                            label=f"{airport} Trend"
                        )

                    ax.set_title("Average Noise Level (dB) per Hour with Overlaid Trends")
                    ax.set_xlabel("Hour of Day")
                    ax.set_ylabel("Average Noise Level (dB)")
                    ax.set_xticks(range(0, 24))
                    ax.legend(title="Airport", loc='upper right')
                    fig.tight_layout()

                    st.pyplot(fig)

                except Exception as e:
                    st.error(f"Failed to merge or visualize datasets: {e}")














