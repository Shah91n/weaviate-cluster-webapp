import streamlit as st
from core.search.hybrid import hybrid_search, hybrid_search_with_multiple_vectors
from core.search.vector import vector_search, vector_search_with_multiple_vectors, parse_vector_input
from core.search.keyword import keyword_search
from core.collection.overview import list_collections
from core.object.read import get_tenant_names
from pages.utils.page_config import set_custom_page_config
from pages.utils.navigation import navigate
from pages.utils.helper import update_side_bar_labels
from core.connection.weaviate_connection_manager import get_weaviate_client

# Initialize session state variables
def initialize_session_state():
	if 'selected_collection' not in st.session_state:
		st.session_state.selected_collection = None
	if 'search_query' not in st.session_state:
		st.session_state.search_query = ""
	if 'search_alpha' not in st.session_state:
		st.session_state.search_alpha = 0.5
	if 'search_limit' not in st.session_state:
		st.session_state.search_limit = 3
	if 'search_type' not in st.session_state:
		st.session_state.search_type = "Hybrid"
	if 'selected_target_vector' not in st.session_state:
		st.session_state.selected_target_vector = None
	if 'search_selected_tenant' not in st.session_state:
		st.session_state.search_selected_tenant = None

# Display the search
def display_search_interface():
	st.subheader("Search in Collection")

	# Collections list
	collections = list_collections() or []
	if not collections:
		st.warning("No collections available. Create a collection first.")
		st.session_state.selected_collection = None
		return

	# Determine default selection index from session
	default_index = 0
	if st.session_state.get('selected_collection') in collections:
		try:
			default_index = collections.index(st.session_state.selected_collection)
		except Exception:
			default_index = 0

	selected_collection = st.selectbox(
		"Select Collection",
		options=collections,
		index=default_index,
		help="Choose a collection to search in",
	)

	# Tenant selection (only for MT collections)
	tenant_names = get_tenant_names(selected_collection) or []
	selected_tenant = None
	if tenant_names:
		tenant_names = sorted(tenant_names)
		selected_tenant_index = 0
		if st.session_state.get('search_selected_tenant') in tenant_names:
			try:
				selected_tenant_index = tenant_names.index(st.session_state.search_selected_tenant)
			except Exception:
				selected_tenant_index = 0
		selected_tenant = st.selectbox(
			"Select Tenant",
			tenant_names,
			index=selected_tenant_index,
			help="Choose a tenant to scope your search",
			key="search_tenant_select",
		)
	else:
		st.session_state.search_selected_tenant = None

	# Get the collection and check named vectors
	client = get_weaviate_client()
	if not selected_collection:
		st.error("No collection selected")
		return
	collection = client.collections.use(selected_collection)
	collection_config = collection.config.get()
	target_vector = None
	if getattr(collection_config, 'vector_config', None):
		vector_names = list(collection_config.vector_config.keys())
		target_vector = st.selectbox(
			"Select Target Vector",
			options=vector_names,
			index=0,
			help="Choose which named vector to search",
		)
		st.session_state.selected_target_vector = target_vector
	else:
		st.session_state.selected_target_vector = None

	# Search type
	search_type = st.radio(
		"Search Type",
		options=["Hybrid", "Keyword", "Vector"],
		horizontal=True,
		help="Choose between hybrid (vector + keyword) or keyword-only search",
	)

	query = st.text_input(
		"Search Query/Vector",
		value=st.session_state.search_query,
		help="Enter your search query/vector (for vector search, use a comma-separated list of floats like: 0.1,0.2,0.3)",
	)

	col1, col2 = st.columns(2)
	with col1:
		alpha_str = None
		if search_type == "Hybrid":
			alpha_str = st.text_input(
				"Alpha",
				value=str(st.session_state.search_alpha),
				help="Balance between vector and keyword search (0.0 to 1.0)",
				key="search_alpha_input",
			)
	with col2:
		limit_str = st.text_input(
			"Limit",
			value=str(st.session_state.search_limit),
			help="Maximum number of results to return",
			key="search_limit_input",
		)

	# Search button
	search_button = st.button("Search")
	if search_button:
		if tenant_names and not selected_tenant:
			st.error("Please select a tenant for this collection")
			return

		# Parse and persist inputs from text fields
		try:
			limit_val = int(st.session_state.get('search_limit_input', limit_str or str(st.session_state.search_limit)))
		except Exception:
			st.error("Limit must be an integer between 1 and 100")
			return
		if not (1 <= limit_val <= 100):
			st.error("Limit must be between 1 and 100")
			return

		# Parse alpha if hybrid
		if search_type == "Hybrid":
			try:
				raw_alpha = st.session_state.get('search_alpha_input', alpha_str or str(st.session_state.search_alpha))
				alpha_val = float(raw_alpha)
			except Exception:
				st.error("Alpha must be a number between 0.0 and 1.0")
				return
			if not (0.0 <= alpha_val <= 1.0):
				st.error("Alpha must be between 0.0 and 1.0")
				return
			st.session_state.search_alpha = alpha_val
			alpha = alpha_val
		else:
			alpha = None

		# Persist session state
		st.session_state.selected_collection = selected_collection
		st.session_state.selected_target_vector = target_vector
		st.session_state.search_query = query
		st.session_state.search_type = search_type
		st.session_state.search_selected_tenant = selected_tenant
		st.session_state.search_limit = limit_val

		# Perform search
		try:
			if search_type == "Hybrid":
				if st.session_state.selected_target_vector:
					success, message, df, time_taken = hybrid_search_with_multiple_vectors(
						selected_collection,
						target_vector,
						query,
						alpha,
						limit_val,
						tenant_name=selected_tenant,
					)
				else:
					success, message, df, time_taken = hybrid_search(
						selected_collection,
						query,
						alpha,
						limit_val,
						tenant_name=selected_tenant,
					)
			elif search_type == "Vector":
				vector_list = parse_vector_input(query)
				if st.session_state.selected_target_vector:
					success, message, df, time_taken = vector_search_with_multiple_vectors(
						selected_collection,
						target_vector,
						vector_list,
						limit_val,
						tenant_name=selected_tenant,
					)
				else:
					success, message, df, time_taken = vector_search(
						selected_collection,
						vector_list,
						limit_val,
						tenant_name=selected_tenant,
					)
			else:
				success, message, df, time_taken = keyword_search(
					selected_collection,
					query,
					limit_val,
					tenant_name=selected_tenant,
				)
		except ValueError as e:
			st.error(f"Invalid vector format: {e}")
			return

		# Display results
		display_results(success, message, df, time_taken)

# Function to display results
def display_results(success: bool, message: str, df, time_taken: float):
	if success:
		# Create a container for the success message and timing
		col1, col2 = st.columns([3, 1])
		with col1:
			st.success(message)
		with col2:
			st.info(f"Query Time Taken: {time_taken/1000:.3f}s ({time_taken:.2f}ms - {time_taken/1000/60:.3f}m)")

		if not df.empty:
			st.dataframe(df, width="stretch")
	else:
		st.error(message)

def main():
	set_custom_page_config(page_title="Search")
	navigate()
	update_side_bar_labels()

	if st.session_state.get("client_ready"):
		initialize_session_state()

		st.markdown("""
		            Search across your collections using either hybrid or keyword search.
		            """)

		# Display search types in columns
		col1, col2 = st.columns(2)
		with col1:
			st.markdown("""
			            **Hybrid Search**:
			            - Combines vector and keyword search capabilities
			            - Adjust alpha to balance between vector and keyword search
			            - Best for semantic similarity and keyword matching
			            """)
		with col2:
			st.markdown("""
			            **Keyword Search (BM25)**:
			            - Pure keyword-based search
			            - Fast and efficient for exact matches
			            - No vector similarity involved
			            """)

		# Add tokenization information banner
		st.info("""
		        **Tokenization in Weaviate Search**
		        
		        Tokenization plays a crucial role in search functionality. Weaviate offers various tokenization options to configure how keyword searches and filters are performed for each property.
		        
		        To learn more about tokenization options and how they affect your search results, visit the [Weaviate Tokenization Documentation](https://weaviate.io/developers/academy/py/tokenization/options).
		        """)

		# Display search interface
		display_search_interface()
	else:
		st.warning("Please Establish a connection to Weaviate in Cluster page!")

if __name__ == "__main__":
	main()
