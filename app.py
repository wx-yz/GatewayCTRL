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
import pandas as pd  # Import pandas for dataframes
from streamlit_option_menu import option_menu  # Import the function

# Set page config - MUST be the first Streamlit command
st.set_page_config(
    page_title="GatewayCTRL",  # Shorter title
    page_icon="static/logo.png",  # Use your logo
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Icon Mapping ---
GATEWAY_ICONS = {
    "aws": "static/aws.png",
    "wso2": "static/wso2.png",
    "kong": "static/kong.png",
    "gravitee": "static/gravitee.png",
    "tyk": "static/tyk.png",
}

# Font Awesome Icons for Sidebar (Example)
PAGE_ICONS = {
    "Dashboard": "fas tachometer",
    "Gateway Management": "fas server",
    "API Management": "fas list",
    "Settings": "fas cogs"  # Example if you add settings
}

# Helper function to get icon path or return None
def get_gateway_icon(gateway_type):
    return GATEWAY_ICONS.get(gateway_type)

# --- Inject Custom CSS ---
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        logger.warning(f"CSS file not found: {file_name}")

local_css("static/styles.css")

# --- Database Initialization & Session State ---
db = Database()
if 'gateways' not in st.session_state:
    st.session_state.gateways = db.get_gateways()

if 'temp_dirs' not in st.session_state:
    st.session_state['temp_dirs'] = []

if 'start_time' not in st.session_state:
    st.session_state['start_time'] = time.time()

# --- Sidebar Navigation ---
st.sidebar.image("static/logo.png")  # Keep logo
# st.sidebar.title("GatewayCTRL")  # Keep title

# Use streamlit-option-menu for navigation
with st.sidebar:  # Place option_menu within the sidebar context
    selected_page_name = option_menu(
        menu_title=None,  # No main menu title needed
        options=["Dashboard", "Gateway Management", "API Management"],  # Page names
        icons=[PAGE_ICONS["Dashboard"].replace("fas fa-", ""),  # Use icon names without 'fas fa-' prefix
               PAGE_ICONS["Gateway Management"].replace("fas fa-", ""),
               PAGE_ICONS["API Management"].replace("fas fa-", "")],
        menu_icon="cast",  # Optional overall menu icon
        default_index=0,  # Start on Dashboard
        styles={  # Apply styles consistent with your CSS
            "container": {"padding": "0!important", "background-color": "var(--card-background)"},
            "icon": {"color": "var(--text-secondary)", "font-size": "18px"},  # Adjust icon size/color
            "nav-link": {"font-size": "1rem", "text-align": "left", "margin": "0px", "--hover-color": "rgba(255, 255, 255, 0.05)", "color": "var(--text-secondary)"},
            "nav-link-selected": {"background-color": "rgba(74, 144, 226, 0.15)", "color": "var(--primary-color)", "font-weight": "600"},
            "nav-link-selected > .icon": {"color": "var(--primary-color)"},  # Ensure selected icon color changes
        }
    )

st.sidebar.markdown("---")  # Keep separator before system status
# Display resource usage for the current process
st.sidebar.subheader("App Status")  # Changed title slightly
try:
    # Get the current process
    process = psutil.Process(os.getpid())

    # Get CPU usage for the process (use interval for a more accurate reading)
    process_cpu_usage = process.cpu_percent(interval=0.1)
    st.sidebar.progress(int(process_cpu_usage))
    st.sidebar.caption(f"App CPU Usage: {process_cpu_usage:.1f}%")

    # Get memory usage for the process (RSS - Resident Set Size)
    process_mem_info = process.memory_info()
    process_mem_used_mb = process_mem_info.rss / (1024 * 1024)  # Convert bytes to MB

    # Get total system memory to calculate percentage (optional, but good context)
    total_system_memory = psutil.virtual_memory().total
    process_mem_percent = (process_mem_info.rss / total_system_memory) * 100 if total_system_memory > 0 else 0

    st.sidebar.progress(int(process_mem_percent))
    st.sidebar.caption(f"App Memory Usage: {process_mem_used_mb:.1f} MB ({process_mem_percent:.1f}%)")

except Exception as e:
    logger.error(f"Could not get process resource usage: {e}")
    st.sidebar.caption("Could not retrieve app usage.")

# --- Page Content ---
if selected_page_name == "Dashboard":
    st.title("📊 Dashboard")
    st.markdown("Overview of your configured API Gateways.")

    total_gateways = len(st.session_state.gateways)
    total_apis = 0  # Calculate below

    # Use columns for key metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Gateways Configured", total_gateways)
    # Placeholder for total APIs, calculated below
    total_apis_placeholder = col2.empty()

    st.markdown("### Gateway Status & API Counts")

    if not st.session_state.gateways:
        st.info("No gateways configured yet. Add one in 'Gateway Management'.")
    else:
        gateway_cols = st.columns(len(st.session_state.gateways) if len(st.session_state.gateways) <= 4 else 4)  # Max 4 columns
        col_idx = 0
        for gateway in st.session_state.gateways:
            with gateway_cols[col_idx % len(gateway_cols)]:
                # Use a container with custom class for card styling
                with st.container():
                    icon_path = get_gateway_icon(gateway['type'])
                    st.markdown(f"#### ![vendorlogo](/app/{icon_path}) {gateway['name']}")
                    st.caption(f"Type: {gateway['type'].upper()} | URL: {gateway['config'].url}")
                    try:
                        # Create instance first
                        gateway_instance = GatewayFactory.create_gateway(gateway['type'], gateway['config'])

                        # Test connection
                        connection_ok = False
                        with st.spinner("Testing connection..."):
                            connection_ok = gateway_instance.test_connection()

                        if connection_ok:
                            st.success("Connected") # Display connection status
                            # Fetch API count only if connected
                            with st.spinner("Fetching API count..."):
                                apis = gateway_instance.get_apis()  # Consider caching this
                            api_count = len(apis)
                            total_apis += api_count
                            st.metric("APIs", api_count)
                        else:
                            st.error("Connection Failed") # Display connection status
                            st.metric("APIs", "N/A") # Show N/A if connection failed

                    except Exception as e:
                        logger.error(f"Error testing connection or getting APIs for gateway {gateway['name']} in dashboard: {str(e)}", exc_info=False)
                        st.error("Error") # General error state
                        st.metric("APIs", "Error")

            col_idx += 1

        # Update total APIs metric
        total_apis_placeholder.metric("Total APIs Managed", total_apis)

elif selected_page_name == "Gateway Management":
    st.title("🔧 Gateway Management")
    st.markdown("Add, configure, and remove API Gateway connections.")

    # --- Determine which gateway to edit (if any) ---
    # Check if an edit button was clicked in the previous run
    gateway_name_to_edit_from_button = st.session_state.get('editing_gateway_name')
    default_selectbox_index = 0
    if gateway_name_to_edit_from_button:
        try:
            # Find the index of the gateway clicked for editing
            gateway_names_list = ["<New Gateway>"] + [g['name'] for g in st.session_state.gateways]
            default_selectbox_index = gateway_names_list.index(gateway_name_to_edit_from_button)
        except ValueError:
            # Gateway might have been deleted in another session/tab, default to New
            pass
        # Clear the state variable after using it
        del st.session_state['editing_gateway_name']

    # --- Add/Edit Gateway Form ---
    with st.container():
        # st.markdown('<div class="card">', unsafe_allow_html=True) # Assuming card style is applied by container or CSS
        st.markdown('<div class="card-header"><i class="fas fa-plus-circle"></i> Add / Edit Gateway</div>', unsafe_allow_html=True)

        # Add/Edit gateway form logic
        gateway_names = ["<New Gateway>"] + [g['name'] for g in st.session_state.gateways]
        # Use the calculated default_index
        selected_gateway_name_to_edit = st.selectbox(
            "Select Gateway to Edit or Add New",
            gateway_names,
            index=default_selectbox_index, # Set default based on edit button click
            key="gw_edit_select"
        )

        # Pre-fill form if editing (based on selectbox value)
        gateway_to_edit = None
        if selected_gateway_name_to_edit != "<New Gateway>":
            gateway_to_edit = next((g for g in st.session_state.gateways if g['name'] == selected_gateway_name_to_edit), None)

        # Form fields (pre-filled based on gateway_to_edit)
        gateway_name = st.text_input("Gateway Name", value=gateway_to_edit['name'] if gateway_to_edit else "", key="gw_name_input")
        gateway_type = st.selectbox(
            "Gateway Type",
            list(GatewayFactory._gateways.keys()),
            index=list(GatewayFactory._gateways.keys()).index(gateway_to_edit['type']) if gateway_to_edit else 0,
            key="gw_type_select"
        )
        gateway_url = st.text_input("Gateway Management URL", value=gateway_to_edit['config'].url if gateway_to_edit else "", key="gw_url_input")

        # SSL Configuration
        st.markdown("###### SSL Configuration")
        verify_ssl = st.checkbox("Verify SSL Certificate", value=gateway_to_edit['config'].verify_ssl if gateway_to_edit else True, key="gw_ssl_verify")
        # Display current cert path if editing and exists
        current_cert_path = gateway_to_edit['config'].cert_path if gateway_to_edit else None
        if current_cert_path:
            st.caption(f"Current certificate: `{os.path.basename(current_cert_path)}`")
        uploaded_cert = st.file_uploader("Upload New Custom CA Certificate (Optional, replaces existing)", type=['pem', 'crt'], key="gw_cert_upload")
        cert_path = current_cert_path # Start with existing path

        # Gateway Specific Configuration
        additional_config = {}
        st.markdown(f"###### {gateway_type.upper()} Specific Configuration")
        # Use unique keys for inputs within specific config sections
        if gateway_type == 'wso2':
            username = st.text_input("Username", value=gateway_to_edit['config'].additional_config.get('username', '') if gateway_to_edit else "", key="gw_wso2_user")
            password = st.text_input("Password", type="password", value=gateway_to_edit['config'].additional_config.get('password', '') if gateway_to_edit else "", key="gw_wso2_pass")
            additional_config = {'username': username, 'password': password}
        # ... (Add unique keys like key="gw_kong_key", key="gw_tyk_secret" etc. for other gateway types) ...

        # Add/Update Button
        if st.button("💾 Save Gateway Configuration"):
            if not gateway_name or not gateway_url:
                st.error("Gateway Name and URL are required.")
            # Prevent editing name to conflict with another existing gateway (if editing)
            elif gateway_to_edit and gateway_name != gateway_to_edit['name'] and any(g['name'] == gateway_name for g in st.session_state.gateways):
                 st.error(f"A gateway with the name '{gateway_name}' already exists.")
            # Prevent adding a new gateway with a conflicting name
            elif not gateway_to_edit and any(g['name'] == gateway_name for g in st.session_state.gateways):
                 st.error(f"A gateway with the name '{gateway_name}' already exists.")
            else:
                # Handle certificate upload (overwrites cert_path if new file uploaded)
                if uploaded_cert is not None:
                    cert_dir = "certificates"
                    os.makedirs(cert_dir, exist_ok=True)
                    # Use the potentially new gateway_name for the cert filename
                    new_cert_filename = f"{gateway_name}_ca.{uploaded_cert.name.split('.')[-1]}"
                    cert_path = os.path.join(cert_dir, new_cert_filename)
                    with open(cert_path, "wb") as f:
                        f.write(uploaded_cert.getvalue())
                    logger.info(f"Saved/Updated custom certificate to {cert_path}")
                    # Clean up old cert file if name changed and old cert existed
                    if gateway_to_edit and current_cert_path and current_cert_path != cert_path and os.path.exists(current_cert_path):
                         try:
                             os.remove(current_cert_path)
                             logger.info(f"Removed old certificate file: {current_cert_path}")
                         except OSError as e:
                             logger.error(f"Error removing old certificate file {current_cert_path}: {e}")

                config = GatewayConfig(
                    name=gateway_name, # Use the name from the input field
                    url=gateway_url,
                    additional_config=additional_config,
                    verify_ssl=verify_ssl,
                    cert_path=cert_path
                )

                try:
                    # Test connection before saving
                    gateway_instance = GatewayFactory.create_gateway(gateway_type, config)
                    with st.spinner("Testing connection..."):
                        if gateway_instance.test_connection():
                            original_name = gateway_to_edit['name'] if gateway_to_edit else gateway_name
                            if gateway_to_edit: # Update existing
                                db.update_gateway(original_name, gateway_type, config) # Use original name to find record
                                st.success(f"Gateway '{config.name}' updated successfully!")
                            else: # Add new
                                db.add_gateway(config.name, gateway_type, config)
                                st.success(f"Gateway '{config.name}' added successfully!")

                            # Update session state and rerun
                            st.session_state.gateways = db.get_gateways()
                            time.sleep(1) # Brief pause
                            st.rerun() # Use st.rerun() instead of experimental_rerun
                        else:
                            st.error("Connection test failed. Please check configuration and network.")
                except Exception as e:
                    logger.error(f"Error saving/testing gateway {gateway_name}: {e}", exc_info=True)
                    st.error(f"Failed to save gateway: {e}")

        # st.markdown('</div>', unsafe_allow_html=True) # Assuming card style is applied by container or CSS

    # --- List Existing Gateways ---
    if st.session_state.gateways:
        st.markdown("### Existing Gateways")
        for gateway in st.session_state.gateways:
            # st.markdown('<div class="card">', unsafe_allow_html=True) # Start card div

            icon_path = get_gateway_icon(gateway['type'])
            col1, col2, col3 = st.columns([8, 1, 1]) # Adjust column ratios

            with col1:
                st.markdown(f"#### ![vendorlogo](/app/{icon_path}) {gateway['name']}")
                st.caption(f"Type: {gateway['type'].upper()} | URL: {gateway['config'].url}")
                with st.expander("View Configuration"):
                    # Use model_dump() instead of dict()
                    config_dict = gateway['config'].model_dump()
                    # Mask sensitive fields before displaying
                    if 'password' in config_dict.get('additional_config', {}):
                        config_dict['additional_config']['password'] = "****"
                    if 'tyk_auth_secret' in config_dict.get('additional_config', {}):
                         config_dict['additional_config']['tyk_auth_secret'] = "****"
                    if 'aws_secret_access_key' in config_dict.get('additional_config', {}):
                         config_dict['additional_config']['aws_secret_access_key'] = "****"
                    st.json(config_dict)

            with col2: # Edit Button Column
                 edit_key = f"edit_{gateway['name']}"
                 if st.button("✏️", key=edit_key, help=f"Edit {gateway['name']}"):
                     st.session_state['editing_gateway_name'] = gateway['name']
                     st.rerun() # Use st.rerun() instead of experimental_rerun

            with col3: # Delete Button Column
                delete_key = f"delete_{gateway['name']}"
                if st.button("🗑️", key=delete_key, help=f"Delete {gateway['name']}"):
                    cert_path_to_delete = gateway['config'].cert_path
                    db.delete_gateway(gateway['name'])
                    if cert_path_to_delete and os.path.exists(cert_path_to_delete):
                        try:
                            os.remove(cert_path_to_delete)
                            logger.info(f"Deleted certificate file: {cert_path_to_delete}")
                        except OSError as e:
                            logger.error(f"Error deleting certificate file {cert_path_to_delete}: {e}")
                    st.session_state.gateways = db.get_gateways()
                    st.success(f"Gateway '{gateway['name']}' deleted.")
                    time.sleep(1)
                    st.rerun() # Use st.rerun() instead of experimental_rerun

            st.markdown('</div>', unsafe_allow_html=True) # End card div

elif selected_page_name == "API Management":
    st.title("🌐 API Management")
    st.markdown("View and manage APIs on your configured gateways.")
    st.markdown("---")

    if not st.session_state.gateways:
        st.info("No gateways configured. Please add one in 'Gateway Management'.")
    else:
        gateway_options = {g['name']: g for g in st.session_state.gateways}
        selected_gateway_name = st.selectbox("Select Gateway", gateway_options.keys())

        if selected_gateway_name:
            selected_gateway_info = gateway_options[selected_gateway_name]
            gateway_type = selected_gateway_info['type']
            gateway_config = selected_gateway_info['config']

            try:
                gateway = GatewayFactory.create_gateway(gateway_type, gateway_config)
                with st.spinner(f"Fetching APIs from {selected_gateway_name}..."):
                    apis = gateway.get_apis()  # Consider caching

                if not apis:
                    st.warning(f"No APIs found on {selected_gateway_name} or failed to fetch.")
                else:
                    # Use a container with card style for API list/management
                    with st.container():
                        # st.markdown('<div class="card">', unsafe_allow_html=True)  # Start card
                        st.markdown(f'<div class="card-header"><i class="fas fa-list"></i> APIs on {selected_gateway_name} ({len(apis)})</div>', unsafe_allow_html=True)

                        # API selection (use name or id as key)
                        api_display_names = {api.get('name', api.get('id', f"Unnamed API {i}")): api.get('id', api.get('api_id')) for i, api in enumerate(apis)}
                        selected_api_display_name = st.selectbox("Select API to Manage", api_display_names.keys())

                        if selected_api_display_name:
                            selected_api_id = api_display_names[selected_api_display_name]
                            # Find the full details of the selected API
                            api_details = next((api for api in apis if api.get('id', api.get('api_id')) == selected_api_id), None)

                            if api_details:
                                st.markdown(f"### Managing: {selected_api_display_name}")
                                st.caption(f"ID: {selected_api_id}")
                                st.markdown("---")

                                # --- Example: Kong API Management Tabs ---
                                if gateway_type == 'kong':
                                    with st.spinner("Fetching API details..."):
                                         # Assuming get_api_metrics fetches routes, plugins etc. for Kong
                                         metrics = gateway.get_api_metrics(selected_api_id)

                                    # Use plain text for tab labels
                                    tab_list = ["Overview", "Routes", "Plugins", "Consumers", "Analytics"]

                                    # Pass the plain text list directly to st.tabs
                                    selected_tab = st.tabs(tab_list)

                                    # Access tabs by index (index corresponds to tab_list)
                                    with selected_tab[0]: # Overview
                                        # Add icon using st.markdown if desired
                                        st.subheader("📊 Overview") # Example: Use emoji or keep plain
                                        st.json(api_details) # Keep JSON for raw data
                                        # ... (metrics display) ...

                                    with selected_tab[1]: # Routes
                                        st.subheader("↕️ Routes") # Example: Use emoji
                                        routes = metrics.get('routes', [])
                                        # ... (rest of Routes tab code) ...

                                    with selected_tab[2]: # Plugins
                                        st.subheader("🧩 Plugins") # Example: Use emoji
                                        # ... (Plugins tab code) ...

                                    with selected_tab[3]: # Consumers
                                        st.subheader("👥 Consumers") # Example: Use emoji
                                        # ... (Consumers tab code) ...

                                    with selected_tab[4]: # Analytics
                                        st.subheader("📈 Analytics") # Example: Use emoji
                                        st.warning("Analytics data display is not yet implemented.")
                                        # ... (Analytics tab code) ...

                                # --- Add elif blocks for WSO2, Gravitee, Tyk specific tabs/views ---
                                elif gateway_type == 'wso2':
                                     # ... (WSO2 specific tabs using plain text labels) ...
                                     wso2_tab_list = ["Definition", "Operations", "Subscriptions", "Analytics"]
                                     wso2_selected_tab = st.tabs(wso2_tab_list)
                                     with wso2_selected_tab[0]: # Definition
                                         st.subheader("📄 Definition (Swagger/OpenAPI)")
                                         # ... fetch and display swagger ...
                                     with wso2_selected_tab[1]: # Operations
                                         st.subheader("⚙️ Operations")
                                         # ... display operations ...
                                     # ... etc ...


                        st.markdown("---")  # Separator
                        if st.button("➕ Create New API"):
                            st.warning("Create API form not implemented yet.")

                        st.markdown('</div>', unsafe_allow_html=True)  # End card

            except Exception as e:
                logger.error(f"Error managing APIs for {selected_gateway_name}: {str(e)}", exc_info=True)
                st.error(f"An error occurred while fetching or displaying APIs for {selected_gateway_name}: {e}")

# --- Footer ---
st.markdown("---")
st.caption("API Gateway Control Plane | Developed with Streamlit")

# --- Cleanup Temporary Directories ---
if 'temp_dirs' in st.session_state:
    for temp_dir in st.session_state['temp_dirs']:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")
    st.session_state['temp_dirs'] = []