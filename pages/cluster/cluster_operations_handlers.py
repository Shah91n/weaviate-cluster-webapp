import pandas as pd
import streamlit as st
import logging
from core.collection.overview import aggregate_collections, get_schema, list_collections, process_collection_config, fetch_collection_config
from core.cluster.cluster_health import get_cluster_statistics, process_statistics, get_shards_info, process_shards_data, get_metadata, diagnose_schema, check_shard_consistency
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Action Handlers (one function per button) for Cluster Operations
# --------------------------------------------------------------------------

# Fetch node info and display node and shard details.
def action_nodes_and_shards():
	logger.info("action_nodes_and_shards called")
	node_info = get_shards_info()
	if node_info:
		processed_data = process_shards_data(node_info)
		node_table = processed_data["node_data"]
		shard_table = processed_data["shard_data"]
		collection_shard_table = processed_data["collection_shard_data"]
		readonly_shards_table = processed_data["readonly_shards"]

		st.markdown("#### Node Details")
		if not node_table.empty:
			st.dataframe(node_table.astype(str), width="stretch")
		else:
			st.warning("No node details available.")

		st.markdown("#### Shard Count")
		if not collection_shard_table.empty:
			st.dataframe(collection_shard_table, width="stretch")
		else:
			st.warning("No shard collection details available.")

		st.markdown("#### Shard Details")
		if not shard_table.empty:
			st.dataframe(shard_table.astype(str), width="stretch")
		else:
			st.warning("No shard details available.")

		# Readonly shards section
		st.markdown("#### Read-only Shards")
		if not readonly_shards_table.empty:
			st.dataframe(readonly_shards_table[["Node Name", "Class", "Shard Name", "Object Count"]].astype(str), width="stretch")
			st.warning("⬇️ This operation requires administrator privileges. Please ensure you are connected with an admin API key.")
			if st.button("Set all Read-only Shards to READY", type="primary"):
				client = get_weaviate_client()
				readonly_groups = readonly_shards_table.groupby("Class")["Shard Name"].apply(list).to_dict()
				for collection_name, shard_names in readonly_groups.items():
					try:
						coll = client.collections.use(collection_name)
						result = coll.config.update_shards(
							status="READY",
							shard_names=shard_names
						)
						st.success(f"Updated {len(shard_names)} shard(s) in '{collection_name}' to READY.")
						st.success(result)
					except Exception as e:
						st.error(f"Failed to update shards in '{collection_name}': {e}")
		else:
			st.info("No read-only shards found in the cluster.")
	else:
		st.error("Failed to retrieve node and shard details.")

# Aggregate collections and tenants.
def action_aggregate_collections_tenants():
	logger.info("action_aggregate_collections_tenants called")
	st.markdown("###### Collections & Tenants aggregation time may vary depending on the dataset size, as it iterates through all collections and tenants. Check below for tables with statistics.")
	result = aggregate_collections()
	if "error" in result:
		st.error(f"Error retrieving collections: {result['error']}")
		return

	# Display collection statistics
	collection_count = result["collection_count"]
	st.markdown(f"###### Total Number of Collections: **{collection_count}**")
	
	# Display empty collections with yellow warning
	empty_collections = result["empty_collections"]
	if empty_collections > 0:
		st.warning(f"###### Total Number of Collections with Zero Objects: **{empty_collections}**")
	else:
		st.markdown("###### Total Number of Collections with Zero Objects: **N/A**")

	# Display tenant statistics
	total_tenants_count = result["total_tenants_count"]
	if total_tenants_count > 0:
		st.markdown(f"###### Total Number of Tenants: **{total_tenants_count}**")
		
		# Display empty tenants with yellow warning
		empty_tenants = result["empty_tenants"]
		if empty_tenants > 0:
			st.warning(f"###### Total Number of Tenants with Zero Objects: **{empty_tenants}**")
		else:
			st.markdown("###### Total Number of Tenants with Zero Objects: **N/A**")
	
	# Display object counts
	total_regular = result["total_objects_regular"]
	if total_regular > 0:
		st.markdown(f"###### Total Objects in Regular Collections: **{total_regular:,}**")
	else:
		st.markdown("###### Total Objects in Regular Collections: **N/A**")

	total_multitenancy = result["total_objects_multitenancy"]
	if total_multitenancy > 0:
		st.markdown(f"###### Total Objects in Multitenancy Collections: **{total_multitenancy:,}**")
	else:
		st.markdown("###### Total Objects in Multitenancy Collections: **N/A**")

	total_combined = result["total_objects_combined"]
	if total_combined > 0:
		st.markdown(f"###### Total Objects (All Collections Combined): **{total_combined:,}**")
	else:
		st.markdown("###### Total Objects (All Collections Combined): **N/A**")

	# Display the main dataframe
	result_df = result["result_df"]
	if not result_df.empty:
		st.dataframe(result_df.astype(str), width="stretch")
	else:
		st.warning("No data to display.")

	# Display empty collections table if any exist
	empty_collections_list = result["empty_collections_list"]
	if empty_collections_list:
		st.markdown("#### Collections with Zero Objects")
		empty_collections_df = pd.DataFrame(empty_collections_list)
		st.dataframe(empty_collections_df, width="stretch")

	# Display empty tenants table if any exist
	empty_tenants_details = result["empty_tenants_details"]
	if empty_tenants_details:
		st.markdown("#### Tenants with Zero Objects")
		empty_tenants_df = pd.DataFrame(empty_tenants_details)
		st.dataframe(empty_tenants_df, width="stretch")

# Fetch and display collection properties.
def action_collection_schema():
	logger.info("action_collection_schema called")
	collections = list_collections()
	if not collections:
		st.warning("No collection(s) available.")
		return

	selected = st.selectbox("Select Collection", options=collections, key="schema_collection_select")
	if st.button("Get Properties", key="get_schema_btn", width="stretch"):
		st.session_state["schema_view_collection"] = selected

	view_collection = st.session_state.get("schema_view_collection")
	if view_collection and view_collection in collections:
		schema = get_schema()
		if not schema or (isinstance(schema, dict) and "error" in schema):
			st.error(schema.get("error", "Failed to load schema") if isinstance(schema, dict) else "Failed to load schema")
			return
		if view_collection not in schema:
			st.warning(f"Collection '{view_collection}' not found.")
			return
		collection_details = schema[view_collection]
		st.markdown(f"#### Collection: {view_collection}")
		st.markdown(f"**Name:** {collection_details.name}")
		st.markdown(f"**Description:** {collection_details.description or 'None'}")
		st.markdown(f"**Vectorizer:** {collection_details.vectorizer or 'If no vectorizer then could be NamedVectors (check collections config) or its BYOV'}")
		st.markdown("#### Properties:")
		properties_data = []
		for prop in collection_details.properties:
			properties_data.append({
				"Property Name": prop.name or "None",
				"Description": prop.description or "None",
				"Data Type": str(prop.data_type) or "None",
				"Searchable": prop.index_searchable,
				"Filterable": prop.index_filterable,
				"Tokenization": str(prop.tokenization) or "None",
				"Vectorizer": prop.vectorizer or "None",
			})
		if properties_data:
			st.dataframe(pd.DataFrame(properties_data), width="stretch")
		else:
			st.markdown("*No properties found.*")

# Fetch and display cluster statistics (RAFT).
def action_statistics():
	logger.info("action_statistics called")
	st.markdown("#### Cluster Statistics Details")
	try:
		stat = get_cluster_statistics()
		if stat is None:
			st.error("Failed to fetch cluster statistics.")
			return

		processed_stats = process_statistics(stat)
		if "error" in processed_stats:
			st.error(processed_stats["error"])
			return

		if processed_stats["synchronized"]:
			st.success("Cluster is Synchronized: ✅")
		else:
			st.error("Cluster is Synchronized: ❌")

		st.dataframe(processed_stats["data"], width="stretch")

		st.markdown("##### Network Information")
		if not processed_stats["network_info"].empty:
			st.dataframe(processed_stats["network_info"], width="stretch")

		st.markdown("##### Latest Configuration")
		if not processed_stats["latest_config"].empty:
			st.dataframe(processed_stats["latest_config"], width="stretch")

	except Exception as e:
		logger.error(f"Error fetching cluster statistics: {e}")
		st.error(f"Error fetching cluster statistics: {e}")

# Fetch and display cluster metadata.
def action_metadata():
	logger.info("action_metadata called")
	st.markdown("#### Cluster Metadata Details")
	metadata_result = get_metadata()

	if "error" in metadata_result:
		st.error(metadata_result["error"])
	else:
		# Display general metadata
		general_metadata_df = metadata_result["general_metadata_df"]
		st.markdown("##### General Information")
		st.dataframe(general_metadata_df, width="stretch")

		# Display standard modules
		standard_modules_df = metadata_result["standard_modules_df"]
		if not standard_modules_df.empty:
			st.markdown("##### Modules")
			st.dataframe(standard_modules_df, width="stretch")

		# Display other modules
		other_modules_df = metadata_result["other_modules_df"]
		if not other_modules_df.empty:
			st.markdown("##### Other Modules")
			st.dataframe(other_modules_df, width="stretch")

# Fetch and display collection configurations.
def action_collections_configuration():
	logger.info("action_collections_configuration called")
	collection_list = list_collections()

	if not collection_list or isinstance(collection_list, dict):
		st.warning("No collections available to display.")
		return

	collection_count = len(collection_list)
	st.markdown(f"###### Total Number of Collections: **{collection_count}**")

	selected = st.selectbox("Select Collection", options=collection_list, key="cfg_collection_select")
	if st.button("Get Configuration", key="get_cfg_btn", width="stretch"):
		st.session_state["cfg_view_collection"] = selected

	view_collection = st.session_state.get("cfg_view_collection")
	if view_collection and view_collection in collection_list:
		st.markdown(f"#### Collection: {view_collection}")
		config = fetch_collection_config(view_collection)
		if config is None:
			st.error(f"Failed to load configuration for '{view_collection}'.")
			return
		processed_config = process_collection_config(config)
		for section, details in processed_config.items():
			if section == "Named Vectors Config" and isinstance(details, dict):
				for vector_name, vector_info in details.items():
					st.markdown(f"##### Named Vector: {vector_name}")
					if "Vectorizer" in vector_info and isinstance(vector_info["Vectorizer"], dict):
						for vec_name, vec_config in vector_info["Vectorizer"].items():
							st.markdown(f"###### Vectorizer: **{vec_name}**")
							if isinstance(vec_config, dict) and vec_config:
								df = pd.DataFrame(list(vec_config.items()), columns=["Key", "Value"])
								st.dataframe(df.astype(str), width="stretch")
							else:
								st.markdown(f"**{vec_config}**")
					if "Vector Index Type" in vector_info:
						st.markdown(f"###### Vector Index Type: **{vector_info['Vector Index Type']}**")
					if "Vector Index Config" in vector_info:
						st.markdown("###### Vector Index Config:")
						sub_details = vector_info["Vector Index Config"]
						if isinstance(sub_details, dict) and sub_details:
							df = pd.DataFrame(list(sub_details.items()), columns=["Key", "Value"])
							st.dataframe(df.astype(str), width="stretch")
						else:
							st.markdown(f"**{sub_details}**")
					for sub_section, sub_details in vector_info.items():
						if sub_section not in ["Vectorizer", "Vector Index Type", "Vector Index Config"]:
							st.markdown(f"###### {sub_section}:")
							if isinstance(sub_details, dict) and sub_details:
								df = pd.DataFrame(list(sub_details.items()), columns=["Key", "Value"])
								st.dataframe(df.astype(str), width="stretch")
							else:
								st.markdown(f"**{sub_details}**")
			elif section == "Vectorizer Config" and isinstance(details, dict):
				st.markdown(f"###### {section}:")
				for vec_name, vec_config in details.items():
					st.markdown(f"###### Vectorizer: **{vec_name}**")
					if isinstance(vec_config, dict) and vec_config:
						df = pd.DataFrame(list(vec_config.items()), columns=["Key", "Value"])
						st.dataframe(df.astype(str), width="stretch")
					else:
						st.markdown(f"**{vec_config}**")
			else:
				st.markdown(f"###### {section}:")
				if isinstance(details, dict) and details:
					df = pd.DataFrame(list(details.items()), columns=["Key", "Value"])
					st.dataframe(df.astype(str), width="stretch")
				else:
					st.markdown(f"**{details}**")

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
			st.dataframe(df_inconsistent_shards.astype(str), width="stretch")
		else:
			st.success("🔄 Shard Consistency — all shards consistent")
	else:
		st.warning("🔄 Shard Consistency — could not retrieve node information")

	# Schema diagnostics
	diagnostics = diagnose_schema()
	if "error" in diagnostics:
		st.error(diagnostics["error"])
		return

	# Summary row
	col1, col2, col3 = st.columns(3)
	with col1:
		st.metric("Collections", diagnostics["collection_count"])
	with col2:
		st.metric("Compression Issues", len(diagnostics["compression_issues"]))
	with col3:
		st.metric("Replication Issues", len(diagnostics["replication_issues"]))

	if diagnostics["collection_count_status"] != "ok":
		st.warning(diagnostics["collection_count_message"])

	# Compression issues — expander + CSV download
	if diagnostics["compression_issues"]:
		with st.expander(f"🗜️ Compression — {len(diagnostics['compression_issues'])} collection(s) missing compression", expanded=False):
			for name in diagnostics["compression_issues"]:
				st.markdown(f"- {name}")
			csv_data = "collection\n" + "\n".join(diagnostics["compression_issues"])
			st.download_button("⬇️ Download list", data=csv_data.encode(), file_name="compression_issues.csv", mime="text/csv", key="dl_compression")
	else:
		st.success("🗜️ Compression — all collections compressed")

	# Replication issues — expander + CSV download
	if diagnostics["replication_issues"]:
		with st.expander(f"🔄 Replication — {len(diagnostics['replication_issues'])} issue(s) found", expanded=False):
			for name in diagnostics["replication_issues"]:
				st.markdown(f"- {name}")
			csv_data = "collection\n" + "\n".join(diagnostics["replication_issues"])
			st.download_button("⬇️ Download list", data=csv_data.encode(), file_name="replication_issues.csv", mime="text/csv", key="dl_replication")
	else:
		st.success("🔄 Replication — all collections properly configured")

	# Per-collection browser
	st.markdown("---")
	collection_names = [c["collection"] for c in diagnostics["all_checks"]]
	selected = st.selectbox("Browse collection:", collection_names, key="diagnose_collection_select")

	if selected:
		check = next(c for c in diagnostics["all_checks"] if c["collection"] == selected)
		has_issues = (
			check["compression"]["status"] not in ("ok", "info")
			or check["replication"]["status"] != "ok"
		)
		if has_issues:
			st.warning(f"⚠️ {selected} — observations to review")
		else:
			st.success(f"✅ {selected} — no issues")

		st.caption("Compression")
		for detail in check["compression"]["details"]:
			st.markdown(detail)
		st.caption("Replication")
		for detail in check["replication"]["details"]:
			st.markdown(detail)
			