"""Manages four calibration .s2p files and provides offset lookups."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from .s2p_parser import S2PData, parse_s2p


@dataclass
class CalOffset:
    """Offset result for a single calibration file at a given frequency."""
    matched_freq_ghz: float
    s12_db: float


class CalibrationService(QObject):
    """Holds the four calibration datasets and emits a signal when any changes."""

    calibration_changed = Signal()

    CAL_LABELS: Dict[str, str] = {
        "cal1": "SigGen → Input PM",
        "cal2": "SigGen → DUT",
        "cal3": "DUT → Output PM",
        "cal4": "DUT → Sig Analyzer",
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._data: Dict[str, Optional[S2PData]] = {
            "cal1": None, "cal2": None, "cal3": None, "cal4": None,
        }
        self._paths: Dict[str, str] = {}

    def load(self, key: str, filepath: str | Path) -> S2PData:
        """Load a calibration file.  Raises on parse error."""
        if key not in self._data:
            raise KeyError(f"Unknown calibration key: {key}")
        data = parse_s2p(filepath)
        self._data[key] = data
        self._paths[key] = str(filepath)
        self.calibration_changed.emit()
        return data

    def get_loaded_path(self, key: str) -> Optional[str]:
        return self._paths.get(key)

    def get_data(self, key: str) -> Optional[S2PData]:
        return self._data.get(key)

    def is_loaded(self, key: str) -> bool:
        return self._data.get(key) is not None

    def all_loaded(self) -> bool:
        return all(v is not None for v in self._data.values())

    def get_offset(self, key: str, freq_ghz: float) -> Optional[CalOffset]:
        """Look up the nearest-frequency S12 offset for a cal file."""
        data = self._data.get(key)
        if data is None:
            return None
        matched_ghz, s12_db = data.find_nearest(freq_ghz)
        return CalOffset(matched_freq_ghz=matched_ghz, s12_db=s12_db)

    def get_all_offsets(
        self, freq_ghz: float
    ) -> Dict[str, Optional[CalOffset]]:
        """Return offsets for all four cal files at the given frequency."""
        return {key: self.get_offset(key, freq_ghz) for key in self._data}

    def summary(self, key: str) -> str:
        """Human-readable summary for a cal file."""
        data = self._data.get(key)
        if data is None:
            return "Not loaded"
        lo, hi = data.freq_range_ghz
        return f"{lo:.2f}-{hi:.2f} GHz, {data.num_points} pts"
