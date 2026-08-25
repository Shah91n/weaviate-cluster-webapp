"""Entrypoint and router.

With `st.navigation` this file is not a page: it runs on every rerun as the frame
around whichever page is active. It owns session state, the single
`st.set_page_config` call, the connection sidebar and the navigation. The cluster
dashboard itself lives in `pages/cluster.py`.
"""

import streamlit as st

from core.connection.weaviate_client import disconnect_weaviate, initialize_weaviate_connection
from pages.utils.helper import clear_session_state, update_side_bar_labels
from pages.utils.navigation import build_navigation
from pages.utils.page_config import LOGO_PATH, configure_app

# --------------------------------------------------------------------------
# Initialize session state
# --------------------------------------------------------------------------
if "client_ready" not in st.session_state:
    st.session_state.client_ready = False
if "use_local" not in st.session_state:
    st.session_state.use_local = False
if "use_custom" not in st.session_state:
    st.session_state.use_custom = False

# Local connection state
if "local_http_port" not in st.session_state:
    st.session_state.local_http_port = 8080
if "local_grpc_port" not in st.session_state:
    st.session_state.local_grpc_port = 50051
if "local_api_key" not in st.session_state:
    st.session_state.local_api_key = ""

# Custom connection state
if "custom_http_host" not in st.session_state:
    st.session_state.custom_http_host = "localhost"
if "custom_http_port" not in st.session_state:
    st.session_state.custom_http_port = 8080
if "custom_grpc_host" not in st.session_state:
    st.session_state.custom_grpc_host = "localhost"
if "custom_grpc_port" not in st.session_state:
    st.session_state.custom_grpc_port = 50051
if "custom_secure" not in st.session_state:
    st.session_state.custom_secure = False
if "custom_api_key" not in st.session_state:
    st.session_state.custom_api_key = ""

# Cloud connection state
if "cloud_endpoint" not in st.session_state:
    st.session_state.cloud_endpoint = ""
if "cloud_api_key" not in st.session_state:
    st.session_state.cloud_api_key = ""

# ============================================
# Auto-populate from URL query parameters
# Example usage:
# streamlit run streamlit_app.py --server.headless=true &
# sleep 2
# open "http://localhost:8501/?endpoint=<YOUR_ENDPOINT>&api_key=<YOUR_API_KEY>"
# ============================================
if "auto_connect_attempted" not in st.session_state:
    st.session_state.auto_connect_attempted = False

# Read query parameters from URL (e.g., ?endpoint=xxx&api_key=yyy)
query_params = st.query_params
if not st.session_state.auto_connect_attempted and "endpoint" in query_params and "api_key" in query_params:
    # Auto-populate cloud connection fields
    st.session_state.cloud_endpoint = query_params["endpoint"]
    st.session_state.cloud_api_key = query_params["api_key"]
    st.session_state.auto_connect_attempted = True
    # Ensure cloud mode is selected (not local/custom)
    st.session_state.use_local = False
    st.session_state.use_custom = False
# ============================================

# Vectorizer keys
if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""
if "cohere_key" not in st.session_state:
    st.session_state.cohere_key = ""
    
# Active connection state
if "active_endpoint" not in st.session_state:
    st.session_state.active_endpoint = ""
if "active_api_key" not in st.session_state:
    st.session_state.active_api_key = ""

# --------------------------------------------------------------------------
# Page config + logo. Called once here; pages must not call st.set_page_config.
# --------------------------------------------------------------------------
configure_app()
st.logo(LOGO_PATH, size="large")

# --------------------------------------------------------------------------
# Navigation. Built before the sidebar widgets so the page menu sits above the
# connection panel. While disconnected it offers the Cluster page only.
# --------------------------------------------------------------------------
current_page = build_navigation(st.session_state.get("client_ready", False))

# --------------------------------------------------------------------------
# Connection panel
# --------------------------------------------------------------------------
st.sidebar.title("✨Weaviate Connection✨")

if not st.session_state.client_ready:
    # Set the default value of connection type
    def local_checkbox_callback():
        if st.session_state.use_local:
            st.session_state.use_custom = False

    def custom_checkbox_callback():
        if st.session_state.use_custom:
            st.session_state.use_local = False

    # Connect to Weaviate
    use_local = st.sidebar.checkbox("Local", key='use_local', on_change=local_checkbox_callback)
    use_custom = st.sidebar.checkbox("Custom", key='use_custom', on_change=custom_checkbox_callback)

    # Conditional UI based on checkboxes
    if st.session_state.use_local:
        st.sidebar.markdown(
            'Clone the repository from [**Shah91n -> WeaviateCluster**](https://github.com/Shah91n/WeaviateCluster) GitHub and following the installation requirements. Then ensure that you have a local Weaviate instance running on your machine before attempting to connect.'
        )
        # This is now a display-only field, its value is derived from other state.
        # It does NOT have a key, which is critical to avoid state conflicts.
        st.sidebar.text_input(
            "Local Cluster Endpoint",
            value=f"http://localhost:{st.session_state.local_http_port}",
            disabled=True,
        )
        st.sidebar.number_input(
            "HTTP Port",
            value=st.session_state.local_http_port,
            key="local_http_port"
        )
        st.sidebar.number_input(
            "gRPC Port",
            value=st.session_state.local_grpc_port,
            key="local_grpc_port"
        )
        st.sidebar.text_input(
            "Local Cluster API Key",
            placeholder="Enter Cluster Admin Key",
            type="password",
            key="local_api_key"
        )

    elif st.session_state.use_custom:
        st.sidebar.markdown(
            'Clone the repository from [**Shah91n -> WeaviateCluster**](https://github.com/Shah91n/WeaviateCluster) GitHub and following the installation requirements. Then ensure that you have a custom Weaviate instance running before attempting to connect.'
        )
        st.sidebar.text_input(
            "Custom HTTP Host",
            placeholder="e.g., localhost",
            key="custom_http_host"
        )
        st.sidebar.number_input(
            "Custom HTTP Port",
            value=st.session_state.custom_http_port,
            key="custom_http_port"
        )
        st.sidebar.text_input(
            "Custom gRPC Host",
            placeholder="e.g., localhost",
            key="custom_grpc_host"
        )
        st.sidebar.number_input(
            "Custom gRPC Port",
            value=st.session_state.custom_grpc_port,
            key="custom_grpc_port"
        )
        st.sidebar.checkbox(
            "Use Secure Connection (HTTPS/gRPC)",
            key="custom_secure"
        )
        st.sidebar.text_input(
            "Custom Cluster API Key",
            placeholder="Enter Cluster Admin Key",
            type="password",
            key="custom_api_key"
        )

    else: # Cloud connection
        st.sidebar.markdown(
            'Connect to a Weaviate Cloud Cluster hosted by Weaviate. You can create clusters at [Weaviate Cloud](https://console.weaviate.cloud/).'
        )
        st.sidebar.text_input(
            "Cloud Cluster Endpoint",
            placeholder="Enter Cluster Endpoint (URL)",
            key="cloud_endpoint"
        )
        st.sidebar.text_input(
            "Cloud Cluster API Key",
            placeholder="Enter Cluster Admin Key",
            type="password",
            key="cloud_api_key"
        )

    # --------------------------------------------------------------------------
    # Vectorizers Integration API Keys Section
    # --------------------------------------------------------------------------
    st.sidebar.markdown("Add API keys for Model provider integrations (optional):")
    st.sidebar.text_input("OpenAI API Key", type="password", key="openai_key")
    st.sidebar.text_input("Cohere API Key", type="password", key="cohere_key")

    # --------------------------------------------------------------------------
    # Connect/Disconnect Buttons
    # --------------------------------------------------------------------------
    if st.sidebar.button("Connect", width="stretch", type="secondary"):
        
        # Vectorizers Integration API Keys
        vectorizer_integration_keys = {}
        if st.session_state.openai_key:
            vectorizer_integration_keys["X-OpenAI-Api-Key"] = st.session_state.openai_key
        if st.session_state.cohere_key:
            vectorizer_integration_keys["X-Cohere-Api-Key"] = st.session_state.cohere_key

        if st.session_state.use_local:
            success, details = initialize_weaviate_connection(
                use_local=True,
                http_port_endpoint=st.session_state.local_http_port,
                grpc_port_endpoint=st.session_state.local_grpc_port,
                cluster_api_key=st.session_state.local_api_key,
                vectorizer_integration_keys=vectorizer_integration_keys
            )
            if success:
                st.sidebar.success("Local connection successful!")
                st.session_state.client_ready = details.get("client_ready", True)
                st.session_state.server_version = details.get("server_version", "N/A")
                st.session_state.active_endpoint = details.get("endpoint", f"http://localhost:{st.session_state.local_http_port}")
                st.session_state.active_api_key = st.session_state.local_api_key
                st.session_state.active_openai_key = st.session_state.openai_key
                st.session_state.active_cohere_key = st.session_state.cohere_key
                st.rerun()
            else:
                st.session_state.client_ready = False
                st.sidebar.error(details.get("error", "Connection failed!"))

        elif st.session_state.use_custom:
            success, details = initialize_weaviate_connection(
                use_custom=True,
                http_host_endpoint=st.session_state.custom_http_host,
                http_port_endpoint=st.session_state.custom_http_port,
                grpc_host_endpoint=st.session_state.custom_grpc_host,
                grpc_port_endpoint=st.session_state.custom_grpc_port,
                custom_secure=st.session_state.custom_secure,
                cluster_api_key=st.session_state.custom_api_key,
                vectorizer_integration_keys=vectorizer_integration_keys
            )
            if success:
                st.sidebar.success("Custom Connection successful!")
                st.session_state.client_ready = details.get("client_ready", True)
                st.session_state.server_version = details.get("server_version", "N/A")
                protocol = "https" if st.session_state.custom_secure else "http"
                st.session_state.active_endpoint = details.get("endpoint", f"{protocol}://{st.session_state.custom_http_host}:{st.session_state.custom_http_port}")
                st.session_state.active_api_key = st.session_state.custom_api_key
                st.session_state.active_openai_key = st.session_state.openai_key
                st.session_state.active_cohere_key = st.session_state.cohere_key
                st.rerun()
            else:
                st.session_state.client_ready = False
                st.sidebar.error(details.get("error", "Connection failed!"))
        else: # Cloud
            cloud_endpoint = st.session_state.cloud_endpoint
            if cloud_endpoint and not cloud_endpoint.startswith('https://'):
                cloud_endpoint = f"https://{cloud_endpoint}"

            if not cloud_endpoint or not st.session_state.cloud_api_key:
                st.sidebar.error("Please insert the cluster endpoint and API key!")
            else:
                success, details = initialize_weaviate_connection(
                    cluster_endpoint=cloud_endpoint,
                    cluster_api_key=st.session_state.cloud_api_key,
                    vectorizer_integration_keys=vectorizer_integration_keys
                )
                if success:
                    st.sidebar.success("Cloud Connection successful!")
                    st.session_state.client_ready = details.get("client_ready", True)
                    st.session_state.server_version = details.get("server_version", "N/A")
                    st.session_state.active_endpoint = details.get("endpoint", cloud_endpoint)
                    st.session_state.active_api_key = st.session_state.cloud_api_key
                    st.session_state.active_openai_key = st.session_state.openai_key
                    st.session_state.active_cohere_key = st.session_state.cohere_key
                    st.rerun()
                else:
                    st.session_state.client_ready = False
                    st.sidebar.error(details.get("error", "Connection failed!"))
else:
    if st.sidebar.button("Disconnect", width="stretch", type="primary"):
        success, message = disconnect_weaviate()
        if success:
            st.toast('Session, states and cache cleared! Weaviate client disconnected successfully!', icon='🔴')
            clear_session_state()
        else:
            st.sidebar.error(message)
    st.sidebar.info("Disconnect Button does clear all session states and cache, and disconnect the Weaviate client to server if connected.")

# --------------------------------------------------------------------------
# Connection status, then hand off to the active page.
# --------------------------------------------------------------------------
update_side_bar_labels()

current_page.run()
