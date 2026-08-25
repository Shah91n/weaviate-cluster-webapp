"""Shared presentation helpers.

Every page rendered its own headings, key/value tables and status lines, which is
why the app looked different from screen to screen. These helpers are the single
place that decides how a section header, a metric row, a config table or a status
line looks.
"""

import logging

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# Status vocabulary shared by the diagnostics and config screens.
STATUS_ICONS = {
	"ok": "✅",
	"warning": "⚠️",
	"critical": "🔴",
	"info": "ℹ️",
}


def require_connection():
	"""Stop rendering the page unless a client is connected.

	Navigation already hides these pages while disconnected; this is the backstop for
	a direct URL or a session that disconnects mid-flight.
	"""
	if not st.session_state.get("client_ready"):
		st.warning("Connect to a Weaviate cluster using the sidebar to continue.")
		st.stop()


def load(reader, *args, error_prefix="Could not load data", **kwargs):
	"""Call a core/ reader and show its error instead of rendering an empty page.

	The readers raise rather than returning an empty result, so a permissions or
	connection failure is never displayed as "nothing found".
	"""
	try:
		return reader(*args, **kwargs)
	except Exception as e:
		st.error(f"{error_prefix}: {e}")
		st.stop()


def section(title, caption=None, icon=None):
	"""A consistent section heading, optionally with a one-line explanation."""
	heading = f"{icon} {title}" if icon else title
	st.markdown(f"##### {heading}")
	if caption:
		st.caption(caption)


def metric_row(metrics, columns=None):
	"""Render a row of KPI tiles from a list of (label, value) or (label, value, help)."""
	if not metrics:
		return
	cols = st.columns(columns or len(metrics))
	for col, metric in zip(cols, metrics):
		label, value = metric[0], metric[1]
		helptext = metric[2] if len(metric) > 2 else None
		with col:
			st.metric(label, value, help=helptext)


def kv_table(data, key_label="Setting", value_label="Value"):
	"""Render a dict as a two-column table.

	Nested config objects read far better as rows than as one very wide record.
	"""
	if not data:
		st.caption("— none —")
		return
	if not isinstance(data, dict):
		st.markdown(f"**{data}**")
		return

	df = pd.DataFrame(
		[(str(k), "—" if v is None else str(v)) for k, v in data.items()],
		columns=[key_label, value_label],
	)
	st.dataframe(
		df,
		width="stretch",
		hide_index=True,
		column_config={
			key_label: st.column_config.TextColumn(key_label, width="medium"),
			value_label: st.column_config.TextColumn(value_label, width="large"),
		},
	)


def data_table(data, empty_message="No data available.", column_config=None, height=None):
	"""Render tabular data without the stringify-everything pattern.

	Accepts a DataFrame or a list of dicts — several core/ readers return the latter —
	so callers never have to wrap their result. Only object columns are coerced to
	text, so numbers stay right-aligned and sortable instead of becoming strings.
	"""
	if data is None:
		st.caption(empty_message)
		return

	df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
	if df.empty:
		st.caption(empty_message)
		return

	safe = df.copy()
	for column in safe.columns:
		if safe[column].dtype == "object":
			safe[column] = safe[column].map(lambda v: "" if v is None else str(v))

	# st.dataframe rejects height=None, so only pass it when a height was asked for.
	extra = {"height": height} if height is not None else {}
	st.dataframe(
		safe,
		width="stretch",
		hide_index=True,
		column_config=column_config,
		**extra,
	)


def status_line(status, message):
	"""One diagnostic line, prefixed with the icon for its status."""
	st.markdown(f"{STATUS_ICONS.get(status, 'ℹ️')} {message}")


def status_callout(status, message):
	"""A full-width callout using the Streamlit box that matches the status."""
	if status == "ok":
		st.success(message)
	elif status == "warning":
		st.warning(message)
	elif status == "critical":
		st.error(message)
	else:
		st.info(message)


def admin_warning(action="This operation"):
	st.warning(f"⚠️ {action} requires an admin API key.")


def download_list(label, items, file_name, key):
	"""Offer a one-column CSV of the given items."""
	if not items:
		return
	csv_data = "item\n" + "\n".join(str(i) for i in items)
	st.download_button(
		label,
		data=csv_data.encode(),
		file_name=file_name,
		mime="text/csv",
		key=key,
	)
