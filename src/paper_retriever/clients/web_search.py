"""Web search fallback using Claude Agent SDK."""

import re
from typing import Any


class WebSearchClient:
    """Client for searching the web for paper PDFs using Claude Agent SDK.

    This is a fallback option when other sources don't have the paper.
    Uses Claude's web search capabilities to find author websites,
    institutional repositories, or other legal sources.
    """

    def __init__(self, enabled: bool = True):
        """Initialize the web search client.

        Args:
            enabled: Whether web search is enabled
        """
        self.enabled = enabled
        self._sdk_available = self._check_sdk_available()

    def _check_sdk_available(self) -> bool:
        """Check if Claude Agent SDK is available."""
        try:
            from claude_code_sdk import query  # noqa: F401

            return True
        except ImportError:
            return False

    async def search_for_pdf(
        self, title: str, doi: str | None = None, authors: list[str] | None = None
    ) -> dict[str, Any] | None:
        """Search the web for a PDF of the paper.

        Uses Claude Agent SDK to intelligently search for:
        - Author's personal/academic websites
        - Institutional repositories
        - ResearchGate or Academia.edu
        - Conference proceedings websites
        - Preprint servers

        Args:
            title: Paper title
            doi: Optional DOI
            authors: Optional list of author names

        Returns:
            Dict with 'pdf_url' and 'source' if found, None otherwise
        """
        if not self.enabled:
            return None

        if not self._sdk_available:
            print(
                "Claude Agent SDK not available. "
                "Install with: pip install claude-code-sdk"
            )
            return None

        from claude_code_sdk import query, ClaudeCodeOptions

        # Build search prompt
        author_str = ", ".join(authors[:3]) if authors else "Unknown authors"
        search_prompt = f"""Find a freely accessible PDF for this academic paper:

Title: {title}
{"DOI: " + doi if doi else ""}
Authors: {author_str}

Search for legal, freely accessible copies on:
1. Author's personal or academic institution website
2. Institutional repositories (university archives)
3. ResearchGate or Academia.edu (public copies)
4. Conference proceedings websites
5. Preprint servers (arXiv, SSRN, etc.)

IMPORTANT: Only find legal, freely accessible copies. Do NOT suggest:
- Sci-Hub or Library Genesis
- Paid access or subscription links
- Links that require login

If you find a direct PDF link, return ONLY the URL on a single line.
If you cannot find a free legal copy, respond with: NOT_FOUND"""

        try:
            result = await query(
                prompt=search_prompt,
                options=ClaudeCodeOptions(
                    allowed_tools=["WebSearch", "WebFetch"],
                    permission_mode="auto",
                    max_turns=5,
                ),
            )

            # Process the result
            response_text = ""
            for message in result:
                if hasattr(message, "content"):
                    if isinstance(message.content, str):
                        response_text += message.content
                    elif isinstance(message.content, list):
                        for block in message.content:
                            if hasattr(block, "text"):
                                response_text += block.text

            # Extract PDF URL from response
            if "NOT_FOUND" in response_text.upper():
                return None

            # Look for PDF URLs in the response
            pdf_urls = re.findall(
                r"https?://[^\s<>\"']+\.pdf(?:\?[^\s<>\"']*)?", response_text, re.I
            )

            if pdf_urls:
                return {"pdf_url": pdf_urls[0], "source": "web_search"}

            # Also look for URLs that might be PDF downloads
            all_urls = re.findall(r"https?://[^\s<>\"']+", response_text)
            for url in all_urls:
                if any(
                    x in url.lower()
                    for x in ["download", "pdf", "fulltext", "full-text"]
                ):
                    return {"pdf_url": url, "source": "web_search"}

            return None

        except Exception as e:
            print(f"Web search failed: {e}")
            return None

    def is_available(self) -> bool:
        """Check if web search is available and enabled.

        Returns:
            True if enabled and SDK is available
        """
        return self.enabled and self._sdk_available
