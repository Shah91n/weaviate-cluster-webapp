import streamlit as st
import pandas as pd
from core.multitenancy.tenantdetails import get_tenant_details, aggregate_tenant_states
from core.collection.overview import get_schema
from core.collection.vector_index import describe_vector_indexes
from pages.utils import ui
from pages.utils.page_config import page_header

#Displays UI for multi-tenancy collections.	Returns True if MT collections are found, False otherwise.
def display_multitenancy():
	schema = ui.load(get_schema, error_prefix="Could not load schema")
	
	if isinstance(schema, dict) and 'error' in schema:
		st.error(schema['error'])
		return False

	# Get collections with multi-tenancy enabled.
	# The schema from client.collections.list_all() is a dict of collection names to config objects.
	enabled_collections = []
	for name, config in schema.items():
		if hasattr(config, 'multi_tenancy_config') and config.multi_tenancy_config and config.multi_tenancy_config.enabled:
			# Convert the config object to a dict for display in a DataFrame.
			mt_config_dict = {
				'enabled': config.multi_tenancy_config.enabled,
				'autoTenantCreation': config.multi_tenancy_config.auto_tenant_creation,
				'autoTenantActivation': config.multi_tenancy_config.auto_tenant_activation
			}
			enabled_collections.append({
				'collection_name': name,
				'multiTenancyConfig': mt_config_dict
			})

	if not enabled_collections:
		st.warning("No collections with enabled multi-tenancy found.")
		st.session_state["enabled_collections"] = [] # Ensure session state is cleared/reset
		return False

	# Always update session state with the fresh list of collections.
	st.session_state["enabled_collections"] = enabled_collections
	# Show a selectbox for the user to choose a collection
	ui.metric_row([("Multi-Tenancy Collections", len(enabled_collections))])
	collection_names = [collection['collection_name'] for collection in enabled_collections]
	selected_collection_name = st.selectbox("MT Collection", collection_names)
	st.session_state["selected_collection_name"] = selected_collection_name

	if st.button("Get Multi Tenancy Configuration", width="stretch"):
		st.session_state["mt_config_shown"] = selected_collection_name

	if st.session_state.get("mt_config_shown") != selected_collection_name:
		return True

	selected_collection = next(
		(c for c in st.session_state["enabled_collections"] if c['collection_name'] == selected_collection_name),
		None,
	)
	if not selected_collection:
		st.error("Failed to find the selected collection in the available collections.")
		return True

	ui.section("Multi-Tenancy Config")
	ui.kv_table(selected_collection['multiTenancyConfig'])

	# Multi-tenant collections often use a dynamic index, whose type and compression are
	# easy to miss — surface both here rather than only on the Cluster config screen.
	config = schema.get(selected_collection_name)
	indexes = describe_vector_indexes(config)
	ui.section("Vector Index")
	if not indexes:
		st.caption("No vector configuration found.")
	for info in indexes:
		ui.metric_row([
			("Vector", info.name),
			("Vector Index Type", info.index_type),
			("Compression", info.compression_summary),
		])
	return True


def tenant_details():
	if st.button("Get Tenant Details", width="stretch"):
		st.session_state["tenant_details_shown"] = st.session_state.get("selected_collection_name")

	selected_collection_name = st.session_state.get("selected_collection_name")
	if st.session_state.get("tenant_details_shown") != selected_collection_name:
		return

	tenants = get_tenant_details(selected_collection_name)
	aggregated_states = aggregate_tenant_states(tenants)
	tenant_data = [
		{
			'Tenant ID': tenant_id,
			'Name': tenant.name,
			'Activity Status Internal': tenant.activityStatusInternal.name,
			'Activity Status': tenant.activityStatus.name,
		}
		for tenant_id, tenant in tenants.items()
	]

	ui.section("Tenant States")
	ui.metric_row([("Tenants", len(tenant_data))] + [(str(k), int(v)) for k, v in aggregated_states.items()])
	ui.data_table(pd.DataFrame(tenant_data), "No tenants found.")


def main():
	page_header("Multi Tenancy")
	ui.require_connection()

	found_mt_collections = display_multitenancy()
	if found_mt_collections:
		tenant_details()


main()
