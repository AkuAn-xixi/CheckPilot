"""测试资源路径解析工具。"""
import os
from pathlib import Path
from typing import List, Optional


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


def _unique_paths(paths: List[Path]) -> List[Path]:
    result = []
    seen = set()
    for path in paths:
        resolved = str(path.resolve(strict=False))
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(path)
    return result


def get_test_cases_candidates() -> List[Path]:
    return _unique_paths([
        BACKEND_DIR / "test_cases",
        PROJECT_ROOT / "test_cases",
        Path.cwd() / "test_cases",
    ])


def _get_existing_subdir(name: str) -> Path | None:
    for base_dir in get_test_cases_candidates():
        subdir = base_dir / name
        if subdir.exists() and subdir.is_dir():
            return subdir
    return None


def get_excel_dir(create: bool = False) -> Path:
    excel_dir = _get_existing_subdir("excel")
    if excel_dir is None:
        excel_dir = BACKEND_DIR / "test_cases" / "excel"
    if create:
        excel_dir.mkdir(parents=True, exist_ok=True)
    return excel_dir


def get_image_dir() -> Path:
    image_dir = _get_existing_subdir("images")
    if image_dir is None:
        image_dir = BACKEND_DIR / "test_cases" / "images"
    return image_dir


def list_excel_files() -> List[str]:
    file_names = set()
    for base_dir in _unique_paths([get_excel_dir(create=True)] + [candidate / "excel" for candidate in get_test_cases_candidates()]):
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        for file_path in base_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in {".xlsx", ".xls"}:
                file_names.add(file_path.name)
    return sorted(file_names)


def resolve_excel_file(file_name: str) -> Path:
    for base_dir in _unique_paths([get_excel_dir(create=True)] + [candidate / "excel" for candidate in get_test_cases_candidates()]):
        file_path = base_dir / file_name
        if file_path.exists() and file_path.is_file():
            return file_path
    return get_excel_dir(create=True) / file_name


def resolve_image_file(
    image_name: str,
    excel_file_name: Optional[str] = None,
    excel_file_path: Optional[str | Path] = None,
) -> Path:
    image_ref = str(image_name or "").strip().strip('"').strip("'")
    if not image_ref:
        return get_image_dir()

    normalized_path = Path(os.path.expandvars(image_ref)).expanduser()
    candidates: List[Path] = []

    if normalized_path.is_absolute():
        candidates.append(normalized_path)
    else:
        if excel_file_path is not None:
            excel_path = Path(excel_file_path)
            candidates.append(excel_path.parent / normalized_path)
        elif excel_file_name:
            excel_path = resolve_excel_file(excel_file_name)
            candidates.append(excel_path.parent / normalized_path)

        candidates.extend([
            get_image_dir() / normalized_path,
            get_image_dir() / normalized_path.name,
            Path.cwd() / normalized_path,
            PROJECT_ROOT / normalized_path,
            BACKEND_DIR / normalized_path,
        ])

    for candidate in _unique_paths(candidates):
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    if normalized_path.is_absolute():
        return normalized_path

    if excel_file_path is not None:
        return Path(excel_file_path).parent / normalized_path
    if excel_file_name:
        return resolve_excel_file(excel_file_name).parent / normalized_path
    return get_image_dir() / normalized_path.name