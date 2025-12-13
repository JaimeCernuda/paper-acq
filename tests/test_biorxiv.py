"""Tests for bioRxiv/medRxiv client."""

import pytest

from paper_retriever.clients.biorxiv import BioRxivClient


class TestBioRxivClient:
    """Tests for BioRxivClient."""

    def test_init(self):
        """Test client initialization."""
        client = BioRxivClient()
        assert client.BIORXIV_API is not None
        assert client.MEDRXIV_API is not None


@pytest.mark.asyncio
class TestBioRxivClientAsync:
    """Async tests for BioRxivClient."""

    async def test_get_preprint_non_biorxiv_doi(self):
        """Test that non-bioRxiv DOI returns None."""
        client = BioRxivClient()
        result = await client.get_preprint("10.1038/nature12373")
        assert result is None

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_preprint_biorxiv(self):
        """Test getting bioRxiv preprint."""
        client = BioRxivClient()
        # Use a known bioRxiv DOI
        result = await client.get_preprint("10.1101/2020.01.01.000000")

        if result:
            assert "pdf_url" in result
            assert result["server"] in ("biorxiv", "medrxiv")

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_preprint_pdf_url_format(self):
        """Test that PDF URL has correct format."""
        client = BioRxivClient()
        # Test with any valid bioRxiv DOI
        result = await client.get_preprint("10.1101/2020.01.01.000000")

        if result and result.get("pdf_url"):
            assert ".full.pdf" in result["pdf_url"]
            assert "biorxiv.org" in result["pdf_url"] or "medrxiv.org" in result["pdf_url"]
