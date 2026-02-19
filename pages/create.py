import streamlit as st
from utils.collections.create import (
	get_supported_vectorizers,
	validate_file_format,
	create_collection,
	batch_upload,
	get_collection_info,
	get_collection_objects
)
from utils.page_config import set_custom_page_config
from utils.sidebar.navigation import navigate
from utils.sidebar.helper import update_side_bar_labels

# initialize session state
def initialize_session_state():
	print("initialize_session_state() called")
	if 'collection_info' not in st.session_state:
		st.session_state.collection_info = None

# Create a form for collection creation
def create_collection_form():
	print("create_collection_form() called")
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
		if selected_vectorizer == "text2vec_openai" and not st.session_state.get("active_openai_key"):
			st.warning("⚠️ OpenAI API key is required. Please reconnect with the key or select BYOV.")
		elif selected_vectorizer == "text2vec_cohere" and not st.session_state.get("active_cohere_key"):
			st.warning("⚠️ Cohere API key is required for text2vec_cohere. Please reconnect with the key or select BYOV.")
		elif selected_vectorizer == "text2vec_huggingface" and not st.session_state.get("active_huggingface_key"):
			st.warning("⚠️ HuggingFace API key is required. Please reconnect with the key or select BYOV.")

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
def handle_form_submission(client, collection_name, selected_vectorizer, uploaded_file):
	print("handle_form_submission() called")
	if not collection_name:
		st.error("Please enter a collection name")
		return
	if not uploaded_file:
		st.error("Please upload a data file")
		return

	# Create collection
	success, message = create_collection(client, collection_name, selected_vectorizer)
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

	# Create a placeholder for progress updates
	progress_placeholder = st.empty()

	progress_messages = []

	# Process the batch upload generator
	for success, message, _ in batch_upload(client, collection_name, data):
		progress_messages.append(message)
		# Update progress display with HTML scrollable div on each yield
		html_content = f"""
		                <div style="
		                	height: 300px;
		                	overflow-y: auto;
		                	border: 1px solid #ccc;
		                	padding: 10px;
		                ">
		                {"<br>".join(progress_messages)}
		                </div>
		                """
		progress_placeholder.markdown(html_content, unsafe_allow_html=True)

	# After the loop finishes, the last message should indicate completion status
	# The detailed failed objects will be printed to the terminal

	# Get collection info
	success, info_msg, collection_info = get_collection_info(client, collection_name)
	if success:
		st.session_state.collection_info = collection_info
	else:
		st.error(info_msg)


# Function to display collection information
def display_collection_info(client):
	print("display_collection_info() called")
	if not st.session_state.collection_info:
		return

	info = st.session_state.collection_info

	# Button to view objects
	if st.button(f"View {info['name']} Collection (100 Objects only)", use_container_width=True):
		# Display only Object Count
		st.metric("Object Count", info["object_count"])

		# Then display the objects
		success, msg, df = get_collection_objects(client, info["name"])
		if success:
			st.dataframe(df)
		else: 
			st.error(msg)

def main():

	set_custom_page_config(page_title="Create Collection")

	navigate()

	if st.session_state.get("client_ready"):
		update_side_bar_labels()
		initialize_session_state()
		client = st.session_state.client
		submit_button, collection_name, selected_vectorizer, uploaded_file = create_collection_form()
		if submit_button:
			handle_form_submission(client, collection_name, selected_vectorizer, uploaded_file)
		display_collection_info(client)

	else:
		st.warning("Please Establish a connection to Weaviate in Cluster page!")

if __name__ == "__main__":
	main() 
