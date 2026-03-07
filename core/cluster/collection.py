import pandas as pd
import logging
import requests
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)


# Get collections count
def get_collectios_count():
	logger.info("get_collectios_count() called")
	try:
		client = get_weaviate_client()
		collections = client.collections.list_all()
		collection_count = len(collections)
		return collection_count
	except Exception as e:
		logger.error(f"Error getting collections count: {e}")
		return 0


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
		# track empty collections and tenants
		empty_collections_list = []
		empty_tenants_details = []

		if collections:
			# Store the actual number of collections
			collection_count = len(collections)
			for collection_name in collections:
				collection_row = {"Collection": collection_name, "Count": "", "Tenant": "", "Tenant Count": ""}
				result_data.append(collection_row)
				collection = client.collections.use(collection_name)
				try:
					# Attempt to get tenants for the collection (check if multi-tenancy is enabled)
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


# Get collection schema
def get_schema():
	logger.info("get_schema() called")
	try:
		client = get_weaviate_client()
		response = client.collections.list_all(simple=False)
		return response if response else {}
	except Exception as e:
		logger.error(f"Error getting schema: {e}")
		return {}


# Get the configuration of a collection from the Weaviate instance.
def fetch_collection_config(cluster_url, api_key, collection_name):
	logger.info(f"fetch_collection_config() called for collection: {collection_name}")
	headers = {"Authorization": f"Bearer {api_key}"}
	endpoint = f"{cluster_url}/v1/schema/"
	try:
		response = requests.get(endpoint, headers=headers)
	except requests.RequestException as e:
		return {"error": f"Error fetching schema: {e}"}

	if response.status_code == 200:
		schema = response.json().get("classes", [])
		for cls in schema:
			if cls.get("class") == collection_name:
				return cls
	return {"error": f"Error fetching schema: {response.status_code} - {response.text}"}


# Process the collection configuration to extract relevant information.
def process_collection_config(config):
	logger.info("process_collection_config() called")
	if not config:
		return {"error": "No configuration available"}

	# Base keys to display for both scenarios (single vector and named vectors)
	keys_to_display = {
		"Inverted Index Config": config.get("invertedIndexConfig", {}),
		"Multi-Tenancy Config": config.get("multiTenancyConfig", {}),
		"Replication Config": config.get("replicationConfig", {}),
		"Sharding Config": config.get("shardingConfig", {}),
	}

	# Dynamically add all module configurations as separate sections
	module_configs = config.get("moduleConfig", {})
	for mod_name, mod_conf in module_configs.items():
		# Create a distinct section name for each module configuration
		keys_to_display[f"{mod_name}"] = mod_conf

	# Handle single vector configuration scenario
	if "vectorIndexConfig" in config and "vectorizer" in config:
		keys_to_display["vectorIndexType"] = config.get("vectorIndexType", {})
		keys_to_display["Vector Index Config"] = config.get("vectorIndexConfig", {})

	# Handle named vector configurations scenario
	if "vectorConfig" in config:
		named_vectors_info = {}
		for vector_name, vector_details in config["vectorConfig"].items():
			# Gather details for each named vector dynamically
			info = {
				"Vector Index Type": vector_details.get("vectorIndexType"),
				"Vector Index Config": vector_details.get("vectorIndexConfig", {}),
				"Vectorizer": vector_details.get("vectorizer", {})
			}
			named_vectors_info[vector_name] = info
		keys_to_display["Named Vectors Config"] = named_vectors_info

	return keys_to_display
