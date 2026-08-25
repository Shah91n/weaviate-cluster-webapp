import logging

import pandas as pd
import streamlit as st

from core.cluster.cluster_health import (
	check_shard_consistency,
	diagnose_schema,
	get_cluster_statistics,
	get_metadata,
	get_shards_info,
	process_shards_data,
	process_statistics,
)
from core.collection.overview import (
	aggregate_collections,
	fetch_collection_config,
	get_schema,
	list_collections,
	process_collection_config,
)
from core.connection.weaviate_connection_manager import get_weaviate_client
from pages.utils import ui

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Action Handlers (one function per button) for Cluster Operations
# --------------------------------------------------------------------------


# Fetch node info and display node and shard details.
def action_nodes_and_shards():
	logger.info("action_nodes_and_shards called")
	node_info = get_shards_info()
	if not node_info:
		st.error("Failed to retrieve node and shard details.")
		return

	processed_data = process_shards_data(node_info)
	node_table = processed_data["node_data"]
	shard_table = processed_data["shard_data"]
	collection_shard_table = processed_data["collection_shard_data"]
	readonly_shards_table = processed_data["readonly_shards"]

	total_objects = int(node_table["Object Count (Stats)"].sum()) if not node_table.empty else 0
	total_shards = int(node_table["Shard Count (Stats)"].sum()) if not node_table.empty else 0
	ui.metric_row([
		("Nodes", len(node_table)),
		("Shards", f"{total_shards:,}"),
		("Objects", f"{total_objects:,}"),
		("Read-only Shards", len(readonly_shards_table)),
	])

	ui.section("Node Details")
	ui.data_table(node_table, "No node details available.")

	ui.section("Shard Count per Collection")
	ui.data_table(collection_shard_table, "No shard collection details available.")

	ui.section("Shard Details")
	ui.data_table(shard_table, "No shard details available.")

	ui.section("Read-only Shards")
	if readonly_shards_table.empty:
		st.success("No read-only shards found in the cluster.")
		return

	ui.data_table(readonly_shards_table[["Node Name", "Class", "Shard Name", "Object Count"]])
	ui.admin_warning("Setting shards back to READY")
	if st.button("Set all Read-only Shards to READY", type="primary"):
		client = get_weaviate_client()
		readonly_groups = readonly_shards_table.groupby("Class")["Shard Name"].apply(list).to_dict()
		for collection_name, shard_names in readonly_groups.items():
			try:
				coll = client.collections.use(collection_name)
				result = coll.config.update_shards(status="READY", shard_names=shard_names)
				st.success(f"Updated {len(shard_names)} shard(s) in '{collection_name}' to READY.")
				st.success(result)
			except Exception as e:
				st.error(f"Failed to update shards in '{collection_name}': {e}")


# Aggregate collections and tenants.
def action_aggregate_collections_tenants():
	logger.info("action_aggregate_collections_tenants called")
	st.caption(
		"Aggregation time varies with dataset size — this iterates through every collection and tenant."
	)
	result = aggregate_collections()
	if "error" in result:
		st.error(f"Error retrieving collections: {result['error']}")
		return

	empty_collections = result["empty_collections"]
	total_tenants = result["total_tenants_count"]
	empty_tenants = result["empty_tenants"]

	ui.metric_row([
		("Collections", result["collection_count"]),
		("Empty Collections", empty_collections),
		("Tenants", f"{total_tenants:,}"),
		("Empty Tenants", f"{empty_tenants:,}"),
	])
	ui.metric_row([
		("Objects — Regular", f"{result['total_objects_regular']:,}"),
		("Objects — Multi-tenant", f"{result['total_objects_multitenancy']:,}"),
		("Objects — Combined", f"{result['total_objects_combined']:,}"),
	])

	if empty_collections or empty_tenants:
		st.warning(
			f"{empty_collections} collection(s) and {empty_tenants} tenant(s) hold zero objects."
		)

	ui.section("Collections & Tenants")
	ui.data_table(result["result_df"], "No data to display.")

	if result["empty_collections_list"]:
		with st.expander(f"Collections with zero objects ({empty_collections})"):
			ui.data_table(pd.DataFrame(result["empty_collections_list"]))

	if result["empty_tenants_details"]:
		with st.expander(f"Tenants with zero objects ({empty_tenants})"):
			ui.data_table(pd.DataFrame(result["empty_tenants_details"]))


# Fetch and display collection properties.
def action_collection_schema():
	logger.info("action_collection_schema called")
	collections = ui.load(list_collections, error_prefix="Could not list collections")
	if not collections:
		st.warning("No collection(s) available.")
		return

	selected = st.selectbox("Collection", options=collections, key="schema_collection_select")
	if st.button("Get Properties", key="get_schema_btn", width="stretch"):
		st.session_state["schema_view_collection"] = selected

	view_collection = st.session_state.get("schema_view_collection")
	if not view_collection or view_collection not in collections:
		return

	schema = ui.load(get_schema, error_prefix="Could not load schema")
	if view_collection not in schema:
		st.warning(f"Collection '{view_collection}' not found.")
		return

	details = schema[view_collection]
	ui.section(details.name)
	ui.kv_table({
		"Description": details.description or "None",
		"Vectorizer": details.vectorizer or "Named vectors or BYOV — see Collections Configuration",
		"Properties": len(details.properties or []),
	})

	ui.section("Properties")
	properties_data = [
		{
			"Property Name": prop.name or "None",
			"Description": prop.description or "None",
			"Data Type": str(prop.data_type) or "None",
			"Searchable": prop.index_searchable,
			"Filterable": prop.index_filterable,
			"Tokenization": str(prop.tokenization) or "None",
			"Vectorizer": prop.vectorizer or "None",
		}
		for prop in details.properties
	]
	ui.data_table(pd.DataFrame(properties_data), "No properties found.")


# Fetch and display cluster statistics (RAFT).
def action_statistics():
	logger.info("action_statistics called")
	try:
		stat = get_cluster_statistics()
		if stat is None:
			st.error("Failed to fetch cluster statistics.")
			return

		processed_stats = process_statistics(stat)
		if "error" in processed_stats:
			st.error(processed_stats["error"])
			return

		ui.status_callout(
			"ok" if processed_stats["synchronized"] else "critical",
			"RAFT cluster is synchronized." if processed_stats["synchronized"] else "RAFT cluster is NOT synchronized.",
		)

		ui.section("RAFT State")
		ui.data_table(processed_stats["data"])

		ui.section("Network Information")
		ui.data_table(processed_stats["network_info"], "No network information available.")

		ui.section("Latest Configuration")
		ui.data_table(processed_stats["latest_config"], "No peer configuration available.")

	except Exception as e:
		logger.error(f"Error fetching cluster statistics: {e}")
		st.error(f"Error fetching cluster statistics: {e}")


# Fetch and display cluster metadata.
def action_metadata():
	logger.info("action_metadata called")
	metadata_result = get_metadata()

	if "error" in metadata_result:
		st.error(metadata_result["error"])
		return

	ui.section("General Information")
	ui.data_table(metadata_result["general_metadata_df"])

	standard_modules_df = metadata_result["standard_modules_df"]
	if not standard_modules_df.empty:
		ui.section("Modules", f"{len(standard_modules_df)} module(s) enabled")
		ui.data_table(
			standard_modules_df,
			column_config={"Documentation": st.column_config.LinkColumn("Documentation", display_text="docs")},
		)

	other_modules_df = metadata_result["other_modules_df"]
	if not other_modules_df.empty:
		ui.section("Other Modules")
		ui.data_table(other_modules_df)


def _render_vector_sections(vector_name, sections):
	"""Render one vector's config, leading with its real index type."""
	index_type = sections.get("Vector Index Type", "unknown")
	ui.metric_row([
		("Vector", vector_name),
		("Vector Index Type", index_type),
		("Compression", sections.get("Compression", "none")),
	])
	if sections.get("Vectorizer"):
		st.caption(f"Vectorizer: **{sections['Vectorizer']}**")

	for key, value in sections.items():
		if key in ("Vector Index Type", "Vectorizer", "Compression"):
			continue
		st.markdown(f"**{key}**")
		ui.kv_table(value)


# Fetch and display collection configurations.
def action_collections_configuration():
	logger.info("action_collections_configuration called")
	collection_list = ui.load(list_collections, error_prefix="Could not list collections")

	if not collection_list or isinstance(collection_list, dict):
		st.warning("No collections available to display.")
		return

	selected = st.selectbox("Collection", options=collection_list, key="cfg_collection_select")
	if st.button("Get Configuration", key="get_cfg_btn", width="stretch"):
		st.session_state["cfg_view_collection"] = selected

	view_collection = st.session_state.get("cfg_view_collection")
	if not view_collection or view_collection not in collection_list:
		return

	config = ui.load(fetch_collection_config, view_collection, error_prefix="Could not load configuration")
	if config is None:
		st.error(f"Failed to load configuration for '{view_collection}'.")
		return

	processed_config = process_collection_config(config)
	vectors = processed_config.pop("Vectors", {})

	ui.section(view_collection)
	for section_name, details in processed_config.items():
		with st.expander(section_name, expanded=False):
			ui.kv_table(details)

	if not vectors:
		st.info("This collection has no vector configuration.")
		return

	ui.section("Vectors", f"{len(vectors)} vector(s) configured")
	for vector_name, sections in vectors.items():
		with st.expander(f"{vector_name} — {sections.get('Vector Index Type', 'unknown')}", expanded=True):
			_render_vector_sections(vector_name, sections)


# Diagnose schema configuration
def action_diagnose():
	logger.info("action_diagnose called")

	# Shard consistency
	node_info = get_shards_info()
	if node_info:
		df_inconsistent_shards = check_shard_consistency(node_info)
		if df_inconsistent_shards is not None:
			total = df_inconsistent_shards["Collection"].nunique()
			st.warning(f"🔄 Shard Consistency — {total} inconsistent shard(s) found")
			ui.data_table(df_inconsistent_shards)
		else:
			st.success("🔄 Shard Consistency — all shards consistent")
	else:
		st.warning("🔄 Shard Consistency — could not retrieve node information")

	# Schema diagnostics
	diagnostics = diagnose_schema()
	if "error" in diagnostics:
		st.error(diagnostics["error"])
		return

	ui.metric_row([
		("Collections", diagnostics["collection_count"]),
		("Compression Issues", len(diagnostics["compression_issues"])),
		("Replication Issues", len(diagnostics["replication_issues"])),
	])

	if diagnostics["collection_count_status"] != "ok":
		st.warning(diagnostics["collection_count_message"])

	# Compression issues — expander + CSV download
	if diagnostics["compression_issues"]:
		with st.expander(f"🗜️ Compression — {len(diagnostics['compression_issues'])} vector(s) without compression", expanded=False):
			for name in diagnostics["compression_issues"]:
				st.markdown(f"- {name}")
			ui.download_list("⬇️ Download list", diagnostics["compression_issues"], "compression_issues.csv", "dl_compression")
	else:
		st.success("🗜️ Compression — every vector index is compressed")

	# Replication issues — expander + CSV download
	if diagnostics["replication_issues"]:
		with st.expander(f"🔄 Replication — {len(diagnostics['replication_issues'])} issue(s) found", expanded=False):
			for name in diagnostics["replication_issues"]:
				st.markdown(f"- {name}")
			ui.download_list("⬇️ Download list", diagnostics["replication_issues"], "replication_issues.csv", "dl_replication")
	else:
		st.success("🔄 Replication — all collections properly configured")

	# Per-collection browser
	st.markdown("---")
	collection_names = [c["collection"] for c in diagnostics["all_checks"]]
	selected = st.selectbox("Browse collection:", collection_names, key="diagnose_collection_select")

	if not selected:
		return

	check = next(c for c in diagnostics["all_checks"] if c["collection"] == selected)
	has_issues = (
		check["compression"]["status"] not in ("ok", "info")
		or check["replication"]["status"] != "ok"
	)
	ui.status_callout(
		"warning" if has_issues else "ok",
		f"{selected} — observations to review" if has_issues else f"{selected} — no issues",
	)

	col1, col2 = st.columns(2)
	with col1:
		st.caption("Compression")
		for detail in check["compression"]["details"]:
			st.markdown(detail)
	with col2:
		st.caption("Replication")
		for detail in check["replication"]["details"]:
			st.markdown(detail)
