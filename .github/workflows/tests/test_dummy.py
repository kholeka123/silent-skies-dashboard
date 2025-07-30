import os
import pandas as pd
from data_fetch import load_noise_data

def test_load_noise_data(tmp_path):
    # Create a small test CSV file with lowercase 'timestamp' header
    test_csv_content = "timestamp,NoiseLevel,Airport\n2025-07-17 12:00,65,EDDB"

    test_csv_path = tmp_path / "test_noise.csv"
    test_csv_path.write_text(test_csv_content)

    df = load_noise_data(str(test_csv_path))

    # Assertions
    assert not df.empty
    assert "timestamp" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert df.loc[0, "Airport"] == "EDDB"


