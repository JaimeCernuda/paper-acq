"""Tests for Institutional access client."""

import tempfile
from pathlib import Path

import pytest

from paper_retriever.clients.institutional import InstitutionalAccessClient


class TestInstitutionalAccessClient:
    """Tests for InstitutionalAccessClient."""

    def test_init_default(self):
        """Test client initialization with defaults."""
        client = InstitutionalAccessClient()
        assert client.proxy_url is None
        assert client.vpn_enabled is False
        assert not client.is_authenticated()

    def test_init_with_proxy(self):
        """Test client initialization with proxy URL."""
        client = InstitutionalAccessClient(
            proxy_url="https://ezproxy.example.edu/login?url="
        )
        assert client.proxy_url == "https://ezproxy.example.edu/login?url="
        assert not client.vpn_enabled

    def test_init_with_vpn(self):
        """Test client initialization with VPN enabled."""
        client = InstitutionalAccessClient(vpn_enabled=True)
        assert client.vpn_enabled is True
        assert client.is_authenticated()  # VPN counts as authenticated

    def test_get_proxied_url_with_proxy(self):
        """Test URL proxying."""
        client = InstitutionalAccessClient(
            proxy_url="https://ezproxy.example.edu/login?url="
        )
        proxied = client.get_proxied_url("https://ieeexplore.ieee.org")
        assert proxied == "https://ezproxy.example.edu/login?url=https://ieeexplore.ieee.org"

    def test_get_proxied_url_with_vpn(self):
        """Test that VPN mode doesn't proxy URLs."""
        client = InstitutionalAccessClient(vpn_enabled=True)
        url = "https://ieeexplore.ieee.org"
        proxied = client.get_proxied_url(url)
        assert proxied == url  # Unchanged

    def test_get_proxied_url_no_proxy(self):
        """Test that missing proxy returns original URL."""
        client = InstitutionalAccessClient()
        url = "https://ieeexplore.ieee.org"
        proxied = client.get_proxied_url(url)
        assert proxied == url

    def test_doi_to_proxied_url(self):
        """Test DOI to proxied URL conversion."""
        client = InstitutionalAccessClient(
            proxy_url="https://ezproxy.example.edu/login?url="
        )
        proxied = client.doi_to_proxied_url("10.1109/TEST.2023.1234567")
        assert "ezproxy.example.edu" in proxied
        assert "doi.org/10.1109/TEST.2023.1234567" in proxied

    def test_save_and_load_cookies(self):
        """Test cookie persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_file = Path(tmpdir) / "test_cookies.pkl"

            # Create client and set some cookies
            client = InstitutionalAccessClient(cookies_file=str(cookies_file))
            client._cookies = {"test_cookie": "test_value"}
            client._authenticated = True
            client.save_cookies()

            # Create new client and load cookies
            client2 = InstitutionalAccessClient(cookies_file=str(cookies_file))
            loaded = client2.load_cookies()

            assert loaded is True
            assert client2._cookies == {"test_cookie": "test_value"}
            assert client2.is_authenticated()

    def test_load_cookies_missing_file(self):
        """Test loading cookies when file doesn't exist."""
        client = InstitutionalAccessClient(cookies_file="/nonexistent/path.pkl")
        loaded = client.load_cookies()
        assert loaded is False

    def test_clear_cookies(self):
        """Test clearing cookies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_file = Path(tmpdir) / "test_cookies.pkl"

            client = InstitutionalAccessClient(cookies_file=str(cookies_file))
            client._cookies = {"test": "value"}
            client._authenticated = True
            client.save_cookies()

            assert cookies_file.exists()

            client.clear_cookies()

            assert client._cookies == {}
            assert not client._authenticated
            assert not cookies_file.exists()

    def test_is_authenticated_vpn(self):
        """Test that VPN mode is always authenticated."""
        client = InstitutionalAccessClient(vpn_enabled=True)
        assert client.is_authenticated() is True

    def test_is_authenticated_cookies(self):
        """Test authentication state with cookies."""
        client = InstitutionalAccessClient()
        assert client.is_authenticated() is False

        client._authenticated = True
        assert client.is_authenticated() is True

    def test_extract_pdf_url_ieee(self):
        """Test IEEE PDF URL extraction."""
        client = InstitutionalAccessClient()
        html = '<a href="/stamp/stamp.jsp?tp=&arnumber=123456">PDF</a>'

        import httpx
        url = client._extract_pdf_url(html, httpx.URL("https://ieeexplore.ieee.org/document/123456"))

        assert url is not None
        assert "stamp.jsp" in url

    def test_extract_pdf_url_generic(self):
        """Test generic PDF URL extraction."""
        client = InstitutionalAccessClient()
        html = '<a href="/download/paper.pdf">Download PDF</a>'

        import httpx
        url = client._extract_pdf_url(html, httpx.URL("https://publisher.com/article"))

        assert url is not None
        assert "paper.pdf" in url

    def test_init_with_vpn_script(self):
        """Test client initialization with VPN script."""
        client = InstitutionalAccessClient(
            vpn_enabled=True,
            vpn_script="/path/to/vpn-connect.sh",
        )
        assert client.vpn_enabled is True
        assert client.vpn_script == "/path/to/vpn-connect.sh"

    def test_connect_vpn_no_script(self):
        """Test VPN connection without script returns False."""
        client = InstitutionalAccessClient(vpn_enabled=True)
        result = client.connect_vpn()
        assert result is False

    def test_connect_vpn_missing_script(self):
        """Test VPN connection with missing script returns False."""
        client = InstitutionalAccessClient(
            vpn_enabled=True,
            vpn_script="/nonexistent/script.sh",
        )
        result = client.connect_vpn()
        assert result is False

    def test_connect_vpn_with_script(self):
        """Test VPN connection with working script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple script that exits successfully
            script_path = Path(tmpdir) / "vpn-connect.sh"
            script_path.write_text("#!/bin/bash\nexit 0\n")
            script_path.chmod(0o755)

            client = InstitutionalAccessClient(
                vpn_enabled=True,
                vpn_script=str(script_path),
            )
            result = client.connect_vpn()

            assert result is True
            assert client._vpn_connected is True
            assert client.is_authenticated() is True

    def test_connect_vpn_with_failing_script(self):
        """Test VPN connection with failing script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a script that fails
            script_path = Path(tmpdir) / "vpn-connect.sh"
            script_path.write_text("#!/bin/bash\nexit 1\n")
            script_path.chmod(0o755)

            client = InstitutionalAccessClient(
                vpn_enabled=True,
                vpn_script=str(script_path),
            )
            result = client.connect_vpn()

            assert result is False
            assert client._vpn_connected is False

    def test_disconnect_vpn_no_script(self):
        """Test VPN disconnect without script."""
        client = InstitutionalAccessClient(vpn_enabled=True)
        client._vpn_connected = True
        result = client.disconnect_vpn()

        assert result is True
        assert client._vpn_connected is False

    def test_disconnect_vpn_with_script(self):
        """Test VPN disconnect with script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "vpn-disconnect.sh"
            script_path.write_text("#!/bin/bash\nexit 0\n")
            script_path.chmod(0o755)

            client = InstitutionalAccessClient(vpn_enabled=True)
            client._vpn_connected = True
            result = client.disconnect_vpn(disconnect_script=str(script_path))

            assert result is True
            assert client._vpn_connected is False
