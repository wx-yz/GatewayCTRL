from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel

class GatewayConfig(BaseModel):
    name: str
    url: str
    api_key: Optional[str] = None
    additional_config: Optional[Dict] = None
    verify_ssl: bool = True
    cert_path: Optional[str] = None

class BaseGateway(ABC):
    def __init__(self, config: GatewayConfig):
        self.config = config

    @abstractmethod
    def get_apis(self) -> List[Dict]:
        """Get all APIs from the gateway"""
        pass

    @abstractmethod
    def create_api(self, api_config: Dict) -> Dict:
        """Create a new API in the gateway"""
        pass

    @abstractmethod
    def update_api(self, api_id: str, api_config: Dict) -> Dict:
        """Update an existing API in the gateway"""
        pass

    @abstractmethod
    def delete_api(self, api_id: str) -> bool:
        """Delete an API from the gateway"""
        pass

    @abstractmethod
    def get_api_metrics(self, api_id: str) -> Dict:
        """Get metrics for a specific API"""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test the connection to the gateway"""
        pass 