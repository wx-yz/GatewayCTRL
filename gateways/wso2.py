import requests
from typing import Dict, List, Optional
from .base import BaseGateway, GatewayConfig
import logging

logger = logging.getLogger(__name__)

class WSO2Gateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        super().__init__(config)
        self.base_url = config.url.rstrip('/')
        self.auth = (config.additional_config.get('username', ''),
                    config.additional_config.get('password', ''))
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.verify = config.cert_path if config.cert_path else config.verify_ssl
        logger.debug(f"Initialized WSO2 gateway with URL: {self.base_url}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make an authenticated request to the WSO2 API"""
        url = f"{self.base_url}{endpoint}"
        verify_setting = self.verify if isinstance(self.verify, str) else self.config.verify_ssl
        logger.debug(f"Making {method} request to {url} with verify={verify_setting}")

        try:
            response = requests.request(
                method,
                url,
                auth=self.auth,
                headers=self.headers,
                verify=verify_setting,
                **kwargs
            )
            logger.debug(f"Response status code: {response.status_code}")
            response.raise_for_status()

            if not response.content:
                return {}
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                logger.warning(f"Response from {method} {url} is not valid JSON. Status: {response.status_code}")
                return {}

        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error connecting to {url}: {str(e)}")
            if verify_setting is True and not self.config.verify_ssl:
                logger.warning("Retrying with SSL verification disabled as per configuration...")
                try:
                    response = requests.request(
                        method, url, auth=self.auth, headers=self.headers, verify=False, **kwargs
                    )
                    response.raise_for_status()
                    if not response.content:
                        return {}
                    try:
                        return response.json()
                    except requests.exceptions.JSONDecodeError:
                        return {}
                except requests.exceptions.RequestException as retry_e:
                    logger.error(f"Retry Request Error after SSL failure: {str(retry_e)}")
                    return {"error": True, "message": f"Retry failed: {str(retry_e)}"}
            return {"error": True, "message": f"SSL Error: {str(e)}"}

        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error ({method} {url}): {str(e)}")
            error_details = "No response body or non-JSON error response"
            status_code = "N/A"
            if e.response is not None:
                status_code = e.response.status_code
                try:
                    error_details = e.response.json()
                except requests.exceptions.JSONDecodeError:
                    error_details = e.response.text
            return {"error": True, "message": str(e), "status": status_code, "details": error_details}
        except Exception as e:
            logger.error(f"Unexpected error during request to {url}: {str(e)}", exc_info=True)
            return {"error": True, "message": f"Unexpected error: {str(e)}"}

    def get_apis(self) -> List[Dict]:
        """Get all APIs from the WSO2 gateway"""
        logger.debug("Fetching all APIs")
        apis = []
        offset = 0
        limit = 25

        while True:
            logger.debug(f"Fetching APIs with offset {offset}, limit {limit}")
            try:
                response = self._make_request(
                    'GET',
                    f'/api/am/publisher/v4/apis?offset={offset}&limit={limit}'
                )

                if isinstance(response, dict) and response.get('error'):
                    logger.error(f"Error fetching API batch: {response.get('message')}")
                    break

                api_list = response.get('list', [])
                count = response.get('count', 0)

                if not api_list:
                    logger.debug("No more APIs found in this batch or empty response.")
                    break

                apis.extend(api_list)
                logger.debug(f"Fetched {len(api_list)} APIs in this batch. Total fetched: {len(apis)}")

                if len(apis) >= response.get('pagination', {}).get('total', count):
                    break

                if len(api_list) < limit:
                    logger.debug("Fetched less than limit, assuming end of list.")
                    break

                offset += limit

            except Exception as e:
                logger.error(f"Exception during API pagination: {str(e)}", exc_info=True)
                break

        logger.info(f"Total APIs fetched: {len(apis)}")
        return apis

    def create_api(self, api_config: Dict) -> Dict:
        """Create a new API in the WSO2 gateway"""
        logger.debug(f"Creating API with config: {api_config}")
        payload = {
            'name': api_config.get('name'),
            'context': api_config.get('context'),
            'version': api_config.get('version', '1.0.0'),
        }
        if not payload['name'] or not payload['context']:
            logger.error("API Name and Context are required for creation.")
            return {"error": True, "message": "API Name and Context are required."}

        logger.debug(f"Creating API with payload: {payload}")
        response = self._make_request('POST', '/api/am/publisher/v4/apis', json=payload)
        if isinstance(response, dict) and not response.get('error'):
            logger.info(f"API created successfully: {response.get('id', 'unknown')}")
        else:
            logger.error(f"Failed to create API: {response.get('message', 'Unknown error')}")
        return response

    def update_api(self, api_id: str, api_config: Dict) -> Dict:
        """Update an existing API in the WSO2 gateway"""
        logger.debug(f"Updating API {api_id} with config: {api_config}")
        response = self._make_request(
            'PUT',
            f'/api/am/publisher/v4/apis/{api_id}',
            json=api_config
        )
        if isinstance(response, dict) and not response.get('error'):
            logger.info(f"API {api_id} updated successfully")
        else:
            logger.error(f"Failed to update API {api_id}: {response.get('message', 'Unknown error')}")
        return response

    def delete_api(self, api_id: str) -> bool:
        """Delete an API from the WSO2 gateway"""
        logger.debug(f"Deleting API {api_id}")
        response = self._make_request('DELETE', f'/api/am/publisher/v4/apis/{api_id}')
        is_success = isinstance(response, dict) and not response.get('error', False)
        if is_success:
            logger.info(f"API {api_id} deleted successfully")
        else:
            logger.error(f"Error deleting API {api_id}: {response.get('message', 'Unknown error')}")
        return is_success

    def get_api_metrics(self, api_id: str) -> Dict:
        """Get details and potentially related metrics for a specific API"""
        logger.debug(f"Getting details for API {api_id}")
        api_details = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}')

        if isinstance(api_details, dict) and api_details.get('error'):
            logger.error(f"Failed to get details for API {api_id}: {api_details.get('message')}")
            return {"error": True, "message": f"Failed to get API details: {api_details.get('message')}"}

        return {'details': api_details}

    def test_connection(self) -> bool:
        """Test the connection to the WSO2 gateway"""
        logger.debug("Testing connection to WSO2 gateway")
        try:
            response = self._make_request('GET', '/api/am/publisher/v4/apis?limit=1')
            is_success = isinstance(response, dict) and not response.get("error", False)
            if is_success:
                logger.info("Successfully connected to WSO2 gateway")
            else:
                logger.error(f"Connection test failed: Received error response: {response}")
            return is_success
        except Exception as e:
            logger.error(f"Connection test failed during request execution: {str(e)}", exc_info=True)
            return False

    def get_api_versions(self, api_id: str) -> List[Dict]:
        """Get all versions of an API"""
        logger.warning(f"get_api_versions might need specific implementation for WSO2 v4 based on API structure.")
        details = self.get_api_metrics(api_id).get('details', {})
        api_name = details.get('name')
        if not api_name:
            return []
        all_apis = self.get_apis()
        versions = [api for api in all_apis if api.get('name') == api_name]
        logger.debug(f"Found {len(versions)} potential versions for API name '{api_name}'")
        return versions

    def create_api_version(self, api_id: str, version_config: Dict) -> Dict:
        """Create a new version of an API"""
        logger.debug(f"Creating new version for API {api_id} using copy-api: {version_config}")
        new_version = version_config.get('newVersion')
        if not new_version:
            return {"error": True, "message": "Missing 'newVersion' in version_config"}

        payload = {'newVersion': new_version}
        response = self._make_request(
            'POST',
            f'/api/am/publisher/v4/apis/copy-api?apiId={api_id}',
            json=payload
        )
        if isinstance(response, dict) and not response.get('error'):
            logger.info(f"New version based on {api_id} created successfully: {response.get('id', 'unknown')}")
        else:
            logger.error(f"Error creating API version: {response.get('message', 'Unknown error')}")
        return response

    def get_api_documentation(self, api_id: str) -> List[Dict]:
        """Get all documentation for an API"""
        logger.debug(f"Getting documentation for API {api_id}")
        response = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}/documents')
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"Error getting API documentation: {response.get('message')}")
            return []
        docs = response.get('list', [])
        logger.debug(f"Found {len(docs)} documents")
        return docs

    def add_api_documentation(self, api_id: str, doc_config: Dict) -> Dict:
        """Add documentation to an API"""
        logger.debug(f"Adding documentation to API {api_id}: {doc_config}")
        response = self._make_request(
            'POST',
            f'/api/am/publisher/v4/apis/{api_id}/documents',
            json=doc_config
        )
        if isinstance(response, dict) and not response.get('error'):
            logger.info(f"Documentation added successfully: {response.get('documentId', 'unknown')}")
        else:
            logger.error(f"Error adding API documentation: {response.get('message', 'Unknown error')}")
        return response

    def get_api_operations(self, api_id: str) -> List[Dict]:
        """Get all operations (resources) for an API"""
        logger.debug(f"Getting operations for API {api_id}")
        response = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}/api-operations')
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"Error getting API operations: {response.get('message')}")
            return []

        operations = response.get('list', [])
        logger.debug(f"Found {len(operations)} operations")
        return operations

    def add_api_operation(self, api_id: str, operation_config: Dict) -> Dict:
        """Add a new operation (resource) to an API"""
        logger.debug(f"Adding operation to API {api_id}: {operation_config}")
        response = self._make_request(
            'POST',
            f'/api/am/publisher/v4/apis/{api_id}/api-operations',
            json=operation_config
        )
        if isinstance(response, dict) and not response.get('error'):
            logger.info(f"Operation added successfully: {response.get('id', 'unknown')}")
        else:
            logger.error(f"Error adding API operation: {response.get('message', 'Unknown error')}")
        return response

    def get_api_subscriptions(self, api_id: str) -> List[Dict]:
        """Get all subscriptions for an API"""
        logger.debug(f"Getting subscriptions for API {api_id}")
        response = self._make_request('GET', f'/api/am/publisher/v4/subscriptions?apiId={api_id}')
        if isinstance(response, dict) and response.get('error'):
            logger.error(f"Error getting API subscriptions: {response.get('message')}")
            return []
        subscriptions = response.get('list', [])
        logger.debug(f"Found {len(subscriptions)} subscriptions")
        return subscriptions

    def get_api_analytics(self, api_id: str, time_range: str = "1h") -> Dict:
        """Get analytics data for an API"""
        logger.warning("WSO2 Analytics endpoint needs verification based on deployment.")
        logger.debug(f"Getting analytics for API {api_id} (time range: {time_range})")
        return {"error": True, "message": "Analytics endpoint not implemented/verified for WSO2 v4."}

    def get_api_swagger_definition(self, api_id: str) -> Optional[Dict]:
        """Get the Swagger/OpenAPI definition for a specific API using the correct endpoint."""
        logger.debug(f"Fetching Swagger definition for API {api_id}")
        endpoint = f'/api/am/publisher/v4/apis/{api_id}/swagger-definition'
        response = self._make_request('GET', endpoint)

        if isinstance(response, dict) and not response.get('error', False):
            if 'openapi' in response or 'swagger' in response:
                logger.debug(f"Successfully retrieved Swagger definition for API {api_id}")
                return response
            else:
                logger.warning(f"Response from {endpoint} is a dictionary but not a recognized OpenAPI/Swagger spec.")
                return None
        elif isinstance(response, dict) and response.get('error'):
            logger.error(f"Error getting Swagger definition for API {api_id}: {response.get('message')}")
            return None
        else:
            logger.warning(f"Unexpected response type ({type(response)}) when getting Swagger definition for API {api_id}")
            return None