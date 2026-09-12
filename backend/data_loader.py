import os

import pandas as pd


def load_csv(file_path):
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise ValueError(f"Could not read CSV file: {e}")

    if df.empty:
        raise ValueError("The uploaded CSV file is empty.")

    return df


def load_excel(file_path, sheet_name=0):
    """Load an Excel workbook (.xlsx / .xls) into a DataFrame.

    Only the first sheet is read by default. Requires 'openpyxl'
    (for .xlsx) to be installed.
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {e}")

    if df.empty:
        raise ValueError("The uploaded Excel file is empty.")

    return df


def load_file(file_path):
    """Detect the file type from its extension and load it with the
    appropriate loader. Supports .csv, .xlsx and .xls files.
    """
    _, extension = os.path.splitext(file_path)
    extension = extension.lower()

    if extension == ".csv":
        return load_csv(file_path)

    elif extension in (".xlsx", ".xls"):
        return load_excel(file_path)

    else:
        raise ValueError(
            f"Unsupported file type '{extension}'. "
            "Please upload a .csv, .xlsx or .xls file."
        )