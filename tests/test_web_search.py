"""Tests for Web Search client."""

import pytest

from paper_retriever.clients.web_search import WebSearchClient


class TestWebSearchClient:
    """Tests for WebSearchClient."""

    def test_init_default(self):
        """Test client initialization with defaults."""
        client = WebSearchClient()
        assert client.enabled is True

    def test_init_disabled(self):
        """Test client initialization when disabled."""
        client = WebSearchClient(enabled=False)
        assert client.enabled is False

    def test_is_available_disabled(self):
        """Test availability when disabled."""
        client = WebSearchClient(enabled=False)
        assert client.is_available() is False

    def test_is_available_no_sdk(self):
        """Test availability when SDK not installed."""
        client = WebSearchClient(enabled=True)
        # SDK availability depends on installation
        # Just check it returns a boolean
        assert isinstance(client.is_available(), bool)


@pytest.mark.asyncio
class TestWebSearchClientAsync:
    """Async tests for WebSearchClient."""

    async def test_search_disabled(self):
        """Test search when disabled."""
        client = WebSearchClient(enabled=False)
        result = await client.search_for_pdf("Test Paper Title")
        assert result is None

    @pytest.mark.skip(reason="Requires Claude Agent SDK")
    async def test_search_for_pdf(self):
        """Test searching for a PDF."""
        client = WebSearchClient(enabled=True)

        if not client.is_available():
            pytest.skip("Claude Agent SDK not available")

        result = await client.search_for_pdf(
            title="Attention Is All You Need",
            doi="10.48550/arXiv.1706.03762",
            authors=["Vaswani", "Shazeer", "Parmar"],
        )

        # Result may or may not find a PDF
        if result:
            assert "pdf_url" in result
            assert "source" in result
