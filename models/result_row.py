from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ResultRow:
    """One measurement result row for session tracking and export."""

    mode: str  # "small_signal" or "large_signal"
    frequency_ghz: float

    input_meter_raw_dbm: Optional[float] = None
    output_meter_raw_dbm: Optional[float] = None
    analyzer_raw_dbm: Optional[float] = None

    cal1_matched_freq_ghz: Optional[float] = None
    cal1_s12_db: Optional[float] = None
    cal2_matched_freq_ghz: Optional[float] = None
    cal2_s12_db: Optional[float] = None
    cal3_matched_freq_ghz: Optional[float] = None
    cal3_s12_db: Optional[float] = None
    cal4_matched_freq_ghz: Optional[float] = None
    cal4_s12_db: Optional[float] = None

    actual_input_power_dbm: Optional[float] = None
    actual_output_power_dbm: Optional[float] = None
    actual_spur_or_harmonic_dbm: Optional[float] = None
    gain_db: Optional[float] = None
    output_power_w: Optional[float] = None

    timestamp: datetime = field(default_factory=datetime.now)

    # ---------- export helpers ----------

    EXPORT_HEADERS: list[str] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "EXPORT_HEADERS", [
            "Frequency (GHz)",
            "Input Meter Raw (dBm)",
            "Output Meter Raw (dBm)",
            "Analyzer Raw (dBm)",
            "cal1 Offset (dB)",
            "cal2 Offset (dB)",
            "cal3 Offset (dB)",
            "cal4 Offset (dB)",
            "Actual Input Power (dBm)",
            "Actual Output Power (dBm)",
            "Actual Output Power (W)",
            "Actual Spur/Harmonic (dBm)",
            "Gain (dB)",
            "Timestamp",
            "Mode",
        ])

    def to_export_list(self) -> list[str]:
        """Return a list of formatted strings matching EXPORT_HEADERS order."""

        def _fmt(v: Optional[float], decimals: int = 2) -> str:
            return f"{v:.{decimals}f}" if v is not None else ""

        return [
            _fmt(self.frequency_ghz, 4),
            _fmt(self.input_meter_raw_dbm),
            _fmt(self.output_meter_raw_dbm),
            _fmt(self.analyzer_raw_dbm),
            _fmt(self.cal1_s12_db),
            _fmt(self.cal2_s12_db),
            _fmt(self.cal3_s12_db),
            _fmt(self.cal4_s12_db),
            _fmt(self.actual_input_power_dbm),
            _fmt(self.actual_output_power_dbm),
            _fmt(self.output_power_w, 6),
            _fmt(self.actual_spur_or_harmonic_dbm),
            _fmt(self.gain_db),
            self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.mode,
        ]
