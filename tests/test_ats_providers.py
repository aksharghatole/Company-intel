import unittest
from unittest.mock import patch, Mock

from ats_providers import (parse_board_link, discover_board_links, fetch_workable,
                           fetch_recruitee, fetch_smartrecruiters)
from technographics import discover_jobs, guess_slugs


class ProviderTests(unittest.TestCase):
    def test_board_links(self):
        self.assertEqual(parse_board_link("https://jobs.smartrecruiters.com/Acme"), ("smartrecruiters", "Acme"))
        self.assertEqual(parse_board_link("https://acme.recruitee.com/o/test"), ("recruitee", "acme"))
        self.assertIsNone(parse_board_link("https://jobs.lever.co.evil.example/acme"))
        self.assertIsNone(parse_board_link("https://apply.workable.com/j/123"))
        self.assertIsNone(parse_board_link("https://jobs.lever.co/user%2fother"))

    @patch("ats_providers.safe_request")
    def test_discovery_source(self, fetch):
        fetch.return_value = Mock(status_code=200, url="https://acme.com/careers",
                                  text='<a href="https://apply.workable.com/acme/">Jobs</a>')
        self.assertEqual(discover_board_links("acme.com"),
                         [("workable", "acme", "https://acme.com/careers")])

    @patch("ats_providers._json")
    def test_workable(self, get):
        get.return_value = {"jobs": [{"title": "Engineer", "description": "Firmware", "url": "https://example.com/j/1"}]}
        self.assertEqual(fetch_workable("acme")[0]["content"], "Firmware")
        self.assertIsNone(fetch_workable("../acme"))
        get.assert_called_once()

    @patch("ats_providers._json")
    def test_recruitee(self, get):
        get.return_value = {"offers": [{"title": "Engineer", "description": "PCB", "requirements": "CAD", "slug": "engineer"}]}
        self.assertEqual(fetch_recruitee("acme")[0]["url"], "https://acme.recruitee.com/o/engineer")
        self.assertEqual(fetch_recruitee("acme")[0]["content"], "PCB CAD")

    @patch("ats_providers._json")
    def test_smartrecruiters_details(self, get):
        get.side_effect = [{"content": [{"id": "123", "name": "Engineer"}]},
                           {"name": "Engineer", "jobAd": {"sections": {"jobDescription": {"text": "ENOVIA"}}},
                            "postingUrl": "https://jobs.smartrecruiters.com/acme/123"}]
        self.assertEqual(fetch_smartrecruiters("acme")[0]["content"], "ENOVIA")
        self.assertEqual(get.call_count, 2)

    @patch("technographics.fetch_workable", return_value=[])
    @patch("technographics.discover_board_links", return_value=[("workable", "acme", "https://acme.com/careers")])
    def test_linked_empty_board(self, discover, fetch):
        self.assertEqual(discover_jobs("Acme", "acme.com"),
                         ([], "workable:acme", "website-linked", "https://acme.com/careers"))

    def test_slugs(self):
        self.assertEqual(guess_slugs("Acme & Co.", "www.acme.com")[0], "acme")
        self.assertNotIn("www", guess_slugs("Acme", "www.acme.com"))


if __name__ == "__main__":
    unittest.main()
