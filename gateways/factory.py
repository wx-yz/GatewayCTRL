from typing import Dict, Type, List
from .base import BaseGateway, GatewayConfig
from .kong import KongGateway
from .wso2 import WSO2Gateway
from .tyk import TykGateway
from .gravitee import GraviteeGateway # Import GraviteeGateway
# Import other gateway types as you create them
# from .aws import AWSAPIGateway

class GatewayFactory:
    _gateways = {
        "kong": KongGateway,
        "wso2": WSO2Gateway,
        "tyk": TykGateway,
        "gravitee": GraviteeGateway, # Add Gravitee
        # "aws": AWSAPIGateway,
    }

    @staticmethod
    def create_gateway(gateway_type: str, config: GatewayConfig) -> BaseGateway:
        gateway_class = GatewayFactory._gateways.get(gateway_type.lower())
        if not gateway_class:
            raise ValueError(f"Unsupported gateway type: {gateway_type}")
        return gateway_class(config)

    # Removed get_supported_types as it was causing issues.
    # The UI now directly uses _gateways.keys()