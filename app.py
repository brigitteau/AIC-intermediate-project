import streamlit as st

st.set_page_config(page_title="Syllabus Q&A", page_icon="📚")
st.title("Syllabus Q&A")

# Chat history lives in session_state because Streamlit reruns this
# whole script on every interaction.
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar: syllabus upload
with st.sidebar:
    uploaded = st.file_uploader("Upload a syllabus", type=["pdf", "docx", "txt"])

if uploaded is None:
    st.info("Upload a syllabus in the sidebar to get started.")
    st.stop()

st.success(f"Loaded: {uploaded.name}")

# Show past messages
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Chat box
if question := st.chat_input("Ask about the syllabus"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Placeholder: replace this with retrieval + the Gemini call later
    answer = f"You asked: {question}"

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)