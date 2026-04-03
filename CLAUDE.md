# Weaviate Cluster WebApp — Agent Reference

## Stack & Dependencies

| Item | Detail |
|---|---|
| Language | Python 3.10+ |
| Framework | Streamlit |
| Database | Weaviate |
| Key packages | `streamlit`, `weaviate-client`, `weaviate-client[agents]`, `pandas`, `Pillow`, `requests` |

## Quick Start

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Docker

```bash
docker build -t weaviateclusterapp:latest .
docker run -p 8501:8501 --add-host=localhost:host-gateway weaviateclusterapp
```

## Project Structure

```
streamlit_app.py                     App entrypoint — connection UI + cluster dashboard
core/                                Business logic only — no Streamlit imports
  connection/
    weaviate_connection_manager.py   WeaviateConnectionManager singleton + get_weaviate_manager() / get_weaviate_client()
    weaviate_client.py               initialize_weaviate_connection() / disconnect_weaviate()
  cluster/
    cluster_health.py                diagnose_schema(), get_shards_info(), process_shards_data(),
                                     check_shard_consistency(), get_cluster_statistics(),
                                     process_statistics(), get_metadata()
  collection/
    overview.py                      aggregate_collections(), list_collections(), get_schema(),
                                     fetch_collection_config(), process_collection_config()
    create.py                        get_supported_vectorizers(), validate_file_format(),
                                     check_vectorizer_keys(), create_collection(),
                                     batch_upload() [generator], get_collection_info(),
                                     get_collection_objects(), sanitize_keys()
    delete.py                        delete_all_collections(), delete_collections(),
                                     delete_tenants_from_collection()
    update_collection_config.py      get_collection_config(), update_description_and_inverted_index(),
                                     update_multi_tenancy_and_replication(),
                                     update_hnsw_vector_index(), update_pq_quantizer()
  object/
    read.py                          get_tenant_names(), read_objects_batch() [iterator, 1 000 cap]
    update_object.py                 get_object_in_collection(), get_object_in_tenant(),
                                     display_object_as_table(), update_object_properties()
  search/
    hybrid.py                        hybrid_search(), hybrid_search_with_multiple_vectors()
    keyword.py                       keyword_search()
    vector.py                        vector_search(), vector_search_with_multiple_vectors(),
                                     parse_vector_input()
  multitenancy/
    tenantdetails.py                 get_tenant_details(), aggregate_tenant_states()
  rbac/
    read.py                          list_all_users(), list_all_roles(), list_all_permissions(),
                                     list_users_roles_permissions_combined()
  agents/
    query_agent.py                   run_query_agent(), capture_display(), sanitize_display(),
                                     strip_ansi(), extract_known_fields()
  backup/
    list.py                          detect_backup_storage(), get_backup_backend_label(),
                                     list_backups() [top 10 most recent]
pages/                               Streamlit UI — one file per feature, no SDK calls
  cluster/
    cluster_operations_handlers.py  action_nodes_and_shards(), action_aggregate_collections_tenants(),
                                     action_collection_schema(), action_collections_configuration(),
                                     action_statistics(), action_metadata(), action_diagnose()
  utils/
    navigation.py                    navigate() — sidebar nav + logo
    helper.py                        update_side_bar_labels(), clear_session_state()
    page_config.py                   set_custom_page_config()
  agent.py                           QueryAgent natural-language Q&A UI
  backup.py                          Backup list page (auto-detected S3/GCS/Azure backend)
  create.py                          Create collection + batch upload (CSV/JSON)
  delete.py                          Delete collections and/or tenants
  multitenancy.py                    Multi-tenancy browser — config + tenant details
  rbac.py                            RBAC report — users, roles, permissions, combined report
  read.py                            Paginated object browser (1 000 obj cap, 100/page)
  search.py                          Hybrid / keyword / vector search with named-vector support
  update.py                          Update object properties + collection config
assets/                              Static files (weaviate-logo.png)
```

---

## Architecture

### Layers
- **Entrypoint** (`streamlit_app.py`) — Session state init, connection widgets, auto-connect from URL params, cluster dashboard buttons.
- **Core layer** (`core/`) — Pure business logic. **No `st.*` calls ever.** Each module calls `get_weaviate_client()` from the connection manager.
- **Pages layer** (`pages/`) — Streamlit UI only. **No direct Weaviate SDK calls.** Pages call `core/` functions and render results.
- **Utils layer** (`pages/utils/`) — Shared Streamlit helpers: navigation sidebar, page config, session helpers.

### Connection Manager (`core/connection/weaviate_connection_manager.py`)
Thread-safe singleton pattern. ONE long-lived `WeaviateClient` per session.

```python
from core.connection.weaviate_connection_manager import get_weaviate_client
client = get_weaviate_client()  # always returns the same instance
```

**Never close the client after a single operation.** `disconnect()` is only called during full app disconnect.

The manager also exposes `get_weaviate_manager()` when you need metadata (`get_endpoint()`, `get_api_key()`, `is_ready()`).

---

## Connection Modes

| Mode | SDK call |
|---|---|
| Cloud | `weaviate.connect_to_weaviate_cloud(cluster_url, auth_credentials, ...)` |
| Local | `weaviate.connect_to_local(port, grpc_port, ...)` |
| Custom | `weaviate.connect_to_custom(http_host, http_port, grpc_host, grpc_port, http_secure, grpc_secure, ...)` |

All modes accept optional vectorizer keys (`X-OpenAI-Api-Key`, `X-Cohere-Api-Key`, `X-HuggingFace-Api-Key`) passed as `headers` at connect time.

All connections use `skip_init_checks=True` and `Timeout(init=90, query=900, insert=900)`.

---

## Session State Keys (set in `streamlit_app.py`)

| Key | Purpose |
|---|---|
| `client_ready` | `bool` — connection established |
| `active_endpoint` | Connected cluster URL |
| `active_api_key` | Connected API key |
| `active_openai_key` / `active_cohere_key` / `active_huggingface_key` | Vectorizer keys in-use |
| `server_version` | Weaviate server version string |
| `use_local` / `use_custom` | Connection mode flags |
| `auto_connect_attempted` | Guards single auto-connect from URL params |

Page-level keys are initialized in each page's `initialize_session_state()` or `_ensure_state()` before any widget reads them.

---

## Key Conventions

### Separation of Concerns
- Business logic → `core/`
- Streamlit UI → `pages/` and `streamlit_app.py`
- **Never** import `streamlit` inside `core/`
- **Never** call the Weaviate SDK directly inside a page file — always delegate to a `core/` function

### Logging
- Use `logging.getLogger(__name__)` in every module
- `logger.info()` at function entry points, `logger.error()` for caught exceptions, `logger.debug()` for hot-path helpers
- **Never** use `print()` for operational logging

### Error Handling
- `core/` functions return `(bool, str)` or `(bool, str, data)` tuples on failure paths, or raise `Exception` with a descriptive message
- Pages catch exceptions and display them via `st.error()`
- `batch_upload()` in `create.py` is a **generator** — it `yield`s `(bool, message, None)` tuples for real-time progress feedback

## Sidebar Navigation (in order)

```
🔍  Cluster             streamlit_app.py
🔐  Role-Based Access Control   pages/rbac.py
📄  Multi Tenancy       pages/multitenancy.py
🤖  Agent               pages/agent.py
🧐  Search              pages/search.py
➕  Create              pages/create.py
📁  Read                pages/read.py
🗃️  Update              pages/update.py
🗑️  Delete              pages/delete.py
💾  Backup              pages/backup.py
```

---

## Feature Notes

### Cluster Dashboard (`streamlit_app.py` + `pages/cluster/cluster_operations_handlers.py`)
Seven buttons map to action functions:
- **Aggregate Collections & Tenants** — object counts, empty collection/tenant detection
- **Collection Properties** — schema + property table for a selected collection
- **Collections Configuration** — full config (vectorizer, HNSW, PQ, replication) for a selected collection
- **Nodes & Shards** — node details, shard table, shard-per-collection counts, read-only shard detection + one-click READY fix (⚠️ admin key required)
- **Raft Statistics** — RAFT consensus state, peer network, synchronization sync status
- **Metadata** — server version + enabled modules
- **Diagnose** — shard consistency check + per-collection compression/replication diagnostics with CSV export

### Create (`pages/create.py` / `core/collection/create.py`)
- Supported vectorizers: `text2vec_weaviate`, `text2vec_openai`, `text2vec_huggingface`, `text2vec_cohere`, `BYOV`
- Collections are created with `replication_config=Configure.replication(3)` by default
- Batch upload accepts CSV or JSON; property keys are sanitized (non-alphanumeric → `_`)
- UUIDs are deterministic via `generate_uuid5(obj)`
- Upload is a streaming generator — UI shows live per-object progress

### Read (`pages/read.py` / `core/object/read.py`)
- Caps at **1 000 objects** using the iterator API
- Paginated: 100 items/page, max 10 pages
- Supports tenant scoping and optional vector inclusion

### Search (`pages/search.py`)
- Hybrid: BM25 + vector, configurable `alpha` (0.0–1.0)
- Keyword: BM25 only
- Vector: `near_vector` — accepts comma-separated float list; named-vector (`target_vector`) supported
- All modes return score/distance/metadata columns + timing (ms)
- Named vectors auto-detected from `collection.vector_config`

### Update (`pages/update.py` / `core/collection/update_collection_config.py` / `core/object/update_object.py`)
- **Object update** — fetch by UUID (with optional tenant), type-aware field editors, `collection.data.update()` PATCH
- **Collection config update** — description + inverted index, multi-tenancy + replication, HNSW, PQ quantizer (⚠️ admin key required)

### RBAC (`pages/rbac.py` / `core/rbac/read.py`)
Four views: Users, Roles, Permissions (flat), combined User-Permissions report.
Uses `client.users.db.list_all()` and `client.roles.list_all()`.

### Backup (`pages/backup.py` / `core/backup/list.py`)
- Storage backend auto-detected from endpoint URL: `aws` → S3, `gcp` → GCS, `azure` → Azure Blob Storage
- Lists the 10 most recent backups (`list_backups(limit=10)`)
- Columns: Backup ID, Status, Started At, Completed At, Size (GB), Collections

### Agent (`pages/agent.py` / `core/agents/query_agent.py`)
- Requires `weaviate-client[agents]` (included in `requirements.txt`)
- `QueryAgent` from `weaviate.agents.query` is lazy-imported; a clear `RuntimeError` is raised if the extra is missing
- Supports multi-collection selection, optional system prompt, agents host override, timeout
- Response rendered via `capture_display()` → `sanitize_display()` (strips ANSI codes + box-drawing artifacts)

### Diagnose (`core/cluster/cluster_health.py` → `action_diagnose`)
Checks per collection:
- **Compression** — inspects `quantizer` on named vector configs or single `vector_index_config`
- **Replication** — `asyncEnabled`, `deletionStrategy` (flags `NoAutomatedResolution` as CRITICAL), replication factor (warns on 1 or even numbers)
- **Shard consistency** — compares object counts for the same shard across all nodes; flags mismatches

---

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Start the app
streamlit run streamlit_app.py

# Local Weaviate for testing
docker run -p 8080:8080 -p 50051:50051 cr.weaviate.io/semitechnologies/weaviate:latest
```

No automated test suite. Manual verification against a live Weaviate instance.

---

## Important Notes
- This app is for **development, staging, and troubleshooting** — not production scale.
- Operations marked ⚠️ require an admin API key: shard READY fix, create, update, delete.
- Aggregation and read data is cached in session state for an hour; clear it via Streamlit Developer Options or Disconnect → Reconnect.
- The Disconnect button clears **all** session state keys and `st.cache_data`, then calls `st.rerun()`.
