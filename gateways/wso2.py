import requests
from typing import Dict, List, Optional
from .base import BaseGateway, GatewayConfig
import os
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
        logger.debug(f"Making {method} request to {url}")
        try:
            response = requests.request(
                method,
                url,
                auth=self.auth,
                headers=self.headers,
                verify=self.verify,
                **kwargs
            )
            logger.debug(f"Response status code: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error: {str(e)}")
            if not self.config.verify_ssl and not self.config.cert_path:
                logger.warning("Retrying with SSL verification disabled...")
                response = requests.request(
                    method,
                    url,
                    auth=self.auth,
                    headers=self.headers,
                    verify=False,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error: {str(e)}")
            return {}

    def get_apis(self) -> List[Dict]:
        """Get all APIs from the WSO2 gateway"""
        logger.debug("Fetching all APIs")
        try:
            # Get all APIs with pagination
            apis = []
            offset = 0
            limit = 25
            
            while True:
                logger.debug(f"Fetching APIs with offset {offset}, limit {limit}")
                response = self._make_request(
                    'GET',
                    f'/api/am/publisher/v4/apis?offset={offset}&limit={limit}'
                )
                
                if not response or 'list' not in response:
                    logger.warning("No APIs found in response")
                    break
                    
                apis.extend(response['list'])
                logger.debug(f"Fetched {len(response['list'])} APIs in this batch")
                
                if len(response['list']) < limit:
                    break
                    
                offset += limit
                
            logger.info(f"Total APIs fetched: {len(apis)}")
            return apis
        except Exception as e:
            logger.error(f"Error getting APIs: {str(e)}", exc_info=True)
            return []

    def create_api(self, api_config: Dict) -> Dict:
        """Create a new API in the WSO2 gateway"""
        logger.debug(f"Creating API with config: {api_config}")
        try:
            # Required fields for API creation
            payload = {
                'name': api_config['name'],
                'context': api_config.get('context', f'/{api_config["name"]}'),
                'version': api_config.get('version', '1.0.0'),
                'provider': api_config.get('provider', 'admin'),
                'type': api_config.get('type', 'HTTP'),
                'description': api_config.get('description', ''),
                'endpointConfig': api_config.get('endpointConfig', {
                    'endpoint_type': 'http',
                    'production_endpoints': {
                        'url': api_config.get('endpoint_url', '')
                    }
                }),
                'policies': api_config.get('policies', ['Unlimited']),
                'visibility': api_config.get('visibility', 'PUBLIC'),
                'subscriptionAvailability': api_config.get('subscriptionAvailability', 'ALL_TENANTS'),
                'accessControl': api_config.get('accessControl', 'NONE'),
                'businessInformation': api_config.get('businessInformation', {
                    'businessOwner': api_config.get('businessOwner', ''),
                    'businessOwnerEmail': api_config.get('businessOwnerEmail', ''),
                    'technicalOwner': api_config.get('technicalOwner', ''),
                    'technicalOwnerEmail': api_config.get('technicalOwnerEmail', '')
                })
            }
            
            logger.debug(f"Creating API with payload: {payload}")
            response = self._make_request('POST', '/api/am/publisher/v4/apis', json=payload)
            logger.info(f"API created successfully: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Error creating API: {str(e)}", exc_info=True)
            return {}

    def update_api(self, api_id: str, api_config: Dict) -> Dict:
        """Update an existing API in the WSO2 gateway"""
        logger.debug(f"Updating API {api_id} with config: {api_config}")
        try:
            response = self._make_request(
                'PUT',
                f'/api/am/publisher/v4/apis/{api_id}',
                json=api_config
            )
            logger.info(f"API {api_id} updated successfully")
            return response
        except Exception as e:
            logger.error(f"Error updating API: {str(e)}", exc_info=True)
            return {}

    def delete_api(self, api_id: str) -> bool:
        """Delete an API from the WSO2 gateway"""
        logger.debug(f"Deleting API {api_id}")
        try:
            response = self._make_request('DELETE', f'/api/am/publisher/v4/apis/{api_id}')
            logger.info(f"API {api_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting API: {str(e)}", exc_info=True)
            return False

    def get_api_metrics(self, api_id: str) -> Dict:
        """Get metrics for a specific API"""
        logger.debug(f"Getting metrics for API {api_id}")
        try:
            # Get API details which include some basic metrics
            api_details = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}')
            logger.debug(f"API details: {api_details}")
            
            # Get API usage statistics
            usage_stats = self._make_request(
                'GET',
                f'/api/am/publisher/v4/apis/{api_id}/usage'
            )
            logger.debug(f"Usage stats: {usage_stats}")
            
            # Get API subscription statistics
            subscription_stats = self._make_request(
                'GET',
                f'/api/am/publisher/v4/apis/{api_id}/subscriptions'
            )
            logger.debug(f"Subscription stats: {subscription_stats}")
            
            return {
                'api_id': api_id,
                'details': api_details,
                'usage': usage_stats,
                'subscriptions': subscription_stats
            }
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}", exc_info=True)
            return {}

    def test_connection(self) -> bool:
        """Test the connection to the WSO2 gateway"""
        logger.debug("Testing connection to WSO2 gateway")
        try:
            response = self._make_request('GET', '/api/am/publisher/v4/apis')
            logger.info("Successfully connected to WSO2 gateway")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WSO2 gateway: {str(e)}", exc_info=True)
            return False

    # Additional WSO2-specific methods
    def get_api_versions(self, api_id: str) -> List[Dict]:
        """Get all versions of an API"""
        logger.debug(f"Getting versions for API {api_id}")
        try:
            response = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}/versions')
            versions = response.get('list', [])
            logger.debug(f"Found {len(versions)} versions")
            return versions
        except Exception as e:
            logger.error(f"Error getting API versions: {str(e)}", exc_info=True)
            return []

    def create_api_version(self, api_id: str, version_config: Dict) -> Dict:
        """Create a new version of an API"""
        logger.debug(f"Creating new version for API {api_id}: {version_config}")
        try:
            response = self._make_request(
                'POST',
                f'/api/am/publisher/v4/apis/{api_id}/versions',
                json=version_config
            )
            logger.info(f"Version created successfully: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Error creating API version: {str(e)}", exc_info=True)
            return {}

    def get_api_documentation(self, api_id: str) -> List[Dict]:
        """Get all documentation for an API"""
        logger.debug(f"Getting documentation for API {api_id}")
        try:
            response = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}/documents')
            docs = response.get('list', [])
            logger.debug(f"Found {len(docs)} documents")
            return docs
        except Exception as e:
            logger.error(f"Error getting API documentation: {str(e)}", exc_info=True)
            return []

    def add_api_documentation(self, api_id: str, doc_config: Dict) -> Dict:
        """Add documentation to an API"""
        logger.debug(f"Adding documentation to API {api_id}: {doc_config}")
        try:
            response = self._make_request(
                'POST',
                f'/api/am/publisher/v4/apis/{api_id}/documents',
                json=doc_config
            )
            logger.info(f"Documentation added successfully: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Error adding API documentation: {str(e)}", exc_info=True)
            return {}

    def get_api_operations(self, api_id: str) -> List[Dict]:
        """Get all operations (endpoints) for an API"""
        logger.debug(f"Getting operations for API {api_id}")
        try:
            response = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}/operations')
            # WSO2 API returns operations in a list field
            operations = response.get('list', [])
            # Transform the operations to match the expected format
            transformed_operations = []
            for op in operations:
                transformed_operations.append({
                    'method': op.get('method', ''),
                    'path': op.get('urlTemplate', ''),
                    'description': op.get('description', ''),
                    'name': op.get('displayName', '')
                })
            logger.debug(f"Found {len(transformed_operations)} operations")
            return transformed_operations
        except Exception as e:
            logger.error(f"Error getting API operations: {str(e)}", exc_info=True)
            return []

    def add_api_operation(self, api_id: str, operation_config: Dict) -> Dict:
        """Add a new operation to an API"""
        logger.debug(f"Adding operation to API {api_id}: {operation_config}")
        try:
            response = self._make_request(
                'POST',
                f'/api/am/publisher/v4/apis/{api_id}/operations',
                json=operation_config
            )
            logger.info(f"Operation added successfully: {response.get('id', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"Error adding API operation: {str(e)}", exc_info=True)
            return {}

    def get_api_subscriptions(self, api_id: str) -> List[Dict]:
        """Get all subscriptions for an API"""
        logger.debug(f"Getting subscriptions for API {api_id}")
        try:
            response = self._make_request('GET', f'/api/am/publisher/v4/apis/{api_id}/subscriptions')
            subscriptions = response.get('list', [])
            logger.debug(f"Found {len(subscriptions)} subscriptions")
            return subscriptions
        except Exception as e:
            logger.error(f"Error getting API subscriptions: {str(e)}", exc_info=True)
            return []

    def get_api_analytics(self, api_id: str, time_range: str = "1h") -> Dict:
        """Get analytics data for an API"""
        logger.debug(f"Getting analytics for API {api_id} (time range: {time_range})")
        try:
            response = self._make_request(
                'GET',
                f'/api/am/publisher/v4/apis/{api_id}/analytics',
                params={'timeRange': time_range}
            )
            logger.debug(f"Analytics data: {response}")
            return response
        except Exception as e:
            logger.error(f"Error getting API analytics: {str(e)}", exc_info=True)
            return {} 