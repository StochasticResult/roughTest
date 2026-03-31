"""Unit tests for the .s2p parser and nearest-frequency lookup."""

import math
import tempfile
import textwrap
from pathlib import Path

import pytest
import numpy as np

from services.s2p_parser import S2PData, parse_s2p


# ---------------------------------------------------------------- fixtures

def _write_s2p(content: str) -> Path:
    """Write content to a temp .s2p file and return its path."""
    f = tempfile.NamedTemporaryFile(suffix=".s2p", delete=False, mode="w")
    f.write(textwrap.dedent(content))
    f.close()
    return Path(f.name)


SAMPLE_DB = """\
! Sample 2-port S-parameter file
# GHZ S DB R 50
! freq  S11_dB S11_ang S21_dB S21_ang S12_dB S12_ang S22_dB S22_ang
6.0  -20.0 45.0  -1.5 10.0  -2.30 -5.0  -18.0 60.0
8.0  -19.5 44.0  -1.8 11.0  -3.45 -6.0  -17.5 59.0
10.0 -19.0 43.0  -2.1 12.0  -4.60 -7.0  -17.0 58.0
12.0 -18.5 42.0  -2.4 13.0  -5.75 -8.0  -16.5 57.0
"""

SAMPLE_MA = """\
# MHZ S MA R 50
6000.0  0.1 45.0  0.8 10.0  0.750 -5.0  0.12 60.0
8000.0  0.1 44.0  0.8 11.0  0.650 -6.0  0.12 59.0
"""

SAMPLE_RI = """\
# GHZ S RI R 50
6.0  0.05 0.08  0.7 0.1  0.6 0.3  0.04 0.09
"""

SAMPLE_CAL = """\
Freq Col2 Col3 Loss
6.0  0  0  -2.30
8.0  0  0  -3.45
10.0 0  0  -4.60
"""


# ---------------------------------------------------------------- tests

class TestParseDB:
    def test_basic_parse(self):
        path = _write_s2p(SAMPLE_DB)
        data = parse_s2p(path)
        assert data.num_points == 4
        assert data.freq_unit == "GHZ"
        assert data.data_format == "DB"

    def test_frequencies(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        np.testing.assert_allclose(
            data.frequencies_ghz, [6.0, 8.0, 10.0, 12.0]
        )

    def test_s12_values(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        np.testing.assert_allclose(
            data.s12_db, [-2.30, -3.45, -4.60, -5.75]
        )

    def test_freq_range(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        lo, hi = data.freq_range_ghz
        assert lo == pytest.approx(6.0)
        assert hi == pytest.approx(12.0)


class TestNearestFrequency:
    def test_exact_match(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        freq, s12 = data.find_nearest(8.0)
        assert freq == pytest.approx(8.0)
        assert s12 == pytest.approx(-3.45)

    def test_nearest_below(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        freq, s12 = data.find_nearest(7.9)
        assert freq == pytest.approx(8.0)
        assert s12 == pytest.approx(-3.45)

    def test_nearest_above(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        freq, s12 = data.find_nearest(11.5)
        assert freq == pytest.approx(12.0)
        assert s12 == pytest.approx(-5.75)

    def test_below_range(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        freq, s12 = data.find_nearest(1.0)
        assert freq == pytest.approx(6.0)
        assert s12 == pytest.approx(-2.30)

    def test_above_range(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        freq, s12 = data.find_nearest(20.0)
        assert freq == pytest.approx(12.0)
        assert s12 == pytest.approx(-5.75)

    def test_midpoint_prefers_lower_index(self):
        data = parse_s2p(_write_s2p(SAMPLE_DB))
        freq, _ = data.find_nearest(9.0)
        assert freq in (8.0, 10.0)


class TestParseMHz:
    def test_mhz_units(self):
        data = parse_s2p(_write_s2p(SAMPLE_MA))
        assert data.freq_unit == "MHZ"
        assert data.data_format == "MA"
        np.testing.assert_allclose(data.frequencies_ghz, [6.0, 8.0])

    def test_ma_to_db_conversion(self):
        data = parse_s2p(_write_s2p(SAMPLE_MA))
        expected_6 = 20.0 * math.log10(0.750)
        expected_8 = 20.0 * math.log10(0.650)
        assert data.s12_db[0] == pytest.approx(expected_6, abs=0.01)
        assert data.s12_db[1] == pytest.approx(expected_8, abs=0.01)


class TestParseRI:
    def test_ri_to_db(self):
        data = parse_s2p(_write_s2p(SAMPLE_RI))
        mag = math.sqrt(0.6**2 + 0.3**2)
        expected = 20.0 * math.log10(mag)
        assert data.s12_db[0] == pytest.approx(expected, abs=0.01)


class TestParseSimpleCal:
    def test_reads_frequency_and_loss_columns(self):
        data = parse_s2p(_write_s2p(SAMPLE_CAL))
        np.testing.assert_allclose(data.frequencies_ghz, [6.0, 8.0, 10.0])
        np.testing.assert_allclose(data.s12_db, [-2.30, -3.45, -4.60])

    def test_nearest_lookup_for_simple_cal(self):
        data = parse_s2p(_write_s2p(SAMPLE_CAL))
        freq, loss = data.find_nearest(8.2)
        assert freq == pytest.approx(8.0)
        assert loss == pytest.approx(-3.45)


class TestErrors:
    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            parse_s2p("nonexistent.s2p")

    def test_empty_file(self):
        path = _write_s2p("")
        with pytest.raises(ValueError, match="No valid data"):
            parse_s2p(path)
