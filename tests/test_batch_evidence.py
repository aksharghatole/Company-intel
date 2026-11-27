import io
import json
import unittest
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

from batch import scan_one, scan_dataframe, results_to_csv_bytes, results_to_excel_bytes


class BatchEvidenceTests(unittest.TestCase):
    @patch("batch.get_tech_stack", return_value={"detected": []})
    @patch("batch.get_hiring_signals", return_value={})
    @patch("batch.get_firmographics", return_value={})
    @patch("batch.scan_technographics_free")
    def test_ats_evidence_export(self, ats, firm, hiring, tech):
        job = {"job_title": "Engineer", "url": "https://example.com/jobs/1"}
        ats.return_value = {"ats_detected": "greenhouse:acme", "jobs_scanned": 3,
                            "from_jobs": {"PLM": {"ENOVIA": [job, job]}}}
        row = scan_one({"company": "Acme", "domain": "example.com"})
        self.assertEqual(row["plm_vendors"], "ENOVIA")
        self.assertEqual(row["ats_jobs_scanned"], 3)
        self.assertEqual(row["evidence_count"], 1)
        self.assertEqual(json.loads(row["job_evidence_json"])[0]["url"], job["url"])
        book = load_workbook(io.BytesIO(results_to_excel_bytes(pd.DataFrame([row]))))
        self.assertEqual(book.sheetnames, ["Company Intel", "Job Evidence"])
        self.assertEqual(book["Job Evidence"]["F2"].value, job["url"])

    @patch("batch.scan_one")
    def test_input_order_and_failed_row(self, scan):
        def fake(row):
            if row["company"] == "B":
                raise RuntimeError("failed")
            return row
        scan.side_effect = fake
        df = pd.DataFrame([{"company": name, "domain": "example.com"} for name in "ABC"])
        result = scan_dataframe(df, max_workers=3, delay=0)
        self.assertEqual(result["company"].tolist(), ["A", "B", "C"])
        self.assertEqual(result.loc[1, "error"], "failed")

    def test_formula_safety(self):
        df = pd.DataFrame([{"company": "=1+1", "domain": "example.com"}])
        self.assertIn("'=1+1", results_to_csv_bytes(df).decode())
        workbook = load_workbook(io.BytesIO(results_to_excel_bytes(df)))
        self.assertEqual(workbook["Company Intel"]["A2"].data_type, "s")


if __name__ == "__main__":
    unittest.main()
