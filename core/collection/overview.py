import dataclasses
import logging

import pandas as pd
from core.collection.vector_index import HFRESH, describe_vector_indexes
from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)


def _empty_aggregate(error=None):
	"""The zero-state result. aggregate_collections() always returns this shape."""
	result = {
		"collection_count": 0,
		"total_tenants_count": 0,
		"empty_collections": 0,
		"empty_tenants": 0,
		"total_objects_regular": 0,
		"total_objects_multitenancy": 0,
		"total_objects_combined": 0,
		"result_df": pd.DataFrame(),
		"empty_collections_list": [],
		"empty_tenants_details": [],
	}
	if error is not None:
		result["error"] = error
	return result


# Aggregate collections. Always returns a dict — never None, which the cluster page
# used to receive when the cluster reported no collections.
def aggregate_collections():
	logger.info("aggregate_collections() called")
	try:
		client = get_weaviate_client()
		collections = client.collections.list_all()
		total_tenants_count = 0
		result_data = []
		empty_collections = 0
		empty_tenants = 0
		total_objects_regular = 0
		total_objects_multitenancy = 0
		empty_collections_list = []
		empty_tenants_details = []

		if collections:
			collection_count = len(collections)
			for collection_name in collections:
				collection_row = {"Collection": collection_name, "Count": "", "Tenant": "", "Object Count": ""}
				result_data.append(collection_row)
				collection = client.collections.use(collection_name)
				try:
					tenants = collection.tenants.get()

					if tenants:
						tenant_count = len(tenants)
						total_tenants_count += tenant_count
						collection_tenant_total = 0

						for tenant_name, tenant in tenants.items():
							try:
								tenant_collection = collection.with_tenant(tenant_name)
								objects_count = tenant_collection.aggregate.over_all(total_count=True).total_count
								collection_tenant_total += objects_count
								if objects_count == 0:
									empty_tenants += 1
									empty_tenants_details.append({
										"Collection": collection_name,
										"Tenant": tenant_name,
										"Count": 0
									})
								tenant_row = {"Collection": "", "Count": "", "Tenant": tenant_name, "Object Count": objects_count}
								result_data.append(tenant_row)
							except Exception as e_inner:
								logger.error(f"Error getting tenant count: {e_inner}")
								tenant_row = {"Collection": "", "Count": "", "Tenant": tenant_name, "Object Count": f"ERROR: {e_inner}"}
								result_data.append(tenant_row)

						total_objects_multitenancy += collection_tenant_total

					else:
						objects_count = collection.aggregate.over_all(total_count=True).total_count
						collection_row["Count"] = objects_count
						if objects_count == 0:
							empty_collections += 1
							empty_collections_list.append({
								"Collection": collection_name,
								"Count": 0
							})
						total_objects_regular += objects_count

				except Exception as e:
					if "multi-tenancy is not enabled" in str(e):
						objects_count = collection.aggregate.over_all(total_count=True).total_count
						collection_row["Count"] = objects_count
						if objects_count == 0:
							empty_collections += 1
							empty_collections_list.append({
								"Collection": collection_name,
								"Count": 0
							})
						total_objects_regular += objects_count
					else:
						logger.error(f"Error processing collection {collection_name}: {e}")

			result_df = pd.DataFrame(result_data)

			return {
				"collection_count": collection_count,
				"total_tenants_count": total_tenants_count,
				"empty_collections": empty_collections,
				"empty_tenants": empty_tenants,
				"total_objects_regular": total_objects_regular,
				"total_objects_multitenancy": total_objects_multitenancy,
				"total_objects_combined": total_objects_regular + total_objects_multitenancy,
				"result_df": result_df,
				"empty_collections_list": empty_collections_list,
				"empty_tenants_details": empty_tenants_details
			}

		return _empty_aggregate()
	except Exception as e:
		logger.error(f"Error in aggregate_collections: {e}")
		return _empty_aggregate(error=f"Failed to aggregate collections: {e}")


# List all collections. Raises on failure rather than returning an empty list, so a
# permissions or connection error is never displayed as "no collections".
def list_collections():
	logger.info("list_collections() called")
	try:
		client = get_weaviate_client()
		collections = client.collections.list_all()
		if not collections:
			return []
		if hasattr(collections, "keys"):
			return list(collections.keys())
		return list(collections)
	except Exception as e:
		logger.error(f"Error listing collections: {e}")
		raise Exception(f"Failed to list collections: {e}")


# Get collection schema (full config, simple=False)
def get_schema():
	logger.info("get_schema() called")
	try:
		client = get_weaviate_client()
		response = client.collections.list_all(simple=False)
		return response if response else {}
	except Exception as e:
		logger.error(f"Error getting schema: {e}")
		raise Exception(f"Failed to load schema: {e}")


# Get the full configuration of a single collection using the Weaviate Python client SDK.
def fetch_collection_config(collection_name):
	logger.info(f"fetch_collection_config() called for collection: {collection_name}")
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		return collection.config.get()
	except Exception as e:
		logger.error(f"Error fetching collection config for '{collection_name}': {e}")
		raise Exception(f"Failed to load configuration for '{collection_name}': {e}")


# --------------------------------------------------------------------------
# Config display
#
# The collection config is rendered reflectively rather than from a whitelist of
# fields. Weaviate keeps adding config (object TTL, async replication tuning,
# range filters) and every vectorizer / generative / reranker module writes its
# own shape into moduleConfig, so a hand-written field list silently drops
# whatever it has not been taught about — and on screen a dropped field is
# indistinguishable from a setting the collection does not have.
# --------------------------------------------------------------------------

_SCALARS = (str, int, float, bool)

# Vector layout is normalised by core/collection/vector_index.py, not here.
_VECTOR_FIELDS = {
	"vector_config",
	"vector_index_config",
	"vector_index_type",
	"vectorizer",
	"vectorizer_config",
}

_GENERAL_FIELDS = ("name", "description")

# Properties get their own table via process_collection_properties().
_SKIP_FIELDS = {"properties"}

_SECTION_LABELS = {
	"generative_config": "Generative Config",
	"inverted_index_config": "Inverted Index Config",
	"multi_tenancy_config": "Multi-Tenancy Config",
	"object_ttl_config": "Object TTL Config",
	"references": "References",
	"replication_config": "Replication Config",
	"reranker_config": "Reranker Config",
	"sharding_config": "Sharding Config",
}

_PROPERTY_LABELS = {
	"name": "Property Name",
	"description": "Description",
	"data_type": "Data Type",
	"index_filterable": "Filterable",
	"index_searchable": "Searchable",
	"index_range_filters": "Range Filters",
	"nested_properties": "Nested Properties",
	"text_analyzer": "Text Analyzer",
	"tokenization": "Tokenization",
	"vectorizer": "Vectorizer",
	"vectorizer_config": "Vectorizer Config",
	"vectorizer_configs": "Vectorizer Configs",
}


def _display_value(value):
	"""Render an SDK config value as a readable string."""
	if value is None:
		return "None"
	return str(getattr(value, "value", value))


def _humanize(key):
	return str(key).replace("_", " ").title()


def _config_fields(obj):
	"""The public fields of an SDK config object, or None if it is a leaf value."""
	if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
		return {f.name: getattr(obj, f.name, None) for f in dataclasses.fields(obj)}
	return None


def _flatten_config(value, prefix=""):
	"""Flatten a config object, dict or list into a {dotted key: display value} map.

	Nested module config (``model.baseURL``, ``async_config.max_workers``) keeps its
	path in the key so a two-column table can show it without losing the structure.
	"""
	if isinstance(value, dict):
		flat = {}
		for key, item in value.items():
			flat.update(_flatten_config(item, f"{prefix}.{key}" if prefix else str(key)))
		return flat

	fields = _config_fields(value)
	if fields is not None:
		flat = {}
		for key, item in fields.items():
			flat.update(_flatten_config(item, f"{prefix}.{key}" if prefix else key))
		return flat

	if isinstance(value, (list, tuple, set)):
		items = list(value)
		if not items:
			return {prefix or "value": "[]"}
		if all(isinstance(item, _SCALARS) for item in items):
			return {prefix or "value": ", ".join(_display_value(item) for item in items)}
		flat = {}
		for i, item in enumerate(items):
			flat.update(_flatten_config(item, f"{prefix}[{i}]"))
		return flat

	return {prefix or "value": _display_value(value)}


def _section_value(value):
	"""A section is a row list when the field holds config objects, a kv map otherwise.

	An unset field becomes an empty section rather than a row reading "None", so the
	page can label it as not configured.
	"""
	if value is None:
		return {}
	if isinstance(value, (list, tuple, set)):
		items = list(value)
		if not items:
			return []
		if all(_config_fields(item) is not None for item in items):
			return [_flatten_config(item) for item in items]
	return _flatten_config(value)


def _as_display_dict(params):
	return {k: _display_value(v) for k, v in params.items() if v is not None}


def _describe_index_for_display(info):
	"""Turn one VectorIndexInfo into the ordered sections the config page renders."""
	sections = {"Vector Index Type": info.index_type}

	if info.vectorizer:
		sections["Vectorizer"] = info.vectorizer

	# The module's own settings — model, baseURL, source properties — i.e. what the
	# raw schema reports under moduleConfig for this vector.
	if info.vectorizer_params:
		sections["Vectorizer Config"] = _flatten_config(info.vectorizer_params)

	index_params = _as_display_dict(info.params)
	if index_params:
		sections["Vector Index Config"] = index_params

	# A dynamic index keeps its real settings — and its quantizers — one level down.
	for scope, params in info.sub_indexes.items():
		scope_params = _as_display_dict(params)
		if scope_params:
			sections[f"Sub-Index: {scope}"] = scope_params

	for quantizer in info.quantizers:
		sections[f"Quantizer: {quantizer.label}"] = _as_display_dict(quantizer.params)

	if not info.quantizers:
		sections["Compression"] = "none"
	elif info.index_type == HFRESH:
		sections["Compression"] = f"{info.compression_summary} (built in, always on)"
	else:
		sections["Compression"] = info.compression_summary

	return sections


# Process a SDK CollectionConfig object into a displayable sections dict.
def process_collection_config(config):
	"""Turn an SDK CollectionConfig into ordered, displayable sections.

	Every field the SDK reports is rendered — known ones under a curated label, the
	rest under a humanised version of their own name — so config this function has
	never heard of still reaches the screen.
	"""
	logger.info("process_collection_config() called")
	if config is None:
		return {}

	fields = _config_fields(config)
	if fields is None:
		return {}

	result = {}

	general = {key: _display_value(fields[key]) for key in _GENERAL_FIELDS if key in fields}
	general["properties"] = len(fields.get("properties") or [])
	result["General"] = general

	for key, value in fields.items():
		if key in _GENERAL_FIELDS or key in _SKIP_FIELDS or key in _VECTOR_FIELDS:
			continue
		result[_SECTION_LABELS.get(key, _humanize(key))] = _section_value(value)

	# Vectors — covers named vectors and the legacy single vector alike, and reports the
	# real index type (hnsw / flat / dynamic / hfresh) rather than assuming HNSW.
	indexes = describe_vector_indexes(config)
	if indexes:
		result["Vectors"] = {info.name: _describe_index_for_display(info) for info in indexes}

	return result


# Process the properties of a SDK CollectionConfig into uniform display rows.
def process_collection_properties(config):
	"""One row per property, with every field the SDK reports for it.

	Per-property module settings (``skip``, ``vectorize_property_name``, and the
	per-named-vector variants) are flattened into their own columns rather than
	being dropped. Columns are unioned across properties so the table stays square.
	"""
	logger.info("process_collection_properties() called")
	rows = []

	for prop in getattr(config, "properties", None) or []:
		fields = _config_fields(prop)
		if fields is None:
			continue

		row = {}
		for key, value in fields.items():
			label = _PROPERTY_LABELS.get(key, _humanize(key))
			if key == "nested_properties":
				row[label] = len(value or [])
			elif isinstance(value, dict) or _config_fields(value) is not None:
				for sub_key, sub_value in _flatten_config(value).items():
					row[f"{label}: {sub_key}"] = sub_value
			else:
				row[label] = _display_value(value)
		rows.append(row)

	columns = []
	for row in rows:
		for key in row:
			if key not in columns:
				columns.append(key)

	return [{column: row.get(column, "") for column in columns} for row in rows]
