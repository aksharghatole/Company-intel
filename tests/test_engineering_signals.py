import unittest

from technographics import scan_jobs_for_tech, summarize_evidence


def job(content, url="https://example.com/jobs/1", title="Engineer"):
    return {"title": title, "content": content, "url": url}


class EngineeringSignalsTests(unittest.TestCase):
    def test_aliases_and_html(self):
        result = scan_jobs_for_tech([job("Dassault <b>3DX</b> and ENOVIA; PCB&nbsp;layout; FreeRTOS")])
        self.assertIn("3DEXPERIENCE", result["PLM"])
        self.assertIn("ENOVIA", result["PLM"])
        self.assertIn("PCB design", result["Embedded"])
        self.assertIn("FreeRTOS", result["Embedded"])
        self.assertEqual(result["PLM"]["3DEXPERIENCE"][0]["matched_term"], "3DX")
        self.assertNotIn("<b>", result["PLM"]["3DEXPERIENCE"][0]["snippet"])

    def test_ambiguous_terms_not_matches(self):
        result = scan_jobs_for_tech([job("A typical workday; an inventor; watch Plex; 3DX")])
        self.assertEqual(result, {})

    def test_later_valid_context(self):
        result = scan_jobs_for_tech([job("3DX " + "x " * 100 + " PLM platform 3DX")])
        self.assertIn("3DEXPERIENCE", result["PLM"])

    def test_null_content(self):
        self.assertEqual(scan_jobs_for_tech([{"title": None, "content": None}]), {})

    def test_corroboration_deduplicates_job_links(self):
        result = scan_jobs_for_tech([job("Firmware"), job("Firmware"), job("Firmware", "https://example.com/jobs/2")])
        strength = summarize_evidence(result)["Embedded"]["Firmware"]
        self.assertEqual(strength["distinct_job_links"], 2)
        self.assertEqual(strength["strength"], "multiple job links")


if __name__ == "__main__":
    unittest.main()
