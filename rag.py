import uuid
import chromadb
import ollama

EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 200     # words per chunk
CHUNK_OVERLAP = 40   # words of overlap between consecutive chunks


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split text into overlapping word-based chunks. Overlap keeps
    ideas that span a chunk boundary from being cut in half.
    """
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(chunk_size - overlap, 1)

    for start in range(0, len(words), step):
        chunk_words = words[start:start + chunk_size]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break

    return chunks


def embed_text(text):
    """Embed a single piece of text using the local Ollama embedding model."""
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


class ResearchVectorStore:
    """
    A per-session, in-memory vector store over the content of every
    source the agent has scraped and summarized. Backed by ChromaDB;
    embeddings are computed ourselves via Ollama rather than Chroma's
    default embedding function, so no extra model download is needed
    beyond what's already pulled through Ollama.
    """

    def __init__(self):
        self._client = chromadb.Client()  # ephemeral, in-memory client
        # Unique collection name so multiple sessions/users in the same
        # process never collide with each other's data.
        self._collection = self._client.create_collection(
            name=f"research_sources_{uuid.uuid4().hex[:8]}"
        )
        self._next_id = 0

    def add_source(self, title, url, content):
        """Chunk + embed a source's full text and store it."""
        chunks = chunk_text(content)
        if not chunks:
            return

        ids, embeddings, documents, metadatas = [], [], [], []

        for chunk in chunks:
            try:
                embedding = embed_text(chunk)
            except Exception:
                # Skip chunks that fail to embed rather than aborting
                # the whole source (reliability: don't let one bad
                # chunk block the rest of the pipeline).
                continue

            ids.append(str(self._next_id))
            self._next_id += 1
            embeddings.append(embedding)
            documents.append(chunk)
            metadatas.append({"title": title or "Unknown source", "url": url or ""})

        if ids:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

    def query(self, question, n_results=4):
        """
        Return the most relevant chunks (with title/url) for a question.
        Returns [] if the store is empty or embedding/query fails.
        """
        count = self._collection.count()
        if count == 0:
            return []

        try:
            question_embedding = embed_text(question)
        except Exception:
            return []

        results = self._collection.query(
            query_embeddings=[question_embedding],
            n_results=min(n_results, count),
        )

        chunks = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        for doc, meta in zip(documents, metadatas):
            chunks.append({
                "text": doc,
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
            })

        return chunks
