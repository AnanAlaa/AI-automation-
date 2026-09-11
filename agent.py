import json
import re
import ollama

from tools import (
    OLLAMA_MODEL,
    TOOL_SCHEMAS,
    TOOL_FUNCTIONS,
    generate_report,
)
from rag import ResearchVectorStore

SYSTEM_PROMPT = """You are an AI Research Assistant.

Your job is to help the user research a topic by using the tools
available to you. You do not have live knowledge of the web on your
own - you MUST use the tools to search, read, and summarize real
sources rather than inventing facts, studies, or URLs.

General workflow:
1. If the user gives a broad topic, you may call generate_research_questions
   to get useful search queries.
2. Call search_web ONCE (or at most twice) to find candidate sources.
   Search results only contain titles and short snippets - they are
   NOT enough information to summarize or report on.
3. For AT LEAST 2 of the search results, call scrape_page on the URL,
   then call summarize_source on the result. You MUST do this for
   multiple sources before you are done - do not stop after searching.
4. Use compare_sources if the user wants two sources compared.
5. Use retrieve_context for specific factual follow-up questions once
   sources have been summarized.
6. Use generate_report only once you have gathered and summarized
   enough sources, or when the user explicitly asks for the final report.

Rules:
- Call at most one tool at a time, then wait for its result before
  deciding the next step.
- Never invent URLs, authors, or findings that did not come from a tool.
- If a tool fails or returns nothing useful, tell the user plainly
  instead of making something up.
- Keep answers grounded only in information returned by the tools.
- NEVER present raw search_web snippets (titles/snippets) as your
  final answer or as a "summary" - a snippet is just a preview. You
  must scrape_page and summarize_source before describing a source's
  content or findings to the user.
- You already have working tools for every step (searching, scraping,
  summarizing, comparing, retrieving, reporting). NEVER ask the user
  which search engine, database, website, or method to use, and NEVER
  ask for permission before calling a tool - you already have
  everything you need. Just call the tool.
- If the user gives you a topic or a clear instruction, your very
  next action must be an actual tool call - not a description of
  what you are about to do, and not a clarifying question, unless
  the request is genuinely ambiguous about WHAT to research (not
  HOW to research it).
"""
MAX_TOOL_ITERATIONS = 15
MAX_TOOL_RESULT_CHARS = 4000

class ResearchAgent:
    """
    Holds one research session: the conversation history and the
    sources collected so far, so follow-up questions and the final
    report can use everything gathered earlier.
    """

    def __init__(self, model=OLLAMA_MODEL):
        self.model = model
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.sources = []          # accumulated {title, url, content, summary}
        self._titles_by_url = {}   # url -> title, filled in by search_web
        self._last_scrape = None   # {title, url, content} from the most recent scrape
        self.vector_store = ResearchVectorStore()  # RAG index for this session

    def research_topic(self, topic, max_sources=3, max_queries=3, status_callback=None):
        """
        Runs generate_research_questions -> search_web -> scrape_page ->
        summarize_source for a topic, populates self.sources and the
        vector store, and returns a short synthesized overview.
        """
        if status_callback:
            status_callback("Generating research questions...")

        questions_output = TOOL_FUNCTIONS["generate_research_questions"](topic)
        queries = self._parse_search_queries(questions_output)
        if not queries:
            queries = [topic]  # fallback if parsing failed
        queries = queries[:max_queries]

        seen_urls = set()
        collected = 0

        for query in queries:
            if collected >= max_sources:
                break

            if status_callback:
                status_callback(f"Searching: {query}...")

            results = TOOL_FUNCTIONS["search_web"](query, max_results=3)

            for r in results:
                if collected >= max_sources:
                    break

                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                if status_callback:
                    status_callback(f"Reading: {r.get('title', url)}...")

                content = TOOL_FUNCTIONS["scrape_page"](url)
                if not content:
                    continue

                if status_callback:
                    status_callback(f"Summarizing: {r.get('title', url)}...")

                summary = TOOL_FUNCTIONS["summarize_source"](content)

                self.sources.append({
                    "title": r.get("title", url),
                    "url": url,
                    "content": content,
                    "summary": summary,
                })

                try:
                    self.vector_store.add_source(r.get("title", url), url, content)
                except Exception:
                    pass  # indexing failure shouldn't block research

                collected += 1

        if self.sources:
            if status_callback:
                status_callback("Writing overview...")
            response_text = self._synthesize_overview(topic)
        else:
            response_text = (
                "I couldn't find or read any usable sources for this topic. "
                "Try rephrasing it, or a more specific/different topic."
            )

    
        self.messages.append({"role": "user", "content": f"Research topic: {topic}"})
        self.messages.append({"role": "assistant", "content": response_text})

        return response_text

    def _synthesize_overview(self, topic):
        """One plain (no-tools) LLM call to summarize what was found,
        grounded strictly in the collected summaries."""
        formatted = ""
        for i, s in enumerate(self.sources, start=1):
            formatted += f"\nSOURCE {i}: {s['title']}\nSummary: {s['summary']}\n"

        prompt = f"""You are a research assistant. Based ONLY on the source
summaries below, write a short (4-6 sentence) overview of what was
found about the topic "{topic}". Do not invent facts, sources, or
findings beyond what is given below.

{formatted}
"""
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response["message"]["content"]
        except Exception as e:
            return (
                f"Found {len(self.sources)} source(s) but couldn't generate "
                f"an overview ({e}). See the Sources panel for details."
            )

    @staticmethod
    def _parse_search_queries(ai_output):
        """Pulls the numbered lines under 'SEARCH QUERIES:' out of
        generate_research_questions' output."""
        if not ai_output or "SEARCH QUERIES:" not in ai_output:
            return []

        section = ai_output.split("SEARCH QUERIES:")[1]
        queries = []
        for line in section.splitlines():
            line = line.strip()
            if re.match(r"^\d+\.", line):
                queries.append(re.sub(r"^\d+\.\s*", "", line))
        return queries

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def chat(self, user_message, status_callback=None):
        """
        Send a user message, let the model call tools as needed, and
        return the final text response.

        status_callback(str) is optional - if provided, it's called
        with short status strings ("Searching...", "Scraping...", etc.)
        so a UI (Gradio) can show progress.
        """
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ITERATIONS):
            response = ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=TOOL_SCHEMAS,
            )

            message = response["message"]
            self.messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                # No tool requested -> this is the final answer.
                # Some models occasionally return empty/None content
                # instead of erroring - never let a blank message reach
                # the UI silently.
                content = message.get("content")
                if content and content.strip():
                    return content
                return (
                    "I wasn't able to generate a useful answer to that. "
                    "Could you try rephrasing the question, or ask me to "
                    "look into a specific part of the research?"
                )

            for call in tool_calls:
                name = call["function"]["name"]
                args = call["function"].get("arguments", {}) or {}

                if status_callback:
                    status_callback(f"Using tool: {name}...")

                result = self._execute_tool(name, args)

                self.messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": self._safe_stringify(result),
                })

        return (
            "I wasn't able to finish this within the allowed number of "
            "tool calls. Here is what I found so far - feel free to ask "
            "me to continue or narrow the request."
        )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------
    def _execute_tool(self, name, args):
        """
        Run the requested tool safely and update session state
        (self.sources, self._last_scrape, etc.) where relevant.
        """
        try:
            if name == "search_web":
                query = args.get("query", "")
                max_results = args.get("max_results", 5)
                results = TOOL_FUNCTIONS["search_web"](query, max_results=max_results)
                for r in results:
                    self._titles_by_url[r["url"]] = r["title"]
                return results

            if name == "scrape_page":
                url = args.get("url", "")
                content = TOOL_FUNCTIONS["scrape_page"](url)
                self._last_scrape = {
                    "title": self._titles_by_url.get(url, url),
                    "url": url,
                    "content": content,
                }
                if not content:
                    return {"error": f"Could not scrape {url}."}
                # Return a preview to the model, not the full 20k chars.
                return {"url": url, "content_preview": content[:1500]}

            if name == "summarize_source":
                
                if self._last_scrape and self._last_scrape.get("content"):
                    content = self._last_scrape["content"]
                    title = self._last_scrape["title"]
                    url = self._last_scrape["url"]
                else:
                    content = args.get("content", "")
                    title, url = "Unknown source", ""

                summary = TOOL_FUNCTIONS["summarize_source"](content)

                self.sources.append({
                    "title": title,
                    "url": url,
                    "content": content,
                    "summary": summary,
                })

                try:
                    self.vector_store.add_source(title, url, content)
                except Exception:
                    pass  

                self._last_scrape = None
                return {"title": title, "summary": summary}

            if name == "retrieve_context":
                query = args.get("query", "")
                chunks = self.vector_store.query(query)
                if not chunks:
                    return {"error": "No relevant content found yet - summarize at least one source first."}
                return chunks

            if name == "compare_sources":
                source1 = args.get("source1", "")
                source2 = args.get("source2", "")
                return TOOL_FUNCTIONS["compare_sources"](source1, source2)

            if name == "generate_research_questions":
                topic = args.get("topic", "")
                return TOOL_FUNCTIONS["generate_research_questions"](topic)

            if name == "generate_report":
                
                if not self.sources:
                    return {"error": "No sources gathered yet - search, scrape, and summarize at least one source first."}
                return generate_report(self.sources)

            return {"error": f"Unknown tool '{name}'."}

        except Exception as e:
            
            return {"error": f"Tool '{name}' failed: {e}"}

    @staticmethod
    def _safe_stringify(result):
        """Turn a tool result into a string safe to put back in the
        conversation, truncated so huge results don't blow the context."""
        if isinstance(result, str):
            text = result
        else:
            try:
                text = json.dumps(result, ensure_ascii=False)
            except TypeError:
                text = str(result)

        if len(text) > MAX_TOOL_RESULT_CHARS:
            text = text[:MAX_TOOL_RESULT_CHARS] + " ...[truncated]"
        return text

    # ------------------------------------------------------------------
    # Helpers for the Gradio layer
    # ------------------------------------------------------------------
    def reset(self):
        """Start a fresh session (new topic)."""
        self.__init__(model=self.model)

if __name__ == "__main__":
    agent = ResearchAgent()

    def print_status(msg):
        print(f"[status] {msg}")

    print(agent.chat(
        "Research the topic 'AI in Healthcare' and find a couple of sources.",
        status_callback=print_status,
    ))

    print("\n--- follow-up ---\n")
    print(agent.chat(
        "Now give me the final report.",
        status_callback=print_status,
    ))
