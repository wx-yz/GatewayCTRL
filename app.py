import streamlit as st
from dotenv import load_dotenv
import os
from gateways.factory import GatewayFactory
from gateways.base import GatewayConfig
import json
import tempfile
import logging
from swagger_ui_bundle import swagger_ui_path
import pathlib
import shutil
import base64
from database import Database
import time
from functools import lru_cache
import psutil

# Set page config - MUST be the first Streamlit command
st.set_page_config(
    page_title="API Gateway Control Plane",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a placeholder for loading state
loading_placeholder = st.empty()

# Initialize loading state
def update_loading_state(message: str):
    with loading_placeholder:
        st.info(message)

# Load environment variables
update_loading_state("Initializing...")
load_dotenv()

# Initialize database
update_loading_state("Loading gateways...")
db = Database()

# Initialize session state for gateways if not exists
if 'gateways' not in st.session_state:
    st.session_state.gateways = db.get_gateways()

# Initialize session state for temporary directories
if 'temp_dirs' not in st.session_state:
    st.session_state['temp_dirs'] = []

# Initialize session state for start time
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = time.time()

# Cache expensive operations
@lru_cache(maxsize=128)
def get_gateway_instance(gateway_type: str, config: GatewayConfig):
    return GatewayFactory.create_gateway(gateway_type, config)

@lru_cache(maxsize=128)
def get_api_metrics(gateway, api_id: str):
    return gateway.get_api_metrics(api_id)

# Clear loading placeholder once initialization is complete
loading_placeholder.empty()

def save_gateway_config(gateway_type: str, gateway_name: str, config: GatewayConfig):
    """Save or update gateway configuration"""
    logger.debug(f"Saving gateway config: {gateway_name} ({gateway_type})")
    if db.save_gateway(gateway_type, gateway_name, config):
        # Update session state
        st.session_state.gateways = db.get_gateways()
        logger.debug(f"Current gateways: {[g['name'] for g in st.session_state.gateways]}")
    else:
        st.error("Failed to save gateway configuration")

def delete_gateway(gateway_name: str):
    """Delete a gateway configuration"""
    logger.debug(f"Deleting gateway: {gateway_name}")
    if db.delete_gateway(gateway_name):
        # Update session state
        st.session_state.gateways = db.get_gateways()
        logger.debug(f"Remaining gateways: {[g['name'] for g in st.session_state.gateways]}")
    else:
        st.error("Failed to delete gateway")

def inject_css():
    """Inject custom CSS"""
    with open("static/styles.css", "r") as f:
        css = f.read()
    st.markdown(f"""
        <style>
            {css}
        </style>
    """, unsafe_allow_html=True)

def inject_js():
    """Inject custom JavaScript"""
    with open("static/scripts.js", "r") as f:
        js = f.read()
    st.markdown(f"""
        <script>
            {js}
        </script>
    """, unsafe_allow_html=True)

# Inject CSS and JavaScript
inject_css()
inject_js()

# Sidebar navigation with icons
st.sidebar.title("API Gateway Control Plane")
page = st.sidebar.radio(
    "Navigation",
    [
        ("Dashboard", "📊"),
        ("Gateway Management", "🔧"),
        ("API Management", "🌐"),
        ("Settings", "⚙️")
    ],
    format_func=lambda x: f"{x[1]} {x[0]}"
)[0]

# Main content area
st.title("API Gateway Control Plane")

if page == "Dashboard":
    st.header("Dashboard")
    st.write("Welcome to the API Gateway Control Plane. Select a section from the sidebar to get started.")
    
    # Display gateway and API statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Gateways", len(st.session_state.gateways))
    
    # Calculate total APIs across all gateways
    total_apis = 0
    for gateway in st.session_state.gateways:
        try:
            gateway_instance = GatewayFactory.create_gateway(gateway['type'], gateway['config'])
            apis = gateway_instance.get_apis()
            total_apis += len(apis)
        except Exception as e:
            logger.error(f"Error getting APIs for gateway {gateway['name']}: {str(e)}", exc_info=True)
    
    with col2:
        st.metric("Total APIs", total_apis)
    with col3:
        st.metric("Total Requests", "0")
    
    # List configured gateways with API counts
    st.subheader("Configured Gateways")
    if st.session_state.gateways:
        for gateway in st.session_state.gateways:
            with st.expander(f"{gateway['name']} ({gateway['type']})"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.json(gateway['config'].dict())
                with col2:
                    try:
                        gateway_instance = GatewayFactory.create_gateway(gateway['type'], gateway['config'])
                        apis = gateway_instance.get_apis()
                        st.metric("APIs", len(apis))
                    except Exception as e:
                        logger.error(f"Error getting APIs for gateway {gateway['name']}: {str(e)}", exc_info=True)
                        st.error("Failed to get API count")
    else:
        st.info("No gateways configured yet.")

elif page == "Gateway Management":
    st.header("Gateway Management")
    
    # List and manage existing gateways
    if st.session_state.gateways:
        st.subheader("Existing Gateways")
        for gateway in st.session_state.gateways:
            with st.expander(f"{gateway['name']} ({gateway['type']})"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.json(gateway['config'].dict())
                with col2:
                    if st.button("Delete", key=f"delete_{gateway['name']}"):
                        delete_gateway(gateway['name'])
                        st.experimental_rerun()
    
    # Add/Edit gateway form
    st.subheader("Add/Edit Gateway")
    
    # Gateway type selection
    gateway_type = st.selectbox(
        "Select Gateway Type",
        GatewayFactory.get_available_gateways()
    )
    
    # Gateway configuration form
    with st.form("gateway_config"):
        st.subheader("Gateway Configuration")
        gateway_name = st.text_input("Gateway Name")
        gateway_url = st.text_input("Gateway URL")
        
        # SSL Configuration
        st.subheader("SSL Configuration")
        verify_ssl = st.checkbox("Verify SSL Certificate", value=True)
        cert_file = None
        if not verify_ssl:
            st.warning("Disabling SSL verification is not recommended for production environments.")
        else:
            cert_file = st.file_uploader("Upload Server Certificate (PEM format)", type=['pem', 'crt'])
        
        # Gateway specific configuration
        if gateway_type == 'wso2':
            username = st.text_input("Admin Username")
            password = st.text_input("Admin Password", type="password")
            additional_config = {
                'username': username,
                'password': password
            }
        elif gateway_type == 'kong':
            api_key = st.text_input("API Key", type="password")
            additional_config = {
                'api_key': api_key
            }
        elif gateway_type == 'gravitee': # Add this block
            st.subheader("Gravitee Configuration")
            org_id = st.text_input("Organization ID", value="DEFAULT")
            env_id = st.text_input("Environment ID", value="DEFAULT")
            # Add fields for authentication, e.g., Basic Auth or Token
            auth_type = st.selectbox("Authentication Type", ["Basic Auth", "Bearer Token"])
            if auth_type == "Basic Auth":
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                additional_config = {
                    'organization_id': org_id,
                    'environment_id': env_id,
                    'auth_type': 'basic',
                    'username': username,
                    'password': password
                }
            else: # Bearer Token
                token = st.text_input("Bearer Token", type="password")
                additional_config = {
                    'organization_id': org_id,
                    'environment_id': env_id,
                    'auth_type': 'bearer',
                    'token': token
                }
        elif gateway_type == 'tyk': # Add this block
            st.subheader("Tyk Configuration")
            tyk_auth_secret = st.text_input("Tyk Authorization Secret (x-tyk-authorization)", type="password")
            additional_config = {
                'tyk_auth_secret': tyk_auth_secret
            }
        else:
            # Default or other gateways (Consider removing this generic 'else' if all types are explicitly handled)
            api_key = st.text_input("API Key / Secret", type="password")
            additional_config = {
                'api_key': api_key
            }
        
        submit = st.form_submit_button("Add/Update Gateway")
        
        if submit:
            try:
                logger.debug(f"Attempting to add/update gateway: {gateway_name}")
                # Handle certificate file
                cert_path = None
                if cert_file:
                    logger.debug("Certificate file uploaded")
                    # Create certificates directory if it doesn't exist
                    os.makedirs('certificates', exist_ok=True)
                    # Save certificate to persistent file
                    cert_path = f'certificates/{gateway_name}.pem'
                    with open(cert_path, 'wb') as f:
                        f.write(cert_file.getvalue())
                    logger.debug(f"Certificate saved to {cert_path}")
                
                config = GatewayConfig(
                    name=gateway_name,
                    url=gateway_url,
                    additional_config=additional_config,
                    verify_ssl=verify_ssl,
                    cert_path=cert_path
                )
                
                logger.debug(f"Creating gateway instance for {gateway_name}")
                gateway = GatewayFactory.create_gateway(gateway_type, config)
                
                # Test connection
                logger.debug(f"Testing connection to {gateway_name}")
                if gateway.test_connection():
                    logger.info(f"Successfully connected to {gateway_name}")
                    save_gateway_config(gateway_type, gateway_name, config)
                    st.success(f"Gateway {gateway_name} added/updated successfully!")
                else:
                    logger.error(f"Failed to connect to {gateway_name}")
                    st.error("Failed to connect to the gateway. Please check your credentials.")
            except Exception as e:
                logger.error(f"Error adding/updating gateway: {str(e)}", exc_info=True)
                st.error(f"Error adding/updating gateway: {str(e)}")
                # Clean up certificate file if it was created but gateway creation failed
                if cert_path and os.path.exists(cert_path):
                    os.unlink(cert_path)

elif page == "API Management":
    st.header("API Management")
    
    # Select gateway
    if not st.session_state.gateways:
        st.warning("No gateways configured. Please add a gateway first.")
    else:
        gateway_name = st.selectbox(
            "Select Gateway",
            [g['name'] for g in st.session_state.gateways]
        )
        
        selected_gateway = next(g for g in st.session_state.gateways if g['name'] == gateway_name)
        gateway_type = selected_gateway['type']
        
        # Create gateway instance
        gateway = GatewayFactory.create_gateway(gateway_type, selected_gateway['config'])
        
        # Fetch APIs
        apis = gateway.get_apis()
        
        if not apis:
            st.warning("No APIs found. Please add APIs to your gateway first.")
        else:
            if gateway_type == 'wso2':
                # WSO2 specific API management
                st.subheader("WSO2 API Management")
                
                # Group APIs by name to handle versions
                api_groups = {}
                for api in apis:
                    api_name = api['name']
                    if api_name not in api_groups:
                        api_groups[api_name] = []
                    api_groups[api_name].append(api)
                
                # API selection
                selected_api_name = st.selectbox(
                    "Select API",
                    list(api_groups.keys())
                )
                
                if selected_api_name:
                    selected_api_group = api_groups[selected_api_name]
                    
                    # API details tabs
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "Overview", "Versions", "Documentation", 
                        "Operations", "Analytics"
                    ])
                    
                    with tab1:
                        st.subheader("API Overview")
                        # Display details of the latest version
                        latest_api = max(selected_api_group, key=lambda x: x['version'])
                        st.json(latest_api)
                        
                        # Display API metrics
                        metrics = gateway.get_api_metrics(latest_api['id'])
                        if metrics:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Subscriptions", len(metrics.get('subscriptions', [])))
                            with col2:
                                st.metric("Total Requests", metrics.get('usage', {}).get('totalRequests', 0))
                            with col3:
                                st.metric("Success Rate", f"{metrics.get('usage', {}).get('successRate', 0)}%")
                    
                    with tab2:
                        st.subheader("API Versions")
                        # Display all versions in a table
                        versions_data = []
                        for api in selected_api_group:
                            versions_data.append({
                                "Version": api['version'],
                                "Status": api.get('status', 'Unknown'),
                                "Created": api.get('createdTime', 'Unknown'),
                                "Last Updated": api.get('lastUpdatedTime', 'Unknown')
                            })
                        
                        st.table(versions_data)
                        
                        # Add new version
                        with st.expander("Add New Version"):
                            with st.form("new_version"):
                                version_name = st.text_input("Version Name")
                                version_description = st.text_area("Description")
                                if st.form_submit_button("Add Version"):
                                    version_config = {
                                        'name': selected_api_name,
                                        'version': version_name,
                                        'description': version_description,
                                        'context': latest_api['context'],
                                        'endpointConfig': latest_api.get('endpointConfig', {}),
                                        'policies': latest_api.get('policies', ['Unlimited'])
                                    }
                                    result = gateway.create_api_version(latest_api['id'], version_config)
                                    if result:
                                        st.success("Version added successfully!")
                                        st.experimental_rerun()
                                    else:
                                        st.error("Failed to add version")
                    
                    with tab3:
                        st.subheader("API Documentation")
                        # Get documentation for the latest version
                        docs = gateway.get_api_documentation(latest_api['id'])
                        if docs:
                            st.table(docs)
                        else:
                            st.info("No documentation available")
                        
                        # Add new documentation
                        with st.expander("Add Documentation"):
                            with st.form("new_doc"):
                                doc_name = st.text_input("Document Name")
                                doc_type = st.selectbox(
                                    "Document Type",
                                    ["HOWTO", "SAMPLES", "PUBLIC_FORUM", "SUPPORT_FORUM", "API_MESSAGE_FORMAT"]
                                )
                                doc_content = st.text_area("Content")
                                if st.form_submit_button("Add Documentation"):
                                    doc_config = {
                                        'name': doc_name,
                                        'type': doc_type,
                                        'content': doc_content
                                    }
                                    result = gateway.add_api_documentation(latest_api['id'], doc_config)
                                    if result:
                                        st.success("Documentation added successfully!")
                                        st.experimental_rerun()
                                    else:
                                        st.error("Failed to add documentation")
                    
                    with tab4:
                        st.subheader("API Operations")
                        # Get OpenAPI spec for the latest version
                        operations = gateway.get_api_operations(latest_api['id'])
                        if operations:
                            # Display operations in a table
                            operations_data = []
                            for op in operations:
                                operations_data.append({
                                    "Method": op.get('method', 'Unknown'),
                                    "Path": op.get('path', 'Unknown'),
                                    "Description": op.get('description', '')
                                })
                            st.table(operations_data)
                            
                            # Visualize OpenAPI spec
                            st.subheader("OpenAPI Specification")
                            
                            # Get the OpenAPI specification
                            openapi_spec = latest_api.get('openAPISpec', {})
                            if not openapi_spec:
                                # If no OpenAPI spec is available, create a basic one from operations
                                openapi_spec = {
                                    "openapi": "3.0.0",
                                    "info": {
                                        "title": latest_api['name'],
                                        "version": latest_api['version'],
                                        "description": latest_api.get('description', '')
                                    },
                                    "paths": {}
                                }
                                
                                for op in operations:
                                    path = op.get('path', '')
                                    method = op.get('method', '').lower()
                                    if path and method:
                                        if path not in openapi_spec['paths']:
                                            openapi_spec['paths'][path] = {}
                                        openapi_spec['paths'][path][method] = {
                                            "summary": op.get('name', ''),
                                            "description": op.get('description', ''),
                                            "responses": {
                                                "200": {
                                                    "description": "Successful operation"
                                                }
                                            }
                                        }
                            
                            # Create a temporary directory for Swagger UI
                            temp_dir = pathlib.Path(tempfile.mkdtemp())
                            
                            # Create the OpenAPI spec file
                            spec_file = temp_dir / 'openapi.json'
                            with open(spec_file, 'w') as f:
                                json.dump(openapi_spec, f)
                            
                            # Create the Swagger UI HTML file
                            html_file = temp_dir / 'index.html'
                            
                            # Read the OpenAPI spec file content
                            with open(spec_file, 'r') as f:
                                spec_content = f.read()
                            
                            # Create the HTML content with embedded Swagger UI
                            html_content = f'''
                            <!DOCTYPE html>
                            <html>
                            <head>
                                <title>OpenAPI Specification</title>
                                <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css">
                            </head>
                            <body>
                                <div id="swagger-ui"></div>
                                <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
                                <script>
                                    const spec = {spec_content};
                                    window.onload = function() {{
                                        const ui = SwaggerUIBundle({{
                                            spec: spec,
                                            dom_id: '#swagger-ui',
                                            deepLinking: true,
                                            presets: [
                                                SwaggerUIBundle.presets.apis,
                                                SwaggerUIBundle.SwaggerUIStandalonePreset
                                            ],
                                            layout: "BaseLayout",
                                            docExpansion: "list",
                                            defaultModelsExpandDepth: -1,
                                            defaultModelExpandDepth: 1,
                                            defaultModelRendering: "model"
                                        }})
                                        window.ui = ui
                                    }}
                                </script>
                            </body>
                            </html>
                            '''
                            
                            with open(html_file, 'w') as f:
                                f.write(html_content)
                            
                            # Display the Swagger UI in an iframe
                            st.components.v1.iframe(
                                f"file://{html_file}",
                                height=800,
                                scrolling=True
                            )
                            
                            # Clean up the temporary directory when done
                            st.session_state['temp_dirs'] = st.session_state.get('temp_dirs', [])
                            st.session_state['temp_dirs'].append(temp_dir)
                        else:
                            st.info("No operations available")
                        
                        # Add new operation
                        with st.expander("Add Operation"):
                            with st.form("new_operation"):
                                operation_name = st.text_input("Operation Name")
                                operation_method = st.selectbox(
                                    "HTTP Method",
                                    ["GET", "POST", "PUT", "DELETE", "PATCH"]
                                )
                                operation_path = st.text_input("Path")
                                if st.form_submit_button("Add Operation"):
                                    operation_config = {
                                        'name': operation_name,
                                        'method': operation_method,
                                        'path': operation_path
                                    }
                                    result = gateway.add_api_operation(latest_api['id'], operation_config)
                                    if result:
                                        st.success("Operation added successfully!")
                                        st.experimental_rerun()
                                    else:
                                        st.error("Failed to add operation")
                    
                    with tab5:
                        st.subheader("API Analytics")
                        time_range = st.selectbox(
                            "Time Range",
                            ["1h", "24h", "7d", "30d"]
                        )
                        analytics = gateway.get_api_analytics(latest_api['id'], time_range)
                        if analytics:
                            # Display analytics data
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Requests", analytics.get('totalRequests', 0))
                            with col2:
                                st.metric("Success Rate", f"{analytics.get('successRate', 0)}%")
                            with col3:
                                st.metric("Average Latency", f"{analytics.get('avgLatency', 0)}ms")
                            
                            # Add more analytics visualizations here
                        else:
                            st.info("No analytics data available")
            elif gateway_type == 'kong':
                # Kong specific API management
                st.subheader("Kong API Management")
                
                # API selection
                selected_api = st.selectbox(
                    "Select API",
                    [api['name'] for api in apis]
                )
                
                if selected_api:
                    # Get the selected API details
                    api_details = next(api for api in apis if api['name'] == selected_api)
                    
                    # API details tabs
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "Overview", "Routes", "Plugins", 
                        "Consumers", "Analytics"
                    ])
                    
                    with tab1:
                        st.subheader("API Overview")
                        st.json(api_details)
                        
                        # Display API metrics
                        metrics = gateway.get_api_metrics(api_details['id'])
                        if metrics:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Routes", len(metrics.get('routes', [])))
                            with col2:
                                st.metric("Total Plugins", len(metrics.get('plugins', [])))
                            with col3:
                                st.metric("Total Consumers", len(metrics.get('consumers', [])))
                    
                    with tab2:
                        st.subheader("API Routes")
                        routes = metrics.get('routes', [])
                        if routes:
                            routes_data = []
                            for route in routes:
                                # Safely handle methods that might be None or not a list
                                methods = route.get('methods', [])
                                if methods is None:
                                    methods = []
                                elif not isinstance(methods, list):
                                    methods = [methods]
                                
                                # Safely handle paths that might be None or not a list
                                paths = route.get('paths', [])
                                if paths is None:
                                    paths = []
                                elif not isinstance(paths, list):
                                    paths = [paths]
                                
                                # Safely handle protocols that might be None or not a list
                                protocols = route.get('protocols', [])
                                if protocols is None:
                                    protocols = []
                                elif not isinstance(protocols, list):
                                    protocols = [protocols]
                                
                                routes_data.append({
                                    "Name": route.get('name', ''),
                                    "Paths": ", ".join(paths),
                                    "Methods": ", ".join(methods),
                                    "Protocols": ", ".join(protocols),
                                    "Strip Path": str(route.get('strip_path', False)),
                                    "Preserve Host": str(route.get('preserve_host', False))
                                })
                            st.table(routes_data)
                        else:
                            st.info("No routes configured")
                        
                        # Add new route
                        with st.expander("Add New Route"):
                            with st.form("new_route"):
                                route_name = st.text_input("Route Name")
                                paths = st.text_input("Paths (comma-separated)")
                                methods = st.multiselect(
                                    "Methods",
                                    ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
                                )
                                protocols = st.multiselect(
                                    "Protocols",
                                    ["http", "https"]
                                )
                                strip_path = st.checkbox("Strip Path", value=True)
                                preserve_host = st.checkbox("Preserve Host", value=False)
                                
                                if st.form_submit_button("Add Route"):
                                    route_config = {
                                        'name': route_name,
                                        'paths': [p.strip() for p in paths.split(',')],
                                        'methods': methods,
                                        'protocols': protocols,
                                        'strip_path': strip_path,
                                        'preserve_host': preserve_host,
                                        'service': {'id': api_details['id']}
                                    }
                                    result = gateway._make_request('POST', '/routes', json=route_config)
                                    if result:
                                        st.success("Route added successfully!")
                                        st.experimental_rerun()
                                    else:
                                        st.error("Failed to add route")
                    
                    with tab3:
                        st.subheader("API Plugins")
                        plugins = metrics.get('plugins', [])
                        if plugins:
                            plugins_data = []
                            for plugin in plugins:
                                plugins_data.append({
                                    "Name": plugin.get('name', ''),
                                    "Enabled": str(plugin.get('enabled', False)),
                                    "Config": json.dumps(plugin.get('config', {}))
                                })
                            st.table(plugins_data)
                        else:
                            st.info("No plugins configured")
                        
                        # Add new plugin
                        with st.expander("Add New Plugin"):
                            with st.form("new_plugin"):
                                plugin_name = st.selectbox(
                                    "Plugin Name",
                                    ["rate-limiting", "key-auth", "jwt", "cors", "request-transformer"]
                                )
                                plugin_enabled = st.checkbox("Enabled", value=True)
                                plugin_config = st.text_area("Configuration (JSON)")
                                
                                if st.form_submit_button("Add Plugin"):
                                    try:
                                        config = json.loads(plugin_config) if plugin_config else {}
                                        plugin_config = {
                                            'name': plugin_name,
                                            'enabled': plugin_enabled,
                                            'config': config,
                                            'service': {'id': api_details['id']}
                                        }
                                        result = gateway._make_request('POST', '/plugins', json=plugin_config)
                                        if result:
                                            st.success("Plugin added successfully!")
                                            st.experimental_rerun()
                                        else:
                                            st.error("Failed to add plugin")
                                    except json.JSONDecodeError:
                                        st.error("Invalid JSON configuration")
                    
                    with tab4:
                        st.subheader("API Consumers")
                        consumers = metrics.get('consumers', [])
                        if consumers:
                            consumers_data = []
                            for consumer in consumers:
                                consumers_data.append({
                                    "Username": consumer.get('username', ''),
                                    "Custom ID": consumer.get('custom_id', ''),
                                    "Created": consumer.get('created_at', '')
                                })
                            st.table(consumers_data)
                        else:
                            st.info("No consumers configured")
                        
                        # Add new consumer
                        with st.expander("Add New Consumer"):
                            with st.form("new_consumer"):
                                username = st.text_input("Username")
                                custom_id = st.text_input("Custom ID")
                                
                                if st.form_submit_button("Add Consumer"):
                                    consumer_config = {
                                        'username': username,
                                        'custom_id': custom_id
                                    }
                                    result = gateway._make_request('POST', '/consumers', json=consumer_config)
                                    if result:
                                        st.success("Consumer added successfully!")
                                        st.experimental_rerun()
                                    else:
                                        st.error("Failed to add consumer")
                    
                    with tab5:
                        st.subheader("API Analytics")
                        time_range = st.selectbox(
                            "Time Range",
                            ["1h", "24h", "7d", "30d"]
                        )
                        analytics = gateway.get_api_metrics(api_details['id'])
                        if analytics:
                            # Display analytics data
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Requests", analytics.get('total_requests', 0))
                            with col2:
                                st.metric("Success Rate", f"{analytics.get('success_rate', 0)}%")
                            with col3:
                                st.metric("Average Latency", f"{analytics.get('avg_latency', 0)}ms")
                            
                            # Add more analytics visualizations here
                        else:
                            st.info("No analytics data available")
            elif gateway_type == 'gravitee': # Add this block
                st.subheader("Gravitee API Management")
                # API selection
                selected_api = st.selectbox(
                    "Select API",
                    [api.get('name', api.get('id', 'Unknown')) for api in apis] # Adjust based on Gravitee API structure
                )

                if selected_api:
                    # Find the selected API details (adjust key based on Gravitee response)
                    api_details = next((api for api in apis if api.get('name', api.get('id')) == selected_api), None)

                    if api_details:
                        st.subheader(f"Details for {selected_api}")
                        st.json(api_details)

                        # Add tabs for Overview, Plans, Policies, Analytics etc. based on Gravitee features
                        tab1, tab2 = st.tabs(["Overview", "Analytics"])

                        with tab1:
                            st.write("API Overview details here...")
                            # Add forms for updating/deleting the API

                        with tab2:
                            st.write("API Analytics/Metrics here...")
                            # Fetch and display metrics using gateway.get_api_metrics(api_details['id'])

                # Add form/button to create a new Gravitee API
                with st.expander("Create New Gravitee API"):
                    with st.form("new_gravitee_api"):
                        st.write("Form fields for creating a Gravitee API...")
                        # Add inputs for name, context path, version, endpoints etc.
                        submitted = st.form_submit_button("Create API")
                        if submitted:
                            # Construct api_config dict from form inputs
                            # result = gateway.create_api(api_config)
                            # Show success/error message
                            pass # Placeholder

            elif gateway_type == 'tyk': # Add this block
                st.subheader("Tyk API Management")

                # API selection
                # Adjust the key based on how Tyk returns the API name in the list
                selected_api_name = st.selectbox(
                    "Select API",
                    [api.get('name', api.get('api_id', 'Unknown')) for api in apis]
                )

                if selected_api_name:
                    # Find the selected API details (adjust key based on Tyk response)
                    api_details = next((api for api in apis if api.get('name', api.get('api_id')) == selected_api_name), None)

                    if api_details:
                        # Fetch full details which might include metrics/config
                        full_api_details = gateway.get_api_metrics(api_details['api_id'])

                        st.subheader(f"Details for {selected_api_name}")
                        st.json(full_api_details if full_api_details else api_details) # Show full details if available

                        # Add tabs based on Tyk API Definition structure (e.g., Versioning, Middleware, Analytics)
                        tab1, tab2 = st.tabs(["Overview", "Definition"])

                        with tab1:
                            st.write("API Overview details here...")
                            # Display key info like listen_path, target_url, auth type etc.
                            st.write(f"**Listen Path:** {full_api_details.get('proxy', {}).get('listen_path', 'N/A')}")
                            st.write(f"**Target URL:** {full_api_details.get('proxy', {}).get('target_url', 'N/A')}")
                            auth_type = "Enabled" if full_api_details.get('use_keyless') is False else "Keyless"
                            st.write(f"**Authentication:** {auth_type}")
                            # Add forms for updating/deleting the API

                        with tab2:
                            st.write("Full API Definition:")
                            st.json(full_api_details)


                # Add form/button to create a new Tyk API
                with st.expander("Create New Tyk API"):
                     with st.form("new_tyk_api"):
                         st.write("Define Tyk API (JSON)")
                         # Tyk API definitions are complex JSON objects
                         api_definition_json = st.text_area("API Definition (JSON)", height=400, placeholder='{\n  "name": "MyTykAPI",\n  "api_id": "mytykapi",\n  "org_id": "1",\n  "use_keyless": true,\n  "proxy": {\n    "listen_path": "/mytykapi/",\n    "target_url": "http://httpbin.org",\n    "strip_listen_path": true\n  },\n  "version_data": {\n    "not_versioned": true,\n    "versions": {\n      "Default": {\n        "name": "Default",\n        "use_extended_paths": true\n      }\n    }\n  }\n}')
                         submitted = st.form_submit_button("Create API")
                         if submitted:
                             try:
                                 api_config = json.loads(api_definition_json)
                                 result = gateway.create_api(api_config)
                                 if result and not result.get('error'):
                                     st.success(f"Tyk API created successfully! ID: {result.get('Meta')}")
                                     st.experimental_rerun()
                                 else:
                                     st.error(f"Failed to create Tyk API: {result.get('error', 'Unknown error')}")
                                     if result.get('details'):
                                         st.json(result.get('details'))
                             except json.JSONDecodeError:
                                 st.error("Invalid JSON definition provided.")
                             except Exception as e:
                                 st.error(f"An error occurred: {str(e)}")

elif page == "Settings":
    st.header("Settings")
    st.write("Configure your API Gateway Control Plane settings.")
    
    # Settings interface
    st.subheader("General Settings")
    theme = st.selectbox("Theme", ["Light", "Dark"])
    refresh_rate = st.slider("Data Refresh Rate (seconds)", 30, 300, 60)
    
    # Debug settings
    st.subheader("Debug Settings")
    debug_level = st.selectbox(
        "Logging Level",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        index=1
    )
    logger.setLevel(debug_level)
    
    # Database management
    st.subheader("Database Management")
    if st.button("Clear Database", key="clear_db"):
        if st.warning("Are you sure you want to clear all gateway configurations? This action cannot be undone."):
            if db.clear_database():
                st.session_state.gateways = []
                st.success("Database cleared successfully!")
            else:
                st.error("Failed to clear database")
    
    if st.button("Save Settings"):
        st.success("Settings saved successfully!")

# Add cleanup for temporary directories
if 'temp_dirs' in st.session_state:
    for temp_dir in st.session_state['temp_dirs']:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")
    st.session_state['temp_dirs'] = []

# Add performance monitoring
if st.sidebar.checkbox("Show Performance Metrics", value=False):
    st.sidebar.write("Performance Metrics")
    st.sidebar.metric("Memory Usage", f"{psutil.Process().memory_info().rss / 1024 / 1024:.2f} MB")
    st.sidebar.metric("CPU Usage", f"{psutil.Process().cpu_percent()}%")
    st.sidebar.metric("Response Time", f"{time.time() - st.session_state.get('start_time', time.time()):.2f}s")