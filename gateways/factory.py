from typing import Dict, Type, List
from .base import BaseGateway, GatewayConfig
from .aws import AWSGateway
from .wso2 import WSO2Gateway
from .kong import KongGateway

class GatewayFactory:
    _gateways: Dict[str, Type[BaseGateway]] = {
        'aws': AWSGateway,
        'wso2': WSO2Gateway,
        'kong': KongGateway,
        # Add other gateway implementations here
    }

    @classmethod
    def register_gateway(cls, gateway_type: str, gateway_class: Type[BaseGateway]):
        """Register a new gateway type"""
        cls._gateways[gateway_type] = gateway_class

    @classmethod
    def create_gateway(cls, gateway_type: str, config: GatewayConfig) -> BaseGateway:
        """Create a gateway instance of the specified type"""
        gateway_class = cls._gateways.get(gateway_type)
        if not gateway_class:
            raise ValueError(f"Unknown gateway type: {gateway_type}")
        return gateway_class(config)

    @classmethod
    def get_available_gateways(cls) -> List[str]:
        """Get list of available gateway types"""
        return list(cls._gateways.keys()) 