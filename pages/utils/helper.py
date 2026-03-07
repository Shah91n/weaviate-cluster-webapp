import streamlit as st
import logging
from core.connection.weaviate_connection_manager import get_weaviate_manager

logger = logging.getLogger(__name__)

# Update the side bar labels on the fly
def update_side_bar_labels():
    logger.info("update_side_bar_labels called")
    manager = get_weaviate_manager()
    
    if not manager.is_ready():
        st.warning("Please Establish a connection to Weaviate on the side bar")
    else:
        st.sidebar.info("Connection Status: ✅")
        st.sidebar.info(f"Current Connected Endpoint: {manager.get_endpoint()}")
        if st.session_state.get("server_version"):
            st.sidebar.info(f"Server Version: {st.session_state.get('server_version', 'N/A')}")

# Clear the session state
def clear_session_state():
    logger.info("clear_session_state called")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()
    st.rerun()
