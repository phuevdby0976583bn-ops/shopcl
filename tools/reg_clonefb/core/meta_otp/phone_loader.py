# -*- coding: utf-8 -*-
"""
phone_loader.py - Multi-format phone number loader (.txt, .csv, .xlsx, multiline string)
With automatic phone number column detection and validation.
"""

import os
import re
import csv
from typing import List, Optional

CLEAN_PATTERN = re.compile(r'[\s\-\(\)\.]')
PHONE_PATTERN = re.compile(r'^\+?\d{7,15}$')


def clean_and_validate(value) -> Optional[str]:
    """Strip formatting characters and validate as phone number."""
    if value is None:
        return None
    val_str = str(value).strip()
    if not val_str:
        return None
    if 'e+' in val_str.lower() or 'e-' in val_str.lower():
        try:
            val_str = str(int(float(val_str)))
        except Exception:
            pass
    cleaned = CLEAN_PATTERN.sub('', val_str)
    if PHONE_PATTERN.match(cleaned):
        return cleaned
    return None


def column_phone_score(col_values) -> float:
    """Score a column by how many values look like phone numbers (0.0 to 1.0)."""
    total = 0
    phone_count = 0
    for v in col_values:
        if v and str(v).strip():
            total += 1
            if clean_and_validate(v) is not None:
                phone_count += 1
    return phone_count / total if total > 0 else 0.0


def detect_and_extract_numbers(rows: List[List[str]]) -> List[str]:
    """Auto-detect which column contains phone numbers and extract them."""
    if not rows:
        return []

    max_cols = max(len(row) for row in rows)
    if max_cols == 0:
        return []

    first_row = rows[0]
    has_header = len(rows) > 1 and not any((v and str(v).strip() and clean_and_validate(v)) for v in first_row)
    data_rows = rows[1:] if has_header else rows

    if not data_rows:
        return []

    sample_size = min(len(data_rows), 100)
    sample_rows = data_rows[:sample_size]

    best_col = -1
    best_score = 0.0

    for col_idx in range(max_cols):
        col_values = [row[col_idx] if col_idx < len(row) else '' for row in sample_rows]
        score = column_phone_score(col_values)
        if score > best_score:
            best_score = score
            best_col = col_idx

    if best_col == -1 or best_score < 0.3:
        numbers = []
        for row in data_rows:
            for cell in row:
                c = clean_and_validate(cell)
                if c:
                    numbers.append(c)
                    break
        return numbers

    numbers = []
    for row in data_rows:
        if best_col < len(row):
            cleaned = clean_and_validate(row[best_col])
            if cleaned:
                numbers.append(cleaned)
    return numbers


def read_numbers_from_txt(file_path: str) -> List[str]:
    """Read phone numbers from a plain text file (one per line)."""
    lines = []
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1', 'cp1258']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    numbers = []
    for line in lines:
        cleaned = clean_and_validate(line.strip())
        if cleaned:
            numbers.append(cleaned)
    return numbers


def read_numbers_from_csv(file_path: str) -> List[str]:
    """Read phone numbers from a CSV file with auto column detection."""
    rows = []
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1', 'cp1258']:
        try:
            with open(file_path, 'r', encoding=enc, newline='') as f:
                rows = list(csv.reader(f))
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not rows:
        return []
    return detect_and_extract_numbers(rows)


def read_numbers_from_xlsx(file_path: str) -> List[str]:
    """Read phone numbers from an Excel (.xlsx) file."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows = [[str(cell) if cell is not None else '' for cell in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
        return detect_and_extract_numbers(rows)
    except Exception:
        return []


def parse_numbers_from_text(raw_text: str) -> List[str]:
    """Parse and clean numbers from multiline or delimited string."""
    if not raw_text:
        return []
    tokens = re.split(r'[\r\n,;]+', raw_text)
    numbers = []
    seen = set()
    for tok in tokens:
        c = clean_and_validate(tok.strip())
        if c and c not in seen:
            seen.add(c)
            numbers.append(c)
    return numbers


def read_numbers(file_path_or_text: str) -> List[str]:
    """Universal phone number loader: accepts file path or raw string."""
    if not file_path_or_text:
        return []

    if os.path.exists(file_path_or_text):
        ext = os.path.splitext(file_path_or_text)[1].lower()
        if ext == '.txt':
            return read_numbers_from_txt(file_path_or_text)
        elif ext == '.csv':
            return read_numbers_from_csv(file_path_or_text)
        elif ext in ('.xlsx', '.xls'):
            return read_numbers_from_xlsx(file_path_or_text)
        else:
            return read_numbers_from_txt(file_path_or_text)

    return parse_numbers_from_text(file_path_or_text)
