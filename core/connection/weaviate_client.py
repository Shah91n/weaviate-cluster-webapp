"""Weaviate client initialization service layer."""

import logging
from core.connection.weaviate_connection_manager import get_weaviate_manager

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
	custom_secure=False,
) -> tuple[bool, dict]:
	"""
	Initialize Weaviate connection via singleton manager.
	
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
	tuple[bool, dict]
		(success, details)
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
			endpoint = manager.get_endpoint()
			client = manager.client
			server_version = "N/A"

			# Get version info
			try:
				metadata = client.get_meta()
				server_version = metadata.get("version", "N/A")
			except Exception as e:
				logger.warning(f"Could not retrieve version info: {e}")

			logger.info("Weaviate connection successful")
			return True, {
				"client_ready": manager.is_ready(),
				"endpoint": endpoint,
				"server_version": server_version,
			}
		else:
			return False, {
				"client_ready": False,
				"error": "Failed to establish connection to Weaviate",
			}

	except Exception as e:
		logger.error(f"Connection Error: {e}")
		return False, {
			"client_ready": False,
			"error": f"Connection Error: {e}",
		}


def disconnect_weaviate() -> tuple[bool, str]:
	"""Disconnect from Weaviate."""
	try:
		logger.info("Disconnecting from Weaviate")
		manager = get_weaviate_manager()
		manager.disconnect()
		logger.info("Weaviate disconnected and session cleared")
		return True, "Disconnected"
	except Exception as e:
		logger.error(f"Error during disconnect: {e}")
		return False, f"Error during disconnect: {e}"
