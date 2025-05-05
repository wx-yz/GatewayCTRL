# 🌐 GatewayCTRL

Universal Control Plane for API Gateways. A comprehensive API Gateway management product providing a central control plane for provisioning, managing, and monitoring multiple API gateways across different vendors.

## ✨ Features

*   **Centralized Management:** Configure and view all your API gateways from a single interface.
*   **Multi-Vendor Support:** Seamlessly manage APIs across various gateway providers.
*   **Pluggable Architecture:** Easily extend support for new gateway types.
*   **Intuitive Dashboard:** Monitor gateway status and API counts at a glance.
*   **API Lifecycle Management:** Create, view, update, and delete APIs on supported gateways.
*   **Detailed API Views:** Inspect API configurations, routes, plugins, consumers, and analytics (where supported).
*   **Secure Configuration:** Store gateway credentials securely.

## 🚀 Supported Gateways

Currently supports the following API Gateway vendors:

*   <img src="static/aws.png" width="24"/> **AWS API Gateway:** Manage your REST APIs hosted on AWS.
*   <img src="static/wso2.png" width="24"/> **WSO2 API Manager:** Control APIs deployed on WSO2.
*   <img src="static/kong.png" width="24"/> **Kong Gateway:** Administer services, routes, and plugins in your Kong instances.
*   <img src="static/gravitee.png" width="24"/> **Gravitee:** Manage APIs within your Gravitee environments.
*   <img src="static/tyk.png" width="24"/> **Tyk Gateway:** Configure and manage APIs deployed via Tyk.
*   *(Support for Azure API Management and Google Cloud API Gateway can be added)*

## 🛠️ Installation & Setup

Follow these steps to get the API Gateway Control Plane running locally:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/yourusername/api-gateway-control-plane.git # Replace with your repo URL if different
    cd api-gateway-control-plane
    ```

2.  **Create and Activate Virtual Environment:**
    ```bash
    # Linux/macOS
    python3 -m venv gatewayctrl
    source gatewayctrl/bin/activate

    # Windows
    python -m venv gatewayctrl
    .\gatewayctrl\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Variables (Optional):**
    While the application primarily uses the database for storing gateway configurations, you *could* use a `.env` file for default credentials or settings if extending the application. For the current setup, this step is generally not required as credentials are added via the UI.

## ▶️ Running the Application

1.  **Start the Streamlit App:**
    ```bash
    streamlit run app.py
    ```

2.  **Access the UI:**
    Open your web browser and navigate to the local URL provided by Streamlit (usually `http://localhost:8501`).

## ⚙️ Getting Started: Adding Your First Gateway

1.  **Navigate:** In the sidebar, click on `🔧 Gateway Management`.
2.  **Select Type:** Under "Add/Edit Gateway", choose the type of gateway you want to add (e.g., "Kong", "Gravitee", "Tyk").
3.  **Enter Details:**
    *   **Gateway Name:** A unique name for this connection (e.g., "Kong-Dev", "Gravitee-Prod").
    *   **Gateway URL:** The base URL for the gateway's Management API (e.g., `http://localhost:8001` for Kong, `https://gravitee-management.example.com` for Gravitee).
    *   **SSL Configuration:**
        *   Check/uncheck "Verify SSL Certificate". Unchecking is **not recommended** for production.
        *   Upload a specific server certificate (`.pem`, `.crt`) if needed for verification.
    *   **Gateway Specific Configuration:** Fill in the required authentication details based on the selected gateway type:
        *   **WSO2:** Username and Password.
        *   **Kong:** API Key (if applicable).
        *   **Gravitee:** Organization ID, Environment ID, Authentication Type (Basic Auth or Bearer Token) and corresponding credentials.
        *   **Tyk:** Tyk Authorization Secret (`x-tyk-authorization` header value).
        *   **AWS:** Access Key ID, Secret Access Key, and Region.
4.  **Add Gateway:** Click the "Add/Update Gateway" button.
5.  **Test Connection:** The application will attempt to connect to the gateway. You'll see a success or error message. The gateway will now appear under "Existing Gateways".

## 🧭 Navigating the UI

*   **📊 Dashboard:** Provides a quick overview of configured gateways and the total number of APIs detected across them.
*   **🔧 Gateway Management:** Add, view, configure, and delete gateway connections.
*   **🌐 API Management:** Select a configured gateway to view, manage, and interact with its APIs. Functionality varies based on the gateway type but often includes viewing details, routes, plugins, consumers, and analytics.
*   **⚙️ Settings:** (If implemented) Contains application-level settings.

## 🏗️ Project Structure

```
api-gateway-control-plane/
├── app.py                 # Main Streamlit application UI and logic
├── database.py            # Handles SQLite database interactions
├── gatewayctrl.db         # SQLite database file (created on first run)
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── certificates/          # Stores uploaded SSL certificates (created automatically)
├── gateways/              # Gateway-specific implementations
│   ├── base.py            # Abstract base class for all gateways
│   ├── factory.py         # Factory for creating gateway instances
│   ├── aws.py             # AWS API Gateway implementation
│   ├── gravitee.py        # Gravitee implementation
│   ├── kong.py            # Kong Gateway implementation
│   ├── tyk.py             # Tyk Gateway implementation
│   └── wso2.py            # WSO2 API Manager implementation
├── static/                # CSS and JavaScript files (if used)
│   ├── styles.css
│   └── scripts.js
└── gatewayctrl/           # Virtual environment directory (if named gatewayctrl)
```

## 🧩 Adding New Gateway Types

To extend support for a new API gateway vendor:

1.  **Create Implementation:** Add a new Python file in the `gateways/` directory (e.g., `gateways/new_gateway.py`). Create a class that inherits from [`gateways.base.BaseGateway`](gateways/base.py).
2.  **Implement Methods:** Implement all the abstract methods defined in [`BaseGateway`](gateways/base.py) (`get_apis`, `create_api`, `update_api`, `delete_api`, `get_api_metrics`, `test_connection`). Use an HTTP client (like `requests`) to interact with the target gateway's Management API.
3.  **Register in Factory:** Import your new class in [`gateways/factory.py`](gateways/factory.py) and add it to the `_gateways` dictionary in the [`GatewayFactory`](gateways/factory.py) class.
    ```python
    # filepath: gateways/factory.py
    # ... other imports ...
    from .new_gateway import NewGateway # Import your new class

    class GatewayFactory:
        _gateways: Dict[str, Type[BaseGateway]] = {
            # ... existing gateways ...
            'new_gateway_key': NewGateway, # Add your gateway
        }
        # ... rest of the class ...
    ```
4.  **Update UI (`app.py`):**
    *   Add an `elif gateway_type == 'new_gateway_key':` block in the "Gateway Management" section ([`app.py`](app.py)) to handle the specific configuration fields required for your new gateway.
    *   Add a corresponding `elif` block in the "API Management" section ([`app.py`](app.py)) to display and manage APIs for the new gateway type, tailoring the UI to the features and data provided by its API.

## 🙌 Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
