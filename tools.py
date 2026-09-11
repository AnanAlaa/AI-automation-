# hala's code below

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import ollama
import re

OLLAMA_MODEL = "qwen2.5:7b"

def search_web(query, max_results=5):
    """
    Search the web for relevant research sources.
    """

    results = []

    try:
        with DDGS() as ddgs:

            search_results = ddgs.text(
                query,
                region="us-en",
                safesearch="moderate",
                timelimit=None,
                max_results=max_results
            )

            for result in search_results:

                title = result.get("title", "")
                url = result.get("href", "")
                snippet = result.get("body", "")

                # Ignore empty results
                if not title or not url:
                    continue

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet
                })

    except Exception as e:
        print(f"Search error: {e}")

    return results

# =========================
# 2. PAGE SCRAPER
# =========================

def scrape_page(url):
    """
    Extract clean text from a webpage.
    """

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/120.0 Safari/537.36"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "lxml"
        )

        # Remove unnecessary elements
        for element in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "form"
        ]):
            element.decompose()

        text = soup.get_text(
            separator=" ",
            strip=True
        )

        # Clean extra spaces
        text = re.sub(r"\s+", " ", text)

        # Limit extremely large pages
        text = text[:20000]

        return text

    except Exception as e:
        print(f"Scraping error: {e}")
        return ""

# =========================
# 3. SOURCE SUMMARIZER
# =========================

def summarize_source(content):
    """
    Summarize a source using Ollama.
    """

    if not content:
        return "No content available."

    prompt = f"""
You are a research assistant.

Summarize the following research source.

Requirements:
- Identify the main idea.
- Extract the most important findings.
- Mention important facts or evidence.
- Keep the summary concise and clear.
- Do not invent information.

SOURCE:
{content}
"""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]

    except Exception as e:
        return f"Summarization error: {e}"



# =========================
# 4. SOURCE COMPARATOR
# =========================

def compare_sources(source1, source2):
    """
    Compare two research sources using Ollama.
    """

    prompt = f"""
You are an expert research assistant.

Compare the two sources below.

Explain:
1. Main idea of Source 1
2. Main idea of Source 2
3. Points they agree on
4. Points they disagree on
5. Important differences
6. Overall conclusion

Do not invent information.

SOURCE 1:
{source1}

SOURCE 2:
{source2}
"""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]

    except Exception as e:
        return f"Comparison error: {e}"


# =========================
# 5. REPORT GENERATOR
# =========================

def generate_report(sources):
    """
    Generate a structured research report using ONLY
    the collected source summaries.
    """

    if not sources:
        return "No sources available."

    formatted_sources = ""

    for i, source in enumerate(sources, start=1):

        formatted_sources += f"""
SOURCE {i}
Title: {source["title"]}

Summary:
{source["summary"]}

"""

    prompt = f"""
You are an academic research assistant.

Create a structured research report based ONLY on the
information in the source summaries below.

The report must contain:

1. Introduction
2. Key Findings
3. Conclusion

IMPORTANT RULES:
- Do NOT create or invent any sources.
- Do NOT create authors' names.
- Do NOT create publication dates.
- Do NOT create URLs.
- Do NOT add a Sources section.
- Use ONLY the information provided below.
- If information is not available, do not invent it.

SOURCE SUMMARIES:

{formatted_sources}
"""

    try:

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        report = response["message"]["content"]

        # Add REAL sources from Python
        report += "\n\n## Sources\n\n"

        for i, source in enumerate(sources, start=1):

            report += f"{i}. {source['title']}\n"
            report += f"   {source['url']}\n\n"

        return report

    except Exception as e:

        return f"Report generation error: {e}"

# =========================
# 6. GENERATE RESEARCH QUESTIONS
# =========================
def generate_research_questions(topic):

    prompt = f"""
You are an academic research assistant.

Research topic:
{topic}

Generate exactly 5 research questions and exactly 5 web search queries.

The search queries MUST:
- Be specific to the research topic.
- Use academic and scientific terminology.
- Prefer reliable research sources.
- Avoid dictionary searches.
- Avoid broad single-word searches.
- Focus on studies, evidence, applications, benefits, risks, and findings.

Return ONLY this format:

RESEARCH QUESTIONS:
1. question
2. question
3. question
4. question
5. question

SEARCH QUERIES:
1. query
2. query
3. query
4. query
5. query
"""

    try:

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]

    except Exception as e:
        return f"Question generation error: {e}"

# =========================
# TEST
# =========================

if __name__ == "__main__":

    topic = "Artificial Intelligence in Healthcare"

    # =====================================
    # 1. RESEARCH QUESTIONS + SEARCH QUERIES
    # =====================================

    print("\n==============================")
    print("RESEARCH QUESTIONS")
    print("==============================")

    ai_output = generate_research_questions(topic)

    print(ai_output)

    # Extract search queries generated by Ollama
    queries_section = ai_output.split("SEARCH QUERIES:")[1]

    queries = []

    for line in queries_section.splitlines():

        line = line.strip()

        if re.match(r"^\d+\.", line):
            query = re.sub(r"^\d+\.\s*", "", line)
            queries.append(query)

    # =====================================
    # 2. WEB SEARCH
    # =====================================

    print("\n==============================")
    print("WEB SEARCH")
    print("==============================")

    all_results = []

    for query in queries:

        print(f"\nSearching: {query}")

        results = search_web(query, max_results=3)

        for result in results:

            print("Title:", result["title"])
            print("URL:", result["url"])
            print("Snippet:", result["snippet"])
            print("-" * 60)

            all_results.append(result)

    # =====================================
    # 3. PAGE SCRAPING
    # =====================================

    print("\n==============================")
    print("PAGE SCRAPING")
    print("==============================")

    sources = []

    for result in all_results[:5]:

        print("\nScraping:", result["title"])

        content = scrape_page(result["url"])

        if content:

            print("Scraping successful!")
            print("\nExtracted Content:")
            print(content[:2000])

            sources.append({
                "title": result["title"],
                "url": result["url"],
                "content": content
            })

        else:

            print("Could not scrape this page.")

    # =====================================
    # 4. SOURCE SUMMARIZATION
    # =====================================

    print("\n==============================")
    print("SOURCE SUMMARIZATION")
    print("==============================")

    for source in sources:

        print("\nSummarizing:", source["title"])

        summary = summarize_source(source["content"])

        source["summary"] = summary

        print("\nSummary:")
        print(summary)

    # =====================================
    # 5. SOURCE COMPARISON
    # =====================================

    print("\n==============================")
    print("SOURCE COMPARISON")
    print("==============================")

    if len(sources) >= 2:

        comparison = compare_sources(
            sources[0]["summary"],
            sources[1]["summary"]
        )

        print(comparison)

    else:

        print("Not enough sources to compare.")

    # =====================================
    # 6. REPORT GENERATION
    # =====================================

    print("\n==============================")
    print("FINAL RESEARCH REPORT")
    print("==============================")

    report_sources = []

    for source in sources:

        report_sources.append({
            "title": source["title"],
            "url": source["url"],
            "summary": source["summary"]
        })

    if report_sources:

        report = generate_report(report_sources)

        print(report)

    else:

        print("No sources available for report generation.")


# below is zeina's part

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "generate_research_questions",
            "description": (
                "Generate 5 research questions and 5 web search queries "
                "for a given research topic. Use this first when the "
                "user gives a broad topic and no specific questions yet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The research topic, e.g. 'AI in Healthcare'"
                    }
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for pages relevant to a query. Returns "
                "a list of titles, URLs, and snippets. Use this to find "
                "sources before scraping or summarizing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_page",
            "description": (
                "Download a webpage and extract its clean text content. "
                "Use this after search_web to read a specific URL's content "
                "before summarizing it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL of the page to scrape"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_source",
            "description": (
                "Summarize the text content of one source (article, page, "
                "etc.) into its main idea, findings, and evidence. Use this "
                "after scrape_page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The raw text content to summarize"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_sources",
            "description": (
                "Compare two source summaries and explain their agreements, "
                "disagreements, and overall conclusion. Use this when the "
                "user asks how two sources relate, or to cross-check findings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source1": {
                        "type": "string",
                        "description": "Summary or text of the first source"
                    },
                    "source2": {
                        "type": "string",
                        "description": "Summary or text of the second source"
                    }
                },
                "required": ["source1", "source2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_context",
            "description": (
                "Retrieve the most relevant text chunks from ALL sources "
                "collected so far in this session, ranked by similarity "
                "to a question (RAG - Retrieval-Augmented Generation). "
                "Use this when the user asks a specific factual question "
                "about the research and the short summaries already in "
                "conversation may not contain enough detail to answer "
                "accurately."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or topic to retrieve relevant context for"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "Generate a final structured research report (introduction, "
                "key findings, conclusion, sources) from the sources gathered "
                "so far in this session. Use this only once several sources "
                "have been searched, scraped, and summarized, or when the "
                "user explicitly asks for the final report."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
]

# this is a map 3lshan python y3raf ye3mel el tool el etnada 3leha 
TOOL_FUNCTIONS = {
    "generate_research_questions": generate_research_questions,
    "search_web": search_web,
    "scrape_page": scrape_page,
    "summarize_source": summarize_source,
    "compare_sources": compare_sources,
}
