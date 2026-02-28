"""
Weaviate Client Initialization - Streamlit Integration Layer

This module bridges the singleton connection manager with Streamlit's session state.
It handles connection initialization and session state updates.
"""

import logging
import streamlit as st
from utils.connection.weaviate_connection_manager import get_weaviate_manager

logger = logging.getLogger(__name__)


def initialize_weaviate_connection(
	cluster_endpoint=None,
	cluster_api_key=None,
	use_local=False,
	vectorizer_integration_keys=None,
	use_custom=False,
	http_host_endpoint=None,
	http_port_endpoint=None,
	grpc_host_endpoint=None,
	grpc_port_endpoint=None,
	custom_secure=False
) -> bool:
	"""
	Initialize Weaviate connection via singleton manager and update session state.
	
	Parameters
	----------
	cluster_endpoint : str, optional
		Cloud cluster URL
	cluster_api_key : str, optional
		API key for authentication
	use_local : bool
		Connect to local Weaviate instance
	vectorizer_integration_keys : dict, optional
		API keys for vectorizers
	use_custom : bool
		Connect to custom Weaviate instance
	http_host_endpoint : str, optional
		Custom HTTP host
	http_port_endpoint : int, optional
		Custom HTTP port
	grpc_host_endpoint : str, optional
		Custom gRPC host
	grpc_port_endpoint : int, optional
		Custom gRPC port
	custom_secure : bool
		Use secure connection
	
	Returns
	-------
	bool
		True if connection successful, False otherwise
	"""
	try:
		logger.info("Initializing Weaviate connection")
		manager = get_weaviate_manager()

		# Connect via singleton manager
		success = manager.connect(
			cluster_url=cluster_endpoint,
			api_key=cluster_api_key,
			vectorizer_keys=vectorizer_integration_keys,
			use_local=use_local,
			http_host=http_host_endpoint,
			http_port=http_port_endpoint,
			grpc_host=grpc_host_endpoint,
			grpc_port=grpc_port_endpoint,
			use_secure=custom_secure,
		)

		if success:
			# Update session state with connection info
			client = manager.client
			st.session_state.client_ready = manager.is_ready()
			st.session_state.active_endpoint = manager.get_endpoint()

			# Get version info
			try:
				metadata = client.get_meta()
				st.session_state.server_version = metadata.get("version", "N/A")
			except Exception as e:
				logger.warning(f"Could not retrieve version info: {e}")
				st.session_state.server_version = "N/A"

			logger.info("Weaviate connection successful")
			return True
		else:
			st.sidebar.error("Failed to establish connection to Weaviate")
			st.session_state.client_ready = False
			return False

	except Exception as e:
		logger.error(f"Connection Error: {e}")
		st.sidebar.error(f"Connection Error: {e}")
		st.session_state.client_ready = False
		return False


def disconnect_weaviate():
	"""Disconnect from Weaviate and clear session state"""
	try:
		logger.info("Disconnecting from Weaviate")
		manager = get_weaviate_manager()
		manager.disconnect()
		
		# Clear session state
		for key in list(st.session_state.keys()):
			del st.session_state[key]
		
		logger.info("Weaviate disconnected and session cleared")
	except Exception as e:
		logger.error(f"Error during disconnect: {e}")
