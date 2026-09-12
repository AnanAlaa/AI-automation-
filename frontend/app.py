"""
Businessy - بيزنسي
====================
AI Business Analyst - Gradio Frontend

A friendly chat interface that lets a user:
  - upload a business dataset (.csv, .xlsx, .xls)
  - start new chats and revisit previous ones (history)
  - ask natural-language business questions
  - get answers backed by real Pandas calculations, explained by a
    locally running Ollama model (qwen2.5:7b)
  - switch between light and dark mode

While Businessy is working on an answer, the message box, send button,
new-chat button, chat history, and file upload are all locked so the
user can't send another message or change context mid-response.

Run from the project root with:
    python frontend/app.py
"""

import os
import sys
import uuid

import gradio as gr

# Make sure "backend" package is importable when this file is launched
# directly (python frontend/app.py) from anywhere.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.analyst import BusinessAnalyst
from backend.data_loader import load_file


APP_TITLE = "Businessy - بيزنسي"
NEW_CHAT_LABEL = "New Chat"

IDLE_PLACEHOLDER = "Ask Businessy about your data... اسأل بيزنسي عن بياناتك"
BUSY_PLACEHOLDER = "Businessy is thinking..."

WELCOME_PLACEHOLDER = (
    "### 👋 Welcome to Businessy - بيزنسي\n"
    "1. Upload a **.csv** or **.xlsx** file above.\n"
    "2. Ask a question in plain English or Arabic.\n"
    "3. Get an answer backed by real calculations, not guesses.\n\n"
    "_Try one of the example questions below to get started._"
)

EXAMPLE_QUESTIONS = [
    "What is our total revenue?",
    "Who are our top 5 customers by revenue?",
    "What are the top 3 products by revenue?",
    "Which month had the strongest and weakest sales?",
    "Compare 2024-01 to 2024-02.",
]


# ----------------------------------------------------------------------
# Session / chat-state helpers
#
# Each chat is stored as a dict inside the `sessions` gr.State:
#   {
#       "title": str,
#       "messages": list[{"role": ..., "content": ...}],
#       "analyst": BusinessAnalyst,
#       "df": pandas.DataFrame | None,
#       "filename": str | None,
#   }
# ----------------------------------------------------------------------

def _new_chat_entry():
    chat_id = str(uuid.uuid4())
    entry = {
        "title": NEW_CHAT_LABEL,
        "messages": [],
        "analyst": BusinessAnalyst(),
        "df": None,
        "filename": None,
    }
    return chat_id, entry


def _radio_update(sessions, current_id, interactive=True):
    choices = [(s["title"], cid) for cid, s in sessions.items()]
    return gr.update(choices=choices, value=current_id, interactive=interactive)


def _dataset_status_text(session):
    df = session.get("df")

    if df is None:
        return "_No dataset loaded yet. Upload a .csv or .xlsx file above to get started._"

    columns = ", ".join(str(c) for c in df.columns[:8])
    if len(df.columns) > 8:
        columns += ", ..."

    return (
        f"✅ **{session['filename']}** loaded — "
        f"{len(df):,} rows × {len(df.columns)} columns\n\n"
        f"**Columns:** {columns}"
    )


def _lock_controls(locked):
    """Returns updates for [msg_box, send_btn, new_chat_btn, file_upload]."""
    return (
        gr.update(
            interactive=not locked,
            placeholder=BUSY_PLACEHOLDER if locked else IDLE_PLACEHOLDER,
        ),
        gr.update(interactive=not locked),
        gr.update(interactive=not locked),
        gr.update(interactive=not locked),
    )


# ----------------------------------------------------------------------
# Event handlers
# ----------------------------------------------------------------------

def init_session():
    chat_id, entry = _new_chat_entry()
    sessions = {chat_id: entry}
    return (
        sessions,
        chat_id,
        [],
        _radio_update(sessions, chat_id),
        _dataset_status_text(entry),
        None,
    )


def create_new_chat(sessions):
    chat_id, entry = _new_chat_entry()
    # Newest chat first in the history list.
    new_sessions = {chat_id: entry, **sessions}
    return (
        new_sessions,
        chat_id,
        [],
        _radio_update(new_sessions, chat_id),
        _dataset_status_text(entry),
        None,
    )


def switch_chat(selected_id, sessions):
    if not selected_id or selected_id not in sessions:
        return gr.update(), gr.update(), gr.update(), gr.update()

    session = sessions[selected_id]
    return (
        selected_id,
        session["messages"],
        _dataset_status_text(session),
        None,
    )


def handle_file_upload(filepath, sessions, current_id):
    if filepath is None or current_id not in sessions:
        return sessions, gr.update()

    session = sessions[current_id]

    try:
        df = load_file(filepath)
    except Exception as e:
        return sessions, f"❌ **Could not load file:** {e}"

    session["analyst"].load_data(df)
    session["df"] = df
    session["filename"] = os.path.basename(filepath)
    sessions[current_id] = session

    return sessions, _dataset_status_text(session)


def respond(message, sessions, current_id, chat_history):
    message = (message or "").strip()

    # Nothing to do — leave everything as-is and keep controls unlocked.
    if not message or current_id not in sessions:
        unlocked = _lock_controls(False)
        yield (chat_history, sessions, gr.update()) + unlocked
        return

    session = sessions[current_id]
    chat_history = chat_history + [{"role": "user", "content": message}]

    if session["title"] == NEW_CHAT_LABEL:
        session["title"] = message[:40] + ("…" if len(message) > 40 else "")

    session["messages"] = chat_history
    sessions[current_id] = session

    # ---- Lock the UI and show a "thinking" bubble while Businessy works ----
    thinking = chat_history + [
        {"role": "assistant", "content": "🤔 *Businessy is analyzing your data...*"}
    ]
    locked = _lock_controls(True)
    yield (
        thinking,
        sessions,
        _radio_update(sessions, current_id, interactive=False),
    ) + locked

    if session.get("df") is None:
        answer = (
            "📎 I don't have any data yet — please upload a CSV or Excel "
            "file above and then ask me again."
        )
    else:
        try:
            answer = session["analyst"].ask(message)
        except ValueError as e:
            answer = (
                "⚠️ I couldn't build a reliable analysis plan for that "
                f"question.\n\n**Details:** {e}"
            )
        except Exception as e:
            answer = (
                "🔌 I couldn't reach the local Ollama model.\n\n"
                "Please make sure Ollama is running (`ollama serve`) and "
                "that the model is installed (`ollama pull qwen2.5:7b`).\n\n"
                f"**Details:** {e}"
            )

    final_history = chat_history + [{"role": "assistant", "content": answer}]
    session["messages"] = final_history
    sessions[current_id] = session

    # ---- Unlock the UI again ----
    unlocked = _lock_controls(False)
    yield (
        final_history,
        sessions,
        _radio_update(sessions, current_id, interactive=True),
    ) + unlocked


# ----------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------

CUSTOM_CSS = """
#app-header {text-align: center; padding: 8px 0 4px 0;}
#app-header h1 {margin-bottom: 0px; font-size: 1.7rem;}
#brand-ar {font-size: 1.05rem; opacity: 0.8; direction: rtl;}
#brand-sub {opacity: 0.7; font-size: 0.95rem; margin-top: 2px;}
#sidebar {
    border-radius: 16px;
    padding: 14px !important;
    background: var(--background-fill-secondary);
}
#main-panel {padding: 4px 10px;}
#dataset-status {
    padding: 10px 14px;
    border-radius: 10px;
    background: var(--background-fill-secondary);
    font-size: 0.9rem;
}
#send-btn {min-width: 96px;}
.gradio-container {max-width: 1200px !important; margin: auto;}
footer {display: none !important;}
"""

TOGGLE_THEME_JS = """
() => {
    document.body.classList.toggle('dark');
}
"""


# ----------------------------------------------------------------------
# Build the UI
# ----------------------------------------------------------------------

def build_app():
    with gr.Blocks(title=APP_TITLE) as demo:

        sessions_state = gr.State({})
        current_id_state = gr.State(None)

        gr.Markdown(
            "<div id='app-header'>"
            "<h1>🧠 Businessy</h1>"
            "<div id='brand-ar'>بيزنسي — مساعدك الذكي لتحليل الأعمال</div>"
            "<div id='brand-sub'>Your AI Business Analyst — upload your data and ask away</div>"
            "</div>"
        )

        with gr.Row():
            with gr.Column(scale=1, min_width=260, elem_id="sidebar"):
                new_chat_btn = gr.Button("➕ New Chat", variant="primary")
                history_radio = gr.Radio(
                    choices=[],
                    label="💬 Chat History",
                    interactive=True,
                )
                gr.Markdown("---")
                theme_btn = gr.Button("🌗 Light / Dark Mode")
                gr.Markdown(
                    "<small>💡 Tip: ask things like *'What is total "
                    "revenue and who are the top 5 customers?'* or "
                    "*'Compare 2024-01 to 2024-02'*.</small>"
                )

            with gr.Column(scale=4, elem_id="main-panel"):
                with gr.Row():
                    file_upload = gr.File(
                        label="📁 Upload business data (.csv, .xlsx, .xls)",
                        file_types=[".csv", ".xlsx", ".xls"],
                        scale=3,
                    )
                    dataset_status = gr.Markdown(
                        "_No dataset loaded yet._",
                        elem_id="dataset-status",
                    )

                chatbot = gr.Chatbot(
                    label="Businessy",
                    height=480,
                    avatar_images=(None, "🧠"),
                    buttons=["copy", "copy_all"],
                    placeholder=WELCOME_PLACEHOLDER,
                )

                with gr.Row():
                    msg_box = gr.Textbox(
                        placeholder=IDLE_PLACEHOLDER,
                        show_label=False,
                        scale=8,
                        autofocus=True,
                    )
                    send_btn = gr.Button(
                        "Send ➤", variant="primary", scale=1, elem_id="send-btn"
                    )

                gr.Examples(
                    examples=EXAMPLE_QUESTIONS,
                    inputs=msg_box,
                    label="✨ Try an example question",
                )

        # ---------------- Wiring ----------------

        theme_btn.click(fn=None, js=TOGGLE_THEME_JS)

        demo.load(
            init_session,
            outputs=[
                sessions_state,
                current_id_state,
                chatbot,
                history_radio,
                dataset_status,
                file_upload,
            ],
        )

        new_chat_btn.click(
            create_new_chat,
            inputs=[sessions_state],
            outputs=[
                sessions_state,
                current_id_state,
                chatbot,
                history_radio,
                dataset_status,
                file_upload,
            ],
        )

        history_radio.change(
            switch_chat,
            inputs=[history_radio, sessions_state],
            outputs=[current_id_state, chatbot, dataset_status, file_upload],
        )

        file_upload.upload(
            handle_file_upload,
            inputs=[file_upload, sessions_state, current_id_state],
            outputs=[sessions_state, dataset_status],
        )

        respond_outputs = [
            chatbot,
            sessions_state,
            history_radio,
            msg_box,
            send_btn,
            new_chat_btn,
            file_upload,
        ]

        send_btn.click(
            respond,
            inputs=[msg_box, sessions_state, current_id_state, chatbot],
            outputs=respond_outputs,
        )

        msg_box.submit(
            respond,
            inputs=[msg_box, sessions_state, current_id_state, chatbot],
            outputs=respond_outputs,
        )

    return demo


if __name__ == "__main__":
    app = build_app()
    app.queue()
    app.launch(
        theme=gr.themes.Soft(primary_hue="teal", secondary_hue="blue"),
        css=CUSTOM_CSS,
    )
