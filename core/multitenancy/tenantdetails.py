import logging
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

# Get tenants from a collection.
def get_tenant_details(collection):
	logger.info(f"get_tenant_details() called for collection: {collection}")
	client = get_weaviate_client()
	col = client.collections.use(collection)
	tenants = col.tenants.get()
	return tenants

# This function aggregates the tenant states and counts the number of tenants in each state.
def aggregate_tenant_states(tenants):
	logger.info(f"aggregate_tenant_states() called")
	tenant_states = {}
	for tenant_id, tenant in tenants.items():
		state = tenant.activityStatusInternal.name
		if state not in tenant_states:
			tenant_states[state] = 0
		tenant_states[state] += 1
	return tenant_states

# Get multi-tenancy collections only
# If multiTenancyConfig exists and 'enabled' is True, add the collection to the list
def get_multitenancy_collections(schema):
	print("get_multitenancy_collections() called")
	enabled_collections = []
	for collection in schema.get('classes', []):
		collection_name = collection.get('class', 'Unknown Class')
		multi_tenancy_config = collection.get('multiTenancyConfig', None)
		if multi_tenancy_config and multi_tenancy_config.get('enabled', False):
			enabled_collections.append({
				'collection_name': collection_name,
				'multiTenancyConfig': multi_tenancy_config
			})

	return enabled_collections
