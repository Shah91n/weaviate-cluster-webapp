import pandas as pd
import streamlit as st
import requests
import time
from utils.cluster.collection import aggregate_collections, get_schema, list_collections, process_collection_config, fetch_collection_config, get_collectios_count
from utils.cluster.cluster_operations import fetch_cluster_statistics, process_statistics, get_shards_info, process_shards_data, get_metadata, check_shard_consistency, diagnose_schema

# --------------------------------------------------------------------------
# Action Handlers (one function per button) for Cluster Operations
# --------------------------------------------------------------------------

# Fetch node info and display node and shard details.
def action_nodes_and_shards():
	print("action_nodes_and_shards called")
	node_info = get_shards_info(st.session_state.client)
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
				readonly_groups = readonly_shards_table.groupby("Class")["Shard Name"].apply(list).to_dict()
				for collection_name, shard_names in readonly_groups.items():
					try:
						coll = st.session_state.client.collections.get(collection_name)
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

# Check for shard consistency.
def action_check_shard_consistency():
	print("action_check_shard_consistency called")
	node_info = get_shards_info(st.session_state.client)
	if node_info:
		df_inconsistent_shards = check_shard_consistency(node_info)
		if df_inconsistent_shards is not None:
			inconsistent_collections = list(df_inconsistent_shards["Collection"].unique())
			total = len(inconsistent_collections)
			st.markdown(f"#### Inconsistent Shards Table with {total} Inconsistent collections")
			st.dataframe(df_inconsistent_shards.astype(str), width="stretch")
		else:
			st.success("All shards are consistent.")
	else:
		st.error("Failed to retrieve node and shard details.")

# Aggregate collections and tenants.
def action_aggregate_collections_tenants():
	print("action_aggregate_collections_tenants called")
	st.markdown("###### Collections & Tenants aggregation time may vary depending on the dataset size, as it iterates through all collections and tenants. Check below for tables with statistics.")
	result = aggregate_collections(st.session_state.client)
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
		st.markdown(f"###### Total Number of Collections with Zero Objects: **N/A**")

	# Display tenant statistics
	total_tenants_count = result["total_tenants_count"]
	if total_tenants_count > 0:
		st.markdown(f"###### Total Number of Tenants: **{total_tenants_count}**")
		
		# Display empty tenants with yellow warning
		empty_tenants = result["empty_tenants"]
		if empty_tenants > 0:
			st.warning(f"###### Total Number of Tenants with Zero Objects: **{empty_tenants}**")
		else:
			st.markdown(f"###### Total Number of Tenants with Zero Objects: **N/A**")
	
	# Display object counts
	total_regular = result["total_objects_regular"]
	if total_regular > 0:
		st.markdown(f"###### Total Objects in Regular Collections: **{total_regular:,}**")
	else:
		st.markdown(f"###### Total Objects in Regular Collections: **N/A**")

	total_multitenancy = result["total_objects_multitenancy"]
	if total_multitenancy > 0:
		st.markdown(f"###### Total Objects in Multitenancy Collections: **{total_multitenancy:,}**")
	else:
		st.markdown(f"###### Total Objects in Multitenancy Collections: **N/A**")

	total_combined = result["total_objects_combined"]
	if total_combined > 0:
		st.markdown(f"###### Total Objects (All Collections Combined): **{total_combined:,}**")
	else:
		st.markdown(f"###### Total Objects (All Collections Combined): **N/A**")

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
	print("action_collection_schema called")
	schema = get_schema(st.session_state.client)
	if schema is not None:
		if "error" in schema:
			st.error(schema["error"])
		else:
			st.markdown("#### Collection Properties")
			for collection_name, collection_details in schema.items():
				with st.expander(f"{collection_name}", expanded=False):
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
	else:
		st.warning("No collection(s) available.")

# Fetch and display cluster statistics (RAFT).
def action_statistics(cluster_endpoint, api_key):
	print("action_statistics called")
	st.markdown("#### Cluster Statistics Details")
	try:
		stats = fetch_cluster_statistics(cluster_endpoint, api_key)
		if "error" in stats:
			st.error(stats["error"])
			return

		processed_stats = process_statistics(stats)
		if "error" in processed_stats:
			st.error(processed_stats["error"])
			return

		synchronized = processed_stats["synchronized"]
		if synchronized:
			st.success("Cluster is Synchronized: ✅")
		else:
			st.error("Cluster is Synchronized: ❌")

		# Display main statistics
		flattened_data = processed_stats["data"]
		st.dataframe(flattened_data, width="stretch")

		# Display network information
		st.markdown("##### Network Information")
		network_df = processed_stats["network_info"]
		if not network_df.empty:
			st.dataframe(network_df, width="stretch")

		# Display latest configuration
		st.markdown("##### Latest Configuration")
		latest_config_df = processed_stats["latest_config"]
		if not latest_config_df.empty:
			st.dataframe(latest_config_df, width="stretch")

	except Exception as e:
		st.error(f"Error fetching cluster statistics: {e}")

# Fetch and display cluster metadata.
def action_metadata(cluster_endpoint, api_key):
	print("action_metadata called")
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
def action_collections_configuration(cluster_endpoint, api_key):
	print("action_collections_configuration called")
	"""
	Fetches and displays collection configurations in expandable sections.
	Similar to Collection Properties, this always fetches fresh data.
	"""
	# Fetch fresh collection list every time
	collection_list = list_collections(st.session_state.client)
	
	if not collection_list or isinstance(collection_list, dict):
		st.warning("No collections available to display.")
		return
	
	collection_count = len(collection_list)
	st.markdown(f"###### Total Number of Collections: **{collection_count}**")
	st.markdown("#### Collections Configuration")
	
	# Display each collection in an expander
	for collection_name in collection_list:
		with st.expander(f"{collection_name}", expanded=False):
			# Fetch configuration for this collection
			config = fetch_collection_config(cluster_endpoint, api_key, collection_name)
			if "error" in config:
				st.error(config["error"])
			else:
				processed_config = process_collection_config(config)

				for section, details in processed_config.items():
					# Handle Named Vectors Config
					if section == "Named Vectors Config" and isinstance(details, dict):
						for vector_name, vector_info in details.items():
							# Print the Named Vector title
							st.markdown(f"##### Named Vector: {vector_name}")

							# 1. Display Vectorizer section first if it exists
							if "Vectorizer" in vector_info and isinstance(vector_info["Vectorizer"], dict):
								for vec_name, vec_config in vector_info["Vectorizer"].items():
									st.markdown(f"###### Vectorizer: **{vec_name}**")
									if isinstance(vec_config, dict) and vec_config:
										df = pd.DataFrame(list(vec_config.items()), columns=["Key", "Value"])
										st.dataframe(df.astype(str), width="stretch")
									else:
										st.markdown(f"**{vec_config}**")

							# 2. Display Vector Index Type if it exists
							if "Vector Index Type" in vector_info:
								sub_details = vector_info["Vector Index Type"]
								st.markdown(f"###### Vector Index Type: **{sub_details}**")

							# 3. Display Vector Index Config if it exists
							if "Vector Index Config" in vector_info:
								sub_details = vector_info["Vector Index Config"]
								st.markdown(f"###### Vector Index Config:")
								if isinstance(sub_details, dict) and sub_details:
									df = pd.DataFrame(list(sub_details.items()), columns=["Key", "Value"])
									st.dataframe(df.astype(str), width="stretch")
								else:
									st.markdown(f"**{sub_details}**")

							# 4. Handle any additional subsections
							for sub_section, sub_details in vector_info.items():
								if sub_section not in ["Vectorizer", "Vector Index Type", "Vector Index Config"]:
									st.markdown(f"###### {sub_section}:")
									if isinstance(sub_details, dict) and sub_details:
										df = pd.DataFrame(list(sub_details.items()), columns=["Key", "Value"])
										st.dataframe(df.astype(str), width="stretch")
									else:
										st.markdown(f"**{sub_details}**")

					# Handle Vectorizer Config in NoNamed Vectors Config found
					elif section == "Vectorizer Config" and isinstance(details, dict):
						st.markdown(f"####### {section}:")
						for vec_name, vec_config in details.items():
							st.markdown(f"###### Vectorizer: **{vec_name}**")
							if isinstance(vec_config, dict) and vec_config:
								df = pd.DataFrame(list(vec_config.items()), columns=["Key", "Value"])
								st.dataframe(df.astype(str), width="stretch")
							else:
								st.markdown(f"**{vec_config}**")

							# Retrieve and display module configuration for this vectorizer if available
							module_conf = config.get("moduleConfig", {}).get(vec_name)
							if module_conf:
								st.markdown(f"###### Module Config for {vec_name}:") # Subsection heading
								if isinstance(module_conf, dict) and module_conf:
									df_module = pd.DataFrame(list(module_conf.items()), columns=["Key", "Value"])
									st.dataframe(df_module.astype(str), width="stretch")
								else:
									st.markdown(f"**{module_conf}**")

					# Handle other sections if any
					else:
						st.markdown(f"###### {section}:")
						if isinstance(details, dict) and details:
							df = pd.DataFrame(list(details.items()), columns=["Key", "Value"])
							st.dataframe(df.astype(str), width="stretch")
						else:
							st.markdown(f"**{details}**")

# Diagnose schema configuration
def action_diagnose(cluster_endpoint, api_key):
	print("action_diagnose called")
	st.markdown("#### 🔍 Schema Diagnostics Report")
	st.markdown("Running comprehensive schema diagnostics...")
	
	diagnostics = diagnose_schema(cluster_endpoint, api_key)
	
	if "error" in diagnostics:
		st.error(diagnostics["error"])
		return
	
	# 1. Collection Count Check
	st.markdown("---")
	st.markdown("### 📊 Collection Count Analysis")
	if diagnostics["collection_count_status"] == "critical":
		st.error(diagnostics["collection_count_message"])
	elif diagnostics["collection_count_status"] == "warning":
		st.warning(diagnostics["collection_count_message"])
	else:
		st.success(diagnostics["collection_count_message"])
	
	# Summary metrics
	col1, col2, col3 = st.columns(3)
	with col1:
		st.metric("Total Collections", diagnostics["collection_count"])
	with col2:
		st.metric("Compression Issues", len(diagnostics["compression_issues"]))
	with col3:
		st.metric("Replication Issues", len(diagnostics["replication_issues"]))
	
	# 2. Compression Issues Summary
	st.markdown("---")
	st.markdown("### 🗜️ Compression Configuration Summary")
	if diagnostics["compression_issues"]:
		st.warning(f"⚠️ Found {len(diagnostics['compression_issues'])} without compression enabled")
		with st.expander("📋 Collections without compression", expanded=False):
			for issue in diagnostics["compression_issues"]:
				st.markdown(f"- {issue}")
			st.info("💡 **Recommendation:** Enable RQ, BQ, or PQ compression for better memory management")
	else:
		st.success("✅ All collections have compression properly configured")
	
	# 3. Replication Issues Summary
	st.markdown("---")
	st.markdown("### 🔄 Replication Configuration Summary")
	if diagnostics["replication_issues"]:
		st.error(f"🔴 Found {len(diagnostics['replication_issues'])} with replication issues")
		with st.expander("⚠️ Collections with replication issues", expanded=False):
			for issue in diagnostics["replication_issues"]:
				st.markdown(f"- {issue}")
			st.warning("💡 **Recommendations:**\n- Set `asyncEnabled` to `true` to improve consistency\n- Use `TimeBasedResolution` or `DeleteOnConflict` for deletion strategy\n- Use odd replication factors (3, 5, 7) for optimal RAFT consensus")
	else:
		st.success("✅ All collections have replication properly configured")
	
	# 4. Detailed Collection Diagnostics
	st.markdown("---")
	st.markdown("### 📑 Detailed Collection Diagnostics")
	
	# Filter options
	filter_option = st.selectbox(
		"Filter collections by status:",
		["All Collections", "Only Issues", "Critical Issues Only", "Warnings Only"]
	)
	
	for check in diagnostics["all_checks"]:
		collection_name = check["collection"]
		compression_status = check["compression"]["status"]
		replication_status = check["replication"]["status"]
		
		# Apply filter
		show_collection = False
		if filter_option == "All Collections":
			show_collection = True
		elif filter_option == "Only Issues":
			show_collection = (compression_status != "ok" or replication_status != "ok")
		elif filter_option == "Critical Issues Only":
			show_collection = (compression_status == "critical" or replication_status == "critical")
		elif filter_option == "Warnings Only":
			show_collection = (compression_status == "warning" or replication_status == "warning")
		
		if not show_collection:
			continue
		
		# Determine overall status icon; keep all collections folded
		if compression_status == "critical" or replication_status == "critical":
			status_icon = "🔴"
		elif compression_status == "warning" or replication_status == "warning":
			status_icon = "⚠️"
		else:
			status_icon = "✅"
		expanded = False
		
		with st.expander(f"{status_icon} **{collection_name}**", expanded=expanded):
			# Compression details
			st.markdown("##### 🗜️ Compression Configuration")
			for detail in check["compression"]["details"]:
				st.markdown(detail)
			
			# Replication details
			st.markdown("##### 🔄 Replication Configuration")
			for detail in check["replication"]["details"]:
				st.markdown(detail)
	
	st.markdown("---")
	st.markdown("### ✅ Diagnostics Complete")
	st.info("💡 **Next Steps:** Review any critical or warning issues above and consider applying the recommended configurations.")
			