# AI Research Assistant

An AI-powered research assistant built with Python, a locally running Ollama model, and Gradio. Give it a topic and it generates research questions, searches the web, scrapes and summarizes real sources, answers follow-up questions with full conversation context (grounded in the research via RAG), and produces a structured final report with real, verifiable sources.

**Team members:** Zeina Hossamuldeen and Hla Muhammed

This project fulfills **Team 1: AI Research Assistant**

## 1. Problem Statement

Manually researching a topic means repeatedly searching, opening pages, reading them, and synthesizing findings across sources by hand. This project automates that loop: the user provides a topic, and the application gathers, reads, and condenses real web sources, then lets the user ask grounded follow-up questions and get a structured, source-backed report — without the model inventing facts or citations.

## 2. Application Features

- Generates research questions and search queries from a single topic
- Searches the web and returns real, clickable sources
- Scrapes and cleans webpage content
- Summarizes each source using the LLM
- Compares two sources for agreement/disagreement
- Retrieves relevant raw source text for specific follow-up questions (RAG)
- Produces a structured report (Introduction, Key Findings, Conclusion, Sources) built only from real gathered sources
- Follow-up questions preserve full conversation and research context
- Gradio interface with an activity/status log, a sources panel, a chat, and a report view
- Handles tool, network, and model failures without crashing — errors are shown, not hidden

## 3. Technologies Used

| Purpose | Technology |
|---|---|
| LLM runtime | [Ollama](https://ollama.com) |
| Chat / tool-calling model | `qwen2.5:7b` |
| Embedding model (for RAG) | `nomic-embed-text` |
| Web search | `ddgs` (DuckDuckGo search) |
| Scraping | `requests` + `BeautifulSoup` (`lxml` parser) |
| Vector store (RAG) | `chromadb` (in-memory, per session) |
| Interface | `gradio` |
| Language | Python 3 |

## 4. Ollama Model & How to Run It

This project uses `qwen2.5:7b` as the main chat/tool-calling model.`qwen2.5` was consistently reliable for this project's tool-calling needs.

```bash
# 1. Install Ollama: https://ollama.com/download
# 2. Pull the chat model and the embedding model (used for RAG)
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
# 3. Make sure the Ollama server is running (it usually starts automatically)
ollama serve
```

To use a different model, change `OLLAMA_MODEL` at the top of `tools.py`. Any model with tool-calling support in Ollama (e.g. `llama3.1`) should work, though reliability may vary.

## 5. Installation / Setup Instructions

```bash
git clone <your-repo-url>
cd <your-repo>
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
python app.py
```

Gradio will print a local URL (usually `http://127.0.0.1:7860`) — open it in your browser.

## 6. Application Architecture

This project implements that architecture in two parts, and it's worth explaining the reasoning honestly:

**Part A — Starting research on a topic** (`ResearchAgent.research_topic()` in `agent.py`) runs a fixed Python sequence: `generate_research_questions → search_web → scrape_page → summarize_source`, for up to 3 sources. This sequence never changes based on the topic, so during development it was made deterministic in Python rather than left to the model to decide step-by-step — early testing showed models unreliably chaining 5+ tool calls in a row on their own (inventing tool names, asking unnecessary clarifying questions, or answering from search snippets alone instead of actually reading pages).

**Part B — Everything after that** (follow-up questions, comparisons, retrieval, the report — `ResearchAgent.chat()`) uses the full architecture above: the conversation and the list of available tools are sent to Ollama, Ollama decides whether and which tool to call, Python executes it, the result is returned as a `"role": "tool"` message, and this repeats until Ollama gives a final answer. This is where genuine LLM tool selection happens, and it's demonstrated in the example workflows below.

```
Follow-up flow:
User message
  │
  ▼
ResearchAgent.chat()  (agent.py)
  │  sends conversation + tool schemas
  ▼
Ollama (qwen2.5:7b)
  │  decides: answer directly, OR call a tool
  ▼
Tool Selection → Python Tool (tools.py) or RAG retrieval (rag.py)
  │  search_web / scrape_page / summarize_source /
  │  compare_sources / retrieve_context / generate_report
  ▼
Tool Result → appended back into conversation as a "tool" role message
  ▼
Ollama (qwen2.5:7b) → produces final response
  ▼
Gradio Interface → shown to user (answer, sources panel, activity log)
```

Conversation history is kept in `ResearchAgent.messages` for the whole session, and collected sources are kept in `ResearchAgent.sources`, so both follow-up questions and the final report are grounded in everything gathered so far — not just the latest message.

**Code organization:**
| File | Responsibility |
|---|---|
| `tools.py` | The 6 core research functions, plus tool schemas/lookup for the agent |
| `rag.py` | Chunking, embeddings, and the ChromaDB vector store (RAG) |
| `agent.py` | The `ResearchAgent`: conversation state, the deterministic research pass, and the LLM tool-calling loop |
| `app.py` | Gradio UI and the event handlers that connect buttons to the agent |

## 7. Tools

| Tool | What it does | Input | Output |
|---|---|---|---|
| `generate_research_questions` | Generates 5 research questions + 5 search queries for a topic | `topic: str` | Formatted text block |
| `search_web` | Searches the web via DuckDuckGo | `query: str`, `max_results: int` | List of `{title, url, snippet}` |
| `scrape_page` | Downloads a page and extracts clean text | `url: str` | Cleaned page text (truncated to 20,000 chars) |
| `summarize_source` | Summarizes a source's content with the LLM | `content: str` | Summary text |
| `compare_sources` | Compares two summaries for agreement/disagreement | `source1: str`, `source2: str` | Comparison text |
| `retrieve_context` | RAG: retrieves the most relevant text chunks from all collected sources for a question | `query: str` | List of `{text, title, url}` chunks |
| `generate_report` | Builds the final structured report from all collected sources | *(uses the session's accumulated sources, not model-supplied args)* | Markdown report with a real Sources section |

That's 7 tools total, exceeding the brief's minimum of 5. Every tool is wrapped in error handling (see Section 11) and is exposed to Ollama via `TOOL_SCHEMAS` in `tools.py`, so the LLM — not a manually-triggered button — decides when to call `compare_sources`, `retrieve_context`, and `generate_report`.

## 8. Example Multi-Tool Conversations

**Example 1 — Starting research (Python-orchestrated multi-tool sequence)**

> **User:** *(enters topic)* "AI in Healthcare" → clicks Start Research
>
> **What runs:** `generate_research_questions("AI in Healthcare")` → `search_web(query)` for each generated query → for each result: `scrape_page(url)` → `summarize_source(content)`, repeated across sources until 3 are collected.
>
> **Result:** Sources panel fills with real titles, URLs, and summaries; a short grounded overview is shown in the chat.

**Example 2 — LLM-selected multi-tool follow-up (genuine tool selection)**

> **User:** "What did the sources say specifically about diagnostic accuracy, and how do the first two sources compare?"
>
> **What runs (the LLM decides this, not hardcoded Python):** `retrieve_context("diagnostic accuracy")` to pull the most relevant raw chunks from the RAG index, then `compare_sources(summary_1, summary_2)` using the two summaries already in `agent.sources` — no new search needed, because conversation and source context were preserved.
>
> **Result:** An answer grounded in retrieved source text, followed by a comparison of agreements/disagreements between the two sources.

**Example 3 — Report generation**

> **User:** "Generate the final report."
>
> **What runs:** `generate_report(agent.sources)` — called directly on the real accumulated sources, not through a second LLM pass, so it can't invent sources.

*(Examples 1 and 3 are architecturally guaranteed; Example 2's exact tool choice depends on what the model decides at runtime given the question.)*

## 9. Advanced Topic — Retrieval-Augmented Generation (RAG)

**What it is:** RAG grounds the model's answers in the actual text of collected sources, rather than relying only on the short summaries already sitting in conversation history (which can drop detail) or on the model's own general knowledge (which can be wrong or outdated).

**How it's implemented (`rag.py`):**

1. **Chunking** — every scraped source's full text is split into overlapping ~200-word chunks (`chunk_text()`), so no single chunk is too large to embed meaningfully, and overlap prevents cutting an idea in half at a chunk boundary.
2. **Embeddings** — each chunk is embedded using a local Ollama embedding model (`nomic-embed-text`, via `ollama.embeddings()`), so no external API is required.
3. **Vector store** — `ResearchVectorStore` wraps an in-memory **ChromaDB** collection, created fresh per research session. Chunks are stored with their embedding plus metadata (source title and URL).
4. **Similarity retrieval** — when the agent decides a follow-up question needs more detail than the summaries provide, it calls the `retrieve_context` tool, which embeds the question and asks ChromaDB for the most similar chunks.
5. **Retrieved context sent to Ollama** — the retrieved chunks are fed back into the conversation as a tool result, and Ollama generates its final answer using that retrieved context instead of guessing.

**Integration point:** every time `summarize_source` runs successfully (both during the initial research pass and during any later follow-up), the agent also indexes that source's full content into the session's vector store (see `agent.py`) — so retrieval always has the same underlying text the summaries were built from.

**Goal achieved:** answers to specific factual follow-ups are based on the actual research the app collected, not just the model's general knowledge or a possibly-lossy summary.

## 10. Reliability Mechanisms

- **Tool error handling & fallback:** every tool call is wrapped in try/except; failures (network errors, blocked/403 scraping attempts, embedding failures) return a clear error or are skipped, instead of crashing the agent loop or the app.
- **Iteration cap:** the follow-up tool-calling loop stops after `MAX_TOOL_ITERATIONS` (15) tool calls and tells the user honestly if it couldn't finish, rather than looping forever.
- **Source-of-truth for reports:** `generate_report` always uses the real `{title, url}` data collected in Python — the model is never trusted to invent or relay source URLs.
- **Content grounding for summaries:** `summarize_source` uses the actual scraped text already held in memory (`self._last_scrape`) rather than trusting the model to relay large page content back verbatim as a tool argument.
- **Blank-response guard:** if the model returns empty/`None` content with no tool call (observed during testing), the agent returns a clear fallback message instead of showing a blank UI bubble.
- **Input validation:** empty topics and empty follow-up messages are caught before any tool or LLM call is made.

## 11. Known Limitations

- Web search quality depends on DuckDuckGo results and can vary by topic.
- Scraping is text-only and is blocked by some sites (JS-rendered pages, paywalls, anti-bot/403 protection) — these are skipped automatically rather than stopping the research.
- The initial research pass (search → scrape → summarize) is deterministic Python, not model-chosen — a deliberate reliability trade-off explained in Section 6, since local models proved unreliable at autonomously chaining that many tool calls in the right order.
- The activity log shows tool usage after each turn completes rather than streaming live, since the current agent loop is synchronous.
- No persistent storage — sessions (including the RAG index) reset when the app restarts or a new session is started.
- Report and answer quality depend on the underlying model (`qwen2.5:7b`) and the quality/depth of scraped content.

## 12. Future Improvements

- Let the LLM choose tool order for the initial research pass too, once a more consistently reliable tool-calling model is available.
- Stream tool status live in the UI instead of showing it after each turn completes.
- Add caching for repeated searches/scrapes of the same URL.
- Add a lightweight test suite covering each tool and a couple of end-to-end prompts.
- Add source deduplication when the same URL turns up across multiple search queries.
- Persist sessions/vector store to disk so research isn't lost on restart.
