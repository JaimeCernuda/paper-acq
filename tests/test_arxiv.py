"""Tests for arXiv client."""

import pytest

from paper_retriever.clients.arxiv_client import ArxivClient


class TestArxivClient:
    """Tests for ArxivClient."""

    def test_init(self):
        """Test client initialization."""
        client = ArxivClient()
        assert client.client is not None
        assert client.client.delay_seconds == 3


@pytest.mark.asyncio
class TestArxivClientAsync:
    """Async tests for ArxivClient."""

    @pytest.mark.skip(reason="Requires network access")
    async def test_search_by_doi_arxiv(self):
        """Test searching by arXiv DOI."""
        client = ArxivClient()
        result = await client.search_by_doi("10.48550/arXiv.1706.03762")

        assert result is not None
        assert "attention" in result.title.lower()

    async def test_search_by_doi_non_arxiv(self):
        """Test that non-arXiv DOI returns None."""
        client = ArxivClient()
        result = await client.search_by_doi("10.1038/nature12373")
        assert result is None

    @pytest.mark.skip(reason="Requires network access")
    async def test_search_by_title(self):
        """Test searching by title."""
        client = ArxivClient()
        results = await client.search_by_title("Attention Is All You Need")

        assert len(results) > 0

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_pdf_url(self):
        """Test getting PDF URL from result."""
        client = ArxivClient()
        results = await client.search_by_title("Attention Is All You Need")

        if results:
            pdf_url = client.get_pdf_url(results[0])
            assert pdf_url.startswith("http")
            assert "arxiv.org" in pdf_url

    @pytest.mark.skip(reason="Requires network access")
    async def test_result_to_dict(self):
        """Test converting result to dict."""
        client = ArxivClient()
        results = await client.search_by_title("Attention Is All You Need")

        if results:
            data = ArxivClient.result_to_dict(results[0])
            assert "title" in data
            assert "authors" in data
            assert "pdf_url" in data
            assert isinstance(data["authors"], list)
