import streamlit as st
import pandas as pd
from pages.utils.navigation import navigate
from pages.utils.helper import update_side_bar_labels
from core.multitenancy.tenantdetails import get_tenant_details, aggregate_tenant_states
from core.collection.overview import get_schema
from pages.utils.page_config import set_custom_page_config

#Displays UI for multi-tenancy collections.	Returns True if MT collections are found, False otherwise.
def display_multitenancy():
	schema = get_schema() 
	
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
	collection_count = len(enabled_collections)
	st.markdown(f"###### Total Number of Multi Tenancy Collections in the list: **{collection_count}**\n")
	collection_names = [collection['collection_name'] for collection in enabled_collections]
	selected_collection_name = st.selectbox(
		"Select a MT Collection",
		collection_names,
	)
	st.session_state["selected_collection_name"] = selected_collection_name

	if st.button("Get Multi Tenancy Configuration"):
		selected_collection = next((collection for collection in st.session_state["enabled_collections"] if collection['collection_name'] == selected_collection_name), None)
		if selected_collection:
			multi_tenancy_config = selected_collection['multiTenancyConfig']
			multi_tenancy_df = pd.DataFrame([multi_tenancy_config])
			st.dataframe(multi_tenancy_df.astype(str), width="stretch")
		else:
			st.error("Failed to find the selected collection in the available collections.")
	return True

def tenant_details():
	if st.button("Get Tenant Details"):
		selected_collection_name = st.session_state.get("selected_collection_name")
		tenants = get_tenant_details(selected_collection_name)
		aggregated_states = aggregate_tenant_states(tenants)
		tenant_data = []
		for tenant_id, tenant in tenants.items():
			tenant_data.append({
				'Tenant ID': tenant_id,
				'Name': tenant.name,
				'Activity Status Internal': tenant.activityStatusInternal.name,
				'Activity Status': tenant.activityStatus.name
			})
		st.dataframe(pd.DataFrame(aggregated_states.items(), columns=['Activity Status', 'Count']), width="stretch")
		df = pd.DataFrame(tenant_data)
		st.dataframe(df.astype(str), width="stretch")

def main():

	set_custom_page_config(page_title="Multi Tenancy")

	navigate()

	if st.session_state.get("client_ready"):
		update_side_bar_labels()
		found_mt_collections = display_multitenancy()
		if found_mt_collections:
			tenant_details()
	else:
		st.warning("Please Establish a connection to Weaviate in Cluster page!")

if __name__ == "__main__":
	main()
