"""Logging for paper retrieval operations."""

import re
import sys
from datetime import datetime
from pathlib import Path


class RetrievalLogger:
    """Handles console output and per-paper log files.

    Provides clear visibility into which sources are being tried
    and why they succeed or fail.
    """

    def __init__(
        self,
        output_dir: Path | str,
        doi: str | None = None,
        title: str | None = None,
        console_enabled: bool = True,
    ):
        """Initialize the logger.

        Args:
            output_dir: Directory for log files
            doi: Paper DOI (used for log filename)
            title: Paper title (fallback for log filename)
            console_enabled: Whether to print to console
        """
        self.output_dir = Path(output_dir)
        self.doi = doi
        self.title = title
        self.console_enabled = console_enabled
        self._log_buffer: list[str] = []
        self._started = datetime.now()

        # Create log filename from DOI or title
        identifier = doi or title or "unknown"
        safe_name = self._sanitize_filename(identifier)
        self.log_file = self.output_dir / f"{safe_name}.log"

        # Write header to log
        self._write_header()

    def _sanitize_filename(self, name: str) -> str:
        """Convert DOI or title to safe filename."""
        # Replace common problematic characters
        safe = re.sub(r"[/\\:*?\"<>|]", "_", name)
        # Collapse multiple underscores
        safe = re.sub(r"_+", "_", safe)
        # Limit length
        return safe[:100]

    def _write_header(self) -> None:
        """Write log file header."""
        lines = [
            "=" * 50,
            "Paper Retrieval Log",
            "=" * 50,
            f"DOI: {self.doi or 'N/A'}",
            f"Title: {self.title or 'N/A'}",
            f"Started: {self._started.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for line in lines:
            self._log_to_file(line)

    def header(self, doi: str | None, title: str | None, year: str | None = None) -> None:
        """Print retrieval header to console."""
        self.doi = doi
        self.title = title

        if self.console_enabled:
            self._safe_print(f"\nRetrieving: {doi or 'N/A'}")
            if title:
                year_str = f" ({year})" if year else ""
                self._safe_print(f"  Title: \"{title}\"{year_str}")
            print()

    def _safe_print(self, text: str) -> None:
        """Print text, replacing unencodable characters."""
        try:
            print(text)
        except UnicodeEncodeError:
            # Replace non-ASCII characters for Windows console
            print(text.encode("ascii", errors="replace").decode("ascii"))

    def source_start(self, index: int, total: int, source: str) -> None:
        """Log that we're starting to try a source.

        Args:
            index: Current source number (1-based)
            total: Total number of sources to try
            source: Source name
        """
        msg = f"[{index}/{total}] {source}: checking..."
        self._log_to_file(f"\n[{source.upper()}] Starting...")
        if self.console_enabled:
            # Print without newline, will be updated by source_result
            print(f"[{index}/{total}] {source}: ", end="", flush=True)

    def source_result(
        self,
        index: int,
        total: int,
        source: str,
        success: bool,
        reason: str,
        path: str | None = None,
    ) -> None:
        """Log the result of trying a source.

        Args:
            index: Current source number (1-based)
            total: Total number of sources to try
            source: Source name
            success: Whether the source succeeded
            reason: Human-readable reason for result
            path: Path to downloaded file (if success)
        """
        if success:
            status = "SUCCESS"
            if path:
                msg = f"SUCCESS -> {path}"
            else:
                msg = "SUCCESS"
        else:
            status = "not found"
            msg = f"not found ({reason})"

        self._log_to_file(f"  Result: {status} - {reason}")

        if self.console_enabled:
            # Complete the line started by source_start
            print(msg)

    def detail(self, message: str) -> None:
        """Log a detail message (file only, not console)."""
        self._log_to_file(f"  {message}")

    def error(self, source: str, error: str) -> None:
        """Log an error for a source."""
        self._log_to_file(f"  ERROR: {error}")

    def final_result(self, success: bool, source: str | None = None, path: str | None = None) -> None:
        """Log the final result.

        Args:
            success: Whether retrieval succeeded
            source: Which source succeeded (if any)
            path: Path to downloaded file (if success)
        """
        if success:
            self._log_to_file(f"\n{'=' * 50}")
            self._log_to_file(f"Completed: SUCCESS via {source}")
            self._log_to_file(f"File: {path}")
            # Flush log to disk (stays in output_dir for successful downloads)
            self._flush_log()
        else:
            self._log_to_file(f"\n{'=' * 50}")
            self._log_to_file("Completed: FAILED - no source had PDF")
            # Flush log to disk, then move to fail directory
            self._flush_log()
            self._move_to_fail_dir()

            if self.console_enabled:
                print(f"\nLog saved: {self.log_file}")

    def _log_to_file(self, message: str) -> None:
        """Add message to log buffer."""
        self._log_buffer.append(message)

    def _flush_log(self) -> None:
        """Write buffered log to disk."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write("\n".join(self._log_buffer))
        except Exception as e:
            if self.console_enabled:
                print(f"Warning: Could not write log file: {e}", file=sys.stderr)

    def _move_to_fail_dir(self) -> None:
        """Move log file to fail subdirectory for failed retrievals."""
        try:
            fail_dir = self.output_dir / "fail"
            fail_dir.mkdir(parents=True, exist_ok=True)
            new_path = fail_dir / self.log_file.name
            if self.log_file.exists():
                # Remove existing file if present (from previous run)
                if new_path.exists():
                    new_path.unlink()
                self.log_file.rename(new_path)
                self.log_file = new_path
        except Exception as e:
            if self.console_enabled:
                print(f"Warning: Could not move log to fail dir: {e}", file=sys.stderr)

    def capture_output(self, output: str, source: str) -> None:
        """Capture verbose output from a library (log file only).

        Args:
            output: The captured output
            source: Which source/library produced it
        """
        if output.strip():
            self._log_to_file(f"\n  --- Captured {source} output ---")
            for line in output.strip().split("\n"):
                self._log_to_file(f"  | {line}")
            self._log_to_file(f"  --- End {source} output ---")
