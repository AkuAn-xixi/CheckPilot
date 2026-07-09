import tempfile
import unittest
from pathlib import Path

from backend.app.api import reports


class ReportsApiTests(unittest.TestCase):
    def test_create_report_persists_default_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reports.report_service.reports_root = Path(tmp_dir)
            reports.report_service.reports_root.mkdir(parents=True, exist_ok=True)

            result = reports.create_report(
                reports.ReportCreateRequest(title="ASR 冒烟报告", template_key="default", kind="asr")
            )

            report = result["report"]
            self.assertEqual(result["status"], "success")
            self.assertEqual(report["title"], "ASR 冒烟报告")
            self.assertEqual(report["kind"], "asr")
            self.assertEqual(report["template_key"], "default")
            self.assertEqual(report["status"], "draft")
            self.assertGreaterEqual(len(report["sections"]), 4)
            self.assertTrue(Path(report["file_path"]).exists())
            self.assertEqual(Path(report["file_path"]).suffix, ".html")
            self.assertTrue(report["report_url"].endswith(".html"))
            self.assertIn("<html", Path(report["file_path"]).read_text(encoding="utf-8"))

    def test_overview_and_detail_return_created_report(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reports.report_service.reports_root = Path(tmp_dir)
            reports.report_service.reports_root.mkdir(parents=True, exist_ok=True)

            created = reports.create_report(
                reports.ReportCreateRequest(title="设备回归", template_key="blank", kind="device")
            )["report"]

            overview = reports.get_reports_overview()
            listing = reports.list_reports()
            detail = reports.get_report(created["report_id"])

            self.assertEqual(overview["status"], "success")
            self.assertEqual(overview["stats"]["report_count"], 1)
            self.assertEqual(len(overview["recent_reports"]), 1)
            self.assertEqual(listing["reports"][0]["report_id"], created["report_id"])
            self.assertEqual(detail["report"]["report_id"], created["report_id"])
            self.assertEqual(detail["report"]["template_key"], "blank")
            self.assertTrue(detail["report"]["report_url"].endswith(".html"))

    def test_create_asr_batch_report_renders_html_template(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reports.report_service.reports_root = Path(tmp_dir)
            reports.report_service.reports_root.mkdir(parents=True, exist_ok=True)

            result = reports.create_asr_batch_report(
                reports.AsrBatchReportCreateRequest(
                    title="ASR 全量执行",
                    file_name="demo.xlsx",
                    label="全部用例",
                    device="device-001",
                    model_name="Qwen-ASR",
                    row_results=[
                        reports.AsrBatchCaseResult(row_index=1, case_title="UC-1", asr_result="PASS", asr_score=0.98, transcribed_text="hello", tts_text="hello", audio_path="audio/uc1.wav", transcript_path="results/uc1.txt"),
                        reports.AsrBatchCaseResult(row_index=2, case_title="UC-2", asr_result="FAIL", asr_score=0.42, transcribed_text="world", tts_text="hello", compare_result_path="results/uc2_compare.txt", reference_path="references/uc2.txt", note="文本不一致"),
                    ],
                    execution_logs=[
                        reports.ReportLogEntry(status="info", message="开始批量执行"),
                        reports.ReportLogEntry(status="success", message="执行完成"),
                    ],
                )
            )

            report = result["report"]
            html_content = Path(report["file_path"]).read_text(encoding="utf-8")
            self.assertEqual(report["kind"], "asr-batch")
            self.assertEqual(report["template_key"], "asr")
            self.assertEqual(report["status"], "published")
            self.assertEqual(report["summary"]["total"], 2)
            self.assertEqual(report["summary"]["passed"], 1)
            self.assertEqual(report["summary"]["failed"], 1)
            self.assertIn("ASR 全量执行", html_content)
            self.assertIn("UC-1", html_content)
            self.assertIn("开始批量执行", html_content)
            self.assertIn("结论与建议", html_content)
            self.assertIn("附件与证据", html_content)
            self.assertIn("report-table-row-fail", html_content)
            self.assertIn("results/uc2_compare.txt", html_content)
            self.assertTrue(report["report_url"].endswith(".html"))

    def test_create_excel_batch_report_renders_case_rows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            reports.report_service.reports_root = Path(tmp_dir)
            reports.report_service.reports_root.mkdir(parents=True, exist_ok=True)

            result = reports.create_excel_batch_report(
                reports.ExcelBatchReportCreateRequest(
                    title="图片批量执行",
                    file_name="demo.xlsx",
                    label="全部用例",
                    device="device-001",
                    row_results=[
                        reports.ExcelBatchCaseResult(row_index=1, case_title="TC-001", verify_result="PASS", score=0.97, detail="相似度 97.00%"),
                        reports.ExcelBatchCaseResult(row_index=2, case_title="TC-002", verify_result="FAIL", score=0.42, detail="图标不匹配，当前相似度 42.00%"),
                    ],
                    execution_logs=[
                        reports.ReportLogEntry(status="info", message="开始批量执行"),
                        reports.ReportLogEntry(status="success", message="执行完成"),
                    ],
                )
            )

            report = result["report"]
            html_content = Path(report["file_path"]).read_text(encoding="utf-8")
            self.assertEqual(report["kind"], "excel-batch")
            self.assertEqual(report["status"], "published")
            self.assertEqual(report["summary"]["total"], 2)
            self.assertEqual(report["summary"]["passed"], 1)
            self.assertEqual(report["summary"]["failed"], 1)
            self.assertIn("图片批量执行", html_content)
            self.assertIn("TC-001", html_content)
            self.assertIn("测试结果", html_content)
            self.assertIn("结果细节", html_content)
            self.assertIn("图标不匹配", html_content)
            self.assertTrue(report["report_url"].endswith(".html"))


if __name__ == "__main__":
    unittest.main()