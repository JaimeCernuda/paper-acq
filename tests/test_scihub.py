"""Tests for Sci-Hub client."""

import tempfile
from pathlib import Path

import pytest

from paper_retriever.clients.scihub import ScihubClient


class TestScihubClient:
    """Tests for ScihubClient."""

    def test_init_default(self):
        """Test client initialization with defaults."""
        client = ScihubClient()
        assert client.timeout == 60.0
        assert client.max_retries == 2
        assert client.proxy is None

    def test_init_with_params(self):
        """Test client initialization with custom params."""
        client = ScihubClient(
            timeout=30.0,
            max_retries=3,
            proxy="socks5://127.0.0.1:1080",
        )
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.proxy == "socks5://127.0.0.1:1080"

    def test_is_available(self):
        """Test availability check."""
        client = ScihubClient()
        assert client.is_available() is True

    def test_extract_pdf_url_iframe(self):
        """Test PDF URL extraction from iframe."""
        client = ScihubClient()
        html = '<iframe src="//moscow.sci-hub.se/123/abc.pdf"></iframe>'
        url = client._extract_pdf_url(html, "https://sci-hub.se")
        assert url == "https://moscow.sci-hub.se/123/abc.pdf"

    def test_extract_pdf_url_embed(self):
        """Test PDF URL extraction from embed."""
        client = ScihubClient()
        html = '<embed src="/downloads/paper.pdf" type="application/pdf">'
        url = client._extract_pdf_url(html, "https://sci-hub.se")
        assert url == "https://sci-hub.se/downloads/paper.pdf"

    def test_extract_pdf_url_absolute(self):
        """Test PDF URL extraction with absolute URL."""
        client = ScihubClient()
        html = '<a href="https://cdn.sci-hub.se/doc/123.pdf">Download</a>'
        url = client._extract_pdf_url(html, "https://sci-hub.se")
        assert url == "https://cdn.sci-hub.se/doc/123.pdf"

    def test_extract_pdf_url_not_found(self):
        """Test PDF URL extraction when no PDF found."""
        client = ScihubClient()
        html = "<html><body>No PDF here</body></html>"
        url = client._extract_pdf_url(html, "https://sci-hub.se")
        assert url is None

    def test_mirrors_list(self):
        """Test that mirrors list is populated."""
        client = ScihubClient()
        assert len(client.MIRRORS) > 0
        for mirror in client.MIRRORS:
            assert mirror.startswith("https://")


@pytest.mark.asyncio
class TestScihubClientAsync:
    """Async tests for ScihubClient."""

    @pytest.mark.skip(reason="Requires network access to unofficial source")
    async def test_download_by_doi(self):
        """Test downloading by DOI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ScihubClient()
            output_path = Path(tmpdir) / "test.pdf"
            result = await client.download_by_doi("10.1145/3375633", output_path)
            # Result depends on network/availability
            if result:
                assert output_path.exists()
                assert result["source"] == "scihub"

    async def test_download_by_doi_invalid(self):
        """Test downloading with invalid DOI returns None gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = ScihubClient(timeout=5.0, max_retries=1)
            output_path = Path(tmpdir) / "test.pdf"
            # This should return None, not raise an exception
            result = await client.download_by_doi(
                "10.9999/invalid/doi/does/not/exist", output_path
            )
            assert result is None

    async def test_download_by_title_without_scidownl(self):
        """Test that title search without scidownl returns None."""
        client = ScihubClient()
        # Force scidownl to be unavailable
        client._scidownl_available = False
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.pdf"
            result = await client.download_by_title("Some Paper Title", output_path)
            assert result is None
