import streamlit as st
from pages.utils.page_config import set_custom_page_config
from pages.utils.navigation import navigate
from pages.utils.helper import update_side_bar_labels
from core.collection.overview import list_collections
from core.agents.query_agent import run_query_agent, capture_display, extract_known_fields, sanitize_display


def render_response(response):
    display_text = capture_display(response)
    structured = extract_known_fields(response)

    st.markdown("### 🧠 Agent Answer")
    answer = structured.get("answer")
    if answer:
        st.success(answer)

    sanitized = sanitize_display(display_text)
    with st.expander("Response", expanded=False):
        st.code(sanitized, language="text")

    if structured:
        st.markdown("##### 📦 Additional Sections")
        for key, val in structured.items():
            if key == "answer":
                continue
            with st.expander(key.title(), expanded=False):
                st.write(val)

# Session init
def initialize_session_state():
    if 'agent_collections' not in st.session_state:
        st.session_state.agent_collections = []
    if 'agent_question' not in st.session_state:
        st.session_state.agent_question = ''
    if 'agent_system_prompt' not in st.session_state:
        st.session_state.agent_system_prompt = ''
    if 'agent_timeout' not in st.session_state:
        st.session_state.agent_timeout = 60
    if 'agent_host' not in st.session_state:
        st.session_state.agent_host = ''


def display_agent_ui():
    # Fetch collections fresh each render
    collections = list_collections()

    if isinstance(collections, dict):  # error scenario
        st.error(collections.get('error', 'Error fetching collections'))
        return

    if not collections:
        st.warning('No collections available. Create a collection first.')
        return

    st.markdown('##### Select Collections for the Agent')
    selected = st.multiselect(
        'Collections',
        options=collections,
        default=collections[:1],
        help='Choose one or more collections for the agent to query'
    )

    st.markdown('##### Ask the Agent')
    question = st.text_area(
        'Question',
        value=st.session_state.agent_question,
        placeholder='Ask a natural language question about your data...',
        help='Must not be empty when executing the agent'
    )

    with st.expander('Advanced Options', expanded=False):
        system_prompt = st.text_area(
            'System Prompt (optional)',
            value=st.session_state.agent_system_prompt,
            placeholder='Custom system instructions for the agent'
        )
        host = st.text_input(
            'Agents Host Override (optional)',
            value=st.session_state.agent_host,
            placeholder='e.g. https://agents.service.internal'
        )
        timeout = st.number_input(
            'Timeout (seconds)',
            min_value=5,
            max_value=300,
            value=st.session_state.agent_timeout,
            step=5,
            help='Request timeout for the agent'
        )

    run_btn = st.button('Run Agent Query', type='primary', use_container_width=True)

    if run_btn:
        # Validation
        if not selected:
            st.error('Please select at least one collection.')
            return
        if not question.strip():
            st.error('Question must not be empty.')
            return

        # Persist state
        st.session_state.agent_collections = selected
        st.session_state.agent_question = question
        st.session_state.agent_system_prompt = system_prompt
        st.session_state.agent_host = host
        st.session_state.agent_timeout = timeout

        try:
            with st.spinner('Querying agent...'):
                response = run_query_agent(
                    collections=selected,
                    question=question.strip(),
                    system_prompt=system_prompt.strip() if system_prompt.strip() else None,
                    agents_host=host.strip() if host.strip() else None,
                    timeout=timeout,
                )
            render_response(response)
        except RuntimeError as re:
            st.error(str(re))
        except Exception as e:
            st.error(f'Agent query failed: {e}')


def main():
    set_custom_page_config(page_title='Agent')
    navigate()
    update_side_bar_labels()

    if not st.session_state.get('client_ready'):
        st.warning('Please Establish a connection to Weaviate in Cluster page!')
        return

    initialize_session_state()

    st.markdown('''
        Interact with an AI Agent that leverages your Data.
        1. Select one or more collections.
        2. Provide a natural language question.
        3. (Optional) Add a system prompt to guide the agent.
        4. Run the query and inspect the answer, structured sections, and raw display output.
    ''')

    display_agent_ui()


if __name__ == '__main__':
    main()
