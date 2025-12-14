"""Tests for Library Genesis client."""

import tempfile
from pathlib import Path

import pytest

from paper_retriever.clients.libgen import LibGenClient


class TestLibGenClient:
    """Tests for LibGenClient."""

    def test_init_default(self):
        """Test client initialization with defaults."""
        client = LibGenClient()
        assert client.timeout == 60.0
        assert client.max_retries == 2

    def test_init_with_params(self):
        """Test client initialization with custom params."""
        client = LibGenClient(timeout=30.0, max_retries=3)
        assert client.timeout == 30.0
        assert client.max_retries == 3

    def test_is_available(self):
        """Test availability check."""
        client = LibGenClient()
        assert client.is_available() is True

    def test_extract_download_info_get_php(self):
        """Test download info extraction with get.php pattern."""
        client = LibGenClient()
        html = '<a href="https://libgen.rs/scimag/get.php?md5=abc123">GET</a>'
        info = client._extract_download_info(html)
        assert info is not None
        assert "md5=abc123" in info["url"]

    def test_extract_download_info_library_lol(self):
        """Test download info extraction with library.lol pattern."""
        client = LibGenClient()
        html = '<a href="https://library.lol/scimag/abc123">GET</a>'
        info = client._extract_download_info(html)
        assert info is not None
        assert "library.lol" in info["url"]

    def test_extract_download_info_relative(self):
        """Test download info extraction with relative URL."""
        client = LibGenClient()
        html = '<a href="/scimag/get.php?md5=abc123">GET</a>'
        info = client._extract_download_info(html)
        assert info is not None
        assert info["url"] == "/scimag/get.php?md5=abc123"

    def test_extract_download_info_not_found(self):
        """Test download info extraction when no link found."""
        client = LibGenClient()
        html = "<html><body>No downloads here</body></html>"
        info = client._extract_download_info(html)
        assert info is None

    def test_extract_pdf_from_download_page(self):
        """Test PDF URL extraction from download page."""
        client = LibGenClient()
        html = '<a href="https://download.example.com/file.pdf">Download</a>'
        url = client._extract_pdf_from_download_page(html)
        assert url == "https://download.example.com/file.pdf"

    def test_extract_pdf_from_download_page_get_button(self):
        """Test PDF URL extraction from GET button."""
        client = LibGenClient()
        html = '<a href="https://cdn.libgen.lc/ads.php?md5=abc">GET</a>'
        url = client._extract_pdf_from_download_page(html)
        assert url is not None

    def test_extract_pdf_from_download_page_not_found(self):
        """Test PDF URL extraction when no PDF found."""
        client = LibGenClient()
        html = "<html><body>No PDF link here</body></html>"
        url = client._extract_pdf_from_download_page(html)
        assert url is None

    def test_mirrors_list(self):
        """Test that mirrors lists are populated."""
        client = LibGenClient()
        assert len(client.SEARCH_MIRRORS) > 0
        assert len(client.DOWNLOAD_MIRRORS) > 0
        for mirror in client.SEARCH_MIRRORS:
            assert mirror.startswith("https://")


@pytest.mark.asyncio
class TestLibGenClientAsync:
    """Async tests for LibGenClient."""

    @pytest.mark.skip(reason="Requires network access to unofficial source")
    async def test_download_by_doi(self):
        """Test downloading by DOI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LibGenClient()
            output_path = Path(tmpdir) / "test.pdf"
            result = await client.download_by_doi("10.1145/3375633", output_path)
            if result:
                assert output_path.exists()
                assert result["source"] == "libgen"

    async def test_download_by_doi_invalid(self):
        """Test downloading with invalid DOI returns None gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LibGenClient(timeout=5.0, max_retries=1)
            output_path = Path(tmpdir) / "test.pdf"
            # This should return None, not raise an exception
            result = await client.download_by_doi(
                "10.9999/invalid/doi/does/not/exist", output_path
            )
            assert result is None

    @pytest.mark.skip(reason="Requires network access to unofficial source")
    async def test_download_by_title(self):
        """Test downloading by title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = LibGenClient()
            output_path = Path(tmpdir) / "test.pdf"
            result = await client.download_by_title(
                "Attention Is All You Need", output_path
            )
            if result:
                assert output_path.exists()
                assert result["source"] == "libgen"
