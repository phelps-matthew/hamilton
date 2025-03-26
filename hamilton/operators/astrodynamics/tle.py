from requests.auth import HTTPBasicAuth
from loguru import logger
from time import sleep
import requests
from typing import Optional, Tuple
import os

def tle_from_norad_sat_id(sat_id: int) -> tuple[str, str]:
    """Get the TLE for a given NORAD satellite ID.
    
    First tries Celestrak (no auth needed), falls back to Space-Track if needed.
    
    Args:
        sat_id: NORAD catalog ID of the satellite
        
    Returns:
        Tuple of (TLE line 1, TLE line 2)
    """
    logger.debug(f"Retrieving TLE for satellite ID: {sat_id}")
    # Try Celestrak first (no auth required)
    logger.debug(f"Attempting to retrieve TLE from Celestrak for satellite ID: {sat_id}")
    celestrak_tle = get_tle_from_celestrak(sat_id)
    if celestrak_tle:
        logger.debug(f"Successfully retrieved TLE from Celestrak for satellite ID: {sat_id}")
        return celestrak_tle
    
    # Fall back to Space-Track if Celestrak fails
    logger.debug(f"Celestrak retrieval failed, falling back to Space-Track for satellite ID: {sat_id}")
    return get_tle_from_spacetrack(sat_id)


def get_tle_from_celestrak(sat_id: int) -> Optional[Tuple[str, str]]:
    """Get TLE from Celestrak's API.
    
    Args:
        sat_id: NORAD catalog ID
        
    Returns:
        Tuple of (TLE line 1, TLE line 2) or None if not found
    """
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={sat_id}&FORMAT=TLE"
    logger.debug(f"Making request to Celestrak: {url}")
    try:
        response = requests.get(url, timeout=10)
        logger.debug(f"Celestrak response status code: {response.status_code}")
        
        if response.status_code == 200 and len(response.text.strip().split('\n')) >= 3:
            lines = response.text.strip().split('\n')
            logger.debug(f"Celestrak returned {len(lines)} lines")
            # Celestrak returns 3 lines: name, TLE line 1, TLE line 2
            return lines[1], lines[2]
        
        logger.debug(f"Celestrak did not return valid TLE data for satellite ID: {sat_id}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching TLE from Celestrak for satellite ID {sat_id}: {e}")
        return None


def get_tle_from_spacetrack(sat_id: int) -> Tuple[str, str]:
    """Get TLE from Space-Track using credentials.
    
    Args:
        sat_id: NORAD catalog ID
        
    Returns:
        Tuple of (TLE line 1, TLE line 2)
        
    Raises:
        Exception: If TLE cannot be retrieved
    """
    # Space-Track credentials should be configured in your environment or config
    username = os.environ.get("SPACETRACK_USERNAME", None)
    password = os.environ.get("SPACETRACK_PASSWORD", None)
    logger.debug(f"Using Space-Track credentials for user: {username}")
    
    if username is None or password is None:
        logger.error("Space-Track credentials not found in environment variables")
        raise Exception("Space-Track credentials not found in environment variables")
    
    # Login to Space-Track
    auth_url = "https://www.space-track.org/ajaxauth/login"
    auth_data = {
        "identity": username,
        "password": password
    }
    
    logger.debug("Authenticating with Space-Track")
    session = requests.Session()
    login_response = session.post(auth_url, data=auth_data)
    
    if login_response.status_code != 200:
        logger.error(f"Failed to authenticate with Space-Track: {login_response.status_code}")
        raise Exception(f"Failed to authenticate with Space-Track: {login_response.status_code}")
    
    logger.debug("Successfully authenticated with Space-Track")
    
    # Query for the TLE
    tle_url = f"https://www.space-track.org/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{sat_id}/orderby/TLE_LINE1 ASC/format/tle"
    logger.debug(f"Querying Space-Track for TLE: {tle_url}")
    
    try:
        response = session.get(tle_url)
        logger.debug(f"Space-Track response status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get TLE from Space-Track: {response.status_code}")
            raise Exception(f"Failed to get TLE from Space-Track: {response.status_code}")
        
        tle_data = response.text.strip().split('\n')
        logger.debug(f"Space-Track returned {len(tle_data)} lines")
        
        if len(tle_data) < 2:
            logger.error(f"Invalid TLE data received for satellite ID {sat_id}")
            raise Exception(f"Invalid TLE data received for satellite ID {sat_id}")
        
        # Space-Track returns TLEs in pairs of lines
        logger.debug(f"Successfully retrieved TLE from Space-Track for satellite ID: {sat_id}")
        return tle_data[0], tle_data[1]
    
    finally:
        # Logout from Space-Track
        logger.debug("Logging out from Space-Track")
        session.get("https://www.space-track.org/auth/logout")
        sleep(1)  # Be nice to the API

def batch_tle_from_norad_sat_ids(sat_ids: list[int]) -> dict[int, tuple[str, str]]:
    """Get TLEs for multiple NORAD satellite IDs efficiently.
    
    First tries Celestrak (batch request), then falls back to Space-Track for any missing satellites.
    
    Args:
        sat_ids: List of NORAD catalog IDs
        
    Returns:
        Dictionary mapping satellite IDs to tuples of (TLE line 1, TLE line 2)
    """
    # Try Celestrak first (supports batch requests)
    logger.debug(f"Attempting to retrieve TLEs from Celestrak for {len(sat_ids)} satellites")
    results = batch_tle_from_celestrak(sat_ids)
    
    # Check if any satellites are missing
    missing_ids = [sat_id for sat_id in sat_ids if sat_id not in results]
    logger.debug(f"Missing satellites from Celestrak: {missing_ids}")
    
    # If we have missing satellites, try Space-Track
    if missing_ids:
        logger.debug(f"Attempting to retrieve {len(missing_ids)} missing TLEs from Space-Track")
        space_track_results = batch_tle_from_spacetrack(missing_ids)
        # Merge the results
        results.update(space_track_results)
    
    logger.debug(f"Successfully retrieved TLEs for {len(results)} out of {len(sat_ids)} satellites")
    return results


def batch_tle_from_celestrak(sat_ids: list[int]) -> dict[int, tuple[str, str]]:
    """Get TLEs for multiple satellites from Celestrak in a single request.
    
    Args:
        sat_ids: List of NORAD catalog IDs
        
    Returns:
        Dictionary mapping satellite IDs to tuples of (TLE line 1, TLE line 2)
    """
    logger.debug(f"Attempting to retrieve TLEs from Celestrak for {len(sat_ids)} satellites")
    
    # Celestrak allows comma-separated IDs
    id_list = "&".join([f"CATNR={sat_id}" for sat_id in sat_ids])
    url = f"https://celestrak.org/NORAD/elements/gp.php?{id_list}&FORMAT=TLE"
    logger.debug(f"Making batch request to Celestrak: {url}")
    
    results = {}
    try:
        response = requests.get(url, timeout=10)
        logger.debug(f"Celestrak batch response status code: {response.status_code}")
        logger.debug(f"Celestrak batch raw response: {repr(response.text)}")
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            logger.debug(f"Celestrak returned {len(lines)} lines for batch request")
            
            # Process the TLEs (every 3 lines is a complete entry)
            for i in range(0, len(lines), 3):
                if i+2 < len(lines):
                    # Extract satellite ID from line 2 (positions 2-6)
                    try:
                        logger.debug(f"Processing line group: {lines[i:i+3]}")
                        sat_id = int(lines[i+1][2:7].strip())
                        results[sat_id] = (lines[i+1], lines[i+2])
                        logger.debug(f"Parsed TLE for satellite ID: {sat_id}")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse satellite ID from TLE: {lines[i+1] if i+1 < len(lines) else 'unknown'}, error: {e}")
    except Exception as e:
        logger.warning(f"Error fetching TLEs from Celestrak: {e}")
    
    logger.debug(f"Successfully retrieved {len(results)} TLEs from Celestrak batch request")
    return results


def batch_tle_from_spacetrack(sat_ids: list[int]) -> dict[int, tuple[str, str]]:
    """Get TLEs for multiple satellites from Space-Track in a single request.
    
    Args:
        sat_ids: List of NORAD catalog IDs
        
    Returns:
        Dictionary mapping satellite IDs to tuples of (TLE line 1, TLE line 2)
    """
    logger.debug(f"Attempting to retrieve TLEs from Space-Track for {len(sat_ids)} satellites")
    # Space-Track credentials
    username = os.environ.get("SPACETRACK_USERNAME", None)
    password = os.environ.get("SPACETRACK_PASSWORD", None)
    logger.debug(f"Using Space-Track credentials for user: {username}")
    
    if username is None or password is None:
        logger.error("Space-Track credentials not found in environment variables")
        raise Exception("Space-Track credentials not found in environment variables")
    
    # Login to Space-Track
    auth_url = "https://www.space-track.org/ajaxauth/login"
    auth_data = {
        "identity": username,
        "password": password
    }
    
    logger.debug("Authenticating with Space-Track for batch request")
    session = requests.Session()
    login_response = session.post(auth_url, data=auth_data)
    
    if login_response.status_code != 200:
        logger.error(f"Failed to authenticate with Space-Track: {login_response.status_code}")
        raise Exception(f"Failed to authenticate with Space-Track: {login_response.status_code}")
    
    logger.debug("Successfully authenticated with Space-Track for batch request")
    
    # Create comma-separated list of satellite IDs
    id_str = ",".join(str(sat_id) for sat_id in sat_ids)
    
    # Query for the TLEs
    tle_url = f"https://www.space-track.org/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{id_str}/orderby/NORAD_CAT_ID ASC/format/tle"
    logger.debug(f"Querying Space-Track for batch TLEs: {tle_url}")
    
    results = {}
    try:
        response = session.get(tle_url)
        logger.debug(f"Space-Track batch response status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get TLEs from Space-Track: {response.status_code}")
            raise Exception(f"Failed to get TLEs from Space-Track: {response.status_code}")
        
        lines = response.text.strip().split('\n')
        logger.debug(f"Space-Track returned {len(lines)} lines for batch request")
        
        # Process the TLEs (every 2 lines is a complete entry)
        for i in range(0, len(lines), 2):
            if i+1 < len(lines):
                try:
                    # Extract satellite ID from line 1 (positions 2-7)
                    sat_id = int(lines[i][2:7].strip())
                    results[sat_id] = (lines[i], lines[i+1])
                    logger.trace(f"Parsed TLE for satellite ID: {sat_id}")
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse satellite ID from TLE: {lines[i] if i < len(lines) else 'unknown'}")
    
    finally:
        # Logout from Space-Track
        logger.debug("Logging out from Space-Track after batch request")
        session.get("https://www.space-track.org/auth/logout")
        sleep(1)  # Be nice to the API
    
    logger.debug(f"Successfully retrieved {len(results)} TLEs from Space-Track batch request")
    return results


# Example usage
if __name__ == "__main__":
    # Test single satellite
    logger.info("Testing single TLE retrieval from Celestrak")
    logger.info(tle_from_norad_sat_id(61072))
    
    # Test Space-Track retrieval
    logger.info("Testing TLE retrieval from Space-Track")
    # Force Space-Track by temporarily modifying get_tle_from_celestrak to return None
    original_func = get_tle_from_celestrak
    get_tle_from_celestrak = lambda x: None
    logger.info(tle_from_norad_sat_id(61072))
    get_tle_from_celestrak = original_func
    
    # Test fallback mechanism
    logger.info("Testing TLE retrieval from Celestrak with Space-Track fallback")
    logger.info(tle_from_norad_sat_id(61072))
    
    # Test batch retrieval
    logger.info("Testing batch TLE retrieval")
    sat_ids = [25544, 61072, 33591]  # ISS, your previous example, and another satellite
    results = batch_tle_from_norad_sat_ids(sat_ids)
    for sat_id, tle in results.items():
        logger.info(f"Satellite {sat_id}: {tle}")
