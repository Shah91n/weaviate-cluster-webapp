import logging
import streamlit as st
import json
from datetime import datetime, date
from core.object.update_object import get_object_in_collection, display_object_as_table, get_object_in_tenant, update_object_properties
from core.collection.update_collection_config import get_collection_config, update_description_and_inverted_index, update_multi_tenancy_and_replication
from core.collection.vector_index import (
	DYNAMIC,
	HFRESH,
	IMMUTABLE_QUANTIZER_INDEXES,
	MUTABLE_INDEX_FIELDS,
	MUTABLE_QUANTIZER_FIELDS,
	QUANTIZERS_BY_INDEX,
	describe_vector_indexes,
	update_vector_index,
)
from core.collection.overview import fetch_collection_config, list_collections
from pages.utils.page_config import page_header
from pages.utils import ui
from weaviate.classes.config import StopwordsPreset

logger = logging.getLogger(__name__)

# Function to map schema properties to their types
def build_type_map_from_schema(config):
	type_map = {}
	if config is None:
		return type_map
	for prop in getattr(config, "properties", []):
		name = getattr(prop, "name", None)
		data_type = getattr(prop, "data_type", None)
		if name is None or data_type is None:
			continue
		dt_str = data_type.value  # e.g. 'text', 'text[]', 'int', 'object[]'
		if dt_str.endswith("[]"):
			type_map[name] = dt_str[:-2] + "_array"
		else:
			type_map[name] = dt_str
	return type_map

# Function to parse values based on their type
def parse_value_by_type(value, type_name):
	if type_name in ('text', 'string', 'uuid', 'geoCoordinates', 'phoneNumber', 'blob'):
		return str(value)
	elif type_name == 'boolean':
		if isinstance(value, bool):
			return value
		if isinstance(value, str):
			return value.lower() == 'true'
		return bool(value)
	elif type_name == 'int':
		try:
			return int(value)
		except Exception:
			return None
	elif type_name == 'number':
		try:
			return float(value)
		except Exception:
			return None
	elif type_name == 'date':
		# Accept both string and date/datetime
		if isinstance(value, (datetime, date)):
			return value.strftime('%Y-%m-%dT%H:%M:%S+00:00')
		elif isinstance(value, str):
			try:
				dt = datetime.fromisoformat(value)
				return dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
			except Exception:
				return value
		else:
			return str(value)
	elif type_name.endswith('_array'):
		base_type = type_name[:-6]
		if isinstance(value, list):
			return [parse_value_by_type(v, base_type) for v in value]
		try:
			arr = json.loads(value)
			return [parse_value_by_type(v, base_type) for v in arr]
		except Exception:
			return []
	elif type_name == 'object':
		if isinstance(value, dict):
			return value
		try:
			return json.loads(value)
		except Exception:
			return {}
	else:
		return value

# Function to format values for display
def format_value_for_display(value, type_name):
	logger.debug("format_value_for_display called")
	if type_name.endswith('_array') or type_name == 'object':
		return json.dumps(value, indent=2) if value else '[]' if type_name.endswith('_array') else '{}'
	elif type_name == 'date':
		if isinstance(value, str):
			try:
				return datetime.fromisoformat(value.replace('Z', '+00:00'))
			except Exception:
				return value
		elif isinstance(value, (datetime, date)):
			return value
		else:
			return value
	elif type_name == 'boolean':
		return bool(value)
	elif type_name == 'int':
		try:
			return int(value)
		except Exception:
			return 0
	elif type_name == 'number':
		try:
			return float(value)
		except Exception:
			return 0.0
	else:
		return str(value) if value is not None else ''

# Function to display the object as a table and edit its properties
def get_object_details():
	logger.info("get_object_details called")
	collection_name = st.text_input("Collection Name")
	object_uuid = st.text_input("Object UUID")
	with_tenant = st.checkbox("Tenant", value=False)

	tenant_name = None
	if with_tenant:
		tenant_name = st.text_input("Tenant Name")

	fetch_object_clicked = st.button("Fetch The Object", width="stretch")

	# Initialize session state for edit mode and object data
	if 'edit_mode' not in st.session_state:
		st.session_state.edit_mode = False
	if 'current_object' not in st.session_state:
		st.session_state.current_object = None
	if 'object_display' not in st.session_state:
		st.session_state.object_display = None
	if 'type_map' not in st.session_state:
		st.session_state.type_map = None

	# Fetch schema and build type map
	if collection_name and (st.session_state.type_map is None or st.session_state.get('last_collection_name') != collection_name):
		# Best effort: the name is typed by hand, so a miss just means no type hints.
		try:
			config = fetch_collection_config(collection_name)
		except Exception:
			config = None
		if config is not None:
			st.session_state.type_map = build_type_map_from_schema(config)
			st.session_state.last_collection_name = collection_name
		else:
			st.session_state.type_map = None
			st.session_state.last_collection_name = None

	# "Fetch Object"
	if fetch_object_clicked:
		if not collection_name.strip() or not object_uuid.strip():
			st.error("Please insert both Collection Name and UUID.")
			return

		try:
			# Fetch and display object
			if with_tenant and tenant_name:
				data_object = get_object_in_tenant(collection_name, object_uuid, tenant_name)
			else:
				data_object = get_object_in_collection(collection_name, object_uuid)

			if data_object:
				st.session_state.current_object = data_object
				st.session_state.object_display = display_object_as_table(data_object)
				st.session_state.edit_mode = False
			else:
				st.error(f"Object with UUID '{object_uuid}' not found.")
		except ValueError:
			st.error("Invalid UUID: Not a valid UUID or unable to extract it.")
		except Exception as e:
			st.error(f"An error occurred: {e}")

	# Display object data if available
	if st.session_state.object_display is not None:
		st.markdown("### Object Data")
		st.dataframe(st.session_state.object_display, width="stretch")

		# Add Edit button below the table
		if not st.session_state.edit_mode:
			if st.button("Edit Object", type="primary"):
				st.session_state.edit_mode = True
				st.rerun()

	# Edit mode UI
	if st.session_state.edit_mode and st.session_state.current_object:
		st.markdown("### Edit Object Properties")

		# Create form for editing properties
		with st.form("edit_object_form"):
			edited_properties = {}
			type_map = st.session_state.type_map or {}
			# Display and edit each property
			for key, value in st.session_state.current_object.properties.items():
				type_name = type_map.get(key, 'text')
				st.markdown(f"#### {key} ({type_name})")
				if type_name.endswith('_array') or type_name == 'object':
					edited_properties[key] = st.text_area(
						"Value (JSON Array/Object)",
						value=format_value_for_display(value, type_name),
						height=100,
						key=f"textarea_{key}"
					)
				elif type_name == 'date':
					dt_val = format_value_for_display(value, type_name)
					if isinstance(dt_val, (datetime, date)):
						edited_properties[key] = st.date_input(
							"Value (Date)",
							value=dt_val,
							key=f"date_{key}"
						)
					else:
						edited_properties[key] = st.text_input(
							"Value (Date String)",
							value=str(dt_val),
							key=f"date_{key}"
						)
				elif type_name == 'number':
					try:
						num_val = float(value)
					except Exception:
						num_val = 0.0
					edited_properties[key] = st.number_input(
						"Value (Number)",
						value=num_val,
						key=f"number_{key}"
					)
				elif type_name == 'int':
					try:
						int_val = int(value)
					except Exception:
						int_val = 0
					edited_properties[key] = st.number_input(
						"Value (Int)",
						value=int_val,
						step=1,
						key=f"int_{key}"
					)
				elif type_name == 'boolean':
					bool_val = bool(value)
					if isinstance(value, str):
						bool_val = value.lower() == 'true'
					edited_properties[key] = st.checkbox(
						"Value (Boolean)",
						value=bool_val,
						key=f"bool_{key}"
					)
				else: # text and fallback
					edited_properties[key] = st.text_input(
						"Value (Text)",
						value=str(value),
						key=f"text_{key}"
					)
			col1, col2 = st.columns(2)
			with col1:
				submitted = st.form_submit_button("Save Changes", width="stretch")
			with col2:
				cancel = st.form_submit_button("Cancel", width="stretch")
			if submitted:
				try:
					# Parse the values before updating
					parsed_properties = {}
					for key, value in edited_properties.items():
						type_name = type_map.get(key, 'text')
						parsed_properties[key] = parse_value_by_type(value, type_name)
					# Update the object
					if with_tenant and tenant_name:
						update_object_properties(collection_name,
							object_uuid,
							parsed_properties,
							tenant_name
						)
					else:
						update_object_properties(collection_name,
							object_uuid,
							parsed_properties
						)
					st.success("Object updated successfully!")
					st.session_state.edit_mode = False
					# Refresh the object display
					if with_tenant and tenant_name:
						data_object = get_object_in_tenant(collection_name, object_uuid, tenant_name)
					else:
						data_object = get_object_in_collection(collection_name, object_uuid)
					st.session_state.current_object = data_object
					st.session_state.object_display = display_object_as_table(data_object)
					st.rerun()
				except Exception as e:
					st.error(f"Failed to update object: {e}")
			if cancel:
				st.session_state.edit_mode = False
				st.rerun()

# --------------------------------------------------------------------------
# Collection configuration
# --------------------------------------------------------------------------

def _field_widget(field, current, key):
	"""Render one mutable field, prefilled from the live config."""
	if field.kind == "enum":
		options = field.options or []
		current_name = getattr(current, "name", None) or (str(current) if current else field.default)
		index = options.index(current_name) if current_name in options else 0
		return st.selectbox(field.label, options, index=index, key=key, help=field.help or None)

	value = current if current is not None else field.default
	try:
		value = int(value)
	except (TypeError, ValueError):
		value = int(field.default)
	return st.number_input(
		field.label,
		value=value,
		min_value=field.min_value,
		step=1,
		key=key,
		help=field.help or None,
	)


def _render_fields(fields, current_values, key_prefix):
	"""Render a group of mutable fields and collect what the user entered."""
	values = {}
	columns = st.columns(2)
	for position, field in enumerate(fields):
		with columns[position % 2]:
			values[field.name] = _field_widget(field, current_values.get(field.name), f"{key_prefix}_{field.name}")
	return values


def _render_quantizer(info, scope, key_prefix):
	"""Render the quantizer controls for one arm of an index.

	The quantizer *type* is immutable once a collection exists — the client rejects
	a change outright — so an existing quantizer is shown as a fixed label and only
	its mutable fields are editable.
	"""
	quantizer = info.quantizer_for(scope)
	allowed = QUANTIZERS_BY_INDEX.get(info.index_type, [])

	if quantizer is not None:
		if info.index_type == HFRESH:
			st.caption(f"Quantizer: **{quantizer.type.upper()}** — built into HFresh, always on and cannot be swapped.")
		elif info.index_type in IMMUTABLE_QUANTIZER_INDEXES:
			st.caption(f"Quantizer: **{quantizer.type.upper()}** — compression on a {info.index_type} index is immutable after creation.")
			ui.kv_table({k: v for k, v in quantizer.params.items() if v is not None})
			return None, None
		else:
			st.caption(f"Quantizer: **{quantizer.type.upper()}** — the type cannot be changed after creation, only its settings.")
		values = _render_fields(
			MUTABLE_QUANTIZER_FIELDS.get(quantizer.type, []),
			quantizer.params,
			f"{key_prefix}_q",
		)
		return quantizer.type, values

	if info.index_type in IMMUTABLE_QUANTIZER_INDEXES:
		st.caption(f"No compression. Compression on a {info.index_type} index can only be set at creation time.")
		return None, None
	if not allowed:
		return None, None

	st.caption("No compression enabled.")
	if not st.checkbox("Enable compression", key=f"{key_prefix}_q_enable"):
		return None, None
	quantizer_type = st.selectbox(
		"Quantizer",
		allowed,
		format_func=str.upper,
		key=f"{key_prefix}_q_type",
		help="Pick carefully — the quantizer type cannot be changed afterwards.",
	)
	values = _render_fields(MUTABLE_QUANTIZER_FIELDS.get(quantizer_type, []), {}, f"{key_prefix}_q")
	return quantizer_type, values


def render_vector_index_section(collection_name, config):
	"""Vector index editor, driven by the collection's actual index type."""
	indexes = describe_vector_indexes(config)
	if not indexes:
		st.info("This collection has no vector configuration.")
		return

	if len(indexes) > 1:
		names = [info.name for info in indexes]
		selected_name = st.selectbox("Vector", names, key="vec_index_select")
		info = next(i for i in indexes if i.name == selected_name)
	else:
		info = indexes[0]

	ui.metric_row([
		("Vector", info.name),
		("Vector Index Type", info.index_type),
		("Compression", info.compression_summary),
	])
	if info.vectorizer:
		st.caption(f"Vectorizer: **{info.vectorizer}**")
	if not info.is_named:
		st.caption("Legacy single-vector layout — updates are sent without a vector name.")

	key_prefix = f"vi_{collection_name}_{info.name}"
	params = {}
	sub_index_params = {}
	sub_index_quantizers = {}
	quantizer_type = None
	quantizer_params = None

	index_fields = MUTABLE_INDEX_FIELDS.get(info.index_type, [])
	if index_fields:
		ui.section(f"{info.index_type} settings")
		params = _render_fields(index_fields, info.params, key_prefix)

	if info.index_type == DYNAMIC:
		# A dynamic index holds a full hnsw and flat config, each with its own quantizer.
		st.caption("A dynamic index starts as flat and switches to HNSW past the threshold, so both arms are configured separately.")
		for scope in info.scopes:
			ui.section(f"{scope} arm")
			sub_index_params[scope] = _render_fields(
				MUTABLE_INDEX_FIELDS.get(scope, []),
				info.sub_indexes.get(scope, {}),
				f"{key_prefix}_{scope}",
			)
			q_type, q_values = _render_quantizer(info, scope, f"{key_prefix}_{scope}")
			if q_type:
				sub_index_quantizers[scope] = {"type": q_type, "params": q_values}
	else:
		ui.section("Compression")
		quantizer_type, quantizer_params = _render_quantizer(info, "", key_prefix)

	ui.admin_warning("Updating a vector index")
	if st.button("Update Vector Index", type="primary", width="stretch", key=f"{key_prefix}_save"):
		try:
			update_vector_index(
				collection_name=collection_name,
				vector_name=info.name,
				is_named=info.is_named,
				index_type=info.index_type,
				params=params,
				quantizer_type=quantizer_type,
				quantizer_params=quantizer_params,
				sub_index_params=sub_index_params,
				sub_index_quantizers=sub_index_quantizers,
			)
			st.success(f"Vector index '{info.name}' ({info.index_type}) updated.")
		except Exception as e:
			st.error(f"Failed to update: {str(e)}")


def render_description_section(collection_name, config):
	description = st.text_input("Description", value=getattr(config, "description", "") or "", key="desc_input")

	inverted = getattr(config, "inverted_index_config", None)
	bm25 = getattr(inverted, "bm25", None) if inverted else None
	stopwords = getattr(inverted, "stopwords", None) if inverted else None

	preset = getattr(stopwords, "preset", StopwordsPreset.EN) if stopwords else StopwordsPreset.EN
	preset_names = [e.name for e in StopwordsPreset]
	preset_name = getattr(preset, "name", str(preset))
	additions = getattr(stopwords, "additions", None) or []
	removals = getattr(stopwords, "removals", None) or []

	col1, col2 = st.columns(2)
	with col1:
		bm25_b = st.number_input("BM25 b", value=float(getattr(bm25, "b", 0.75) if bm25 else 0.75), min_value=0.0, max_value=1.0, step=0.01, key="bm25_b")
		cleanup_interval = st.number_input("Cleanup Interval (s)", value=int(getattr(inverted, "cleanup_interval_seconds", 60) if inverted else 60), min_value=0, key="cleanup_interval")
		stopwords_add = st.text_input("Stopwords Additions", value=", ".join(additions), key="stop_add", help="Comma separated.")
	with col2:
		bm25_k1 = st.number_input("BM25 k1", value=float(getattr(bm25, "k1", 1.2) if bm25 else 1.2), min_value=0.0, step=0.01, key="bm25_k1")
		preset_str = st.selectbox("Stopwords Preset", preset_names, index=preset_names.index(preset_name) if preset_name in preset_names else 0, key="stopwords_preset")
		stopwords_remove = st.text_input("Stopwords Removals", value=", ".join(removals), key="stop_remove", help="Comma separated.")

	if st.button("Update Description & Inverted Index", type="primary", width="stretch", key="save_desc_inv"):
		try:
			update_description_and_inverted_index(
				collection_name,
				description,
				bm25_b,
				bm25_k1,
				cleanup_interval,
				StopwordsPreset[preset_str] if preset_str else None,
				stopwords_add,
				stopwords_remove,
			)
			st.success("Description & inverted index updated.")
		except Exception as e:
			st.error(f"Failed to update: {str(e)}")


def render_tenancy_replication_section(collection_name, config):
	multi = getattr(config, "multi_tenancy_config", None)
	repl = getattr(config, "replication_config", None)
	mt_enabled = bool(getattr(multi, "enabled", False)) if multi else False

	if not mt_enabled:
		st.caption("Multi-tenancy is disabled for this collection; the tenant settings below have no effect until it is enabled.")

	col1, col2 = st.columns(2)
	with col1:
		auto_tenant_creation = st.checkbox("Auto Tenant Creation", value=bool(getattr(multi, "auto_tenant_creation", False)) if multi else False, key="auto_tenant_creation")
		auto_tenant_activation = st.checkbox("Auto Tenant Activation", value=bool(getattr(multi, "auto_tenant_activation", False)) if multi else False, key="auto_tenant_activation")
	with col2:
		strategies = ["DELETE_ON_CONFLICT", "NO_AUTOMATED_RESOLUTION", "TIME_BASED_RESOLUTION"]
		current = getattr(repl, "deletion_strategy", None)
		current_name = getattr(current, "name", "DELETE_ON_CONFLICT")
		deletion_strategy_str = st.selectbox("Deletion Strategy", strategies, index=strategies.index(current_name) if current_name in strategies else 0, key="del_strategy")
		async_enabled = st.checkbox("Async Enabled", value=bool(getattr(repl, "async_enabled", False)) if repl else False, key="async_enabled")

	st.caption(f"Replication factor is **{getattr(repl, 'factor', 1) if repl else 1}** and cannot be changed here — use replica movement.")

	if st.button("Update Multi-tenancy & Replication", type="primary", width="stretch", key="save_multi_repl"):
		try:
			update_multi_tenancy_and_replication(
				collection_name,
				auto_tenant_creation,
				auto_tenant_activation,
				async_enabled,
				deletion_strategy_str,
			)
			st.success("Multi-tenancy & replication updated.")
		except Exception as e:
			st.error(f"Failed to update: {str(e)}")


# Get collection configuration
def get_collection_configuration():
	collections = ui.load(list_collections, error_prefix="Could not list collections")
	if not collections:
		st.info("No collections available.")
		return

	selected_collection = st.selectbox(
		"Collection",
		options=collections,
		help="Choose a collection to update its configuration",
	)
	if not selected_collection:
		return

	st.session_state.current_collection = selected_collection
	try:
		config = get_collection_config(selected_collection)
	except Exception as e:
		st.error(f"Error in retrieving collection configuration. Reason: {str(e)}")
		return

	with st.expander("Description & Inverted Index", expanded=False):
		render_description_section(selected_collection, config)

	with st.expander("Multi-tenancy & Replication", expanded=False):
		render_tenancy_replication_section(selected_collection, config)

	with st.expander("Vector Index & Compression", expanded=True):
		render_vector_index_section(selected_collection, config)


def main():
	page_header("Update")
	ui.require_connection()

	# Create tabs for different update operations
	tab1, tab2 = st.tabs(["Update Object", "Update Collection Configuration"])
	with tab1:
		get_object_details()
	with tab2:
		get_collection_configuration()


main()
