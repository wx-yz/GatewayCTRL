import requests
from typing import Dict, List, Optional
from .base import BaseGateway, GatewayConfig
import logging

logger = logging.getLogger(__name__)

class KongGateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        super().__init__(config)
        self.base_url = config.url.rstrip('/')
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if 'api_key' in config.additional_config:
            self.headers['apikey'] = config.additional_config['api_key']
        self.verify = config.cert_path if config.cert_path else config.verify_ssl
        logger.debug(f"Initialized Kong gateway with URL: {self.base_url}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make an authenticated request to the Kong API"""
        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making {method} request to {url}")
        try:
            response = requests.request(
                method,
                url,
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
        """Get all APIs from the Kong gateway"""
        logger.debug("Fetching all APIs")
        try:
            response = self._make_request('GET', '/services')
            apis = response.get('data', [])
            logger.info(f"Found {len(apis)} APIs")
            return apis
        except Exception as e:
            logger.error(f"Error getting APIs: {str(e)}", exc_info=True)
            return []

    def create_api(self, api_config: Dict) -> Dict:
        """Create a new API in the Kong gateway"""
        logger.debug(f"Creating API with config: {api_config}")
        try:
            # Kong requires a service and a route
            service_config = {
                'name': api_config['name'],
                'url': api_config.get('endpoint_url', ''),
                'retries': api_config.get('retries', 5),
                'connect_timeout': api_config.get('connect_timeout', 60000),
                'write_timeout': api_config.get('write_timeout', 60000),
                'read_timeout': api_config.get('read_timeout', 60000)
            }
            
            # Create service
            service = self._make_request('POST', '/services', json=service_config)
            
            # Create route
            route_config = {
                'service': {'id': service['id']},
                'paths': api_config.get('paths', ['/']),
                'methods': api_config.get('methods', ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']),
                'protocols': api_config.get('protocols', ['http', 'https']),
                'strip_path': api_config.get('strip_path', True),
                'preserve_host': api_config.get('preserve_host', False)
            }
            
            route = self._make_request('POST', '/routes', json=route_config)
            
            logger.info(f"API created successfully: {service['id']}")
            return {
                'id': service['id'],
                'name': service['name'],
                'url': service['url'],
                'route': route
            }
        except Exception as e:
            logger.error(f"Error creating API: {str(e)}", exc_info=True)
            return {}

    def update_api(self, api_id: str, api_config: Dict) -> Dict:
        """Update an existing API in the Kong gateway"""
        logger.debug(f"Updating API {api_id} with config: {api_config}")
        try:
            # Update service
            service_config = {
                'url': api_config.get('endpoint_url', ''),
                'retries': api_config.get('retries', 5),
                'connect_timeout': api_config.get('connect_timeout', 60000),
                'write_timeout': api_config.get('write_timeout', 60000),
                'read_timeout': api_config.get('read_timeout', 60000)
            }
            
            service = self._make_request('PATCH', f'/services/{api_id}', json=service_config)
            
            # Update route if provided
            if 'route_id' in api_config:
                route_config = {
                    'paths': api_config.get('paths', ['/']),
                    'methods': api_config.get('methods', ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']),
                    'protocols': api_config.get('protocols', ['http', 'https']),
                    'strip_path': api_config.get('strip_path', True),
                    'preserve_host': api_config.get('preserve_host', False)
                }
                
                self._make_request('PATCH', f'/routes/{api_config["route_id"]}', json=route_config)
            
            logger.info(f"API {api_id} updated successfully")
            return service
        except Exception as e:
            logger.error(f"Error updating API: {str(e)}", exc_info=True)
            return {}

    def delete_api(self, api_id: str) -> bool:
        """Delete an API from the Kong gateway"""
        logger.debug(f"Deleting API {api_id}")
        try:
            # Get routes for the service
            routes = self._make_request('GET', f'/services/{api_id}/routes')
            for route in routes.get('data', []):
                self._make_request('DELETE', f'/routes/{route["id"]}')
            
            # Delete service
            self._make_request('DELETE', f'/services/{api_id}')
            logger.info(f"API {api_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting API: {str(e)}", exc_info=True)
            return False

    def get_api_metrics(self, api_id: str) -> Dict:
        """Get metrics for a specific API"""
        logger.debug(f"Getting metrics for API {api_id}")
        try:
            # Get service details
            service = self._make_request('GET', f'/services/{api_id}')
            
            # Get routes
            routes = self._make_request('GET', f'/services/{api_id}/routes')
            
            # Get plugins
            plugins = self._make_request('GET', f'/services/{api_id}/plugins')
            
            return {
                'api_id': api_id,
                'service': service,
                'routes': routes.get('data', []),
                'plugins': plugins.get('data', [])
            }
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}", exc_info=True)
            return {}

    def test_connection(self) -> bool:
        """Test the connection to the Kong gateway"""
        logger.debug("Testing connection to Kong gateway")
        try:
            response = self._make_request('GET', '/services')
            logger.info("Successfully connected to Kong gateway")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kong gateway: {str(e)}", exc_info=True)
            return False 