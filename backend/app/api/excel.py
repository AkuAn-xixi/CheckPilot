"""Excel API路由模块"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from typing import Optional
from app.models.schemas import (
    ExcelExecuteRequest,
    AppendSequenceRequest,
    WriteCellRequest,
    ExcelValidationResult,
    ExcelAnalysisResult
)
from app.runtime import get_current_device, get_monitor_live_sequence
from app.services.excel_service import excel_service
from app.utils.path_resolver import get_excel_dir, resolve_excel_file, resolve_image_file

router = APIRouter(prefix="/api/excel", tags=["excel"])

@router.get("/files")
async def get_excel_files():
    """获取当前工作目录下的Excel文件"""
    files = excel_service.get_excel_files()
    return {"files": files}

@router.get("/validate")
async def validate_excel_file(file_name: str = Query(..., description="Excel文件名")):
    """验证Excel文件格式和内容"""
    try:
        result = excel_service.validate(file_name)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")

@router.get("/analyze")
async def analyze_excel_file(file_name: str = Query(..., description="Excel文件名")):
    """分析Excel文件内容"""
    try:
        result = excel_service.analyze(file_name)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")

@router.get("/preview")
async def preview_excel_file(file_name: str = Query(..., description="Excel文件名")):
    """预览Excel文件内容"""
    try:
        result = excel_service.preview(file_name)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")

@router.post("/upload")
async def upload_excel_file(file: UploadFile = File(...)):
    """上传Excel文件"""
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="只支持 .xlsx 和 .xls 格式的文件")

    file_path = get_excel_dir(create=True) / file.filename

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {"filename": file.filename, "message": "文件上传成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")

@router.delete("/delete")
async def delete_excel_file(file_name: str = Query(..., description="Excel文件名")):
    """删除Excel文件"""
    file_path = resolve_excel_file(file_name)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        file_path.unlink()
        return {"status": "success", "message": f"文件 {file_name} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@router.post("/write_cell")
async def write_cell(req: WriteCellRequest):
    """写入Excel单元格"""
    try:
        result = excel_service.write_cell(
            req.file_name,
            req.column_name,
            req.row_index,
            req.value
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {str(e)}")

@router.post("/append_sequence")
async def append_sequence(req: AppendSequenceRequest):
    """追加序列到Excel"""
    current_device = get_current_device()
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")

    monitor_live_sequence = get_monitor_live_sequence()
    try:
        df = excel_service.analyze(req.file_name)
        last_row = len(df.get('valid_rows', []))
        excel_service.write_cell(req.file_name, 'sequence', last_row + 1, req.sequence)
        return {"status": "ok", "message": "序列已追加"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"追加失败: {str(e)}")

@router.get("/verify_image")
async def verify_image(file_name: str = Query(...), image_name: str = Query(...)):
    """获取校验图片"""
    image_path = resolve_image_file(image_name, excel_file_name=file_name)

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")

    return FileResponse(image_path)
