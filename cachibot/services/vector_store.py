"""
Vector Store Service for Knowledge Base.

Provides embedding generation and similarity search.
Uses Prompture embedding drivers (OpenAI, Ollama) as primary backend,
with fastembed as a fallback for local/offline use.

On PostgreSQL: uses pgvector for native cosine distance search.
On SQLite: loads embeddings into memory and computes cosine similarity with numpy.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import select

if TYPE_CHECKING:
    from fastembed import TextEmbedding

    from prompture.drivers.async_embedding_base import AsyncEmbeddingDriver

from cachibot.models.knowledge import DocChunk
from cachibot.storage import db
from cachibot.storage.models.knowledge import DocChunk as DocChunkORM
from cachibot.storage.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

# Prefixes that indicate a fastembed model (not a provider/model format)
_FASTEMBED_PREFIXES = ("BAAI/", "sentence-transformers/", "jinaai/")


@dataclass
class SearchResult:
    """A search result with similarity score."""

    chunk: DocChunk
    score: float  # Cosine similarity (0-1, higher is better)
    document_filename: str | None = None


class VectorStore:
    """
    Vector store for document chunk embeddings.

    Uses Prompture embedding drivers (OpenAI, Ollama) as primary backend.
    Falls back to fastembed for local models (BAAI/*, sentence-transformers/*).

    On PostgreSQL: uses pgvector for native cosine distance search.
    On SQLite: loads embeddings into memory and computes cosine similarity with numpy.
    """

    DEFAULT_MODEL = "openai/text-embedding-3-small"
    EMBEDDING_DIM = 1536

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or self.DEFAULT_MODEL
        self._embedder: TextEmbedding | None = None  # fastembed fallback
        self._async_driver: AsyncEmbeddingDriver | None = None
        self._repo = KnowledgeRepository()

    def _is_provider_model(self) -> bool:
        """Check if the model uses provider/model format (not a fastembed model)."""
        return not any(self.model_name.startswith(prefix) for prefix in _FASTEMBED_PREFIXES)

    def _get_async_driver(self) -> "AsyncEmbeddingDriver":
        """Lazily instantiate a Prompture async embedding driver."""
        if self._async_driver is None:
            from prompture.drivers.embedding_registry import get_async_embedding_driver_for_model

            self._async_driver = get_async_embedding_driver_for_model(self.model_name)
        return self._async_driver

    def _get_embedder(self) -> "TextEmbedding":
        """Lazily load the fastembed model (fallback for local models)."""
        if self._embedder is None:
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding(model_name=self.model_name)
        return self._embedder

    def get_dimensions(self) -> int:
        """Get the embedding dimensions for the current model."""
        from prompture.drivers.embedding_base import EMBEDDING_MODEL_DIMENSIONS

        # Try the full model name first, then just the model ID part
        if self.model_name in EMBEDDING_MODEL_DIMENSIONS:
            return EMBEDDING_MODEL_DIMENSIONS[self.model_name]
        parts = self.model_name.split("/", 1)
        if len(parts) > 1 and parts[1] in EMBEDDING_MODEL_DIMENSIONS:
            return EMBEDDING_MODEL_DIMENSIONS[parts[1]]

        # Fall back to driver's default
        if self._is_provider_model():
            try:
                driver = self._get_async_driver()
                return driver.default_dimensions
            except Exception:
                pass
        return self.EMBEDDING_DIM

    @staticmethod
    def serialize_embedding(embedding: list[float] | np.ndarray) -> list[float]:
        """Convert embedding to list for storage.

        Both pgvector and VectorType (SQLite) accept list[float].
        """
        if isinstance(embedding, np.ndarray):
            return embedding.tolist()  # type: ignore[no-any-return]
        return list(embedding)

    def _embed_sync(self, texts: list[str]) -> list[np.ndarray]:
        """Synchronous embedding generation via fastembed (for use in executor)."""
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

        Uses Prompture async drivers for provider models (OpenAI, Ollama).
        Falls back to fastembed via executor for local models.
        """
        if not texts:
            return []

        if self._is_provider_model():
            return await self._embed_via_driver(texts)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._embed_sync, texts)

    async def _embed_via_driver(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings using a Prompture async embedding driver."""
        driver = self._get_async_driver()
        result = await driver.embed(texts, {})
        raw_embeddings = result["embeddings"]
        return [np.array(e, dtype=np.float32) for e in raw_embeddings]

    async def search_similar(
        self,
        bot_id: str,
        query: str,
        limit: int = 3,
        min_score: float = 0.3,
    ) -> list[SearchResult]:
        """
        Search for chunks similar to the query.

        On PostgreSQL: uses pgvector cosine_distance() for O(log N) search.
        On SQLite: loads embeddings into memory and uses numpy for similarity.

        Args:
            bot_id: Bot to search within
            query: Search query text
            limit: Maximum results to return
            min_score: Minimum similarity score (0-1)

        Returns:
            List of SearchResult sorted by similarity (highest first)
        """
        # Generate query embedding
        query_embedding = await self.embed_text(query)

        if db.db_type == "postgresql":
            return await self._search_pgvector(bot_id, query_embedding, limit, min_score)
        else:
            return await self._search_in_memory(bot_id, query_embedding, limit, min_score)

    async def _search_pgvector(
        self,
        bot_id: str,
        query_embedding: np.ndarray,
        limit: int,
        min_score: float,
    ) -> list[SearchResult]:
        """Search using pgvector's native cosine distance (PostgreSQL only)."""
        query_embedding_list = query_embedding.tolist()

        # pgvector cosine distance: 0 = identical, 2 = opposite
        # similarity = 1 - distance
        cosine_distance = DocChunkORM.embedding.cosine_distance(query_embedding_list)

        stmt = (
            select(
                DocChunkORM,
                (1 - cosine_distance).label("similarity"),
            )
            .where(DocChunkORM.bot_id == bot_id)
            .where(DocChunkORM.embedding.isnot(None))
            .where((1 - cosine_distance) >= min_score)
            .order_by(cosine_distance)  # ascending = most similar first
            .limit(limit)
        )

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.all()

        results: list[SearchResult] = []
        for row_model, similarity in rows:
            chunk = DocChunk(
                id=row_model.id,
                document_id=row_model.document_id,
                bot_id=row_model.bot_id,
                chunk_index=row_model.chunk_index,
                content=row_model.content,
                embedding=None,  # Don't return the embedding blob
            )
            results.append(SearchResult(chunk=chunk, score=float(similarity)))

        return results

    async def _search_in_memory(
        self,
        bot_id: str,
        query_embedding: np.ndarray,
        limit: int,
        min_score: float,
    ) -> list[SearchResult]:
        """Search using in-memory cosine similarity (SQLite fallback)."""
        # Load all embeddings for this bot
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(DocChunkORM).where(
                    DocChunkORM.bot_id == bot_id,
                    DocChunkORM.embedding.isnot(None),
                )
            )
            rows = result.scalars().all()

        if not rows:
            return []

        # Compute cosine similarity in-memory
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        scored: list[tuple[float, DocChunkORM]] = []

        for row in rows:
            emb = row.embedding
            if emb is None:
                continue
            emb_array = np.array(emb, dtype=np.float32)
            emb_norm = emb_array / (np.linalg.norm(emb_array) + 1e-10)
            similarity = float(np.dot(query_norm, emb_norm))
            if similarity >= min_score:
                scored.append((similarity, row))

        # Sort by similarity descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        results: list[SearchResult] = []
        for similarity, row_model in top:
            chunk = DocChunk(
                id=row_model.id,
                document_id=row_model.document_id,
                bot_id=row_model.bot_id,
                chunk_index=row_model.chunk_index,
                content=row_model.content,
                embedding=None,
            )
            results.append(SearchResult(chunk=chunk, score=similarity))

        return results

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
    """Get the shared VectorStore instance (config-aware)."""
    global _vector_store
    if _vector_store is None:
        from cachibot.config import Config

        config = Config.load()
        _vector_store = VectorStore(model_name=config.knowledge.embedding_model)
    return _vector_store
