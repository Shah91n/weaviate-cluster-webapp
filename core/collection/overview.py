import pandas as pd
import logging
from core.collection.vector_index import HFRESH, describe_vector_indexes
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)


def _empty_aggregate(error=None):
	"""The zero-state result. aggregate_collections() always returns this shape."""
	result = {
		"collection_count": 0,
		"total_tenants_count": 0,
		"empty_collections": 0,
		"empty_tenants": 0,
		"total_objects_regular": 0,
		"total_objects_multitenancy": 0,
		"total_objects_combined": 0,
		"result_df": pd.DataFrame(),
		"empty_collections_list": [],
		"empty_tenants_details": [],
	}
	if error is not None:
		result["error"] = error
	return result


# Aggregate collections. Always returns a dict — never None, which the cluster page
# used to receive when the cluster reported no collections.
def aggregate_collections():
	logger.info("aggregate_collections() called")
	try:
		client = get_weaviate_client()
		collections = client.collections.list_all()
		total_tenants_count = 0
		result_data = []
		empty_collections = 0
		empty_tenants = 0
		total_objects_regular = 0
		total_objects_multitenancy = 0
		empty_collections_list = []
		empty_tenants_details = []

		if collections:
			collection_count = len(collections)
			for collection_name in collections:
				collection_row = {"Collection": collection_name, "Count": "", "Tenant": "", "Object Count": ""}
				result_data.append(collection_row)
				collection = client.collections.use(collection_name)
				try:
					tenants = collection.tenants.get()

					if tenants:
						tenant_count = len(tenants)
						total_tenants_count += tenant_count
						collection_tenant_total = 0

						for tenant_name, tenant in tenants.items():
							try:
								tenant_collection = collection.with_tenant(tenant_name)
								objects_count = tenant_collection.aggregate.over_all(total_count=True).total_count
								collection_tenant_total += objects_count
								if objects_count == 0:
									empty_tenants += 1
									empty_tenants_details.append({
										"Collection": collection_name,
										"Tenant": tenant_name,
										"Count": 0
									})
								tenant_row = {"Collection": "", "Count": "", "Tenant": tenant_name, "Object Count": objects_count}
								result_data.append(tenant_row)
							except Exception as e_inner:
								logger.error(f"Error getting tenant count: {e_inner}")
								tenant_row = {"Collection": "", "Count": "", "Tenant": tenant_name, "Object Count": f"ERROR: {e_inner}"}
								result_data.append(tenant_row)

						total_objects_multitenancy += collection_tenant_total

					else:
						objects_count = collection.aggregate.over_all(total_count=True).total_count
						collection_row["Count"] = objects_count
						if objects_count == 0:
							empty_collections += 1
							empty_collections_list.append({
								"Collection": collection_name,
								"Count": 0
							})
						total_objects_regular += objects_count

				except Exception as e:
					if "multi-tenancy is not enabled" in str(e):
						objects_count = collection.aggregate.over_all(total_count=True).total_count
						collection_row["Count"] = objects_count
						if objects_count == 0:
							empty_collections += 1
							empty_collections_list.append({
								"Collection": collection_name,
								"Count": 0
							})
						total_objects_regular += objects_count
					else:
						logger.error(f"Error processing collection {collection_name}: {e}")

			result_df = pd.DataFrame(result_data)

			return {
				"collection_count": collection_count,
				"total_tenants_count": total_tenants_count,
				"empty_collections": empty_collections,
				"empty_tenants": empty_tenants,
				"total_objects_regular": total_objects_regular,
				"total_objects_multitenancy": total_objects_multitenancy,
				"total_objects_combined": total_objects_regular + total_objects_multitenancy,
				"result_df": result_df,
				"empty_collections_list": empty_collections_list,
				"empty_tenants_details": empty_tenants_details
			}

		return _empty_aggregate()
	except Exception as e:
		logger.error(f"Error in aggregate_collections: {e}")
		return _empty_aggregate(error=f"Failed to aggregate collections: {e}")


# List all collections. Raises on failure rather than returning an empty list, so a
# permissions or connection error is never displayed as "no collections".
def list_collections():
	logger.info("list_collections() called")
	try:
		client = get_weaviate_client()
		collections = client.collections.list_all()
		if not collections:
			return []
		if hasattr(collections, "keys"):
			return list(collections.keys())
		return list(collections)
	except Exception as e:
		logger.error(f"Error listing collections: {e}")
		raise Exception(f"Failed to list collections: {e}")


# Get collection schema (full config, simple=False)
def get_schema():
	logger.info("get_schema() called")
	try:
		client = get_weaviate_client()
		response = client.collections.list_all(simple=False)
		return response if response else {}
	except Exception as e:
		logger.error(f"Error getting schema: {e}")
		raise Exception(f"Failed to load schema: {e}")


# Get the full configuration of a single collection using the Weaviate Python client SDK.
def fetch_collection_config(collection_name):
	logger.info(f"fetch_collection_config() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		return collection.config.get()
	except Exception as e:
		logger.error(f"Error fetching collection config for '{collection_name}': {e}")
		raise Exception(f"Failed to load configuration for '{collection_name}': {e}")


def _display_value(value):
	"""Render an SDK config value as a readable string."""
	if value is None:
		return "None"
	return str(getattr(value, "value", value))


def _as_display_dict(params):
	return {k: _display_value(v) for k, v in params.items() if v is not None}


def _describe_index_for_display(info):
	"""Turn one VectorIndexInfo into the ordered sections the config page renders."""
	sections = {"Vector Index Type": info.index_type}

	if info.vectorizer:
		sections["Vectorizer"] = info.vectorizer

	index_params = _as_display_dict(info.params)
	if index_params:
		sections["Vector Index Config"] = index_params

	# A dynamic index keeps its real settings — and its quantizers — one level down.
	for scope, params in info.sub_indexes.items():
		scope_params = _as_display_dict(params)
		if scope_params:
			sections[f"Sub-Index: {scope}"] = scope_params

	for quantizer in info.quantizers:
		sections[f"Quantizer: {quantizer.label}"] = _as_display_dict(quantizer.params)

	if not info.quantizers:
		sections["Compression"] = "none"
	elif info.index_type == HFRESH:
		sections["Compression"] = f"{info.compression_summary} (built in, always on)"
	else:
		sections["Compression"] = info.compression_summary

	return sections


# Process a SDK CollectionConfig object into a displayable sections dict.
def process_collection_config(config):
	logger.info("process_collection_config() called")
	if config is None:
		return {}

	result = {}

	# Inverted Index Config
	inv = getattr(config, "inverted_index_config", None)
	if inv:
		inv_dict = {}
		cleanup = getattr(inv, "cleanup_interval_seconds", None)
		if cleanup is not None:
			inv_dict["cleanup_interval_seconds"] = cleanup
		bm25 = getattr(inv, "bm25", None)
		if bm25:
			inv_dict["bm25_b"] = getattr(bm25, "b", None)
			inv_dict["bm25_k1"] = getattr(bm25, "k1", None)
		stopwords = getattr(inv, "stopwords", None)
		if stopwords:
			inv_dict["stopwords_preset"] = str(getattr(stopwords, "preset", ""))
			additions = getattr(stopwords, "additions", [])
			removals = getattr(stopwords, "removals", [])
			if additions:
				inv_dict["stopwords_additions"] = str(additions)
			if removals:
				inv_dict["stopwords_removals"] = str(removals)
		result["Inverted Index Config"] = {k: v for k, v in inv_dict.items() if v is not None}

	# Multi-Tenancy Config
	mt = getattr(config, "multi_tenancy_config", None)
	if mt:
		result["Multi-Tenancy Config"] = {
			"enabled": getattr(mt, "enabled", False),
			"auto_tenant_creation": getattr(mt, "auto_tenant_creation", False),
			"auto_tenant_activation": getattr(mt, "auto_tenant_activation", False),
		}

	# Replication Config
	repl = getattr(config, "replication_config", None)
	if repl:
		result["Replication Config"] = {
			"factor": getattr(repl, "factor", 1),
			"async_enabled": getattr(repl, "async_enabled", False),
			"deletion_strategy": str(getattr(repl, "deletion_strategy", "")),
		}

	# Sharding Config
	sharding = getattr(config, "sharding_config", None)
	if sharding:
		sharding_dict = {}
		for attr in ("virtual_per_physical", "desired_count", "actual_count", "actual_virtual_count", "key", "strategy", "function"):
			val = getattr(sharding, attr, None)
			if val is not None:
				sharding_dict[attr] = val
		if sharding_dict:
			result["Sharding Config"] = sharding_dict

	# Vectors — covers named vectors and the legacy single vector alike, and reports the
	# real index type (hnsw / flat / dynamic / hfresh) rather than assuming HNSW.
	indexes = describe_vector_indexes(config)
	if indexes:
		result["Vectors"] = {info.name: _describe_index_for_display(info) for info in indexes}

	return result
