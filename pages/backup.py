import streamlit as st
import pandas as pd
from pages.utils.navigation import navigate
from pages.utils.helper import update_side_bar_labels
from pages.utils.page_config import set_custom_page_config
from core.backup.list import list_backups, get_backup_backend_label


def main():
    set_custom_page_config(page_title="Backup")
    navigate()
    if not st.session_state.get("client_ready"):
        st.warning("Please Establish a connection to Weaviate in Cluster page!")
        return

    update_side_bar_labels()

    backend_label = get_backup_backend_label()
    st.write(f"Detected storage backend: **{backend_label}**")

    if st.button("List Backups", width="stretch"):
        try:
            backups = list_backups(limit=10)
            if not backups:
                st.info("No backups found.")
            else:
                df = pd.DataFrame(backups)
                st.subheader("💾 Backups")
                st.dataframe(df, width="stretch")
                st.caption(f"Showing {len(df)} most recent backup(s)")
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Failed to list backups: {e}")


if __name__ == "__main__":
    main()
