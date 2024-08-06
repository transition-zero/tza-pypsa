import numpy as np


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