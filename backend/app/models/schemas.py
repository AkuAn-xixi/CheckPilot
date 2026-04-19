"""Pydantic模型定义"""
from pydantic import BaseModel
from typing import Optional, List, Any

class DeviceSelectRequest(BaseModel):
    device_index: int

class CommandExecuteRequest(BaseModel):
    commands: str

class SingleCommandExecuteRequest(BaseModel):
    command: str

class ExcelExecuteRequest(BaseModel):
    file_name: str
    row_index: int

class AppendSequenceRequest(BaseModel):
    file_name: str
    sequence: str

class WriteCellRequest(BaseModel):
    file_name: str
    column_name: str
    row_index: int
    value: str

class DeviceInfo(BaseModel):
    serial: str
    status: str

class CommandResult(BaseModel):
    status: str
    message: str
    keyname: Optional[str] = None
    keycode: Optional[int] = None

class ExcelValidationError(BaseModel):
    row: Optional[int] = None
    column: Optional[str] = None
    message: str

class ExcelValidationResult(BaseModel):
    success: bool
    errors: List[str]
    warnings: List[str]
    total_rows: int

class ExcelRowData(BaseModel):
    row: int
    title: str
    step: str
    verify_image: str
    test_result: str
    oriStep: str
    preScript: str
    commands: List[str]

class ExcelAnalysisResult(BaseModel):
    valid_rows: List[ExcelRowData]
    skipped_rows: List[dict]
    total_rows: int

class VerifyImageResult(BaseModel):
    success: bool
    matched: bool
    score: float
    struct_score: float
    color_score: float
    message: str

class ExecutionStreamEvent(BaseModel):
    status: str
    message: str
    screenshot_url: Optional[str] = None
    verify_result: Optional[str] = None
    score: Optional[float] = None
