import time
import json
import pandas as pd
import logging
from typing import Optional, Tuple
from weaviate.classes.query import MetadataQuery
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

# Vector search function
# This function performs a vector search on a specified collection in Weaviate.

def vector_search(
    collection: str,
    vectors: list[float],
    limit: int = 3,
    tenant_name: Optional[str] = None,
) -> Tuple[bool, str, pd.DataFrame, float]:
	logger.info(f"vector_search() called for collection: {collection}")
	try:
		# Get client from singleton manager
		client = get_weaviate_client()
		# Get collection
		coll = client.collections.use(collection)
		if tenant_name:
			coll = coll.with_tenant(tenant_name)

		# Measure performance
		start_time = time.time() * 1000 # Convert to milliseconds

		# Perform search
		response = coll.query.near_vector(
			near_vector=vectors,
			limit=limit,
			return_metadata=MetadataQuery(
				creation_time=True,
				last_update_time=True,
				distance=True,
				certainty=True,
				score=True,
				explain_score=True,
				is_consistent=True
			)
		)

		# Calculate time taken
		end_time = time.time() * 1000
		time_taken = end_time - start_time

		# Process results into a list of dictionaries
		results = []
		for obj in response.objects:
			result_dict = {
				"Distance": obj.metadata.distance if hasattr(obj.metadata, 'distance') else 'N/A',
				"Certainty": obj.metadata.certainty if hasattr(obj.metadata, 'certainty') else 'N/A',
				"Creation Time": obj.metadata.creation_time if hasattr(obj.metadata, 'creation_time') else 'N/A',
				"Last Update Time": obj.metadata.last_update_time if hasattr(obj.metadata, 'last_update_time') else 'N/A'
			}

			if tenant_name:
				result_dict["Tenant"] = tenant_name

			# Add properties
			for key, value in obj.properties.items():
				if isinstance(value, (dict, list)):
					result_dict[key] = json.dumps(value, indent=2)
				else:
					result_dict[key] = value

			results.append(result_dict)

		# Convert to DataFrame
		df = pd.DataFrame(results)
		return True, f"Found {len(results)} results", df, time_taken

	except Exception as e:
		logger.error(f"Error performing Vector search: {str(e)}")
		return False, f"Error performing Vector search: {str(e)}", pd.DataFrame(), 0.0


def vector_search_with_multiple_vectors(
    collection: str,
    targetvector: str,
    vectors: list[float],
    limit: int = 3,
    tenant_name: Optional[str] = None,
) -> Tuple[bool, str, pd.DataFrame, float]:
	logger.info(f"vector_search_with_multiple_vectors() called for collection: {collection}")
	try:
		# Get client from singleton manager
		client = get_weaviate_client()
		# Get collection
		coll = client.collections.use(collection)
		if tenant_name:
			coll = coll.with_tenant(tenant_name)

		# Measure performance
		start_time = time.time() * 1000 # Convert to milliseconds

		# Perform search
		response = coll.query.near_vector(
			near_vector=vectors,
			target_vector=targetvector,
			limit=limit,
			return_metadata=MetadataQuery(
				creation_time=True,
				last_update_time=True,
				distance=True,
				certainty=True,
				score=True,
				explain_score=True,
				is_consistent=True
			)
		)

		# Calculate time taken
		end_time = time.time() * 1000
		time_taken = end_time - start_time

		# Process results into a list of dictionaries
		results = []
		for obj in response.objects:
			result_dict = {
				"Distance": obj.metadata.distance if hasattr(obj.metadata, 'distance') else 'N/A',
				"Certainty": obj.metadata.certainty if hasattr(obj.metadata, 'certainty') else 'N/A',
				"Creation Time": obj.metadata.creation_time if hasattr(obj.metadata, 'creation_time') else 'N/A',
				"Last Update Time": obj.metadata.last_update_time if hasattr(obj.metadata, 'last_update_time') else 'N/A'
			}

			if tenant_name:
				result_dict["Tenant"] = tenant_name

			# Add properties
			for key, value in obj.properties.items():
				if isinstance(value, (dict, list)):
					result_dict[key] = json.dumps(value, indent=2)
				else:
					result_dict[key] = value

			results.append(result_dict)

		# Convert to DataFrame
		df = pd.DataFrame(results)
		return True, f"Found {len(results)} results", df, time_taken

	except Exception as e:
		logger.error(f"Error performing Vector search: {str(e)}")
		return False, f"Error performing Vector search: {str(e)}", pd.DataFrame(), 0.0
	
def parse_vector_input(vector_string: str) -> list[float]:
    logger.info("parse_vector_input() called")
    try:
        # Remove all whitespace and newlines first
        cleaned = vector_string.replace('\n', '').replace('\r', '').replace(' ', '')
        
        # Remove outer brackets if present
        cleaned = cleaned.strip('[]')
        
        # Split by comma and convert to float
        vector_list = [float(x.strip()) for x in cleaned.split(',') if x.strip()]
        
        return vector_list
    except ValueError as e:
        logger.error(f"Invalid vector format: {e}")
        raise ValueError(f"Invalid vector format: {e}")
