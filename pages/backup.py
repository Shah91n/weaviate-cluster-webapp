import pandas as pd
import streamlit as st

from core.backup.list import get_backup_backend_label, list_backups
from pages.utils import ui
from pages.utils.page_config import page_header


def main():
	page_header("Backup")
	ui.require_connection()

	backend_label = get_backup_backend_label()
	st.caption(f"Storage backend detected from the endpoint: **{backend_label}**")

	if st.button("List Backups", icon="💾", width="stretch"):
		st.session_state["backup_listed"] = True

	if not st.session_state.get("backup_listed"):
		return

	try:
		backups = list_backups(limit=10)
	except ValueError as e:
		st.error(str(e))
		return
	except Exception as e:
		st.error(f"Failed to list backups: {e}")
		return

	if not backups:
		st.info("No backups found.")
		return

	df = pd.DataFrame(backups)
	ui.section("Backups", f"The {len(df)} most recent backup(s)", icon="💾")

	if "Status" in df.columns:
		statuses = df["Status"].value_counts().to_dict()
		ui.metric_row([("Backups", len(df))] + [(str(k), int(v)) for k, v in statuses.items()])

	ui.data_table(df)


main()
