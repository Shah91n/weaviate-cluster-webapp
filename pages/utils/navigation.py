"""Navigation for the multipage app.

The entrypoint (`streamlit_app.py`) is the router: it calls `build_navigation()` and
runs whatever page comes back. Because `st.navigation` is used, Streamlit ignores the
`pages/` directory as an implicit page source — every page is declared here.

While disconnected only the Cluster page is offered, so no other page can be reached
before there is a client to serve it. That is a navigation affordance rather than a
guard, so pages still call `ui.require_connection()`.
"""

import streamlit as st

# Named cluster_dashboard.py, not cluster.py, so it cannot shadow the
# pages/cluster/ handlers package. As the default page it is served at the app root.
CLUSTER_PAGE = ("pages/cluster_dashboard.py", "Cluster", "🔍")

NAV_SECTIONS = (
	(
		"Explore",
		(
			CLUSTER_PAGE,
			("pages/rbac.py", "Role-Based Access Control", "🔐"),
			("pages/multitenancy.py", "Multi Tenancy", "📄"),
			("pages/backup.py", "Backup", "💾"),
		),
	),
	(
		"Query",
		(
			("pages/agent.py", "Agent", "🤖"),
			("pages/search.py", "Search", "🧐"),
		),
	),
	(
		"Manage",
		(
			("pages/create.py", "Create", "➕"),
			("pages/read.py", "Read", "📁"),
			("pages/update.py", "Update", "🗃️"),
			("pages/delete.py", "Delete", "🗑️"),
		),
	),
)


def _page(spec, default=False):
	path, title, icon = spec
	return st.Page(path, title=title, icon=icon, default=default)


def build_navigation(client_ready):
	"""Return the navigation for the current connection state.

	Cluster is always the default page, so it stays served at the app root.
	"""
	if not client_ready:
		return st.navigation([_page(CLUSTER_PAGE, default=True)], position="sidebar")

	pages = {
		section: [_page(spec, default=spec is CLUSTER_PAGE) for spec in specs]
		for section, specs in NAV_SECTIONS
	}
	return st.navigation(pages, position="sidebar")
