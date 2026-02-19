import csv
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from weaviate import Client
from weaviate.util import generate_uuid5
from weaviate.classes.config import Configure
from utils.cluster.cluster_operations import get_schema
import streamlit as st
import re

# Supported vectorizers
def get_supported_vectorizers() -> List[str]:
	print("get_supported_vectorizers() called")
	return ["text2vec_weaviate", "text2vec_openai", "text2vec_huggingface", "text2vec_cohere", "BYOV"]

# Validate file format
def validate_file_format(file_content: str, file_type: str) -> tuple[bool, str, Optional[List[Dict[str, Any]]]]:
	print("validate_file_format() called")
	try:
		if file_type == "csv":
			# Try to parse CSV
			csv_reader = csv.DictReader(file_content.splitlines())
			headers = csv_reader.fieldnames
			if not headers:
				return False, "CSV file has no headers", None
			data = list(csv_reader)
			if not data:
				return False, "CSV file is empty", None
			return True, "Valid CSV format", data
		elif file_type == "json":
			# Try to parse JSON
			data = json.loads(file_content)
			if not isinstance(data, list):
				return False, "JSON must be an array of objects", None
			if not data:
				return False, "JSON array is empty", None
			if not all(isinstance(item, dict) for item in data):
				return False, "All JSON elements must be objects", None
			return True, "Valid JSON format", data
		else:
			return False, f"Unsupported file type: {file_type}", None
	except Exception as e:
		return False, f"Error parsing file: {str(e)}", None

# Check if required API keys are present for the selected vectorizer
def check_vectorizer_keys(vectorizer: str) -> tuple[bool, str]:
	print(f"check_vectorizer_keys() called with vectorizer: {vectorizer}")
	if vectorizer == "text2vec_openai" and not st.session_state.get("active_openai_key"):
		return False, "OpenAI API key is required. Please reconnect with the key or select BYOV."
	elif vectorizer == "text2vec_cohere" and not st.session_state.get("active_cohere_key"):
		return False, "Cohere API key is required for text2vec_cohere. Please reconnect with the key or select BYOV."
	elif vectorizer == "text2vec_huggingface" and not st.session_state.get("active_huggingface_key"):
		return False, "HuggingFace API key is required. Please reconnect with the key or select BYOV."
	return True, ""

# Create a new collection
def create_collection(client: Client, collection_name: str, vectorizer: str) -> tuple[bool, str]:
	print(f"create_collection() called with collection_name: {collection_name}, vectorizer: {vectorizer}")
	try:
		# Check if collection already exists
		if client.collections.exists(collection_name):
			return False, f"Collection '{collection_name}' already exists"

		# Check if required API keys are present
		has_keys, key_message = check_vectorizer_keys(vectorizer)
		if not has_keys:
			return False, key_message

		# Configure vectorizer
		if vectorizer == "text2vec_weaviate":
			vector_config = Configure.Vectors.text2vec_weaviate()
		elif vectorizer == "text2vec_openai":
			vector_config = Configure.Vectors.text2vec_openai()
		elif vectorizer == "text2vec_huggingface":
			vector_config = Configure.Vectors.text2vec_huggingface()
		elif vectorizer == "text2vec_cohere":
			vector_config = Configure.Vectors.text2vec_cohere()
		elif vectorizer == "BYOV":
			vector_config = Configure.Vectors.self_provided()
		# Create collection
		client.collections.create(
			name=collection_name,
			vector_config=vector_config,
			replication_config=Configure.replication(3)
		)
		return True, f"Collection '{collection_name}' created successfully"
	except Exception as e:
		return False, f"Error creating collection: {str(e)}"

# Sanitize keys for Weaviate
def sanitize_keys(data_item: Dict[str, Any]) -> Dict[str, Any]:
	print("sanitize_keys() called")
	sanitized_item = {}
	for key, value in data_item.items():
		# Replace spaces and invalid characters with underscores
		sanitized_key = re.sub(r'[^0-9a-zA-Z_]+', '_', key)
		# Ensure the key starts with a letter or underscore
		if not re.match(r'^[A-Za-z_]', sanitized_key):
			sanitized_key = '_' + sanitized_key
		sanitized_item[sanitized_key] = value
	return sanitized_item

# Batch data. Reduce/Increase Batch Size as per your requirement. You can also pass concurrent_requests in batch.fixed_size(batch_size=1000, concurrent_requests=4)
def batch_upload(client: Client, collection_name: str, data: List[Dict[str, Any]], batch_size: int = 1000):
	print(f"batch_upload() called")
	if not client.collections.exists(collection_name):
		yield False, f"Collection '{collection_name}' does not exist", None
		return

	total_objects = len(data)

	with client.batch.fixed_size(batch_size=batch_size) as batch:
		for i, obj in enumerate(data, 1):
			sanitized_obj = sanitize_keys(obj)
			uuid = generate_uuid5(obj)
			try:
				batch.add_object(
					collection=collection_name,
					properties=sanitized_obj,
					uuid=uuid
				)
				# Yield a queuing message immediately for real-time feedback
				yield True, f"Queuing object {i}/{total_objects}: {uuid}", None
			except Exception as e:
				yield False, f"Failed to queue object {i}/{total_objects}: {str(e)}", None

# Get the newely created collection
def get_collection_info(client: Client, collection_name: str) -> tuple[bool, str, Optional[Dict[str, Any]]]:
	print(f"get_collection_info() called for collection: {collection_name}")
	try:
		if not client.collections.exists(collection_name):
			return False, f"Collection '{collection_name}' does not exist", None

		collection = client.collections.get(collection_name)
		aggregate_result = collection.aggregate.over_all()
		# Get schema information using the existing get_schema function
		schema = get_schema(st.session_state.client)
		collection_schema = next((c for c in schema.get("classes", []) if c.get("class") == collection_name), None)

		info = {
			"name": collection_name,
			"object_count": aggregate_result.total_count if hasattr(aggregate_result, 'total_count') else 0,
			"properties": collection_schema.get("properties", []) if collection_schema else [],
			"vectorizer": collection_schema.get("vectorizer", "none") if collection_schema else "none"
		}
		return True, "Collection info retrieved successfully", info
	except Exception as e:
		return False, f"Error getting collection info: {str(e)}", None

# Get the first 100 objects from the collection as check up
def get_collection_objects(client: Client, collection_name: str, limit: int = 100) -> tuple[bool, str, Optional[pd.DataFrame]]:
	print(f"get_collection_objects() called")
	try:
		if not client.collections.exists(collection_name):
			return False, f"Collection '{collection_name}' does not exist", None

		collection = client.collections.get(collection_name)
		objects = []
		count = 0

		for item in collection.iterator(include_vector=True):
			if count >= limit:
				break
			objects.append({
				**item.properties,
				"vector": item.vector
			})
			count += 1

		if not objects:
			return True, "No objects found", pd.DataFrame()

		df = pd.DataFrame(objects)
		return True, f"Retrieved {len(df)} objects", df
	except Exception as e:
		return False, f"Error retrieving objects: {str(e)}", None 
