import streamlit as st
from core.connection.weaviate_client import initialize_weaviate_connection, disconnect_weaviate
from pages.cluster.cluster_operations_handlers import action_aggregate_collections_tenants, action_collections_configuration, action_metadata, action_nodes_and_shards, action_collection_schema, action_statistics, action_diagnose
from pages.utils.navigation import navigate
from pages.utils.helper import update_side_bar_labels, clear_session_state
from pages.utils.page_config import set_custom_page_config

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
if "huggingface_key" not in st.session_state:
    st.session_state.huggingface_key = ""
    
# Active connection state
if "active_endpoint" not in st.session_state:
    st.session_state.active_endpoint = ""
if "active_api_key" not in st.session_state:
    st.session_state.active_api_key = ""

# --------------------------------------------------------------------------
# Streamlit Page Config
# --------------------------------------------------------------------------

# Use with default page title
set_custom_page_config()

# --------------------------------------------------------------------------
# Navigation on side bar
# --------------------------------------------------------------------------
navigate()

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
    st.sidebar.text_input("HuggingFace API Key", type="password", key="huggingface_key")

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
        if st.session_state.huggingface_key:
            vectorizer_integration_keys["X-HuggingFace-Api-Key"] = st.session_state.huggingface_key

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
                st.session_state.active_huggingface_key = st.session_state.huggingface_key
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
                st.session_state.active_huggingface_key = st.session_state.huggingface_key
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
                    st.session_state.active_huggingface_key = st.session_state.huggingface_key
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

# Essential run for the first time
update_side_bar_labels()

# --------------------------------------------------------------------------
# Main Page Content (Cluster Operations)
# --------------------------------------------------------------------------
st.markdown("Aggregation & Read Data is cached in the session state for an hour - to clear the cache either clear the cache in the Streamlit Developer Options or Disconnect then reconnect again.")

# --------------------------------------------------------------------------
# Buttons (calls a function)
# --------------------------------------------------------------------------
col1, col2, col3 = st.columns([1, 1, 1])
col4, col5, col6 = st.columns([1, 1, 1])
col7, col8, col9 = st.columns([1, 1, 1])

# Dictionary: button name => action function
button_actions = {
    "nodes": action_nodes_and_shards,
    "aggregate_collections_tenants": action_aggregate_collections_tenants,
    "collection_properties": action_collection_schema,
    "collections_configuration": action_collections_configuration,
    "statistics": action_statistics,
    "metadata": action_metadata,
    "diagnose": action_diagnose
}

with col1:
    if st.button("Aggregate Collections & Tenants", width="stretch"):
        st.session_state["active_button"] = "aggregate_collections_tenants"

with col2:
    if st.button("Collection Properties", width="stretch"):
        st.session_state["active_button"] = "collection_properties"

with col3:
    if st.button("Collections Configuration", width="stretch"):
        st.session_state["active_button"] = "collections_configuration"

with col4:
    if st.button("Nodes & Shards", width="stretch"):
        st.session_state["active_button"] = "nodes"

with col5:
    if st.button("Raft Statistics", width="stretch"):
        st.session_state["active_button"] = "statistics"

with col6:
    if st.button("Metadata",width="stretch"):
        st.session_state["active_button"] = "metadata"

with col7:
    if st.button("Diagnose", width="stretch"):
        st.session_state["active_button"] = "diagnose"

# --------------------------------------------------------------------------
# Execute the active button's action
# --------------------------------------------------------------------------
active_button = st.session_state.get("active_button")
if active_button and st.session_state.get("client_ready"):
    action_fn = button_actions.get(active_button)
    if action_fn:
        action_fn()
    else:
        st.warning("No action mapped for this button. Please report this issue to Mohamed Shahin in Weaviate Community Slack.")
elif not st.session_state.get("client_ready"):
    st.warning("Connect to Weaviate first!")
