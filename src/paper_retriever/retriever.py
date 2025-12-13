"""Main paper retrieval orchestration."""

import asyncio
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from paper_retriever.config import Config
from paper_retriever.rate_limiter import RateLimiter
from paper_retriever.clients.crossref import CrossRefClient
from paper_retriever.clients.unpaywall import UnpaywallClient
from paper_retriever.clients.arxiv_client import ArxivClient
from paper_retriever.clients.pmc import PMCClient
from paper_retriever.clients.biorxiv import BioRxivClient
from paper_retriever.clients.semantic_scholar import SemanticScholarClient
from paper_retriever.clients.institutional import InstitutionalAccessClient
from paper_retriever.clients.web_search import WebSearchClient


class RetrievalStatus(Enum):
    """Status of a retrieval attempt."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class RetrievalResult:
    """Result of a paper retrieval attempt."""

    doi: str | None
    title: str
    status: RetrievalStatus
    source: str | None = None
    pdf_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class PaperRetriever:
    """Main orchestrator for paper PDF retrieval."""

    def __init__(self, config: Config):
        """Initialize the paper retriever.

        Args:
            config: Configuration object.
        """
        self.config = config
        self.clients = self._init_clients()
        self.rate_limiter = RateLimiter(config.rate_limits)

    def _init_clients(self) -> dict[str, Any]:
        """Initialize all API clients."""
        clients: dict[str, Any] = {
            "crossref": CrossRefClient(self.config.email),
            "unpaywall": UnpaywallClient(self.config.email),
            "arxiv": ArxivClient(),
            "pmc": PMCClient(
                api_key=self.config.api_keys.get("ncbi"),
                email=self.config.email,
            ),
            "biorxiv": BioRxivClient(),
            "semantic_scholar": SemanticScholarClient(
                api_key=self.config.api_keys.get("semantic_scholar"),
            ),
        }

        # Initialize institutional client if configured
        inst_config = self.config.institutional
        if inst_config.get("enabled"):
            clients["institutional"] = InstitutionalAccessClient(
                proxy_url=inst_config.get("proxy_url"),
                vpn_enabled=inst_config.get("vpn_enabled", False),
                vpn_script=inst_config.get("vpn_script"),
                cookies_file=inst_config.get("cookies_file", ".institutional_cookies.pkl"),
                download_dir=self.config.download.get("output_dir", "./downloads"),
            )

        # Initialize web search client
        if self.config.is_source_enabled("web_search"):
            clients["web_search"] = WebSearchClient(enabled=True)

        return clients

    async def retrieve(
        self, doi: str | None = None, title: str | None = None
    ) -> RetrievalResult:
        """Retrieve PDF for a paper.

        Args:
            doi: Paper DOI.
            title: Paper title.

        Returns:
            RetrievalResult with status and file path.
        """
        if not doi and not title:
            return RetrievalResult(
                doi=None,
                title="",
                status=RetrievalStatus.ERROR,
                error="Must provide DOI or title",
            )

        # Resolve metadata if needed
        metadata = await self._resolve_metadata(doi, title)
        resolved_doi = metadata.get("doi") if metadata else doi
        resolved_title = metadata.get("title") if metadata else title

        # Check if already downloaded
        output_path = self._get_output_path(metadata or {"doi": doi, "title": title})
        if self.config.download.get("skip_existing") and output_path.exists():
            return RetrievalResult(
                doi=resolved_doi,
                title=resolved_title or "",
                status=RetrievalStatus.SKIPPED,
                source="cached",
                pdf_path=str(output_path),
                metadata=metadata,
            )

        # Try sources in priority order
        sources = self.config.get_sorted_sources()

        for source_name in sources:
            if not self.config.is_source_enabled(source_name):
                continue

            # Skip unofficial sources if not enabled
            if source_name in ("scihub", "libgen") and not self.config.is_unofficial_enabled():
                continue

            await self.rate_limiter.wait(source_name)

            result = await self._try_source(
                source_name,
                resolved_doi,
                resolved_title or title or "",
                metadata or {},
                output_path,
            )
            if result and result.status == RetrievalStatus.SUCCESS:
                result.metadata = metadata
                return result

        return RetrievalResult(
            doi=resolved_doi,
            title=resolved_title or title or "",
            status=RetrievalStatus.NOT_FOUND,
            error="PDF not found in any source",
            metadata=metadata,
        )

    async def _resolve_metadata(
        self, doi: str | None = None, title: str | None = None
    ) -> dict[str, Any] | None:
        """Resolve full metadata from DOI or title.

        Args:
            doi: Paper DOI.
            title: Paper title.

        Returns:
            Metadata dict or None.
        """
        if doi:
            try:
                await self.rate_limiter.wait("crossref")
                work = await self.clients["crossref"].get_work(doi)
                if work:
                    return CrossRefClient.extract_metadata(work)
            except Exception:
                pass

        if title:
            try:
                await self.rate_limiter.wait("crossref")
                results = await self.clients["crossref"].search_title(title)
                if results:
                    # Find best matching title
                    best_match = self._find_best_title_match(title, results)
                    if best_match:
                        return CrossRefClient.extract_metadata(best_match)
            except Exception:
                pass

        # Return basic metadata if nothing found
        return {"doi": doi, "title": title}

    def _find_best_title_match(
        self, query_title: str, results: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Find the best matching result for a title query.

        Args:
            query_title: The title searched for.
            results: List of CrossRef results.

        Returns:
            Best matching result or None.
        """
        query_normalized = self._normalize_title(query_title)

        best_match = None
        best_score = 0

        for result in results:
            titles = result.get("title", [])
            if not titles:
                continue

            result_title = titles[0] if isinstance(titles, list) else titles
            result_normalized = self._normalize_title(result_title)

            # Simple similarity score based on common words
            query_words = set(query_normalized.split())
            result_words = set(result_normalized.split())
            common = len(query_words & result_words)
            total = len(query_words | result_words)
            score = common / total if total > 0 else 0

            if score > best_score:
                best_score = score
                best_match = result

        # Require at least 50% similarity
        return best_match if best_score >= 0.5 else None

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize a title for comparison."""
        # Remove punctuation and lowercase
        normalized = re.sub(r"[^\w\s]", "", title.lower())
        # Remove extra whitespace
        return " ".join(normalized.split())

    async def _try_source(
        self,
        source: str,
        doi: str | None,
        title: str,
        metadata: dict[str, Any],
        output_path: Path,
    ) -> RetrievalResult | None:
        """Try to retrieve PDF from a specific source.

        Args:
            source: Source name.
            doi: Paper DOI.
            title: Paper title.
            metadata: Paper metadata.
            output_path: Path to save PDF.

        Returns:
            RetrievalResult or None if source doesn't have the paper.
        """
        client = self.clients.get(source)
        if not client:
            return None

        try:
            if source == "unpaywall" and doi:
                result = await client.get_oa_location(doi)
                if result and result.get("pdf_url"):
                    if await self._download_pdf(result["pdf_url"], output_path):
                        return RetrievalResult(
                            doi=doi,
                            title=title,
                            status=RetrievalStatus.SUCCESS,
                            source="unpaywall",
                            pdf_path=str(output_path),
                        )

            elif source == "arxiv":
                # Check if arXiv paper by DOI
                if doi and "arxiv" in doi.lower():
                    result = await client.search_by_doi(doi)
                    if result:
                        pdf_url = client.get_pdf_url(result)
                        if await self._download_pdf(pdf_url, output_path):
                            return RetrievalResult(
                                doi=doi,
                                title=title,
                                status=RetrievalStatus.SUCCESS,
                                source="arxiv",
                                pdf_path=str(output_path),
                            )

                # Search by title as fallback
                results = await client.search_by_title(title)
                if results:
                    # Verify title match
                    for result in results:
                        if self._titles_match(title, result.title):
                            pdf_url = client.get_pdf_url(result)
                            if await self._download_pdf(pdf_url, output_path):
                                return RetrievalResult(
                                    doi=doi,
                                    title=title,
                                    status=RetrievalStatus.SUCCESS,
                                    source="arxiv",
                                    pdf_path=str(output_path),
                                )

            elif source == "pmc" and doi:
                pmcid = await client.doi_to_pmcid(doi)
                if pmcid:
                    pdf_url = await client.get_pdf_url(pmcid)
                    if pdf_url and await self._download_pdf(pdf_url, output_path):
                        return RetrievalResult(
                            doi=doi,
                            title=title,
                            status=RetrievalStatus.SUCCESS,
                            source="pmc",
                            pdf_path=str(output_path),
                        )

            elif source == "biorxiv" and doi:
                result = await client.get_preprint(doi)
                if result and result.get("pdf_url"):
                    if await self._download_pdf(result["pdf_url"], output_path):
                        return RetrievalResult(
                            doi=doi,
                            title=title,
                            status=RetrievalStatus.SUCCESS,
                            source=result.get("server", "biorxiv"),
                            pdf_path=str(output_path),
                        )

            elif source == "semantic_scholar":
                result = None
                if doi:
                    result = await client.get_paper(doi)

                if not result or not result.get("pdf_url"):
                    # Search by title
                    results = await client.search_title(title)
                    for r in results:
                        if r.get("openAccessPdf") and self._titles_match(
                            title, r.get("title", "")
                        ):
                            result = {
                                "pdf_url": r["openAccessPdf"].get("url"),
                                "title": r.get("title"),
                            }
                            break

                if result and result.get("pdf_url"):
                    if await self._download_pdf(result["pdf_url"], output_path):
                        return RetrievalResult(
                            doi=doi,
                            title=title,
                            status=RetrievalStatus.SUCCESS,
                            source="semantic_scholar",
                            pdf_path=str(output_path),
                        )

            elif source == "institutional" and doi:
                # Institutional access via EZProxy
                if not client.is_authenticated():
                    # Skip if not authenticated (user needs to run auth first)
                    pass
                else:
                    if await client.download_pdf(doi, output_path):
                        return RetrievalResult(
                            doi=doi,
                            title=title,
                            status=RetrievalStatus.SUCCESS,
                            source="institutional",
                            pdf_path=str(output_path),
                        )

            elif source == "web_search":
                # Web search fallback using Claude Agent SDK
                authors = metadata.get("authors", [])
                author_names = [
                    a.get("family", "") or a.get("name", "")
                    for a in authors
                    if isinstance(a, dict)
                ]
                result = await client.search_for_pdf(
                    title=title,
                    doi=doi,
                    authors=author_names,
                )
                if result and result.get("pdf_url"):
                    if await self._download_pdf(result["pdf_url"], output_path):
                        return RetrievalResult(
                            doi=doi,
                            title=title,
                            status=RetrievalStatus.SUCCESS,
                            source="web_search",
                            pdf_path=str(output_path),
                        )

        except Exception as e:
            # Log but don't fail - try next source
            print(f"Error with {source}: {e}")

        return None

    def _titles_match(self, title1: str, title2: str) -> bool:
        """Check if two titles are similar enough to be the same paper.

        Args:
            title1: First title.
            title2: Second title.

        Returns:
            True if titles match.
        """
        norm1 = self._normalize_title(title1)
        norm2 = self._normalize_title(title2)

        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return False

        common = len(words1 & words2)
        total = len(words1 | words2)
        similarity = common / total

        return similarity >= 0.7

    async def _download_pdf(self, url: str, output_path: Path) -> bool:
        """Download PDF from URL.

        Args:
            url: URL to download from.
            output_path: Path to save the file.

        Returns:
            True if download successful.
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            async with httpx.AsyncClient(
                follow_redirects=True, timeout=60
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Verify it's actually a PDF
                content = response.content
                if len(content) < 1000:
                    return False

                # Check for PDF magic bytes
                if not content.startswith(b"%PDF"):
                    # Some servers return HTML instead of PDF
                    return False

                output_path.write_bytes(content)
                return True

        except Exception as e:
            print(f"Download failed from {url}: {e}")
            return False

    def _get_output_path(self, metadata: dict[str, Any]) -> Path:
        """Generate output path for PDF.

        Args:
            metadata: Paper metadata.

        Returns:
            Output file path.
        """
        base_dir = Path(self.config.download.get("output_dir", "./downloads"))

        # Extract filename components
        first_author = metadata.get("first_author", "Unknown")
        year = metadata.get("year", "")
        title = metadata.get("title") or "untitled"

        if isinstance(title, list):
            title = title[0] if title else "untitled"

        # Ensure title is a string
        if title is None:
            title = "untitled"

        # Sanitize title
        max_len = self.config.download.get("max_title_length", 50)
        title_short = re.sub(r"[^\w\s-]", "", str(title))[:max_len]

        # Build filename
        parts = []
        if first_author and first_author != "Unknown":
            parts.append(re.sub(r"[^\w]", "", first_author))
        if year:
            parts.append(str(year))
        if title_short:
            parts.append(title_short.strip())

        filename = "_".join(parts) if parts else "paper"
        filename = re.sub(r"\s+", "_", filename)
        filename = f"{filename}.pdf"

        return base_dir / filename


async def batch_retrieve(
    retriever: PaperRetriever,
    papers: list[dict[str, str | None]],
    max_concurrent: int = 3,
) -> list[RetrievalResult]:
    """Batch retrieve papers with concurrency control.

    Args:
        retriever: PaperRetriever instance.
        papers: List of dicts with 'doi' and/or 'title' keys.
        max_concurrent: Maximum concurrent retrievals.

    Returns:
        List of RetrievalResults.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def retrieve_with_semaphore(paper: dict[str, str | None]) -> RetrievalResult:
        async with semaphore:
            return await retriever.retrieve(
                doi=paper.get("doi"),
                title=paper.get("title"),
            )

    tasks = [retrieve_with_semaphore(p) for p in papers]
    return await asyncio.gather(*tasks)
