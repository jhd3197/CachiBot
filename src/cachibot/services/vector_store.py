"""
Vector Store Service for Knowledge Base.

Provides embedding generation and similarity search using fastembed.
"""

import asyncio
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from fastembed import TextEmbedding

from cachibot.models.knowledge import DocChunk
from cachibot.storage.repository import KnowledgeRepository


@dataclass
class SearchResult:
    """A search result with similarity score."""

    chunk: DocChunk
    score: float  # Cosine similarity (0-1, higher is better)
    document_filename: str | None = None


class VectorStore:
    """
    Vector store for document chunk embeddings.

    Uses fastembed for embedding generation and numpy for similarity search.
    Embeddings are stored as BLOB in SQLite for portability.
    """

    # Default embedding model (384 dimensions, good balance of quality/speed)
    DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM = 384

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or self.DEFAULT_MODEL
        self._embedder: TextEmbedding | None = None
        self._repo = KnowledgeRepository()

    def _get_embedder(self) -> "TextEmbedding":
        """Lazily load the embedding model."""
        if self._embedder is None:
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding(model_name=self.model_name)
        return self._embedder

    @staticmethod
    def serialize_embedding(embedding: list[float] | np.ndarray) -> bytes:
        """Serialize embedding to bytes for SQLite storage."""
        if isinstance(embedding, np.ndarray):
            return embedding.astype(np.float32).tobytes()
        return struct.pack(f"{len(embedding)}f", *embedding)

    @staticmethod
    def deserialize_embedding(data: bytes) -> np.ndarray:
        """Deserialize embedding from SQLite BLOB."""
        return np.frombuffer(data, dtype=np.float32)

    def _embed_sync(self, texts: list[str]) -> list[np.ndarray]:
        """Synchronous embedding generation (for use in executor)."""
        embedder = self._get_embedder()
        # fastembed returns a generator; convert to list
        embeddings = list(embedder.embed(texts))
        return [np.array(e, dtype=np.float32) for e in embeddings]

    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        """
        Generate embeddings for multiple texts.

        Runs in executor to avoid blocking the async event loop.
        """
        if not texts:
            return []

        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self._embed_sync, texts)
        return embeddings

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))

    async def search_similar(
        self,
        bot_id: str,
        query: str,
        limit: int = 3,
        min_score: float = 0.3,
    ) -> list[SearchResult]:
        """
        Search for chunks similar to the query.

        Args:
            bot_id: Bot to search within
            query: Search query text
            limit: Maximum results to return
            min_score: Minimum similarity score (0-1)

        Returns:
            List of SearchResult sorted by similarity (highest first)
        """
        # Get all chunks for this bot
        chunks = await self._repo.get_all_chunks_by_bot(bot_id)
        if not chunks:
            return []

        # Filter chunks with embeddings
        chunks_with_embeddings = [c for c in chunks if c.embedding]
        if not chunks_with_embeddings:
            return []

        # Embed the query
        query_embedding = await self.embed_text(query)

        # Compute similarities
        results: list[SearchResult] = []
        for chunk in chunks_with_embeddings:
            chunk_embedding = self.deserialize_embedding(chunk.embedding)  # type: ignore
            score = self.cosine_similarity(query_embedding, chunk_embedding)

            if score >= min_score:
                results.append(SearchResult(chunk=chunk, score=score))

        # Sort by score (descending) and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def get_document_filenames(self, bot_id: str) -> dict[str, str]:
        """Get mapping of document_id -> filename for a bot."""
        docs = await self._repo.get_documents_by_bot(bot_id)
        return {doc.id: doc.filename for doc in docs}

    async def search_with_filenames(
        self,
        bot_id: str,
        query: str,
        limit: int = 3,
        min_score: float = 0.3,
    ) -> list[SearchResult]:
        """Search and include document filenames in results."""
        results = await self.search_similar(bot_id, query, limit, min_score)

        if not results:
            return results

        # Get filenames
        filenames = await self.get_document_filenames(bot_id)

        # Attach filenames to results
        for result in results:
            result.document_filename = filenames.get(result.chunk.document_id)

        return results


# Singleton instance for shared use
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get the shared VectorStore instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
