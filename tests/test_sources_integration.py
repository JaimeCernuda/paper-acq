"""Integration tests for individual sources.

Each test uses a config that enables ONLY that source, testing it in isolation.
Run with: uv run pytest tests/test_sources_integration.py -v -s

These tests require network access and download actual PDFs.
"""

import asyncio
import shutil
from pathlib import Path

import pytest

from paper_retriever.config import Config
from paper_retriever.retriever import PaperRetriever, RetrievalStatus


# Test papers known to be available from each source
TEST_PAPERS = {
    "unpaywall": {
        # PLOS ONE paper - guaranteed open access
        "doi": "10.1371/journal.pone.0115069",
        "title": None,
    },
    "arxiv": {
        # Famous "Attention Is All You Need" paper
        "doi": None,
        "title": "Attention Is All You Need",
    },
    "pmc": {
        # Paper with PDF in PMC OA subset (PMC7314460)
        "doi": "10.1002/lio2.393",
        "title": None,
    },
    "biorxiv": {
        # Early SARS-CoV-2 paper on bioRxiv
        "doi": "10.1101/2020.01.22.915660",
        "title": None,
    },
    "semantic_scholar": {
        # Nature Communications paper - has OA PDF
        # Use CorpusID since DOI lookup sometimes fails
        "doi": "259307834",  # CorpusID format
        "title": "Lean-water hydrogel electrolyte for zinc ion batteries",
    },
    "institutional": {
        # IEEE paper (requires institutional access)
        "doi": "10.1109/Cluster48925.2021.00064",
        "title": "HFlow",
    },
}

CONFIGS_DIR = Path(__file__).parent / "configs"


# No automatic cleanup - tests may run on Windows where file locks are common
# Run manually: rm -rf downloads/test_*


class TestUnpaywallSource:
    """Test Unpaywall source in isolation."""

    @pytest.mark.asyncio
    async def test_unpaywall_download(self):
        """Test downloading an open access paper via Unpaywall."""
        config = Config.load(CONFIGS_DIR / "unpaywall_only.yaml")
        retriever = PaperRetriever(config)

        paper = TEST_PAPERS["unpaywall"]
        result = await retriever.retrieve(doi=paper["doi"])

        print(f"\nUnpaywall result: {result.status}")
        print(f"  Source: {result.source}")
        print(f"  Error: {result.error}")

        # Unpaywall availability varies - skip if not found
        if result.status != RetrievalStatus.SUCCESS:
            pytest.skip(f"Paper not in Unpaywall: {result.error}")
        assert result.source == "unpaywall"
        assert result.pdf_path and Path(result.pdf_path).exists()


class TestArxivSource:
    """Test arXiv source in isolation."""

    @pytest.mark.asyncio
    async def test_arxiv_download(self):
        """Test downloading a paper from arXiv."""
        config = Config.load(CONFIGS_DIR / "arxiv_only.yaml")
        retriever = PaperRetriever(config)

        paper = TEST_PAPERS["arxiv"]
        result = await retriever.retrieve(title=paper["title"])

        print(f"\narXiv result: {result.status}")
        print(f"  Source: {result.source}")
        print(f"  Error: {result.error}")

        assert result.status == RetrievalStatus.SUCCESS, f"Failed: {result.error}"
        assert result.source == "arxiv"
        assert result.pdf_path and Path(result.pdf_path).exists()


class TestPmcSource:
    """Test PubMed Central source in isolation."""

    @pytest.mark.asyncio
    async def test_pmc_download(self):
        """Test downloading a paper from PubMed Central."""
        config = Config.load(CONFIGS_DIR / "pmc_only.yaml")
        retriever = PaperRetriever(config)

        paper = TEST_PAPERS["pmc"]
        result = await retriever.retrieve(doi=paper["doi"])

        print(f"\nPMC result: {result.status}")
        print(f"  Source: {result.source}")
        print(f"  Error: {result.error}")

        # PMC availability varies - skip if not found
        if result.status != RetrievalStatus.SUCCESS:
            pytest.skip(f"Paper not in PMC: {result.error}")
        assert result.source == "pmc"
        assert result.pdf_path and Path(result.pdf_path).exists()


class TestBiorxivSource:
    """Test bioRxiv source in isolation."""

    @pytest.mark.asyncio
    async def test_biorxiv_download(self):
        """Test downloading a preprint from bioRxiv."""
        config = Config.load(CONFIGS_DIR / "biorxiv_only.yaml")
        retriever = PaperRetriever(config)

        paper = TEST_PAPERS["biorxiv"]
        result = await retriever.retrieve(doi=paper["doi"])

        print(f"\nbioRxiv result: {result.status}")
        print(f"  Source: {result.source}")
        print(f"  Error: {result.error}")

        # bioRxiv may block or paper may not exist - skip if not found
        if result.status != RetrievalStatus.SUCCESS:
            pytest.skip(f"Paper not available from bioRxiv: {result.error}")
        assert result.source == "biorxiv"
        assert result.pdf_path and Path(result.pdf_path).exists()


class TestSemanticScholarSource:
    """Test Semantic Scholar source in isolation."""

    @pytest.mark.asyncio
    async def test_semantic_scholar_download(self):
        """Test downloading a paper via Semantic Scholar."""
        config = Config.load(CONFIGS_DIR / "semantic_scholar_only.yaml")
        retriever = PaperRetriever(config)

        paper = TEST_PAPERS["semantic_scholar"]
        result = await retriever.retrieve(doi=paper["doi"])

        print(f"\nSemantic Scholar result: {result.status}")
        print(f"  Source: {result.source}")
        print(f"  Error: {result.error}")

        # Semantic Scholar may not always have OA PDFs
        if result.status == RetrievalStatus.SUCCESS:
            assert result.source == "semantic_scholar"
            assert result.pdf_path and Path(result.pdf_path).exists()
        else:
            pytest.skip(f"Semantic Scholar had no OA PDF: {result.error}")


class TestInstitutionalSource:
    """Test institutional access source in isolation."""

    @pytest.mark.asyncio
    async def test_institutional_download(self):
        """Test downloading a paper via institutional access (IEEE)."""
        config = Config.load(CONFIGS_DIR / "institutional_only.yaml")

        # Check if cookies exist
        cookies_file = Path(config.institutional.get("cookies_file", ".institutional_cookies.pkl"))
        if not cookies_file.exists():
            pytest.skip("No institutional cookies - run 'paper-retriever auth' first")

        retriever = PaperRetriever(config)

        paper = TEST_PAPERS["institutional"]
        result = await retriever.retrieve(doi=paper["doi"])

        print(f"\nInstitutional result: {result.status}")
        print(f"  Source: {result.source}")
        print(f"  Error: {result.error}")

        assert result.status == RetrievalStatus.SUCCESS, f"Failed: {result.error}"
        assert result.source == "institutional"
        assert result.pdf_path and Path(result.pdf_path).exists()


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])
