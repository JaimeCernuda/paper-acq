"""Sci-Hub client for downloading papers via scidownl library."""

import asyncio
import logging
import re
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import httpx


class ScihubClient:
    """Client for downloading papers from Sci-Hub.

    Uses the scidownl library when available, falls back to direct HTTP.
    Requires unofficial.disclaimer_accepted to be True in config.
    """

    # Known working Sci-Hub mirrors (updated regularly by community)
    MIRRORS = [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru",
    ]

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 2,
        proxy: str | None = None,
    ):
        """Initialize the Sci-Hub client.

        Args:
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts per mirror.
            proxy: Optional proxy URL (e.g., "socks5://127.0.0.1:1080").
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.proxy = proxy
        self._scidownl_available = self._check_scidownl()

    def _check_scidownl(self) -> bool:
        """Check if scidownl library is available."""
        try:
            from scidownl import scihub_download  # noqa: F401

            return True
        except ImportError:
            return False

    async def download_by_doi(
        self, doi: str, output_path: Path
    ) -> dict[str, Any] | None:
        """Download a paper by DOI.

        Args:
            doi: The DOI of the paper.
            output_path: Path to save the PDF.

        Returns:
            Dict with 'pdf_path' and 'source' if successful, None otherwise.
        """
        if self._scidownl_available:
            result = await self._download_with_scidownl(doi, "doi", output_path)
            if result:
                return result

        # Fallback to direct method
        return await self._download_direct(doi, output_path)

    async def download_by_title(
        self, title: str, output_path: Path
    ) -> dict[str, Any] | None:
        """Download a paper by title (less reliable).

        Args:
            title: The paper title.
            output_path: Path to save the PDF.

        Returns:
            Dict with 'pdf_path' and 'source' if successful, None otherwise.
        """
        if self._scidownl_available:
            return await self._download_with_scidownl(title, "title", output_path)
        return None  # Direct method only works with DOI

    async def _download_with_scidownl(
        self, identifier: str, paper_type: str, output_path: Path
    ) -> dict[str, Any] | None:
        """Download using scidownl library.

        Args:
            identifier: DOI, PMID, or title.
            paper_type: Type of identifier ("doi", "pmid", "title").
            output_path: Path to save the PDF.

        Returns:
            Result dict or None.
        """
        from scidownl import scihub_download

        try:
            # scidownl is synchronous, run in executor
            loop = asyncio.get_event_loop()

            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            def do_download():
                # Suppress scidownl's verbose loguru output
                # Capture stdout and stderr to prevent console spam
                captured_out = StringIO()
                captured_err = StringIO()

                # Also suppress loguru if present
                try:
                    import loguru
                    loguru.logger.disable("scidownl")
                except ImportError:
                    pass

                # Suppress standard logging from scidownl
                logging.getLogger("scidownl").setLevel(logging.CRITICAL)

                try:
                    with redirect_stdout(captured_out), redirect_stderr(captured_err):
                        scihub_download(
                            identifier,
                            paper_type=paper_type,
                            out=str(output_path),
                        )
                except Exception:
                    # Errors are handled below by checking if file exists
                    pass

                # Store captured output for debugging if needed
                self._last_output = captured_out.getvalue()
                self._last_errors = captured_err.getvalue()

                return output_path.exists()

            success = await loop.run_in_executor(None, do_download)

            if success and output_path.exists():
                # Verify it's a valid PDF
                content = output_path.read_bytes()
                if content.startswith(b"%PDF") and len(content) > 1000:
                    return {"pdf_path": str(output_path), "source": "scihub"}
                else:
                    # Invalid file, remove it
                    output_path.unlink(missing_ok=True)

        except Exception:
            # Silently fail - errors are logged at higher level
            pass

        return None

    async def _download_direct(
        self, doi: str, output_path: Path
    ) -> dict[str, Any] | None:
        """Download directly from Sci-Hub mirrors.

        Fallback when scidownl is not installed or fails.

        Args:
            doi: The DOI to download.
            output_path: Path to save the PDF.

        Returns:
            Result dict or None.
        """
        for mirror in self.MIRRORS:
            for attempt in range(self.max_retries):
                try:
                    result = await self._try_mirror(mirror, doi, output_path)
                    if result:
                        return result
                except Exception:
                    # Silently retry - errors logged at higher level
                    await asyncio.sleep(1)  # Brief delay between retries

        return None

    async def _try_mirror(
        self, mirror: str, doi: str, output_path: Path
    ) -> dict[str, Any] | None:
        """Try to download from a specific mirror.

        Args:
            mirror: The Sci-Hub mirror URL.
            doi: The DOI to download.
            output_path: Path to save the PDF.

        Returns:
            Result dict or None.
        """
        url = f"{mirror}/{doi}"

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            # First get the page to find PDF link
            response = await client.get(url)

            if response.status_code == 503:
                # Bot protection triggered
                return None

            if response.status_code == 404:
                # Paper not found on this mirror
                return None

            response.raise_for_status()

            # Extract PDF URL from page
            pdf_url = self._extract_pdf_url(response.text, mirror)
            if not pdf_url:
                return None

            # Download the PDF
            pdf_response = await client.get(pdf_url)
            pdf_response.raise_for_status()

            content = pdf_response.content
            if not content.startswith(b"%PDF") or len(content) < 1000:
                return None

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)

            return {"pdf_path": str(output_path), "source": "scihub"}

    def _extract_pdf_url(self, html: str, mirror: str) -> str | None:
        """Extract PDF URL from Sci-Hub page.

        Args:
            html: The HTML content.
            mirror: The mirror base URL.

        Returns:
            PDF URL or None.
        """
        # Pattern 1: iframe/embed src
        patterns = [
            r'<iframe[^>]+src="([^"]+\.pdf[^"]*)"',
            r'<embed[^>]+src="([^"]+\.pdf[^"]*)"',
            r'onclick="location\.href=\'([^\']+\.pdf[^\']*)\'"',
            r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>',
            # Sci-Hub specific patterns
            r'<iframe[^>]+src="([^"]+)"[^>]*id="pdf"',
            r'<embed[^>]+src="([^"]+)"[^>]*type="application/pdf"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                pdf_url = match.group(1)
                if pdf_url.startswith("//"):
                    pdf_url = "https:" + pdf_url
                elif pdf_url.startswith("/"):
                    pdf_url = mirror + pdf_url
                return pdf_url

        return None

    def is_available(self) -> bool:
        """Check if the client can attempt downloads.

        Returns:
            True (always can try direct method).
        """
        return True
