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
streamlit_app.py                     Entrypoint/router — session state, page config,
                                     connection UI, st.navigation
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
                                     batch_upload() [generator, server-side streaming],
                                     get_collection_info(), get_collection_objects(),
                                     sanitize_keys()
    delete.py                        delete_all_collections(), delete_collections(),
                                     delete_tenants_from_collection()
    update_collection_config.py      get_collection_config(), update_description_and_inverted_index(),
                                     update_multi_tenancy_and_replication()
    vector_index.py                  describe_vector_indexes(), update_vector_index(),
                                     build_index_update(), MUTABLE_INDEX_FIELDS,
                                     MUTABLE_QUANTIZER_FIELDS, QUANTIZERS_BY_INDEX
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
    navigation.py                    build_navigation() — st.navigation, NAV_SECTIONS
    helper.py                        update_side_bar_labels(), clear_session_state()
    page_config.py                   configure_app() [entrypoint only], page_header()
    ui.py                            require_connection(), section(), metric_row(),
                                     kv_table(), data_table(), status_line(),
                                     status_callout(), admin_warning(), download_list()
  cluster_dashboard.py               Cluster dashboard page (default page, served at /)
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
- **Entrypoint / router** (`streamlit_app.py`) — Session state init, the single `st.set_page_config`,
  auto-connect from URL params, the connection sidebar, and `st.navigation(...).run()`. It is not a
  page: it runs on every rerun as the frame around the active page.
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

All modes accept optional vectorizer keys (`X-OpenAI-Api-Key`, `X-Cohere-Api-Key`) passed as `headers` at connect time.

All connections use `skip_init_checks=True` and `Timeout(init=90, query=900, insert=900)`.

---

## Session State Keys (set in `streamlit_app.py`)

| Key | Purpose |
|---|---|
| `client_ready` | `bool` — connection established |
| `active_endpoint` | Connected cluster URL |
| `active_api_key` | Connected API key |
| `active_openai_key` / `active_cohere_key` | Vectorizer keys in-use |
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

### Presentation
- Headings, KPI rows, config tables and status lines come from `pages/utils/ui.py` — do not
  hand-roll `st.dataframe(df.astype(str))` or ad-hoc `st.markdown("###### ...")` headings
- Theme lives in `.streamlit/config.toml`. The rule it encodes: **colour is a status
  channel, not decoration** — chrome (sidebar, panels, borders) is achromatic, and
  saturation is reserved for the active page, primary actions and health states.
  Streamlit's stock yellow/blue alert colours are deliberately muted so a real warning
  is the loudest thing on screen. Fonts are system stacks: no webfont dependency
- Destructive actions are confirmed with `st.dialog`, long operations use `st.status`

### Vector Index Configuration
All reads and writes of vector index config go through `core/collection/vector_index.py`.
It normalises the two collection layouts (named vectors under `vector_config` vs. the legacy
single vector under `vector_index_config`) and all four index types (`hnsw`, `flat`,
`dynamic`, `hfresh`) into `VectorIndexInfo` objects.

- **Never hardcode `"hnsw"`.** Read the type from `VectorIndexInfo.index_type`, which comes
  from the SDK's own `vic.vector_index_type()`.
- A `dynamic` index has **no `.quantizer` attribute** — its quantizers live under
  `.hnsw.quantizer` and `.flat.quantizer`. `VectorIndexInfo.scopes` / `.quantizer_for(scope)`
  handle this; reading `vic.quantizer` directly reports "no compression" on a compressed
  collection.
- Quantizer **type** is immutable after creation; only its mutable fields can change.
- `flat` compression is immutable after creation; `hfresh` RQ is mandatory and always on.
- Named-vector collections update via `vector_config=Reconfigure.Vectors.update(...)`;
  legacy collections via `vectorizer_config=` (the only parameter that accepts a dynamic update).
- Quantizer updates on an index whose config has no `pq` key (HFresh) need
  **weaviate-client > 4.23.0**; 4.23.0 reads `vector_index_config["pq"]` unguarded in
  `_CollectionConfigUpdate.__check_quantizers` and raises `KeyError('pq')`.

### Logging
- Use `logging.getLogger(__name__)` in every module
- `logger.info()` at function entry points, `logger.error()` for caught exceptions, `logger.debug()` for hot-path helpers
- **Never** use `print()` for operational logging

### Error Handling
- `core/` functions return `(bool, str)` or `(bool, str, data)` tuples on failure paths, or raise `Exception` with a descriptive message
- **Never turn a read failure into an empty result.** `list_collections()`, `get_schema()` and
  `fetch_collection_config()` raise; returning `[]`/`{}`/`None` renders a permissions or
  connection error as "no collections", which is indistinguishable from an empty cluster.
  Pages call them through `ui.load(reader, ...)`, which shows the error and stops the page
- `aggregate_collections()` always returns a dict (see `_empty_aggregate()`), never `None`
- Pages catch exceptions and display them via `st.error()`
- `batch_upload()` in `create.py` is a **generator** — it `yield`s `(ok, message, payload)` tuples for
  real-time progress; `payload` is `None`, a `{queued, total}` progress dict, or the final summary dict

## Navigation

`st.navigation` + `st.Page`, built in `pages/utils/navigation.py`. Because `st.navigation` is
used, Streamlit ignores `pages/` as an implicit page source — every page is declared there.

**While disconnected, only the Cluster page is offered.** The rest appear once `client_ready`
is set. That is an affordance, not a guard: every page still calls `ui.require_connection()`,
which `st.stop()`s the body.

**Do not set `client.showSidebarNavigation = false`** in `.streamlit/config.toml`. It sets
`hide_sidebar_nav` on the frontend, which hides the `st.navigation` menu — every page link
disappears. It was only ever needed to suppress the legacy `pages/` auto-navigation, and
`st.navigation` already does that.

Page rules:
- A page is a plain script ending in a bare `main()` call — **no** `if __name__ == "__main__"`,
  and `streamlit run pages/<x>.py` is no longer supported. Run `streamlit run streamlit_app.py`.
- A page must **not** call `st.set_page_config` — the router owns it. Use `page_header(title)`.
- A page must **not** call `update_side_bar_labels()` — the router does it once.
- `pages/cluster_dashboard.py` is named that way so it cannot shadow the `pages/cluster/`
  handlers package. As the default page it is served at the app root.

Grouped by task:

```
EXPLORE
  🔍  Cluster                     streamlit_app.py
  🔐  Role-Based Access Control   pages/rbac.py
  📄  Multi Tenancy               pages/multitenancy.py
  💾  Backup                      pages/backup.py
QUERY
  🤖  Agent                       pages/agent.py
  🧐  Search                      pages/search.py
MANAGE
  ➕  Create                      pages/create.py
  📁  Read                        pages/read.py
  🗃️  Update                      pages/update.py
  🗑️  Delete                      pages/delete.py
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
- Supported vectorizers: `text2vec_weaviate`, `text2vec_openai`, `text2vec_cohere`, `BYOV`
- Collections are created with `replication_config=Configure.replication(3)` by default
- Batch upload accepts CSV or JSON; property keys are sanitized (non-alphanumeric → `_`)
- UUIDs are deterministic via `generate_uuid5(obj)`
- Import uses **server-side batching only** (`client.batch.stream()`, Weaviate 1.36+), which lets
  the server set the pace via backpressure. No client-side batching fallback — deliberate
- `batch_upload()` yields progress roughly every 1% of the file and aborts past `max_errors`
  insert failures; the final yield carries a summary dict (mode, counts, failed objects)

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

### Update (`pages/update.py` / `core/collection/update_collection_config.py` / `core/collection/vector_index.py` / `core/object/update_object.py`)
- **Object update** — fetch by UUID (with optional tenant), type-aware field editors, `collection.data.update()` PATCH
- **Collection config update** — description + inverted index, multi-tenancy + replication, and a
  vector index editor whose fields are driven by the collection's actual index type (⚠️ admin key required)

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
- **Compression** — via `describe_vector_indexes()`, so dynamic indexes report the quantizer on
  each of their hnsw/flat arms and HFresh reports its built-in RQ
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

No pytest suite. Pages are smoke-tested headlessly with `streamlit.testing.v1.AppTest`
against a live cluster: initialise from `streamlit_app.py` (the router) and use
`AppTest.switch_page("pages/<x>.py")` to reach each page. Test both connection states, and
discover collection names from the client rather than hardcoding them.

---

## Important Notes
- This app is for **development, staging, and troubleshooting** — not production scale.
- Operations marked ⚠️ require an admin API key: shard READY fix, create, update, delete.
- Aggregation and read data is cached in session state for an hour; clear it via Streamlit Developer Options or Disconnect → Reconnect.
- The Disconnect button clears **all** session state keys and `st.cache_data`, then calls `st.rerun()`.
