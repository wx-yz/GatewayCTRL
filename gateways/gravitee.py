# filepath: gateways/gravitee.py
import requests
import logging
import base64
from typing import Dict, List, Optional
from .base import BaseGateway, GatewayConfig

logger = logging.getLogger(__name__)

class GraviteeGateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        super().__init__(config)
        # Use v2 management API path based on curl examples
        self.base_url = f"{config.url.rstrip('/')}/management/v2"
        self.headers = getattr(self, 'headers', {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        self.auth_headers = self._get_auth_headers(config.additional_config)
        self.org_id = config.additional_config.get('organization_id', 'DEFAULT')
        self.env_id = config.additional_config.get('environment_id', 'DEFAULT')
        self.verify = config.cert_path if config.cert_path else config.verify_ssl
        logger.debug(f"Initialized Gravitee gateway (v2 API) with URL: {self.base_url}, Org: {self.org_id}, Env: {self.env_id}")

    def _get_auth_headers(self, additional_config: Dict) -> Dict:
        """Helper to create authentication headers."""
        auth_type = additional_config.get('auth_type')
        if auth_type == 'basic':
            username = additional_config.get('username')
            password = additional_config.get('password')
            if username and password:
                creds = f"{username}:{password}"
                encoded_creds = base64.b64encode(creds.encode()).decode()
                logger.debug("Using Basic Authentication for Gravitee.")
                return {'Authorization': f'Basic {encoded_creds}'}
        elif auth_type == 'bearer':
            token = additional_config.get('token')
            if token:
                logger.debug("Using Bearer Token Authentication for Gravitee.")
                return {'Authorization': f'Bearer {token}'}
        logger.warning("No valid authentication configured for Gravitee.")
        return {}

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict | List: # Allow returning List for list endpoints
        """Make an authenticated request to the Gravitee Management API v2"""
        # Construct the full URL using the v2 base path
        url = f"{self.base_url}/organizations/{self.org_id}/environments/{self.env_id}{endpoint}"
        request_headers = {**self.headers, **self.auth_headers}
        request_headers.update(kwargs.pop('headers', {}))

        logger.debug(f"Making {method} request to {url}")
        try:
            response = requests.request(
                method,
                url,
                headers=request_headers,
                verify=self.verify,
                **kwargs
            )
            response.raise_for_status()
            # Handle empty response body (e.g., for DELETE or some POST/PUT)
            if not response.content:
                return {}
            # Try parsing JSON, return raw text if not JSON
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                 logger.warning(f"Response from {method} {url} is not valid JSON. Status: {response.status_code}")
                 return {'warning': 'Non-JSON response', 'content': response.text}

        except requests.exceptions.RequestException as e:
            error_details = ""
            status_code = 'N/A'
            if e.response is not None:
                status_code = e.response.status_code
                try:
                    error_details = e.response.json()
                except ValueError:
                    error_details = e.response.text
            logger.error(f"Request Error: {method} {url} failed with status {status_code}. Details: {error_details}. Exception: {str(e)}", exc_info=True)
            return {'error': True, 'status': status_code, 'message': str(e), 'details': error_details}
        except Exception as e:
             logger.error(f"Error processing request to {url}: {str(e)}", exc_info=True)
             return {'error': True, 'message': str(e)}

    def get_apis(self) -> List[Dict]:
        """Get all APIs from the Gravitee gateway using the v2 API"""
        logger.debug("Fetching all APIs from Gravitee (v2)")
        # Use GET /apis endpoint for listing
        result = self._make_request('GET', '/apis')

        # Check for errors returned by _make_request
        if isinstance(result, dict) and result.get('error'):
            logger.error(f"Failed to get APIs: {result.get('message')}")
            return []

        # Gravitee v2 list APIs might return a list directly or a dict with pagination/data
        # Adjust based on the actual response structure. Assuming it returns a list directly for now.
        if isinstance(result, list):
            logger.info(f"Successfully fetched {len(result)} APIs from Gravitee.")
            return result
        elif isinstance(result, dict) and 'data' in result and isinstance(result['data'], list):
             # Handle potential pagination structure like {'data': [...], 'pagination': {...}}
             logger.info(f"Successfully fetched {len(result['data'])} APIs from Gravitee (paginated response).")
             # TODO: Implement pagination handling if needed
             return result['data']
        else:
            logger.warning(f"Received unexpected format when fetching APIs: {type(result)}")
            return []

    def create_api(self, api_config: Dict) -> Dict:
        """Create a new API in the Gravitee gateway"""
        logger.debug(f"Creating Gravitee API with config: {api_config}")
        # Example endpoint: POST /apis
        # Ensure api_config matches Gravitee's expected format for v2
        return self._make_request('POST', '/apis', json=api_config)

    def update_api(self, api_id: str, api_config: Dict) -> Dict:
        """Update an existing API in the Gravitee gateway"""
        logger.debug(f"Updating Gravitee API {api_id} with config: {api_config}")
        # Example endpoint: PUT /apis/{api_id}
        return self._make_request('PUT', f'/apis/{api_id}', json=api_config)

    def delete_api(self, api_id: str) -> bool:
        """Delete an API from the Gravitee gateway"""
        logger.debug(f"Deleting Gravitee API {api_id}")
        # Example endpoint: DELETE /apis/{api_id}
        result = self._make_request('DELETE', f'/apis/{api_id}')
        # Return True if the request was successful (no error dictionary returned)
        return not (isinstance(result, dict) and result.get('error', False))

    def get_api_metrics(self, api_id: str) -> Dict:
        """Get metrics for a specific API"""
        logger.debug(f"Getting metrics for Gravitee API {api_id}")
        # Implementation needed: Call Gravitee's metrics/analytics endpoints
        # This might involve multiple calls or specific analytics endpoints.
        # Example: GET /apis/{api_id}/analytics?type=hits&field=status...
        return {} # Placeholder

    def test_connection(self) -> bool:
        """Test the connection to the Gravitee gateway using v2 API"""
        logger.debug("Testing connection to Gravitee (v2)")
        try:
            # Use an endpoint that requires authentication but is lightweight.
            # GET /user might still work, or try fetching organization details.
            result = self._make_request('GET', '/user') # Or '/organizations/{self.org_id}'
            if isinstance(result, dict) and result.get('error'):
                 logger.error(f"Connection test failed: Received error response: {result}")
                 return False
            logger.info("Gravitee connection test successful.")
            return True
        except Exception as e:
            logger.error(f"Connection test failed during request execution: {str(e)}", exc_info=True)
            return False