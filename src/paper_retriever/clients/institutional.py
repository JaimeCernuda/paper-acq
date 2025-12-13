"""Institutional access client using EZProxy and Selenium."""

import pickle
import re
import time
from pathlib import Path
from typing import Any

import httpx


class InstitutionalAccessClient:
    """Client for accessing papers through institutional proxy (EZProxy).

    Supports two modes:
    1. VPN mode: When connected to institutional VPN, direct access works
    2. EZProxy mode: Uses proxy URL rewriting with Selenium authentication
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        vpn_enabled: bool = False,
        cookies_file: str = ".institutional_cookies.pkl",
        download_dir: str = "./downloads",
    ):
        """Initialize the institutional access client.

        Args:
            proxy_url: EZProxy URL (e.g., "https://ezproxy.gl.iit.edu/login?url=")
            vpn_enabled: If True, assume VPN is connected and use direct access
            cookies_file: Path to save/load authentication cookies
            download_dir: Directory to save downloaded PDFs
        """
        self.proxy_url = proxy_url
        self.vpn_enabled = vpn_enabled
        self.cookies_file = Path(cookies_file)
        self.download_dir = Path(download_dir)
        self._cookies: dict[str, str] = {}
        self._authenticated = False

    def get_proxied_url(self, url: str) -> str:
        """Convert a URL to a proxied URL.

        Args:
            url: Original URL (e.g., DOI URL or publisher URL)

        Returns:
            Proxied URL if proxy is configured, otherwise original URL
        """
        if self.vpn_enabled:
            return url

        if self.proxy_url:
            return f"{self.proxy_url}{url}"

        return url

    def doi_to_proxied_url(self, doi: str) -> str:
        """Convert a DOI to a proxied publisher URL.

        Args:
            doi: The DOI to convert

        Returns:
            Proxied URL for the DOI
        """
        doi_url = f"https://doi.org/{doi}"
        return self.get_proxied_url(doi_url)

    def load_cookies(self) -> bool:
        """Load previously saved authentication cookies.

        Returns:
            True if cookies were loaded successfully
        """
        if not self.cookies_file.exists():
            return False

        try:
            with open(self.cookies_file, "rb") as f:
                self._cookies = pickle.load(f)
            self._authenticated = True
            return True
        except (pickle.PickleError, EOFError):
            return False

    def save_cookies(self) -> None:
        """Save authentication cookies for reuse."""
        with open(self.cookies_file, "wb") as f:
            pickle.dump(self._cookies, f)

    def authenticate_interactive(self) -> bool:
        """Authenticate interactively using Selenium.

        Opens a browser window for the user to complete Shibboleth/SAML login.

        Returns:
            True if authentication was successful

        Raises:
            ImportError: If selenium is not installed
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
        except ImportError:
            raise ImportError(
                "Selenium is required for interactive authentication. "
                "Install with: pip install selenium webdriver-manager"
            )

        if not self.proxy_url:
            print("Error: proxy_url must be configured for authentication")
            return False

        # Try to use webdriver-manager if available
        try:
            from webdriver_manager.chrome import ChromeDriverManager

            service = Service(ChromeDriverManager().install())
        except ImportError:
            service = None

        options = Options()
        options.add_argument("--start-maximized")

        if service:
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)

        try:
            # Navigate to proxy login with a test URL
            test_url = self.get_proxied_url("https://ieeexplore.ieee.org")
            driver.get(test_url)

            print("\n" + "=" * 60)
            print("INSTITUTIONAL LOGIN REQUIRED")
            print("=" * 60)
            print("\nA browser window has opened for authentication.")
            print("Please complete the login process (Shibboleth/SAML).")
            print("\nPress Enter here once you're logged in and see")
            print("the publisher's website (e.g., IEEE Xplore)...")
            print("=" * 60)
            input()

            # Extract cookies from Selenium
            selenium_cookies = driver.get_cookies()
            self._cookies = {}

            for cookie in selenium_cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    self._cookies[name] = value

            # Save cookies for reuse
            self.save_cookies()
            self._authenticated = True

            print("\nAuthentication successful! Cookies saved.")
            return True

        except Exception as e:
            print(f"\nAuthentication failed: {e}")
            return False

        finally:
            driver.quit()

    async def download_pdf(self, doi: str, output_path: Path) -> bool:
        """Download a PDF using institutional access.

        Args:
            doi: The DOI of the paper
            output_path: Path to save the PDF

        Returns:
            True if download was successful
        """
        # Ensure we have cookies loaded
        if not self._authenticated and not self.vpn_enabled:
            if not self.load_cookies():
                print("Not authenticated. Run authenticate_interactive() first.")
                return False

        # Build the proxied URL
        url = self.doi_to_proxied_url(doi)

        # Create httpx client with cookies
        cookies = httpx.Cookies()
        for name, value in self._cookies.items():
            cookies.set(name, value)

        async with httpx.AsyncClient(
            cookies=cookies, follow_redirects=True, timeout=60
        ) as client:
            try:
                # First, resolve the DOI to get the actual publisher page
                response = await client.get(url)

                # Try to find PDF link in the response
                pdf_url = self._extract_pdf_url(response.text, response.url)

                if not pdf_url:
                    print(f"Could not find PDF link for DOI: {doi}")
                    return False

                # Download the PDF
                pdf_response = await client.get(pdf_url)

                if pdf_response.status_code != 200:
                    return False

                content = pdf_response.content
                if len(content) < 1000 or not content.startswith(b"%PDF"):
                    return False

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(content)
                return True

            except Exception as e:
                print(f"Download failed: {e}")
                return False

    def _extract_pdf_url(self, html: str, base_url: httpx.URL) -> str | None:
        """Extract PDF URL from publisher page HTML.

        Args:
            html: The HTML content of the publisher page
            base_url: The base URL for resolving relative links

        Returns:
            PDF URL or None if not found
        """
        # IEEE Xplore pattern
        ieee_match = re.search(r'href="([^"]*stamp\.jsp[^"]*)"', html)
        if ieee_match:
            stamp_url = ieee_match.group(1)
            if not stamp_url.startswith("http"):
                stamp_url = f"https://ieeexplore.ieee.org{stamp_url}"
            return self.get_proxied_url(stamp_url) if not self.vpn_enabled else stamp_url

        # ACM pattern
        acm_match = re.search(r'href="([^"]*\.pdf[^"]*)"', html)
        if acm_match:
            pdf_url = acm_match.group(1)
            if not pdf_url.startswith("http"):
                pdf_url = f"{base_url.scheme}://{base_url.host}{pdf_url}"
            return self.get_proxied_url(pdf_url) if not self.vpn_enabled else pdf_url

        # Generic PDF link pattern
        generic_match = re.search(r'href="([^"]+)"[^>]*>[^<]*(?:PDF|Download)[^<]*</a>', html, re.I)
        if generic_match:
            pdf_url = generic_match.group(1)
            if not pdf_url.startswith("http"):
                pdf_url = f"{base_url.scheme}://{base_url.host}{pdf_url}"
            return self.get_proxied_url(pdf_url) if not self.vpn_enabled else pdf_url

        return None

    def is_authenticated(self) -> bool:
        """Check if the client has valid authentication.

        Returns:
            True if authenticated (cookies loaded or VPN enabled)
        """
        return self._authenticated or self.vpn_enabled

    def clear_cookies(self) -> None:
        """Clear saved cookies and authentication state."""
        self._cookies = {}
        self._authenticated = False
        if self.cookies_file.exists():
            self.cookies_file.unlink()
