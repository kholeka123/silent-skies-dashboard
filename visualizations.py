# visualizations.py — Silent Skies Dashboard Visualizations

import streamlit as st
import pydeck as pdk
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")

def plot_map(df_arrivals: pd.DataFrame, icao_list: list, airports_info: dict) -> None:
    """
    Render a PyDeck map with arrival airport locations and flight points.

    Args:
        df_arrivals (pd.DataFrame): DataFrame containing arrival flights info.
        icao_list (list): List of ICAO airport codes selected.
        airports_info (dict): Dict with airport lat/lon/city info.
    """
    if df_arrivals.empty:
        st.warning("No arrivals data to plot on map.")
        return

    # Create scatter points for flights on map
    flight_points = df_arrivals.dropna(subset=['arrival_latitude', 'arrival_longitude'])
    flight_layer = pdk.Layer(
        "ScatterplotLayer",
        data=flight_points,
        get_position='[arrival_longitude, arrival_latitude]',
        get_color='[200, 30, 0, 160]',
        get_radius=1000,
        pickable=True,
        auto_highlight=True,
    )

    # Mark selected airports with bigger blue circles
    airport_points = [
        {"name": f"{code} - {airports_info[code]['city']}", 
         "coordinates": [airports_info[code]['lon'], airports_info[code]['lat']]} 
        for code in icao_list if code in airports_info
    ]
    airport_layer = pdk.Layer(
        "ScatterplotLayer",
        data=airport_points,
        get_position='coordinates',
        get_color='[0, 0, 255, 200]',
        get_radius=2000,
        pickable=True,
        auto_highlight=True,
    )

    # Center the map roughly around the first selected airport or fallback
    if airport_points:
        initial_view = pdk.ViewState(
            latitude=airport_points[0]['coordinates'][1],
            longitude=airport_points[0]['coordinates'][0],
            zoom=7,
            pitch=0,
        )
    else:
        initial_view = pdk.ViewState(latitude=52, longitude=13, zoom=4, pitch=0)

    deck = pdk.Deck(
        layers=[flight_layer, airport_layer],
        initial_view_state=initial_view,
        tooltip={"text": "{name}"}
    )

    st.subheader("🗺️ Flight Arrivals Map")
    st.pydeck_chart(deck)

def plot_noise_subplots(df_noise: pd.DataFrame, icao_list: list) -> None:
    """
    Plot noise measurements time series subplots, one subplot per selected airport ICAO.

    Args:
        df_noise (pd.DataFrame): Noise data with 'timestamp', 'noise_db', and 'icao' columns.
        icao_list (list): List of selected ICAO airport codes.
    """
    if df_noise.empty:
        st.warning("No noise data to plot.")
        return

    filtered = df_noise[df_noise['icao'].isin(icao_list)]
    if filtered.empty:
        st.warning("No noise data for selected airports.")
        return

    st.subheader("🔊 Noise Level Over Time by Airport")
    n_airports = len(icao_list)
    fig, axes = plt.subplots(n_airports, 1, figsize=(12, 3 * n_airports), sharex=True)
    if n_airports == 1:
        axes = [axes]

    for ax, icao in zip(axes, icao_list):
        data = filtered[filtered['icao'] == icao]
        if data.empty:
            ax.text(0.5, 0.5, f"No data for {icao}", ha='center', va='center')
            continue
        sns.lineplot(data=data, x='timestamp', y='noise_db', ax=ax)
        ax.set_title(f"Noise Levels at {icao}")
        ax.set_ylabel("Noise (dB)")
        ax.set_xlabel("")
        ax.grid(True)

    plt.xlabel("Time")
    st.pyplot(fig)

def plot_arrival_histograms(df_arrivals: pd.DataFrame) -> None:
    """
    Plot histogram of flight arrivals by hour of day aggregated across airports.

    Args:
        df_arrivals (pd.DataFrame): DataFrame with 'arrival_scheduled_utc' timestamps.
    """
    if df_arrivals.empty:
        st.warning("No arrivals data to plot histogram.")
        return

    st.subheader("✈️ Flight Arrivals by Hour of Day")

    df_arrivals['hour'] = df_arrivals['arrival_scheduled_utc'].dt.hour
    plt.figure(figsize=(10, 4))
    sns.histplot(df_arrivals['hour'], bins=24, kde=False, color='navy')
    plt.xlabel("Hour of Day (UTC)")
    plt.ylabel("Number of Arrivals")
    plt.xticks(range(0, 24))
    plt.grid(True, axis='y')
    st.pyplot(plt.gcf())

def plot_combined_hourly(df_noise: pd.DataFrame, df_arrivals: pd.DataFrame, icao_list: list) -> None:
    """
    Plot combined hourly average noise and number of arrivals by airport.

    Args:
        df_noise (pd.DataFrame): Noise data with 'timestamp', 'noise_db', 'icao'.
        df_arrivals (pd.DataFrame): Arrival data with 'arrival_scheduled_utc', 'icao'.
        icao_list (list): List of selected airports.
    """
    if df_noise.empty or df_arrivals.empty:
        st.warning("Insufficient data for combined hourly plot.")
        return

    st.subheader("📊 Hourly Average Noise & Flight Arrivals")

    # Prepare noise hourly average
    noise = df_noise[df_noise['icao'].isin(icao_list)].copy()
    noise['hour'] = noise['timestamp'].dt.floor('H')
    noise_avg = noise.groupby(['icao', 'hour'])['noise_db'].mean().reset_index()

    # Prepare arrivals hourly count
    arrivals = df_arrivals[df_arrivals['icao'].isin(icao_list)].copy()
    arrivals['hour'] = arrivals['arrival_scheduled_utc'].dt.floor('H')
    arrivals_count = arrivals.groupby(['icao', 'hour']).size().reset_index(name='arrivals_count')

    # Merge on icao and hour
    merged = pd.merge(noise_avg, arrivals_count, on=['icao', 'hour'], how='outer').fillna(0)

    # Plot per airport
    n_airports = len(icao_list)
    fig, axes = plt.subplots(n_airports, 1, figsize=(14, 4 * n_airports), sharex=True)

    if n_airports == 1:
        axes = [axes]

    for ax, icao in zip(axes, icao_list):
        data = merged[merged['icao'] == icao].sort_values('hour')
        if data.empty:
            ax.text(0.5, 0.5, f"No data for {icao}", ha='center', va='center')
            continue
        ax2 = ax.twinx()
        ax.plot(data['hour'], data['noise_db'], 'b-', label='Avg Noise (dB)')
        ax2.bar(data['hour'], data['arrivals_count'], alpha=0.3, color='orange', label='Arrivals Count')

        ax.set_ylabel("Avg Noise (dB)", color='b')
        ax2.set_ylabel("Arrivals Count", color='orange')
        ax.set_title(f"{icao} Hourly Noise & Arrivals")
        ax.grid(True)
        ax.legend(loc='upper left')
        ax2.legend(loc='upper right')

    plt.xlabel("Time (Hourly)")
    plt.tight_layout()
    st.pyplot(fig)





















