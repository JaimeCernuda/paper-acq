"""CrossRef API client for metadata resolution."""

from typing import Any

import httpx


class CrossRefClient:
    """Client for the CrossRef API."""

    BASE_URL = "https://api.crossref.org"

    def __init__(self, email: str):
        """Initialize the CrossRef client.

        Args:
            email: Email for polite pool access.
        """
        self.email = email
        self.headers = {"User-Agent": f"PaperRetriever/1.0 (mailto:{email})"}

    async def get_work(self, doi: str) -> dict[str, Any] | None:
        """Get metadata for a DOI.

        Args:
            doi: The DOI to look up.

        Returns:
            Paper metadata dict or None if not found.
        """
        # URL-encode the DOI for the path
        url = f"{self.BASE_URL}/works/{doi}"
        params = {"mailto": self.email} if self.email else {}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json().get("message")
            except httpx.HTTPStatusError:
                return None

    async def search_title(self, title: str, rows: int = 5) -> list[dict[str, Any]]:
        """Search for papers by title.

        Args:
            title: The title to search for.
            rows: Maximum number of results.

        Returns:
            List of paper metadata dicts.
        """
        url = f"{self.BASE_URL}/works"
        params = {
            "query.title": title,
            "rows": rows,
        }
        if self.email:
            params["mailto"] = self.email

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json().get("message", {}).get("items", [])
            except httpx.HTTPStatusError:
                return []

    @staticmethod
    def extract_metadata(work: dict[str, Any]) -> dict[str, Any]:
        """Extract useful metadata from a CrossRef work response.

        Args:
            work: Raw CrossRef work response.

        Returns:
            Extracted metadata dict.
        """
        # Extract authors
        authors = work.get("author", [])
        first_author = authors[0].get("family", "Unknown") if authors else "Unknown"

        # Extract title
        titles = work.get("title", [])
        title = titles[0] if titles else "untitled"

        # Extract year
        date_parts = (
            work.get("published-print", {}).get("date-parts", [[None]])
            or work.get("published-online", {}).get("date-parts", [[None]])
            or work.get("created", {}).get("date-parts", [[None]])
        )
        year = date_parts[0][0] if date_parts and date_parts[0] else None

        # Extract container/journal
        container = work.get("container-title", [])
        journal = container[0] if container else None

        # Extract links that might be PDFs
        links = work.get("link", [])
        pdf_links = [
            link.get("URL")
            for link in links
            if link.get("content-type") == "application/pdf"
        ]

        return {
            "doi": work.get("DOI"),
            "title": title,
            "first_author": first_author,
            "authors": authors,
            "year": year,
            "journal": journal,
            "pdf_links": pdf_links,
            "is_referenced_by_count": work.get("is-referenced-by-count"),
        }
