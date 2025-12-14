"""Institutional access client using EZProxy and Selenium."""

import glob
import pickle
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
        vpn_script: str | None = None,
        cookies_file: str = ".institutional_cookies.pkl",
        download_dir: str = "./downloads",
    ):
        """Initialize the institutional access client.

        Args:
            proxy_url: EZProxy URL (e.g., "https://ezproxy.gl.iit.edu/login?url=")
            vpn_enabled: If True, assume VPN is connected and use direct access
            vpn_script: Path to script that connects to VPN (run during auth)
            cookies_file: Path to save/load authentication cookies
            download_dir: Directory to save downloaded PDFs
        """
        self.proxy_url = proxy_url
        self.vpn_enabled = vpn_enabled
        self.vpn_script = vpn_script
        self.cookies_file = Path(cookies_file)
        self.download_dir = Path(download_dir)
        self._cookies: dict[str, str] = {}
        self._authenticated = False
        self._vpn_connected = False
        self._last_error: str | None = None

        # Auto-load cookies if they exist
        if self.cookies_file.exists():
            self.load_cookies()

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
                data = pickle.load(f)

            # Handle both old format (dict) and new format (dict with selenium_cookies)
            if isinstance(data, dict) and "selenium_cookies" in data:
                self._selenium_cookies = data["selenium_cookies"]
                self._cookies = data["simple_cookies"]
            elif isinstance(data, dict):
                # Old format - just simple cookies
                self._cookies = data
                self._selenium_cookies = []
            else:
                return False

            self._authenticated = True
            return True
        except (pickle.PickleError, EOFError):
            return False

    def save_cookies(self) -> None:
        """Save authentication cookies for reuse."""
        data = {
            "selenium_cookies": getattr(self, "_selenium_cookies", []),
            "simple_cookies": self._cookies,
        }
        with open(self.cookies_file, "wb") as f:
            pickle.dump(data, f)

    def connect_vpn(self) -> bool:
        """Run the VPN connection script.

        Returns:
            True if VPN connected successfully (or no script configured)
        """
        if not self.vpn_script:
            print("No VPN script configured.")
            return False

        script_path = Path(self.vpn_script)
        if not script_path.exists():
            print(f"VPN script not found: {self.vpn_script}")
            return False

        print(f"\nRunning VPN script: {self.vpn_script}")
        print("=" * 60)

        try:
            # Run the script
            result = subprocess.run(
                [str(script_path)],
                shell=True,
                capture_output=False,  # Let output go to terminal for interactive scripts
                text=True,
            )

            if result.returncode == 0:
                print("=" * 60)
                print("VPN script completed successfully.")
                self._vpn_connected = True
                self._authenticated = True
                return True
            else:
                print("=" * 60)
                print(f"VPN script failed with exit code: {result.returncode}")
                return False

        except Exception as e:
            print(f"Error running VPN script: {e}")
            return False

    def disconnect_vpn(self, disconnect_script: str | None = None) -> bool:
        """Run a VPN disconnect script if provided.

        Args:
            disconnect_script: Path to disconnect script (optional)

        Returns:
            True if disconnect was successful
        """
        if not disconnect_script:
            self._vpn_connected = False
            return True

        script_path = Path(disconnect_script)
        if not script_path.exists():
            print(f"Disconnect script not found: {disconnect_script}")
            return False

        try:
            result = subprocess.run(
                [str(script_path)],
                shell=True,
                capture_output=True,
                text=True,
            )
            self._vpn_connected = False
            return result.returncode == 0
        except Exception as e:
            print(f"Error running disconnect script: {e}")
            return False

    def _get_available_browser(self) -> tuple[Any, str] | None:
        """Detect and return an available browser driver.

        Tries browsers in order: Chrome, Edge, Firefox.
        Returns the first one that works.

        Returns:
            Tuple of (driver, browser_name) or None if no browser available.
        """
        try:
            from selenium import webdriver
        except ImportError:
            return None

        browsers = [
            ("chrome", self._try_chrome),
            ("edge", self._try_edge),
            ("firefox", self._try_firefox),
        ]

        for name, try_func in browsers:
            try:
                driver = try_func(webdriver)
                if driver:
                    return driver, name
            except Exception:
                continue

        return None

    def _try_chrome(self, webdriver: Any) -> Any | None:
        """Try to create a Chrome driver."""
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.add_argument("--start-maximized")

        # Try with webdriver-manager first
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except Exception:
            pass

        # Try without webdriver-manager
        try:
            return webdriver.Chrome(options=options)
        except Exception:
            return None

    def _try_edge(self, webdriver: Any) -> Any | None:
        """Try to create an Edge driver."""
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service

        options = Options()
        options.add_argument("--start-maximized")

        # Try with webdriver-manager first
        try:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            service = Service(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        except Exception:
            pass

        # Try without webdriver-manager
        try:
            return webdriver.Edge(options=options)
        except Exception:
            return None

    def _try_firefox(self, webdriver: Any) -> Any | None:
        """Try to create a Firefox driver."""
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service

        options = Options()

        # Try with webdriver-manager first
        try:
            from webdriver_manager.firefox import GeckoDriverManager
            service = Service(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        except Exception:
            pass

        # Try without webdriver-manager
        try:
            return webdriver.Firefox(options=options)
        except Exception:
            return None

    def _get_browser_with_profile(self, profile_dir: str) -> tuple[Any, str] | None:
        """Create a browser with persistent profile for authentication.

        Args:
            profile_dir: Directory for browser profile.

        Returns:
            Tuple of (driver, browser_name) or None if no browser available.
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from selenium.webdriver.edge.service import Service as EdgeService
        except ImportError:
            return None

        # Try Chrome first
        try:
            options = ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--profile-directory=Default")
            # Disable automation flags that might affect session persistence
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = ChromeService(ChromeDriverManager().install())
                return webdriver.Chrome(service=service, options=options), "chrome"
            except Exception:
                return webdriver.Chrome(options=options), "chrome"
        except Exception:
            pass

        # Try Edge
        try:
            options = EdgeOptions()
            options.add_argument("--start-maximized")
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--profile-directory=Default")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            try:
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                service = EdgeService(EdgeChromiumDriverManager().install())
                return webdriver.Edge(service=service, options=options), "edge"
            except Exception:
                return webdriver.Edge(options=options), "edge"
        except Exception:
            pass

        return None

    def _get_browser_with_download_dir(
        self, download_dir: str, use_profile: bool = True
    ) -> tuple[Any, str] | None:
        """Create a browser configured for automatic PDF downloads.

        Args:
            download_dir: Directory where downloads should be saved.
            use_profile: If True, use persistent profile to maintain login state.

        Returns:
            Tuple of (driver, browser_name) or None if no browser available.
        """
        try:
            from selenium import webdriver
        except ImportError:
            return None

        # Get profile directory for persistent sessions
        profile_dir = None
        if use_profile:
            profile_dir = str(Path.home() / ".paper_retriever_browser_profile")
            Path(profile_dir).mkdir(parents=True, exist_ok=True)

        browsers = [
            ("chrome", lambda: self._try_chrome_with_downloads(webdriver, download_dir, profile_dir)),
            ("edge", lambda: self._try_edge_with_downloads(webdriver, download_dir, profile_dir)),
            ("firefox", lambda: self._try_firefox_with_downloads(webdriver, download_dir, profile_dir)),
        ]

        for name, try_func in browsers:
            try:
                driver = try_func()
                if driver:
                    return driver, name
            except Exception:
                continue

        return None

    def _try_chrome_with_downloads(
        self, webdriver: Any, download_dir: str, profile_dir: str | None = None
    ) -> Any | None:
        """Try to create a Chrome driver configured for downloads."""
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.add_argument("--start-maximized")

        # Use persistent profile for login state
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--profile-directory=Default")

        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except Exception:
            pass

        try:
            return webdriver.Chrome(options=options)
        except Exception:
            return None

    def _try_edge_with_downloads(
        self, webdriver: Any, download_dir: str, profile_dir: str | None = None
    ) -> Any | None:
        """Try to create an Edge driver configured for downloads."""
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service

        options = Options()
        options.add_argument("--start-maximized")

        # Use persistent profile for login state
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument("--profile-directory=Default")

        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        }
        options.add_experimental_option("prefs", prefs)

        try:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            service = Service(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        except Exception:
            pass

        try:
            return webdriver.Edge(options=options)
        except Exception:
            return None

    def _try_firefox_with_downloads(
        self, webdriver: Any, download_dir: str, profile_dir: str | None = None
    ) -> Any | None:
        """Try to create a Firefox driver configured for downloads."""
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service

        options = Options()
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", download_dir)
        options.set_preference("browser.download.useDownloadDir", True)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf")
        options.set_preference("pdfjs.disabled", True)

        # Use persistent profile for login state
        if profile_dir:
            options.set_preference("profile", profile_dir)

        try:
            from webdriver_manager.firefox import GeckoDriverManager
            service = Service(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        except Exception:
            pass

        try:
            return webdriver.Firefox(options=options)
        except Exception:
            return None

    def _wait_for_download(self, download_dir: str, timeout: int = 60) -> str | None:
        """Wait for a PDF file to appear in the download directory.

        Args:
            download_dir: Directory to watch for downloads.
            timeout: Maximum time to wait in seconds.

        Returns:
            Path to the downloaded PDF file, or None if timeout.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Look for PDF files
            pdf_files = glob.glob(f"{download_dir}/*.pdf")
            if pdf_files:
                # Check if download is complete (no .crdownload or .part files)
                for pdf_file in pdf_files:
                    partial_chrome = f"{pdf_file}.crdownload"
                    partial_firefox = pdf_file.replace(".pdf", ".pdf.part")
                    if not Path(partial_chrome).exists() and not Path(partial_firefox).exists():
                        # Verify it's a real PDF
                        try:
                            with open(pdf_file, "rb") as f:
                                header = f.read(5)
                                if header == b"%PDF-":
                                    return pdf_file
                        except Exception:
                            pass
            time.sleep(1)
        return None

    def _download_pdf_selenium(self, article_url: str, output_path: Path) -> bool:
        """Download PDF using Selenium browser automation.

        Used for publishers like Elsevier/ScienceDirect that require JavaScript
        for PDF downloads.

        Args:
            article_url: The article page URL (e.g., ScienceDirect article page).
            output_path: Path to save the downloaded PDF.

        Returns:
            True if download was successful.
        """
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError:
            self._last_error = "Selenium not installed"
            return False

        # Create temporary download directory
        with tempfile.TemporaryDirectory() as download_dir:
            result = self._get_browser_with_download_dir(download_dir)
            if not result:
                self._last_error = "no browser available for Selenium"
                return False

            driver, browser_name = result

            try:
                # Inject cookies with FULL domain info from selenium_cookies
                selenium_cookies = getattr(self, "_selenium_cookies", [])
                if not selenium_cookies:
                    self._last_error = "no cookies with domain info - re-run: uv run paper-retriever auth"
                    return False

                # Use Chrome DevTools Protocol to set cookies WITHOUT visiting each domain
                # This bypasses the redirect-to-Okta problem
                for cookie in selenium_cookies:
                    try:
                        # Build CDP cookie parameters
                        cdp_cookie = {
                            "name": cookie["name"],
                            "value": cookie["value"],
                            "domain": cookie.get("domain", ""),
                            "path": cookie.get("path", "/"),
                        }
                        if cookie.get("secure"):
                            cdp_cookie["secure"] = True
                        if cookie.get("httpOnly"):
                            cdp_cookie["httpOnly"] = True
                        if cookie.get("sameSite"):
                            cdp_cookie["sameSite"] = cookie["sameSite"]

                        driver.execute_cdp_cmd("Network.setCookie", cdp_cookie)
                    except Exception:
                        pass  # Some cookies may fail, that's OK

                # Navigate to the article page
                # For ScienceDirect, convert /abs/ URL to full article URL
                if "/article/abs/" in article_url:
                    article_url = article_url.replace("/article/abs/", "/article/")

                driver.get(article_url)
                time.sleep(3)

                # For ScienceDirect, click the PDF download button on the article page
                if "sciencedirect" in article_url:
                    # Try multiple approaches to download PDF

                    # Approach 1: Click "View PDF" or "Download PDF" button on article page
                    pdf_buttons = [
                        "a.pdf-download-btn-link",
                        "a[data-aa-name='srp-view-pdf']",
                        "#pdfLink",
                        "a.accessbar-link-pdf",
                        "a[aria-label*='PDF']",
                        "button[aria-label*='PDF']",
                        "a.download-link",
                    ]

                    for selector in pdf_buttons:
                        try:
                            btn = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            btn.click()
                            time.sleep(3)

                            # Check if download started
                            pdf_file = self._wait_for_download(download_dir, timeout=45)
                            if pdf_file:
                                output_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy(pdf_file, output_path)
                                return True
                        except Exception:
                            continue

                    # Approach 2: Navigate directly to PDF URL
                    pii_match = re.search(r'/pii/([A-Z0-9]+)', article_url, re.I)
                    if pii_match:
                        pii = pii_match.group(1)
                        parsed = urlparse(article_url)
                        pdf_url = f"{parsed.scheme}://{parsed.netloc}/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"

                        driver.get(pdf_url)
                        time.sleep(5)

                        pdf_file = self._wait_for_download(download_dir, timeout=45)
                        if pdf_file:
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy(pdf_file, output_path)
                            return True

                # Fallback: Try clicking PDF button
                pdf_selectors = [
                    # ScienceDirect specific
                    "a.pdf-download-btn-link",
                    "#pdfLink",
                    "a[aria-label='Download PDF']",
                    "a[aria-label='View PDF']",
                    "button[aria-label='Download PDF']",
                    # Generic
                    "a[href*='pdfft']",
                    "a[href*='/pdf']",
                ]

                pdf_clicked = False
                for selector in pdf_selectors:
                    try:
                        pdf_button = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        pdf_button.click()
                        pdf_clicked = True
                        break
                    except Exception:
                        continue

                if not pdf_clicked:
                    # Try finding by link text
                    try:
                        pdf_link = driver.find_element(By.PARTIAL_LINK_TEXT, "PDF")
                        pdf_link.click()
                        pdf_clicked = True
                    except Exception:
                        pass

                if not pdf_clicked:
                    # Debug: save page source to understand what we're seeing
                    current_url = driver.current_url.lower()
                    if "okta" in current_url or "login" in current_url or "saml" in current_url:
                        self._last_error = "redirected to login - cookies may not have worked"
                    else:
                        # Save page source for debugging
                        try:
                            debug_file = output_path.parent / f"{output_path.stem}_debug.html"
                            debug_file.write_text(driver.page_source, encoding="utf-8")
                            self._last_error = f"could not find PDF download button (debug saved to {debug_file})"
                        except Exception:
                            self._last_error = "could not find PDF download button"
                    return False

                # Wait for download to complete
                pdf_file = self._wait_for_download(download_dir, timeout=60)

                if pdf_file:
                    # Copy to output location
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(pdf_file, output_path)
                    return True

                self._last_error = "PDF download timed out"
                return False

            except Exception as e:
                self._last_error = f"Selenium error: {str(e)}"
                return False

            finally:
                driver.quit()

    def authenticate_interactive(self) -> bool:
        """Authenticate interactively using Selenium.

        Opens a browser window for the user to complete Shibboleth/SAML login.
        Automatically detects available browsers (Chrome, Edge, Firefox).
        Uses a persistent browser profile so login state is preserved.

        Returns:
            True if authentication was successful

        Raises:
            ImportError: If selenium is not installed
            RuntimeError: If no supported browser is available
        """
        try:
            from selenium import webdriver  # noqa: F401
        except ImportError:
            raise ImportError(
                "Selenium is required for interactive authentication. "
                "Install with: pip install selenium webdriver-manager"
            )

        if not self.proxy_url:
            print("Error: proxy_url must be configured for authentication")
            return False

        # Use persistent profile so Okta session is preserved for downloads
        profile_dir = str(Path.home() / ".paper_retriever_browser_profile")
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        # Try to find an available browser with persistent profile
        result = self._get_browser_with_profile(profile_dir)
        if result is None:
            supported = ["Google Chrome", "Microsoft Edge", "Mozilla Firefox"]
            raise RuntimeError(
                "No supported browser found.\n"
                f"Please install one of: {', '.join(supported)}\n"
                "The browser must be installed in its default location."
            )

        driver, browser_name = result
        print(f"Using {browser_name} browser for authentication...")
        print(f"Profile saved to: {profile_dir}")

        try:
            # Navigate to proxy login with a test URL (IEEE)
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

            # Extract cookies from Selenium - save FULL cookie objects with domain info
            # Get cookies from current domain (IEEE)
            selenium_cookies = driver.get_cookies()
            print(f"  Captured {len(selenium_cookies)} cookies from IEEE")

            # Now visit other publishers to capture their cookies too
            # The Okta session should carry over, so no additional login needed
            other_publishers = [
                ("ScienceDirect", "https://www.sciencedirect.com"),
                ("ACM", "https://dl.acm.org"),
            ]

            for name, url in other_publishers:
                try:
                    print(f"  Visiting {name} to capture cookies...")
                    proxied_url = self.get_proxied_url(url)
                    driver.get(proxied_url)
                    time.sleep(3)

                    # Check if we landed on a login page
                    current_url = driver.current_url.lower()
                    if "okta" in current_url or "login" in current_url:
                        print(f"  {name} requires additional login - please complete it")
                        print("  Press Enter when done...")
                        input()
                        time.sleep(2)

                    publisher_cookies = driver.get_cookies()
                    selenium_cookies.extend(publisher_cookies)
                    print(f"  Captured {len(publisher_cookies)} cookies from {name}")
                except Exception as e:
                    print(f"  Warning: Could not capture {name} cookies: {e}")

            # Also capture cookies from EZProxy domain
            if self.proxy_url:
                try:
                    ezproxy_base = self.proxy_url.split("?")[0].rstrip("/")
                    driver.get(ezproxy_base)
                    time.sleep(1)
                    ezproxy_cookies = driver.get_cookies()
                    selenium_cookies.extend(ezproxy_cookies)
                    print(f"  Captured {len(ezproxy_cookies)} cookies from EZProxy")
                except Exception:
                    pass

            # Deduplicate cookies by name+domain
            seen = set()
            unique_cookies = []
            for c in selenium_cookies:
                key = (c.get("name"), c.get("domain"))
                if key not in seen:
                    seen.add(key)
                    unique_cookies.append(c)

            self._selenium_cookies = unique_cookies  # Full cookie objects for Selenium
            self._cookies = {}  # Simple dict for httpx

            for cookie in unique_cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    self._cookies[name] = value

            # Save both formats for reuse
            self.save_cookies()
            self._authenticated = True

            print(f"\nAuthentication successful! {len(unique_cookies)} cookies saved from {len(seen)} domains.")
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
        self._last_error = None  # Reset error state

        # Ensure we have cookies loaded
        if not self._authenticated and not self.vpn_enabled:
            if not self.load_cookies():
                self._last_error = "not authenticated - run: paper-retriever auth"
                return False

        # Build the proxied URL
        url = self.doi_to_proxied_url(doi)

        # Create httpx client with cookies
        cookies = httpx.Cookies()
        for name, value in self._cookies.items():
            cookies.set(name, value)

        # Browser-like headers to avoid bot detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        async with httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            follow_redirects=True,
            timeout=60,
            verify=False,  # EZProxy often has cert issues
        ) as client:
            try:
                # First, resolve the DOI to get the actual publisher page
                response = await client.get(url)
                self._last_response_url = str(response.url)
                self._last_response_status = response.status_code

                if response.status_code != 200:
                    self._last_error = f"publisher page returned HTTP {response.status_code}"
                    return False

                # Check if we got a login page instead of the paper
                if "login" in str(response.url).lower() and "ezproxy" in str(response.url).lower():
                    self._last_error = "redirected to login - cookies may be expired, run: paper-retriever auth"
                    return False

                # Special handling for Elsevier linkinghub (uses JavaScript redirect)
                response_url = str(response.url)
                if "linkinghub" in response_url:
                    # Extract PII and navigate to ScienceDirect article page
                    pii_match = re.search(r'/pii/([A-Z0-9]+)', response_url, re.I)
                    if pii_match:
                        pii = pii_match.group(1)
                        host = response.url.host
                        ezproxy_idx = host.find("ezproxy")
                        if ezproxy_idx > 0:
                            proxy_suffix = host[ezproxy_idx:]
                            article_url = f"https://www-sciencedirect-com.{proxy_suffix}/science/article/pii/{pii}"
                            # Fetch the ScienceDirect article page
                            article_response = await client.get(article_url)
                            if article_response.status_code == 200:
                                # Update response to the article page
                                response = article_response
                                self._last_response_url = str(response.url)

                # Try to find PDF link in the response
                pdf_url = self._extract_pdf_url(response.text, response.url)
                self._last_pdf_url = pdf_url  # Store for debugging

                if not pdf_url:
                    # Save a snippet of the page for debugging
                    self._last_error = f"no PDF link found on page (URL: {response.url})"
                    return False

                # Download the PDF
                pdf_response = await client.get(pdf_url)

                if pdf_response.status_code != 200:
                    # ScienceDirect needs Selenium - httpx can't handle JS-based PDF download
                    if "sciencedirect" in str(response.url) or "elsevier" in str(response.url):
                        article_url = str(response.url)
                        return self._download_pdf_selenium(article_url, output_path)
                    self._last_error = f"PDF download returned HTTP {pdf_response.status_code}"
                    return False

                content = pdf_response.content
                if len(content) < 1000:
                    self._last_error = f"content too small ({len(content)} bytes)"
                    return False

                if not content.startswith(b"%PDF"):
                    # ScienceDirect returns HTML - need Selenium for PDF download
                    if "sciencedirect" in str(response.url):
                        # Try Selenium-based download for ScienceDirect
                        article_url = str(response.url)
                        return self._download_pdf_selenium(article_url, output_path)

                    # Check what we actually got
                    content_preview = content[:100].decode("utf-8", errors="replace")
                    self._last_error = f"not a PDF file (starts with: {content_preview[:50]}...)"
                    return False

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(content)
                return True

            except Exception as e:
                # Store error for logging at higher level
                self._last_error = str(e)
                return False

    def _extract_pdf_url(self, html: str, base_url: httpx.URL) -> str | None:
        """Extract PDF URL from publisher page HTML.

        Args:
            html: The HTML content of the publisher page
            base_url: The base URL for resolving relative links

        Returns:
            PDF URL or None if not found
        """
        base_url_str = str(base_url)

        # IEEE Xplore - extract arnumber from URL and construct PDF link
        # URL format: https://ieeexplore.ieee.org/document/9556010/
        if "ieeexplore" in base_url_str:
            arnumber_match = re.search(r'/document/(\d+)', base_url_str)
            if arnumber_match:
                arnumber = arnumber_match.group(1)
                # Construct PDF URL - use the proxied host if via EZProxy
                if "ezproxy" in base_url_str:
                    # Extract the proxied host (e.g., ieeexplore-ieee-org.ezproxy.gl.iit.edu)
                    host = base_url.host
                    pdf_url = f"https://{host}/stampPDF/getPDF.jsp?tp=&arnumber={arnumber}"
                else:
                    pdf_url = f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={arnumber}"
                return pdf_url

        # Legacy IEEE pattern (stamp.jsp in HTML)
        ieee_match = re.search(r'href="([^"]*stamp\.jsp[^"]*)"', html)
        if ieee_match:
            stamp_url = ieee_match.group(1)
            if not stamp_url.startswith("http"):
                stamp_url = f"https://ieeexplore.ieee.org{stamp_url}"
            return self.get_proxied_url(stamp_url) if not self.vpn_enabled else stamp_url

        # ACM Digital Library - look for PDF link
        if "acm.org" in base_url_str or "dl-acm-org" in base_url_str:
            # ACM PDF links are in format /doi/pdf/10.1145/xxx
            acm_pdf_match = re.search(r'href="(/doi/pdf/[^"]+)"', html)
            if acm_pdf_match:
                pdf_path = acm_pdf_match.group(1)
                pdf_url = f"{base_url.scheme}://{base_url.host}{pdf_path}"
                return pdf_url

        # Elsevier/ScienceDirect - look for PDF link in HTML or construct from PII
        if "sciencedirect" in base_url_str:
            # Look for explicit PDF link in the page
            pdf_link = re.search(r'href="([^"]*pdfft[^"]*)"', html)
            if pdf_link:
                pdf_url = pdf_link.group(1)
                if not pdf_url.startswith("http"):
                    pdf_url = f"{base_url.scheme}://{base_url.host}{pdf_url}"
                return pdf_url

            # Construct PDF URL from PII
            pii_match = re.search(r'/pii/([A-Z0-9]+)', base_url_str, re.I)
            if pii_match:
                pii = pii_match.group(1)
                pdf_url = f"{base_url.scheme}://{base_url.host}/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
                return pdf_url

        # Legacy linkinghub handling (should be handled in download_pdf now)
        if "linkinghub" in base_url_str:
            pii_match = re.search(r'/pii/([A-Z0-9]+)', base_url_str, re.I)
            if pii_match:
                pii = pii_match.group(1)
                if "ezproxy" in base_url_str:
                    host = base_url.host
                    ezproxy_idx = host.find("ezproxy")
                    if ezproxy_idx > 0:
                        proxy_suffix = host[ezproxy_idx:]
                        pdf_url = f"https://www-sciencedirect-com.{proxy_suffix}/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
                        return pdf_url

        # Generic .pdf link pattern
        pdf_match = re.search(r'href="([^"]*\.pdf[^"]*)"', html)
        if pdf_match:
            pdf_url = pdf_match.group(1)
            if not pdf_url.startswith("http"):
                pdf_url = f"{base_url.scheme}://{base_url.host}{pdf_url}"
            return self.get_proxied_url(pdf_url) if not self.vpn_enabled else pdf_url

        # Generic PDF/Download button pattern
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

    def get_last_error(self) -> str | None:
        """Get the last error that occurred during download.

        Returns:
            Error message or None if no error.
        """
        return self._last_error

    def get_last_response_url(self) -> str | None:
        """Get the final URL after redirects from last request."""
        return getattr(self, "_last_response_url", None)

    def get_last_pdf_url(self) -> str | None:
        """Get the PDF URL that was attempted."""
        return getattr(self, "_last_pdf_url", None)
