import logging

import streamlit as st

from core.connection.weaviate_connection_manager import get_weaviate_manager

logger = logging.getLogger(__name__)


def _shorten_endpoint(endpoint, limit=34):
	"""Cloud endpoints are long enough to wrap the sidebar three times over."""
	if not endpoint:
		return "N/A"
	endpoint = str(endpoint).replace("https://", "").replace("http://", "")
	if len(endpoint) <= limit:
		return endpoint
	return f"{endpoint[: limit - 1]}…"


# Show the live connection state in the sidebar.
def update_side_bar_labels():
	logger.info("update_side_bar_labels called")
	manager = get_weaviate_manager()

	# Sidebar status only — the main-area prompt is require_connection()'s job, and
	# the router calls this on every page, so a warning here would double up.
	if not manager.is_ready():
		st.sidebar.error("Disconnected")
		return

	endpoint = manager.get_endpoint()
	st.sidebar.success("Connected")
	st.sidebar.caption("ENDPOINT")
	st.sidebar.markdown(f"`{_shorten_endpoint(endpoint)}`", help=str(endpoint))
	version = st.session_state.get("server_version")
	if version:
		st.sidebar.caption(f"Server version {version}")


# Clear the session state
def clear_session_state():
	logger.info("clear_session_state called")
	for key in list(st.session_state.keys()):
		del st.session_state[key]
	st.cache_data.clear()
	st.rerun()
