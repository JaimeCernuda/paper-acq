"""Tests for Semantic Scholar client."""

import pytest

from paper_retriever.clients.semantic_scholar import SemanticScholarClient


class TestSemanticScholarClient:
    """Tests for SemanticScholarClient."""

    def test_init_default(self):
        """Test client initialization with defaults."""
        client = SemanticScholarClient()
        assert client.api_key is None
        assert client.delay == 3.0  # Slow without API key
        assert "x-api-key" not in client.headers

    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = SemanticScholarClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.delay == 0.01  # Fast with API key
        assert client.headers["x-api-key"] == "test_key"


@pytest.mark.asyncio
class TestSemanticScholarClientAsync:
    """Async tests for SemanticScholarClient."""

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_paper_by_doi(self):
        """Test getting paper by DOI."""
        client = SemanticScholarClient()
        result = await client.get_paper("10.18653/v1/N19-1423")  # BERT paper

        if result:
            assert "title" in result
            assert "authors" in result

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_paper_not_found(self):
        """Test getting non-existent paper."""
        client = SemanticScholarClient()
        result = await client.get_paper("10.9999/doesnotexist")
        assert result is None

    @pytest.mark.skip(reason="Requires network access")
    async def test_search_title(self):
        """Test searching by title."""
        client = SemanticScholarClient()
        results = await client.search_title("BERT: Pre-training")

        assert len(results) > 0

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_paper_by_arxiv_id(self):
        """Test getting paper by arXiv ID."""
        client = SemanticScholarClient()
        result = await client.get_paper_by_arxiv_id("1706.03762")  # Transformer

        if result:
            assert "title" in result
            assert "attention" in result.get("title", "").lower()
