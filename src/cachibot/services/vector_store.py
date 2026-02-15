"""
Vector Store Service for Knowledge Base.

Provides embedding generation and similarity search.
Uses pgvector for native similarity search on PostgreSQL,
or in-memory cosine similarity on SQLite.
"""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import select

if TYPE_CHECKING:
    from fastembed import TextEmbedding

from cachibot.models.knowledge import DocChunk
from cachibot.storage import db
from cachibot.storage.models.knowledge import DocChunk as DocChunkORM
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

    Uses fastembed for embedding generation.
    On PostgreSQL: uses pgvector for native cosine distance search.
    On SQLite: loads embeddings into memory and computes cosine similarity with numpy.
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
    def serialize_embedding(embedding: list[float] | np.ndarray) -> list[float]:
        """Convert embedding to list for storage.

        Both pgvector and VectorType (SQLite) accept list[float].
        """
        if isinstance(embedding, np.ndarray):
            return embedding.tolist()
        return list(embedding)

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

        async with db.async_session_maker() as session:
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
        async with db.async_session_maker() as session:
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
