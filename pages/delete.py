import logging

import streamlit as st

from core.collection.delete import delete_all_collections, delete_collections, delete_tenants_from_collection
from core.collection.overview import list_collections
from core.object.read import get_tenant_names
from pages.utils import ui
from pages.utils.page_config import page_header

logger = logging.getLogger(__name__)

DELETE_ALL_PHRASE = "DELETE ALL"


def initialize_session_state():
	"""Initialize session state variables"""
	if "selected_collections" not in st.session_state:
		st.session_state.selected_collections = set()
	if "selected_tenants" not in st.session_state:
		st.session_state.selected_tenants = {}
	if "collections_list" not in st.session_state:
		st.session_state.collections_list = []
	if "mt_collections" not in st.session_state:
		st.session_state.mt_collections = {}
	if "delete_result" not in st.session_state:
		st.session_state.delete_result = None


def _finish(success, message):
	"""Record the outcome and rerun, so it survives closing the dialog."""
	st.session_state.delete_result = (success, message)
	st.rerun()


def show_delete_result():
	result = st.session_state.get("delete_result")
	if not result:
		return
	success, message = result
	ui.status_callout("ok" if success else "critical", message)
	st.session_state.delete_result = None


# --------------------------------------------------------------------------
# Confirmation dialogs — a delete is irreversible, so nothing here fires
# straight off a single button press.
# --------------------------------------------------------------------------

@st.dialog("Delete collections")
def confirm_delete_collections(names):
	st.error(
		f"This permanently deletes {len(names)} collection(s) and every object inside them. "
		"There is no undo."
	)
	for name in sorted(names):
		st.markdown(f"- `{name}`")
	ui.admin_warning("Deleting collections")

	col1, col2 = st.columns(2)
	with col1:
		if st.button("Delete permanently", type="primary", width="stretch"):
			success, message = delete_collections(list(names))
			if success:
				st.session_state.selected_collections.clear()
			_finish(success, message)
	with col2:
		if st.button("Cancel", width="stretch"):
			st.rerun()


@st.dialog("Delete tenants")
def confirm_delete_tenants(selection):
	total = sum(len(tenants) for tenants in selection.values())
	st.error(
		f"This permanently deletes {total} tenant(s) across {len(selection)} collection(s), "
		"including all of their objects. There is no undo."
	)
	for collection, tenants in sorted(selection.items()):
		st.markdown(f"**{collection}** — {len(tenants)} tenant(s)")
	ui.admin_warning("Deleting tenants")

	col1, col2 = st.columns(2)
	with col1:
		if st.button("Delete permanently", type="primary", width="stretch"):
			messages = []
			all_ok = True
			for collection, tenants in selection.items():
				success, message = delete_tenants_from_collection(collection, list(tenants))
				messages.append(message)
				all_ok = all_ok and success
				if success:
					st.session_state.selected_tenants[collection].clear()
			_finish(all_ok, " ".join(messages))
	with col2:
		if st.button("Cancel", width="stretch"):
			st.rerun()


@st.dialog("Delete ALL collections")
def confirm_delete_all(collection_count):
	st.error(
		f"This wipes all {collection_count} collection(s) and every object in the cluster. "
		"This is irreversible."
	)
	phrase = st.text_input(f"Type `{DELETE_ALL_PHRASE}` to confirm", key="delete_all_phrase")
	ui.admin_warning("Deleting all collections")

	col1, col2 = st.columns(2)
	with col1:
		if st.button(
			"Delete everything",
			type="primary",
			width="stretch",
			disabled=phrase.strip() != DELETE_ALL_PHRASE,
		):
			success, message = delete_all_collections()
			if success:
				st.session_state.selected_collections.clear()
			_finish(success, message)
	with col2:
		if st.button("Cancel", width="stretch"):
			st.rerun()


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

def handle_collection_selection():
	"""Handle the regular collections section"""
	regular_collections = [
		c for c in st.session_state.collections_list if c not in st.session_state.mt_collections
	]

	ui.section("Collections", "Single-tenant collections. Deleting one removes all of its objects.")
	if not regular_collections:
		st.info("No single-tenant collections found.")
		return

	selected = st.session_state.selected_collections
	with st.container(height=340, border=True):
		for col in sorted(regular_collections):
			if st.checkbox(col, key=f"col_{col}", value=col in selected):
				selected.add(col)
			else:
				selected.discard(col)

	st.caption(f"{len(selected)} of {len(regular_collections)} selected")
	if st.button(
		"Delete Selected Collections",
		icon="🗑️",
		type="primary",
		width="stretch",
		disabled=not selected,
	):
		confirm_delete_collections(set(selected))


def handle_mt_collection_selection():
	"""Handle the multi-tenancy collections section"""
	ui.section("Multi-Tenancy Collections", "Select individual tenants to remove.")
	if not st.session_state.mt_collections:
		st.info("No multi-tenancy collections found.")
		return

	for collection in sorted(st.session_state.mt_collections.keys()):
		tenants = st.session_state.mt_collections[collection]
		chosen = st.session_state.selected_tenants.setdefault(collection, set())
		with st.expander(f"{collection} — {len(tenants)} tenant(s)"):
			if not tenants:
				st.info("No tenants found in this collection.")
				continue
			for tenant in tenants:
				if st.checkbox(tenant, key=f"tenant_{collection}_{tenant}", value=tenant in chosen):
					chosen.add(tenant)
				else:
					chosen.discard(tenant)

	selection = {c: t for c, t in st.session_state.selected_tenants.items() if t}
	total = sum(len(t) for t in selection.values())
	st.caption(f"{total} tenant(s) selected")
	if st.button(
		"Delete Selected Tenants",
		icon="🗑️",
		type="primary",
		width="stretch",
		disabled=not selection,
	):
		confirm_delete_tenants({c: set(t) for c, t in selection.items()})


def get_all_collections_and_tenants():
	"""Main function to display and manage collections"""
	collections = sorted(ui.load(list_collections, error_prefix="Could not list collections"))
	st.session_state.collections_list = collections

	st.session_state.mt_collections = {}
	for collection in collections:
		tenants = get_tenant_names(collection)
		if tenants:
			st.session_state.mt_collections[collection] = sorted(tenants)

	show_delete_result()

	ui.metric_row([
		("Collections", len(collections)),
		("Multi-tenant", len(st.session_state.mt_collections)),
		("Tenants", sum(len(t) for t in st.session_state.mt_collections.values())),
	])

	handle_collection_selection()
	st.markdown("---")
	handle_mt_collection_selection()

	st.markdown("---")
	with st.expander("⚠️ Danger zone", expanded=False):
		st.caption("Wipes every collection in the cluster. Requires typing a confirmation phrase.")
		if st.button("Delete ALL Collections", icon="💀", width="stretch", key="delete_all_btn", disabled=not collections):
			confirm_delete_all(len(collections))


def main():
	page_header("Delete")
	ui.require_connection()

	initialize_session_state()
	get_all_collections_and_tenants()


main()
