"""Standalone HTML reporting service."""
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ..config import settings


class ReportNotFoundError(FileNotFoundError):
    """Raised when a requested report file does not exist."""


class InvalidReportTemplateError(ValueError):
    """Raised when a requested report template key is unsupported."""


REPORT_DATA_PATTERN = re.compile(
    r'<script id="report-data" type="application/json">(?P<data>.*?)</script>',
    re.DOTALL,
)


class ReportService:
    def __init__(self, reports_root: Path | None = None):
        self.reports_root = Path(reports_root or settings.REPORTS_DIR)
        self.reports_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_title(title: str) -> str:
        normalized = str(title or "").strip()
        return normalized or "未命名测试报告"

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower())
        return normalized.strip("-") or "draft"

    def _report_file(self, report_id: str) -> Path:
        sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "", str(report_id or "").strip())
        if not sanitized:
            raise ReportNotFoundError("报告 ID 无效")
        return self.reports_root / f"{sanitized}.html"

    @staticmethod
    def _report_url(report_id: str) -> str:
        return f"/report-files/{report_id}.html"

    def _read_payload(self, file_path: Path) -> dict[str, Any]:
        try:
            raw_html = file_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ReportNotFoundError(f"未找到报告: {file_path.stem}") from exc
        except OSError as exc:
            raise ValueError(f"报告文件损坏: {file_path}") from exc

        match = REPORT_DATA_PATTERN.search(raw_html)
        if not match:
            raise ValueError(f"报告文件格式错误: {file_path}")

        try:
            payload = json.loads(match.group("data"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"报告文件数据损坏: {file_path}") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"报告文件格式错误: {file_path}")
        return payload

    def _write_report_file(self, file_path: Path, payload: dict[str, Any]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.render_report_html(payload), encoding="utf-8")

    def list_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "default",
                "label": "默认骨架",
                "description": "包含用例明细、附件占位和结论模块，适合继续扩展执行数据。",
                "sections": ["cases", "artifacts", "conclusion"],
            },
            {
                "key": "asr",
                "label": "ASR 执行报告",
                "description": "适合承载 ASR 全量执行结果，内置用例明细、执行日志和结论模块。",
                "sections": ["cases", "artifacts", "logs", "conclusion"],
            },
            {
                "key": "blank",
                "label": "空白骨架",
                "description": "仅创建最小元信息和空 section 列表，适合完全自定义。",
                "sections": [],
            },
        ]

    def _build_default_sections(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "cases",
                "title": "用例明细",
                "type": "table",
                "columns": [
                    {"key": "case_id", "label": "用例 ID"},
                    {"key": "title", "label": "标题"},
                    {"key": "status", "label": "状态"},
                    {"key": "duration_ms", "label": "耗时(ms)"},
                    {"key": "note", "label": "备注"},
                ],
                "rows": [],
            },
            {
                "id": "artifacts",
                "title": "附件",
                "type": "attachments",
                "items": [],
            },
            {
                "id": "conclusion",
                "title": "结论与建议",
                "type": "summary",
                "blocks": [
                    {
                        "id": "overall",
                        "title": "总体结论",
                        "content": "在这里总结本次测试结论，并标记是否具备继续流转条件。",
                    },
                    {
                        "id": "next_actions",
                        "title": "后续动作",
                        "fields": [
                            {"key": "recommendation", "label": "发布建议", "value": "待评估"},
                            {"key": "owner", "label": "责任归属", "value": "待补充"},
                            {"key": "eta", "label": "预计完成", "value": "待补充"},
                        ],
                    },
                ],
            },
        ]

    def _build_asr_sections(
        self,
        *,
        file_name: str = "",
        batch_label: str = "",
        device: str = "",
        model_name: str = "",
        row_results: list[dict[str, Any]] | None = None,
        artifact_items: list[dict[str, Any]] | None = None,
        execution_logs: list[dict[str, Any]] | None = None,
        conclusion_blocks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": "cases",
                "title": "用例明细",
                "type": "table",
                "columns": [
                    {"key": "row_index", "label": "行号"},
                    {"key": "case_title", "label": "用例标题"},
                    {"key": "status", "label": "状态"},
                    {"key": "score", "label": "得分"},
                    {"key": "transcribed_text", "label": "识别文本"},
                    {"key": "tts_text", "label": "TTS 文本"},
                    {"key": "note", "label": "备注"},
                ],
                "rows": row_results or [],
            },
            {
                "id": "artifacts",
                "title": "附件与证据",
                "type": "attachments",
                "items": artifact_items or [],
            },
            {
                "id": "logs",
                "title": "执行日志",
                "type": "log",
                "items": execution_logs or [],
            },
            {
                "id": "conclusion",
                "title": "结论与建议",
                "type": "summary",
                "blocks": conclusion_blocks or [
                    {
                        "id": "overall",
                        "title": "总体结论",
                        "content": "批量执行完成后，这里会汇总最终结论与处置建议。",
                    }
                ],
            },
        ]

    def _build_excel_batch_sections(
        self,
        *,
        file_name: str = "",
        batch_label: str = "",
        device: str = "",
        row_results: list[dict[str, Any]] | None = None,
        execution_logs: list[dict[str, Any]] | None = None,
        conclusion_blocks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": "cases",
                "title": "用例明细",
                "type": "table",
                "columns": [
                    {"key": "row_index", "label": "行号"},
                    {"key": "case_title", "label": "测试ID"},
                    {"key": "status", "label": "测试结果"},
                    {"key": "detail", "label": "结果细节"},
                ],
                "rows": row_results or [],
            },
            {
                "id": "conclusion",
                "title": "结论与建议",
                "type": "summary",
                "blocks": conclusion_blocks or [
                    {
                        "id": "overall",
                        "title": "总体结论",
                        "content": "图片校验批量执行完成后，这里会汇总整体结果与后续建议。",
                    }
                ],
            },
        ]

    def build_report_payload(
        self,
        *,
        title: str,
        template_key: str = "default",
        kind: str = "custom",
        status: str = "draft",
        metadata: dict[str, Any] | None = None,
        summary: dict[str, Any] | None = None,
        sections: list[dict[str, Any]] | None = None,
        runs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_title = self._normalize_title(title)
        normalized_template = str(template_key or "default").strip().lower() or "default"
        timestamp = self._now().isoformat()

        if sections is None:
            if normalized_template == "default":
                sections = self._build_default_sections()
            elif normalized_template == "asr":
                sections = self._build_asr_sections()
            elif normalized_template == "blank":
                sections = []
            else:
                raise InvalidReportTemplateError(f"不支持的报告模板: {template_key}")

        normalized_summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "pass_rate": 0,
        }
        if isinstance(summary, dict):
            normalized_summary.update(summary)

        normalized_metadata = {
            "owner": "",
            "source": "manual",
            "tags": [],
        }
        if isinstance(metadata, dict):
            normalized_metadata.update(metadata)

        return {
            "report_id": "",
            "title": normalized_title,
            "kind": str(kind or "custom").strip() or "custom",
            "template_key": normalized_template,
            "status": str(status or "draft").strip() or "draft",
            "created_at": timestamp,
            "updated_at": timestamp,
            "metadata": normalized_metadata,
            "summary": normalized_summary,
            "sections": sections,
            "runs": list(runs or []),
        }

    def _next_report_id(self, title: str) -> str:
        timestamp = self._now().strftime("%Y%m%d_%H%M%S")
        slug = self._slugify(title)[:32]
        base_id = f"report_{timestamp}_{slug}"
        candidate = base_id
        suffix = 1
        while self._report_file(candidate).exists():
            suffix += 1
            candidate = f"{base_id}_{suffix}"
        return candidate

    def _summarize_report(self, payload: dict[str, Any], file_path: Path) -> dict[str, Any]:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
        return {
            "report_id": str(payload.get("report_id") or file_path.stem),
            "title": str(payload.get("title") or file_path.stem),
            "kind": str(payload.get("kind") or "custom"),
            "template_key": str(payload.get("template_key") or "default"),
            "status": str(payload.get("status") or "draft"),
            "created_at": str(payload.get("created_at") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
            "section_count": len(sections),
            "summary": {
                "total": int(summary.get("total") or 0),
                "passed": int(summary.get("passed") or 0),
                "failed": int(summary.get("failed") or 0),
                "blocked": int(summary.get("blocked") or 0),
            },
            "file_path": str(file_path),
            "report_url": self._report_url(str(payload.get("report_id") or file_path.stem)),
        }

    def create_report(
        self,
        *,
        title: str,
        template_key: str = "default",
        kind: str = "custom",
    ) -> dict[str, Any]:
        payload = self.build_report_payload(title=title, template_key=template_key, kind=kind)
        report_id = self._next_report_id(payload["title"])
        payload["report_id"] = report_id
        file_path = self._report_file(report_id)
        self._write_report_file(file_path, payload)
        payload["file_path"] = str(file_path)
        payload["report_url"] = self._report_url(report_id)
        return payload

    def create_asr_batch_report(
        self,
        *,
        title: str,
        file_name: str,
        batch_label: str,
        device: str,
        model_name: str,
        row_results: list[dict[str, Any]],
        execution_logs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_rows: list[dict[str, Any]] = []
        passed = 0
        failed = 0
        blocked = 0
        no_ref = 0
        logs_by_row = self._group_execution_logs_by_row(execution_logs)

        for item in row_results:
            status = str(item.get("asr_result") or item.get("status") or "UNKNOWN").strip().upper() or "UNKNOWN"
            if status == "PASS":
                passed += 1
            elif status == "FAIL":
                failed += 1
            else:
                blocked += 1
                if status == "NO_REF":
                    no_ref += 1

            score = item.get("asr_score")
            row_index = int(item.get("row_index") or 0)
            transcript_path = str(item.get("transcript_path") or "").strip()
            compare_result_path = str(item.get("compare_result_path") or "").strip()
            normalized_rows.append({
                "row_index": row_index,
                "case_title": str(item.get("case_title") or item.get("title") or "").strip(),
                "status": status,
                "score": score,
                "transcribed_text": str(item.get("transcribed_text") or "").strip(),
                "tts_text": str(item.get("tts_text") or "").strip(),
                "reference_text": str(item.get("reference_text") or "").strip(),
                "reference_path": str(item.get("reference_path") or "").strip(),
                "audio_path": str(item.get("audio_path") or "").strip(),
                "transcript_path": transcript_path,
                "transcript_preview": self._read_text_artifact_preview(transcript_path),
                "compare_result_path": compare_result_path,
                "compare_result_preview": self._read_text_artifact_preview(compare_result_path),
                "note": str(item.get("note") or "").strip(),
                "execution_logs": logs_by_row.get(row_index, []),
                "case_detail_id": f"asr-row-{row_index}",
            })

        total = len(normalized_rows)
        pass_rate = round((passed / total) * 100, 2) if total else 0
        summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "pass_rate": pass_rate,
            "no_ref": no_ref,
        }
        artifact_items = self._build_asr_artifact_items(normalized_rows)
        failure_rows = [item for item in normalized_rows if self._status_tone(item.get("status")) == "fail"]
        conclusion_blocks = self._build_asr_conclusion_blocks(
            summary=summary,
            failure_rows=failure_rows,
            artifact_count=len(artifact_items),
        )
        sections = self._build_asr_sections(
            file_name=file_name,
            batch_label=batch_label,
            device=device,
            model_name=model_name,
            row_results=normalized_rows,
            artifact_items=artifact_items,
            execution_logs=list(execution_logs or []),
            conclusion_blocks=conclusion_blocks,
        )
        metrics_section = next((section for section in sections if section.get("id") == "metrics"), None)
        if isinstance(metrics_section, dict):
            metrics_section["items"] = [
                {"key": "total", "label": "总用例", "value": total},
                {"key": "passed", "label": "通过", "value": passed},
                {"key": "failed", "label": "失败", "value": failed},
                {"key": "no_ref", "label": "缺参考", "value": no_ref},
                {"key": "pass_rate", "label": "通过率", "value": f"{pass_rate:.2f}%"},
            ]

        payload = self.build_report_payload(
            title=title,
            template_key="asr",
            kind="asr-batch",
            status="published",
            metadata={
                "source": "excel-asr-batch",
                "tags": ["asr", "batch"],
                "device": device,
                "model_name": model_name,
                "file_name": file_name,
            },
            summary=summary,
            sections=sections,
            runs=normalized_rows,
        )
        report_id = self._next_report_id(payload["title"])
        payload["report_id"] = report_id
        payload["updated_at"] = self._now().isoformat()
        file_path = self._report_file(report_id)
        self._write_report_file(file_path, payload)
        payload["file_path"] = str(file_path)
        payload["report_url"] = self._report_url(report_id)
        return payload

    def create_excel_batch_report(
        self,
        *,
        title: str,
        file_name: str,
        batch_label: str,
        device: str,
        row_results: list[dict[str, Any]],
        execution_logs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_rows: list[dict[str, Any]] = []
        passed = 0
        failed = 0
        blocked = 0
        logs_by_row = self._group_execution_logs_by_row(execution_logs)

        for item in row_results:
            status = self._normalize_status(item.get("verify_result") or item.get("status"))
            if status == "PASS":
                passed += 1
            elif status in {"FAIL", "ERROR"}:
                failed += 1
            else:
                blocked += 1

            score = item.get("score")
            detail = str(item.get("detail") or "").strip()
            if not detail:
                detail = f"相似度 {self._format_scalar(score)}" if score not in (None, "") else "未返回校验细节"

            row_index = int(item.get("row_index") or 0)
            verify_image = str(item.get("verify_image") or "").strip()
            verify_image_data_url = str(item.get("verify_image_data_url") or "").strip()
            compare_details = self._normalize_compare_details(item.get("compare_details"))

            # 处理多次执行轮次
            raw_runs = item.get("runs") or []
            runs = []
            if raw_runs:
                for run in raw_runs:
                    run_logs = run.get("execution_logs") or []
                    runs.append({
                        "run_index": run.get("run_index", len(runs) + 1),
                        "status": self._normalize_status(run.get("status") or status),
                        "score": run.get("score"),
                        "detail": str(run.get("detail") or "").strip(),
                        "screenshot_url": str(run.get("screenshot_url") or "").strip(),
                        "video_url": str(run.get("video_url") or "").strip(),
                        "compare_engine": str(run.get("compare_engine") or "").strip(),
                        "model_name": str(run.get("model_name") or "").strip(),
                        "compare_details": self._normalize_compare_details(run.get("compare_details")),
                        "execution_logs": run_logs,
                    })

            normalized_rows.append({
                "row_index": row_index,
                "case_title": str(item.get("case_title") or item.get("title") or "").strip(),
                "status": status,
                "score": score,
                "detail": detail,
                "verify_image": verify_image,
                "verify_image_url": verify_image_data_url or self._build_excel_verify_image_url(file_name, verify_image),
                "screenshot_url": str(item.get("screenshot_url") or "").strip(),
                "video_url": str(item.get("video_url") or "").strip(),
                "compare_engine": str(item.get("compare_engine") or "").strip(),
                "model_name": str(item.get("model_name") or "").strip(),
                "compare_details": compare_details,
                "execution_logs": logs_by_row.get(row_index, []),
                "case_detail_id": f"excel-row-{row_index}",
                "runs": runs,
            })

        total = len(normalized_rows)
        pass_rate = round((passed / total) * 100, 2) if total else 0
        summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "pass_rate": pass_rate,
        }
        failure_rows = [item for item in normalized_rows if self._status_tone(item.get("status")) == "fail"]
        conclusion_blocks = [
            {
                "id": "overall",
                "title": "总体结论",
                "content": f"本次共执行 {total} 条图片校验用例，通过 {passed} 条，失败 {failed} 条，未完成 {blocked} 条。",
            },
            {
                "id": "failure_focus",
                "title": "失败关注项",
                "fields": [
                    {
                        "key": f"failure_{index + 1}",
                        "label": item.get("case_title") or f"第 {item.get('row_index') or '-'} 行",
                        "value": item.get("detail") or self._status_label(item.get("status")),
                    }
                    for index, item in enumerate(failure_rows[:5])
                ] or [
                    {"key": "failures", "label": "失败用例", "value": "无"}
                ],
            },
        ]
        sections = self._build_excel_batch_sections(
            file_name=file_name,
            batch_label=batch_label,
            device=device,
            row_results=normalized_rows,
            execution_logs=list(execution_logs or []),
            conclusion_blocks=conclusion_blocks,
        )

        payload = self.build_report_payload(
            title=title,
            template_key="default",
            kind="excel-batch",
            status="published",
            metadata={
                "source": "excel-image-batch",
                "tags": ["excel", "image", "batch"],
                "device": device,
                "file_name": file_name,
            },
            summary=summary,
            sections=sections,
            runs=normalized_rows,
        )
        report_id = self._next_report_id(payload["title"])
        payload["report_id"] = report_id
        payload["updated_at"] = self._now().isoformat()
        file_path = self._report_file(report_id)
        self._write_report_file(file_path, payload)
        payload["file_path"] = str(file_path)
        payload["report_url"] = self._report_url(report_id)
        return payload

    def list_reports(self) -> list[dict[str, Any]]:
        self.reports_root.mkdir(parents=True, exist_ok=True)
        reports: list[dict[str, Any]] = []
        for file_path in self.reports_root.glob("*.html"):
            try:
                payload = self._read_payload(file_path)
            except ValueError:
                continue
            reports.append(self._summarize_report(payload, file_path))

        reports.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return reports

    def get_report(self, report_id: str) -> dict[str, Any]:
        file_path = self._report_file(report_id)
        payload = self._read_payload(file_path)
        payload["report_id"] = str(payload.get("report_id") or report_id)
        payload["file_path"] = str(file_path)
        payload["report_url"] = self._report_url(payload["report_id"])
        return payload

    def delete_report(self, report_id: str) -> dict[str, Any]:
        file_path = self._report_file(report_id)
        if not file_path.exists():
            raise ReportNotFoundError(f"未找到报告: {report_id}")

        title = report_id
        associated_files: list[Path] = []
        try:
            payload = self._read_payload(file_path)
            title = self._normalize_title(str(payload.get("title") or report_id))
            # 收集报告中引用的录音、识别文本、比对结果等文件
            for section in payload.get("sections", []):
                for row in section.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    for key in ("audio_path", "transcript_path", "compare_result_path"):
                        p = str(row.get(key) or "").strip()
                        if p:
                            associated_files.append(Path(p))
        except ValueError:
            title = report_id

        # 删除报告文件
        try:
            file_path.unlink()
        except FileNotFoundError as exc:
            raise ReportNotFoundError(f"未找到报告: {report_id}") from exc
        except OSError as exc:
            raise ValueError(f"删除报告失败: {file_path}") from exc

        # 删除关联的录音/识别/比对文件
        deleted_files = []
        for f in associated_files:
            try:
                if f.exists():
                    f.unlink()
                    deleted_files.append(str(f))
            except OSError:
                pass

        return {
            "report_id": report_id,
            "title": title,
            "file_path": str(file_path),
            "deleted_files": deleted_files,
        }

    def delete_reports(self, report_ids: list[str]) -> dict[str, Any]:
        """批量删除报告：逐个尽力删除（含关联文件），单个失败不中断，返回成功/失败清单。"""
        deleted: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for report_id in report_ids:
            normalized = str(report_id or "").strip()
            if not normalized:
                continue
            try:
                deleted.append(self.delete_report(normalized))
            except (ReportNotFoundError, ValueError) as exc:
                failed.append({"report_id": normalized, "detail": str(exc)})
        return {"deleted": deleted, "failed": failed}

    def get_overview(self) -> dict[str, Any]:
        reports = self.list_reports()
        totals = {
            "report_count": len(reports),
            "draft_count": sum(1 for item in reports if item.get("status") == "draft"),
            "published_count": sum(1 for item in reports if item.get("status") == "published"),
            "total_cases": sum(int(item.get("summary", {}).get("total") or 0) for item in reports),
            "passed_cases": sum(int(item.get("summary", {}).get("passed") or 0) for item in reports),
            "failed_cases": sum(int(item.get("summary", {}).get("failed") or 0) for item in reports),
        }
        return {
            "stats": totals,
            "recent_reports": reports[:5],
        }

    @staticmethod
    def _format_scalar(value: Any) -> str:
        if value in (None, ""):
            return "-"
        if isinstance(value, float):
            return f"{value * 100:.2f}%" if 0 <= value <= 1 else f"{value:.2f}"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _normalize_status(value: Any) -> str:
        normalized = str(value or "").strip().upper()
        return normalized or "UNKNOWN"

    def _status_tone(self, value: Any) -> str:
        status = self._normalize_status(value)
        if status == "PASS":
            return "pass"
        if status in {"FAIL", "ERROR"}:
            return "fail"
        if status in {"NO_REF", "BLOCKED", "SKIPPED"}:
            return "warning"
        if status == "UNKNOWN":
            return "muted"
        return "info"

    def _status_label(self, value: Any) -> str:
        status = self._normalize_status(value)
        mapping = {
            "PASS": "通过",
            "FAIL": "失败",
            "ERROR": "异常",
            "NO_REF": "缺参考",
            "BLOCKED": "阻塞",
            "SKIPPED": "跳过",
            "UNKNOWN": "待确认",
        }
        return mapping.get(status, status)

    @staticmethod
    def _case_title(row: dict[str, Any]) -> str:
        title = str(row.get("case_title") or row.get("title") or "").strip()
        if title:
            return title
        row_index = row.get("row_index")
        if row_index not in (None, ""):
            return f"第 {row_index} 行"
        return "未命名用例"

    def _collect_case_rows(self, payload: dict[str, Any], sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        runs = payload.get("runs")
        if isinstance(runs, list) and runs:
            return [item for item in runs if isinstance(item, dict)]

        for section in sections:
            if str(section.get("id") or "").strip().lower() != "cases":
                continue
            rows = section.get("rows")
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        return []

    def _collect_overview_fields(self, payload: dict[str, Any], sections: list[dict[str, Any]]) -> list[dict[str, str]]:
        collected: list[dict[str, str]] = []
        seen: set[str] = set()

        def add_field(label: str, value: Any) -> None:
            normalized_label = str(label or "").strip()
            formatted = self._format_scalar(value)
            if not normalized_label or formatted == "-" or normalized_label in seen:
                return
            seen.add(normalized_label)
            collected.append({"label": normalized_label, "value": formatted})

        for section in sections:
            if str(section.get("id") or "").strip().lower() != "overview":
                continue
            for block in section.get("blocks", []):
                if not isinstance(block, dict):
                    continue
                for field in block.get("fields", []):
                    if not isinstance(field, dict):
                        continue
                    add_field(str(field.get("label") or field.get("key") or "字段"), field.get("value"))

        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        add_field("执行人", metadata.get("owner"))
        add_field("数据来源", metadata.get("source"))
        if isinstance(metadata.get("tags"), list) and metadata.get("tags"):
            add_field("标签", ", ".join(str(item).strip() for item in metadata["tags"] if str(item).strip()))

        return collected[:8]

    def _derive_verdict(self, summary: dict[str, Any]) -> dict[str, str]:
        total = int(summary.get("total") or 0)
        passed = int(summary.get("passed") or 0)
        failed = int(summary.get("failed") or 0)
        blocked = int(summary.get("blocked") or 0)
        pass_rate = float(summary.get("pass_rate") or 0)

        if total == 0:
            return {
                "tone": "muted",
                "title": "待补充执行结果",
                "detail": "当前报告已生成，但还没有足以输出正式判断的执行数据。",
                "recommendation": "补充执行结果后再做发布或提测结论。",
            }
        if failed > 0:
            return {
                "tone": "fail",
                "title": "需修复后复测",
                "detail": f"本次共执行 {total} 条用例，其中 {failed} 条失败，当前结果不建议直接流转。",
                "recommendation": "优先修复失败项并回归，再评估是否具备提测或发布条件。",
            }
        if blocked > 0:
            return {
                "tone": "warning",
                "title": "存在阻塞项",
                "detail": f"本次已通过 {passed} 条，但仍有 {blocked} 条阻塞或待确认结果。",
                "recommendation": "补齐阻塞项后再给出最终准入结论。",
            }
        if total == passed:
            return {
                "tone": "pass",
                "title": "结果稳定，可进入下一阶段",
                "detail": f"本次执行 {total} 条用例全部通过，通过率 {pass_rate:.2f}%。",
                "recommendation": "可按既定流程进入下一轮验证、提测或发布评审。",
            }
        return {
            "tone": "info",
            "title": "建议复核后确认",
            "detail": f"当前通过 {passed}/{total} 条用例，仍需结合环境信息做最终判断。",
            "recommendation": "建议补齐关键信息后再输出正式结论。",
        }

    def _build_asr_artifact_items(self, row_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        artifact_specs = [
            ("audio_path", "录音文件", "audio"),
            ("transcript_path", "识别文本", "transcript"),
            ("compare_result_path", "比对结果", "compare"),
            ("reference_path", "参考文本", "reference"),
        ]

        for item in row_results:
            case_title = self._case_title(item)
            for key, label, kind in artifact_specs:
                value = str(item.get(key) or "").strip()
                if not value:
                    continue
                dedupe_key = (kind, value)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                artifacts.append(
                    {
                        "name": f"{case_title} · {label}",
                        "path": value,
                        "kind": kind,
                        "detail": f"来源用例：{case_title}",
                    }
                )
        return artifacts

    def _build_asr_conclusion_blocks(
        self,
        *,
        summary: dict[str, Any],
        failure_rows: list[dict[str, Any]],
        artifact_count: int,
    ) -> list[dict[str, Any]]:
        verdict = self._derive_verdict(summary)
        focus_items = "、".join(self._case_title(item) for item in failure_rows[:3]) or "无"
        return [
            {
                "id": "overall",
                "title": "总体结论",
                "content": verdict["detail"],
            },
            {
                "id": "next_actions",
                "title": "后续动作",
                "fields": [
                    {"key": "recommendation", "label": "发布建议", "value": verdict["recommendation"]},
                    {"key": "focus", "label": "重点关注", "value": focus_items},
                    {"key": "artifact_count", "label": "证据数量", "value": artifact_count},
                ],
            },
        ]

    def _collect_artifact_items(self, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for section in sections:
            if str(section.get("id") or "").strip().lower() != "artifacts":
                continue
            items = section.get("items")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    @staticmethod
    def _build_excel_verify_image_url(file_name: str, image_name: str) -> str:
        normalized_file_name = str(file_name or "").strip()
        normalized_image_name = str(image_name or "").strip()
        if not normalized_file_name or not normalized_image_name:
            return ""
        return f"/api/excel/verify_image?{urlencode({'file_name': normalized_file_name, 'image_name': normalized_image_name})}"

    @staticmethod
    def _normalize_compare_details(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}

        normalized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key or "").strip()
            if not normalized_key or item in (None, ""):
                continue
            if isinstance(item, (str, int, float, bool)):
                normalized[normalized_key] = item
        return normalized

    def _group_execution_logs_by_row(self, execution_logs: list[dict[str, Any]] | None) -> dict[int, list[dict[str, Any]]]:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for item in execution_logs or []:
            if not isinstance(item, dict):
                continue

            try:
                row_index = int(item.get("row_index") or 0)
            except (TypeError, ValueError):
                row_index = 0

            if row_index <= 0:
                continue

            normalized_item = {
                "status": str(item.get("status") or "info").strip().lower() or "info",
                "message": str(item.get("message") or "").strip(),
                "happened_at": str(item.get("happened_at") or "").strip(),
            }
            if not normalized_item["message"]:
                continue

            grouped.setdefault(row_index, []).append(normalized_item)

        return grouped

    @staticmethod
    def _read_text_artifact_preview(path_value: str, max_length: int = 4000) -> str:
        path_text = str(path_value or "").strip()
        if not path_text:
            return ""

        try:
            file_path = Path(path_text)
            if not file_path.exists() or not file_path.is_file():
                return ""
            content = file_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            return ""

        if len(content) <= max_length:
            return content
        return content[:max_length].rstrip() + "\n..."

    def _render_summary_blocks(self, blocks: list[dict[str, Any]]) -> str:
        if not blocks:
            return '<div class="report-empty">暂无摘要内容。</div>'

        html_blocks: list[str] = []
        for block in blocks:
            title = escape(str(block.get("title") or "摘要"))
            if isinstance(block.get("fields"), list):
                field_items = "".join(
                    (
                        '<div class="report-field-item">'
                        f'<span>{escape(str(item.get("label") or item.get("key") or "字段"))}</span>'
                        f'<strong>{escape(self._format_scalar(item.get("value")))}</strong>'
                        '</div>'
                    )
                    for item in block.get("fields", [])
                )
                html_blocks.append(
                    '<section class="report-block">'
                    f'<h3>{title}</h3>'
                    f'<div class="report-field-grid">{field_items}</div>'
                    '</section>'
                )
                continue

            content = escape(str(block.get("content") or "-"))
            html_blocks.append(
                '<section class="report-block">'
                f'<h3>{title}</h3>'
                f'<p>{content}</p>'
                '</section>'
            )
        return "".join(html_blocks)

    def _render_metrics_items(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return '<div class="report-empty">暂无指标。</div>'
        return '<div class="report-metric-grid">' + ''.join(
            (
                '<div class="report-metric-card">'
                f'<span>{escape(str(item.get("label") or item.get("key") or "指标"))}</span>'
                f'<strong>{escape(self._format_scalar(item.get("value")))}</strong>'
                '</div>'
            )
            for item in items
        ) + '</div>'

    def _render_excel_case_detail(self, row: dict[str, Any]) -> str:
        verify_image_name = str(row.get("verify_image") or "").strip()
        verify_image_url = str(row.get("verify_image_url") or "").strip()

        runs = row.get("runs") or []
        if not runs:
            runs = [{
                "run_index": 1,
                "status": row.get("status"),
                "score": row.get("score"),
                "detail": row.get("detail"),
                "screenshot_url": str(row.get("screenshot_url") or "").strip(),
                "compare_engine": row.get("compare_engine"),
                "model_name": row.get("model_name"),
                "compare_details": row.get("compare_details"),
                "execution_logs": row.get("execution_logs") or [],
            }]

        has_multiple_runs = len(runs) > 1
        case_id = str(row.get("case_detail_id") or row.get("row_index") or "case")

        # 生成每个 run 的内容块
        run_blocks = []
        for idx, run in enumerate(runs):
            run_idx = run.get("run_index", idx + 1)
            display = "block" if idx == 0 else "none"
            run_id = f"{case_id}-run-{run_idx}"

            # 比对分数
            compare_details = self._normalize_compare_details(run.get("compare_details"))
            compare_specs = [
                ("score", "综合得分"),
                ("template_score", "模板匹配"),
                ("structure_score", "结构相似"),
                ("feature_score", "特征相似"),
                ("color_score", "颜色相似"),
                ("dino_score", "DINO 得分"),
                ("aspect_ratio_score", "宽高比"),
            ]
            compare_content = ''.join(
                (
                    '<div class="report-field-item">'
                    f'<span>{escape(label)}</span>'
                    f'<strong>{escape(self._format_scalar(compare_details[key]))}</strong>'
                    '</div>'
                )
                for key, label in compare_specs
                if key in compare_details
            )
            compare_html = (
                '<div class="report-field-grid">' + compare_content + '</div>'
                if compare_content
                else '<div class="report-empty">暂无比对指标。</div>'
            )

            # 状态行
            status_label = self._status_label(run.get("status"))
            score_text = self._format_scalar(run.get("score"))
            engine = str(run.get("compare_engine") or "OpenCV").strip()
            status_html = (
                f'<div class="report-field-grid">'
                f'<div class="report-field-item"><span>测试结果</span><strong>{status_label}</strong></div>'
                f'<div class="report-field-item"><span>综合得分</span><strong>{escape(score_text)}</strong></div>'
                f'<div class="report-field-item"><span>比对引擎</span><strong>{escape(engine)}</strong></div>'
                f'</div>'
            )

            # 图片对照
            screenshot_url = str(run.get("screenshot_url") or "").strip()
            image_cards = [
                {"title": "校验图", "url": verify_image_url, "caption": verify_image_name, "empty_text": verify_image_name or "未配置校验图片"},
                {"title": "执行截图", "url": screenshot_url, "caption": "", "empty_text": "当前没有可展示的执行截图"},
            ]
            images_html = '<div class="report-case-image-grid">' + ''.join(
                (
                    '<section class="report-case-image-card">'
                    f'<h3>{escape(item["title"])}</h3>'
                    + (f'<p>{escape(item["caption"])}</p>' if item["caption"] else '')
                    + (
                        # 图片按需加载：报告只存 URL 不嵌 base64，懒加载避免打开时一次性拉取全部图片；
                        # onerror 兜底隐藏加载失败的裂图（如图片仅存在于本地文件夹时）
                        f'<img class="report-case-image" src="{escape(item["url"])}" alt="{escape(item["title"])}" loading="lazy" onerror="this.style.display=\'none\'">'
                        if item["url"]
                        else f'<div class="report-empty">{escape(item["empty_text"])}</div>'
                    )
                    + '</section>'
                )
                for item in image_cards
            ) + '</div>'

            # 执行录屏
            video_url = str(run.get("video_url") or "").strip()
            if video_url:
                video_id = f"video-{run_id}"
                # 根据视频 URL 扩展名确定 MIME 类型
                if video_url.endswith('.webm'):
                    mime_type = 'video/webm'
                elif video_url.endswith('.avi'):
                    mime_type = 'video/x-msvideo'
                else:
                    mime_type = 'video/mp4'
                video_html = (
                    f'<div style="margin-top:8px;">'
                    f'<button onclick="var v=document.getElementById(\'{video_id}\');'
                    f'if(v.style.display===\'none\'){{v.style.display=\'block\';this.textContent=\'关闭录屏\'}}'
                    f'else{{v.style.display=\'none\';this.textContent=\'▶ 播放录屏\'}}" '
                    f'style="padding:6px 16px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px;">'
                    f'▶ 播放录屏</button>'
                    f' <a href="{escape(video_url)}" download style="padding:6px 16px;background:#e2e8f0;color:#334155;border:none;border-radius:4px;cursor:pointer;font-size:13px;text-decoration:none;">下载录屏</a>'
                    f'<video id="{video_id}" controls preload="metadata" style="display:none;width:100%;max-width:800px;margin-top:8px;">'
                    f'<source src="{escape(video_url)}" type="{mime_type}">'
                    f'您的浏览器不支持视频播放'
                    f'</video></div>'
                )
            else:
                video_html = ''

            # 执行日志
            execution_logs = [item for item in run.get("execution_logs", []) if isinstance(item, dict)]
            logs_html = self._render_log_section(execution_logs)

            run_blocks.append(
                f'<div id="{run_id}" class="report-run-panel" style="display:{display};">'
                f'{status_html}'
                f'<section class="report-case-detail-block"><h3>比对分数</h3>{compare_html}</section>'
                f'<section class="report-case-detail-block"><h3>图片对照</h3>{images_html}</section>'
                + (f'<section class="report-case-detail-block"><h3>执行录屏</h3>{video_html}</section>' if video_html else '')
                + f'<section class="report-case-detail-block"><h3>执行日志</h3>{logs_html}</section>'
                f'</div>'
            )

        runs_html = ''.join(run_blocks)

        # 轮次切换器
        switcher_html = ''
        if has_multiple_runs:
            buttons = ''.join(
                f'<button class="report-run-tab" data-run-id="{case_id}-run-{run.get("run_index", i+1)}" '
                f'{"class=\"report-run-tab report-run-tab-active\"" if i == 0 else "class=\"report-run-tab\""}'
                f'>第 {run.get("run_index", i+1)} 轮</button>'
                for i, run in enumerate(runs)
            )
            switcher_html = f'<div class="report-run-switcher">{buttons}</div>'

        return (
            '<div class="report-case-detail-panel">'
            f'{switcher_html}'
            f'{runs_html}'
            '</div>'
        )

    def _render_asr_case_detail(self, row: dict[str, Any]) -> str:
        summary_items = [
            ("识别结果", self._status_label(row.get("status"))),
            ("识别得分", self._format_scalar(row.get("score"))),
            ("备注", row.get("note") or "-"),
        ]
        summary_html = '<div class="report-field-grid">' + ''.join(
            (
                '<div class="report-field-item">'
                f'<span>{escape(label)}</span>'
                f'<strong>{escape(str(value))}</strong>'
                '</div>'
            )
            for label, value in summary_items
            if value not in (None, "")
        ) + '</div>'

        text_cards = [
            ("识别文本", str(row.get("transcribed_text") or "").strip() or "暂无识别文本"),
            ("TTS 文本", str(row.get("tts_text") or "").strip() or "暂无 TTS 文本"),
            ("参考文本", str(row.get("reference_text") or "").strip() or "暂无参考文本"),
        ]
        texts_html = '<div class="report-case-text-grid">' + ''.join(
            (
                '<section class="report-case-text-card">'
                f'<h3>{escape(title)}</h3>'
                f'<p>{escape(content)}</p>'
                '</section>'
            )
            for title, content in text_cards
        ) + '</div>'

        artifact_specs = [
            ("audio_path", "录音文件", "audio"),
            ("transcript_path", "识别文本文件", "transcript"),
            ("compare_result_path", "比对结果文件", "compare"),
            ("reference_path", "参考文本文件", "reference"),
        ]
        artifacts = [
            {
                "name": f"{self._case_title(row)} · {label}",
                "path": str(row.get(key) or "").strip(),
                "kind": kind,
                "detail": f"来源用例：{self._case_title(row)}",
            }
            for key, label, kind in artifact_specs
            if str(row.get(key) or "").strip()
        ]
        artifacts_html = self._render_attachment_section(artifacts)

        compare_preview = str(row.get("compare_result_preview") or "").strip()
        transcript_preview = str(row.get("transcript_preview") or "").strip()
        preview_blocks = []
        if compare_preview:
            preview_blocks.append(
                '<section class="report-case-detail-block">'
                '<h3>比对详细结果</h3>'
                f'<pre class="report-case-preview">{escape(compare_preview)}</pre>'
                '</section>'
            )
        if transcript_preview:
            preview_blocks.append(
                '<section class="report-case-detail-block">'
                '<h3>识别文本文件</h3>'
                f'<pre class="report-case-preview">{escape(transcript_preview)}</pre>'
                '</section>'
            )

        execution_logs = [item for item in row.get("execution_logs", []) if isinstance(item, dict)]

        return (
            '<div class="report-case-detail-panel">'
            '<section class="report-case-detail-block">'
            '<h3>执行概况</h3>'
            f'{summary_html}'
            '</section>'
            '<section class="report-case-detail-block">'
            '<h3>文本对照</h3>'
            f'{texts_html}'
            '</section>'
            '<section class="report-case-detail-block">'
            '<h3>结果文件</h3>'
            f'{artifacts_html}'
            '</section>'
            + ''.join(preview_blocks)
            + '<section class="report-case-detail-block">'
            '<h3>执行日志</h3>'
            f'{self._render_log_section(execution_logs)}'
            '</section>'
            '</div>'
        )

    def _render_table_cell(self, column: dict[str, Any], row: dict[str, Any]) -> str:
        column_key = str(column.get("key") or "").strip()
        value = row.get(column_key)
        if column_key in {"status", "asr_result"}:
            tone = self._status_tone(value)
            label = self._status_label(value)
            return f'<span class="report-status-badge report-status-badge-{tone}">{escape(label)}</span>'
        if column_key in {"score", "asr_score"} and value not in (None, ""):
            return f'<span class="report-score">{escape(self._format_scalar(value))}</span>'
        return escape(self._format_scalar(value))

    def _render_table_section(self, section: dict[str, Any]) -> str:
        columns = [item for item in section.get("columns", []) if isinstance(item, dict)]
        rows = [item for item in section.get("rows", []) if isinstance(item, dict)]
        if not columns:
            return '<div class="report-empty">当前表格未定义列。</div>'

        def get_case_detail_renderer(row: dict[str, Any]):
            if any(row.get(key) for key in ("verify_image", "verify_image_url", "screenshot_url", "compare_details", "compare_engine", "model_name", "runs")):
                return self._render_excel_case_detail
            if any(row.get(key) for key in ("transcribed_text", "tts_text", "reference_text", "audio_path", "transcript_path", "compare_result_path")):
                return self._render_asr_case_detail
            if row.get("execution_logs"):
                return self._render_excel_case_detail
            return None

        supports_case_detail = str(section.get("id") or "").strip().lower() == "cases" and any(
            get_case_detail_renderer(row) is not None
            for row in rows
        )

        table_head = ''.join(
            f'<th>{escape(str(column.get("label") or column.get("key") or "列"))}</th>'
            for column in columns
        )
        if supports_case_detail:
            table_head += '<th>执行详细</th>'
        if not rows:
            colspan = len(columns) + (1 if supports_case_detail else 0)
            table_body = f'<tr><td colspan="{colspan}" class="report-empty-cell">暂无数据</td></tr>'
        else:
            table_rows: list[str] = []
            for row in rows:
                tone = self._status_tone(row.get("status") or row.get("asr_result"))
                row_html = f'<tr class="report-table-row report-table-row-{tone}">' + ''.join(
                    f'<td>{self._render_table_cell(column, row)}</td>'
                    for column in columns
                )

                if supports_case_detail:
                    render_case_detail = get_case_detail_renderer(row)
                    detail_row_id = escape(str(row.get("case_detail_id") or f"case-{row.get('row_index') or len(table_rows) + 1}"))
                    row_html += (
                        '<td class="report-detail-cell">'
                        f'<button type="button" class="report-detail-button" data-detail-target="{detail_row_id}" aria-expanded="false">执行详细</button>'
                        '</td>'
                        '</tr>'
                        + (
                            f'<tr id="{detail_row_id}" class="report-case-detail-row" hidden>'
                            f'<td colspan="{len(columns) + 1}">{render_case_detail(row)}</td>'
                            '</tr>'
                            if render_case_detail is not None else ''
                        )
                    )
                else:
                    row_html += '</tr>'

                table_rows.append(row_html)

            table_body = ''.join(table_rows)

        return (
            '<div class="report-table-wrap">'
            '<table class="report-table">'
            f'<thead><tr>{table_head}</tr></thead>'
            f'<tbody>{table_body}</tbody>'
            '</table>'
            '</div>'
        )

    def _render_log_section(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return '<div class="report-empty">暂无执行日志。</div>'

        rendered = []
        for item in items:
            status = str(item.get("status") or "info").strip().lower()
            happened_at = str(item.get("happened_at") or "").strip()
            rendered.append(
                '<div class="report-log-item">'
                + f'<span class="report-log-badge report-log-badge-{escape(status)}">{escape(status.upper())}</span>'
                + (f'<span class="report-log-time">{escape(happened_at)}</span>' if happened_at else '')
                + f'<p>{escape(str(item.get("message") or ""))}</p>'
                + '</div>'
            )
        return '<div class="report-log-list">' + ''.join(rendered) + '</div>'

    def _render_attachment_section(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return '<div class="report-empty">暂无附件。</div>'
        return '<div class="report-attachment-list">' + ''.join(
            (
                '<div class="report-attachment-item">'
                '<div class="report-attachment-head">'
                f'<strong>{escape(str(item.get("name") or "附件"))}</strong>'
                f'<span class="report-attachment-kind">{escape(str(item.get("kind") or "evidence"))}</span>'
                '</div>'
                f'<p class="report-attachment-path">{escape(str(item.get("path") or item.get("value") or ""))}</p>'
                f'<p>{escape(str(item.get("detail") or item.get("description") or ""))}</p>'
                '</div>'
            )
            for item in items
        ) + '</div>'

    def _render_section(self, section: dict[str, Any]) -> str:
        section_type = str(section.get("type") or "summary").strip().lower()
        title = escape(str(section.get("title") or section.get("id") or "Section"))
        section_id = escape(str(section.get("id") or "section"))
        if section_type == "summary":
            body = self._render_summary_blocks([item for item in section.get("blocks", []) if isinstance(item, dict)])
        elif section_type == "metrics":
            body = self._render_metrics_items([item for item in section.get("items", []) if isinstance(item, dict)])
        elif section_type == "table":
            body = self._render_table_section(section)
        elif section_type == "log":
            body = self._render_log_section([item for item in section.get("items", []) if isinstance(item, dict)])
        elif section_type == "attachments":
            body = self._render_attachment_section([item for item in section.get("items", []) if isinstance(item, dict)])
        else:
            body = f'<pre class="report-fallback">{escape(json.dumps(section, ensure_ascii=False, indent=2))}</pre>'

        return (
            f'<section class="report-section" id="{section_id}">'
            '<div class="report-section-head">'
            f'<h2>{title}</h2>'
            f'<span>{escape(section_type)}</span>'
            '</div>'
            f'{body}'
            '</section>'
        )

    def render_report_html(self, payload: dict[str, Any]) -> str:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        hidden_section_ids = {"overview", "metrics"}
        hidden_section_titles = {"执行概览", "指标看板"}
        if str(payload.get("kind") or "").strip().lower() == "excel-batch":
            hidden_section_ids.add("logs")
            hidden_section_titles.add("执行日志")
        if str(payload.get("kind") or "").strip().lower() == "asr-batch":
            hidden_section_ids.update({"logs", "artifacts"})
            hidden_section_titles.update({"执行日志", "附件与证据"})
        sections = [
            item
            for item in payload.get("sections", [])
            if isinstance(item, dict)
            and str(item.get("id") or "").strip().lower() not in hidden_section_ids
            and str(item.get("title") or "").strip() not in hidden_section_titles
        ]
        serialized_payload = json.dumps(
            {
                **payload,
                "sections": sections,
            },
            ensure_ascii=False,
            indent=2,
        ).replace("</script>", "<\\/script>")

        total_val = summary.get("total", 0)
        passed_val = summary.get("passed", 0)
        failed_val = summary.get("failed", 0)
        blocked_val = summary.get("blocked", 0)
        pass_rate_val = float(summary.get('pass_rate') or 0)
        pass_rate_text = f"{pass_rate_val:.2f}%"
        pass_rate_class = "report-value-green" if pass_rate_val >= 90 else "report-value-red"

        summary_cards = [
            ("总用例", total_val, ""),
            ("通过", passed_val, "report-value-green"),
            ("失败", failed_val, "report-value-red"),
            ("阻塞", blocked_val, "report-value-yellow"),
            ("通过率", pass_rate_text, pass_rate_class),
        ]
        summary_html = ''.join(
            (
                '<div class="report-summary-card">'
                f'<span>{escape(str(label))}</span>'
                f'<strong class="{value_class}">{escape(self._format_scalar(value))}</strong>'
                '</div>'
            )
            for label, value, value_class in summary_cards
        )

        # 图表数据
        chart_data_json = json.dumps({
            "total": total_val,
            "passed": passed_val,
            "failed": failed_val,
            "blocked": blocked_val,
            "passRate": pass_rate_val,
        }, ensure_ascii=False)

        sections_html = ''.join(self._render_section(section) for section in sections) or '<div class="report-empty">当前报告没有 section。</div>'

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(str(payload.get("title") or "测试报告"))}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef4fb;
      --card: rgba(255, 255, 255, 0.84);
      --line: rgba(148, 163, 184, 0.22);
      --text: #0f172a;
      --muted: #64748b;
      --primary: #0f62fe;
      --soft: #dbeafe;
      --success: #15803d;
      --error: #b91c1c;
      --info: #1d4ed8;
      font-family: "Segoe UI", "PingFang SC", "Noto Sans SC", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(96, 165, 250, 0.22), transparent 28%),
        radial-gradient(circle at top right, rgba(251, 191, 36, 0.16), transparent 24%),
        var(--bg);
      color: var(--text);
      padding: 32px 20px 40px;
    }}
    .report-shell {{ max-width: 1240px; margin: 0 auto; display: grid; gap: 20px; }}
    .report-hero, .report-section {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 24px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.92), 0 24px 60px rgba(15, 23, 42, 0.08);
    }}
    .report-hero-top {{ display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; }}
    .report-eyebrow {{ margin: 0; font-size: 12px; letter-spacing: 0.22em; text-transform: uppercase; color: var(--muted); }}
    h1 {{ margin: 10px 0 0; font-size: clamp(2rem, 5vw, 3.6rem); line-height: 0.98; letter-spacing: -0.06em; }}
    .report-section-head span {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .report-section-head span {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(15, 98, 254, 0.08);
      color: var(--primary);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .report-hero-meta {{ margin-top: 12px; color: var(--muted); line-height: 1.6; }}
    .report-summary-grid, .report-metric-grid, .report-field-grid {{ display: grid; gap: 12px; }}
    .report-summary-grid {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin-top: 22px; }}
        .report-hero-grid {{ display: grid; gap: 16px; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr) minmax(0, 1fr); }}
        .report-panel {{
            display: grid;
            gap: 12px;
            padding: 18px;
            border-radius: 24px;
            background: rgba(248, 250, 252, 0.88);
            border: 1px solid rgba(148, 163, 184, 0.16);
        }}
        .report-panel-pass {{ background: linear-gradient(180deg, rgba(236, 253, 245, 0.95), rgba(248, 250, 252, 0.9)); border-color: rgba(34, 197, 94, 0.22); }}
        .report-panel-fail {{ background: linear-gradient(180deg, rgba(254, 242, 242, 0.98), rgba(248, 250, 252, 0.9)); border-color: rgba(239, 68, 68, 0.22); }}
        .report-panel-warning {{ background: linear-gradient(180deg, rgba(255, 251, 235, 0.96), rgba(248, 250, 252, 0.9)); border-color: rgba(245, 158, 11, 0.22); }}
        .report-panel-eyebrow {{ margin: 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--muted); }}
        .report-panel h2 {{ margin: 0; font-size: 1.3rem; line-height: 1.18; }}
        .report-panel p {{ margin: 0; color: var(--muted); line-height: 1.72; }}
        .report-panel-footnote {{ font-size: 0.88rem; color: var(--text); }}
        .report-summary-card, .report-metric-card, .report-field-item {{
      background: rgba(248, 250, 252, 0.86);
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 20px;
      padding: 16px;
      display: grid;
      gap: 8px;
    }}
        .report-summary-card span, .report-metric-card span, .report-field-item span {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
    }}
        .report-summary-card strong, .report-metric-card strong, .report-field-item strong {{ font-size: 1.35rem; line-height: 1.1; }}
    .report-value-green {{ color: #15803d; }}
    .report-value-red {{ color: #b91c1c; }}
    .report-value-yellow {{ color: #b45309; }}
    .report-charts-section {{ margin-top: 22px; }}
    .report-charts-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
    .report-charts-header h3 {{ margin: 0; font-size: 1.1rem; }}
    .report-charts-nav {{ display: flex; gap: 8px; align-items: center; }}
    .report-charts-nav button {{
      width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--line);
      background: var(--card); cursor: pointer; display: flex; align-items: center;
      justify-content: center; font-size: 18px; color: var(--text); transition: all 0.15s;
    }}
    .report-charts-nav button:hover {{ background: var(--soft); }}
    .report-charts-nav button:disabled {{ opacity: 0.35; cursor: not-allowed; }}
    .report-chart-title {{ font-size: 13px; color: var(--muted); text-align: center; letter-spacing: 0.06em; }}
    .report-chart-container {{ display: flex; justify-content: center; align-items: center; min-height: 320px; }}
    .report-chart-container canvas {{ max-width: 480px; max-height: 360px; }}
    .report-run-switcher {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }}
    .report-run-tab {{
      padding: 6px 16px; border-radius: 999px; border: 1px solid var(--line);
      background: var(--card); cursor: pointer; font-size: 13px; font-weight: 600;
      color: var(--muted); transition: all 0.15s;
    }}
    .report-run-tab:hover {{ background: var(--soft); color: var(--text); }}
    .report-run-tab-active {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
    .report-run-tab-active:hover {{ background: #0b4fc4; color: #fff; }}
    .report-content {{ display: grid; gap: 18px; }}
    .report-section-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: start; margin-bottom: 16px; }}
    .report-section-head h2 {{ margin: 0; font-size: 1.2rem; }}
    .report-block {{ display: grid; gap: 10px; padding: 16px; border-radius: 20px; background: rgba(248, 250, 252, 0.9); border: 1px solid rgba(148, 163, 184, 0.14); }}
    .report-block h3 {{ margin: 0; font-size: 1rem; }}
    .report-block p, .report-attachment-item p, .report-log-item p {{ margin: 0; color: var(--muted); line-height: 1.7; }}
    .report-table-wrap {{ overflow-x: auto; }}
    .report-table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    .report-table th, .report-table td {{ border-bottom: 1px solid rgba(226, 232, 240, 0.9); padding: 12px 10px; text-align: left; vertical-align: top; }}
    .report-table th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); background: rgba(248, 250, 252, 0.8); }}
        .report-table-row-pass td {{ background: rgba(240, 253, 244, 0.64); }}
        .report-table-row-fail td {{ background: rgba(254, 242, 242, 0.84); }}
        .report-table-row-warning td {{ background: rgba(255, 251, 235, 0.88); }}
        .report-detail-cell {{ width: 120px; }}
        .report-detail-button {{
            width: 100%;
            border: 1px solid rgba(15, 98, 254, 0.18);
            background: rgba(15, 98, 254, 0.08);
            color: var(--primary);
            border-radius: 999px;
            padding: 9px 14px;
            font-weight: 700;
            cursor: pointer;
        }}
        .report-case-detail-row td {{ background: rgba(241, 245, 249, 0.72); }}
        .report-case-detail-panel {{ display: grid; gap: 16px; padding: 8px 2px; }}
        .report-case-detail-block {{ display: grid; gap: 12px; }}
        .report-case-detail-block h3 {{ margin: 0; font-size: 1rem; }}
        .report-case-text-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
        .report-case-text-card {{ display: grid; gap: 10px; padding: 14px; border-radius: 18px; background: rgba(255, 255, 255, 0.78); border: 1px solid rgba(148, 163, 184, 0.16); }}
        .report-case-text-card h3 {{ margin: 0; font-size: 0.96rem; }}
        .report-case-text-card p {{ margin: 0; color: var(--muted); line-height: 1.7; white-space: pre-wrap; word-break: break-word; }}
        .report-case-image-grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
        .report-case-image-card {{ display: grid; gap: 10px; padding: 14px; border-radius: 18px; background: rgba(255, 255, 255, 0.78); border: 1px solid rgba(148, 163, 184, 0.16); }}
        .report-case-image-card h3 {{ margin: 0; font-size: 0.96rem; }}
        .report-case-image-card p {{ margin: 0; color: var(--muted); word-break: break-all; }}
        .report-case-image {{ width: 100%; max-height: 320px; object-fit: contain; border-radius: 14px; background: rgba(226, 232, 240, 0.45); }}
        .report-case-preview {{ margin: 0; overflow: auto; padding: 16px; border-radius: 16px; background: #0f172a; color: #dbeafe; white-space: pre-wrap; word-break: break-word; }}
        .report-status-badge {{ display: inline-flex; align-items: center; padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}
        .report-status-badge-pass {{ background: rgba(22, 163, 74, 0.12); color: var(--success); }}
        .report-status-badge-fail {{ background: rgba(220, 38, 38, 0.12); color: var(--error); }}
        .report-status-badge-warning {{ background: rgba(245, 158, 11, 0.18); color: #b45309; }}
        .report-status-badge-muted {{ background: rgba(148, 163, 184, 0.16); color: var(--muted); }}
        .report-status-badge-info {{ background: rgba(37, 99, 235, 0.12); color: var(--info); }}
        .report-score {{ font-weight: 700; color: var(--text); }}
    .report-empty, .report-empty-cell {{ color: var(--muted); text-align: center; padding: 18px; }}
    .report-log-list, .report-attachment-list {{ display: grid; gap: 12px; }}
    .report-log-item, .report-attachment-item {{ padding: 14px 16px; border-radius: 18px; background: rgba(248, 250, 252, 0.9); border: 1px solid rgba(148, 163, 184, 0.14); display: grid; gap: 8px; }}
    .report-log-time {{ font-size: 12px; color: var(--muted); }}
        .report-highlight-list {{ display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }}
        .report-highlight-item {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; padding: 12px 14px; border-radius: 18px; background: rgba(255, 255, 255, 0.72); border: 1px solid rgba(239, 68, 68, 0.14); }}
        .report-highlight-item strong {{ font-size: 0.95rem; }}
        .report-highlight-item span {{ color: var(--muted); text-align: right; line-height: 1.6; }}
    .report-log-badge {{ display: inline-flex; width: fit-content; padding: 4px 10px; border-radius: 999px; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; }}
    .report-log-badge-success {{ background: rgba(22, 163, 74, 0.12); color: var(--success); }}
    .report-log-badge-error {{ background: rgba(220, 38, 38, 0.12); color: var(--error); }}
    .report-log-badge-info {{ background: rgba(37, 99, 235, 0.12); color: var(--info); }}
    .report-log-badge-warning {{ background: rgba(245, 158, 11, 0.16); color: #b45309; }}
        .report-attachment-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
        .report-attachment-kind {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; background: rgba(15, 98, 254, 0.08); color: var(--primary); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
        .report-attachment-path {{ font-family: "Cascadia Code", "Consolas", monospace; color: var(--text); word-break: break-all; }}
    .report-fallback {{ margin: 0; overflow: auto; padding: 16px; border-radius: 16px; background: #0f172a; color: #dbeafe; }}
    @media (max-width: 720px) {{
      body {{ padding: 18px 12px 24px; }}
      .report-hero, .report-section {{ padding: 18px; border-radius: 22px; }}
      .report-hero-top {{ flex-direction: column; }}
            .report-hero-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
</head>
<body>
  <div class="report-shell">
    <header class="report-hero">
      <div class="report-hero-top">
        <div>
          <p class="report-eyebrow">Precision Automation Report</p>
          <h1>{escape(str(payload.get("title") or "测试报告"))}</h1>
          <p class="report-hero-meta">创建时间 {escape(str(payload.get("created_at") or "-"))} · 更新时间 {escape(str(payload.get("updated_at") or "-"))}</p>
        </div>
      </div>
            <div class="report-summary-grid">{summary_html}</div>
            <div class="report-charts-section">
              <div class="report-charts-header">
                <h3>📊 数据可视化</h3>
                <div class="report-charts-nav">
                  <button id="chart-prev" title="上一个图表">‹</button>
                  <span id="chart-indicator" class="report-chart-title"></span>
                  <button id="chart-next" title="下一个图表">›</button>
                </div>
              </div>
              <div class="report-chart-container">
                <canvas id="report-chart"></canvas>
              </div>
            </div>
    </header>
    <main class="report-content">{sections_html}</main>
  </div>
  <script id="report-data" type="application/json">{serialized_payload}</script>
    <script>
        (() => {{
            document.addEventListener('click', (event) => {{
                // 执行详细展开/收起
                const detailBtn = event.target.closest('[data-detail-target]');
                if (detailBtn) {{
                    const targetId = detailBtn.getAttribute('data-detail-target');
                    if (targetId) {{
                        const detailRow = document.getElementById(targetId);
                        if (detailRow) {{
                            const expanded = detailBtn.getAttribute('aria-expanded') === 'true';
                            detailBtn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
                            detailBtn.textContent = expanded ? '执行详细' : '收起详细';
                            detailRow.hidden = expanded;
                        }}
                    }}
                    return;
                }}

                // 轮次切换
                const runTab = event.target.closest('.report-run-tab');
                if (runTab) {{
                    const runId = runTab.getAttribute('data-run-id');
                    if (!runId) return;
                    const panel = document.getElementById(runId);
                    if (!panel) return;
                    const switcher = runTab.closest('.report-run-switcher');
                    if (!switcher) return;
                    // 隐藏同组所有 run panel
                    const detailPanel = switcher.closest('.report-case-detail-panel');
                    if (detailPanel) {{
                        detailPanel.querySelectorAll('.report-run-panel').forEach(p => p.style.display = 'none');
                    }}
                    panel.style.display = 'block';
                    // 切换 active tab
                    switcher.querySelectorAll('.report-run-tab').forEach(t => t.classList.remove('report-run-tab-active'));
                    runTab.classList.add('report-run-tab-active');
                }}
            }});
        }})();
    </script>
    <script>
        (() => {{
            const data = {chart_data_json};
            const canvas = document.getElementById('report-chart');
            const indicator = document.getElementById('chart-indicator');
            const prevBtn = document.getElementById('chart-prev');
            const nextBtn = document.getElementById('chart-next');
            if (!canvas || typeof Chart === 'undefined') return;

            const COLORS = {{
                passed: '#15803d',
                failed: '#b91c1c',
                blocked: '#b45309',
                total: '#0f62fe',
            }};

            const chartDefs = [
                {{
                    name: '饼图',
                    build: () => ({{
                        type: 'pie',
                        data: {{
                            labels: ['通过', '失败', '阻塞'],
                            datasets: [{{ data: [data.passed, data.failed, data.blocked], backgroundColor: [COLORS.passed, COLORS.failed, COLORS.blocked], borderWidth: 0 }}]
                        }},
                        options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
                    }})
                }},
                {{
                    name: '环形图',
                    build: () => ({{
                        type: 'doughnut',
                        data: {{
                            labels: ['通过', '失败', '阻塞'],
                            datasets: [{{ data: [data.passed, data.failed, data.blocked], backgroundColor: [COLORS.passed, COLORS.failed, COLORS.blocked], borderWidth: 0, cutout: '55%' }}]
                        }},
                        options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
                    }})
                }},
                {{
                    name: '柱状图',
                    build: () => ({{
                        type: 'bar',
                        data: {{
                            labels: ['总用例', '通过', '失败', '阻塞'],
                            datasets: [{{
                                label: '数量',
                                data: [data.total, data.passed, data.failed, data.blocked],
                                backgroundColor: [COLORS.total, COLORS.passed, COLORS.failed, COLORS.blocked],
                                borderRadius: 8,
                                borderSkipped: false,
                            }}]
                        }},
                        options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
                    }})
                }},
                {{
                    name: '水平条形图',
                    build: () => ({{
                        type: 'bar',
                        data: {{
                            labels: ['通过', '失败', '阻塞'],
                            datasets: [{{
                                label: '数量',
                                data: [data.passed, data.failed, data.blocked],
                                backgroundColor: [COLORS.passed, COLORS.failed, COLORS.blocked],
                                borderRadius: 8,
                                borderSkipped: false,
                            }}]
                        }},
                        options: {{ indexAxis: 'y', responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
                    }})
                }},
                {{
                    name: '雷达图',
                    build: () => ({{
                        type: 'radar',
                        data: {{
                            labels: ['通过率', '通过', '失败', '阻塞', '总量'],
                            datasets: [{{
                                label: '测试结果',
                                data: [
                                    data.passRate,
                                    data.total > 0 ? (data.passed / data.total * 100) : 0,
                                    data.total > 0 ? (data.failed / data.total * 100) : 0,
                                    data.total > 0 ? (data.blocked / data.total * 100) : 0,
                                    100
                                ],
                                backgroundColor: 'rgba(15, 98, 254, 0.15)',
                                borderColor: COLORS.total,
                                pointBackgroundColor: COLORS.total,
                            }}]
                        }},
                        options: {{ responsive: true, scales: {{ r: {{ beginAtZero: true, max: 100, ticks: {{ stepSize: 20 }} }} }}, plugins: {{ legend: {{ position: 'bottom' }} }} }}
                    }})
                }},
                {{
                    name: '极区图',
                    build: () => ({{
                        type: 'polarArea',
                        data: {{
                            labels: ['通过', '失败', '阻塞'],
                            datasets: [{{ data: [data.passed, data.failed, data.blocked], backgroundColor: ['rgba(21,128,61,0.7)', 'rgba(185,28,28,0.7)', 'rgba(180,83,9,0.7)'], borderWidth: 0 }}]
                        }},
                        options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
                    }})
                }},
            ];

            let currentIndex = 0;
            let chartInstance = null;

            const render = (index) => {{
                if (chartInstance) chartInstance.destroy();
                const def = chartDefs[index];
                chartInstance = new Chart(canvas, def.build());
                indicator.textContent = def.name + ' (' + (index + 1) + '/' + chartDefs.length + ')';
                prevBtn.disabled = index === 0;
                nextBtn.disabled = index === chartDefs.length - 1;
            }};

            prevBtn.addEventListener('click', () => {{ if (currentIndex > 0) render(--currentIndex); }});
            nextBtn.addEventListener('click', () => {{ if (currentIndex < chartDefs.length - 1) render(++currentIndex); }});
            render(0);
        }})();
    </script>
</body>
</html>'''


report_service = ReportService()