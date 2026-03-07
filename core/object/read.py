import logging
from typing import Any, Dict, List, Optional

from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)


def get_tenant_names(collection_name):
	logger.info(f"get_tenant_names() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		tenants = collection.tenants.get()
		return [tenant.name for tenant in tenants.values()] if tenants else []
	except Exception as error:
		if "multi-tenancy is not enabled" in str(error).lower():
			return []
		logger.error(f"Error retrieving tenants: {error}")
		return []


def _get_collection(collection_name: str, tenant_name: Optional[str] = None):
	client = get_weaviate_client()
	collection = client.collections.use(collection_name)
	if tenant_name:
		collection = collection.with_tenant(tenant_name)
	return collection


def _item_to_dict(item, include_vector: bool) -> Dict[str, Any]:
	obj = {
		"uuid": str(item.uuid),
	}
	if getattr(item, "properties", None):
		obj.update(item.properties)
	if include_vector:
		obj["vector"] = getattr(item, "vector", None)
	return obj


def read_objects_batch(
	collection_name: str,
	tenant_name: Optional[str] = None,
	limit: Optional[int] = 1000,
	include_vector: bool = True,
) -> List[Dict[str, Any]]:
	collection = _get_collection(collection_name, tenant_name)

	objects: List[Dict[str, Any]] = []
	for item in collection.iterator(include_vector=include_vector):
		objects.append(_item_to_dict(item, include_vector))
		if limit is not None and len(objects) >= limit:
			break
	return objects
