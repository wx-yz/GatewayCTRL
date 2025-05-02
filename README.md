# API Gateway Control Plane

A comprehensive API Gateway management product that provides a central control plane for managing multiple API gateways across different providers.

## Features

- Centralized management of multiple API gateways
- Support for various gateway providers:
  - Cloud Providers: AWS API Gateway, Azure API Management, Google Cloud API Gateway
  - Third-party: Kong, WSO2, Tyk, Gravitee
- Pluggable architecture for easy addition of new gateway types
- Dashboard for monitoring and management
- API lifecycle management
- Metrics and analytics

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/api-gateway-control-plane.git
cd api-gateway-control-plane
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your configuration:
```env
# Example configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AZURE_SUBSCRIPTION_ID=your_azure_subscription_id
AZURE_TENANT_ID=your_azure_tenant_id
AZURE_CLIENT_ID=your_azure_client_id
AZURE_CLIENT_SECRET=your_azure_client_secret
```

## Usage

1. Start the application:
```bash
streamlit run app.py
```

2. Open your browser and navigate to `http://localhost:8501`

## Project Structure

```
api-gateway-control-plane/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Project dependencies
├── .env                  # Environment variables
└── gateways/             # Gateway implementations
    ├── __init__.py
    ├── base.py           # Base gateway class
    ├── factory.py        # Gateway factory
    ├── aws.py            # AWS API Gateway implementation
    └── ...               # Other gateway implementations
```

## Adding New Gateway Types

To add support for a new gateway type:

1. Create a new class in the `gateways` directory that inherits from `BaseGateway`
2. Implement all required methods
3. Register the new gateway type in `GatewayFactory`

Example:
```python
from gateways.base import BaseGateway, GatewayConfig
from gateways.factory import GatewayFactory

class NewGateway(BaseGateway):
    def __init__(self, config: GatewayConfig):
        super().__init__(config)
        # Implementation...

# Register the new gateway
GatewayFactory.register_gateway('new_gateway', NewGateway)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 