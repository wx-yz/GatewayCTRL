# filepath: gateways/gravitee.py
import requests
import logging
import base64
import json
from typing import Dict, List, Optional, Union
from .base import BaseGateway, GatewayConfig

logger = logging.getLogger(__name__)

class GraviteeGateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        """Initializes the Gravitee Gateway client."""
        super().__init__(config)
        
        # Original base URL from config (e.g., http://localhost:8083)
        management_api_url = config.url.rstrip('/')
        
        self.organization_id = config.additional_config.get('gravitee_organization_id', 'DEFAULT')
        self.environment_id = config.additional_config.get('gravitee_environment_id', 'DEFAULT')
        
        # Construct the new base_url for v2 APIs
        self.base_url = f"{management_api_url}/management/v2/organizations/{self.organization_id}/environments/{self.environment_id}"
        
        self.username = config.additional_config.get('gravitee_username')
        self.password = config.additional_config.get('gravitee_password')

        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        if self.username and self.password:
            auth_string = f"{self.username}:{self.password}"
            encoded_auth_string = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            self.headers['Authorization'] = f"Basic {encoded_auth_string}"
            self.auth_configured = True
            logger.debug("Gravitee Basic Authentication header configured.")
        else:
            self.auth_configured = False
            logger.warning("Gravitee username or password missing. Authentication will not be configured.")

        self.verify = config.cert_path if config.cert_path else config.verify_ssl
        logger.debug(f"Initialized Gravitee gateway. Effective Base URL: {self.base_url}, SSL Verify: {self.verify}, Auth Configured: {self.auth_configured}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Union[Dict, List, None]:
        """Makes an authenticated request to the Gravitee Management API."""
        if not self.auth_configured:
            logger.error("Cannot make request: Gravitee authentication is not configured (username/password missing).")
            return {"error": True, "message": "Gravitee authentication credentials missing.", "status": "Configuration Error"}

        # Ensure endpoint starts with a slash if it's not empty
        if endpoint and not endpoint.startswith('/'):
            url_endpoint = f"/{endpoint}"
        else:
            url_endpoint = endpoint
            
        url = f"{self.base_url}{url_endpoint}" # endpoint is now relative to the new base_url
        logger.debug(f"Making {method} request to Gravitee: {url}")
        response = None
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                verify=self.verify,
                timeout=20,
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
            status_code = "N/A"
            error_details_for_return = "No response body or error in processing."
            content_for_log = "No response body or error in processing."
            if e.response is not None:
                status_code = e.response.status_code
                try:
                    error_details_for_return = e.response.json()
                    content_for_log = json.dumps(error_details_for_return)
                except requests.exceptions.JSONDecodeError:
                    error_details_for_return = e.response.text
                    content_for_log = e.response.text
                except Exception as detail_processing_ex:
                    logger.error(f"Error processing response details for logging: {detail_processing_ex}")
                    if hasattr(e.response, 'text') and e.response.text:
                        content_for_log = e.response.text
                        if error_details_for_return == "No response body or error in processing.":
                             error_details_for_return = e.response.text
            if not isinstance(content_for_log, str):
                try:
                    content_for_log = str(content_for_log)
                except Exception:
                    content_for_log = "Could not convert error content to string for logging."
            logger.error(f"Gravitee API Error Response (Status {status_code}): {content_for_log[:500]}")
            return {"error": True, "message": str(e), "status": status_code, "details": error_details_for_return}
        except Exception as e:
            logger.error(f"Unexpected error processing request to {url}: {str(e)}", exc_info=True)
            return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def test_connection(self) -> bool:
        """Tests the connection and authentication to the Gravitee Management API."""
        logger.info("Testing connection to Gravitee gateway...")
        # For v2, try fetching the current user details relative to the environment
        # The endpoint is typically /user
        response = self._make_request('GET', '/')

        is_success = not (isinstance(response, dict) and response.get("error"))
        if is_success:
            logger.info("Gravitee connection test successful.")
        else:
            logger.error(f"Gravitee connection test failed. Response: {response}")
        return is_success

    def get_apis(self) -> List[Dict]:
        """Gets APIs from the Gravitee gateway (environment specific)."""
        logger.debug("Fetching APIs from Gravitee environment")
        # Endpoint for APIs within an environment
        response = self._make_request('GET', '/apis', params={'size': 500, 'page': 1}) # Adjust params as needed

        if isinstance(response, list):
            apis = [{'id': api.get('id'), 'name': api.get('name')} for api in response if api.get('id') and api.get('name')]
            logger.info(f"Successfully fetched {len(apis)} APIs from Gravitee.")
            return apis
        elif isinstance(response, dict) and response.get('error'): # Check for paginated response
            if 'data' in response and isinstance(response['data'], list): # Gravitee v4 paginated response
                apis = [{'id': api.get('id'), 'name': api.get('name')} for api in response['data'] if api.get('id') and api.get('name')]
                logger.info(f"Successfully fetched {len(apis)} APIs from Gravitee (paginated).")
                return apis
            logger.error(f"Failed to get Gravitee APIs: {response.get('message')}")
            return []
        else: # Gravitee v4 paginated response is a dict
            if isinstance(response, dict) and 'data' in response and isinstance(response['data'], list):
                apis = [{'id': api.get('id'), 'name': api.get('name')} for api in response['data'] if api.get('id') and api.get('name')]
                logger.info(f"Successfully fetched {len(apis)} APIs from Gravitee (paginated).")
                return apis
            logger.warning(f"Received unexpected response type ({type(response).__name__}) or structure when fetching Gravitee APIs. Response: {str(response)[:200]}")
            return []


    def get_api_details(self, api_id: str) -> Optional[Dict]:
        """Gets the full definition for a specific API from Gravitee."""
        logger.debug(f"Getting details for Gravitee API {api_id}")
        response = self._make_request('GET', f'/apis/{api_id}') # Relative to environment

        if isinstance(response, dict) and not response.get("error"):
            logger.info(f"Successfully fetched details for Gravitee API {api_id}.")
            return response
        else:
            logger.error(f"Failed to get details for Gravitee API {api_id}. Response: {response}")
            return None

    def create_api(self, api_config: Dict) -> Optional[Dict]:
        """Creates a new API in Gravitee (environment specific)."""
        logger.info(f"Attempting to create Gravitee API: {api_config.get('name', 'N/A')}")
        response = self._make_request('POST', '/apis', json=api_config) # Relative to environment
        if isinstance(response, dict) and not response.get("error"):
            logger.info(f"Successfully created Gravitee API. Response: {response}")
            return response
        else:
            logger.error(f"Failed to create Gravitee API. Response: {response}")
            return None

    def update_api(self, api_id: str, api_config: Dict) -> bool:
        """Updates an existing API in Gravitee (environment specific)."""
        logger.info(f"Attempting to update Gravitee API {api_id}")
        response = self._make_request('PUT', f'/apis/{api_id}', json=api_config) # Relative to environment
        is_success = not (isinstance(response, dict) and response.get("error"))
        if is_success:
            logger.info(f"Successfully updated Gravitee API {api_id}.")
        else:
            logger.error(f"Failed to update Gravitee API {api_id}. Response: {response}")
        return is_success

    def delete_api(self, api_id: str) -> bool:
        """Deletes an API from Gravitee (environment specific)."""
        logger.info(f"Attempting to delete Gravitee API {api_id}")
        response = self._make_request('DELETE', f'/apis/{api_id}') # Relative to environment
        is_success = not (isinstance(response, dict) and response.get("error"))
        if is_success:
            logger.info(f"Successfully deleted Gravitee API {api_id}.")
        else:
            logger.error(f"Failed to delete Gravitee API {api_id}. Response: {response}")
        return is_success

    def get_api_metrics(self, api_id: str) -> Dict:
        """Placeholder for getting API metrics from Gravitee."""
        logger.warning(f"get_api_metrics for Gravitee API {api_id} is not fully implemented.")
        details = self.get_api_details(api_id)
        return {"definition": details} if details else {"error": "Could not retrieve API details"}