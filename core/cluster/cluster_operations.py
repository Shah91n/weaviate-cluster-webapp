import requests
import pandas as pd
from collections import defaultdict
import logging
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)


# Diagnose schema configuration
def diagnose_schema(cluster_url, api_key):
    print("diagnose_schema() called")
    try:
        url = f"{cluster_url}/v1/schema"
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        schema = response.json()
        
        collections = schema.get("classes", [])
        collection_count = len(collections)
        
        # Storage for diagnostics
        diagnostics = {
            "collection_count": collection_count,
            "collection_count_status": "ok",
            "collection_count_message": "",
            "compression_issues": [],
            "replication_issues": [],
            "all_checks": []
        }
        
        # 1. Check collection count
        if collection_count > 1000:
            diagnostics["collection_count_status"] = "critical"
            diagnostics["collection_count_message"] = f"🔴 CRITICAL: {collection_count} collections detected! This seems to be a Multi-Tenancy case and to be reviewed immediately."
        elif collection_count > 100:
            diagnostics["collection_count_status"] = "warning"
            diagnostics["collection_count_message"] = f"⚠️ WARNING: {collection_count} collections detected. This seems to be a Multi-Tenancy case."
        else:
            diagnostics["collection_count_message"] = f"✅ OK: {collection_count} collections detected."
        
        # 2 & 3. Check each collection's configuration
        for cls in collections:
            collection_name = cls.get("class", "Unknown")
            collection_diagnostics = {
                "collection": collection_name,
                "compression": {"status": "ok", "details": []},
                "replication": {"status": "ok", "details": []}
            }
            
            # Compression check: prioritize vectorConfig, then fallback to vectorIndexConfig
            vector_index_config = cls.get("vectorIndexConfig", {})
            vector_config = cls.get("vectorConfig", {})

            compression_found = False

            # Prefer named vectors (vectorConfig)
            if vector_config:
                for vector_name, vector_details in vector_config.items():
                    vec_index_config = vector_details.get("vectorIndexConfig", {})
                    rq = vec_index_config.get("rq", {}).get("enabled", False)
                    bq = vec_index_config.get("bq", {}).get("enabled", False)
                    pq = vec_index_config.get("pq", {}).get("enabled", False)

                    if rq or bq or pq:
                        compression_found = True
                        enabled_types = []
                        if rq: enabled_types.append("RQ")
                        if bq: enabled_types.append("BQ")
                        if pq: enabled_types.append("PQ")
                        collection_diagnostics["compression"]["details"].append(
                            f"✅ vectorConfig['{vector_name}']: Compression enabled ({', '.join(enabled_types)})"
                        )
                    else:
                        collection_diagnostics["compression"]["status"] = "warning"
                        collection_diagnostics["compression"]["details"].append(
                            f"⚠️ vectorConfig['{vector_name}']: No compression enabled (enable RQ/BQ/PQ)"
                        )
                        diagnostics["compression_issues"].append(f"{collection_name} (vectorConfig: {vector_name})")

            # Fallback to single vector config only if no vectorConfig defined
            elif vector_index_config:
                rq = vector_index_config.get("rq", {}).get("enabled", False)
                bq = vector_index_config.get("bq", {}).get("enabled", False)
                pq = vector_index_config.get("pq", {}).get("enabled", False)

                if rq or bq or pq:
                    compression_found = True
                    enabled_types = []
                    if rq: enabled_types.append("RQ")
                    if bq: enabled_types.append("BQ")
                    if pq: enabled_types.append("PQ")
                    collection_diagnostics["compression"]["details"].append(
                        f"✅ Compression enabled: {', '.join(enabled_types)}"
                    )
                else:
                    collection_diagnostics["compression"]["status"] = "warning"
                    collection_diagnostics["compression"]["details"].append(
                        "⚠️ No compression enabled (RQ/BQ/PQ). Consider enabling for better memory management."
                    )
                    diagnostics["compression_issues"].append(collection_name)

            # If no compression config found at all
            if not vector_config and not vector_index_config:
                collection_diagnostics["compression"]["status"] = "info"
                collection_diagnostics["compression"]["details"].append("ℹ️ No vector configuration found")
            
            # Check replication configuration
            replication_config = cls.get("replicationConfig", {})
            if replication_config:
                # Check asyncEnabled
                async_enabled = replication_config.get("asyncEnabled", False)
                if not async_enabled:
                    collection_diagnostics["replication"]["status"] = "critical"
                    collection_diagnostics["replication"]["details"].append(
                        "🔴 CRITICAL: asyncEnabled is FALSE - Async replication not enabled; can cause consistency issues. Set to TRUE."
                    )
                    diagnostics["replication_issues"].append(f"{collection_name} (async)"
                    )
                else:
                    collection_diagnostics["replication"]["details"].append("✅ asyncEnabled is TRUE (correct)")
                
                # Check deletionStrategy
                deletion_strategy = replication_config.get("deletionStrategy", "")
                if deletion_strategy == "NoAutomatedResolution":
                    collection_diagnostics["replication"]["status"] = "critical" if collection_diagnostics["replication"]["status"] != "critical" else "critical"
                    collection_diagnostics["replication"]["details"].append("🔴 CRITICAL: deletionStrategy is 'NoAutomatedResolution' - Deletes are not handled! Should be 'TimeBasedResolution' or 'DeleteOnConflict'.")
                    diagnostics["replication_issues"].append(f"{collection_name} (deletion)")
                elif deletion_strategy in ["TimeBasedResolution", "DeleteOnConflict"]:
                    collection_diagnostics["replication"]["details"].append(f"✅ deletionStrategy is '{deletion_strategy}' (correct)")
                else:
                    collection_diagnostics["replication"]["details"].append(f"ℹ️ deletionStrategy: {deletion_strategy if deletion_strategy else 'Not specified'}")
                
                # Check replication factor
                replication_factor = replication_config.get("factor", 1)
                if replication_factor == 1:
                    collection_diagnostics["replication"]["status"] = "warning" if collection_diagnostics["replication"]["status"] == "ok" else collection_diagnostics["replication"]["status"]
                    collection_diagnostics["replication"]["details"].append("⚠️ WARNING: Replication factor is 1 (no replication)")
                elif replication_factor % 2 == 0:
                    collection_diagnostics["replication"]["status"] = "warning" if collection_diagnostics["replication"]["status"] == "ok" else collection_diagnostics["replication"]["status"]
                    collection_diagnostics["replication"]["details"].append(f"⚠️ WARNING: Replication factor is {replication_factor} (even number). RAFT consensus works best with odd numbers (3, 5, 7).")
                else:
                    collection_diagnostics["replication"]["details"].append(f"✅ Replication factor is {replication_factor} (optimal for RAFT)")
            else:
                collection_diagnostics["replication"]["details"].append("ℹ️ No replication configuration found")
            
            diagnostics["all_checks"].append(collection_diagnostics)
        
        return diagnostics
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch schema for diagnostics: {e}"}

# Get shards information
def get_shards_info():
    logger.info("get_shards_info() called")
    try:
        client = get_weaviate_client()
        node_info = client.cluster.nodes(output="verbose")
        return node_info
    except Exception as e:
        logger.error(f"Error getting shards info: {e}")
        return None

# Process shards data from node information
def process_shards_data(node_info):
    logger.info("process_shards_data() called")
    node_data = []
    shard_data = []
    collection_shard_counts = []
    readonly_shards = []

    if not node_info:
        return {
            "node_data": pd.DataFrame(),
            "shard_data": pd.DataFrame(), 
            "collection_shard_data": pd.DataFrame(),
            "readonly_shards": pd.DataFrame()
        }

    for node in node_info:
        logger.debug(f"Processing node: {node.name}")
        
        # Node-level data
        node_data.append({
            "Node Name": node.name,
            "Git Hash": node.git_hash,
            "Version": node.version,
            "Status": node.status,
            "Object Count (Stats)": node.stats.object_count,
            "Shard Count (Stats)": node.stats.shard_count,
        })

        # Dictionary to count shards per collection for this node
        collection_counts = {}

        # Shard-level data for each node
        for shard in node.shards:            
            shard_info = {
                "Node Name": node.name,
                "Class": shard.collection,
                "Shard Name": shard.name,
                "Object Count": shard.object_count,
                "Index Status": shard.vector_indexing_status,
                "Vector Queue Length": shard.vector_queue_length,
                "Compressed": shard.compressed,
                "Loaded": shard.loaded
            }
            shard_data.append(shard_info)

            # Check specifically for READONLY status
            if hasattr(shard, 'vector_indexing_status') and shard.vector_indexing_status == "READONLY":
                readonly_shards.append(shard_info)

            # Increment count for this collection on the current node
            collection_counts[shard.collection] = collection_counts.get(shard.collection, 0) + 1

        # Append shard collection counts for the current node
        for collection, count in collection_counts.items():
            collection_shard_counts.append({
                "Node Name": node.name,
                "Collection": collection,
                "Shard Count": count
            })

    return {
        "node_data": pd.DataFrame(node_data),
        "shard_data": pd.DataFrame(shard_data), 
        "collection_shard_data": pd.DataFrame(collection_shard_counts),
        "readonly_shards": pd.DataFrame(readonly_shards) if readonly_shards else pd.DataFrame()
    }

# Display shards information
def display_shards_table(processed_data):
    logger.info("display_shards_table() called")
    return processed_data["node_data"], processed_data["shard_data"]

# Check consistency of shard object counts across nodes. Returns a DataFrame of inconsistencies, or None if consistent.
def check_shard_consistency(node_info):
    logger.info("check_shard_consistency() called")
    shard_data = defaultdict(list)
    for node in node_info:
        # node.shards is a list of shards for this node
        for shard in node.shards:
            shard_key = (shard.collection, shard.name)
            shard_data[shard_key].append((node.name, shard.object_count))

    inconsistent_shards = []
    for (collection, shard_name), details in shard_data.items():
        object_counts = [obj_count for _, obj_count in details]
        # Inconsistent if not all object counts are identical
        if len(set(object_counts)) > 1:
            for node_name, object_count in details:
                inconsistent_shards.append({
                    "Collection": collection,
                    "Shard": shard_name,
                    "Node": node_name,
                    "Object Count": object_count,
                })

    if inconsistent_shards:
        df_inconsistent_shards = pd.DataFrame(inconsistent_shards)
        return df_inconsistent_shards

    return None
    
# Get cluster statistics
def fetch_cluster_statistics(cluster_url, api_key):
    logger.info(f"fetch_cluster_statistics() called with cluster_url: {cluster_url}")
    try:
        url = f"{cluster_url}/v1/cluster/statistics"
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status() 

        return response.json() 
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching cluster statistics: {e}")
        return {"error": f"Failed to fetch cluster statistics: {e}"}

# Process cluster statistics data
def process_statistics(stats):
    logger.info("process_statistics() called")
    if "statistics" not in stats:
        return {"error": "Invalid statistics data received."}

    flattened_data = []
    latest_config_data = []
    network_info = []
    synchronized = stats.get("synchronized", False)
    
    for node in stats["statistics"]:
        # Base data for node statistics
        base_data = {
            "Node Name": node.get("name", "N/A"),
            "Leader ID": node.get("leaderId", "N/A"),
            "Leader Address": node.get("leaderAddress", "N/A"),
            "State": node.get("raft", {}).get("state", "N/A"),
            "Status": node.get("status", "N/A"),
            "Ready": node.get("ready", "N/A"),
            "DB Loaded": node.get("dbLoaded", "N/A"),
            "Open": node.get("open", "N/A"),
            "Is Voter": node.get("isVoter", "N/A"),
            "Applied Index": node.get("raft", {}).get("appliedIndex", "N/A"),
            "Commit Index": node.get("raft", {}).get("commitIndex", "N/A"),
            "Last Contact": node.get("raft", {}).get("lastContact", "N/A"),
            "Last Log Index": node.get("raft", {}).get("lastLogIndex", "N/A"),
            "Last Log Term": node.get("raft", {}).get("lastLogTerm", "N/A"),
            "Initial Last Applied Index": node.get("initialLastAppliedIndex", "N/A"),
            "Num Peers": node.get("raft", {}).get("numPeers", "N/A"),
            "Term": node.get("raft", {}).get("term", "N/A"),
            "FSM Pending": node.get("raft", {}).get("fsmPending", "N/A"),
            "Last Snapshot Index": node.get("raft", {}).get("lastSnapshotIndex", "N/A"),
            "Last Snapshot Term": node.get("raft", {}).get("lastSnapshotTerm", "N/A"),
            "Protocol Version": node.get("raft", {}).get("protocolVersion", "N/A"),
            "Protocol Version Max": node.get("raft", {}).get("protocolVersionMax", "N/A"),
            "Protocol Version Min": node.get("raft", {}).get("protocolVersionMin", "N/A"),
            "Snapshot Version Max": node.get("raft", {}).get("snapshotVersionMax", "N/A"),
            "Snapshot Version Min": node.get("raft", {}).get("snapshotVersionMin", "N/A"),
        }
        flattened_data.append(base_data)

        # Process latestConfiguration
        latest_config = node.get("raft", {}).get("latestConfiguration", [])
        for config in latest_config:
            # Extract network info
            address = config.get("address", "N/A")
            if ":" in address:
                ip, port = address.rsplit(":", 1)
                network_info.append({
                    "Pod": config.get("id", "N/A"),
                    "IP": ip,
                    "Port": port
                })

            config_data = {
                "Node Name": node.get("name", "N/A"),
                "Node State": node.get("raft", {}).get("state", "N/A"),
                "Peer ID": config.get("id", "N/A"),
                "Peer Address": address,
                "Peer Suffrage": "Voter" if config.get("suffrage") == 0 else "Non-Voter"
            }
            latest_config_data.append(config_data)

    df_data = pd.DataFrame(flattened_data).fillna("N/A")
    df_config = pd.DataFrame(latest_config_data).fillna("N/A")
    df_network = pd.DataFrame(network_info).drop_duplicates().fillna("N/A")

    return {
        "data": df_data,
        "synchronized": synchronized,
        "latest_config": df_config,
        "network_info": df_network
    }

# Get cluster metadata
def get_metadata():
    logger.info("get_metadata() called")
    try:
        client = get_weaviate_client()
        metadata = client.get_meta()

        # Process general metadata (excluding modules)
        general_metadata = {
            key: str(value) for key, value in metadata.items() if key != "modules"
        }
        general_metadata_df = pd.DataFrame(general_metadata.items(), columns=["Key", "Value"])

        # Process modules
        modules_data = metadata.get("modules", {})
        standard_modules = []  # For modules with standard structure (name + documentationHref)
        other_modules = []     # For modules with different structure

        for module_name, module_details in modules_data.items():
            if isinstance(module_details, dict):
                if "name" in module_details and "documentationHref" in module_details:
                    standard_modules.append({
                        "Module": str(module_name),
                        "Name": str(module_details.get("name", "N/A")),
                        "Documentation": str(module_details.get("documentationHref", "N/A"))
                    })
                else:
                    # Other module format
                    other_module = {"Module": str(module_name)}
                    other_module.update({k: str(v) if v is not None else "N/A" 
                                       for k, v in module_details.items()})
                    other_modules.append(other_module)

        standard_modules_df = pd.DataFrame(standard_modules) if standard_modules else pd.DataFrame()
        other_modules_df = pd.DataFrame(other_modules) if other_modules else pd.DataFrame()

        return {
            "general_metadata_df": general_metadata_df,
            "standard_modules_df": standard_modules_df,
            "other_modules_df": other_modules_df
        }

    except Exception as e:
        logger.error(f"Error fetching cluster metadata: {e}")
        return {"error": f"Failed to fetch cluster metadata: {e}"}
    