"""Unpaywall API client for open access PDF discovery."""

from typing import Any

import httpx


class UnpaywallClient:
    """Client for the Unpaywall API."""

    BASE_URL = "https://api.unpaywall.org/v2"

    def __init__(self, email: str):
        """Initialize the Unpaywall client.

        Args:
            email: Email required for API access.
        """
        self.email = email

    async def get_oa_location(self, doi: str) -> dict[str, Any] | None:
        """Get open access PDF URL for a DOI.

        Args:
            doi: The DOI to look up.

        Returns:
            Dict with PDF URL and metadata, or None if not found.
        """
        if not self.email:
            return None

        url = f"{self.BASE_URL}/{doi}"
        params = {"email": self.email}

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()

                # Check for OA PDF
                if data.get("is_oa") and data.get("best_oa_location"):
                    location = data["best_oa_location"]
                    return {
                        "pdf_url": location.get("url_for_pdf"),
                        "landing_page": location.get("url"),
                        "host_type": location.get("host_type"),
                        "license": location.get("license"),
                        "version": location.get("version"),
                    }

                # Check all OA locations as fallback
                oa_locations = data.get("oa_locations", [])
                for location in oa_locations:
                    pdf_url = location.get("url_for_pdf")
                    if pdf_url:
                        return {
                            "pdf_url": pdf_url,
                            "landing_page": location.get("url"),
                            "host_type": location.get("host_type"),
                            "license": location.get("license"),
                            "version": location.get("version"),
                        }

                return None
            except httpx.HTTPStatusError:
                return None
