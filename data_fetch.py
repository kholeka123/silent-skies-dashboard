import pandas as pd
import requests

def load_noise_data(uploaded_file):
    """Load noise data from CSV or XLSX and parse 'timestamp' column if present."""
    try:
        if isinstance(uploaded_file, str):  # local path (for testing)
            if uploaded_file.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.endswith(".xlsx"):
                df = pd.read_excel(uploaded_file)
            else:
                raise ValueError("Unsupported file type")
        else:  # Streamlit uploaded file-like object
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded_file)
            else:
                raise ValueError("Unsupported file type")

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df

    except Exception as e:
        raise RuntimeError(f"Failed to load file: {e}")

def get_weather(lat, lon, api_key):
    """Fetch current weather from OpenWeatherMap API."""
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "Temperature (°C)": data["main"]["temp"],
            "Wind Speed (m/s)": data["wind"]["speed"],
            "Conditions": data["weather"][0]["description"].capitalize(),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather: {e}")

def enrich_with_weather(df, lat, lon, api_key):
    """Add weather details as columns to the DataFrame."""
    try:
        weather = get_weather(lat, lon, api_key)
        for key, value in weather.items():
            df[key] = value
        return df
    except Exception as e:
        raise RuntimeError(f"Failed to enrich with weather: {e}")

def merge_by_time(
    df_noise,
    df_flights,
    time_col_noise="timestamp",
    time_col_flight="arrival_scheduled_utc",
    tolerance="5min",
):
    """Merge noise and flight data on nearest timestamps within a time tolerance."""
    try:
        if time_col_noise not in df_noise.columns:
            raise ValueError(f"Missing column '{time_col_noise}' in noise data.")
        if time_col_flight not in df_flights.columns:
            raise ValueError(f"Missing column '{time_col_flight}' in flight data.")

        # Ensure consistent timezone awareness for merging
        if pd.api.types.is_datetime64tz_dtype(df_noise[time_col_noise]):
            # noise is timezone-aware
            if not pd.api.types.is_datetime64tz_dtype(df_flights[time_col_flight]):
                # flights is naive — convert flights to UTC aware
                df_flights[time_col_flight] = df_flights[time_col_flight].dt.tz_localize("UTC")
        else:
            # noise is naive
            if pd.api.types.is_datetime64tz_dtype(df_flights[time_col_flight]):
                # flights is aware — convert flights to naive (UTC)
                df_flights[time_col_flight] = df_flights[time_col_flight].dt.tz_convert(None)

        df_noise_sorted = df_noise.sort_values(by=time_col_noise).copy()
        df_flights_sorted = df_flights.sort_values(by=time_col_flight).copy()

        df_merged = pd.merge_asof(
            df_noise_sorted,
            df_flights_sorted,
            left_on=time_col_noise,
            right_on=time_col_flight,
            direction="nearest",
            tolerance=pd.Timedelta(tolerance),
        )
        return df_merged
    except Exception as e:
        raise RuntimeError(f"Failed to merge data: {e}")








