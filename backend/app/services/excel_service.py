"""Excel服务模块"""
import os
import pandas as pd
from typing import Dict, Any, List
from app.utils.adb_controller import ADBController
from app.utils.validators import ExcelValidator

class ExcelService:
    """Excel服务类"""

    def __init__(self):
        self.controller = ADBController()
        self.validator = ExcelValidator()

    def get_excel_files(self, directory: str = None) -> List[str]:
        """获取目录下的Excel文件列表"""
        if directory is None:
            directory = os.path.join(os.getcwd(), 'test_cases', 'excel')

        excel_files = []
        if os.path.exists(directory) and os.path.isdir(directory):
            for file in os.listdir(directory):
                if file.endswith('.xlsx') or file.endswith('.xls'):
                    excel_files.append(file)

        return excel_files

    def validate(self, file_name: str) -> Dict[str, Any]:
        """验证Excel文件"""
        file_path = os.path.join(os.getcwd(), 'test_cases', 'excel', file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_name}")

        return self.validator.validate(file_path)

    def analyze(self, file_name: str) -> Dict[str, Any]:
        """分析Excel文件"""
        file_path = os.path.join(os.getcwd(), 'test_cases', 'excel', file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_name}")

        return self.controller.read_excel_commands(file_path)

    def read_commands(self, file_name: str, row_index: int) -> Dict[str, Any]:
        """读取指定行的命令"""
        file_path = os.path.join(os.getcwd(), 'test_cases', 'excel', file_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_name}")

        return self.controller.read_excel_commands(file_path, row_index)

    def write_cell(self, file_name: str, column_name: str, row_index: int, value: str) -> Dict[str, Any]:
        """写入单元格"""
        file_path = os.path.join(os.getcwd(), 'test_cases', 'excel', file_name)
        if not os.path.exists(file_path):
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
