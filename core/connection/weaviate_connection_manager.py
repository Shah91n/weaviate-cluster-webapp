"""
Weaviate Connection Manager - Thread-Safe Singleton Pattern
===========================================================

This module provides a singleton Weaviate client manager for consistent connection
management across the entire application. ONE long-lived client instance is created
and reused throughout the application lifetime.

WHY SINGLETON?
The Weaviate Python client uses httpx for HTTP communication and maintains
a persistent connection to the cluster. Creating multiple clients causes unnecessary
connection setup/teardown overhead. Weaviate recommends ONE long-lived client instance
per application.

ARCHITECTURE:
- One client instance per application lifetime
- httpx (HTTP client) handles persistent connection via connection pooling
- Concurrent requests are multiplexed over the single HTTP connection
- Lazy initialization of async client on first use
- Thread-safe singleton pattern with lock
"""

import logging
import threading
import atexit
import weaviate
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeaviateConnectionManager:
    """
    Thread-safe singleton manager that maintains ONE long-lived Weaviate client connection.
    
    Architecture:
    - One client instance per application lifetime
    - httpx (HTTP client) handles persistent connection via connection pooling
    - Concurrent requests are multiplexed over the single HTTP connection
    - Thread-safe initialization with lock
    
    RECOMMENDATION: Use get_weaviate_manager() module-level function instead of
    directly instantiating this class.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Thread-safe singleton instantiation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the singleton (only once)"""
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._cluster_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._headers: Dict[str, str] = {}
        self._sync_client: Optional[Any] = None
        self._async_client: Optional[Any] = None
        self._initialized = True
        
        # Register cleanup on application shutdown
        atexit.register(self.disconnect)
        
        logger.info("WeaviateConnectionManager singleton initialized")

    def connect(
        self,
        cluster_url: Optional[str] = None,
        api_key: Optional[str] = None,
        vectorizer_keys: Optional[Dict[str, str]] = None,
        use_local: bool = False,
        http_host: Optional[str] = None,
        http_port: Optional[int] = None,
        grpc_host: Optional[str] = None,
        grpc_port: Optional[int] = None,
        use_secure: bool = False,
    ) -> bool:
        """
        Connect to Weaviate with given parameters.
        
        Parameters
        ----------
        cluster_url : str, optional
            Cloud cluster URL (e.g., https://cluster-name.weaviate.network)
        api_key : str, optional
            API key for authentication
        vectorizer_keys : dict, optional
            Headers for vectorizer API keys (e.g., {"X-OpenAI-Api-Key": "..."})
        use_local : bool
            Connect to local Weaviate instance
        http_host : str, optional
            HTTP host for custom connection
        http_port : int, optional
            HTTP port for custom/local connection
        grpc_host : str, optional
            gRPC host for custom connection
        grpc_port : int, optional
            gRPC port for custom/local connection
        use_secure : bool
            Use HTTPS/gRPC secure connections
        
        Returns
        -------
        bool
            True if connection successful, False otherwise
        """
        try:
            # Construct cluster URL if using local/custom connection
            if use_local:
                self._cluster_url = f"http://localhost:{http_port or 8080}"
            elif http_host:
                protocol = "https" if use_secure else "http"
                self._cluster_url = f"{protocol}://{http_host}:{http_port or 8080}"
            else:
                self._cluster_url = cluster_url

            self._api_key = api_key

            # Build headers with vectorizer API keys
            self._headers = {}
            if vectorizer_keys:
                self._headers.update(vectorizer_keys)

            # Close existing connection if any
            if self._sync_client:
                try:
                    self._sync_client.close()
                    logger.info("Closed existing Weaviate client connection")
                except Exception as e:
                    logger.warning(f"Error closing existing client: {e}")

            # Create new client connection
            auth_credentials = Auth.api_key(api_key) if api_key else None

            if use_local:
                self._sync_client = weaviate.connect_to_local(
                    auth_credentials=auth_credentials,
                    port=http_port or 8080,
                    grpc_port=grpc_port or 50051,
                    skip_init_checks=True,
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=90, query=900, insert=900)
                    ),
                    headers=self._headers or None,
                )
                logger.info(f"Connected to local Weaviate instance (HTTP: {http_port}, gRPC: {grpc_port})")
            elif http_host:
                self._sync_client = weaviate.connect_to_custom(
                    http_host=http_host,
                    http_port=http_port or 8080,
                    http_secure=use_secure,
                    grpc_host=grpc_host,
                    grpc_port=grpc_port or 50051,
                    grpc_secure=use_secure,
                    auth_credentials=auth_credentials,
                    skip_init_checks=True,
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=90, query=900, insert=900)
                    ),
                    headers=self._headers or None,
                )
                logger.info(f"Connected to custom Weaviate instance at {self._cluster_url}")
            else:
                self._sync_client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=self._cluster_url,
                    auth_credentials=auth_credentials,
                    skip_init_checks=True,
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=90, query=900, insert=900)
                    ),
                    headers=self._headers or None,
                )
                logger.info(f"Connected to Weaviate Cloud cluster: {self._cluster_url}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            self._sync_client = None
            return False

    @property
    def client(self):
        """
        Return the singleton synchronous Weaviate client.
        
        This is the same client instance every time - DO NOT close it after use.
        The persistent HTTP connection (via httpx) is reused across all requests.
        
        Returns
        -------
        WeaviateClient
            The long-lived client instance
            
        Raises
        ------
        RuntimeError
            If not connected or client was closed
        """
        if self._sync_client is None:
            raise RuntimeError("Not connected to Weaviate. Call connect() first.")
        return self._sync_client

    async def get_async_client(self):
        """
        Return the singleton asynchronous Weaviate client.
        
        Lazily initializes the async client on first call. The same instance
        is returned on subsequent calls.
        
        Returns
        -------
        WeaviateAsyncClient
            The long-lived async client instance
        """
        if self._async_client is None:
            try:
                auth_credentials = Auth.api_key(self._api_key) if self._api_key else None
                self._async_client = await weaviate.use_async_with_weaviate_cloud(
                    cluster_url=self._cluster_url,
                    auth_credentials=auth_credentials,
                    headers=self._headers or None,
                    additional_config=AdditionalConfig(
                        timeout=Timeout(init=90, query=900, insert=900)
                    ),
                    skip_init_checks=False
                ).__aenter__()
                logger.info("Async Weaviate client initialized")
            except Exception as e:
                logger.error(f"Failed to create async Weaviate client: {e}")
                raise
        return self._async_client

    def is_ready(self) -> bool:
        """
        Check if Weaviate is ready to accept requests.
        
        Returns
        -------
        bool
            True if Weaviate is ready, False otherwise
        """
        try:
            if self._sync_client is None:
                return False
            return self._sync_client.is_ready()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_endpoint(self) -> str:
        """
        Get the current cluster endpoint URL.
        
        Returns
        -------
        str
            Cluster URL or empty string if not connected
        """
        return self._cluster_url or ""

    def get_api_key(self) -> str:
        """
        Get the current API key (DO NOT expose in logs).
        
        Returns
        -------
        str
            API key or empty string if not set
        """
        return self._api_key or ""

    def disconnect(self):
        """
        Close the Weaviate client connections and reset state.
        
        This should ONLY be called during application shutdown.
        DO NOT call this after individual requests.
        """
        try:
            if self._sync_client:
                self._sync_client.close()
                logger.info("Weaviate synchronous client closed")
                self._sync_client = None

            if self._async_client:
                logger.info("Weaviate asynchronous client marked for closure")
                self._async_client = None

            self._cluster_url = None
            self._api_key = None
            self._headers = {}
        except Exception as e:
            logger.error(f"Error disconnecting from Weaviate: {e}")


# Singleton instance getter
_manager_instance: Optional[WeaviateConnectionManager] = None


def get_weaviate_manager() -> WeaviateConnectionManager:
    """
    Get the singleton WeaviateConnectionManager instance.
    
    Use this to access manager methods like connect(), is_ready(), disconnect().
    
    Returns
    -------
    WeaviateConnectionManager
        The singleton manager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = WeaviateConnectionManager()
    return _manager_instance


def get_weaviate_client():
    """
    Get the singleton Weaviate client instance.
    
    This returns the SAME client instance every time. Use this client directly
    for all operations - do not close it after use.
    
    Example:
        client = get_weaviate_client()
        result = client.collections.use("products").query.fetch_objects()
        # Client remains open for next request
    
    Returns
    -------
    WeaviateClient
        The singleton client instance
        
    Raises
    ------
    RuntimeError
        If not connected to Weaviate
    """
    manager = get_weaviate_manager()
    return manager.client


async def get_async_weaviate_client():
    """
    Get the singleton async Weaviate client instance.
    
    This returns the SAME async client every time. Use this client directly
    for all async operations - do not close it after use.
    
    Lazy initialization: The async client is only created on first call.
    Subsequent calls return the same instance.
    
    Example:
        client = await get_async_weaviate_client()
        result = await client.collections.use("products").query.fetch_objects()
        # Client remains open for next request
    
    Returns
    -------
    WeaviateAsyncClient
        The singleton async client instance
    """
    manager = get_weaviate_manager()
    return await manager.get_async_client()


def close_weaviate_connection():
    """
    Close the Weaviate connection and cleanup.
    
    This should ONLY be called during application shutdown.
    The connection is automatically closed via atexit, so manual
    calls are typically unnecessary.
    """
    global _manager_instance
    if _manager_instance:
        _manager_instance.disconnect()
        _manager_instance = None
        logger.info("Weaviate connection closed and manager reset")
