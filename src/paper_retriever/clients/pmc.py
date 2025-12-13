"""PubMed Central API client for biomedical literature."""

import xml.etree.ElementTree as ET
from typing import Any

import httpx


class PMCClient:
    """Client for PubMed Central APIs."""

    IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
    OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
    EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: str | None = None, email: str | None = None):
        """Initialize the PMC client.

        Args:
            api_key: NCBI API key for higher rate limits.
            email: Email for identification.
        """
        self.api_key = api_key
        self.email = email
        self.delay = 0.1 if api_key else 0.34  # Respect rate limits

    async def doi_to_pmcid(self, doi: str) -> str | None:
        """Convert DOI to PMCID.

        Args:
            doi: The DOI to convert.

        Returns:
            PMCID or None if not found.
        """
        params: dict[str, Any] = {"ids": doi, "format": "json"}
        if self.api_key:
            params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(self.IDCONV_URL, params=params)
                response.raise_for_status()
                data = response.json()
                records = data.get("records", [])
                if records and "pmcid" in records[0]:
                    return records[0]["pmcid"]
            except httpx.HTTPStatusError:
                pass
        return None

    async def get_pdf_url(self, pmcid: str) -> str | None:
        """Get PDF URL for a PMCID.

        Args:
            pmcid: The PMCID to look up.

        Returns:
            PDF URL or None if not available.
        """
        params: dict[str, Any] = {"id": pmcid, "format": "pdf"}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(self.OA_URL, params=params)
                response.raise_for_status()

                # Parse XML response for PDF link
                root = ET.fromstring(response.text)

                # Check for errors
                error = root.find(".//error")
                if error is not None:
                    return None

                # Find PDF link
                link = root.find(".//link[@format='pdf']")
                if link is not None:
                    href = link.get("href")
                    # Convert FTP URLs to HTTPS if needed
                    if href and href.startswith("ftp://"):
                        href = href.replace("ftp://", "https://")
                    return href
            except (httpx.HTTPStatusError, ET.ParseError):
                pass
        return None

    async def search_by_title(
        self, title: str, max_results: int = 5
    ) -> list[dict[str, Any]]:
        """Search PMC by title.

        Args:
            title: The title to search for.
            max_results: Maximum number of results.

        Returns:
            List of search results with PMCIDs.
        """
        # First, search for IDs
        search_url = f"{self.EUTILS_BASE}/esearch.fcgi"
        params: dict[str, Any] = {
            "db": "pmc",
            "term": f'"{title}"[Title]',
            "retmax": max_results,
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(search_url, params=params)
                response.raise_for_status()
                data = response.json()
                id_list = data.get("esearchresult", {}).get("idlist", [])

                results = []
                for pmcid in id_list:
                    results.append({"pmcid": f"PMC{pmcid}"})
                return results
            except httpx.HTTPStatusError:
                return []
