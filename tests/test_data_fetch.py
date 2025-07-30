import pandas as pd
from data_fetch import load_noise_data, get_airport_coordinates

def test_load_noise_data():
    # Create a sample DataFrame and save it to a temp CSV
    sample_data = pd.DataFrame({
        'timestamp': ['2025-07-17T12:00:00Z'],
        'noise_level': [65],
        'airport': ['EDDB']
    })
    sample_data.to_csv('sample_noise.csv', index=False)

    # Load it using your function
    df = load_noise_data('sample_noise.csv')

    assert isinstance(df, pd.DataFrame)
    assert 'noise_level' in df.columns
    assert df.iloc[0]['airport'] == 'EDDB'

def test_get_airport_coordinates():
    coords = get_airport_coordinates('EDDB')
    assert isinstance(coords, dict)
    assert 'lat' in coords and 'lon' in coords
    assert isinstance(coords['lat'], float)
