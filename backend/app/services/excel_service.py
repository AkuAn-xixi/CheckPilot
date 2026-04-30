"""Excel服务模块"""
from copy import copy
from pathlib import Path
import pandas as pd
from typing import Dict, Any, List, Optional
from openpyxl import load_workbook
from ..utils.adb_controller import ADBController
from ..utils.validators import ExcelValidator
from ..utils.path_resolver import list_excel_files, resolve_excel_file

class ExcelService:
    """Excel服务类"""

    OPENPYXL_SUPPORTED_SUFFIXES = {'.xlsx', '.xlsm', '.xltx', '.xltm'}

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

    @staticmethod
    def _load_workbook_sheet(file_path: Path):
        workbook = load_workbook(
            file_path,
            keep_vba=file_path.suffix.lower() in {'.xlsm', '.xltm'},
        )
        worksheet = workbook.worksheets[0] if workbook.worksheets else workbook.active
        return workbook, worksheet

    @classmethod
    def _supports_cell_level_write(cls, file_path: Path) -> bool:
        return file_path.suffix.lower() in cls.OPENPYXL_SUPPORTED_SUFFIXES

    @staticmethod
    def _get_header_map(worksheet) -> Dict[str, int]:
        header_map = {}
        for column_index in range(1, worksheet.max_column + 1):
            header_value = worksheet.cell(row=1, column=column_index).value
            if header_value is None:
                continue

            header_name = str(header_value).strip()
            if header_name and header_name not in header_map:
                header_map[header_name] = column_index

        return header_map

    @staticmethod
    def _clone_cell_style(source_cell, target_cell) -> None:
        if source_cell is None or not source_cell.has_style:
            return

        target_cell._style = copy(source_cell._style)

    def _ensure_column(self, worksheet, header_map: Dict[str, int], column_name: str) -> int:
        existing_index = header_map.get(column_name)
        if existing_index is not None:
            return existing_index

        column_index = worksheet.max_column + 1 if worksheet.max_column else 1
        header_cell = worksheet.cell(row=1, column=column_index)
        if column_index > 1:
            self._clone_cell_style(worksheet.cell(row=1, column=column_index - 1), header_cell)
        header_cell.value = column_name
        header_map[column_name] = column_index
        return column_index

    def _prepare_target_cell(self, worksheet, row_index: int, column_index: int):
        target_cell = worksheet.cell(row=row_index, column=column_index)
        if target_cell.has_style:
            return target_cell

        style_source = None

        if column_index > 1:
            left_cell = worksheet.cell(row=row_index, column=column_index - 1)
            if left_cell.has_style:
                style_source = left_cell

        if style_source is None and row_index > 2:
            above_cell = worksheet.cell(row=row_index - 1, column=column_index)
            if above_cell.has_style:
                style_source = above_cell

        if style_source is not None:
            self._clone_cell_style(style_source, target_cell)

        return target_cell

    def _write_sheet_cell(self, worksheet, row_index: int, column_index: int, value: Any) -> None:
        target_cell = self._prepare_target_cell(worksheet, row_index, column_index)
        target_cell.value = value

    @staticmethod
    def _has_meaningful_cell_value(value: Any) -> bool:
        if value is None:
            return False

        if pd.isna(value):
            return False

        normalized = str(value).strip()
        return normalized != '' and normalized.lower() != 'nan'

    @staticmethod
    def _normalize_command_sequence(sequence: Any) -> str:
        return ','.join(
            part.strip()
            for part in str(sequence or '').split(',')
            if part.strip()
        )

    @classmethod
    def _compress_adjacent_command_sequence(cls, sequence: Any) -> str:
        normalized_sequence = cls._normalize_command_sequence(sequence)
        if not normalized_sequence:
            return ''

        parts = [part.strip() for part in normalized_sequence.split(',') if part.strip()]
        compressed_parts: List[str] = []

        for part in parts:
            segments = part.split('/')
            if len(segments) < 3:
                compressed_parts.append(part)
                continue

            key = segments[0]
            try:
                count = int(segments[1])
            except (TypeError, ValueError):
                count = 1
            if count <= 0:
                count = 1

            delay = segments[2]
            if delay == '*':
                compressed_parts.append(f"{key}/{count}/{delay}")
                continue

            last = compressed_parts[-1] if compressed_parts else None
            if last:
                last_segments = last.split('/')
                if len(last_segments) >= 3 and last_segments[0] == key and last_segments[2] == delay:
                    try:
                        last_count = int(last_segments[1])
                    except (TypeError, ValueError):
                        last_count = 1
                    if last_count <= 0:
                        last_count = 1

                    compressed_parts[-1] = f"{key}/{last_count + count}/{delay}"
                    continue

            compressed_parts.append(f"{key}/{count}/{delay}")

        return ','.join(compressed_parts)

    def _find_latest_blank_prescript_data_row_with_pandas(self, df: pd.DataFrame) -> int:
        if 'preScript' not in df.columns:
            df['preScript'] = None

        for data_row_index in range(len(df) - 1, -1, -1):
            row = df.iloc[data_row_index]
            pre_script_value = row.get('preScript')
            ori_step_value = row.get('oriStep') if 'oriStep' in df.columns else None

            if self._has_meaningful_cell_value(pre_script_value) or self._has_meaningful_cell_value(ori_step_value):
                continue

            has_other_content = any(
                self._has_meaningful_cell_value(value)
                for column_name, value in row.items()
                if column_name not in {'preScript', 'oriStep'}
            )
            if has_other_content:
                return data_row_index

        raise ValueError('未找到 oriStep 和 preScript 都为空的可写入数据行')

    def _find_latest_blank_prescript_excel_row(self, worksheet, pre_script_column_index: int, ori_step_column_index: Optional[int] = None) -> int:
        for excel_row in range(worksheet.max_row, 1, -1):
            pre_script_value = worksheet.cell(row=excel_row, column=pre_script_column_index).value
            ori_step_value = worksheet.cell(row=excel_row, column=ori_step_column_index).value if ori_step_column_index else None

            if self._has_meaningful_cell_value(pre_script_value) or self._has_meaningful_cell_value(ori_step_value):
                continue

            has_other_content = any(
                self._has_meaningful_cell_value(worksheet.cell(row=excel_row, column=column_index).value)
                for column_index in range(1, worksheet.max_column + 1)
                if column_index != pre_script_column_index and column_index != ori_step_column_index
            )
            if has_other_content:
                return excel_row

        raise ValueError('未找到 oriStep 和 preScript 都为空的可写入数据行')

    def _write_cell_with_pandas(self, file_path: Path, file_name: str, column_name: str, row_index: int, value: str) -> Dict[str, Any]:
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
            "column_name": col,
            "preserved_format": False,
        }

    def _update_case_fields_with_pandas(
        self,
        file_path: Path,
        file_name: str,
        excel_row: int,
        title: str,
        ori_step: str,
        pre_script: str,
        verify_image: str,
        step: Optional[str] = None,
    ) -> Dict[str, Any]:
        df = pd.read_excel(file_path)

        data_row_index = int(excel_row) - 2
        if data_row_index < 0 or data_row_index >= len(df):
            raise ValueError(f"Excel行号超出范围: {excel_row}")

        title_column = 'testID' if 'testID' in df.columns else 'title'
        verify_image_column = 'checkPic' if 'checkPic' in df.columns else 'verify_image'
        has_split_step_columns = 'oriStep' in df.columns or 'preScript' in df.columns

        if title_column not in df.columns:
            df[title_column] = None
        if verify_image_column not in df.columns:
            df[verify_image_column] = None

        df.loc[data_row_index, title_column] = title
        df.loc[data_row_index, verify_image_column] = verify_image

        columns = {
            "title": title_column,
            "verify_image": verify_image_column,
        }

        if has_split_step_columns:
            if 'oriStep' not in df.columns:
                df['oriStep'] = None
            if 'preScript' not in df.columns:
                df['preScript'] = None

            df.loc[data_row_index, 'oriStep'] = ori_step
            df.loc[data_row_index, 'preScript'] = pre_script
            columns.update({
                "ori_step": 'oriStep',
                "pre_script": 'preScript',
            })
        else:
            step_column = 'step' if 'step' in df.columns else 'operation' if 'operation' in df.columns else 'step'
            if step_column not in df.columns:
                df[step_column] = None

            fallback_step = ori_step or step or ''
            df.loc[data_row_index, step_column] = fallback_step
            columns["step"] = step_column

        df.to_excel(file_path, index=False)

        return {
            "status": "ok",
            "file": file_name,
            "excel_row": int(excel_row),
            "data_row_index": data_row_index,
            "columns": columns,
            "preserved_format": False,
        }

    def write_cell(self, file_name: str, column_name: str, row_index: int, value: str) -> Dict[str, Any]:
        """写入单元格"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        try:
            if not self._supports_cell_level_write(file_path):
                return self._write_cell_with_pandas(file_path, file_name, column_name, row_index, value)

            workbook, worksheet = self._load_workbook_sheet(file_path)
            header_map = self._get_header_map(worksheet)
            col = column_name
            column_index = self._ensure_column(worksheet, header_map, col)

            ri = int(row_index)
            if ri < 0:
                ri = 0

            excel_row_index = ri + 2
            self._write_sheet_cell(worksheet, excel_row_index, column_index, value)
            workbook.save(file_path)
            workbook.close()

            return {
                "status": "ok",
                "file": file_name,
                "row_index": ri,
                "column_name": col,
                "preserved_format": True,
            }
        except Exception as e:
            raise Exception(f"写入失败: {e}")

    def append_sequence_to_latest_prescript(self, file_name: str, sequence: str) -> Dict[str, Any]:
        """将序列写入 preScript 列中最后一个 oriStep 和 preScript 都为空的有效数据行。"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        normalized_sequence = self._compress_adjacent_command_sequence(sequence)
        if not normalized_sequence:
            raise ValueError('待写入的序列不能为空')

        try:
            if not self._supports_cell_level_write(file_path):
                df = pd.read_excel(file_path)
                appended_new_row = False
                try:
                    data_row_index = self._find_latest_blank_prescript_data_row_with_pandas(df)
                except ValueError:
                    data_row_index = len(df)
                    df = df.reindex(range(data_row_index + 1))
                    if 'preScript' not in df.columns:
                        df['preScript'] = None
                    appended_new_row = True

                df.loc[data_row_index, 'preScript'] = normalized_sequence
                df.to_excel(file_path, index=False)

                return {
                    "status": "ok",
                    "file": file_name,
                    "excel_row": data_row_index + 2,
                    "data_row_index": data_row_index,
                    "column_name": "preScript",
                    "appended_new_row": appended_new_row,
                    "preserved_format": False,
                }

            workbook, worksheet = self._load_workbook_sheet(file_path)
            try:
                header_map = self._get_header_map(worksheet)
                pre_script_column_index = self._ensure_column(worksheet, header_map, 'preScript')
                ori_step_column_index = header_map.get('oriStep')
                appended_new_row = False
                try:
                    excel_row = self._find_latest_blank_prescript_excel_row(worksheet, pre_script_column_index, ori_step_column_index)
                except ValueError:
                    excel_row = worksheet.max_row + 1
                    appended_new_row = True

                self._write_sheet_cell(worksheet, excel_row, pre_script_column_index, normalized_sequence)
                workbook.save(file_path)

                return {
                    "status": "ok",
                    "file": file_name,
                    "excel_row": excel_row,
                    "data_row_index": excel_row - 2,
                    "column_name": "preScript",
                    "appended_new_row": appended_new_row,
                    "preserved_format": True,
                }
            finally:
                workbook.close()
        except Exception as e:
            raise Exception(f"写入 preScript 失败: {e}")

    def update_case_fields(
        self,
        file_name: str,
        excel_row: int,
        title: str,
        ori_step: str,
        pre_script: str,
        verify_image: str,
        step: Optional[str] = None,
    ) -> Dict[str, Any]:
        """按 Excel 行号更新图片校验用例的展示字段。"""
        file_path = resolve_excel_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        try:
            if not self._supports_cell_level_write(file_path):
                return self._update_case_fields_with_pandas(
                    file_path,
                    file_name,
                    excel_row,
                    title,
                    ori_step,
                    pre_script,
                    verify_image,
                    step,
                )

            workbook, worksheet = self._load_workbook_sheet(file_path)
            header_map = self._get_header_map(worksheet)

            data_row_index = int(excel_row) - 2
            actual_excel_row = int(excel_row)
            if data_row_index < 0 or actual_excel_row > worksheet.max_row:
                raise ValueError(f"Excel行号超出范围: {excel_row}")

            title_column = 'testID' if 'testID' in header_map else 'title'
            verify_image_column = 'checkPic' if 'checkPic' in header_map else 'verify_image'
            has_split_step_columns = 'oriStep' in header_map or 'preScript' in header_map

            title_column_index = self._ensure_column(worksheet, header_map, title_column)
            verify_image_column_index = self._ensure_column(worksheet, header_map, verify_image_column)

            self._write_sheet_cell(worksheet, actual_excel_row, title_column_index, title)
            self._write_sheet_cell(worksheet, actual_excel_row, verify_image_column_index, verify_image)

            columns = {
                "title": title_column,
                "verify_image": verify_image_column,
            }

            if has_split_step_columns:
                ori_step_column_index = self._ensure_column(worksheet, header_map, 'oriStep')
                pre_script_column_index = self._ensure_column(worksheet, header_map, 'preScript')

                self._write_sheet_cell(worksheet, actual_excel_row, ori_step_column_index, ori_step)
                self._write_sheet_cell(worksheet, actual_excel_row, pre_script_column_index, pre_script)
                columns.update({
                    "ori_step": 'oriStep',
                    "pre_script": 'preScript',
                })
            else:
                step_column = 'step' if 'step' in header_map else 'operation' if 'operation' in header_map else 'step'
                step_column_index = self._ensure_column(worksheet, header_map, step_column)

                fallback_step = ori_step or step or ''
                self._write_sheet_cell(worksheet, actual_excel_row, step_column_index, fallback_step)
                columns["step"] = step_column

            workbook.save(file_path)
            workbook.close()

            return {
                "status": "ok",
                "file": file_name,
                "excel_row": int(excel_row),
                "data_row_index": data_row_index,
                "columns": columns,
                "preserved_format": True,
            }
        except Exception as e:
            raise Exception(f"更新用例字段失败: {e}")

excel_service = ExcelService()
