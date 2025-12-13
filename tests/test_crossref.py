"""Tests for CrossRef client."""

import pytest

from paper_retriever.clients.crossref import CrossRefClient


class TestCrossRefClient:
    """Tests for CrossRefClient."""

    def test_init(self):
        """Test client initialization."""
        client = CrossRefClient("test@example.com")
        assert client.email == "test@example.com"
        assert "mailto:test@example.com" in client.headers["User-Agent"]

    def test_init_empty_email(self):
        """Test client with empty email."""
        client = CrossRefClient("")
        assert client.email == ""

    def test_extract_metadata_full(self):
        """Test metadata extraction with full data."""
        work = {
            "DOI": "10.1234/test",
            "title": ["Test Paper Title"],
            "author": [
                {"family": "Smith", "given": "John"},
                {"family": "Doe", "given": "Jane"},
            ],
            "published-print": {"date-parts": [[2023, 5, 15]]},
            "container-title": ["Test Journal"],
            "is-referenced-by-count": 42,
            "link": [
                {"URL": "http://example.com/paper.pdf", "content-type": "application/pdf"}
            ],
        }

        metadata = CrossRefClient.extract_metadata(work)

        assert metadata["doi"] == "10.1234/test"
        assert metadata["title"] == "Test Paper Title"
        assert metadata["first_author"] == "Smith"
        assert metadata["year"] == 2023
        assert metadata["journal"] == "Test Journal"
        assert metadata["is_referenced_by_count"] == 42
        assert "http://example.com/paper.pdf" in metadata["pdf_links"]

    def test_extract_metadata_minimal(self):
        """Test metadata extraction with minimal data."""
        work = {"DOI": "10.1234/test"}

        metadata = CrossRefClient.extract_metadata(work)

        assert metadata["doi"] == "10.1234/test"
        assert metadata["first_author"] == "Unknown"
        assert metadata["year"] is None
        assert metadata["journal"] is None

    def test_extract_metadata_online_date(self):
        """Test extraction uses online date when print date missing."""
        work = {
            "DOI": "10.1234/test",
            "title": ["Test"],
            "published-online": {"date-parts": [[2022, 3, 10]]},
        }

        metadata = CrossRefClient.extract_metadata(work)
        assert metadata["year"] == 2022

    def test_extract_metadata_title_as_string(self):
        """Test extraction handles title as string."""
        work = {
            "DOI": "10.1234/test",
            "title": "Single Title String",  # Not a list
            "author": [],
        }

        metadata = CrossRefClient.extract_metadata(work)
        # Should handle gracefully
        assert metadata["first_author"] == "Unknown"


@pytest.mark.asyncio
class TestCrossRefClientAsync:
    """Async tests for CrossRefClient (require network)."""

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_work(self):
        """Test getting work by DOI."""
        client = CrossRefClient("test@example.com")
        work = await client.get_work("10.1038/nature12373")

        assert work is not None
        assert work.get("DOI") == "10.1038/nature12373"

    @pytest.mark.skip(reason="Requires network access")
    async def test_get_work_not_found(self):
        """Test getting non-existent work."""
        client = CrossRefClient("test@example.com")
        work = await client.get_work("10.9999/doesnotexist")

        assert work is None

    @pytest.mark.skip(reason="Requires network access")
    async def test_search_title(self):
        """Test searching by title."""
        client = CrossRefClient("test@example.com")
        results = await client.search_title("Attention Is All You Need")

        assert len(results) > 0
        # First result should be relevant
        assert "attention" in results[0].get("title", [""])[0].lower()
