"""Pure calculation functions for RF power measurements.

All functions operate on plain floats; no side effects.
Internal precision is maintained — rounding is only for display.
"""

from __future__ import annotations

from typing import Optional


class CalculationService:
    """Stateless service holding the calibration-corrected formulas."""

    @staticmethod
    def actual_input_power(
        input_meter_dbm: float,
        cal1_offset_db: float,
        cal2_offset_db: float,
    ) -> float:
        """Actual Input Power = Input Meter Reading − cal2_offset + cal1_offset"""
        return input_meter_dbm - cal2_offset_db + cal1_offset_db

    @staticmethod
    def actual_output_power(
        output_meter_dbm: float,
        cal3_offset_db: float,
    ) -> float:
        """Actual Output Power = Output Meter Reading + cal3_offset"""
        return output_meter_dbm + cal3_offset_db

    @staticmethod
    def actual_spur_or_harmonic(
        analyzer_dbm: float,
        cal4_offset_db: float,
    ) -> float:
        """Actual Spur/Harmonic = Analyzer Reading + cal4_offset"""
        return analyzer_dbm + cal4_offset_db

    @staticmethod
    def gain(
        actual_output_dbm: float,
        actual_input_dbm: float,
    ) -> float:
        """Gain (dB) = Actual Output Power − Actual Input Power"""
        return actual_output_dbm - actual_input_dbm

    @staticmethod
    def dbm_to_watt(power_dbm: float) -> float:
        """Convert dBm to Watts: W = 10^((dBm − 30) / 10)"""
        return 10.0 ** ((power_dbm - 30.0) / 10.0)

    @staticmethod
    def relative_dbc(
        signal_dbm: float,
        reference_dbm: float,
    ) -> float:
        """Return dBc = signal − reference (both in dBm)."""
        return signal_dbm - reference_dbm

    @staticmethod
    def format_dbm(value: Optional[float], decimals: int = 2) -> str:
        if value is None:
            return "---"
        return f"{value:+.{decimals}f}"

    @staticmethod
    def format_db(value: Optional[float], decimals: int = 2) -> str:
        if value is None:
            return "---"
        return f"{value:+.{decimals}f}"

    @staticmethod
    def format_watt(value: Optional[float], decimals: int = 6) -> str:
        if value is None:
            return "---"
        return f"{value:.{decimals}f}"
