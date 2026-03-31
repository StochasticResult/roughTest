# RF Lambda Test Assistant

## Start

Double-click:

`start_rf_lambda_app.bat`

## Before Use

Prepare these four calibration files:

1. `cal1`: signal generator -> input power meter
2. `cal2`: signal generator -> DUT
3. `cal3`: DUT -> output power meter
4. `cal4`: DUT -> signal analyzer

## How To Use

1. Open the app.
2. Click `Show Calibration Files`.
3. Load `cal1`, `cal2`, `cal3`, and `cal4`.
4. Open the `Small Signal` tab or the `Large Signal` tab.
5. Enter the test frequency in `GHz`, or choose one from the quick list.
6. Enter `Input Power` manually in `dBm`.
7. Enter `Output Power` manually in `dBm`.
8. Enter the signal analyzer reading in `dBm`.
9. Read the calculated results:
   - Actual Input
   - Actual Output
   - Actual Spur / Harmonic
   - Gain
   - Output Power in Watts
10. Click `Save Current` to store the current row.
11. Use `Copy Current`, `Copy All`, or `Export CSV` when needed.

## Tab Meaning

- `Small Signal`: analyzer input is treated as spur
- `Large Signal`: analyzer input is treated as harmonic

## Notes

- Power input is manual.
- Calibration lookup uses the nearest frequency point.
- Calibration files can be either:
  - `.s2p`: reads `S12`
  - `.cal`: reads column 1 as frequency and column 4 as loss
- Displayed offsets are rounded to 2 decimal places.
