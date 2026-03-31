"""Unit tests for the calculation service formulas."""

import math
import pytest

from services.calculation_service import CalculationService


@pytest.fixture
def calc():
    return CalculationService()


class TestActualInputPower:
    def test_basic(self, calc):
        result = calc.actual_input_power(
            input_meter_dbm=-10.0,
            cal1_offset_db=-0.5,
            cal2_offset_db=-1.2,
        )
        # -10.0 - (-1.2) + (-0.5) = -10.0 + 1.2 - 0.5 = -9.3
        assert result == pytest.approx(-9.3)

    def test_positive_offsets(self, calc):
        result = calc.actual_input_power(
            input_meter_dbm=5.0,
            cal1_offset_db=0.3,
            cal2_offset_db=0.8,
        )
        # 5.0 - 0.8 + 0.3 = 4.5
        assert result == pytest.approx(4.5)

    def test_zero_offsets(self, calc):
        result = calc.actual_input_power(-12.0, 0.0, 0.0)
        assert result == pytest.approx(-12.0)


class TestActualOutputPower:
    def test_basic(self, calc):
        result = calc.actual_output_power(
            output_meter_dbm=20.0,
            cal3_offset_db=-1.5,
        )
        # 20.0 - (-1.5) = 21.5
        assert result == pytest.approx(21.5)

    def test_positive_offset(self, calc):
        result = calc.actual_output_power(15.0, 0.8)
        # 15.0 - 0.8 = 14.2
        assert result == pytest.approx(14.2)


class TestActualSpurHarmonic:
    def test_basic(self, calc):
        result = calc.actual_spur_or_harmonic(-45.0, -2.0)
        # -45.0 - (-2.0) = -43.0
        assert result == pytest.approx(-43.0)


class TestGain:
    def test_basic(self, calc):
        result = calc.gain(actual_output_dbm=20.0, actual_input_dbm=-5.0)
        assert result == pytest.approx(25.0)

    def test_negative_gain(self, calc):
        result = calc.gain(actual_output_dbm=-10.0, actual_input_dbm=5.0)
        assert result == pytest.approx(-15.0)


class TestDbmToWatt:
    def test_0dbm(self, calc):
        assert calc.dbm_to_watt(0.0) == pytest.approx(0.001)

    def test_30dbm(self, calc):
        assert calc.dbm_to_watt(30.0) == pytest.approx(1.0)

    def test_20dbm(self, calc):
        assert calc.dbm_to_watt(20.0) == pytest.approx(0.1)

    def test_negative(self, calc):
        assert calc.dbm_to_watt(-10.0) == pytest.approx(1e-4)

    def test_formula_identity(self, calc):
        # 10^((dBm-30)/10)
        for dbm in [-30, -10, 0, 10, 20, 30, 40]:
            expected = 10 ** ((dbm - 30) / 10)
            assert calc.dbm_to_watt(float(dbm)) == pytest.approx(expected)


class TestRelativeDbc:
    def test_basic(self, calc):
        result = calc.relative_dbc(-45.0, 20.0)
        assert result == pytest.approx(-65.0)


class TestFormatting:
    def test_format_dbm_positive(self, calc):
        assert calc.format_dbm(12.345) == "+12.35"

    def test_format_dbm_negative(self, calc):
        assert calc.format_dbm(-3.1) == "-3.10"

    def test_format_dbm_none(self, calc):
        assert calc.format_dbm(None) == "---"

    def test_format_watt(self, calc):
        assert calc.format_watt(0.001234) == "0.001234"
