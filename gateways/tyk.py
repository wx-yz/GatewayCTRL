# filepath: gateways/tyk.py
import requests
import logging
from typing import Dict, List, Optional, Union
from .base import BaseGateway, GatewayConfig

logger = logging.getLogger(__name__)

class TykGateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        """Initializes the Tyk Gateway client."""
        super().__init__(config)
        self.base_url = config.url.rstrip('/')
        self.auth_secret = config.additional_config.get('tyk_auth_secret')

        if not self.auth_secret:
            logger.warning("Tyk Authorization Secret ('tyk_auth_secret') is missing in the configuration.")

        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            **({'X-Tyk-Authorization': self.auth_secret} if self.auth_secret else {})
        }

        self.verify = config.cert_path if config.cert_path else config.verify_ssl
        logger.debug(f"Initialized Tyk gateway. URL: {self.base_url}, SSL Verify: {self.verify}, Auth Header Set: {bool(self.auth_secret)}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Union[Dict, List, None]:
        """
        Makes an authenticated request to the Tyk Gateway API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path (e.g., '/tyk/apis').
            **kwargs: Additional arguments passed to requests.request (e.g., json, params).

        Returns:
            A dictionary or list containing the JSON response on success,
            None if the response is empty but successful,
            or a dictionary containing error details on failure.
        """
        if not self.auth_secret and 'X-Tyk-Authorization' not in self.headers:
            logger.error("Cannot make request: Tyk Authorization Secret is missing.")
            return {"error": True, "message": "Tyk Authorization Secret is missing in configuration.", "status": "Configuration Error"}

        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making {method} request to {url}")
        response = None
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                verify=self.verify,
                timeout=15,
                **kwargs
            )
            logger.debug(f"Response status code: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
            response.raise_for_status()

            if not response.content:
                logger.debug("Successful response with empty content.")
                return None

            try:
                json_response = response.json()
                logger.debug("Successfully parsed JSON response.")
                return json_response
            except requests.exceptions.JSONDecodeError:
                logger.warning(f"Successful response from {method} {url} but content is not valid JSON. Status: {response.status_code}. Content: {response.text[:200]}...")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Request timed out: {method} {url}")
            return {"error": True, "message": "Request timed out", "status": "Timeout"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error: {str(e)}", exc_info=False)
            error_details = "No response body or non-JSON error response"
            status_code = "N/A"
            if e.response is not None:
                status_code = e.response.status_code
                try:
                    error_details = e.response.json()
                    logger.error(f"Tyk API Error Response (JSON): {error_details}")
                except requests.exceptions.JSONDecodeError:
                    error_details = e.response.text
                    logger.error(f"Tyk API Error Response (non-JSON): {error_details[:500]}...")
            return {"error": True, "message": str(e), "status": status_code, "details": error_details}
        except Exception as e:
            logger.error(f"Unexpected error processing request to {url}: {str(e)}", exc_info=True)
            return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def test_connection(self) -> bool:
        """Tests the connection and authentication to the Tyk gateway API."""
        logger.info("Testing connection to Tyk gateway...")
        response = self._make_request('GET', '/tyk/apis')

        is_success = not (isinstance(response, dict) and response.get("error"))

        if is_success:
            logger.info("Tyk connection test successful.")
        else:
            logger.error(f"Tyk connection test failed. Response: {response}")

        return is_success

    def get_apis(self) -> List[Dict]:
        """Gets all APIs from the Tyk gateway."""
        logger.debug("Fetching all APIs from Tyk")
        response = self._make_request('GET', '/tyk/apis')

        if isinstance(response, list):
            apis = [{'id': api.get('api_id'), 'name': api.get('name')} for api in response if api.get('api_id') and api.get('name')]
            logger.info(f"Successfully fetched {len(apis)} APIs from Tyk.")
            return apis
        elif isinstance(response, dict) and response.get('error'):
            logger.error(f"Failed to get Tyk APIs: {response.get('message')}")
            return []
        else:
            logger.warning(f"Received unexpected response type ({type(response).__name__}) when fetching Tyk APIs.")
            return []

    def get_api_details(self, api_id: str) -> Optional[Dict]:
        """Gets the full definition for a specific API."""
        logger.debug(f"Getting details for Tyk API {api_id}")
        response = self._make_request('GET', f'/tyk/apis/{api_id}')

        if isinstance(response, dict) and not response.get("error"):
            logger.info(f"Successfully fetched details for API {api_id}.")
            return response
        else:
            logger.error(f"Failed to get details for Tyk API {api_id}. Response: {response}")
            return None

    def create_api(self, api_config: Dict) -> Optional[Dict]:
        """Creates a new API definition in Tyk."""
        logger.info(f"Attempting to create Tyk API: {api_config.get('name', 'N/A')}")
        response = self._make_request('POST', '/tyk/apis', json=api_config)
        if isinstance(response, dict) and not response.get("error"):
            logger.info(f"Successfully created Tyk API. Response: {response}")
            return response
        else:
            logger.error(f"Failed to create Tyk API. Response: {response}")
            return None

    def update_api(self, api_id: str, api_config: Dict) -> bool:
        """Updates an existing API definition in Tyk."""
        logger.info(f"Attempting to update Tyk API {api_id}")
        response = self._make_request('PUT', f'/tyk/apis/{api_id}', json=api_config)
        is_success = not (isinstance(response, dict) and response.get("error"))
        if is_success:
            logger.info(f"Successfully updated Tyk API {api_id}.")
        else:
            logger.error(f"Failed to update Tyk API {api_id}. Response: {response}")
        return is_success

    def delete_api(self, api_id: str) -> bool:
        """Deletes an API definition from Tyk."""
        logger.info(f"Attempting to delete Tyk API {api_id}")
        response = self._make_request('DELETE', f'/tyk/apis/{api_id}')
        is_success = not (isinstance(response, dict) and response.get("error"))
        if is_success:
            logger.info(f"Successfully deleted Tyk API {api_id}.")
        else:
            logger.error(f"Failed to delete Tyk API {api_id}. Response: {response}")
        return is_success

    def get_api_metrics(self, api_id: str) -> Dict:
        """
        Placeholder for getting API metrics (e.g., usage, errors).
        Tyk analytics might require different endpoints or configurations.
        """
        logger.warning(f"get_api_metrics for Tyk API {api_id} is not fully implemented.")
        details = self.get_api_details(api_id)
        return {"definition": details} if details else {"error": "Could not retrieve API details"}