import os

import streamlit as st
from PIL import Image

LOGO_PATH = os.path.join("assets", "weaviate-logo.png")

PAGE_CAPTIONS = {
	"Cluster": "Connect to a cluster and inspect nodes, shards, schema and health.",
	"Role-Based Access Control": "Users, roles and the permissions behind them.",
	"Multi Tenancy": "Multi-tenant collections and the state of their tenants.",
	"Agent": "Ask questions about your data in natural language.",
	"Search": "Hybrid, keyword and vector search with named-vector support.",
	"Create": "Create a collection and stream a CSV or JSON file into it.",
	"Read": "Browse objects page by page, with optional tenant scoping.",
	"Update": "Edit object properties and the mutable parts of a collection config.",
	"Delete": "Remove collections or individual tenants.",
	"Backup": "Recent backups from the cluster's configured storage backend.",
}


# Called once, from the entrypoint router. st.set_page_config must not be called
# again from a page — with st.navigation the entrypoint owns it.
def configure_app(layout="wide", initial_sidebar_state="expanded"):
	st.set_page_config(
		page_title="Weaviate Cluster",
		layout=layout,
		initial_sidebar_state=initial_sidebar_state,
		page_icon=Image.open(LOGO_PATH),
	)


# Called at the top of each page body. The browser tab title comes from the page's
# st.Page(title=...); this renders the in-page heading.
def page_header(page_title, caption=None):
	st.title(page_title)
	caption = caption or PAGE_CAPTIONS.get(page_title)
	if caption:
		st.caption(caption)
