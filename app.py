import gradio as gr
from agent import ResearchAgent
from tools import generate_report


# ----------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------

def run_with_log(action):
    """Runs an agent action, catching errors and collecting status messages.
    `action` is a function that takes a status-reporting function and
    returns the answer text."""
    log = []
    try:
        answer = action(log.append)
    except Exception as e:
        answer = f"❌ Error: {e}"
    return answer, format_log(log)


def add_turn(history, user_msg, bot_msg):
    """Adds one question+answer pair to the chat history."""
    return (history or []) + [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": bot_msg},
    ]


def format_sources(sources):
    if not sources:
        return "_No sources collected yet._"
    text = ""
    for i, s in enumerate(sources, start=1):
        text += f"**{i}. {s['title']}**\n{s.get('url', '')}\n\n{s.get('summary', '')}\n\n---\n\n"
    return text


def format_log(messages):
    return "\n".join(messages) if messages else "Ready."


# ----------------------------------------------------------------------
# Event handlers - one per button/action
# ----------------------------------------------------------------------

def start_research(topic, agent):
    topic = (topic or "").strip()
    if not topic:
        return agent, "⚠️ Please enter a topic.", "_No sources collected yet._", []

    agent = ResearchAgent()
    answer, log_text = run_with_log(lambda cb: agent.research_topic(topic, status_callback=cb))
    chat_history = add_turn([], f"Research topic: {topic}", answer)
    return agent, log_text, format_sources(agent.sources), chat_history


def send_followup(message, agent, chat_history):
    message = (message or "").strip()

    if agent is None:
        return add_turn(chat_history, message, "⚠️ Start a research session first."), agent, "Ready.", "_No sources collected yet._", ""

    if not message:
        return chat_history, agent, "Ready.", format_sources(agent.sources), ""

    answer, log_text = run_with_log(lambda cb: agent.chat(message, status_callback=cb))
    return add_turn(chat_history, message, answer), agent, log_text, format_sources(agent.sources), ""


def make_report(agent):
    if agent is None or not agent.sources:
        return "⚠️ No sources collected yet - research a topic first."
    answer, _ = run_with_log(lambda cb: generate_report(agent.sources))
    return answer


def reset_session():
    return None, "", "Ready.", "_No sources collected yet._", [], "", ""


# ----------------------------------------------------------------------
# UI layout
# ----------------------------------------------------------------------
with gr.Blocks(title="AI Research Assistant") as demo:
    agent_state = gr.State(value=None)

    gr.Markdown("# 🔎 AI Research Assistant")
    gr.Markdown("Enter a topic to research, then ask follow-up questions or generate a final report.")

    with gr.Row():
        topic_input = gr.Textbox(label="Research Topic", placeholder="e.g. AI in Healthcare", scale=4)
        start_btn = gr.Button("Start Research", variant="primary", scale=1)

    activity_log = gr.Textbox(label="Activity Log", value="Ready.", interactive=False, lines=3)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Sources & Summaries")
            sources_display = gr.Markdown("_No sources collected yet._")
        with gr.Column():
            gr.Markdown("### Follow-up Questions")
            chatbot = gr.Chatbot(label="Conversation", height=400)
            with gr.Row():
                followup_input = gr.Textbox(placeholder="Ask a follow-up question...", scale=4)
                send_btn = gr.Button("Send", scale=1)

    with gr.Row():
        report_btn = gr.Button("📄 Generate Final Report")
        reset_btn = gr.Button("🔄 New Session")

    report_display = gr.Markdown()

    # --- Connect buttons to functions ---
    research_outputs = [agent_state, activity_log, sources_display, chatbot]
    start_btn.click(start_research, [topic_input, agent_state], research_outputs)
    topic_input.submit(start_research, [topic_input, agent_state], research_outputs)

    followup_outputs = [chatbot, agent_state, activity_log, sources_display, followup_input]
    send_btn.click(send_followup, [followup_input, agent_state, chatbot], followup_outputs)
    followup_input.submit(send_followup, [followup_input, agent_state, chatbot], followup_outputs)

    report_btn.click(make_report, [agent_state], [report_display])

    reset_outputs = [agent_state, topic_input, activity_log, sources_display, chatbot, followup_input, report_display]
    reset_btn.click(reset_session, [], reset_outputs)


if __name__ == "__main__":
    demo.launch()
