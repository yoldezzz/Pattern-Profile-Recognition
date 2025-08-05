import streamlit as st
from langchain.memory.buffer import ConversationBufferMemory
from langchain_community.utilities import SQLDatabase
from src.agent.agent_core import create_sql_agent_executor, run_sql_agent_executor
from src.dashboard.chart_generator import generate_intelligent_dashboard
from src.utils.voice_utils import voice_to_text, text_to_voice
from src.database.create_db import create_test_db
import os
import json

st.set_page_config(page_title="OptiFlow Pattern Profile", layout="wide")

# Initialize database
if "db" not in st.session_state:
    create_test_db()
    st.session_state.db = SQLDatabase.from_uri("sqlite:///src/database/test_db.db")
    st.success("SQLite database connected!")

# Initialize state
if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="input",
        output_key="output",
        return_messages=True
    )
if "agent_executor" not in st.session_state:
    st.session_state.agent_executor = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Create agent
if st.session_state.db and st.session_state.agent_executor is None:
    st.session_state.agent_executor = create_sql_agent_executor(
        st.session_state.db,
        st.session_state.memory
    )

# Main UI
st.title("🤖 OptiFlow Pattern Profile Assistant")
tabs = st.tabs(["Chat", "Dashboard"])

# Chat Tab
with tabs[0]:
    st.header("Chat Assistant (Text or Voice)")
    audio_file = st.file_uploader("Upload a .wav file for voice input", type=["wav"])
    user_prompt = st.chat_input("Enter your query (e.g., 'Show Alice's pattern'):")

    if audio_file:
        with open("temp_audio.wav", "wb") as f:
            f.write(audio_file.read())
        user_prompt = voice_to_text("temp_audio.wav")
        st.write(f"Transcribed voice input: {user_prompt}")
        os.remove("temp_audio.wav")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)

        with st.spinner("Processing..."):
            history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages[:-1]])
            assistant_reply = run_sql_agent_executor(
                st.session_state.agent_executor,
                user_prompt,
                history
            )

            # Generate voice report
            voice_file = text_to_voice(assistant_reply, "output.wav")
            st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
            with st.chat_message("assistant"):
                st.write(assistant_reply)
                st.audio(voice_file, format="audio/wav")
                with open(voice_file, "rb") as f:
                    st.download_button("Download Voice Report", f, file_name="report.wav")

        st.session_state.memory.save_context(
            {"input": user_prompt},
            {"output": assistant_reply}
        )

# Dashboard Tab
with tabs[1]:
    st.header("Pattern Profile Dashboard")
    dashboard_prompt = st.text_input("Enter dashboard query (e.g., 'Show Alice's pattern'):")
    if dashboard_prompt:
        with st.spinner("Generating dashboard..."):
            result = generate_intelligent_dashboard(st.session_state.db, dashboard_prompt)
            if "error" in result:
                st.error(result["error"])
            else:
                st.components.v1.html(
                    f"""
                    <div style="width:100%;height:400px;">
                        {result['avatars_html']}
                        <canvas id="myChart"></canvas>
                    </div>
                    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                    <script>
                        const ctx = document.getElementById('myChart').getContext('2d');
                        new Chart(ctx, {json.dumps(result['chart_config'])});
                    </script>
                    """,
                    height=450
                )