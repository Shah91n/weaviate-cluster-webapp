import streamlit as st
from PIL import Image
import os

# This function is used to set up the sidebar navigation for the Streamlit app.
# It includes links to different pages of the app and displays the Weaviate logo.
def navigate():
	logo_path = os.path.join("assets", "weaviate-logo.png")
	logo_image = Image.open(logo_path)
	st.sidebar.image(logo_image,width=100)
	st.sidebar.page_link("streamlit_app.py", label="Cluster", icon="🔍")
	st.sidebar.page_link("pages/rbac.py", label="Role-Based Access Control", icon="🔐")
	st.sidebar.page_link("pages/multitenancy.py", label="Multi Tenancy", icon="📄")
	st.sidebar.page_link("pages/agent.py", label="Agent", icon="🤖")
	st.sidebar.page_link("pages/search.py", label="Search", icon="🧐")
	st.sidebar.page_link("pages/create.py", label="Create", icon="➕")
	st.sidebar.page_link("pages/read.py", label="Read", icon="📁")
	st.sidebar.page_link("pages/update.py", label="Update", icon="🗃️")
	st.sidebar.page_link("pages/delete.py", label="Delete", icon="🗑️")
	st.sidebar.markdown("---")
