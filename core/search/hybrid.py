import time
import re
import json
import pandas as pd
import logging
from typing import Optional, Tuple
from weaviate.classes.query import MetadataQuery
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

# Hybrid search function
# This function performs a hybrid search on a specified collection in Weaviate.
def hybrid_search(
    collection: str,
    query: str,
    alpha: float = 0.5,
    limit: int = 3,
    tenant_name: Optional[str] = None,
) -> Tuple[bool, str, pd.DataFrame, float]:
	logger.info(f"hybrid_search() called for collection: {collection}")
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
		response = coll.query.hybrid(
			query=query,
			alpha=alpha,
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
				"Score": f"{obj.metadata.score:.6f}",
				"Original Score": f"{float(re.search(r'original score ([\d.]+)', obj.metadata.explain_score).group(1)):.6f}",
				"Explain Score": obj.metadata.explain_score,
				"Distance": obj.metadata.distance if hasattr(obj.metadata, 'distance') else 'N/A',
				"Certainty": obj.metadata.certainty if hasattr(obj.metadata, 'certainty') else 'N/A',
				"Is Consistent": obj.metadata.is_consistent if hasattr(obj.metadata, 'is_consistent') else 'N/A',
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
		logger.error(f"Error performing hybrid search: {str(e)}")
		return False, f"Error performing hybrid search: {str(e)}", pd.DataFrame(), 0.0

def hybrid_search_with_multiple_vectors(
	collection: str,
	targetvector: str,
	query: str,
	alpha: float = 0.5,
	limit: int = 3,
	tenant_name: Optional[str] = None,
) -> Tuple[bool, str, pd.DataFrame, float]:
	logger.info(f"hybrid_search_with_multiple_vectors() called for collection: {collection}")
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
		response = coll.query.hybrid(
			query=query,
			target_vector=targetvector,
			alpha=alpha,
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
				"Score": f"{obj.metadata.score:.6f}",
				"Original Score": f"{float(re.search(r'original score ([\d.]+)', obj.metadata.explain_score).group(1)):.6f}",
				"Explain Score": obj.metadata.explain_score,
				"Distance": obj.metadata.distance if hasattr(obj.metadata, 'distance') else 'N/A',
				"Certainty": obj.metadata.certainty if hasattr(obj.metadata, 'certainty') else 'N/A',
				"Is Consistent": obj.metadata.is_consistent if hasattr(obj.metadata, 'is_consistent') else 'N/A',
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
		return False, f"Error performing hybrid search: {str(e)}", pd.DataFrame(), 0.0
	