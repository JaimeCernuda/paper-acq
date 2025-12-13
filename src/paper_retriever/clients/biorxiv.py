"""bioRxiv/medRxiv API client for preprint access."""

from typing import Any

import httpx


class BioRxivClient:
    """Client for bioRxiv and medRxiv APIs."""

    BIORXIV_API = "https://api.biorxiv.org/details"
    MEDRXIV_API = "https://api.medrxiv.org/details"

    async def get_preprint(self, doi: str) -> dict[str, Any] | None:
        """Get preprint metadata and PDF URL.

        Args:
            doi: The DOI to look up. Must start with 10.1101 for bioRxiv/medRxiv.

        Returns:
            Dict with preprint info and PDF URL, or None if not found.
        """
        # bioRxiv/medRxiv DOIs start with 10.1101
        if not doi.startswith("10.1101"):
            return None

        async with httpx.AsyncClient(timeout=30) as client:
            for server, api in [
                ("biorxiv", self.BIORXIV_API),
                ("medrxiv", self.MEDRXIV_API),
            ]:
                try:
                    url = f"{api}/{server}/{doi}/na/json"
                    response = await client.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("collection"):
                            item = data["collection"][0]
                            return {
                                "title": item.get("title"),
                                "doi": doi,
                                "pdf_url": f"https://www.{server}.org/content/{doi}.full.pdf",
                                "server": server,
                                "authors": item.get("authors"),
                                "date": item.get("date"),
                                "category": item.get("category"),
                            }
                except httpx.HTTPStatusError:
                    continue

        return None

    async def search_by_date_range(
        self,
        server: str,
        start_date: str,
        end_date: str,
        cursor: int = 0,
    ) -> dict[str, Any]:
        """Search for preprints by date range.

        Args:
            server: Either 'biorxiv' or 'medrxiv'.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            cursor: Pagination cursor.

        Returns:
            Dict with collection of results and message info.
        """
        base_url = self.BIORXIV_API if server == "biorxiv" else self.MEDRXIV_API
        url = f"{base_url}/{server}/{start_date}/{end_date}/{cursor}/json"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError:
                return {"collection": [], "messages": []}
