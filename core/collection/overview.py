import pandas as pd
import logging
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)



# Aggregate collections.
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
				collection_row = {"Collection": collection_name, "Count": "", "Tenant": "", "Tenant Count": ""}
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
								tenant_row = {"Collection": "", "Count": "", "Tenant": tenant_name, "Tenant Count": objects_count}
								result_data.append(tenant_row)
							except Exception as e_inner:
								logger.error(f"Error getting tenant count: {e_inner}")
								tenant_row = {"Collection": "", "Count": "", "Tenant": tenant_name, "Tenant Count": f"ERROR: {e_inner}"}
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
	except Exception as e:
		logger.error(f"Error in aggregate_collections: {e}")
		return {
			"collection_count": 0,
			"total_tenants_count": 0,
			"empty_collections": 0,
			"empty_tenants": 0,
			"total_objects_regular": 0,
			"total_objects_multitenancy": 0,
			"total_objects_combined": 0,
			"result_df": pd.DataFrame(),
			"empty_collections_list": [],
			"empty_tenants_details": []
		}


# List all collections
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
		return []


# Get collection schema (full config, simple=False)
def get_schema():
	logger.info("get_schema() called")
	try:
		client = get_weaviate_client()
		response = client.collections.list_all(simple=False)
		return response if response else {}
	except Exception as e:
		logger.error(f"Error getting schema: {e}")
		return {}


# Get the full configuration of a single collection using the Weaviate Python client SDK.
def fetch_collection_config(collection_name):
	logger.info(f"fetch_collection_config() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		return collection.config.get()
	except Exception as e:
		logger.error(f"Error fetching collection config for '{collection_name}': {e}")
		return None


def _vic_to_dict(vic):
	"""Convert a _VectorIndexConfigHNSW object to a flat display dict."""
	if vic is None:
		return {}
	d = {
		"distance_metric": str(getattr(vic, "distance_metric", "")),
		"ef": getattr(vic, "ef", None),
		"ef_construction": getattr(vic, "ef_construction", None),
		"max_connections": getattr(vic, "max_connections", None),
		"dynamic_ef_min": getattr(vic, "dynamic_ef_min", None),
		"dynamic_ef_max": getattr(vic, "dynamic_ef_max", None),
		"dynamic_ef_factor": getattr(vic, "dynamic_ef_factor", None),
		"flat_search_cutoff": getattr(vic, "flat_search_cutoff", None),
		"vector_cache_max_objects": getattr(vic, "vector_cache_max_objects", None),
		"filter_strategy": str(getattr(vic, "filter_strategy", "")),
		"cleanup_interval_seconds": getattr(vic, "cleanup_interval_seconds", None),
		"skip": getattr(vic, "skip", None),
	}
	quantizer = getattr(vic, "quantizer", None)
	if quantizer is not None:
		q_type = type(quantizer).__name__.lstrip("_").replace("Config", "")
		d["quantizer_type"] = q_type
		# Dynamically read all public fields on the quantizer object
		q_attrs = vars(quantizer) if hasattr(quantizer, "__dict__") else {}
		for attr, val in q_attrs.items():
			if attr.startswith("_"):
				continue
			# Encoder is a nested object — flatten it separately below
			if attr == "encoder":
				continue
			d[f"quantizer_{attr}"] = val
		# Flatten encoder sub-object dynamically if present
		encoder = getattr(quantizer, "encoder", None)
		if encoder is not None:
			enc_attrs = vars(encoder) if hasattr(encoder, "__dict__") else {}
			for attr, val in enc_attrs.items():
				if not attr.startswith("_"):
					d[f"quantizer_encoder_{attr}"] = val
	return {k: str(v) if v is not None else "None" for k, v in d.items() if k in d}


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

	# Named vectors
	vector_config = getattr(config, "vector_config", None)
	if vector_config:
		named_vecs = {}
		for vec_name, named_vec in vector_config.items():
			vec_info = {}

			vectorizer_obj = getattr(named_vec, "vectorizer", None)
			if vectorizer_obj:
				vec_key = getattr(getattr(vectorizer_obj, "vectorizer", None), "value", str(getattr(vectorizer_obj, "vectorizer", "unknown")))
				vec_info["Vectorizer"] = {
					vec_key: getattr(vectorizer_obj, "model", {}) or {}
				}
				src = getattr(vectorizer_obj, "source_properties", None)
				if src:
					vec_info["Vectorizer"][vec_key]["source_properties"] = str(src)

			vic = getattr(named_vec, "vector_index_config", None)
			if vic:
				vec_info["Vector Index Type"] = "hnsw"
				vec_info["Vector Index Config"] = _vic_to_dict(vic)

			named_vecs[vec_name] = vec_info
		result["Named Vectors Config"] = named_vecs

	elif getattr(config, "vector_index_config", None):
		# Single vector
		vic = config.vector_index_config
		result["vectorIndexType"] = "hnsw"
		result["Vector Index Config"] = _vic_to_dict(vic)

		vc = getattr(config, "vectorizer_config", None)
		if vc:
			vec_key = getattr(getattr(vc, "vectorizer", None), "value", str(getattr(vc, "vectorizer", "unknown")))
			result["Vectorizer Config"] = {
				vec_key: getattr(vc, "model", {}) or {}
			}

	return result
