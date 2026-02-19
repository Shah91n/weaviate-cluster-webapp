# Weaviate Cluster Operations

[![Weaviate](https://img.shields.io/static/v1?label=for&message=Weaviate%20%E2%9D%A4&color=green&style=flat-square)](https://weaviate.io/)
[![GitHub Repo stars](https://img.shields.io/github/stars/Shah91n/WeaviateDB-Cluster-WebApp?style=social)](https://github.com/Shah91n/WeaviateDB-Cluster-WebApp)
[![Streamlit App](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://weaviatecluster.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python&logoColor=white)](https://python.org)

Interact with and manage Weaviate Cluster operations. This app provides tools to inspect shards, view collections & tenants, explore schemas, analyze cluster statistics, and interact with objects.

<a href="https://weaviatecluster.streamlit.app/">
  Visit Weaviate Cluster WebApp
</a>

<img width="1840" height="793" alt="image" src="https://github.com/user-attachments/assets/f15cc87a-b1b6-4d79-8964-0d2068760466" />

## Features

### Connection
- **Local**
- **Custom**
- **Cloud**

#### Vectorization
- Weaviate Vectorizer
- Support for OpenAI, Cohere, HuggingFace
- Add API keys for vectorization providers (optional)
- Vectorization during object updates

### Cluster Management
- **Shards & Nodes**
  - View shard details across nodes
  - View node details
  - Update read-only shards to READY status (⚠️ Admin API-Key required)

- **Collections & Tenants**
  - View collections and their tenants
  - Aggregate Collections & Tenants
    - With Data cached
  - Explore collection configurations
  - View schema configuration
  - Analyze cluster statistics and synchronization
  - View cluster metadata & modules
  - Analyze shard consistency
  - Force repair collection objects across nodes
  - Run schema diagnostics

### RBAC
  - View all users and their roles
  - View all roles and their permission types
  - View all permissions in detail
  - Users & Permissions Report

### **Multi Tenancy**
  - View MT collections only and configurations
    - With Data cached
  - Analyze tenants in the collection and states
  
### Object Operations
- **Create** (⚠️ Admin API-Key required)
  - Create new collections
  - Supported Vectorizers (OpenAI, Cohere, HuggingFace)
  - Batch upload data from CSV/JSON files

- **Search**
  - Hybrid search combining vector and keyword capabilities
  - Keyword search (BM25) for exact matches
  - Vector Search for similarity
  - Adjustable alpha parameter (0.0-1.0) for hybrid search balance
  - Performance metrics
  - Detailed result metadata (scores, distances, timing)
  - Support for all vectorized collections

- **Read**
  - View object data in collections/tenants
  - Display data in tables including vectors
    - With Data cached
  - Download data as CSV files

- **Update** (⚠️ Admin API-Key required)
  - Edit collection configuration with support for all mutable parameters
  - Update objects with optional vectorization
  - Export object data to CSV format
  - Verify object consistency across cluster nodes (supports up to 11 nodes)
  - Real-time object validation and error handling

- **Delete** (⚠️ Admin API-Key required)
  - Delete collections and tenants
  - Batch deletion support for multiple collections/tenants

### Agent
Ask natural language questions across one or more collections via the Agents API.

Requirement: install the extra: `weaviate-client[agents]`.

UI Flow:
1. Open Agent page.
2. Select one or multiple collections.
3. Enter question + optional system prompt / host / timeout.
4. Run and inspect Answer, Structured Sections.

## Configuration

### How to Run It on Your Local Machine

**Prerequisites**

- Python 3.10 or higher
- pip installed

**Steps to Run**

1. **Clone the repository:**

    ```bash
    git clone https://github.com/Shah91n/WeaviateCluster.git
    cd WeaviateCluster
    ```

2. **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Run the app:**

    ```bash
    streamlit run streamlit_app.py
    ```

If you haven't already created a `requirements.txt` file, here's what it should look like:

```text
streamlit
weaviate-client
weaviate-client[agents]
requests
pandas
Pillow
```

Or You can also run the Weaviate Cluster using Docker. Follow the steps below to build the Docker image and run the container:

1. **Clone the repository:**

    ```bash
    git clone https://github.com/Shah91n/WeaviateCluster.git
    cd WeaviateCluster
    ```

2. **Build the Docker image:**

    ```bash
    docker build -t weaviateclusterapp:latest .
    ```

3. **Run the Docker container:**

    ```bash
    docker run -p 8501:8501 --add-host=localhost:host-gateway weaviateclusterapp
    ```

This will start the Weaviate Cluster, and you can access it by navigating to `http://localhost:8501` in your web browser.

### How to Run It on a Cloud Cluster

1. Provide the Weaviate endpoint.
2. Provide the API key.
3. Connect and enjoy!

### Notes

This is a personal project and is not officially approved by the Weaviate organization. While functional, the code may not follow all best practices for Python programming or Streamlit. Suggestions and improvements are welcome!

**USE AT YOUR OWN RISK**: While this tool is designed for cluster operation and analysis, there is always a possibility of unknown bugs.

### Contributing

Contributions are welcome through pull requests! Suggestions for improvements and best practices are highly appreciated.
