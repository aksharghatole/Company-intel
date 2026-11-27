import unittest
from unittest.mock import Mock, patch

from ats_providers import parse_board_link, discover_board_links
from technographics import scan_technographics_free
from workday import fetch_workday, parse_workday_board, board_url, _job_path

KEY = "acme.wd5.myworkdayjobs.com/External"


def response(data=None, status=200, headers=None):
    return Mock(status_code=status, headers=headers or {}, json=Mock(return_value=data))


class WorkdayTests(unittest.TestCase):
    def test_board_parsing(self):
        self.assertEqual(parse_workday_board("https://acme.wd5.myworkdayjobs.com/en-US/External/job/Engineer"), KEY)
        self.assertEqual(parse_board_link("https://" + KEY), ("workday", KEY))
        for url in ("https://acme.wd5.myworkdayjobs.com.evil.example/External",
                    "https://user@acme.wd5.myworkdayjobs.com/External",
                    "https://acme.wd5.myworkdayjobs.com:8080/External",
                    "https://acme.wd5.myworkdayjobs.com/en-US"):
            with self.subTest(url=url):
                self.assertIsNone(parse_workday_board(url))
        self.assertEqual(board_url(KEY), "https://" + KEY)

    def test_paths(self):
        self.assertEqual(_job_path("/job/United%20States/Engineer_R1"), "/job/United%20States/Engineer_R1")
        for path in ("//evil.example/job/1", "/job/../jobs", "/job/%2e%2e/jobs",
                     "/job/abc?x=y", "/job/%252e%252e/jobs"):
            self.assertIsNone(_job_path(path))

    @patch("workday.requests.Session")
    def test_list_and_details(self, session):
        client = session.return_value.__enter__.return_value
        client.request.side_effect = [
            response({"total": 200, "jobPostings": [{"title": "Engineer", "externalPath": "/job/Engineer_R1"}]}),
            response({"jobPostingInfo": {"title": "Engineer", "jobDescription": "ENOVIA and firmware", "startDate": "2026-11-01"}})]
        jobs, status, total = fetch_workday(KEY)
        self.assertEqual((status, total), ("available", 200))
        self.assertEqual(jobs[0]["url"], "https://" + KEY + "/job/Engineer_R1")
        self.assertEqual(jobs[0]["posted_date"], "2026-11-01")
        self.assertEqual(client.request.call_args_list[0].args[0], "POST")
        self.assertFalse(client.request.call_args.kwargs["allow_redirects"])

    @patch("workday.requests.Session")
    def test_block_stops_requests(self, session):
        client = session.return_value.__enter__.return_value
        client.request.return_value = response(status=429)
        self.assertEqual(fetch_workday(KEY), (None, "access restricted", None))
        client.request.assert_called_once()

    @patch("workday.requests.Session")
    def test_detail_block_retains_partial_jobs(self, session):
        client = session.return_value.__enter__.return_value
        client.request.side_effect = [
            response({"total": 3, "jobPostings": [{"title": "Engineer", "externalPath": f"/job/Engineer_{n}"} for n in range(3)]}),
            response({"jobPostingInfo": {"jobDescription": "Firmware"}}),
            response(status=403)]
        jobs, status, total = fetch_workday(KEY)
        self.assertEqual((len(jobs), status, total), (1, "access restricted", 3))
        self.assertEqual(client.request.call_count, 3)

    @patch("technographics.fetch_greenhouse")
    @patch("technographics.fetch_workday", return_value=(None, "access restricted", None))
    @patch("technographics.discover_board_links", return_value=[("workday", KEY, "https://acme.com/careers")])
    def test_linked_block_does_not_guess(self, discover, workday, greenhouse):
        result = scan_technographics_free("Acme", "acme.com")
        self.assertEqual(result["ats_identity"], "website-linked")
        self.assertEqual(result["ats_access"], "access restricted")
        self.assertEqual(result["ats_board_url"], "https://" + KEY)
        self.assertEqual(result["jobs_scanned"], 0)
        greenhouse.assert_not_called()

    @patch("ats_providers.safe_request")
    def test_redirect_to_blocked_board(self, fetch):
        fetch.return_value = Mock(status_code=403, url="https://" + KEY)
        self.assertEqual(discover_board_links("acme.com"), [("workday", KEY, "https://acme.com/careers")])


if __name__ == "__main__":
    unittest.main()
