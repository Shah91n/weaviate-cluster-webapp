# Delete collections and tenants from collections in Weaviate
import logging
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

def delete_all_collections():
	logger.info("delete_all_collections() called")
	try:
		client = get_weaviate_client()
		client.collections.delete_all()
		return True, "Successfully deleted all collections."
	except Exception as e:
		logger.error(f"Error deleting all collections: {str(e)}")
		return False, f"Error deleting all collections: {str(e)}"

def delete_collections(collection_names):
	logger.info(f"delete_collections() called with: {collection_names}")
	try:
		client = get_weaviate_client()
		client.collections.delete(collection_names)
		return True, f"Successfully deleted collections: {', '.join(collection_names if isinstance(collection_names, list) else [collection_names])}"
	except Exception as e:
		logger.error(f"Error deleting collections: {str(e)}")
		return False, f"Error deleting collections: {str(e)}"

def delete_tenants_from_collection(collection_name, tenant_names):
	logger.info(f"delete_tenants_from_collection() called with collection: {collection_name} and tenants: {tenant_names}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		collection.tenants.remove(tenant_names)
		return True, f"Successfully deleted tenants: {', '.join(tenant_names)} from collection {collection_name}"
	except Exception as e:
		logger.error(f"Error deleting tenants from collection {collection_name}: {str(e)}")
		return False, f"Error deleting tenants from collection {collection_name}: {str(e)}"
