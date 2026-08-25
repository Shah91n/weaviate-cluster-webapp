import streamlit as st

from pages.cluster.cluster_operations_handlers import (
	action_aggregate_collections_tenants,
	action_collection_schema,
	action_collections_configuration,
	action_diagnose,
	action_metadata,
	action_nodes_and_shards,
	action_statistics,
)
from pages.utils import ui
from pages.utils.page_config import page_header


def main():
	page_header("Cluster")
	ui.require_connection()

	# --------------------------------------------------------------------------
	# Main Page Content (Cluster Operations)
	# --------------------------------------------------------------------------
	st.caption(
		"Aggregation and read data is cached in the session state for an hour. To clear it, "
		"use Clear cache in the Streamlit menu, or disconnect and reconnect."
	)

	# --------------------------------------------------------------------------
	# Cluster operation buttons — one entry per action, rendered three per row.
	# --------------------------------------------------------------------------
	CLUSTER_ACTIONS = (
		("aggregate_collections_tenants", "Aggregate Object Counts", "🧮", action_aggregate_collections_tenants),
		("collection_properties", "Collection Properties", "📋", action_collection_schema),
		("collections_configuration", "Collections Configuration", "⚙️", action_collections_configuration),
		("nodes", "Nodes & Shards", "🖥️", action_nodes_and_shards),
		("statistics", "Raft Statistics", "📊", action_statistics),
		("metadata", "Metadata", "🏷️", action_metadata),
		("diagnose", "Diagnose", "🩺", action_diagnose),
	)

	button_actions = {key: fn for key, _, _, fn in CLUSTER_ACTIONS}
	active_button = st.session_state.get("active_button")

	for row_start in range(0, len(CLUSTER_ACTIONS), 3):
		row = CLUSTER_ACTIONS[row_start:row_start + 3]
		columns = st.columns(3)
		for column, (key, label, icon, _) in zip(columns, row):
			with column:
				if st.button(
					label,
					icon=icon,
					width="stretch",
					key=f"btn_{key}",
					type="primary" if active_button == key else "secondary",
				):
					st.session_state["active_button"] = key
					active_button = key
	# --------------------------------------------------------------------------
	# Execute the active button's action
	# --------------------------------------------------------------------------
	if active_button:
		action_fn = button_actions.get(active_button)
		if action_fn:
			st.markdown("---")
			action_fn()
		else:
			st.warning("No action mapped for this button. Please report this issue to Mohamed Shahin in Weaviate Community Slack.")


main()
