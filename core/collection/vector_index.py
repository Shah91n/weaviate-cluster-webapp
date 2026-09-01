"""Vector index introspection and reconfiguration.

Weaviate exposes four vector index types — hnsw, flat, dynamic and hfresh — each
with its own set of mutable parameters, and two collection layouts:

* modern: one or more named vectors under ``config.vector_config``
* legacy: a single vector under ``config.vector_index_config`` + ``config.vectorizer``

A ``dynamic`` index nests a full hnsw and flat config (and therefore its
quantizers) one level down, which is why reading ``vic.quantizer`` on a dynamic
index always returns ``None`` even when compression is enabled.

This module normalises all of that so callers never branch on layout or index
type themselves.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from weaviate.classes.config import (
	PQEncoderDistribution,
	PQEncoderType,
	Reconfigure,
	VectorFilterStrategy,
)

from core.connection.weaviate_connection_manager import get_weaviate_client

logger = logging.getLogger(__name__)

HNSW = "hnsw"
FLAT = "flat"
DYNAMIC = "dynamic"
HFRESH = "hfresh"

# A dynamic index holds a nested hnsw and flat config; every other type is flat.
SUB_INDEX_SCOPES = {DYNAMIC: (HNSW, FLAT)}

_QUANTIZER_TYPES = {
	"_PQConfig": "pq",
	"_BQConfig": "bq",
	"_SQConfig": "sq",
	"_RQConfig": "rq",
}


# --------------------------------------------------------------------------
# Mutable field registry
#
# Sources: https://docs.weaviate.io/weaviate/config-refs/collections#mutability
#          https://docs.weaviate.io/weaviate/config-refs/indexing/vector-index
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class MutableField:
	"""One editable parameter, with everything a form needs to render it."""

	name: str
	label: str
	kind: str  # "int" | "enum"
	default: Any
	help: str = ""
	options: Optional[List[str]] = None
	min_value: Optional[int] = None


MUTABLE_INDEX_FIELDS: Dict[str, List[MutableField]] = {
	HNSW: [
		MutableField("dynamic_ef_factor", "Dynamic EF Factor", "int", 8, min_value=1),
		MutableField("dynamic_ef_min", "Dynamic EF Min", "int", 100, min_value=1),
		MutableField("dynamic_ef_max", "Dynamic EF Max", "int", 500, min_value=1),
		MutableField("ef", "EF", "int", -1, help="-1 lets Weaviate pick ef dynamically.", min_value=-1),
		MutableField(
			"filter_strategy",
			"Filter Strategy",
			"enum",
			"SWEEPING",
			options=[e.name for e in VectorFilterStrategy],
		),
		MutableField("flat_search_cutoff", "Flat Search Cutoff", "int", 40000, min_value=0),
		MutableField("vector_cache_max_objects", "Vector Cache Max Objects", "int", 1000000000000, min_value=0),
	],
	FLAT: [
		MutableField("vector_cache_max_objects", "Vector Cache Max Objects", "int", 1000000000000, min_value=0),
	],
	DYNAMIC: [
		MutableField(
			"threshold",
			"Threshold",
			"int",
			10000,
			help="Object count at which the index switches from flat to HNSW.",
			min_value=0,
		),
	],
	HFRESH: [
		MutableField(
			"max_posting_size_kb",
			"Max Posting Size (KB)",
			"int",
			48,
			help="Only affects newly-indexed data — existing postings are not re-partitioned.",
			min_value=8,
		),
		MutableField(
			"search_probe",
			"Search Probe",
			"int",
			256,
			help="Posting lists searched per query. Higher = better recall, slower queries.",
			min_value=1,
		),
	],
}

MUTABLE_QUANTIZER_FIELDS: Dict[str, List[MutableField]] = {
	"pq": [
		MutableField("centroids", "Centroids", "int", 256, min_value=1),
		MutableField("segments", "Segments", "int", 0, min_value=0),
		MutableField("training_limit", "Training Limit", "int", 100000, min_value=1),
		MutableField("encoder_type", "Encoder Type", "enum", "KMEANS", options=[e.name for e in PQEncoderType]),
		MutableField(
			"encoder_distribution",
			"Encoder Distribution",
			"enum",
			"LOG_NORMAL",
			options=[e.name for e in PQEncoderDistribution],
		),
	],
	"bq": [
		MutableField("rescore_limit", "Rescore Limit", "int", 20, min_value=-1),
	],
	"sq": [
		MutableField("rescore_limit", "Rescore Limit", "int", 20, min_value=-1),
		MutableField("training_limit", "Training Limit", "int", 100000, min_value=1),
	],
	"rq": [
		MutableField(
			"rescore_limit",
			"Rescore Limit",
			"int",
			20,
			help="Candidates rescored against uncompressed vectors. Higher = better recall.",
			min_value=-1,
		),
	],
}

# Quantizer types each index type accepts on an update, per the Reconfigure API.
QUANTIZERS_BY_INDEX: Dict[str, List[str]] = {
	HNSW: ["pq", "bq", "sq", "rq"],
	FLAT: ["bq", "rq"],
	DYNAMIC: ["bq"],
	HFRESH: ["rq"],
}

# Index types whose quantizer settings cannot be changed after creation.
IMMUTABLE_QUANTIZER_INDEXES = {FLAT}


# --------------------------------------------------------------------------
# Read side
# --------------------------------------------------------------------------

@dataclass
class QuantizerInfo:
	"""A quantizer found on an index, or on one arm of a dynamic index."""

	type: str  # "pq" | "bq" | "sq" | "rq"
	scope: str  # "" for a simple index, "hnsw"/"flat" for a dynamic index
	params: Dict[str, Any] = field(default_factory=dict)

	@property
	def label(self) -> str:
		return f"{self.scope}.{self.type.upper()}" if self.scope else self.type.upper()


@dataclass
class VectorIndexInfo:
	"""One vector's index, normalised across layouts and index types."""

	name: str
	index_type: str
	vectorizer: Optional[str] = None
	vectorizer_params: Dict[str, Any] = field(default_factory=dict)
	is_named: bool = True
	params: Dict[str, Any] = field(default_factory=dict)
	sub_indexes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
	quantizers: List[QuantizerInfo] = field(default_factory=list)

	@property
	def scopes(self) -> List[str]:
		"""The arms that carry a quantizer: [""] normally, ["hnsw", "flat"] for dynamic."""
		return list(SUB_INDEX_SCOPES.get(self.index_type, ("",)))

	def quantizer_for(self, scope: str = "") -> Optional[QuantizerInfo]:
		for q in self.quantizers:
			if q.scope == scope:
				return q
		return None

	@property
	def is_compressed(self) -> bool:
		"""True only when every arm of the index carries a quantizer."""
		return all(self.quantizer_for(scope) is not None for scope in self.scopes)

	@property
	def compression_summary(self) -> str:
		if not self.quantizers:
			return "none"
		return ", ".join(q.label for q in self.quantizers)


def _public_attrs(obj: Any, skip: tuple = ()) -> Dict[str, Any]:
	"""Read the public dataclass fields off an SDK config object."""
	if obj is None:
		return {}
	raw = vars(obj) if hasattr(obj, "__dict__") else {}
	return {k: v for k, v in raw.items() if not k.startswith("_") and k not in skip}


def _read_quantizer(vic: Any, scope: str) -> Optional[QuantizerInfo]:
	quantizer = getattr(vic, "quantizer", None)
	if quantizer is None:
		return None

	q_type = _QUANTIZER_TYPES.get(type(quantizer).__name__)
	if q_type is None:
		q_type = type(quantizer).__name__.lstrip("_").replace("Config", "").lower()

	params = _public_attrs(quantizer, skip=("encoder",))
	encoder = getattr(quantizer, "encoder", None)
	if encoder is not None:
		params["encoder_type"] = getattr(encoder, "type_", None)
		params["encoder_distribution"] = getattr(encoder, "distribution", None)
	return QuantizerInfo(type=q_type, scope=scope, params=params)


def _index_type_of(vic: Any) -> str:
	"""Ask the SDK config object what it is — never assume hnsw."""
	vector_index_type = getattr(vic, "vector_index_type", None)
	if callable(vector_index_type):
		try:
			return str(vector_index_type())
		except Exception:  # pragma: no cover - defensive
			logger.debug("vector_index_type() failed on %s", type(vic).__name__)
	return type(vic).__name__.lstrip("_").replace("VectorIndexConfig", "").lower() or HNSW


def _describe_one(
	name: str,
	vic: Any,
	vectorizer: Optional[str],
	is_named: bool,
	vectorizer_params: Optional[Dict[str, Any]] = None,
) -> VectorIndexInfo:
	index_type = _index_type_of(vic)
	info = VectorIndexInfo(
		name=name,
		index_type=index_type,
		vectorizer=vectorizer,
		vectorizer_params=vectorizer_params or {},
		is_named=is_named,
		params=_public_attrs(vic, skip=("quantizer", "hnsw", "flat")),
	)

	if index_type in SUB_INDEX_SCOPES:
		# A dynamic index carries its real settings — and its quantizers — one level down.
		for scope in SUB_INDEX_SCOPES[index_type]:
			sub = getattr(vic, scope, None)
			if sub is None:
				continue
			info.sub_indexes[scope] = _public_attrs(sub, skip=("quantizer",))
			quantizer = _read_quantizer(sub, scope)
			if quantizer is not None:
				info.quantizers.append(quantizer)
	else:
		quantizer = _read_quantizer(vic, "")
		if quantizer is not None:
			info.quantizers.append(quantizer)

	return info


def _vectorizer_details(vectorizer_obj: Any):
	"""(module name, module params) for a vectorizer config object.

	The params are the module's own settings — model, baseURL, source properties —
	which is what the raw schema reports under ``moduleConfig``. Reading only the
	name throws them away, so a collection vectorized by OpenAI looks identical to
	one vectorized by anything else.
	"""
	if vectorizer_obj is None:
		return None, {}
	inner = getattr(vectorizer_obj, "vectorizer", vectorizer_obj)
	name = str(getattr(inner, "value", inner))
	params = {
		k: v
		for k, v in _public_attrs(vectorizer_obj, skip=("vectorizer",)).items()
		if v is not None
	}
	return name, params


def describe_vector_indexes(config: Any) -> List[VectorIndexInfo]:
	"""Normalise a collection config into one VectorIndexInfo per vector.

	Handles both the named-vector layout and the legacy single-vector layout, and
	unwraps dynamic indexes so their nested quantizers are visible.
	"""
	if config is None:
		return []

	vector_config = getattr(config, "vector_config", None)
	if vector_config:
		indexes = []
		for vec_name, named_vec in vector_config.items():
			vic = getattr(named_vec, "vector_index_config", None)
			if vic is None:
				continue
			vec_name_str, vec_params = _vectorizer_details(getattr(named_vec, "vectorizer", None))
			indexes.append(
				_describe_one(
					name=vec_name,
					vic=vic,
					vectorizer=vec_name_str,
					is_named=True,
					vectorizer_params=vec_params,
				)
			)
		return indexes

	vic = getattr(config, "vector_index_config", None)
	if vic is None:
		return []

	# The legacy layout splits the vectorizer in two: `vectorizer` names the module,
	# `vectorizer_config` carries its settings.
	name, params = _vectorizer_details(getattr(config, "vectorizer_config", None))
	vectorizer = getattr(config, "vectorizer", None)
	if vectorizer is not None:
		name = str(getattr(vectorizer, "value", vectorizer))
	return [
		_describe_one(
			name="default",
			vic=vic,
			vectorizer=name,
			is_named=False,
			vectorizer_params=params,
		)
	]


# --------------------------------------------------------------------------
# Write side
# --------------------------------------------------------------------------

def _build_quantizer_update(quantizer_type: str, params: Dict[str, Any]):
	builder = getattr(Reconfigure.VectorIndex.Quantizer, quantizer_type, None)
	if builder is None:
		raise Exception(f"Unsupported quantizer type: {quantizer_type}")

	kwargs: Dict[str, Any] = {}
	for key, value in params.items():
		if value is None:
			continue
		if key == "encoder_type":
			kwargs[key] = value if isinstance(value, PQEncoderType) else PQEncoderType[str(value)]
		elif key == "encoder_distribution":
			kwargs[key] = (
				value
				if isinstance(value, PQEncoderDistribution)
				else PQEncoderDistribution[str(value)]
			)
		else:
			kwargs[key] = value
	return builder(**kwargs)


def _coerce_index_params(index_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
	kwargs: Dict[str, Any] = {}
	for key, value in params.items():
		if value is None:
			continue
		if key == "filter_strategy":
			kwargs[key] = (
				value if isinstance(value, VectorFilterStrategy) else VectorFilterStrategy[str(value)]
			)
		else:
			kwargs[key] = value
	return kwargs


def build_index_update(
	index_type: str,
	params: Optional[Dict[str, Any]] = None,
	quantizer_type: Optional[str] = None,
	quantizer_params: Optional[Dict[str, Any]] = None,
	sub_index_params: Optional[Dict[str, Dict[str, Any]]] = None,
	sub_index_quantizers: Optional[Dict[str, Dict[str, Any]]] = None,
):
	"""Build the ``_VectorIndexConfig*Update`` object for this index type.

	``sub_index_params`` / ``sub_index_quantizers`` are keyed by scope ("hnsw",
	"flat") and only apply to a dynamic index.
	"""
	builder = getattr(Reconfigure.VectorIndex, index_type, None)
	if builder is None:
		raise Exception(f"Unsupported vector index type: {index_type}")

	kwargs = _coerce_index_params(index_type, params or {})

	if index_type in SUB_INDEX_SCOPES:
		for scope in SUB_INDEX_SCOPES[index_type]:
			scope_params = (sub_index_params or {}).get(scope) or {}
			scope_quantizer = (sub_index_quantizers or {}).get(scope) or {}
			q_type = scope_quantizer.get("type")
			nested = build_index_update(
				index_type=scope,
				params=scope_params,
				quantizer_type=q_type,
				quantizer_params=scope_quantizer.get("params"),
			)
			if nested is not None:
				kwargs[scope] = nested
	elif quantizer_type:
		kwargs["quantizer"] = _build_quantizer_update(quantizer_type, quantizer_params or {})

	return builder(**kwargs)


def _apply_index_update(collection, vector_name, is_named, index_update):
	"""Send an index update using the right call for the collection layout.

	Named-vector collections go through ``vector_config=Reconfigure.Vectors.update(...)``;
	legacy single-vector collections go through ``vectorizer_config=``, which is the only
	parameter that also accepts a dynamic index update.
	"""
	if is_named:
		collection.config.update(
			vector_config=Reconfigure.Vectors.update(
				name=vector_name,
				vector_index_config=index_update,
			)
		)
	else:
		collection.config.update(vectorizer_config=index_update)


def update_vector_index(
	collection_name: str,
	vector_name: str,
	is_named: bool,
	index_type: str,
	params: Optional[Dict[str, Any]] = None,
	quantizer_type: Optional[str] = None,
	quantizer_params: Optional[Dict[str, Any]] = None,
	sub_index_params: Optional[Dict[str, Dict[str, Any]]] = None,
	sub_index_quantizers: Optional[Dict[str, Dict[str, Any]]] = None,
) -> bool:
	"""Apply a vector index update for any index type and either collection layout."""
	logger.info(
		"update_vector_index() called for collection: %s, vector: %s, type: %s",
		collection_name,
		vector_name,
		index_type,
	)
	try:
		client = get_weaviate_client()
		collection = client.collections.use(collection_name)
		index_update = build_index_update(
			index_type=index_type,
			params=params,
			quantizer_type=quantizer_type,
			quantizer_params=quantizer_params,
			sub_index_params=sub_index_params,
			sub_index_quantizers=sub_index_quantizers,
		)

		# NOTE: quantizer updates on an index whose config has no "pq" key (HFresh) need
		# weaviate-client > 4.23.0 — earlier versions read vector_index_config["pq"]
		# unguarded in _CollectionConfigUpdate.__check_quantizers and raise KeyError('pq').
		_apply_index_update(collection, vector_name, is_named, index_update)
		return True
	except Exception as e:
		logger.error(f"Failed to update vector index: {str(e)}")
		raise Exception(f"Failed to update vector index: {str(e)}")
