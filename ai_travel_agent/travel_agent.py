import streamlit as st
from openai import OpenAI
from mem0 import Memory

# Set up the Streamlit App
st.title("AI Travel Agent with Memory 🧳 (Local Ollama)")
st.caption("Chat with a travel assistant who remembers your preferences and past interactions — fully local, no API key needed.")

# Point the OpenAI SDK at Ollama's OpenAI-compatible endpoint.
# No real key is needed; Ollama ignores it, but the SDK requires a non-empty string.
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

CHAT_MODEL = "llama3.2:latest"
EMBED_MODEL = "nomic-embed-text:latest"  # run: ollama pull nomic-embed-text

# Initialize Mem0 with Qdrant + local Ollama for both the LLM and the embedder
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 768,  # nomic-embed-text output dimension
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": CHAT_MODEL,
            "temperature": 0,
            "max_tokens": 2000,
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": EMBED_MODEL,
            "ollama_base_url": "http://localhost:11434",
        },
    },
}
memory = Memory.from_config(config)

# Sidebar for username and memory view
st.sidebar.title("Enter your username:")
previous_user_id = st.session_state.get("previous_user_id", None)
user_id = st.sidebar.text_input("Enter your Username")

if user_id != previous_user_id:
    st.session_state.messages = []
    st.session_state.previous_user_id = user_id

# Sidebar option to show memory
st.sidebar.title("Memory Info")
if st.sidebar.button("View My Memory"):
    if user_id:
        memories = memory.get_all(filters={"user_id": user_id})
        if memories and "results" in memories and memories["results"]:
            st.sidebar.write(f"Memory history for **{user_id}**:")
            for mem in memories["results"]:
                if "memory" in mem:
                    st.sidebar.write(f"- {mem['memory']}")
        else:
            st.sidebar.info("No learning history found for this user ID.")
    else:
        st.sidebar.error("Please enter a username to view memory info.")

# Initialize the chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display the chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
prompt = st.chat_input("Where would you like to travel?")

if prompt and user_id:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Retrieve relevant memories
    relevant_memories = memory.search(query=prompt, filters={"user_id": user_id})
    context = "Relevant past information:\n"
    if relevant_memories and "results" in relevant_memories:
        for mem in relevant_memories["results"]:
            if "memory" in mem:
                context += f"- {mem['memory']}\n"

    # Prepare the full prompt
    full_prompt = f"{context}\nHuman: {prompt}\nAI:"

    # Generate response from local Ollama model
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a travel assistant with access to past conversations."},
                    {"role": "user", "content": full_prompt},
                ],
            )
            if not response.choices or response.choices[0].message.content is None:
                st.error("Received empty or null response from the local model.")
                st.stop()
            answer = response.choices[0].message.content
            st.markdown(answer)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": answer})

    # Store the user query and AI response in memory
    memory.add(prompt, user_id=user_id, metadata={"role": "user"})
    memory.add(answer, user_id=user_id, metadata={"role": "assistant"})
elif not user_id:
    st.info("Please enter a username to start the chat.")