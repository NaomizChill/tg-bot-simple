# cleanup_coverage.py
import os
import shutil
from pathlib import Path

# Корень проекта
ROOT = Path(__file__).resolve().parent

print("--- Running cleanup script ---")

# Удаляем файл .coverage
coverage_file = ROOT / ".coverage"
if coverage_file.exists():
    print(f"Deleting file: {coverage_file}")
    coverage_file.unlink()

# Удаляем каталог htmlcov
htmlcov_dir = ROOT / "htmlcov"
if htmlcov_dir.is_dir():
    print(f"Deleting directory: {htmlcov_dir}")
    shutil.rmtree(htmlcov_dir)

print("--- Cleanup finished ---")