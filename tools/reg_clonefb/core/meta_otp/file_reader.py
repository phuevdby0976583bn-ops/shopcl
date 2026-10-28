import os
import re
import csv
import json
from core.meta_otp.config import *

# Settings cache (loaded once)
_settings_cache = None

def load_settings(setting_key="api_settings"):
    """Load and cache settings from Setting.json."""
    global _settings_cache
    if _settings_cache is None:
        try:
            with open("Setting.json", "r") as f:
                _settings_cache = json.load(f)
        except:
            _settings_cache = {}

        if "api_settings" not in _settings_cache and "forget_settings" in _settings_cache:
            _settings_cache["api_settings"] = _settings_cache.get("forget_settings", {})

    return _settings_cache.get(setting_key, {})

CLEAN_PATTERN = re.compile(r'[\s\-\(\)\.]')
PHONE_PATTERN = re.compile(r'^\+?\d{7,15}$')

def clean_and_validate(value):
    """Strip formatting characters and validate as phone number."""
    if not value:
        return None
    cleaned = CLEAN_PATTERN.sub('', str(value).strip())
    if PHONE_PATTERN.match(cleaned):
        return cleaned
    return None

def column_phone_score(col_values):
    """Score a column by how many values look like phone numbers (0.0 to 1.0)."""
    total = 0
    phone_count = 0
    for v in col_values:
        if v and str(v).strip():
            total += 1
            if clean_and_validate(v) is not None:
                phone_count += 1
    return phone_count / total if total > 0 else 0

def detect_and_extract_numbers(rows):
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

    # Sample up to 100 rows for column detection
    sample_size = min(len(data_rows), 100)
    sample_rows = data_rows[:sample_size]

    best_col = -1
    best_score = 0

    for col_idx in range(max_cols):
        col_values = (row[col_idx] if col_idx < len(row) else '' for row in sample_rows)
        score = column_phone_score(col_values)
        if score > best_score:
            best_score = score
            best_col = col_idx

    if best_col == -1 or best_score < 0.5:
        return []

    numbers = []
    for row in data_rows:
        if best_col < len(row):
            cleaned = clean_and_validate(row[best_col])
            if cleaned:
                numbers.append(cleaned)
    return numbers

def read_numbers_from_txt(file_path):
    """Read phone numbers from a plain text file (one per line)."""
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        return []

    numbers = []
    for line in lines:
        cleaned = clean_and_validate(line.strip())
        if cleaned:
            numbers.append(cleaned)
    return numbers

def read_numbers_from_csv(file_path):
    """Read phone numbers from a CSV file with auto column detection."""
    rows = []
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=enc, newline='') as f:
                rows = list(csv.reader(f))
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not rows:
        return []
    return detect_and_extract_numbers(rows)

def read_numbers_from_xlsx(file_path):
    """Read phone numbers from an Excel (.xlsx) file."""
    try:
        import openpyxl
    except ImportError:
        print(f"{RED} openpyxl not installed! Run: pip install openpyxl")
        return []

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows = [[str(cell) if cell is not None else '' for cell in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
    except Exception as e:
        print(f"{RED} Error reading Excel file: {e}")
        return []

    if not rows:
        return []
    return detect_and_extract_numbers(rows)

def read_numbers(file_path):
    """Read phone numbers from any supported file format (.txt, .csv, .xlsx)."""
    if not os.path.exists(file_path):
        return []

    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.txt':
        return read_numbers_from_txt(file_path)
    elif ext == '.csv':
        return read_numbers_from_csv(file_path)
    elif ext == '.xlsx':
        return read_numbers_from_xlsx(file_path)
    else:
        return []


# Interactive file selection and number loading

def process_number_list_fallback():
    """Fallback: try to load numbers from Number_List.txt directly."""
    if os.path.exists("Number_List.txt"):
        with open("Number_List.txt", "r", encoding="utf-8", errors="ignore") as f:
            numbers = [line.strip() for line in f if line.strip()]
        if numbers:
            print(f"{GREEN} [{RED}●{GREEN}] Selected File {EKL} Number_List.txt")
            input(f"{WHITE} Press Enter to Start Processing {len(numbers)} Numbers...")
            return numbers
        else:
            print(f"{WHITE} 'Number_List.txt' file is empty.")
    else:
        print(f"{WHITE} 'Number_List.txt' file was not found.")

    input(f"{WHITE} Press Enter to exit...")
    return None

def finalize_numbers(numbers, source_name):
    """Remove duplicates, save to Number_List.txt, and confirm with user."""
    if numbers:
        nums = list(dict.fromkeys(numbers))
        with open("Number_List.txt", "w", encoding="utf-8", errors="ignore") as f:
            for num in nums:
                f.write(num + "\n")

        print(f"{GREEN} [{RED}●{GREEN}] Total Unique Numbers Extracted {EKL} {len(nums)}")
        if source_name != "Number_List.txt":
            print(f"{GREEN} [{RED}●{GREEN}] Found from: {source_name}")
            print(f"{GREEN} [{RED}●{GREEN}] Saved to 'Number_List.txt'\n")

        input(f"{WHITE} Press Enter to Start Processing {len(nums)} Numbers...")
        return nums
    return None

def file_input(setting_key="api_settings"):
    """Interactive file selection based on settings configuration."""
    settings = load_settings(setting_key)
    file_settings = settings.get("file_input_settings", {})
    always_use_txt = file_settings.get("always_use_txt", False)
    use_multiple_excel = file_settings.get("use_multiple_excel_files", False)

    # Mode 1: Always use Number_List.txt
    if always_use_txt:
        return process_number_list_fallback()

    # Mode 2: Batch process all Excel files in current directory
    if use_multiple_excel:
        xlsx_files = [f for f in os.listdir('.') if f.endswith(".xlsx") and not f.startswith("~$")]
        if xlsx_files:
            print(f"{GREEN} [{RED}●{GREEN}] Found {len(xlsx_files)} Excel Files.")
            all_numbers = []
            for f in xlsx_files:
                print(f"{WHITE} Extracting from {EKL} {f}...")
                nums = read_numbers_from_xlsx(f)
                if nums:
                    all_numbers.extend(nums)
                    print(f"{GREEN}  -> Found {len(nums)} numbers.")
                else:
                    print(f"{RED}  -> Failed: No valid numbers found or error occurred.")

            if all_numbers:
                return finalize_numbers(all_numbers, f"{len(xlsx_files)} Excel files")
            else:
                print(f"{RED} No valid numbers found in any Excel files.")
                return process_number_list_fallback()
        else:
            print(f"{WHITE} No Excel files found.")
            return process_number_list_fallback()

    # Mode 3: Interactive file selection
    supported_ext = ('.txt', '.csv', '.xlsx')
    files = [f for f in os.listdir('.') if f.lower().endswith(supported_ext) and not f.startswith("~$")]

    if not files:
        print(f"{WHITE} No Supported files found.")
        return process_number_list_fallback()

    filename = None
    if len(files) == 1:
        filename = files[0]
    else:
        print(f"{GREEN} [{RED}●{GREEN}] Found {len(files)} File(s):")
        for idx, f in enumerate(files, 1):
            print(f" {GREEN}[{RED}{idx}{GREEN}] {WHITE}{f}")
        print(f"{LINE}")

        while True:
            try:
                choice = input(f"{GREEN} [{RED}●{GREEN}] Select File (1-{len(files)}) {EKL} ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(files):
                        filename = files[idx]
                        break
                print(f"{RED} Invalid selection!")
            except:
                pass

    print(f"{GREEN} [{RED}●{GREEN}] Selected File {EKL} {filename}\n")

    nums = read_numbers(filename)
    if nums:
        return finalize_numbers(nums, filename)
    else:
        print(f"{RED} Error: No valid phone numbers extracted from {filename}.")
        return process_number_list_fallback()
