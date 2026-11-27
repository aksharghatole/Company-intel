import unittest
from unittest.mock import Mock, patch

import pandas as pd

from batch import scan_one
from safe_web import normalize_domain, validate_public_url, safe_request
from technographics import scan_jobs_for_tech


def address(ip):
    return (2, 1, 6, "", (ip, 443))


class DomainTests(unittest.TestCase):
    def test_normalizes_url(self):
        self.assertEqual(normalize_domain(" HTTPS://Example.COM/about "), "example.com")

    def test_rejects_unsafe_inputs(self):
        for value in ("localhost", "127.0.0.1", "http://[::1]", "http://user@example.com",
                      "http://example.com:8080", "ftp://example.com", "foo.internal",
                      "http://example.com\\@evil.com", "example.com\nbad", "169.254.169.254"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_domain(value)

    @patch("safe_web.socket.getaddrinfo")
    def test_dns_mixed_addresses_rejected(self, dns):
        dns.return_value = [address("93.184.216.34"), address("10.0.0.1")]
        with self.assertRaises(ValueError):
            validate_public_url("https://example.com")

    @patch("safe_web.socket.getaddrinfo")
    def test_dns_public(self, dns):
        dns.return_value = [address("93.184.216.34")]
        self.assertEqual(validate_public_url("https://example.com"), "example.com")

    @patch("safe_web.requests.Session")
    @patch("safe_web.socket.getaddrinfo")
    def test_redirect_to_private_dns_blocked(self, dns, session):
        dns.side_effect = [[address("93.184.216.34")], [address("192.168.0.1")]]
        client = session.return_value.__enter__.return_value
        client.request.return_value = Mock(status_code=302,
                                           headers={"Location": "https://private.example.com"},
                                           url="https://example.com")
        with self.assertRaises(ValueError):
            safe_request("https://example.com", headers={}, timeout=1)
        self.assertEqual(client.request.call_count, 1)

    @patch("safe_web.requests.Session")
    @patch("safe_web.socket.getaddrinfo")
    def test_public_redirect(self, dns, session):
        dns.return_value = [address("93.184.216.34")]
        client = session.return_value.__enter__.return_value
        final = Mock(status_code=200, headers={}, url="https://example.com/about")
        client.request.side_effect = [Mock(status_code=301, headers={"Location": "/about"},
                                           url="https://example.com"), final]
        self.assertIs(safe_request("https://example.com", headers={}, timeout=1), final)
        self.assertEqual(client.request.call_count, 2)
        self.assertFalse(client.request.call_args.kwargs["allow_redirects"])


class BatchTests(unittest.TestCase):
    @patch("batch.get_tech_stack")
    def test_missing_and_invalid_rows_do_not_scan(self, tech):
        for row in ({"company": "Acme", "domain": pd.NA},
                    {"company": "Acme", "domain": "localhost"}):
            self.assertTrue(scan_one(row)["error"])
        tech.assert_not_called()

    @patch("batch.get_firmographics", return_value={})
    @patch("batch.get_hiring_signals", return_value={})
    @patch("batch.get_tech_stack", return_value={"error": "DNS failed", "detected": []})
    @patch("batch.scan_technographics_free", return_value={})
    def test_scan_error_is_visible(self, ats, tech, hiring, firm):
        result = scan_one({"company": "Acme", "domain": "https://example.com/about"})
        self.assertEqual(result["domain"], "example.com")
        self.assertEqual(result["error"], "DNS failed")


class TechnographicTests(unittest.TestCase):
    def test_vendor_evidence(self):
        findings = scan_jobs_for_tech([{"title": "Mechanical Engineer",
                                       "content": "SolidWorks and ENOVIA experience",
                                       "url": "https://example.com/jobs/1"}])
        self.assertIn("ENOVIA", findings["PLM"])
        self.assertEqual(findings["CAD"]["SolidWorks"][0]["url"], "https://example.com/jobs/1")


if __name__ == "__main__":
    unittest.main()
