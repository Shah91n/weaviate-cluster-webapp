from weaviate.classes.config import Reconfigure, ReplicationDeletionStrategy
import logging
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

# Get the current configuration of a collection
def get_collection_config(collection_name):
	logger.info(f"get_collection_config() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		config = collection.config.get()
		return config
	except Exception as e:
		logger.error(f"Failed to get collection configuration: {str(e)}")
		raise Exception(f"Failed to get collection configuration: {str(e)}")

# --- Sectioned update helpers ---

def update_description_and_inverted_index(collection_name, description, bm25_b, bm25_k1, cleanup_interval_seconds, stopwords_preset, stopwords_additions, stopwords_removals):
	logger.info(f"update_description_and_inverted_index() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		update_config = {}
		if description is not None:
			update_config['description'] = description
		inverted_kwargs = {}
		if bm25_b is not None:
			inverted_kwargs['bm25_b'] = bm25_b
		if bm25_k1 is not None:
			inverted_kwargs['bm25_k1'] = bm25_k1
		if cleanup_interval_seconds is not None:
			inverted_kwargs['cleanup_interval_seconds'] = cleanup_interval_seconds
		if stopwords_additions is not None:
			inverted_kwargs['stopwords_additions'] = [item.strip() for item in stopwords_additions.split(',') if item.strip()]
		if stopwords_preset is not None:
			inverted_kwargs['stopwords_preset'] = stopwords_preset
		if stopwords_removals is not None:
			inverted_kwargs['stopwords_removals'] = [item.strip() for item in stopwords_removals.split(',') if item.strip()]
		if inverted_kwargs:
			update_config['inverted_index_config'] = Reconfigure.inverted_index(**inverted_kwargs)
		if update_config:
			collection.config.update(**update_config)
		return True
	except Exception as e:
		logger.error(f"Failed to update description/inverted index: {str(e)}")
		raise Exception(f"Failed to update description/inverted index: {str(e)}")

def update_multi_tenancy_and_replication(collection_name, auto_tenant_creation, auto_tenant_activation, async_enabled, deletion_strategy):
	logger.info(f"update_multi_tenancy_and_replication() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		update_config = {}
		multi_kwargs = {}
		if auto_tenant_creation is not None:
			multi_kwargs['auto_tenant_creation'] = auto_tenant_creation
		if auto_tenant_activation is not None:
			multi_kwargs['auto_tenant_activation'] = auto_tenant_activation
		if multi_kwargs:
			update_config['multi_tenancy_config'] = Reconfigure.multi_tenancy(**multi_kwargs)
		repl_kwargs = {}
		if async_enabled is not None:
			repl_kwargs['async_enabled'] = async_enabled
		if deletion_strategy is not None:
			if isinstance(deletion_strategy, ReplicationDeletionStrategy):
				repl_kwargs['deletion_strategy'] = deletion_strategy
			elif isinstance(deletion_strategy, str) and hasattr(ReplicationDeletionStrategy, deletion_strategy):
				repl_kwargs['deletion_strategy'] = getattr(ReplicationDeletionStrategy, deletion_strategy)
			else:
				raise Exception(f"Invalid ReplicationDeletionStrategy: {deletion_strategy}")
		if repl_kwargs:
			update_config['replication_config'] = Reconfigure.replication(**repl_kwargs)
		if update_config:
			collection.config.update(**update_config)
		return True
	except Exception as e:
		logger.error(f"Failed to update multi-tenancy/replication: {str(e)}")
		raise Exception(f"Failed to update multi-tenancy/replication: {str(e)}")
