"""Export and clipboard utilities for session result data."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import List

from PySide6.QtWidgets import QApplication

from models.result_row import ResultRow


class ExportService:
    """Provides CSV export and clipboard copy for ResultRow lists."""

    @staticmethod
    def rows_to_csv_string(rows: List[ResultRow], delimiter: str = ",") -> str:
        """Serialize rows to a CSV-formatted string."""
        if not rows:
            return ""
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=delimiter)
        writer.writerow(rows[0].EXPORT_HEADERS)
        for row in rows:
            writer.writerow(row.to_export_list())
        return buf.getvalue()

    @staticmethod
    def single_row_to_text(row: ResultRow, delimiter: str = "\t") -> str:
        """Format a single row as tab-separated text (for pasting into Excel)."""
        return delimiter.join(row.to_export_list())

    @staticmethod
    def copy_to_clipboard(text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    @staticmethod
    def copy_row(row: ResultRow) -> None:
        ExportService.copy_to_clipboard(ExportService.single_row_to_text(row))

    @staticmethod
    def copy_all_rows(rows: List[ResultRow]) -> None:
        text = ExportService.rows_to_csv_string(rows, delimiter="\t")
        ExportService.copy_to_clipboard(text)

    @staticmethod
    def export_csv(rows: List[ResultRow], filepath: str | Path) -> None:
        """Write rows to a CSV file."""
        filepath = Path(filepath)
        content = ExportService.rows_to_csv_string(rows)
        filepath.write_text(content, encoding="utf-8-sig")
