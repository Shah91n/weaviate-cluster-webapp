import pandas as pd
import logging
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

# Get object in Non Multitenant collection
def get_object_in_collection(collection_name, uuid):
	logger.info(f"get_object_in_collection() called for collection: {collection_name}, uuid: {uuid}")
	client = get_weaviate_client()
	collection = client.collections.use(collection_name)
	data_object = collection.query.fetch_object_by_id(uuid, include_vector=True)

	if data_object is None:
		logger.warning(f"Object with UUID '{uuid}' not found.")
		return None

	return data_object

# Get object in Multitenant collection
def get_object_in_tenant(collection_name, uuid, tenant):
	logger.info(f"get_object_in_tenant() called for collection: {collection_name}, uuid: {uuid}, tenant: {tenant}")
	client = get_weaviate_client()
	collection = client.collections.use(collection_name).with_tenant(tenant)
	data_object = collection.query.fetch_object_by_id(uuid, include_vector=True)

	if data_object is None:
		logger.warning(f"Object with UUID '{uuid}' not found.")
		return None

	return data_object

# Display object in a table format
def display_object_as_table(data_object):
	if data_object is None:
		logger.info("No data to display.")
		return

	metadata_fields = {
		"Creation Time": data_object.metadata.creation_time,
		"Last Update Time": data_object.metadata.last_update_time,
	}

	additional_data = {
		"UUID": str(data_object.uuid),
		"Collection": data_object.collection,
		"Vectors": data_object.vector
	}

	additional_data.update(metadata_fields)

	if data_object.properties:
		for key, value in data_object.properties.items():
			additional_data[key] = value

	df = pd.DataFrame([additional_data])

	return df

# Update object
def update_object_properties(collection_name, uuid, properties, tenant=None):
	logger.info(f"update_object_properties() called for collection: {collection_name}, uuid: {uuid}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		if tenant:
			collection = collection.with_tenant(tenant)
		collection.data.update(
			uuid=uuid,
			properties=properties
		)
		return True
	except Exception as e:
		logger.error(f"Failed to update object: {str(e)}")
		raise Exception(f"Failed to update object: {str(e)}")
