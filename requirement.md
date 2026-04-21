Build a Python desktop application for RF Lambda test data assistance and live measurement calculation.

Goal:
Create a practical, accurate, easy-to-use desktop tool that helps operators perform and record RF amplifier tests for the RFLUPA06G12GD workflow. The tool is for Small Signal and Large Signal testing only. Ignore vibration test completely. The highest priority is calculation accuracy and result readability. UX should be clean, convenient, and fast for bench use.

Tech stack requirements:
- Language: Python
- GUI: Prefer PySide6 or PyQt6
- Architecture: clean, modular, maintainable
- Package structure should be clear
- Include a requirements.txt
- Include a README with setup and usage instructions
- If possible, support Windows first
- The app should be runnable as a normal desktop app

Main concept:
The user will provide four .s2p calibration files:
1. cal1: signal generator -> input power meter
2. cal2: signal generator -> DUT
3. cal3: DUT -> output power meter
4. cal4: DUT -> signal analyzer

The software must parse these .s2p files and, for any requested frequency, find the nearest frequency point in the file, read S12 in dB, and round/display that offset to 2 decimal places.

Important:
- Use nearest frequency, not interpolation
- Read S12
- Format offset values as xx.xx
- Frequency units in the s2p files may need to be handled correctly
- Be careful with GHz / MHz / Hz unit parsing if needed
- Assume these offsets are in dB

Device I/O requirements:
The software should automatically read two R&S power meters:
- Output power meter: NRP-Z85, serial 102918
- Input power meter: NRP-Z85, serial 101874

Do not hardcode fragile assumptions if device discovery can be done robustly.
Try to identify the connected meters by serial number and assign them correctly.

Signal analyzer behavior:
- The signal analyzer is NOT required to be fully controlled by the software for sweep setup
- The operator will manually adjust the signal analyzer and manually read harmonic or spur power from it
- The software only needs a user input field for the analyzer reading in dBm
- In Large Signal mode this analyzer value is for harmonic
- In Small Signal mode this analyzer value is for spur

Tabs / workflow:
Create two separate tabs:
1. Small Signal
2. Large Signal

Keep them separate because the calculation meaning and displayed labels differ.

UI / user experience requirements:
The UI must be optimized for bench use:
- Large, clear numeric displays
- Easy frequency entry
- Very few clicks
- Real-time updates when values change
- Clearly labeled fields
- Good visibility for live calculated values
- A clean layout for operator workflow
- Avoid clutter
- Make it obvious which values are raw meter readings vs corrected actual values
- Make it easy for the user to copy values into Excel / report tables manually

Recommended UI layout per tab:
A. Calibration section
- Load cal1 file
- Load cal2 file
- Load cal3 file
- Load cal4 file
- Show file loaded status
- Show parsed status
- Optional: show a small summary like frequency range and point count

B. Test input section
- Frequency input template for current test frequency
- User can type the current frequency being tested
- Prefer a convenient input format, e.g. GHz numeric input
- Show nearest matched frequencies from each cal file
- Show the corresponding offsets used from each cal file
- Display offsets with 2 decimals

C. Live measurement section
- Read input power meter live
- Read output power meter live
- Display raw meter readings live
- Let the user refresh automatically or manually
- Consider polling every 0.5 to 1 second, but make it configurable
- Clearly show connection status of each meter

D. Analyzer entry section
- User manually enters analyzer dBm reading
- In Small Signal tab label this as “Signal Analyzer Spur Reading (dBm)”
- In Large Signal tab label this as “Signal Analyzer Harmonic Reading (dBm)”

E. Calculated results section
Display clearly:
- Actual Input Power
- Actual Output Power
- Actual Spur or Actual Harmonic
- Gain = Actual Output Power - Actual Input Power
- Output Power in Watt
Use big readable values.

F. Quick copy / export section
- Let user copy the currently displayed row as text or CSV
- Let user append current result to an internal session table
- Let user export session table to CSV / Excel-friendly format
- This is very useful because user wants to fill final report manually

Core calculation rules:
Use exactly these formulas.

1. Actual Input Power
Actual Input Power = Input Power Meter Reading - cal2_offset + cal1_offset

Where:
- Input Power Meter Reading is the live reading from the input meter
- cal2_offset is the nearest-frequency S12 from cal2
- cal1_offset is the nearest-frequency S12 from cal1

2. Actual Output Power
Actual Output Power = Output Power Meter Reading - cal3_offset

Where:
- Output Power Meter Reading is the live reading from the output meter
- cal3_offset is the nearest-frequency S12 from cal3

3. Actual Harmonic or Actual Spur
Actual Harmonic_or_Spur = User Entered Signal Analyzer Reading - cal4_offset

Where:
- User Entered Signal Analyzer Reading is manually typed by operator
- cal4_offset is the nearest-frequency S12 from cal4

4. Gain
Gain = Actual Output Power - Actual Input Power

5. Output Power in Watt
Power_W = 10 ^ ((Power_dBm - 30) / 10)

Use Actual Output Power for this conversion.

Operator workflow to support:
The workflow should match this:

1. Operator adjusts signal generator
2. Software continuously shows the live output power meter reading and also the corrected real output power using cal3 offset, so operator can adjust signal generator until desired real output power is reached
3. Operator manually adjusts signal analyzer and reads the harmonic or spur
4. Operator types the analyzer reading into the software
5. Software immediately computes all corrected values in real time
6. User manually fills the official report table, or optionally copies the row from the app

Important behavior details:
- Every time the frequency changes, recompute all nearest offsets and all corrected values immediately
- Every time the analyzer entry changes, recompute immediately
- Every time the live meter reading updates, recompute immediately
- If any required input is missing, show blank or clearly indicate incomplete state
- Round displayed results reasonably, e.g. 2 decimals for dBm, dB, offsets; maybe 3 decimals for Watts if appropriate
- Internally keep full precision as much as possible, only round for display
- Make sure sign handling is correct for negative offsets
- Be careful not to accidentally use absolute value for offsets

Offset parser requirements:
Implement a robust .s2p parser with these features:
- Read Touchstone .s2p files
- Parse option line correctly if possible
- Extract frequency and S12 in dB
- If data is not already in dB/angle format, convert correctly if needed
- But if simplifying assumptions are made, document them clearly
- When queried with a frequency, find the nearest available point
- Return:
  - matched frequency
  - matched S12 dB offset
- Display offset rounded to 2 decimals
- Add tests for the parser

Device communication requirements:
For the R&S NRP-Z85 meters:
- Try to implement direct device reading in Python
- Prefer robust communication using available VISA / Rohde & Schwarz libraries if practical
- Separate hardware layer from UI layer
- The app should not freeze when reading devices
- Use worker threads or async-safe polling
- Show device status:
  - connected
  - disconnected
  - reading error
- If the meters are not available, allow a simulation or manual-entry fallback mode for development/testing
- Very important: make manual fallback possible so the app can still be used/tested without hardware connected

Recommended implementation structure:
- app.py or main.py
- ui/
- services/
  - s2p_parser.py
  - calibration_service.py
  - power_meter_service.py
  - calculation_service.py
  - export_service.py
- models/
- tests/

Suggested data model for one result row:
- mode: small_signal or large_signal
- frequency_ghz
- input_meter_raw_dbm
- output_meter_raw_dbm
- analyzer_raw_dbm
- cal1_matched_freq
- cal1_s12_db
- cal2_matched_freq
- cal2_s12_db
- cal3_matched_freq
- cal3_s12_db
- cal4_matched_freq
- cal4_s12_db
- actual_input_power_dbm
- actual_output_power_dbm
- actual_spur_or_harmonic_dbm
- gain_db
- output_power_w
- timestamp

Small Signal tab specifics:
- Analyzer input label should be Spur Reading
- Corrected analyzer result label should be Actual Spur (dBm)
- Optionally also show Spur (dBc) = Actual Spur - Actual Output Power, if useful
- Make labels and exported field names match small signal meaning

Large Signal tab specifics:
- Analyzer input label should be Harmonic Reading
- Corrected analyzer result label should be Actual Harmonic (dBm)
- Optionally also show Harmonic (dBc) = Actual Harmonic - Actual Output Power
- This is useful for later manual report filling

Output / export expectations:
The official document contains many result tables. The software does not need to auto-generate the final customer document immediately unless you can do it cleanly and reliably.
Best practical output:
- Session result table inside the app
- Export to CSV
- Export to Excel-friendly CSV with clear headers
- Allow copy-current-row
- Allow copy-all-session-rows
- Keep output very readable and directly usable for manual report filling

Recommended displayed fields in exported rows:
- Frequency (GHz)
- Input Meter Raw (dBm)
- Output Meter Raw (dBm)
- Analyzer Raw (dBm)
- cal1 Offset (dB)
- cal2 Offset (dB)
- cal3 Offset (dB)
- cal4 Offset (dB)
- Actual Input Power (dBm)
- Actual Output Power (dBm)
- Actual Output Power (W)
- Actual Spur/Harmonic (dBm)
- Gain (dB)
- Timestamp
- Mode

Reliability requirements:
- Do not silently fail
- Show meaningful errors if cal files are missing or malformed
- Validate frequency input
- Validate analyzer numeric input
- Validate meter connection
- Prevent UI freezing
- Prevent stale data confusion
- Show last update time for meter readings
- Make sure the app behaves safely if one meter disconnects during use

Development quality requirements:
- Write clean, modular code
- Add docstrings
- Add type hints
- Add at least basic unit tests for:
  - nearest-frequency lookup
  - s2p parsing
  - calculation formulas
- Keep business logic separated from GUI
- Avoid monolithic code

Nice-to-have features if easy:
- Manual desired output power target field, so operator can see error from target
- Visual indicator showing whether corrected output power is at target
- Save / load session
- Dark mode or high-contrast bench-friendly theme
- Keyboard-friendly operation
- Auto-select common test frequencies from a dropdown template
- For this project, common test frequencies can be easy templates for the user to click/select

Frequency template convenience:
Since the user said frequency input should be convenient, provide a quick-select template list of common frequencies such as:
- 6.0
- 6.5
- 7.0
- 7.5
- 8.0
- 8.5
- 9.0
- 9.5
- 10.0
- 10.5
- 11.0
- 11.5
- 12.0
But still allow custom manual entry.

Final delivery expected from you:
- Complete Python source code
- requirements.txt
- README.md
- clear instructions for running
- modular architecture
- fallback simulation/manual mode for meters
- polished UI
- accurate live calculations
- code comments only where useful, not excessive

Very important reminders:
- Ignore vibration test completely
- Use nearest frequency from each .s2p file
- Read S12
- Display offsets rounded to 2 decimals
- Small Signal and Large Signal must be separate tabs
- User manually inputs analyzer reading
- Power meters should be read automatically
- Focus on accuracy, readability, and good operator workflow