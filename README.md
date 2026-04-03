# Weaviate Cluster Operations

[![Weaviate](https://img.shields.io/static/v1?label=for&message=Weaviate%20%E2%9D%A4&color=green&style=flat-square)](https://weaviate.io/)
[![GitHub Repo stars](https://img.shields.io/github/stars/Shah91n/WeaviateDB-Cluster-WebApp?style=social)](https://github.com/Shah91n/WeaviateDB-Cluster-WebApp)
[![Streamlit App](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://weaviatecluster.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white)](https://python.org)

A lightweight Streamlit web app built for developers who need a quick, visual way to manage and understand their Weaviate cluster. It's designed for **development, staging, and testing environments** — not for production-scale use.

Use it to look up data, browse collections, diagnose schema health, inspect cluster state, and understand how your Weaviate instance is configured. It covers the basics well: general data lookup, collection analysis, replication and compression checks, RBAC inspection, and multi-tenancy browsing — all without writing a single query.

<a href="https://weaviatecluster.streamlit.app/">
  Visit Weaviate Cluster WebApp (It's recommended to run it locally, do not use it on Streamlit cloud)
</a>

<img width="1900" height="872" alt="image" src="https://github.com/user-attachments/assets/3ae3a762-a5d8-48dd-8253-5bf3a30945f5" />

## Features

### Connection
Connect via three modes — all with optional vectorizer API key injection:
- **Local** — Weaviate running on `localhost` (configurable HTTP/gRPC ports)
- **Custom** — Any reachable Weaviate host with full HTTP/gRPC control
- **Cloud** — Weaviate Cloud cluster via URL + API key
- **Auto-Connect via URL params** — `?endpoint=<URL>&api_key=<KEY>`

Vectorizer integrations: OpenAI, Cohere, HuggingFace (keys injected as request headers at connect time).

### Cluster Management
- **Nodes & Shards** — View node details, shard info, set read-only shards to READY (⚠️ requires admin key)
- **Aggregate Collections & Tenants** — Object counts, empty collection/tenant detection
- **Collection Properties** — Schema and property details per collection
- **Collections Configuration** — Full collection config (vectorizer, index, module, replication)
- **Raft Statistics** — RAFT consensus state, peer network, synchronization status
- **Metadata** — Server version, enabled modules
- **Diagnose** — Schema health checks (compression, replication factor, deletion strategy, shard consistency)

### RBAC
- Users, roles, permissions — individual and combined report views

### Multi-Tenancy
- Filter MT-only collections, view config, list tenants with activity states

### Object Operations
- **Create** — Create collections (5 vectorizers + BYOV), batch upload from CSV/JSON (⚠️ admin key required)
- **Read** — Paginated object browser up to 1 000 objects, supports tenants, includes vectors
- **Search** — Hybrid (BM25 + vector), keyword (BM25), and near-vector search with named-vector support, alpha tuning, and performance metrics
- **Update** — Edit collection config (inverted index, replication, HNSW, PQ) and patch individual objects with type-aware field editors (⚠️ admin key required)
- **Delete** — Delete one or more collections or tenants (⚠️ admin key required)

### Agent
Natural language Q&A over collections via the Weaviate Agents API.
Requires `weaviate-client[agents]` (included in `requirements.txt`).

### Backup
List the 10 most recent backups stored in the cluster's cloud storage backend (S3, GCS, or Azure Blob Storage).
The storage backend is auto-detected from the connected endpoint URL (`aws` → S3, `gcp` → GCS, `azure` → Azure).
Displays: Backup ID, Status, Started At, Completed At, Size (GB), Collections included.

---

## Architecture

```
streamlit_app.py               Entrypoint — connection UI + cluster dashboard
core/                          Business logic (no Streamlit imports)
  connection/                  Singleton client manager + init helpers
  cluster/                     Nodes/shards, RAFT statistics, metadata, diagnostics (SDK only)
  collection/                  Collection listing, schema, config fetch/processing, create, delete, update
  object/                      Read and update individual objects
  search/                      Hybrid, keyword, vector search
  multitenancy/                Tenant listing and state aggregation
  rbac/                        Users, roles, permissions
  agents/                      QueryAgent wrapper
  backup/                      Backup listing with auto-detected storage backend
pages/                         Streamlit UI (one file per feature)
  cluster/                     Cluster dashboard action handlers
  utils/                       Navigation, page config, session helpers
assets/                        Static files (logo)
```

**Core layer** (`core/`) contains only pure business logic — no `st.*` calls ever.  
**Pages layer** (`pages/`) contains only UI — no direct Weaviate SDK calls.  
The singleton in `core/connection/weaviate_connection_manager.py` maintains one long-lived client per session.

---

## Setup

### Prerequisites
- Python 3.10+
- A running Weaviate instance (local, custom, or cloud)

### Install & Run
```bash
git clone https://github.com/Shah91n/WeaviateDB-Cluster-WebApp.git
cd WeaviateDB-Cluster-WebApp
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Docker
```bash
docker build -t weaviateclusterapp:latest .
docker run -p 8501:8501 --add-host=localhost:host-gateway weaviateclusterapp
```

Access the app at `http://localhost:8501`.

### Local Weaviate (for testing)
```bash
docker run -p 8080:8080 -p 50051:50051 cr.weaviate.io/semitechnologies/weaviate:latest
```

---

## Notes

- This is a community project, not an official Weaviate product.
- Read page caps at **1 000 objects** via the iterator API.
- All cluster operations use the Weaviate Python client.
- **USE AT YOUR OWN RISK** — always use an admin key only in trusted environments.

## Contributing

Pull requests and suggestions are welcome!

