import boto3
from typing import Dict, List
from .base import BaseGateway, GatewayConfig

class AWSGateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        super().__init__(config)
        self.client = boto3.client(
            'apigateway',
            aws_access_key_id=config.additional_config.get('aws_access_key_id'),
            aws_secret_access_key=config.additional_config.get('aws_secret_access_key'),
            region_name=config.additional_config.get('region', 'us-east-1')
        )

    def get_apis(self) -> List[Dict]:
        try:
            response = self.client.get_rest_apis()
            return response.get('items', [])
        except Exception as e:
            print(f"Error getting APIs: {str(e)}")
            return []

    def create_api(self, api_config: Dict) -> Dict:
        try:
            response = self.client.create_rest_api(
                name=api_config['name'],
                description=api_config.get('description', ''),
                version=api_config.get('version', '1.0')
            )
            return response
        except Exception as e:
            print(f"Error creating API: {str(e)}")
            return {}

    def update_api(self, api_id: str, api_config: Dict) -> Dict:
        try:
            response = self.client.update_rest_api(
                restApiId=api_id,
                patchOperations=[
                    {
                        'op': 'replace',
                        'path': '/name',
                        'value': api_config['name']
                    }
                ]
            )
            return response
        except Exception as e:
            print(f"Error updating API: {str(e)}")
            return {}

    def delete_api(self, api_id: str) -> bool:
        try:
            self.client.delete_rest_api(restApiId=api_id)
            return True
        except Exception as e:
            print(f"Error deleting API: {str(e)}")
            return False

    def get_api_metrics(self, api_id: str) -> Dict:
        try:
            # This is a simplified example. In a real implementation,
            # you would use CloudWatch to get detailed metrics
            return {
                'api_id': api_id,
                'metrics': {
                    'requests': 0,
                    'errors': 0,
                    'latency': 0
                }
            }
        except Exception as e:
            print(f"Error getting metrics: {str(e)}")
            return {}

    def test_connection(self) -> bool:
        try:
            self.client.get_rest_apis()
            return True
        except Exception:
            return False 