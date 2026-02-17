"""Tests for the Knowledge Base pipeline: document processor, vector store, and context builder."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from cachibot.models.knowledge import DocChunk, DocumentStatus
from cachibot.services.context_builder import ContextBuilder, KnowledgeContext
from cachibot.services.document_processor import DocumentProcessor
from cachibot.services.vector_store import SearchResult, VectorStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vector_store():
    """Create a VectorStore with a mocked fastembed embedder."""
    vs = VectorStore(model_name="test-model")
    # Mock the embedder so we never download an actual model
    mock_embedder = MagicMock()

    def fake_embed(texts):
        """Return deterministic fake embeddings (384-dim) for each text."""
        for _text in texts:
            rng = np.random.RandomState(hash(_text) % (2**31))
            yield rng.randn(384).astype(np.float32)

    mock_embedder.embed = fake_embed
    vs._embedder = mock_embedder
    return vs


@pytest.fixture
def txt_file(tmp_path) -> Path:
    """Create a sample .txt file."""
    p = tmp_path / "sample.txt"
    p.write_text("Hello world. This is a test document with some content.", encoding="utf-8")
    return p


@pytest.fixture
def md_file(tmp_path) -> Path:
    """Create a sample .md file."""
    p = tmp_path / "sample.md"
    p.write_text("# Title\n\nSome **markdown** content.\n\n- Item 1\n- Item 2", encoding="utf-8")
    return p


# ===========================================================================
# Document Processor Tests
# ===========================================================================


class TestDocumentProcessorExtraction:
    """Tests for text extraction from different file types."""

    def test_extract_txt(self, txt_file):
        processor = DocumentProcessor()
        text = processor.extract_text(txt_file, "txt")
        assert "Hello world" in text
        assert "test document" in text

    def test_extract_md(self, md_file):
        processor = DocumentProcessor()
        text = processor.extract_text(md_file, "md")
        assert "# Title" in text
        assert "**markdown**" in text
        assert "Item 1" in text

    def test_extract_txt_empty_file(self, tmp_path):
        p = tmp_path / "empty.txt"
        p.write_text("", encoding="utf-8")
        processor = DocumentProcessor()
        text = processor.extract_text(p, "txt")
        assert text == ""

    def test_extract_txt_unicode(self, tmp_path):
        p = tmp_path / "unicode.txt"
        p.write_text("Hola mundo. Esto es una prueba con acentos: cafe\u0301.", encoding="utf-8")
        processor = DocumentProcessor()
        text = processor.extract_text(p, "txt")
        assert "Hola mundo" in text


class TestDocumentProcessorChunking:
    """Tests for text chunking logic."""

    def test_empty_text_returns_empty(self):
        processor = DocumentProcessor(chunk_size=10, chunk_overlap=2)
        assert processor.chunk_text("") == []

    def test_whitespace_only_returns_empty(self):
        processor = DocumentProcessor(chunk_size=10, chunk_overlap=2)
        assert processor.chunk_text("   \n\t  ") == []

    def test_short_text_single_chunk(self):
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=10)
        text = "This is a short piece of text."
        chunks = processor.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "This is a short piece of text."

    def test_exact_chunk_size_single_chunk(self):
        processor = DocumentProcessor(chunk_size=5, chunk_overlap=1)
        text = "one two three four five"
        chunks = processor.chunk_text(text)
        assert len(chunks) == 1

    def test_multiple_chunks_created(self):
        processor = DocumentProcessor(chunk_size=3, chunk_overlap=1)
        text = "one two three four five six seven"
        chunks = processor.chunk_text(text)
        assert len(chunks) > 1

    def test_chunk_overlap_works(self):
        processor = DocumentProcessor(chunk_size=3, chunk_overlap=1)
        text = "alpha beta gamma delta epsilon zeta"
        chunks = processor.chunk_text(text)
        # With overlap=1 and size=3, stride = 2
        # Chunk 0: alpha beta gamma
        # Chunk 1: gamma delta epsilon
        # Chunk 2: epsilon zeta
        assert len(chunks) >= 2
        assert chunks[0] == "alpha beta gamma"
        assert chunks[1] == "gamma delta epsilon"

    def test_whitespace_normalized(self):
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=10)
        text = "word1   word2\n\nword3\tword4"
        chunks = processor.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "word1 word2 word3 word4"

    def test_no_overlap_stride(self):
        processor = DocumentProcessor(chunk_size=3, chunk_overlap=0)
        text = "a b c d e f"
        chunks = processor.chunk_text(text)
        assert chunks[0] == "a b c"
        assert chunks[1] == "d e f"


class TestDocumentProcessorPipeline:
    """Tests for the full process_document pipeline."""

    async def test_process_document_txt(self, txt_file, mock_vector_store):
        processor = DocumentProcessor(chunk_size=5, chunk_overlap=1, vector_store=mock_vector_store)
        processor._repo = MagicMock()
        processor._repo.update_document_status = AsyncMock()
        processor._repo.save_chunks = AsyncMock()

        count = await processor.process_document(
            document_id="doc-1",
            bot_id="bot-1",
            file_path=txt_file,
            file_type="txt",
        )

        assert count > 0
        processor._repo.save_chunks.assert_called_once()
        saved_chunks = processor._repo.save_chunks.call_args[0][0]
        assert len(saved_chunks) == count
        for chunk in saved_chunks:
            assert chunk.bot_id == "bot-1"
            assert chunk.document_id == "doc-1"
            assert chunk.embedding is not None

        processor._repo.update_document_status.assert_called_with(
            "doc-1", DocumentStatus.READY, chunk_count=count
        )

    async def test_process_empty_document(self, tmp_path, mock_vector_store):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")

        processor = DocumentProcessor(vector_store=mock_vector_store)
        processor._repo = MagicMock()
        processor._repo.update_document_status = AsyncMock()

        count = await processor.process_document(
            document_id="doc-empty",
            bot_id="bot-1",
            file_path=empty_file,
            file_type="txt",
        )

        assert count == 0
        processor._repo.update_document_status.assert_called_with(
            "doc-empty", DocumentStatus.READY, chunk_count=0
        )

    async def test_process_document_failure_sets_failed(self, txt_file, mock_vector_store):
        processor = DocumentProcessor(vector_store=mock_vector_store)
        processor._repo = MagicMock()
        processor._repo.update_document_status = AsyncMock()
        processor._repo.save_chunks = AsyncMock(side_effect=RuntimeError("db error"))

        with pytest.raises(RuntimeError, match="db error"):
            await processor.process_document(
                document_id="doc-fail",
                bot_id="bot-1",
                file_path=txt_file,
                file_type="txt",
            )

        processor._repo.update_document_status.assert_called_with("doc-fail", DocumentStatus.FAILED)


# ===========================================================================
# Vector Store Tests
# ===========================================================================


class TestVectorStoreSerialization:
    """Tests for embedding serialization (pgvector format: list[float])."""

    def test_serialize_list_returns_list(self):
        original = [1.0, 2.0, 3.0, 0.5, -1.5]
        serialized = VectorStore.serialize_embedding(original)
        assert isinstance(serialized, list)
        assert serialized == original

    def test_serialize_numpy_returns_list(self):
        original = np.array([0.1, 0.2, 0.3, -0.4], dtype=np.float32)
        serialized = VectorStore.serialize_embedding(original)
        assert isinstance(serialized, list)
        np.testing.assert_allclose(serialized, original.tolist(), atol=1e-6)

    def test_serialize_preserves_values(self):
        embedding = [1.0, 2.0, 3.0]
        result = VectorStore.serialize_embedding(embedding)
        assert result == [1.0, 2.0, 3.0]

    def test_serialize_384_dim(self):
        """Serialize with the actual embedding dimension used in production."""
        rng = np.random.RandomState(42)
        original = rng.randn(384).astype(np.float32)
        serialized = VectorStore.serialize_embedding(original)
        assert isinstance(serialized, list)
        assert len(serialized) == 384
        np.testing.assert_allclose(serialized, original.tolist(), atol=1e-6)

    def test_serialize_zeros(self):
        zeros = [0.0] * 10
        serialized = VectorStore.serialize_embedding(zeros)
        assert serialized == [0.0] * 10


class TestCosineSimilarity:
    """Tests for cosine similarity computation (standalone numpy tests)."""

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def test_identical_vectors(self):
        a = np.array([1.0, 2.0, 3.0])
        score = self._cosine_similarity(a, a)
        assert abs(score - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        score = self._cosine_similarity(a, b)
        assert abs(score) < 1e-6

    def test_opposite_vectors(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([-1.0, -2.0, -3.0])
        score = self._cosine_similarity(a, b)
        assert abs(score - (-1.0)) < 1e-6

    def test_zero_vector_returns_zero(self):
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 2.0, 3.0])
        assert self._cosine_similarity(a, b) == 0.0
        assert self._cosine_similarity(b, a) == 0.0

    def test_known_value(self):
        a = np.array([1.0, 0.0])
        b = np.array([1.0, 1.0])
        # cos(45 degrees) = 1/sqrt(2) ~ 0.7071
        score = self._cosine_similarity(a, b)
        assert abs(score - (1.0 / np.sqrt(2))) < 1e-6

    def test_symmetry(self):
        rng = np.random.RandomState(99)
        a = rng.randn(50).astype(np.float32)
        b = rng.randn(50).astype(np.float32)
        assert abs(self._cosine_similarity(a, b) - self._cosine_similarity(b, a)) < 1e-6


class TestVectorStoreSearch:
    """Tests for search_similar functionality (mocked session for pgvector queries)."""

    async def test_search_no_results_returns_empty(self, mock_vector_store):
        """When database returns no matching chunks, result is empty."""
        mock_vector_store.embed_text = AsyncMock(return_value=np.ones(384, dtype=np.float32))
        mock_vector_store._search_pgvector = AsyncMock(return_value=[])
        mock_vector_store._search_in_memory = AsyncMock(return_value=[])

        results = await mock_vector_store.search_similar("bot-1", "test query")

        assert results == []
        mock_vector_store.embed_text.assert_called_once_with("test query")

    async def test_search_returns_mapped_results(self, mock_vector_store):
        """Results from search are correctly returned as SearchResult objects."""
        mock_vector_store.embed_text = AsyncMock(return_value=np.ones(384, dtype=np.float32))

        expected = [
            SearchResult(
                chunk=DocChunk(
                    id="chunk-close",
                    document_id="doc-1",
                    bot_id="bot-1",
                    chunk_index=0,
                    content="close content",
                    embedding=None,
                ),
                score=0.95,
            ),
            SearchResult(
                chunk=DocChunk(
                    id="chunk-far",
                    document_id="doc-1",
                    bot_id="bot-1",
                    chunk_index=1,
                    content="far content",
                    embedding=None,
                ),
                score=0.72,
            ),
        ]
        mock_vector_store._search_pgvector = AsyncMock(return_value=expected)
        mock_vector_store._search_in_memory = AsyncMock(return_value=expected)

        results = await mock_vector_store.search_similar("bot-1", "test", limit=10, min_score=0.0)

        assert len(results) == 2
        assert results[0].chunk.id == "chunk-close"
        assert results[0].score == 0.95
        assert results[0].chunk.content == "close content"
        assert results[1].chunk.id == "chunk-far"
        assert results[1].score == 0.72

    async def test_search_result_embeddings_are_none(self, mock_vector_store):
        """Returned SearchResult chunks should not include the embedding blob."""
        mock_vector_store.embed_text = AsyncMock(return_value=np.ones(384, dtype=np.float32))

        expected = [
            SearchResult(
                chunk=DocChunk(
                    id="chunk-1",
                    document_id="doc-1",
                    bot_id="bot-1",
                    chunk_index=0,
                    content="test content",
                    embedding=None,
                ),
                score=0.85,
            ),
        ]
        mock_vector_store._search_pgvector = AsyncMock(return_value=expected)
        mock_vector_store._search_in_memory = AsyncMock(return_value=expected)

        results = await mock_vector_store.search_similar("bot-1", "test")

        assert len(results) == 1
        assert results[0].chunk.embedding is None

    async def test_search_with_filenames(self, mock_vector_store):
        """search_with_filenames attaches document filenames to results."""
        mock_vector_store.embed_text = AsyncMock(return_value=np.ones(384, dtype=np.float32))

        search_results = [
            SearchResult(
                chunk=DocChunk(
                    id="chunk-1",
                    document_id="doc-1",
                    bot_id="bot-1",
                    chunk_index=0,
                    content="test content",
                    embedding=None,
                ),
                score=0.85,
            ),
        ]
        mock_vector_store._search_pgvector = AsyncMock(return_value=search_results)
        mock_vector_store._search_in_memory = AsyncMock(return_value=search_results)

        mock_vector_store._repo = MagicMock()
        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.filename = "guide.pdf"
        mock_vector_store._repo.get_documents_by_bot = AsyncMock(return_value=[mock_doc])

        results = await mock_vector_store.search_with_filenames("bot-1", "test")

        assert len(results) == 1
        assert results[0].document_filename == "guide.pdf"


# ===========================================================================
# Context Builder Tests
# ===========================================================================


class TestKnowledgeContext:
    """Tests for KnowledgeContext.to_prompt_section formatting."""

    def test_all_sections(self):
        ctx = KnowledgeContext(
            instructions="Do X and Y.",
            relevant_docs="[From: doc.pdf]\nSome relevant text.",
            recent_history="[msg-1] User: hello",
            contacts="- Alice: friend",
            skills="### Greeting\nSay hi nicely.",
            notes="### My Note\nSome content.",
        )
        result = ctx.to_prompt_section()
        assert "## Active Skills" in result
        assert "## Custom Instructions" in result
        assert "## Notes" in result
        assert "## Known Contacts" in result
        assert "## Relevant Knowledge" in result
        assert "## Recent Conversation Summary" in result

    def test_section_ordering(self):
        ctx = KnowledgeContext(
            instructions="instructions",
            relevant_docs="docs",
            recent_history="history",
            contacts="contacts",
            skills="skills",
            notes="notes",
        )
        result = ctx.to_prompt_section()
        # Skills should come first, then instructions, notes, contacts, docs, history
        skills_pos = result.index("Active Skills")
        instructions_pos = result.index("Custom Instructions")
        notes_pos = result.index("Notes")
        contacts_pos = result.index("Known Contacts")
        docs_pos = result.index("Relevant Knowledge")
        history_pos = result.index("Recent Conversation Summary")

        assert skills_pos < instructions_pos
        assert instructions_pos < notes_pos
        assert notes_pos < contacts_pos
        assert contacts_pos < docs_pos
        assert docs_pos < history_pos

    def test_empty_context(self):
        ctx = KnowledgeContext(
            instructions=None,
            relevant_docs=None,
            recent_history=None,
            contacts=None,
            skills=None,
            notes=None,
        )
        assert ctx.to_prompt_section() == ""

    def test_partial_context(self):
        ctx = KnowledgeContext(
            instructions="Be helpful.",
            relevant_docs=None,
            recent_history=None,
            contacts=None,
            skills=None,
            notes=None,
        )
        result = ctx.to_prompt_section()
        assert "## Custom Instructions" in result
        assert "Be helpful." in result
        assert "Relevant Knowledge" not in result
        assert "Recent Conversation" not in result

    def test_separator_between_sections(self):
        ctx = KnowledgeContext(
            instructions="inst",
            relevant_docs="docs",
            recent_history=None,
            contacts=None,
            skills=None,
        )
        result = ctx.to_prompt_section()
        assert "\n\n---\n\n" in result


class TestContextBuilderBuildContext:
    """Tests for ContextBuilder.build_context assembly."""

    async def test_build_context_with_no_data(self):
        """When all repos return empty data, context should be gracefully empty."""
        builder = ContextBuilder(vector_store=MagicMock())
        builder._repo = MagicMock()
        builder._repo.get_instructions = AsyncMock(return_value=None)
        builder._repo.get_bot_messages = AsyncMock(return_value=[])
        builder._contacts_repo = MagicMock()
        builder._contacts_repo.get_contacts_by_bot = AsyncMock(return_value=[])
        builder._skills_repo = MagicMock()
        builder._skills_repo.get_bot_skill_definitions = AsyncMock(return_value=[])
        builder._notes_repo = MagicMock()
        builder._notes_repo.search_notes = AsyncMock(return_value=[])
        builder._notes_repo.get_notes_by_bot = AsyncMock(return_value=[])

        mock_vs = builder._vector_store
        mock_vs.search_with_filenames = AsyncMock(return_value=[])

        ctx = await builder.build_context("bot-1", "hello")
        assert ctx.instructions is None
        assert ctx.relevant_docs is None
        assert ctx.recent_history is None
        assert ctx.contacts is None
        assert ctx.skills is None
        assert ctx.notes is None
        assert ctx.to_prompt_section() == ""

    async def test_build_context_with_instructions(self):
        builder = ContextBuilder(vector_store=MagicMock())
        builder._repo = MagicMock()
        instruction_mock = MagicMock()
        instruction_mock.content = "Always be polite."
        builder._repo.get_instructions = AsyncMock(return_value=instruction_mock)
        builder._repo.get_bot_messages = AsyncMock(return_value=[])
        builder._contacts_repo = MagicMock()
        builder._contacts_repo.get_contacts_by_bot = AsyncMock(return_value=[])
        builder._skills_repo = MagicMock()
        builder._skills_repo.get_bot_skill_definitions = AsyncMock(return_value=[])
        builder._notes_repo = MagicMock()
        builder._notes_repo.search_notes = AsyncMock(return_value=[])
        builder._notes_repo.get_notes_by_bot = AsyncMock(return_value=[])

        mock_vs = builder._vector_store
        mock_vs.search_with_filenames = AsyncMock(return_value=[])

        ctx = await builder.build_context("bot-1", "hello")
        assert ctx.instructions == "Always be polite."

    async def test_build_context_relevant_docs(self):
        mock_vs = MagicMock()
        mock_vs.search_with_filenames = AsyncMock(
            return_value=[
                SearchResult(
                    chunk=DocChunk(
                        id="c-1",
                        document_id="d-1",
                        bot_id="bot-1",
                        chunk_index=0,
                        content="Python is great.",
                    ),
                    score=0.85,
                    document_filename="guide.pdf",
                ),
            ]
        )

        builder = ContextBuilder(vector_store=mock_vs)
        builder._repo = MagicMock()
        builder._repo.get_instructions = AsyncMock(return_value=None)
        builder._repo.get_bot_messages = AsyncMock(return_value=[])
        builder._contacts_repo = MagicMock()
        builder._contacts_repo.get_contacts_by_bot = AsyncMock(return_value=[])
        builder._skills_repo = MagicMock()
        builder._skills_repo.get_bot_skill_definitions = AsyncMock(return_value=[])
        builder._notes_repo = MagicMock()
        builder._notes_repo.search_notes = AsyncMock(return_value=[])
        builder._notes_repo.get_notes_by_bot = AsyncMock(return_value=[])

        ctx = await builder.build_context("bot-1", "tell me about python")
        assert ctx.relevant_docs is not None
        assert "Python is great." in ctx.relevant_docs
        assert "guide.pdf" in ctx.relevant_docs

    async def test_build_context_empty_query_skips_docs(self):
        mock_vs = MagicMock()
        mock_vs.search_with_filenames = AsyncMock(return_value=[])

        builder = ContextBuilder(vector_store=mock_vs)
        builder._repo = MagicMock()
        builder._repo.get_instructions = AsyncMock(return_value=None)
        builder._repo.get_bot_messages = AsyncMock(return_value=[])
        builder._contacts_repo = MagicMock()
        builder._contacts_repo.get_contacts_by_bot = AsyncMock(return_value=[])
        builder._skills_repo = MagicMock()
        builder._skills_repo.get_bot_skill_definitions = AsyncMock(return_value=[])
        builder._notes_repo = MagicMock()
        builder._notes_repo.search_notes = AsyncMock(return_value=[])
        builder._notes_repo.get_notes_by_bot = AsyncMock(return_value=[])

        ctx = await builder.build_context("bot-1", "   ")
        assert ctx.relevant_docs is None

    async def test_build_enhanced_system_prompt_with_context(self):
        mock_vs = MagicMock()
        mock_vs.search_with_filenames = AsyncMock(return_value=[])

        builder = ContextBuilder(vector_store=mock_vs)
        builder._repo = MagicMock()
        instruction_mock = MagicMock()
        instruction_mock.content = "Be concise."
        builder._repo.get_instructions = AsyncMock(return_value=instruction_mock)
        builder._repo.get_bot_messages = AsyncMock(return_value=[])
        builder._contacts_repo = MagicMock()
        builder._contacts_repo.get_contacts_by_bot = AsyncMock(return_value=[])
        builder._skills_repo = MagicMock()
        builder._skills_repo.get_bot_skill_definitions = AsyncMock(return_value=[])
        builder._notes_repo = MagicMock()
        builder._notes_repo.search_notes = AsyncMock(return_value=[])
        builder._notes_repo.get_notes_by_bot = AsyncMock(return_value=[])

        prompt = await builder.build_enhanced_system_prompt(
            base_prompt="You are CachiBot.",
            bot_id="bot-1",
            user_message="hello",
        )
        assert "You are CachiBot." in prompt
        assert "Be concise." in prompt
        assert "Custom Instructions" in prompt

    async def test_build_enhanced_system_prompt_no_context(self):
        mock_vs = MagicMock()
        mock_vs.search_with_filenames = AsyncMock(return_value=[])

        builder = ContextBuilder(vector_store=mock_vs)
        builder._repo = MagicMock()
        builder._repo.get_instructions = AsyncMock(return_value=None)
        builder._repo.get_bot_messages = AsyncMock(return_value=[])
        builder._contacts_repo = MagicMock()
        builder._contacts_repo.get_contacts_by_bot = AsyncMock(return_value=[])
        builder._skills_repo = MagicMock()
        builder._skills_repo.get_bot_skill_definitions = AsyncMock(return_value=[])
        builder._notes_repo = MagicMock()
        builder._notes_repo.search_notes = AsyncMock(return_value=[])
        builder._notes_repo.get_notes_by_bot = AsyncMock(return_value=[])

        prompt = await builder.build_enhanced_system_prompt(
            base_prompt="You are CachiBot.",
            bot_id="bot-1",
            user_message="   ",
        )
        # With no context, should just return base prompt
        assert prompt == "You are CachiBot."

    async def test_build_enhanced_system_prompt_default_base(self):
        mock_vs = MagicMock()
        mock_vs.search_with_filenames = AsyncMock(return_value=[])

        builder = ContextBuilder(vector_store=mock_vs)
        builder._repo = MagicMock()
        builder._repo.get_instructions = AsyncMock(return_value=None)
        builder._repo.get_bot_messages = AsyncMock(return_value=[])
        builder._contacts_repo = MagicMock()
        builder._contacts_repo.get_contacts_by_bot = AsyncMock(return_value=[])
        builder._skills_repo = MagicMock()
        builder._skills_repo.get_bot_skill_definitions = AsyncMock(return_value=[])
        builder._notes_repo = MagicMock()
        builder._notes_repo.search_notes = AsyncMock(return_value=[])
        builder._notes_repo.get_notes_by_bot = AsyncMock(return_value=[])

        prompt = await builder.build_enhanced_system_prompt(
            base_prompt=None,
            bot_id="bot-1",
            user_message="hi",
        )
        assert "You are a helpful AI assistant." in prompt
