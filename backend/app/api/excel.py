"""Excel API路由模块"""
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from typing import Optional
from ..models.schemas import (
    ExcelExecuteRequest,
    AppendSequenceRequest,
    AppendAssertRequest,
    WriteCellRequest,
    ExcelCaseFieldsUpdateRequest,
    AddCaseRequest,
    DeleteCasesRequest,
    ExcelValidationResult,
    ExcelAnalysisResult
)
from ..services.excel_service import excel_service
from ..utils.path_resolver import get_excel_dir, resolve_excel_file, resolve_image_file

router = APIRouter(prefix="/api/excel", tags=["excel"])

@router.get("/files")
async def get_excel_files():
    """获取当前工作目录下的Excel文件"""
    files = await asyncio.to_thread(excel_service.get_excel_files)
    return {"files": files}

@router.get("/validate")
async def validate_excel_file(file_name: str = Query(..., description="Excel文件名")):
    """验证Excel文件格式和内容"""
    try:
        result = await asyncio.to_thread(excel_service.validate, file_name)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")

@router.get("/analyze")
async def analyze_excel_file(file_name: str = Query(..., description="Excel文件名")):
    """分析Excel文件内容"""
    try:
        # analyze 是阻塞 CPU 操作（pandas 读表 + 命令解析），放线程池执行，
        # 避免分析大文件时冻结事件循环、导致其它接口（如设备列表）全部超时。
        result = await asyncio.to_thread(excel_service.analyze, file_name)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")

@router.get("/preview")
async def preview_excel_file(file_name: str = Query(..., description="Excel文件名")):
    """预览Excel文件内容"""
    try:
        result = await asyncio.to_thread(excel_service.preview, file_name)
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
        print(f"[write_cell] file={req.file_name} col={req.column_name} row={req.row_index} value={repr(req.value)}")
        result = await asyncio.to_thread(
            excel_service.write_cell,
            req.file_name,
            req.column_name,
            req.row_index,
            req.value
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"写入失败: {str(e)}")

@router.post("/update_case_fields")
async def update_case_fields(req: ExcelCaseFieldsUpdateRequest):
    """更新图片校验执行页中的标题、步骤和校验图片。"""
    try:
        result = await asyncio.to_thread(
            excel_service.update_case_fields,
            req.file_name,
            req.excel_row,
            req.title,
            req.ori_step,
            req.pre_script,
            req.verify_image,
            req.step,
            req.test_result,
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
        result = await asyncio.to_thread(
            excel_service.append_sequence_to_latest_prescript,
            req.file_name, req.sequence, req.case_number, req.assert_format,
            req.check_pic, req.check_point,
        )
        message = f"序列已写入第 {result['excel_row']} 行的 preScript"
        written_columns = result.get('written_columns') or []
        if written_columns:
            message += f"，并已同步写入 {'/'.join(written_columns)}"
        return {
            **result,
            "message": message,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 preScript 失败: {str(e)}")

@router.get("/case_state")
async def get_case_state(file_name: str = Query(...), case_number: str = Query(...)):
    """查询指定 case 在 Excel 中的当前状态（是否存在、assert 次数、checkPic 数量等）。"""
    try:
        return await asyncio.to_thread(excel_service.get_case_state, file_name, case_number)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询 case 状态失败: {str(e)}")

@router.post("/append_assert")
async def append_assert(req: AppendAssertRequest):
    """直接将 Assert 指令写入指定 case 的 preScript 末尾（已有则覆盖）。"""
    try:
        result = await asyncio.to_thread(excel_service.append_assert_to_case, req.file_name, req.case_number, req.assert_format)
        action = "覆盖" if result.get("replaced") else "追加"
        return {**result, "message": f"Assert 已{action}写入第 {result['excel_row']} 行"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入 Assert 失败: {str(e)}")

@router.get("/verify_image")
async def verify_image(file_name: str = Query(...), image_name: str = Query(...)):
    """获取校验图片"""
    image_path = resolve_image_file(image_name, excel_file_name=file_name)

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")

    return FileResponse(image_path)

@router.post("/add_case")
async def add_case(req: AddCaseRequest):
    """新增一行用例到 Excel（占位命令 OK/1/1，保证在列表可见）。"""
    try:
        return await asyncio.to_thread(excel_service.add_case, req.file_name, req.title)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新增用例失败: {str(e)}")

@router.post("/delete_cases")
async def delete_cases(req: DeleteCasesRequest):
    """按 Excel 行号删除用例（支持批量）。"""
    try:
        return await asyncio.to_thread(excel_service.delete_cases, req.file_name, req.excel_rows)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除用例失败: {str(e)}")
