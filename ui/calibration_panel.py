"""Calibration file loader panel — shared between Small & Large Signal tabs."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.calibration_service import CalibrationService


class _CalFileRow(QWidget):
    """Compact calibration loader row."""

    def __init__(
        self,
        cal_key: str,
        description: str,
        cal_service: CalibrationService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._key = cal_key
        self._cal = cal_service

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._label = QLabel(f"{cal_key.upper()}  {description}")
        # self._label.setMinimumWidth(230) # Removed to prevent cutoff/overflow
        self._label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        layout.addWidget(self._label)

        self._status = QLabel("Not loaded")
        self._status.setObjectName("status_warn")
        # self._status.setMinimumWidth(85)
        layout.addWidget(self._status)

        self._summary = QLabel("No file selected.")
        self._summary.setWordWrap(True)
        self._summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._summary, 1)

        self._btn = QPushButton("Load")
        self._btn.setMinimumWidth(80)
        self._btn.clicked.connect(self._load_file)
        layout.addWidget(self._btn)

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self._key} calibration file",
            "",
            "Calibration Files (*.cal *.s2p);;Touchstone Files (*.s2p);;All Files (*)",
        )
        if not path:
            return
        self.load_from_path(path)

    def load_from_path(self, path: str) -> None:
        try:
            self._cal.load(self._key, path)
            self._status.setText("Loaded")
            self._status.setObjectName("status_ok")
            self._status.style().polish(self._status)
            self._summary.setText(f"{Path(path).name} | {self._cal.summary(self._key)}")
        except Exception as exc:
            self._status.setText("Error")
            self._status.setObjectName("status_err")
            self._status.style().polish(self._status)
            self._summary.setText(str(exc)[:120])


class CalibrationPanel(QGroupBox):
    """Panel containing four compact calibration rows."""

    def __init__(
        self,
        cal_service: CalibrationService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("Calibration Files", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._rows: Dict[str, _CalFileRow] = {}

        for key, desc in CalibrationService.CAL_LABELS.items():
            row = _CalFileRow(key, desc, cal_service, self)
            self._rows[key] = row
            layout.addWidget(row)
            
    def load_cal_file(self, key: str, path: str) -> None:
        if key in self._rows:
            self._rows[key].load_from_path(path)
