import requests
import logging
import json # Import json for decoding check

logger = logging.getLogger("BackendComm")

def get_config_from_backend(base_url, device_id, timeout=10):
    """
    Fetches device configuration from the backend API.
    Returns the configuration dictionary on success, None on failure.
    """
    if not base_url.startswith(('http://', 'https://')):
         logger.error(f"Invalid BackendURL format: {base_url}")
         return None

    # Ensure trailing slash is handled correctly
    safe_base_url = base_url.rstrip('/')
    url = f"{safe_base_url}/api/devices/{device_id}/config"
    logger.info(f"Requesting configuration from: {url}")

    headers = {'Accept': 'application/json'}

    try:
        response = requests.get(url, timeout=timeout, headers=headers)

        # Check for successful status code (2xx)
        response.raise_for_status()

        # Try to decode JSON
        config_data = response.json()
        logger.debug(f"Received config data: {config_data}")
        if isinstance(config_data, dict):
             return config_data
        else:
             logger.warning(f"Received config, but it's not a JSON object (dictionary): {type(config_data)}")
             return None # Or maybe {} if empty dict is acceptable default

    except requests.exceptions.HTTPError as e:
        # Handle specific HTTP errors (4xx, 5xx)
        if e.response.status_code == 404:
            logger.warning(f"Device configuration not found on backend (404) for ID {device_id}.")
        else:
            logger.error(f"HTTP error fetching config from {url}: {e.response.status_code} {e.response.reason}")
            logger.debug(f"Response body: {e.response.text}")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error fetching config from {url}: {e}")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching config from {url} after {timeout} seconds.")
        return None
    except requests.exceptions.RequestException as e:
        # Catch other potential requests errors
        logger.error(f"Error fetching config from {url}: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON received from backend config endpoint {url}. Body: {response.text}")
        return None
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error during config fetch: {e}", exc_info=True)
        return None
