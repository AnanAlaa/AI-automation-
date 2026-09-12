# 🧠 Businessy - بيزنسي — AI Business Analyst

**Team Project 4 — AI Business Analyst**
AI & Automation Engineering — Final Team Project (Ollama-based AI Application)

Businessy is a friendly, bilingual-branded chat assistant that lets you upload a
business dataset (CSV or Excel) and ask natural-language questions about it.
Python/Pandas does all the real calculation; a locally running Ollama model
(`qwen2.5:7b`) understands the question, plans which analysis tools to run,
and explains the results in plain language.

---

## 1. Problem Statement

Business teams often have raw sales/revenue spreadsheets but no easy way to
query them without writing code or building a chart. Businessy closes that
gap: upload a spreadsheet, ask a question in plain English (or Arabic), and
get a grounded, numbers-accurate answer — with the LLM strictly forbidden
from inventing or recalculating numbers itself.

## 2. Application Features

- 💬 **Chat interface** with conversation history preserved per chat.
- 🆕 **New Chat** button — start a fresh analysis session at any time.
- 🗂️ **Chat history sidebar** — revisit and continue any previous conversation.
- 📁 **Upload CSV or Excel** (`.csv`, `.xlsx`, `.xls`) directly in the app.
- 🌗 **Light & Dark mode** toggle.
- 🌍 Friendly UI with bilingual branding (English / Arabic: بيزنسي).
- 🛡️ **Reliability guardrails**: input validation, safe error handling, and
  a strict "Python calculates, the model only explains" rule so answers
  can't hallucinate numbers.

## 3. Technologies Used

| Layer            | Technology                          |
|-------------------|--------------------------------------|
| LLM runtime        | [Ollama](https://ollama.com) (local) |
| Model              | `qwen2.5:7b`                         |
| Data processing    | Python, Pandas, openpyxl             |
| Frontend / UI      | Gradio (`gradio>=5.0`)               |
| Language           | Python 3.10+                          |

## 4. Ollama Model Used & How to Run It

This app calls a **locally running** Ollama server — no cloud API keys needed.

1. Install Ollama: https://ollama.com/download
2. Pull the model used by this app:
   ```bash
   ollama pull qwen2.5:7b
   ```
3. Make sure the Ollama server is running (it usually starts automatically
   after install; otherwise run):
   ```bash
   ollama serve
   ```

If the model can't be reached, Businessy will show a friendly in-chat error
telling you to check `ollama serve` and the pulled model, instead of crashing.

> Want a smaller/faster model? Edit `MODEL_NAME` in
> `backend/ollama_client.py` and pull that model instead.

## 5. Installation / Setup Instructions

### Requirements
- Python 3.10+
- Ollama installed and running locally (see above)

### Quick start

```bash
# 1. Unzip the project and enter the folder
cd Businessy-AI-Business-Analyst

# 2. Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Make sure Ollama is running and the model is pulled (see section 4)

# 5. Run the app
python frontend/app.py
```

Gradio will print a local URL (e.g. `http://127.0.0.1:7860`) — open it in
your browser.

### Even quicker

- **macOS / Linux:** `./run.sh`
- **Windows:** double-click `run.bat`

Both scripts create a virtual environment, install dependencies, and launch
the app for you.

## 6. Application Architecture

```
User (browser)
   │  types a question / uploads a file
   ▼
Gradio Frontend (frontend/app.py)
   │  manages chats, history, uploaded dataset per chat
   ▼
BusinessAnalyst (backend/analyst.py)
   │  Step 1: sends dataset schema + question to Ollama → gets a JSON "tool plan"
   ▼
Ollama (qwen2.5:7b)  ──►  "call get_total_revenue, get_top_products, ..."
   │
   ▼
Python Tool Layer (backend/analysis_tools.py)
   │  Pandas performs the ACTUAL calculations (ground truth)
   ▼
BusinessAnalyst
   │  Step 2: sends the question + Python results back to Ollama
   ▼
Ollama (qwen2.5:7b)  ──►  turns numbers into a clear, human explanation
   │
   ▼
Gradio Chatbot  ──►  shown to the user
```

This matches the required architecture:
`User → Interface → Ollama → Tool Selection → Python Tool(s) → Tool Result → Ollama → Final Response`

Ollama **never** performs the math — it only decides which tools to call
and later explains the Python-calculated results in natural language.

### Folder structure

```
Businessy-AI-Business-Analyst/
├── frontend/
│   └── app.py              # Gradio UI (chat, history, upload, theme toggle)
├── backend/
│   ├── analyst.py          # BusinessAnalyst: planning + execution + explanation
│   ├── analysis_tools.py   # The 5 Pandas analysis tools (ground truth math)
│   ├── data_loader.py      # CSV / Excel loading & validation
│   ├── ollama_client.py    # Thin wrapper around the local Ollama call
│   └── schema_analyzer.py  # Builds a dataset schema summary for the LLM
├── data/                   # Sample demo datasets
├── tests/                  # Basic tests for data loading & analysis tools
├── requirements.txt
├── run.sh / run.bat        # One-command launchers
└── README.md
```

## 7. Tools (5 required, all implemented)

All tools live in `backend/analysis_tools.py`, are selected by the LLM, and
executed by Python/Pandas (never guessed by the model):

| Tool | Description | Required inputs | Returns |
|------|--------------|------------------|---------|
| `get_total_revenue` | Calculates total revenue using the chosen revenue definition (direct column, quantity×price, or quantity×price×(1-discount)). | `revenue_definition` | Single float total |
| `get_monthly_sales` | Groups revenue by calendar month, and identifies the strongest and weakest month. | `date_column`, `revenue_definition` | Monthly breakdown + strongest/weakest month |
| `get_top_products` | Ranks products/items by total revenue and returns the top N. | `product_column`, `revenue_definition`, `top_n` | Ranked list of products with revenue |
| `get_customer_statistics` | Aggregates transactions, total revenue, and average revenue per customer/segment. | `customer_column`, `revenue_definition` | Per-customer/segment statistics |
| `compare_periods` | Compares total revenue between two specific months and computes the change (absolute + %). | `date_column`, `revenue_definition`, `period1`, `period2` | Revenue for both periods + change |

Every tool safely handles missing/invalid columns (via `errors="coerce"` and
validation in `analyst.py`, which rejects any column name the LLM invents
that doesn't actually exist in the uploaded dataset — this is the app's
**reliability mechanism**: strict input/plan validation before any
calculation runs).

## 8. Example Multi-Tool Conversations

**Example 1 — revenue + products + customers + timing (single question, 4 tools):**
> "Give me a full performance overview: total revenue, top 3 products,
> which customer segment brings in the most revenue, and which month was
> strongest?"

Workflow: `get_total_revenue` → `get_top_products` → `get_customer_statistics`
→ `get_monthly_sales` → Ollama combines all four results into one answer.

**Example 2 — period comparison with explanation (2 tools):**
> "How did January 2025 compare to February 2025, and what were the top 5
> products overall?"

Workflow: `compare_periods` (Jan vs Feb) → `get_top_products` (top 5) →
Ollama explains the revenue change and lists the ranked products, using the
exact numbers Python returned.

## 9. Advanced Concept Implemented

**Reliability through plan validation & guarded natural-language grounding.**

Rather than trusting the LLM's output directly, `BusinessAnalyst.ask()`:
1. Forces the model to output a **structured JSON tool plan** (not free text).
2. **Validates every column name and function name** in that plan against the
   real uploaded dataset before running anything — an invented column name
   is rejected with a clear error instead of silently failing or crashing.
3. Feeds the model only the **Python-calculated results** in the final step,
   with an explicit instruction set forbidding it from recalculating,
   renaming, reordering, or inventing values — Python is the only source of
   truth.

This turns an otherwise unpredictable LLM into a dependable analysis
explainer, which is the core reliability requirement for this project.

## 10. Known Limitations

- Uploaded datasets and chat conversation content live in server memory for
  the running session — restarting the server clears them (chat titles are
  not persisted to disk).
- Only the first sheet of an Excel workbook is read.
- Very large files may be slow, since the whole file is loaded into memory
  with Pandas.
- The quality of answers depends on the local model (`qwen2.5:7b`); a
  smaller/quantized model may occasionally produce a plan Businessy has to
  reject and ask you to rephrase.

## 11. Future Improvements

- Add chart/visualization generation (e.g., Plotly) alongside text answers.
- Persist chats and datasets to disk/a database so they survive restarts.
- Add a "Analyze My Business" one-click multi-step report generator.
- Support selecting a specific sheet when uploading multi-sheet Excel files.
- Add streaming, token-by-token responses from Ollama.

---

## Team

- Project 4 — AI Business Analyst
- Eyad Mostafa Atwa & Abd Allah El Gammal
