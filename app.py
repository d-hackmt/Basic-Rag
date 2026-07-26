"""Streamlit chat app for the HR Policy Assistant.

Run with:  streamlit run app.py
"""

import streamlit as st

from hr_assistant.pipeline import ask, build_hr_assistant

st.set_page_config(page_title="HR Policy Assistant", page_icon="🤖")
st.title("🤖 HR Policy Assistantttttttttt")
st.caption("Ask me anything about the company HR policy document.")


@st.cache_resource(show_spinner="Setting up the assistant (only happens once)...")
def get_agent():
    return build_hr_assistant()


agent = get_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Show the past conversation
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Get a new question from the user
question = st.chat_input("Ask a question about HR policy...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = ask(agent, question)
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
