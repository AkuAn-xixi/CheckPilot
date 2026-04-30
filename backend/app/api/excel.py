"""Excel API路由模块"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from typing import Optional
from ..models.schemas import (
    ExcelExecuteRequest,
    AppendSequenceRequest,
    WriteCellRequest,
    ExcelCaseFieldsUpdateRequest,
    ExcelValidationResult,
    ExcelAnalysisResult
)
from ..services.excel_service import excel_service
from ..utils.path_resolver import get_excel_dir, resolve_excel_file, resolve_image_file

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

@router.post("/update_case_fields")
async def update_case_fields(req: ExcelCaseFieldsUpdateRequest):
    """更新图片校验执行页中的标题、步骤和校验图片。"""
    try:
        result = excel_service.update_case_fields(
            req.file_name,
            req.excel_row,
            req.title,
            req.ori_step,
            req.pre_script,
            req.verify_image,
            req.step,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新用例字段失败: {str(e)}")

@router.post("/append_sequence")
async def append_sequence(req: AppendSequenceRequest):
    """将序列写入 preScript 列中最后一个仍为空的有效数据行。"""
    try:
        result = excel_service.append_sequence_to_latest_prescript(req.file_name, req.sequence)
        return {
            **result,
            "message": f"序列已写入第 {result['excel_row']} 行的 preScript",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 preScript 失败: {str(e)}")

@router.get("/verify_image")
async def verify_image(file_name: str = Query(...), image_name: str = Query(...)):
    """获取校验图片"""
    image_path = resolve_image_file(image_name, excel_file_name=file_name)

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")

    return FileResponse(image_path)
