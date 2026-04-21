"""Calibration file parser.

For this project, calibration values are always taken from:
- column 1: frequency
- column 4: loss/offset in dB

Header option lines (e.g. ``# HZ ...``) are still used only to
determine frequency unit conversion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np


_FREQ_MULTIPLIER = {
    "HZ": 1.0,
    "KHZ": 1e3,
    "MHZ": 1e6,
    "GHZ": 1e9,
}


@dataclass(frozen=True)
class S2PData:
    """Parsed 2-port S-parameter data with nearest-frequency lookup."""

    frequencies_hz: np.ndarray
    s12_db: np.ndarray
    freq_unit: str
    data_format: str
    num_points: int
    filepath: str

    @property
    def frequencies_ghz(self) -> np.ndarray:
        return self.frequencies_hz / 1e9

    @property
    def freq_range_ghz(self) -> Tuple[float, float]:
        if self.num_points == 0:
            return (0.0, 0.0)
        return (float(self.frequencies_ghz[0]), float(self.frequencies_ghz[-1]))

    def find_nearest(self, freq_ghz: float) -> Tuple[float, float]:
        """Return (matched_freq_ghz, s12_db) for the nearest point."""
        if self.num_points == 0:
            raise ValueError("S2P data is empty")
        freq_hz = freq_ghz * 1e9
        idx = int(np.argmin(np.abs(self.frequencies_hz - freq_hz)))
        matched_ghz = float(self.frequencies_hz[idx] / 1e9)
        matched_s12 = float(self.s12_db[idx])
        return (matched_ghz, matched_s12)


def parse_s2p(filepath: str | Path) -> S2PData:
    """Parse a calibration file and return structured offset data.

    Raises ``ValueError`` on malformed files.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    freq_unit = "GHZ"
    data_format = "DB"

    raw_freqs: list[float] = []
    raw_s12_vals: list[Tuple[float, float]] = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("!"):
                continue

            if line.startswith("#"):
                freq_unit, _ = _parse_option_line(line)
                continue

            parts = line.split()
            if not parts:
                continue

            try:
                vals = [float(v) for v in parts]
            except ValueError:
                continue

            # Project rule: always use the 4th column as calibration value.
            if len(vals) >= 4:
                raw_freqs.append(vals[0])
                raw_s12_vals.append((vals[3], 0.0))

    if not raw_freqs:
        raise ValueError(f"No valid data points found in {filepath}")

    multiplier = _FREQ_MULTIPLIER.get(freq_unit.upper(), 1e9)
    frequencies_hz = np.array(raw_freqs) * multiplier

    s12_db = _convert_to_db(raw_s12_vals, data_format)

    return S2PData(
        frequencies_hz=frequencies_hz,
        s12_db=s12_db,
        freq_unit=freq_unit,
        data_format=data_format,
        num_points=len(raw_freqs),
        filepath=str(filepath),
    )


def _parse_option_line(line: str) -> Tuple[str, str]:
    """Extract frequency unit and data format from the option line."""
    tokens = line.upper().replace("#", "").split()
    freq_unit = "GHZ"
    data_format = "MA"

    for tok in tokens:
        if tok in _FREQ_MULTIPLIER:
            freq_unit = tok
        elif tok in ("DB", "MA", "RI"):
            data_format = tok
    return freq_unit, data_format


def _convert_to_db(
    pairs: list[Tuple[float, float]], data_format: str
) -> np.ndarray:
    """Convert S12 value pairs to dB depending on the source format."""
    result = np.empty(len(pairs), dtype=np.float64)

    for i, (v1, v2) in enumerate(pairs):
        if data_format == "DB":
            # Calibration files usually store loss as negative dB.
            # Use positive magnitude globally so all downstream features
            # (target error, auto level, export) share one consistent sign.
            result[i] = abs(v1)
        elif data_format == "MA":
            mag = abs(v1)
            if mag > 0:
                result[i] = 20.0 * math.log10(mag)
            else:
                result[i] = -200.0  # floor value for zero magnitude
        elif data_format == "RI":
            mag = math.sqrt(v1 * v1 + v2 * v2)
            if mag > 0:
                result[i] = 20.0 * math.log10(mag)
            else:
                result[i] = -200.0
        else:
            result[i] = abs(v1)  # fallback: treat as dB magnitude

    return result
