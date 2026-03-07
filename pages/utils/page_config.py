import streamlit as st
from PIL import Image
import os

# Custom function to set the page configuration
def set_custom_page_config(page_title="Weaviate Cluster", layout="wide", initial_sidebar_state="expanded"):

	logo_path = os.path.join("assets", "weaviate-logo.png")
	logo_image = Image.open(logo_path)

	st.set_page_config(
		page_title=f"{page_title} {st.session_state.get('active_endpoint', 'N/A')}",
		layout=layout,
		initial_sidebar_state=initial_sidebar_state,
		page_icon=logo_image,
	)

	st.title(page_title)
	