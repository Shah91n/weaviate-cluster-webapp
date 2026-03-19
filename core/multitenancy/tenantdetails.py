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
	logger.info("aggregate_tenant_states() called")
	tenant_states = {}
	for tenant_id, tenant in tenants.items():
		state = tenant.activityStatusInternal.name
		if state not in tenant_states:
			tenant_states[state] = 0
		tenant_states[state] += 1
	return tenant_states

