import logging
import streamlit as st
import pandas as pd
from core.collection.create import (
	get_supported_vectorizers,
	validate_file_format,
	create_collection,
	batch_upload,
	get_collection_info,
	get_collection_objects
)
from pages.utils import ui
from pages.utils.page_config import page_header

logger = logging.getLogger(__name__)

# initialize session state
def initialize_session_state():
	logger.info("initialize_session_state() called")
	if 'collection_info' not in st.session_state:
		st.session_state.collection_info = None

# Create a form for collection creation
def create_collection_form():
	with st.form("create_collection_form"):
		# Collection name input
		collection_name = st.text_input("Collection Name", placeholder="Enter collection name").strip()

		# Vectorizer selection
		vectorizers = get_supported_vectorizers()
		selected_vectorizer = st.selectbox(
			"Select Vectorizer",
			options=vectorizers,
			help="Choose a vectorizer for the collection. Select 'BYOV' if you plan to upload vectors manually."
		)

		# Show warnings for missing API keys
		if selected_vectorizer == "text2vec_openai" and not st.session_state.get("openai_key"):
			st.warning("⚠️ OpenAI API key is required. Please reconnect with the key or select BYOV.")
		elif selected_vectorizer == "text2vec_cohere" and not st.session_state.get("cohere_key"):
			st.warning("⚠️ Cohere API key is required for text2vec_cohere. Please reconnect with the key or select BYOV.")

		# File upload
		uploaded_file = st.file_uploader(
			"Upload .csv or .json Data File",
			type=["csv", "json"],
			help="Upload a CSV or JSON file containing your data"
		)

		# Submit button
		submit_button = st.form_submit_button("Create Collection and Upload Data")

		return submit_button, collection_name, selected_vectorizer, uploaded_file

# Handle form submission
def handle_form_submission(collection_name, selected_vectorizer, uploaded_file):
	logger.info("handle_form_submission() called")
	if not collection_name:
		st.error("Please enter a collection name")
		return
	if not uploaded_file:
		st.error("Please upload a data file")
		return

	# Create collection
	integration_keys = {}
	if st.session_state.get("openai_key"):
		integration_keys["X-OpenAI-Api-Key"] = st.session_state.openai_key
	if st.session_state.get("cohere_key"):
		integration_keys["X-Cohere-Api-Key"] = st.session_state.cohere_key

	success, message = create_collection(
		collection_name,
		selected_vectorizer,
		integration_keys=integration_keys,
	)
	if not success:
		st.error(message)
		return

	st.success(message)

	# Read and validate file
	file_content = uploaded_file.getvalue().decode('utf-8')
	file_type = uploaded_file.name.split('.')[-1].lower()

	is_valid, validation_msg, data = validate_file_format(file_content, file_type)
	if not is_valid:
		st.error(f"File validation failed: {validation_msg}")
		return

	summary = run_import(collection_name, data)

	# Get collection info
	success, info_msg, collection_info = get_collection_info(collection_name)
	if success:
		st.session_state.collection_info = collection_info
	else:
		st.error(info_msg)

	return summary


# Stream the file into the collection, showing live progress.
def run_import(collection_name, data):
	total = len(data)
	summary = None
	log_lines = []

	with st.status(f"Importing {total} object(s)…", expanded=True) as status:
		progress = st.progress(0.0)
		log = st.empty()

		for ok, message, payload in batch_upload(collection_name, data):
			if payload and "queued" in payload:
				progress.progress(min(payload["queued"] / max(payload["total"], 1), 1.0))
			if payload and "succeeded" in payload:
				summary = payload
			# Only surface the notable lines; per-object chatter is not useful here.
			if not ok or payload is None:
				log_lines.append(("❌ " if not ok else "") + message)
				log.markdown("\n\n".join(log_lines[-8:]))

		progress.progress(1.0)
		if summary and not summary["failed"] and not summary["aborted"]:
			status.update(label=f"Imported {summary['total']} object(s)", state="complete")
		else:
			status.update(label="Import finished with errors", state="error")

	if not summary:
		return None

	ui.metric_row([
		("Objects in file", f"{summary['total']:,}"),
		("Imported", f"{summary['succeeded']:,}"),
		("Failed", f"{len(summary['failed']):,}"),
	])

	if summary["failed"]:
		with st.expander(f"Failed objects ({len(summary['failed'])})", expanded=False):
			failures = pd.DataFrame([
				{"UUID": str(getattr(f, "original_uuid", "") or ""), "Message": str(getattr(f, "message", f))}
				for f in summary["failed"][:200]
			])
			ui.data_table(failures)
			if len(summary["failed"]) > 200:
				st.caption(f"Showing the first 200 of {len(summary['failed'])} failures.")

	return summary


# Function to display collection information
def display_collection_info():
	logger.info("display_collection_info() called")
	if not st.session_state.collection_info:
		return

	info = st.session_state.collection_info

	ui.section(info["name"])
	ui.metric_row([
		("Objects", f"{info['object_count']:,}"),
		("Properties", len(info["properties"])),
		("Vectorizer", info["vectorizer"]),
	])

	if st.button(f"Preview {info['name']} (first 100 objects)", width="stretch"):
		success, msg, df = get_collection_objects(info["name"])
		if success:
			ui.data_table(df, "No objects found.")
		else:
			st.error(msg)


def main():
	page_header("Create")
	ui.require_connection()

	initialize_session_state()
	submit_button, collection_name, selected_vectorizer, uploaded_file = create_collection_form()
	if submit_button:
		handle_form_submission(collection_name, selected_vectorizer, uploaded_file)
	display_collection_info()


main()
