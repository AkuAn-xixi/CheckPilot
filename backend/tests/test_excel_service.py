import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from backend.app.services.excel_service import ExcelService
from backend.app.utils.validators import ExcelValidator


class UpdateCaseFieldsTests(unittest.TestCase):
    def setUp(self):
        self.service = ExcelService()

    def test_update_case_fields_updates_split_step_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / 'cases.xlsx'
            pd.DataFrame([
                {
                    'testID': 'Old Title',
                    'oriStep': 'HOME/1/1',
                    'preScript': 'LEFT/1/1',
                    'checkPic': 'old.png',
                }
            ]).to_excel(excel_path, index=False)

            with mock.patch('backend.app.services.excel_service.resolve_excel_file', return_value=excel_path):
                result = self.service.update_case_fields(
                    'cases.xlsx',
                    2,
                    'New Title',
                    'OK/1/1',
                    'DOWN/1/1',
                    'new.png',
                )

            updated_df = pd.read_excel(excel_path)
            self.assertEqual(updated_df.loc[0, 'testID'], 'New Title')
            self.assertEqual(updated_df.loc[0, 'oriStep'], 'OK/1/1')
            self.assertEqual(updated_df.loc[0, 'preScript'], 'DOWN/1/1')
            self.assertEqual(updated_df.loc[0, 'checkPic'], 'new.png')
            self.assertEqual(result['columns']['ori_step'], 'oriStep')
            self.assertEqual(result['columns']['pre_script'], 'preScript')

    def test_update_case_fields_falls_back_to_single_step_column(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / 'legacy.xlsx'
            pd.DataFrame([
                {
                    'title': 'Legacy Title',
                    'step': 'HOME/1/1',
                    'verify_image': 'old.png',
                }
            ]).to_excel(excel_path, index=False)

            with mock.patch('backend.app.services.excel_service.resolve_excel_file', return_value=excel_path):
                result = self.service.update_case_fields(
                    'legacy.xlsx',
                    2,
                    'Legacy Updated',
                    'BACK/1/1',
                    'IGNORED/1/1',
                    'new.png',
                )

            updated_df = pd.read_excel(excel_path)
            self.assertEqual(updated_df.loc[0, 'title'], 'Legacy Updated')
            self.assertEqual(updated_df.loc[0, 'step'], 'BACK/1/1')
            self.assertEqual(updated_df.loc[0, 'verify_image'], 'new.png')
            self.assertEqual(result['columns']['step'], 'step')

    def test_update_case_fields_preserves_existing_cell_style(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / 'styled.xlsx'
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(['testID', 'oriStep', 'preScript', 'checkPic'])
            worksheet.append(['Old Title', 'HOME/1/1', 'LEFT/1/1', 'old.png'])
            worksheet['A2'].fill = PatternFill(fill_type='solid', fgColor='FFFF00')
            worksheet['A2'].font = Font(bold=True, color='FF0000')
            worksheet['D2'].fill = PatternFill(fill_type='solid', fgColor='00FF00')
            workbook.save(excel_path)
            workbook.close()

            with mock.patch('backend.app.services.excel_service.resolve_excel_file', return_value=excel_path):
                self.service.update_case_fields(
                    'styled.xlsx',
                    2,
                    'Styled Title',
                    'OK/1/1',
                    'DOWN/1/1',
                    'styled.png',
                )

            updated_workbook = load_workbook(excel_path)
            updated_worksheet = updated_workbook.active
            self.assertEqual(updated_worksheet['A2'].value, 'Styled Title')
            self.assertEqual(updated_worksheet['D2'].value, 'styled.png')
            self.assertEqual(updated_worksheet['A2'].fill.fill_type, 'solid')
            self.assertTrue((updated_worksheet['A2'].fill.fgColor.rgb or '').endswith('FFFF00'))
            self.assertTrue(updated_worksheet['A2'].font.bold)
            self.assertTrue((updated_worksheet['D2'].fill.fgColor.rgb or '').endswith('00FF00'))
            updated_workbook.close()


class WriteCellTests(unittest.TestCase):
    def setUp(self):
        self.service = ExcelService()

    def test_write_cell_preserves_existing_cell_style(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / 'sequence.xlsx'
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(['sequence'])
            worksheet.append(['old'])
            worksheet['A2'].fill = PatternFill(fill_type='solid', fgColor='FFCC00')
            worksheet['A2'].font = Font(italic=True)
            workbook.save(excel_path)
            workbook.close()

            with mock.patch('backend.app.services.excel_service.resolve_excel_file', return_value=excel_path):
                result = self.service.write_cell('sequence.xlsx', 'sequence', 0, 'new')

            updated_workbook = load_workbook(excel_path)
            updated_worksheet = updated_workbook.active
            self.assertEqual(updated_worksheet['A2'].value, 'new')
            self.assertEqual(updated_worksheet['A2'].fill.fill_type, 'solid')
            self.assertTrue((updated_worksheet['A2'].fill.fgColor.rgb or '').endswith('FFCC00'))
            self.assertTrue(updated_worksheet['A2'].font.italic)
            self.assertEqual(result['column_name'], 'sequence')
            updated_workbook.close()


class ExcelValidationTests(unittest.TestCase):
    def test_validate_allows_tts_marker_in_command_cells(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / 'asr.xlsx'
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'])
            worksheet.append([None, None, 'case-1', None, None, 'HOME/1/1,TTS,OK/1/1', None, None, None, None])
            workbook.save(excel_path)
            workbook.close()

            result = ExcelValidator.validate(str(excel_path))

        self.assertTrue(result['success'], result['errors'])


if __name__ == '__main__':
    unittest.main()