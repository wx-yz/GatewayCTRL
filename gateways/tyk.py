# filepath: gateways/tyk.py
import requests
import logging
from typing import Dict, List, Optional
from .base import BaseGateway, GatewayConfig

logger = logging.getLogger(__name__)

class TykGateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        super().__init__(config)
        self.base_url = config.url.rstrip('/')
        self.auth_secret = config.additional_config.get('tyk_auth_secret', '')
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-tyk-authorization': self.auth_secret
        }
        self.verify = config.cert_path if config.cert_path else config.verify_ssl
        logger.debug(f"Initialized Tyk gateway with URL: {self.base_url}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict | List:
        """Make an authenticated request to the Tyk Gateway API. Can return Dict or List."""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making {method} request to {url}")
        response = None # Initialize response variable
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                verify=self.verify,
                **kwargs
            )
            logger.debug(f"Response status code: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # Handle successful response body
            if not response.content:
                logger.debug("Response content is empty, returning empty dict.")
                return {}
            try:
                # Attempt to parse JSON
                json_response = response.json()
                logger.debug("Successfully parsed JSON response.")
                return json_response # Return the parsed JSON (could be dict or list)
            except requests.exceptions.JSONDecodeError:
                # Log warning if successful response is not JSON, but return {} to indicate HTTP success
                logger.warning(f"Successful response from {method} {url} but content is not valid JSON. Status: {response.status_code}. Returning empty dict.")
                return {} # Treat as success for connection test purposes

        except requests.exceptions.RequestException as e:
            # Handle HTTP errors (4xx, 5xx) or connection issues
            logger.error(f"Request Error: {str(e)}", exc_info=True)
            error_details = "No response body or non-JSON error response"
            status_code = "N/A"
            if e.response is not None:
                status_code = e.response.status_code
                try:
                    # Try to get JSON error details from Tyk
                    error_details = e.response.json()
                    logger.error(f"Tyk API Error Response (JSON): {error_details}")
                except requests.exceptions.JSONDecodeError:
                    # If error response isn't JSON, get raw text
                    error_details = e.response.text
                    logger.error(f"Tyk API Error Response (non-JSON): {error_details}")
            # Return a standardized error dictionary
            return {"error": True, "message": str(e), "status": status_code, "details": error_details}
        except Exception as e:
             # Catch any other unexpected errors during request processing
             logger.error(f"Unexpected error processing request to {url}: {str(e)}", exc_info=True)
             return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def get_apis(self) -> List[Dict]:
        """Get all APIs from the Tyk gateway"""
        logger.debug("Fetching all APIs from Tyk")
        # Expecting /tyk/apis to return a list directly now based on test_connection error
        response = self._make_request('GET', '/tyk/apis')
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"Failed to get Tyk APIs: {response.get('message')}")
            return []
        # If the response is a list, return it directly. Otherwise return empty list.
        return response if isinstance(response, list) else []

    def create_api(self, api_config: Dict) -> Dict:
        """Create a new API in the Tyk gateway"""
        logger.debug(f"Creating Tyk API with config: {api_config}")
        # Assuming create returns a Dict
        response = self._make_request('POST', '/tyk/apis', json=api_config)
        return response if isinstance(response, dict) else {'error': True, 'message': 'Unexpected response type'}

    def update_api(self, api_id: str, api_config: Dict) -> Dict:
        """Update an existing API in the Tyk gateway"""
        logger.debug(f"Updating Tyk API {api_id} with config: {api_config}")
        # Assuming update returns a Dict
        response = self._make_request('PUT', f'/tyk/apis/{api_id}', json=api_config)
        return response if isinstance(response, dict) else {'error': True, 'message': 'Unexpected response type'}

    def delete_api(self, api_id: str) -> bool:
        """Delete an API from the Tyk gateway"""
        logger.debug(f"Deleting Tyk API {api_id}")
        # Assuming delete returns a Dict (even if empty on success)
        response = self._make_request('DELETE', f'/tyk/apis/{api_id}')
        # Success if response is a dict and does NOT contain the 'error' key
        return isinstance(response, dict) and not response.get("error", False)

    def get_api_metrics(self, api_id: str) -> Dict:
        """Get details for a specific API"""
        logger.debug(f"Getting details for Tyk API {api_id}")
        # Assuming get specific API returns a Dict
        response = self._make_request('GET', f'/tyk/apis/{api_id}')
        # Return the response directly if it's a dict and not an error, otherwise empty dict
        return response if isinstance(response, dict) and not response.get("error") else {}

    def test_connection(self) -> bool:
        """Test the connection to the Tyk gateway"""
        logger.debug("Testing connection to Tyk gateway")
        try:
            # Attempt to list APIs. _make_request handles response parsing.
            response = self._make_request('GET', '/tyk/apis')

            # Check the type of the response.
            # Success if it's a list (meaning the API call worked and returned a list of APIs)
            # OR if it's a dictionary that does NOT contain the 'error' key.
            is_success = False
            response_type = type(response).__name__
            if isinstance(response, list):
                is_success = True # Successful call returning a list is considered success
                logger.debug("Connection test received a list, considering connection successful.")
            elif isinstance(response, dict):
                is_success = not response.get("error", False)
                logger.debug(f"Connection test received a dict. Error key present: {response.get('error', False)}")
            else:
                logger.warning(f"Connection test received unexpected type: {response_type}")

            # Add detailed logging
            response_summary = {"status": "success", "type": response_type}
            if isinstance(response, dict) and response.get("error"):
                response_summary = response # Log the error details

            logger.debug(f"Connection test response summary: {response_summary}")
            logger.info(f"Tyk connection test result: {is_success}")
            return is_success
        except Exception as e:
            # This catches errors *before* or *after* _make_request if something else goes wrong
            logger.error(f"Connection test failed due to exception in test_connection method: {str(e)}", exc_info=True)
            return False