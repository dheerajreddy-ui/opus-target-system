"""ChromaDB RAG pipeline for document retrieval."""

import re

import chromadb


INJECTION_KEYWORDS = [
    "ignore previous",
    "system prompt",
    "you are now",
    "act as",
    "disregard",
    "bypass",
    "override instructions",
    "new instructions",
    "forget your",
    "important system update",
]


class RAGPipeline:
    def __init__(self, collection_name: str = "documents", persist_dir: str | None = None):
        if persist_dir:
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(self, doc_id: str, content: str, metadata: dict | None = None):
        """Add a document (or chunk) to the collection."""
        self.collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata or {}],
        )

    def query(self, user_query: str, n_results: int = 3) -> list[dict]:
        """Retrieve relevant document chunks."""
        if self.collection.count() == 0:
            return []
        results = self.collection.query(
            query_texts=[user_query],
            n_results=min(n_results, self.collection.count()),
        )
        docs = []
        for i in range(len(results["ids"][0])):
            docs.append(
                {
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                }
            )
        return docs

    def augmented_prompt(self, user_query: str, system_prompt: str) -> str:
        """Build a prompt with RAG context injected."""
        docs = self.query(user_query)
        if not docs:
            return system_prompt
        context_parts = []
        for doc in docs:
            source = doc["metadata"].get("source", "unknown")
            context_parts.append(f"[Source: {source}]\n{doc['content']}")
        context_block = "\n\n---\n\n".join(context_parts)
        return f"{system_prompt}\n\n## Relevant Documents\n{context_block}"

    def filter_results(self, results: list[dict], defense_manager=None) -> list[dict]:
        """Filter RAG results for injection patterns (level 3+)."""
        if defense_manager is None or not defense_manager.is_enabled("rag_safety_filter"):
            return results
        filtered = []
        for doc in results:
            content_lower = doc.get("content", "").lower()
            is_suspicious = any(kw in content_lower for kw in INJECTION_KEYWORDS)
            if not is_suspicious:
                filtered.append(doc)
        return filtered
