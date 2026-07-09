"""Reports API routes."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.report_service import InvalidReportTemplateError, ReportNotFoundError, report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportCreateRequest(BaseModel):
    title: str = Field(default="新测试报告", min_length=1)
    template_key: str = Field(default="default", min_length=1)
    kind: str = Field(default="custom", min_length=1)


class AsrBatchCaseResult(BaseModel):
    row_index: int = Field(..., ge=1)
    case_title: str = Field(default="")
    asr_result: str = Field(default="")
    asr_score: float | None = Field(default=None)
    transcribed_text: str = Field(default="")
    tts_text: str = Field(default="")
    reference_text: str = Field(default="")
    reference_path: str = Field(default="")
    audio_path: str = Field(default="")
    transcript_path: str = Field(default="")
    compare_result_path: str = Field(default="")
    note: str = Field(default="")


class ExcelCaseRunResult(BaseModel):
    run_index: int = Field(default=1, ge=1)
    status: str = Field(default="")
    score: float | None = Field(default=None)
    detail: str = Field(default="")
    screenshot_url: str = Field(default="")
    video_url: str = Field(default="")
    compare_engine: str = Field(default="")
    model_name: str = Field(default="")
    compare_details: dict[str, Any] = Field(default_factory=dict)
    execution_logs: list[dict[str, Any]] = Field(default_factory=list)


class ExcelBatchCaseResult(BaseModel):
    row_index: int = Field(..., ge=1)
    case_title: str = Field(default="")
    verify_result: str = Field(default="")
    score: float | None = Field(default=None)
    detail: str = Field(default="")
    verify_image: str = Field(default="")
    verify_image_data_url: str = Field(default="")
    screenshot_url: str = Field(default="")
    video_url: str = Field(default="")
    compare_engine: str = Field(default="")
    model_name: str = Field(default="")
    compare_details: dict[str, Any] = Field(default_factory=dict)
    runs: list[ExcelCaseRunResult] = Field(default_factory=list)


class ReportLogEntry(BaseModel):
    status: str = Field(default="info")
    message: str = Field(default="")
    row_index: int | None = Field(default=None, ge=1)
    happened_at: str = Field(default="")


class AsrBatchReportCreateRequest(BaseModel):
    title: str = Field(default="")
    file_name: str = Field(default="")
    label: str = Field(default="")
    device: str = Field(default="")
    model_name: str = Field(default="")
    row_results: list[AsrBatchCaseResult] = Field(default_factory=list)
    execution_logs: list[ReportLogEntry] = Field(default_factory=list)


class ExcelBatchReportCreateRequest(BaseModel):
    title: str = Field(default="")
    file_name: str = Field(default="")
    label: str = Field(default="")
    device: str = Field(default="")
    row_results: list[ExcelBatchCaseResult] = Field(default_factory=list)
    execution_logs: list[ReportLogEntry] = Field(default_factory=list)


def _success(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "success",
        **payload,
    }


@router.get("/templates")
def list_report_templates():
    return _success({
        "templates": report_service.list_templates(),
    })


@router.get("/overview")
def get_reports_overview():
    return _success(report_service.get_overview())


@router.get("")
def list_reports():
    return _success({
        "reports": report_service.list_reports(),
    })


@router.get("/{report_id}")
def get_report(report_id: str):
    try:
        report = report_service.get_report(report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _success({
        "report": report,
    })


@router.delete("/{report_id}")
def delete_report(report_id: str):
    try:
        deleted_report = report_service.delete_report(report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _success({
        "deleted_report": deleted_report,
    })


@router.post("")
def create_report(payload: ReportCreateRequest):
    try:
        report = report_service.create_report(
            title=payload.title,
            template_key=payload.template_key,
            kind=payload.kind,
        )
    except InvalidReportTemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _success({
        "report": report,
    })


@router.post("/asr-batch")
def create_asr_batch_report(payload: AsrBatchReportCreateRequest):
    if not payload.row_results:
        raise HTTPException(status_code=400, detail="当前批量执行没有可写入报告的用例结果")

    title = payload.title.strip() or "ASR 批量执行报告"
    report = report_service.create_asr_batch_report(
        title=title,
        file_name=payload.file_name,
        batch_label=payload.label,
        device=payload.device,
        model_name=payload.model_name,
        row_results=[item.model_dump() for item in payload.row_results],
        execution_logs=[item.model_dump() for item in payload.execution_logs],
    )
    return _success({
        "report": report,
    })


@router.post("/excel-batch")
def create_excel_batch_report(payload: ExcelBatchReportCreateRequest):
    if not payload.row_results:
        raise HTTPException(status_code=400, detail="当前批量执行没有可写入报告的用例结果")

    title = payload.title.strip() or "图片校验批量执行报告"
    report = report_service.create_excel_batch_report(
        title=title,
        file_name=payload.file_name,
        batch_label=payload.label,
        device=payload.device,
        row_results=[item.model_dump() for item in payload.row_results],
        execution_logs=[item.model_dump() for item in payload.execution_logs],
    )
    return _success({
        "report": report,
    })