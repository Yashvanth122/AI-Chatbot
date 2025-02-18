import streamlit as st
from typing import Generator
from groq import Groq
import sqlite3
import json
from datetime import datetime

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id TEXT,
            chat_name TEXT,
            messages TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

# Save chat history to database
def save_chat_to_db(user_id, chat_name, messages):
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    messages_json = json.dumps(messages)
    cursor.execute("""
        INSERT INTO chats (timestamp, user_id, chat_name, messages)
        VALUES (?, ?, ?, ?)
    """, (timestamp, user_id, chat_name, messages_json))
    conn.commit()

# Load chat history from database
def load_chat_history(user_id):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT chat_id, timestamp, chat_name, messages FROM chats
        WHERE user_id = ?
        ORDER BY timestamp DESC
    """, (user_id,))
    return cursor.fetchall()

# Initialize database
conn = init_db()

# Set page config
st.set_page_config(page_icon="💬", layout="wide", page_title="AI Chatbot")

# Custom CSS for better UI
st.markdown("""
    <style>
    .stTextInput>div>div>input {
        border-radius: 20px;
        padding: 10px;
    }
    .stButton>button {
        border-radius: 20px;
        padding: 10px 20px;
        background-color: #4CAF50;
        color: white;
        border: none;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .stSelectbox>div>div>div {
        border-radius: 20px;
        padding: 10px;
    }
    .stSlider>div>div>div {
        border-radius: 20px;
    }
    .stChatMessage {
        border-radius: 20px;
        padding: 10px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Function to display emoji as a Notion-style page icon
def icon(emoji: str):
    st.write(
        f'<span style="font-size: 78px; line-height: 1">{emoji}</span>',
        unsafe_allow_html=True,
    )

# Display the icon and title
icon("🤖")
st.title("Chat Interface")

# Initialize Groq client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# Initialize chat history and selected model
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_model" not in st.session_state:
    st.session_state.selected_model = None

# Define model details
models = {
    "gemma2-9b-it": {"name": "Gemma2-9b-it", "tokens": 8192, "developer": "Google"},
    "llama-3.3-70b-versatile": {"name": "LLaMA3.3-70b-versatile", "tokens": 128000, "developer": "Meta"},
    "llama-3.1-8b-instant": {"name": "LLaMA3.1-8b-instant", "tokens": 128000, "developer": "Meta"},
    "llama3-70b-8192": {"name": "LLaMA3-70b-8192", "tokens": 8192, "developer": "Meta"},
    "llama3-8b-8192": {"name": "LLaMA3-8b-8192", "tokens": 8192, "developer": "Meta"},
    "mixtral-8x7b-32768": {"name": "Mixtral-8x7b-Instruct-v0.1", "tokens": 32768, "developer": "Mistral"},
}

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    model_option = st.selectbox(
        "Choose a model:",
        options=list(models.keys()),
        format_func=lambda x: models[x]["name"],
        index=4  # Default to mixtral
    )

    max_tokens_range = models[model_option]["tokens"]
    max_tokens = st.slider(
        "Max Tokens:",
        min_value=512,
        max_value=max_tokens_range,
        value=min(32768, max_tokens_range),
        step=512,
        help=f"Adjust the maximum number of tokens (words) for the model's response. Max for selected model: {max_tokens_range}"
    )

# Sidebar for previous chats
with st.sidebar:
    st.header("Previous Chats")
    user_id = "user_123"  # Replace with actual user ID (e.g., from authentication)
    chat_history = load_chat_history(user_id)
    for chat in chat_history:
        chat_id, timestamp, chat_name, messages_json = chat
        if st.button(f"{chat_name} - {timestamp}"):
            st.session_state.messages = json.loads(messages_json)
            st.rerun()

# Detect model change and clear chat history if model has changed
if st.session_state.selected_model != model_option:
    st.session_state.messages = []
    st.session_state.selected_model = model_option

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    avatar = '🤖' if message["role"] == "assistant" else '👨‍💻'
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Function to generate chat responses
def generate_chat_responses(chat_completion) -> Generator[str, None, None]:
    for chunk in chat_completion:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# Chat input
if prompt := st.chat_input("Enter your prompt here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar='👨‍💻'):
        st.markdown(prompt)

    # Fetch response from Groq API
    try:
        chat_completion = client.chat.completions.create(
            model=model_option,
            messages=[
                {
                    "role": m["role"],
                    "content": m["content"]
                }
                for m in st.session_state.messages
            ],
            max_tokens=max_tokens,
            stream=True
        )

        # Use the generator function with st.write_stream
        with st.chat_message("assistant", avatar="🤖"):
            chat_responses_generator = generate_chat_responses(chat_completion)
            full_response = st.write_stream(chat_responses_generator)
    except Exception as e:
        st.error(e, icon="🚨")

    # Append the full response to session_state.messages
    if isinstance(full_response, str):
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response})
    else:
        combined_response = "\n".join(str(item) for item in full_response)
        st.session_state.messages.append(
            {"role": "assistant", "content": combined_response})

    # Save chat history to database
    chat_name = prompt[:50] if prompt else "Untitled Chat"  # Use the first 50 chars of the prompt as the chat name
    save_chat_to_db(user_id, chat_name, st.session_state.messages)