import streamlit as st

from core.rbac.read import (
	list_all_permissions,
	list_all_roles,
	list_all_users,
	list_users_roles_permissions_combined,
)
from pages.utils import ui
from pages.utils.page_config import page_header

# key -> (button label, icon, heading, loader, count label)
RBAC_VIEWS = (
	("users", "Users", "🫂", list_all_users, "user(s)"),
	("roles", "Roles", "🎭", list_all_roles, "role(s)"),
	("permissions", "Permissions", "🔐", list_all_permissions, "permission entr(ies)"),
	("combined", "User Permissions Report", "📋", list_users_roles_permissions_combined, "user-role assignment(s)"),
)


def main():
	page_header("Role-Based Access Control")
	ui.require_connection()

	# The selection is kept in session state so the table survives any other rerun.
	active = st.session_state.get("rbac_view")
	columns = st.columns(len(RBAC_VIEWS))
	for column, (key, label, icon, _, _) in zip(columns, RBAC_VIEWS):
		with column:
			if st.button(
				label,
				icon=icon,
				width="stretch",
				key=f"rbac_{key}",
				type="primary" if active == key else "secondary",
			):
				st.session_state["rbac_view"] = key
				active = key

	if not active:
		st.info("Select one of the buttons above to view RBAC information.")
		return

	_, label, icon, loader, count_label = next(v for v in RBAC_VIEWS if v[0] == active)
	try:
		rows = loader()
	except Exception as e:
		st.error(f"Failed to load {label.lower()}: {e}")
		return

	st.markdown("---")
	ui.section(label, icon=icon)
	ui.metric_row([(label, len(rows) if rows is not None else 0)])
	ui.data_table(rows, f"No {count_label} found.")


main()
