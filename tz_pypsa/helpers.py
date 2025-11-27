import numpy as np
import pandas as pd
import xarray as xr


def haversine(
        lat1 : float, 
        lon1 : float, 
        lat2 : float, 
        lon2 : float,
    ) -> float:
    '''
    
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) using haversine fomula.

    Parameters
    ----------
    
        lat1 : float
            Latitude of point 1
        lon1 : float
            Longitude of point 1
        lat2 : float
            Latitude of point 2
        lon2 : float
            Longitude of point 2
    
    Returns
    ----------
    
        float:
            The distance between the two points in kilometers
    
    '''
    R = 6371  # Earth radius in kilometers
    
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    
    a = np.sin(delta_phi / 2.0) ** 2 + \
        np.cos(phi1) * np.cos(phi2) * \
        np.sin(delta_lambda / 2.0) ** 2
    
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    return R * c

def load_soc_bounds_as_xarray(
        min_csv: str , 
        max_csv: str ,
        unit: str,
    ) -> xr.Dataset:
    """
    Load and merge SOC bounds from flat CSVs.
    
    """
    def process_csv(filepath, var, unit):
        df = pd.read_csv(filepath)
        df = df.loc[df.user_data.notna()]
        df['StorageUnit'] = df['technology'] + ":" + df['node']
        df[unit] = df[unit].astype(int)
        df = df.rename(columns={
            'user_data': var}
            )
        return df.set_index(['StorageUnit', unit])[[var]]

    # Process csv
    df_min = process_csv(min_csv, 'min_frac', unit)
    df_max = process_csv(max_csv, 'max_frac', unit)
    
    # Merge on the Index
    df_merged = pd.concat([df_min, df_max], axis=1, join='outer')

    # Convert to xarray
    ds = df_merged.to_xarray()

    print(f"Loaded SOC bounds for {ds.sizes['StorageUnit']} units and {ds.sizes[unit]} {unit}.")
    
    return ds