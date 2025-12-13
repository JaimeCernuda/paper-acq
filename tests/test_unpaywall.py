"""Tests for Unpaywall client."""

import pytest

from paper_retriever.clients.unpaywall import UnpaywallClient


class TestUnpaywallClient:
    """Tests for UnpaywallClient."""

    def test_init(self):
        """Test client initialization."""
        client = UnpaywallClient("test@example.com")
        assert client.email == "test@example.com"

    def test_init_empty_email(self):
        """Test client with empty email."""
        client = UnpaywallClient("")
        assert client.email == ""


@pytest.mark.asyncio
class TestUnpaywallClientAsync:
    """Async tests for UnpaywallClient."""

    async def test_get_oa_location_no_email(self):
        """Test that empty email returns None."""
        client = UnpaywallClient("")
        result = await client.get_oa_location("10.1234/test")
        assert result is None

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_oa_location_open_access(self):
        """Test getting OA location for an open access paper."""
        client = UnpaywallClient("test@example.com")
        # Use a known OA paper
        result = await client.get_oa_location("10.1371/journal.pone.0000000")

        if result:  # May vary based on paper availability
            assert "pdf_url" in result or "landing_page" in result

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_oa_location_not_found(self):
        """Test getting OA location for non-existent DOI."""
        client = UnpaywallClient("test@example.com")
        result = await client.get_oa_location("10.9999/doesnotexist")
        assert result is None
