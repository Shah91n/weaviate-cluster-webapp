import streamlit as st
from pages.utils.navigation import navigate
from pages.utils.helper import update_side_bar_labels
from core.collection.overview import list_collections
from core.object.read import get_tenant_names
from core.collection.delete import delete_collections, delete_tenants_from_collection, delete_all_collections
from pages.utils.page_config import set_custom_page_config

def initialize_session_state():
	"""Initialize session state variables"""
	if "selected_collections" not in st.session_state:
		st.session_state.selected_collections = set()
	if "selected_tenants" not in st.session_state:
		st.session_state.selected_tenants = {} 
	if "collections_list" not in st.session_state:
		st.session_state.collections_list = []
	if "mt_collections" not in st.session_state:
		st.session_state.mt_collections = {} 

def handle_collection_selection():
	"""Handle the regular collections section"""
	st.subheader("Collections")

	# Get regular collections (those without tenants)
	regular_collections = [c for c in st.session_state.collections_list 
		if c not in st.session_state.mt_collections]

	if regular_collections:
		# Always show warning and delete button
		st.warning("WARNING: This is a DELETE operation to the database and cannot be undone. Please ensure you are connected with admin privileges.", icon="⚠️")

		if st.button("🗑️ Delete Selected Collections", type="primary", width="stretch"):
			if len(st.session_state.selected_collections) == 0:
				st.error("Please select at least one collection to delete")
			else:
				success, message = delete_collections(
					list(st.session_state.selected_collections)
				)
				if success:
					st.success(message)
					st.session_state.selected_collections.clear()
					st.rerun()
				else:
					st.error(message)

		st.write("Select collections to delete:")
		with st.container(height=400):
			for col in sorted(regular_collections):
				key = f"col_{col}"
				if st.checkbox(col, key=key, value=col in st.session_state.selected_collections):
					st.session_state.selected_collections.add(col)
				else:
					st.session_state.selected_collections.discard(col)
	else:
		st.info("No collections found")

def handle_mt_collection_selection():
	"""Handle the multi-tenancy collections section"""
	st.subheader("Multi-Tenancy Collections")

	if st.session_state.mt_collections:
		# Always show warning and delete button
		st.warning("WARNING: This is a DELETE operation to the database and cannot be undone. Please ensure you are connected with admin privileges.", icon="⚠️")

		if st.button("🗑️ Delete Selected Tenants", type="primary", width="stretch"):
			if not any(st.session_state.selected_tenants.values()):
				st.error("Please select at least one tenant to delete")
			else:
				for collection, tenants in st.session_state.selected_tenants.items():
					if tenants:
						success, message = delete_tenants_from_collection(

							collection,
							list(tenants)
						)
						if success:
							st.success(message)
							st.session_state.selected_tenants[collection].clear()
						else:
							st.error(message)
				st.rerun()

		# MT Collections and their tenants
		for collection in sorted(st.session_state.mt_collections.keys()):
			tenants = st.session_state.mt_collections[collection]

			with st.expander(f"📁 {collection}"):
				if tenants:
					# Initialize selected tenants for this collection if not exists
					if collection not in st.session_state.selected_tenants:
						st.session_state.selected_tenants[collection] = set()

					# Tenant checkboxes
					for tenant in tenants:
						key = f"tenant_{collection}_{tenant}"
						if st.checkbox(tenant, key=key, 
							value=tenant in st.session_state.selected_tenants[collection]):
							st.session_state.selected_tenants[collection].add(tenant)
						else:
							st.session_state.selected_tenants[collection].discard(tenant)
				else:
					st.info("No tenants found in this collection")
	else:
		st.info("No multi-tenancy collections found")

def get_all_collections_and_tenants():
	"""Main function to display and manage collections"""
	# Refresh collections list
	collections = list_collections()
	collections.sort()
	st.session_state.collections_list = collections

	# Update MT collections and their tenants
	st.session_state.mt_collections = {}
	for collection in collections:
		tenants = get_tenant_names(collection)
		if tenants:
			st.session_state.mt_collections[collection] = sorted(tenants)

	# DANGER ZONE: Delete all collections
	with st.expander("⚠️ DANGER ZONE — Delete ALL Collections", expanded=False):
		st.error(
			"🚨 CRITICAL WARNING: This will permanently wipe EVERY collection and ALL data "
			"from the cluster. This action is IRREVERSIBLE. There is no undo. "
			"Do NOT proceed unless you are absolutely certain and have the necessary administrator privileges."
		)
		confirm = st.checkbox(
			"I understand this will permanently delete ALL collections and ALL data. This cannot be undone.",
			key="delete_all_confirm"
		)
		if confirm:
			if st.button("💀 DELETE ALL COLLECTIONS", type="primary", width="stretch", key="delete_all_btn"):
				success, message = delete_all_collections()
				if success:
					st.success(message)
					st.session_state.selected_collections.clear()
					st.rerun()
				else:
					st.error(message)

	st.markdown("---")
	# Display collections sections
	handle_collection_selection()
	st.markdown("---")
	handle_mt_collection_selection()

def main():
	set_custom_page_config(page_title="Delete Collections & Tenants")

	navigate()

	if st.session_state.get("client_ready"):
		update_side_bar_labels()
		initialize_session_state()
		get_all_collections_and_tenants()
	else:
		st.warning("Please Establish a connection to Weaviate in Cluster page!")

if __name__ == "__main__":
	main()
