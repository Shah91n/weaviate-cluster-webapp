from weaviate.classes.config import Reconfigure, PQEncoderType, PQEncoderDistribution, VectorFilterStrategy, ReplicationDeletionStrategy
import pandas as pd
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

def update_hnsw_vector_index(collection_name, dynamic_ef_factor, dynamic_ef_min, dynamic_ef_max, filter_strategy, flat_search_cutoff, vector_cache_max_objects):
	logger.info(f"update_hnsw_vector_index() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		hnsw_params = {}
		if dynamic_ef_factor is not None:
			hnsw_params['dynamic_ef_factor'] = dynamic_ef_factor
		if dynamic_ef_min is not None:
			hnsw_params['dynamic_ef_min'] = dynamic_ef_min
		if dynamic_ef_max is not None:
			hnsw_params['dynamic_ef_max'] = dynamic_ef_max
		if filter_strategy is not None:
			if isinstance(filter_strategy, VectorFilterStrategy):
				hnsw_params['filter_strategy'] = filter_strategy
			elif isinstance(filter_strategy, str) and hasattr(VectorFilterStrategy, filter_strategy):
				hnsw_params['filter_strategy'] = getattr(VectorFilterStrategy, filter_strategy)
			else:
				raise Exception(f"Invalid VectorFilterStrategy: {filter_strategy}")
		if flat_search_cutoff is not None:
			hnsw_params['flat_search_cutoff'] = flat_search_cutoff
		if vector_cache_max_objects is not None:
			hnsw_params['vector_cache_max_objects'] = vector_cache_max_objects
		if hnsw_params:
			collection.config.update(vector_config=Reconfigure.VectorIndex.hnsw(**hnsw_params))
		return True
	except Exception as e:
		logger.error(f"Failed to update HNSW vector index: {str(e)}")
		raise Exception(f"Failed to update HNSW vector index: {str(e)}")

def update_pq_quantizer(collection_name, pq_enabled, pq_centroids, pq_segments, pq_training_limit, pq_encoder_type, pq_encoder_distribution):
	logger.info(f"update_pq_quantizer() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		pq_kwargs = {}
		if pq_enabled is not None:
			pq_kwargs['enabled'] = pq_enabled
		if pq_centroids is not None:
			pq_kwargs['centroids'] = pq_centroids
		if pq_segments is not None:
			pq_kwargs['segments'] = pq_segments
		if pq_training_limit is not None:
			pq_kwargs['training_limit'] = pq_training_limit
		if pq_encoder_type is not None:
			if isinstance(pq_encoder_type, PQEncoderType):
				pq_kwargs['encoder_type'] = pq_encoder_type
			elif isinstance(pq_encoder_type, str) and hasattr(PQEncoderType, pq_encoder_type):
				pq_kwargs['encoder_type'] = getattr(PQEncoderType, pq_encoder_type)
			else:
				raise Exception(f"Invalid PQEncoderType: {pq_encoder_type}")
		if pq_encoder_distribution is not None:
			if isinstance(pq_encoder_distribution, PQEncoderDistribution):
				pq_kwargs['encoder_distribution'] = pq_encoder_distribution
			elif isinstance(pq_encoder_distribution, str) and hasattr(PQEncoderDistribution, pq_encoder_distribution):
				pq_kwargs['encoder_distribution'] = getattr(PQEncoderDistribution, pq_encoder_distribution)
			else:
				raise Exception(f"Invalid PQEncoderDistribution: {pq_encoder_distribution}")
		collection.config.update(vector_config=Reconfigure.VectorIndex.hnsw(quantizer=Reconfigure.VectorIndex.Quantizer.pq(**pq_kwargs)))
		return True
	except Exception as e:
		logger.error(f"Failed to update PQ quantizer: {str(e)}")
		raise Exception(f"Failed to update PQ quantizer: {str(e)}")

# Convert and display collection configuration to a pandas DataFrame
def display_config_as_table(config):
	logger.info("display_config_as_table() called")
	if config is None:
		return pd.DataFrame()
	flat_config = {}
	flat_config['Description'] = getattr(config, 'description', None)
	if hasattr(config, 'inverted_index_config') and config.inverted_index_config is not None:
		inverted = config.inverted_index_config
		flat_config.update({
			'BM25 B': getattr(inverted, 'bm25_b', None),
			'BM25 K1': getattr(inverted, 'bm25_k1', None),
			'Cleanup Interval (s)': getattr(inverted, 'cleanup_interval_seconds', None),
			'Stopwords Preset': getattr(inverted, 'stopwords_preset', None),
			'Stopwords Additions': ', '.join(getattr(inverted, 'stopwords_additions', []) if getattr(inverted, 'stopwords_additions', []) is not None else []),
			'Stopwords Removals': ', '.join(getattr(inverted, 'stopwords_removals', []) if getattr(inverted, 'stopwords_removals', []) is not None else []),
		})
	if hasattr(config, 'multi_tenancy_config') and config.multi_tenancy_config is not None:
		multi = config.multi_tenancy_config
		flat_config.update({
			'Auto Tenant Creation': getattr(multi, 'auto_tenant_creation', None),
			'Auto Tenant Activation': getattr(multi, 'auto_tenant_activation', None)
		})
	if hasattr(config, 'replication_config') and config.replication_config is not None:
		repl = config.replication_config
		deletion_strategy_val = getattr(repl, 'deletion_strategy', None)
		flat_config['Deletion Strategy'] = deletion_strategy_val.name if deletion_strategy_val is not None else None
		flat_config['Async Enabled'] = getattr(repl, 'async_enabled', None)
	if hasattr(config, 'vector_config') and config.vector_config is not None:
		vector = config.vector_config
		vector_index_type = getattr(vector, 'type', None)
		flat_config['Vector Index Type'] = vector_index_type
		flat_config['Vector Cache Max Objects'] = getattr(vector, 'vector_cache_max_objects', None)
		if vector_index_type == 'hnsw':
			flat_config.update({
				'Dynamic EF Factor': getattr(vector, 'dynamic_ef_factor', None),
				'Dynamic EF Min': getattr(vector, 'dynamic_ef_min', None),
				'Dynamic EF Max': getattr(vector, 'dynamic_ef_max', None),
				'Filter Strategy': getattr(vector, 'filter_strategy', None).name if getattr(vector, 'filter_strategy', None) is not None else None,
				'Flat Search Cutoff': getattr(vector, 'flat_search_cutoff', None),
			})
			if hasattr(vector, 'quantizer') and vector.quantizer is not None:
				quantizer = vector.quantizer
				if getattr(quantizer, 'type', None) == 'pq':
					flat_config['PQ Enabled'] = getattr(quantizer, 'enabled', None)
					flat_config['PQ Centroids'] = getattr(quantizer, 'centroids', None)
					flat_config['PQ Segments'] = getattr(quantizer, 'segments', None)
					flat_config['PQ Training Limit'] = getattr(quantizer, 'training_limit', None)
					if hasattr(quantizer, 'encoder') and quantizer.encoder is not None:
						flat_config['PQ Encoder Type'] = getattr(quantizer.encoder, 'type', None)
						flat_config['PQ Encoder Distribution'] = getattr(quantizer.encoder, 'distribution', None)
	df = pd.DataFrame([flat_config])
	return df 
