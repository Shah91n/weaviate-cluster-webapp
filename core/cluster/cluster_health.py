import pandas as pd
from collections import defaultdict
import logging
from weaviate.classes.config import ReplicationDeletionStrategy
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)


# Diagnose schema configuration using the Weaviate Python client SDK
def diagnose_schema():
    logger.info("diagnose_schema() called")
    try:
        client = get_weaviate_client()
        schema = client.collections.list_all(simple=False)

        collection_count = len(schema)

        diagnostics = {
            "collection_count": collection_count,
            "collection_count_status": "ok",
            "collection_count_message": "",
            "compression_issues": [],
            "replication_issues": [],
            "all_checks": []
        }

        if collection_count > 1000:
            diagnostics["collection_count_status"] = "critical"
            diagnostics["collection_count_message"] = f"🔴 CRITICAL: {collection_count} collections detected! This seems to be a Multi-Tenancy case and to be reviewed immediately."
        elif collection_count > 100:
            diagnostics["collection_count_status"] = "warning"
            diagnostics["collection_count_message"] = f"⚠️ WARNING: {collection_count} collections detected. This seems to be a Multi-Tenancy case."
        else:
            diagnostics["collection_count_message"] = f"✅ OK: {collection_count} collections detected."

        for col_config in schema.values():
            collection_name = col_config.name
            collection_diagnostics = {
                "collection": collection_name,
                "compression": {"status": "ok", "details": []},
                "replication": {"status": "ok", "details": []}
            }

            # Compression check — prefer named vectors (vector_config), fall back to single vector_index_config
            vector_config = getattr(col_config, "vector_config", None)
            vector_index_config = getattr(col_config, "vector_index_config", None)

            if vector_config:
                for vec_name, named_vec in vector_config.items():
                    vic = getattr(named_vec, "vector_index_config", None)
                    quantizer = getattr(vic, "quantizer", None) if vic else None
                    if quantizer is not None:
                        q_type = type(quantizer).__name__.lstrip("_").replace("Config", "")
                        collection_diagnostics["compression"]["details"].append(
                            f"✅ vectorConfig['{vec_name}']: Compression enabled ({q_type})"
                        )
                    else:
                        collection_diagnostics["compression"]["status"] = "warning"
                        collection_diagnostics["compression"]["details"].append(
                            f"⚠️ vectorConfig['{vec_name}']: No compression enabled (enable RQ/BQ/PQ)"
                        )
                        diagnostics["compression_issues"].append(f"{collection_name} (vec: {vec_name})")
            elif vector_index_config:
                quantizer = getattr(vector_index_config, "quantizer", None)
                if quantizer is not None:
                    q_type = type(quantizer).__name__.lstrip("_").replace("Config", "")
                    collection_diagnostics["compression"]["details"].append(
                        f"✅ Compression enabled: {q_type}"
                    )
                else:
                    collection_diagnostics["compression"]["status"] = "warning"
                    collection_diagnostics["compression"]["details"].append(
                        "⚠️ No compression enabled. Consider enabling for better memory management."
                    )
                    diagnostics["compression_issues"].append(collection_name)
            else:
                collection_diagnostics["compression"]["status"] = "info"
                collection_diagnostics["compression"]["details"].append("ℹ️ No vector configuration found")

            # Replication check
            replication_config = getattr(col_config, "replication_config", None)
            if replication_config:
                async_enabled = getattr(replication_config, "async_enabled", False)
                if not async_enabled:
                    collection_diagnostics["replication"]["status"] = "critical"
                    collection_diagnostics["replication"]["details"].append(
                        "🔴 CRITICAL: asyncEnabled is FALSE - Async replication not enabled; can cause consistency issues. Set to TRUE."
                    )
                    diagnostics["replication_issues"].append(f"{collection_name} (async)")
                else:
                    collection_diagnostics["replication"]["details"].append("✅ asyncEnabled is TRUE")

                deletion_strategy = getattr(replication_config, "deletion_strategy", None)
                if deletion_strategy is not None:
                    if deletion_strategy == ReplicationDeletionStrategy.NO_AUTOMATED_RESOLUTION:
                        collection_diagnostics["replication"]["status"] = "critical"
                        collection_diagnostics["replication"]["details"].append(
                            "🔴 CRITICAL: deletionStrategy is 'NoAutomatedResolution' - Deletes are not handled! Should be 'TimeBasedResolution' or 'DeleteOnConflict'."
                        )
                        diagnostics["replication_issues"].append(f"{collection_name} (deletion)")
                    elif deletion_strategy in (
                        ReplicationDeletionStrategy.TIME_BASED_RESOLUTION,
                        ReplicationDeletionStrategy.DELETE_ON_CONFLICT,
                    ):
                        collection_diagnostics["replication"]["details"].append(
                            f"✅ deletionStrategy is '{deletion_strategy.value}'"
                        )
                    else:
                        collection_diagnostics["replication"]["details"].append(
                            f"ℹ️ deletionStrategy: {deletion_strategy}"
                        )

                replication_factor = getattr(replication_config, "factor", 1)
                if replication_factor == 1:
                    if collection_diagnostics["replication"]["status"] == "ok":
                        collection_diagnostics["replication"]["status"] = "warning"
                    collection_diagnostics["replication"]["details"].append(
                        "⚠️ WARNING: Replication factor is 1 (no replication)"
                    )
                elif replication_factor % 2 == 0:
                    if collection_diagnostics["replication"]["status"] == "ok":
                        collection_diagnostics["replication"]["status"] = "warning"
                    collection_diagnostics["replication"]["details"].append(
                        f"⚠️ WARNING: Replication factor is {replication_factor} (even number). RAFT consensus works best with odd numbers (3, 5, 7)."
                    )
                else:
                    collection_diagnostics["replication"]["details"].append(
                        f"✅ Replication factor is {replication_factor}"
                    )
            else:
                collection_diagnostics["replication"]["details"].append("ℹ️ No replication configuration found")

            diagnostics["all_checks"].append(collection_diagnostics)

        return diagnostics

    except Exception as e:
        logger.error(f"Error in diagnose_schema: {e}")
        return {"error": f"Failed to run schema diagnostics: {e}"}


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

        node_data.append({
            "Node Name": node.name,
            "Git Hash": node.git_hash,
            "Version": node.version,
            "Status": node.status,
            "Object Count (Stats)": node.stats.object_count,
            "Shard Count (Stats)": node.stats.shard_count,
        })

        collection_counts = {}

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

            if hasattr(shard, "vector_indexing_status") and shard.vector_indexing_status == "READONLY":
                readonly_shards.append(shard_info)

            collection_counts[shard.collection] = collection_counts.get(shard.collection, 0) + 1

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


# Check consistency of shard object counts across nodes. Returns a DataFrame of inconsistencies, or None if consistent.
def check_shard_consistency(node_info):
    logger.info("check_shard_consistency() called")
    shard_data = defaultdict(list)
    for node in node_info:
        for shard in node.shards:
            shard_key = (shard.collection, shard.name)
            shard_data[shard_key].append((node.name, shard.object_count))

    inconsistent_shards = []
    for (collection, shard_name), details in shard_data.items():
        object_counts = [obj_count for _, obj_count in details]
        if len(set(object_counts)) > 1:
            for node_name, object_count in details:
                inconsistent_shards.append({
                    "Collection": collection,
                    "Shard": shard_name,
                    "Node": node_name,
                    "Object Count": object_count,
                })

    if inconsistent_shards:
        return pd.DataFrame(inconsistent_shards)

    return None


# Get cluster statistics
def get_cluster_statistics():
    logger.info("get_cluster_statistics() called")
    client = get_weaviate_client()
    return client.cluster.statistics()


# Process cluster statistics data
def process_statistics(stat):
    logger.info("process_statistics() called")
    if stat is None:
        return {"error": "Failed to fetch cluster statistics."}

    flattened_data = []
    latest_config_data = []
    network_info = []
    synchronized = stat.synchronized

    for node in stat.statistics:
        base_data = {
            "Node Name": node.name,
            "Leader ID": node.leader_id,
            "Leader Address": node.leader_address,
            "State": node.raft.state,
            "Status": node.status,
            "Ready": node.ready,
            "DB Loaded": node.db_loaded,
            "Open": node.is_open,
            "Is Voter": node.is_voter,
            "Applied Index": node.raft.applied_index,
            "Commit Index": node.raft.commit_index,
            "Last Contact": node.raft.last_contact,
            "Last Log Index": node.raft.last_log_index,
            "Last Log Term": node.raft.last_log_term,
            "Initial Last Applied Index": node.initial_last_applied_index,
            "Num Peers": node.raft.num_peers,
            "Term": node.raft.term,
            "FSM Pending": node.raft.fsm_pending,
            "Last Snapshot Index": node.raft.last_snapshot_index,
            "Last Snapshot Term": node.raft.last_snapshot_term,
            "Protocol Version": node.raft.protocol_version,
            "Protocol Version Max": node.raft.protocol_version_max,
            "Protocol Version Min": node.raft.protocol_version_min,
            "Snapshot Version Max": node.raft.snapshot_version_max,
            "Snapshot Version Min": node.raft.snapshot_version_min,
        }
        flattened_data.append(base_data)

        if node.raft.latest_configuration:
            for member in node.raft.latest_configuration:
                address = str(member.address) if member.address else "N/A"
                if ":" in address:
                    ip, port = address.rsplit(":", 1)
                    network_info.append({
                        "Pod": str(member.node_id) if member.node_id else "N/A",
                        "IP": ip,
                        "Port": port
                    })
                config_data = {
                    "Node Name": node.name,
                    "Node State": node.raft.state,
                    "Peer ID": str(member.node_id) if member.node_id else "N/A",
                    "Peer Address": address,
                    "Peer Suffrage": str(member.suffrage) if member.suffrage else "N/A",
                }
                latest_config_data.append(config_data)

    df_data = pd.DataFrame(flattened_data).fillna("N/A")
    df_config = pd.DataFrame(latest_config_data).fillna("N/A") if latest_config_data else pd.DataFrame()
    df_network = pd.DataFrame(network_info).drop_duplicates().fillna("N/A") if network_info else pd.DataFrame()

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

        general_metadata = {
            key: str(value) for key, value in metadata.items() if key != "modules"
        }
        general_metadata_df = pd.DataFrame(general_metadata.items(), columns=["Key", "Value"])

        modules_data = metadata.get("modules", {})
        standard_modules = []
        other_modules = []

        for module_name, module_details in modules_data.items():
            if isinstance(module_details, dict):
                if "name" in module_details and "documentationHref" in module_details:
                    standard_modules.append({
                        "Module": str(module_name),
                        "Name": str(module_details.get("name", "N/A")),
                        "Documentation": str(module_details.get("documentationHref", "N/A"))
                    })
                else:
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
