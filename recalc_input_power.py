"""Recalculate correct Actual Input Power from legacy wrong data.

Usage examples:
  python recalc_input_power.py --wrong-actual-input -9.3 --cal1-offset -0.5 --cal2-offset -1.2
  python recalc_input_power.py --input-meter-raw -10.0 --cal1-offset -0.5 --cal2-offset -1.2

Offset values can be entered as positive or negative; this tool uses magnitude.
"""

from __future__ import annotations

import argparse


def _mag(value: float) -> float:
    return abs(value)


def correct_from_wrong_actual(
    wrong_actual_input_dbm: float, cal1_offset_db: float, cal2_offset_db: float
) -> float:
    """Convert legacy wrong Actual Input Power to the corrected value.

    Legacy wrong formula (offset sign not normalized):
      wrong = input_raw - (-cal2_mag) + (-cal1_mag) = input_raw + cal2_mag - cal1_mag

    Correct formula (current):
      correct = input_raw - cal2_mag + cal1_mag

    Therefore:
      correct = wrong + 2 * (cal1_mag - cal2_mag)
    """
    cal1 = _mag(cal1_offset_db)
    cal2 = _mag(cal2_offset_db)
    return wrong_actual_input_dbm + 2.0 * (cal1 - cal2)


def correct_from_input_meter(
    input_meter_raw_dbm: float, cal1_offset_db: float, cal2_offset_db: float
) -> float:
    """Compute corrected Actual Input Power directly from raw meter + offsets."""
    cal1 = _mag(cal1_offset_db)
    cal2 = _mag(cal2_offset_db)
    return input_meter_raw_dbm - cal2 + cal1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Recalculate corrected Actual Input Power without UI."
    )
    p.add_argument("--wrong-actual-input", type=float, help="Legacy wrong Actual Input Power (dBm)")
    p.add_argument("--input-meter-raw", type=float, help="Raw input power meter reading (dBm)")
    p.add_argument("--cal1-offset", type=float, help="cal1 offset (dB, sign optional)")
    p.add_argument("--cal2-offset", type=float, help="cal2 offset (dB, sign optional)")
    return p


def _ask_float(prompt: str) -> float:
    while True:
        text = input(prompt).strip()
        try:
            return float(text)
        except ValueError:
            print("Invalid number, please try again.")


def main() -> None:
    args = _build_parser().parse_args()

    wrong = args.wrong_actual_input
    raw = args.input_meter_raw
    cal1 = args.cal1_offset
    cal2 = args.cal2_offset

    if wrong is None and raw is None:
        print("Select input mode:")
        print("  1) I have legacy wrong Actual Input Power")
        print("  2) I have raw Input Meter Reading")
        mode = input("Enter 1 or 2: ").strip()
        if mode == "1":
            wrong = _ask_float("Enter legacy wrong Actual Input Power (dBm): ")
        else:
            raw = _ask_float("Enter raw Input Meter Reading (dBm): ")

    if cal1 is None:
        cal1 = _ask_float("Enter cal1 offset (dB, signed or unsigned): ")
    if cal2 is None:
        cal2 = _ask_float("Enter cal2 offset (dB, signed or unsigned): ")

    if wrong is not None:
        corrected = correct_from_wrong_actual(wrong, cal1, cal2)
        print(f"Corrected Actual Input Power = {corrected:+.4f} dBm")
    else:
        corrected = correct_from_input_meter(raw, cal1, cal2)
        print(f"Computed Actual Input Power = {corrected:+.4f} dBm")

    print(f"(Offset magnitudes used: cal1={abs(cal1):.4f} dB, cal2={abs(cal2):.4f} dB)")


if __name__ == "__main__":
    main()
