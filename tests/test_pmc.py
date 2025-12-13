"""Tests for PubMed Central client."""

import pytest

from paper_retriever.clients.pmc import PMCClient


class TestPMCClient:
    """Tests for PMCClient."""

    def test_init_default(self):
        """Test client initialization with defaults."""
        client = PMCClient()
        assert client.api_key is None
        assert client.delay == 0.34  # Default rate limit

    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = PMCClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.delay == 0.1  # Faster with API key

    def test_init_with_email(self):
        """Test client initialization with email."""
        client = PMCClient(email="test@example.com")
        assert client.email == "test@example.com"


@pytest.mark.asyncio
class TestPMCClientAsync:
    """Async tests for PMCClient."""

    @pytest.mark.skip(reason="Requires network access")
    async def test_doi_to_pmcid(self):
        """Test converting DOI to PMCID."""
        client = PMCClient()
        # Use a known PMC paper
        pmcid = await client.doi_to_pmcid("10.1371/journal.pmed.0020124")

        # Should return a PMCID if the paper is in PMC
        if pmcid:
            assert pmcid.startswith("PMC")

    @pytest.mark.skip(reason="Requires network access")
    async def test_doi_to_pmcid_not_in_pmc(self):
        """Test DOI not in PMC returns None."""
        client = PMCClient()
        pmcid = await client.doi_to_pmcid("10.9999/notinpmc")
        assert pmcid is None

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_pdf_url(self):
        """Test getting PDF URL for a PMCID."""
        client = PMCClient()
        # Use a known open access PMC ID
        pdf_url = await client.get_pdf_url("PMC2700949")

        if pdf_url:
            assert "pdf" in pdf_url.lower() or "pmc" in pdf_url.lower()

    @pytest.mark.skip(reason="Requires network access")
    async def test_search_by_title(self):
        """Test searching PMC by title."""
        client = PMCClient()
        results = await client.search_by_title("open access publishing")

        assert isinstance(results, list)
