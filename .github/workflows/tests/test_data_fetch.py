import sys
import os
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_fetch import load_noise_data, merge_by_time

@pytest.fixture
def sample_noise_csv(tmp_path):
    csv_content = """timestamp,noise_db
2025-07-17 10:00:00,50
2025-07-17 10:05:00,55
"""
    file = tmp_path / "sample_noise.csv"
    file.write_text(csv_content)
    return str(file)

@pytest.fixture
def sample_flights_df():
    data = {
        "arrival_scheduled_utc": pd.to_datetime(["2025-07-17 10:01:00", "2025-07-17 10:07:00"], utc=True),
        "flight_number": ["AB123", "CD456"],
    }
    return pd.DataFrame(data)

def test_load_noise_data_csv(sample_noise_csv):
    df = load_noise_data(sample_noise_csv)
    assert isinstance(df, pd.DataFrame)
    assert "timestamp" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert len(df) == 2

def test_load_noise_data_wrong_filetype(tmp_path):
    fake_file = tmp_path / "file.txt"
    fake_file.write_text("some text")
    with pytest.raises(RuntimeError, match="Unsupported file type"):
        load_noise_data(str(fake_file))

def test_merge_by_time(sample_flights_df, sample_noise_csv):
    df_noise = load_noise_data(sample_noise_csv)
    df_merged = merge_by_time(df_noise, sample_flights_df, tolerance=pd.Timedelta("2min"))
    assert not df_merged.empty
    assert "flight_number" in df_merged.columns
    assert df_merged.shape[0] == 2
    assert df_merged.iloc[0]["flight_number"] == "AB123"
    assert df_merged.iloc[1]["flight_number"] == "CD456"






