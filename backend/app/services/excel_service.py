"""Excel服务模块"""
from pathlib import Path
import pandas as pd
from typing import Dict, Any, List
from app.utils.adb_controller import ADBController
from app.utils.validators import ExcelValidator
from app.utils.path_resolver import list_excel_files, resolve_excel_file

class ExcelService:
    """Excel服务类"""

    def __init__(self):
        self.controller = ADBController()
        self.validator = ExcelValidator()

    def get_excel_files(self, directory: str = None) -> List[str]:
        """获取目录下的Excel文件列表"""
        if directory is None:
            return list_excel_files()

        target_dir = Path(directory)
        if not target_dir.exists() or not target_dir.is_dir():
            return []

        excel_files = []
        for file_path in target_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in {'.xlsx', '.xls'}:
                excel_files.append(file_path.name)
        return sorted(excel_files)

    def validate(self, file_name: str) -> Dict[str, Any]:
        """验证Excel文件"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        return self.validator.validate(str(file_path))

    def analyze(self, file_name: str) -> Dict[str, Any]:
        """分析Excel文件"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        return self.controller.read_excel_commands(str(file_path))

    def preview(self, file_name: str, limit: int = 100) -> Dict[str, Any]:
        """预览Excel文件内容，返回列名和前几行数据。"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        try:
            df = pd.read_excel(file_path)
            preview_df = df.head(limit).copy()
            preview_df = preview_df.where(pd.notna(preview_df), None)

            return {
                "columns": [str(col) for col in preview_df.columns.tolist()],
                "rows": preview_df.to_dict(orient="records"),
                "row_count": int(len(df))
            }
        except Exception as e:
            raise Exception(f"预览失败: {e}")

    def read_commands(self, file_name: str, row_index: int) -> Dict[str, Any]:
        """读取指定行的命令"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        return self.controller.read_excel_commands(str(file_path), row_index)

    def write_cell(self, file_name: str, column_name: str, row_index: int, value: str) -> Dict[str, Any]:
        """写入单元格"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        try:
            df = pd.read_excel(file_path)
            col = column_name
            if col not in df.columns:
                df[col] = None

            ri = int(row_index)
            if ri < 0:
                ri = 0
            if ri >= len(df):
                df = df.reindex(range(ri + 1))

            df.loc[ri, col] = value
            df.to_excel(file_path, index=False)

            return {
                "status": "ok",
                "file": file_name,
                "row_index": ri,
                "column_name": col
            }
        except Exception as e:
            raise Exception(f"写入失败: {e}")

excel_service = ExcelService()
