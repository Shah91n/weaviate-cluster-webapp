import math

import pandas as pd
import streamlit as st

from core.collection.overview import list_collections
from core.object.read import get_tenant_names, read_objects_batch
from pages.utils.page_config import set_custom_page_config
from pages.utils.helper import update_side_bar_labels
from pages.utils.navigation import navigate

MAX_OBJECTS = 1000
ITEMS_PER_PAGE = 100
MAX_PAGES = 10


def _ensure_state():
	if "collections_list" not in st.session_state:
		st.session_state.collections_list = []
	if "collections_fetched" not in st.session_state:
		st.session_state.collections_fetched = False
	if "read_objects_preview" not in st.session_state:
		st.session_state.read_objects_preview = None
	if "read_preview_collection" not in st.session_state:
		st.session_state.read_preview_collection = None
	if "read_preview_tenant" not in st.session_state:
		st.session_state.read_preview_tenant = None
	if "read_preview_page" not in st.session_state:
		st.session_state.read_preview_page = 1


def _render_table(records):
	df = pd.DataFrame(records)
	if df.empty:
		st.warning("No data found in the selected collection.")
		return

	total_pages = min(MAX_PAGES, max(1, math.ceil(len(records) / ITEMS_PER_PAGE)))
	if st.session_state.read_preview_page > total_pages:
		st.session_state.read_preview_page = 1

	st.info("Showing only 1000 objects of the collection")

	col1, col2, col3 = st.columns([1, 1, 2])
	with col1:
		if st.button("◀️ Previous", disabled=st.session_state.read_preview_page == 1):
			st.session_state.read_preview_page -= 1
			st.rerun()
	with col2:
		if st.button("Next ▶️", disabled=st.session_state.read_preview_page >= total_pages):
			st.session_state.read_preview_page += 1
			st.rerun()
	with col3:
		page = st.number_input(
			f"Page (1-{total_pages})",
			min_value=1,
			max_value=total_pages,
			value=st.session_state.read_preview_page,
		)
		if page != st.session_state.read_preview_page:
			st.session_state.read_preview_page = page
			st.rerun()

	start = (st.session_state.read_preview_page - 1) * ITEMS_PER_PAGE
	end = start + ITEMS_PER_PAGE
	page_df = df.iloc[start:end]

	styled = page_df.astype(str).style.set_table_styles(
		[
			{
				"selector": "td",
				"props": [
					("max-width", "420px"),
					("white-space", "nowrap"),
					("overflow", "hidden"),
					("text-overflow", "ellipsis"),
				],
			}
		]
	)
	st.dataframe(styled, width="stretch", hide_index=True)


def main():
	set_custom_page_config(page_title="Read Collections")
	navigate()
	update_side_bar_labels()
	_ensure_state()

	if not st.session_state.get("client_ready"):
		st.warning("Please establish a connection to Weaviate in Cluster page")
		return

	if st.button("Fetch Collections List", width="stretch"):
		collections = list_collections()
		collections.sort()
		st.session_state.collections_list = collections
		st.session_state.collections_fetched = True
		st.session_state.read_objects_preview = None
		st.session_state.read_preview_collection = None
		st.session_state.read_preview_tenant = None
		st.session_state.read_preview_page = 1
		if not collections:
			st.warning("No collections found in the cluster.")
		st.rerun()

	if not st.session_state.collections_list:
		if st.session_state.collections_fetched:
			st.warning("No collections found in the cluster.")
		return

	selected_collection = st.selectbox(
		"Select a Collection",
		st.session_state.collections_list,
		key="main_collection_select",
	)

	tenant_names = get_tenant_names(selected_collection)
	if tenant_names:
		tenant_names = sorted(tenant_names)

	selected_tenant = None
	if tenant_names:
		selected_tenant = st.selectbox(
			"Select a Tenant",
			tenant_names,
			key="main_tenant_select",
		)

	selection_changed = (
		st.session_state.read_preview_collection != selected_collection
		or st.session_state.read_preview_tenant != selected_tenant
	)
	if selection_changed:
		st.session_state.read_objects_preview = None
		st.session_state.read_preview_page = 1

	col1, col2 = st.columns(2)
	with col1:
		read_clicked = st.button("Read Objects", width="stretch")
	with col2:
		refresh_clicked = st.button("Refresh", width="stretch")

	if read_clicked or refresh_clicked:
		if tenant_names and not selected_tenant:
			st.error("Please select a tenant for this collection")
			return
		with st.spinner("Fetching first 1000 objects with iterator... ⤵️"):
			try:
				objects = read_objects_batch(
					collection_name=selected_collection,
					tenant_name=selected_tenant,
					limit=MAX_OBJECTS,
					include_vector=True,
				)
				st.session_state.read_objects_preview = objects
				st.session_state.read_preview_collection = selected_collection
				st.session_state.read_preview_tenant = selected_tenant
				st.session_state.read_preview_page = 1
			except Exception as error:
				st.error(f"Failed to read objects: {error}")
				return

	if st.session_state.read_objects_preview is not None:
		_render_table(st.session_state.read_objects_preview)


if __name__ == "__main__":
	main()
