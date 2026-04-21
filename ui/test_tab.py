"""Measurement tab — instantiated once for Small Signal, once for Large Signal."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt, Slot, QTimer, QSettings
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.result_row import ResultRow
from services.calibration_service import CalOffset, CalibrationService
from services.calculation_service import CalculationService
from services.export_service import ExportService
from services.power_meter_service import PowerMeterService
from services.siggen_service import SigGenService

COMMON_FREQS = [
    "6.0", "6.5", "7.0", "7.5", "8.0", "8.5",
    "9.0", "9.5", "10.0", "10.5", "11.0", "11.5", "12.0",
]

_DEFAULT_SIGGEN_VISA = "USB0::0x0AAD::0x0054::181367::INSTR"

_TABLE_HEADERS = [
    "Freq\nGHz", "In Raw\ndBm", "Out Raw\ndBm", "Analyzer\ndBm",
    "cal1\ndB", "cal2\ndB", "cal3\ndB", "cal4\ndB",
    "Act In\ndBm", "Act Out\ndBm", "Out\nW",
    "Spur/Harm\ndBm", "Gain\ndB", "Time",
]


class TestTab(QWidget):
    """One measurement tab (Small Signal or Large Signal)."""

    def __init__(
        self,
        mode: str,
        cal_service: CalibrationService,
        siggen_service: SigGenService,
        pm_service: PowerMeterService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._cal = cal_service
        self._siggen = siggen_service
        self._pm = pm_service
        self._calc = CalculationService()

        self._is_small = mode == "small_signal"
        self._analyzer_label = "Spur" if self._is_small else "Harmonic"

        self._current_freq_ghz: Optional[float] = None
        self._offsets: dict[str, Optional[CalOffset]] = {}
        self._input_meter_dbm: Optional[float] = None
        self._output_meter_dbm: Optional[float] = None
        self._input_ts = ""
        self._output_ts = ""
        self._session_rows: List[ResultRow] = []

        self._auto_level_timer = QTimer(self)
        self._auto_level_timer.timeout.connect(self._auto_level_step)
        self._auto_level_active = False
        self._auto_level_last_sg_power = None
        self._auto_level_last_act_out = None

        self._build_ui()
        self._connect_signals()
        # self._enable_manual_mode_defaults()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        main_layout.addWidget(scroll)

        content_widget = QWidget()
        scroll.setWidget(content_widget)

        root = QVBoxLayout(content_widget)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(15)

        dashboard = QHBoxLayout()
        dashboard.setSpacing(20)

        # Column 1: Setup & Cal Offsets
        col1 = QVBoxLayout()
        col1.addWidget(self._build_frequency_section())
        col1.addWidget(self._build_siggen_section())
        col1.addWidget(self._build_offset_section())
        col1.addStretch()
        dashboard.addLayout(col1, 40)

        # Column 2: Raw Readings
        col2 = QVBoxLayout()
        col2.addWidget(self._build_readings_section())
        col2.addStretch()
        dashboard.addLayout(col2, 32)

        # Column 3: Live Results
        col3 = QVBoxLayout()
        col3.addWidget(self._build_results_section())
        
        # Big Save Button under results
        self._btn_save = QPushButton("Save Data Point \u2192")
        self._btn_save.setObjectName("save_big")
        col3.addWidget(self._btn_save)
        
        col3.addStretch()
        dashboard.addLayout(col3, 28)

        root.addLayout(dashboard, 0)
        root.addWidget(self._build_session_section(), 1)

    def _build_frequency_section(self) -> QGroupBox:
        grp = QGroupBox("Test Setup")
        lay = QFormLayout(grp)
        lay.setSpacing(10)

        self._freq_combo = QComboBox()
        self._freq_combo.addItem("-- Custom --")
        self._freq_combo.addItems(COMMON_FREQS)
        lay.addRow("Quick Select:", self._freq_combo)
        
        self._freq_input = QDoubleSpinBox()
        self._freq_input.setRange(0.001, 50.0)
        self._freq_input.setDecimals(4)
        self._freq_input.setSingleStep(0.5)
        self._freq_input.setSpecialValueText("")
        lay.addRow("Frequency (GHz):", self._freq_input)

        self._target_input = QDoubleSpinBox()
        self._target_input.setRange(-100, 60)
        self._target_input.setDecimals(2)
        self._target_input.setValue(0.0)
        lay.addRow("Target Out (dBm):", self._target_input)
        
        self._target_error_label = QLabel("---")
        self._target_error_label.setObjectName("offset_val")
        
        self._btn_auto_level = QPushButton("Auto Level")
        self._btn_auto_level.setCheckable(True)
        
        row_lay = QHBoxLayout()
        row_lay.addWidget(self._target_error_label)
        row_lay.addStretch()
        row_lay.addWidget(self._btn_auto_level)
        
        lay.addRow("Target Error:", row_lay)

        return grp

    def _build_siggen_section(self) -> QGroupBox:
        grp = QGroupBox("Signal Generator")
        root = QVBoxLayout(grp)
        root.setSpacing(10)
        root.setContentsMargins(12, 16, 12, 12)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        st_lbl = QLabel("Status:")
        st_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        status_row.addWidget(st_lbl)
        self._sg_status = QLabel("Disconnected")
        self._sg_status.setObjectName("status_warn")
        self._sg_status.setWordWrap(True)
        self._sg_status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._sg_status.setMinimumWidth(120)
        status_row.addWidget(self._sg_status, 1)
        root.addLayout(status_row)

        visa_cap = QLabel("VISA / resource")
        visa_cap.setObjectName("metric_title")
        root.addWidget(visa_cap)
        self._sg_resource_edit = QLineEdit()
        self._sg_resource_edit.setPlaceholderText("USB0::...::INSTR")
        self._sg_resource_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._sg_resource_edit.setMinimumHeight(28)
        root.addWidget(self._sg_resource_edit)

        conn_row = QHBoxLayout()
        conn_row.setSpacing(8)
        self._btn_sg_connect = QPushButton("Connect")
        self._btn_sg_disconnect = QPushButton("Disconnect")
        for b in (self._btn_sg_connect, self._btn_sg_disconnect):
            b.setMinimumWidth(96)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        conn_row.addWidget(self._btn_sg_connect)
        conn_row.addWidget(self._btn_sg_disconnect)
        conn_row.addStretch(1)
        root.addLayout(conn_row)

        self._sg_sync_check = QCheckBox("Auto-push test frequency to SigGen (when changed)")
        self._sg_sync_check.setChecked(False)
        self._sg_sync_check.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        root.addWidget(self._sg_sync_check)

        power_row = QHBoxLayout()
        power_row.setSpacing(8)
        power_row.addWidget(QLabel("Power (dBm):"))
        self._sg_power_input = QDoubleSpinBox()
        self._sg_power_input.setRange(-140, 30)
        self._sg_power_input.setDecimals(2)
        self._sg_power_input.setSingleStep(1.0)
        self._sg_power_input.setKeyboardTracking(False)  # Important to avoid fighting when typing
        self._sg_power_input.setFixedWidth(118)
        self._sg_power_input.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        power_row.addWidget(self._sg_power_input)
        self._btn_sg_set_power = QPushButton("Set Power")
        self._btn_sg_set_power.setMinimumWidth(96)
        self._btn_sg_set_power.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        power_row.addWidget(self._btn_sg_set_power)
        power_row.addStretch(1)
        root.addLayout(power_row)

        rf_row = QHBoxLayout()
        rf_row.setSpacing(8)
        rf_row.addWidget(QLabel("RF output:"))
        self._btn_sg_rf = QPushButton("RF OFF")
        self._btn_sg_rf.setCheckable(True)
        self._btn_sg_rf.setObjectName("accent")
        self._btn_sg_rf.setMinimumWidth(120)
        self._btn_sg_rf.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        rf_row.addWidget(self._btn_sg_rf)
        rf_row.addStretch(1)
        root.addLayout(rf_row)

        self._btn_sg_release_local = QPushButton("Release panel (Local)")
        self._btn_sg_release_local.setToolTip("可选：SCPI 将仪器切到前面板 Local。")
        self._btn_sg_release_local.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._btn_sg_release_local.setMinimumHeight(30)
        root.addWidget(self._btn_sg_release_local)

        return grp

    def _build_offset_section(self) -> QGroupBox:
        grp = QGroupBox("Calibration Offsets")
        lay = QGridLayout(grp)
        lay.setSpacing(10)
        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)

        self._offset_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for index, key in enumerate(["cal1", "cal2", "cal3", "cal4"]):
            row = index // 2
            col = index % 2
            card = QFrame()
            card.setObjectName("panel_card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(2)

            title = QLabel(key.upper())
            title.setObjectName("section_title")
            card_layout.addWidget(title)

            desc = QLabel(CalibrationService.CAL_LABELS[key])
            desc.setWordWrap(True)
            card_layout.addWidget(desc)

            freq_lbl = QLabel("---")
            freq_lbl.setWordWrap(True)
            card_layout.addWidget(freq_lbl)

            val_lbl = QLabel("---")
            val_lbl.setObjectName("offset_val")
            card_layout.addWidget(val_lbl)

            self._offset_labels[key] = (freq_lbl, val_lbl)
            lay.addWidget(card, row, col)

        return grp

    def _build_readings_section(self) -> QGroupBox:
        grp = QGroupBox("Raw Readings (dBm)")
        lay = QVBoxLayout(grp)
        lay.setSpacing(12)

        # Input Meter
        input_card = QFrame()
        input_card.setObjectName("panel_card")
        in_lay = QFormLayout(input_card)
        in_lay.setContentsMargins(10, 10, 10, 10)
        
        in_title = QLabel("Input Meter")
        in_title.setObjectName("section_title")
        self._input_manual_check = QCheckBox("Manual Entry")
        
        in_header = QHBoxLayout()
        in_header.addWidget(in_title)
        in_header.addStretch()
        in_header.addWidget(self._input_manual_check)
        
        in_lay.addRow(in_header)
        
        self._input_status = QLabel("Status")
        self._input_status.setObjectName("status_warn")
        in_lay.addRow("Status:", self._input_status)
        
        self._input_raw_label = QLabel("---")
        self._input_raw_label.setObjectName("reading_raw")
        in_lay.addRow("Reading:", self._input_raw_label)
        
        self._input_manual = QDoubleSpinBox()
        self._input_manual.setRange(-200, 100)
        self._input_manual.setDecimals(3)
        in_lay.addRow("Manual:", self._input_manual)
        
        self._input_ts_label = QLabel("Last Update: ---")
        in_lay.addRow("", self._input_ts_label)
        lay.addWidget(input_card)

        # Output Meter
        output_card = QFrame()
        output_card.setObjectName("panel_card")
        out_lay = QFormLayout(output_card)
        out_lay.setContentsMargins(10, 10, 10, 10)
        
        out_title = QLabel("Output Meter")
        out_title.setObjectName("section_title")
        self._output_manual_check = QCheckBox("Manual Entry")
        
        out_header = QHBoxLayout()
        out_header.addWidget(out_title)
        out_header.addStretch()
        out_header.addWidget(self._output_manual_check)
        
        out_lay.addRow(out_header)
        
        self._output_status = QLabel("Status")
        self._output_status.setObjectName("status_warn")
        out_lay.addRow("Status:", self._output_status)
        
        self._output_raw_label = QLabel("---")
        self._output_raw_label.setObjectName("reading_raw")
        out_lay.addRow("Reading:", self._output_raw_label)
        
        self._output_manual = QDoubleSpinBox()
        self._output_manual.setRange(-200, 100)
        self._output_manual.setDecimals(3)
        out_lay.addRow("Manual:", self._output_manual)
        
        self._output_ts_label = QLabel("Last Update: ---")
        out_lay.addRow("", self._output_ts_label)
        lay.addWidget(output_card)

        # Analyzer
        analyzer_card = QFrame()
        analyzer_card.setObjectName("panel_card")
        ana_lay = QFormLayout(analyzer_card)
        ana_lay.setContentsMargins(10, 10, 10, 10)
        
        ana_title = QLabel(f"{self._analyzer_label} Analyzer")
        ana_title.setObjectName("section_title")
        ana_lay.addRow(ana_title)
        
        self._analyzer_input = QDoubleSpinBox()
        self._analyzer_input.setRange(-200, 100)
        self._analyzer_input.setDecimals(2)
        self._analyzer_input.setSpecialValueText("")
        self._analyzer_input.setValue(-200)
        ana_lay.addRow("Manual:", self._analyzer_input)
        lay.addWidget(analyzer_card)
        
        return grp

    def _build_results_section(self) -> QGroupBox:
        grp = QGroupBox("Live Results")
        lay = QGridLayout(grp)
        lay.setSpacing(10)
        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)

        self._res_input = self._add_metric_card(lay, 0, 0, "Actual Input")
        self._res_output = self._add_metric_card(lay, 0, 1, "Actual Output")
        self._res_gain = self._add_metric_card(lay, 1, 0, "Gain")
        self._res_output_w = self._add_metric_card(lay, 1, 1, "Output Power (W)")
        self._res_analyzer = self._add_metric_card(
            lay, 2, 0, f"Actual {self._analyzer_label}"
        )
        self._res_dbc = self._add_metric_card(lay, 2, 1, f"{self._analyzer_label} (dBc)")
        return grp

    def _add_metric_card(
        self,
        layout: QGridLayout,
        row: int,
        col: int,
        title_text: str,
    ) -> QLabel:
        card = QFrame()
        card.setObjectName("metric_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(4)

        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setObjectName("metric_title")
        card_layout.addWidget(title)

        value = QLabel("---")
        value.setObjectName("reading_big")
        card_layout.addWidget(value)

        layout.addWidget(card, row, col)
        return value

    def _build_session_section(self) -> QGroupBox:
        grp = QGroupBox("Session Records")
        lay = QVBoxLayout(grp)
        lay.setSpacing(8)

        btn_row = QHBoxLayout()
        self._btn_copy_row = QPushButton("Copy Current")
        btn_row.addWidget(self._btn_copy_row)

        self._btn_copy_all = QPushButton("Copy All")
        btn_row.addWidget(self._btn_copy_all)
        
        self._btn_export = QPushButton("Export CSV")
        btn_row.addWidget(self._btn_export)

        self._btn_delete = QPushButton("Delete Selected")
        btn_row.addWidget(self._btn_delete)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._table = QTableWidget(0, len(_TABLE_HEADERS))
        self._table.setHorizontalHeaderLabels(_TABLE_HEADERS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(260)
        for col, width in enumerate(
            [92, 100, 100, 100, 74, 74, 74, 74, 96, 96, 90, 104, 80, 140]
        ):
            self._table.setColumnWidth(col, width)
        lay.addWidget(self._table)

        return grp

    def _connect_signals(self) -> None:
        self._freq_combo.currentIndexChanged.connect(self._on_combo_changed)
        self._freq_input.valueChanged.connect(self._on_freq_changed)
        self._analyzer_input.valueChanged.connect(self._recompute)
        self._target_input.valueChanged.connect(self._recompute)
        self._cal.calibration_changed.connect(self._on_freq_changed)

        self._input_manual_check.toggled.connect(self._on_input_manual_toggle)
        self._output_manual_check.toggled.connect(self._on_output_manual_toggle)
        self._input_manual.valueChanged.connect(self._on_manual_input_value)
        self._output_manual.valueChanged.connect(self._on_manual_output_value)

        self._siggen.status_changed.connect(self._on_sg_status)
        self._siggen.state_ready.connect(self._on_sg_state)
        
        self._pm.input_reading.connect(self.on_input_reading)
        self._pm.output_reading.connect(self.on_output_reading)
        self._pm.input_status.connect(self.on_input_status)
        self._pm.output_status.connect(self.on_output_status)

        self._btn_sg_set_power.clicked.connect(self._on_sg_set_power)
        # Make pressing Enter in the power input behave identically to clicking "Set Power"
        self._sg_power_input.lineEdit().returnPressed.connect(self._btn_sg_set_power.animateClick)
        
        self._btn_sg_rf.toggled.connect(self._on_sg_rf_toggled)
        self._btn_sg_release_local.clicked.connect(self._siggen.release_to_local_panel)
        self._btn_sg_connect.clicked.connect(self._on_sg_connect)
        self._btn_sg_disconnect.clicked.connect(self._on_sg_disconnect)
        self._btn_auto_level.toggled.connect(self._on_auto_level_toggled)

        self._btn_save.clicked.connect(self._save_row)
        self._btn_copy_row.clicked.connect(self._copy_current_row)
        self._btn_copy_all.clicked.connect(self._copy_all_rows)
        self._btn_export.clicked.connect(self._export_csv)
        self._btn_delete.clicked.connect(self._delete_selected)

    def _enable_manual_mode_defaults(self) -> None:
        self._input_manual_check.blockSignals(True)
        self._output_manual_check.blockSignals(True)
        self._input_manual_check.setChecked(True)
        self._output_manual_check.setChecked(True)
        self._input_manual_check.blockSignals(False)
        self._output_manual_check.blockSignals(False)

        self._input_manual.setEnabled(True)
        self._output_manual.setEnabled(True)
        self._input_status.setText("Manual entry mode")
        self._output_status.setText("Manual entry mode")
        self._input_status.setObjectName("status_warn")
        self._output_status.setObjectName("status_warn")
        self._input_status.style().polish(self._input_status)
        self._output_status.style().polish(self._output_status)

    @Slot(int)
    def _on_combo_changed(self, index: int) -> None:
        if index <= 0:
            return
        try:
            val = float(self._freq_combo.currentText())
            self._freq_input.blockSignals(True)
            self._freq_input.setValue(val)
            self._freq_input.blockSignals(False)
            self._on_freq_changed()
        except ValueError:
            pass

    @Slot()
    def _on_freq_changed(self) -> None:
        val = self._freq_input.value()
        
        # Sync to SigGen if enabled
        if hasattr(self, "_sg_sync_check") and self._sg_sync_check.isChecked() and val >= 0.001:
            self._siggen.set_frequency(val)

        if val < 0.001:
            self._current_freq_ghz = None
            self._clear_offsets()
            self._recompute()
            return
        self._current_freq_ghz = val
        self._update_offsets()
        self._recompute()

    def _on_input_manual_toggle(self, checked: bool) -> None:
        self._input_manual.setEnabled(checked)
        if checked:
            self._input_meter_dbm = self._input_manual.value()
        self._recompute()

    def _on_output_manual_toggle(self, checked: bool) -> None:
        self._output_manual.setEnabled(checked)
        if checked:
            self._output_meter_dbm = self._output_manual.value()
        self._recompute()

    def _on_manual_input_value(self) -> None:
        if self._input_manual_check.isChecked():
            self._input_meter_dbm = self._input_manual.value()
            self._input_ts = datetime.now().strftime("%H:%M:%S")
            self._input_raw_label.setText(f"{self._input_meter_dbm:+.3f} dBm")
            self._input_ts_label.setText(f"Last Update: {self._input_ts}")
            self._recompute()

    def _on_manual_output_value(self) -> None:
        if self._output_manual_check.isChecked():
            self._output_meter_dbm = self._output_manual.value()
            self._output_ts = datetime.now().strftime("%H:%M:%S")
            self._output_raw_label.setText(f"{self._output_meter_dbm:+.3f} dBm")
            self._output_ts_label.setText(f"Last Update: {self._output_ts}")
            self._recompute()

    def siggen_resource_string(self) -> str:
        return self._sg_resource_edit.text().strip()

    def set_siggen_resource_string(self, visa: str) -> None:
        self._sg_resource_edit.setText(visa)

    @Slot()
    def _on_sg_connect(self) -> None:
        text = self.siggen_resource_string()
        if not text:
            QMessageBox.warning(
                self,
                "Signal Generator",
                "Please enter a VISA resource string (e.g. USB0::...::INSTR).",
            )
            return
        self._siggen.connect_device(text)

    @Slot()
    def _on_sg_disconnect(self) -> None:
        self._siggen.disconnect_device()

    @Slot(str)
    def _on_sg_status(self, status: str) -> None:
        self._sg_status.setText(status)
        if "Connected" in status:
            self._sg_status.setObjectName("status_ok")
        elif "failed" in status.lower() or "error" in status.lower():
            self._sg_status.setObjectName("status_err")
        else:
            self._sg_status.setObjectName("status_warn")
        self._sg_status.style().polish(self._sg_status)

    @Slot(float, float, bool)
    def _on_sg_state(self, freq_ghz: float, power_dbm: float, rf_on: bool) -> None:
        state_text = "ON" if rf_on else "OFF"
        self._btn_sg_rf.blockSignals(True)
        self._btn_sg_rf.setText(f"RF {state_text}")
        self._btn_sg_rf.setChecked(rf_on)
        self._btn_sg_rf.blockSignals(False)
        
        # Only update the spinbox if it's not currently focused by the user
        if not self._sg_power_input.hasFocus():
            self._sg_power_input.blockSignals(True)
            self._sg_power_input.setValue(power_dbm)
            self._sg_power_input.blockSignals(False)
            
        if "Connected" in self._sg_status.text():
            self._sg_status.setText(f"Connected | {freq_ghz:.4f} GHz | {power_dbm:.2f} dBm")

    @Slot()
    def _on_sg_set_power(self) -> None:
        val = self._sg_power_input.value()
        self._siggen.set_power(val)

    @Slot(bool)
    def _on_sg_rf_toggled(self, checked: bool) -> None:
        self._siggen.set_rf_state(checked)

    @Slot(bool)
    def _on_auto_level_toggled(self, checked: bool) -> None:
        if checked:
            self._auto_level_active = True
            self._auto_level_last_sg_power = None
            self._auto_level_last_act_out = None
            self._btn_auto_level.setText("Stop Auto Level")
            self._auto_level_step() # Trigger first step immediately
            self._auto_level_timer.start(1000) # Wait 1.0s between steps for faster convergence
        else:
            self._auto_level_active = False
            self._btn_auto_level.setText("Auto Level")
            self._auto_level_timer.stop()

    @Slot()
    def _auto_level_step(self) -> None:
        if not self._auto_level_active:
            return
            
        row = self._build_current_row()
        if not row or row.actual_output_power_dbm is None:
            self._btn_auto_level.setChecked(False)
            QMessageBox.warning(self, "Auto Level", "Cannot read actual output power. Auto level stopped.")
            return
            
        act_out = row.actual_output_power_dbm
        target = self._target_input.value()
        error = target - act_out
        
        if abs(error) <= 0.04:
            self._btn_auto_level.setChecked(False)
            return
            
        current_sg_power = self._sg_power_input.value()
        step = error
        
        if self._auto_level_last_sg_power is not None and self._auto_level_last_act_out is not None:
            delta_sg = current_sg_power - self._auto_level_last_sg_power
            delta_out = act_out - self._auto_level_last_act_out
            
            # 只有在 12 GHz 时，并且单次步长足够大（> 0.5 dBm）才去检测饱和，防止仪器读数跳动产生误判
            if self._current_freq_ghz is not None and self._current_freq_ghz >= 11.9:
                if delta_sg > 0.5: 
                    if (delta_out / delta_sg) < 0.15:
                        self._sg_power_input.setValue(self._auto_level_last_sg_power)
                        self._siggen.set_power(self._auto_level_last_sg_power)
                        self._btn_auto_level.setChecked(False)
                        QMessageBox.warning(self, "Auto Level", "Amplifier saturated at high frequency! Reverted to previous state.")
                        return

            # 聪明步长预测 (Secant Method / 割线法)
            if abs(delta_sg) >= 0.1:
                slope = delta_out / delta_sg
                # 只有当 slope 在放大器的合理物理范围内（比如 0.2 到 2.0）才信任它
                # 如果目前处于增益压缩区（比如 slope=0.5），直接用 error 可能会达不到 target
                # 使用 error / slope 会自动将输入步长放大（变成2倍），从而更大概率一步到位
                if 0.2 <= slope <= 2.0:
                    step = error / slope
        
        # 限制最大跨度，允许最大 5 dB 的跳变以实现极速逼近
        if step > 5.0:
            step = 5.0
        elif step < -5.0:
            step = -5.0
            
        next_power = current_sg_power + step
        next_power = max(-140.0, min(30.0, next_power))
        
        # Round to 2 decimal places to avoid floating point weirdness
        next_power = round(next_power, 2)
        
        self._auto_level_last_sg_power = current_sg_power
        self._auto_level_last_act_out = act_out
        
        self._sg_power_input.setValue(next_power)
        self._siggen.set_power(next_power)

    @Slot(float, str)
    def on_input_reading(self, value: float, ts: str) -> None:
        if self._input_manual_check.isChecked():
            return
        self._input_meter_dbm = value
        self._input_ts = ts
        self._input_raw_label.setText(f"{value:+.3f} dBm")
        self._input_ts_label.setText(f"Last Update: {ts}")
        self._recompute()

    @Slot(float, str)
    def on_output_reading(self, value: float, ts: str) -> None:
        if self._output_manual_check.isChecked():
            return
        self._output_meter_dbm = value
        self._output_ts = ts
        self._output_raw_label.setText(f"{value:+.3f} dBm")
        self._output_ts_label.setText(f"Last Update: {ts}")
        self._recompute()

    @Slot(str)
    def on_input_status(self, status: str) -> None:
        self._input_status.setText(status)
        self._input_status.setObjectName(self._status_object_name(status))
        self._input_status.style().polish(self._input_status)

    @Slot(str)
    def on_output_status(self, status: str) -> None:
        self._output_status.setText(status)
        self._output_status.setObjectName(self._status_object_name(status))
        self._output_status.style().polish(self._output_status)

    def _status_object_name(self, status: str) -> str:
        if any(key in status for key in ("Connected", "Simulation")):
            return "status_ok"
        if any(
            key in status
            for key in ("Disconnected", "ready", "Waiting", "not found", "not available")
        ):
            return "status_warn"
        return "status_err"

    def _update_offsets(self) -> None:
        if self._current_freq_ghz is None:
            self._clear_offsets()
            return
        self._offsets = self._cal.get_all_offsets(self._current_freq_ghz)
        for key, (freq_lbl, val_lbl) in self._offset_labels.items():
            off = self._offsets.get(key)
            if off is None:
                freq_lbl.setText("Not loaded")
                val_lbl.setText("---")
            else:
                freq_lbl.setText(f"Match: {off.matched_freq_ghz:.4f} GHz")
                val_lbl.setText(f"Offset: {off.s12_db:+.2f} dB")

    def _clear_offsets(self) -> None:
        self._offsets = {}
        for freq_lbl, val_lbl in self._offset_labels.values():
            freq_lbl.setText("---")
            val_lbl.setText("---")

    def restore_settings(self, settings: QSettings, prefix: str) -> None:
        freq_str = settings.value(f"{prefix}_freq")
        if freq_str is not None:
            try:
                freq = float(freq_str)
                if freq >= 0.001:
                    self._freq_input.blockSignals(True)
                    self._freq_input.setValue(freq)
                    self._freq_input.blockSignals(False)
                    self._current_freq_ghz = freq
                    self._update_offsets()
                    self._recompute()
            except (ValueError, TypeError):
                pass

        target_str = settings.value(f"{prefix}_target")
        if target_str is not None:
            try:
                target = float(target_str)
                self._target_input.setValue(target)
            except (ValueError, TypeError):
                pass

        sync_str = settings.value(f"{prefix}_sync")
        if sync_str is not None:
            sync = sync_str == "true" or sync_str is True
            self._sg_sync_check.setChecked(sync)

        visa = settings.value("siggen_visa_resource", _DEFAULT_SIGGEN_VISA)
        self._sg_resource_edit.setText(str(visa))

    def save_settings(self, settings: QSettings, prefix: str) -> None:
        settings.setValue(f"{prefix}_freq", self._freq_input.value())
        settings.setValue(f"{prefix}_target", self._target_input.value())
        settings.setValue(f"{prefix}_sync", self._sg_sync_check.isChecked())
        # 两个标签页各有一份输入框；后保存的覆盖前者，便于只在 Large 页改地址也能落盘。
        settings.setValue("siggen_visa_resource", self._sg_resource_edit.text().strip())

    def _recompute(self) -> None:
        c = self._calc
        o = self._offsets

        cal1 = o.get("cal1")
        cal2 = o.get("cal2")
        cal3 = o.get("cal3")
        cal4 = o.get("cal4")

        act_in: Optional[float] = None
        if self._input_meter_dbm is not None and cal1 is not None and cal2 is not None:
            act_in = c.actual_input_power(self._input_meter_dbm, cal1.s12_db, cal2.s12_db)
        self._res_input.setText(c.format_dbm(act_in))

        act_out: Optional[float] = None
        if self._output_meter_dbm is not None and cal3 is not None:
            act_out = c.actual_output_power(self._output_meter_dbm, cal3.s12_db)
        self._res_output.setText(c.format_dbm(act_out))

        out_w: Optional[float] = None
        if act_out is not None:
            out_w = c.dbm_to_watt(act_out)
        self._res_output_w.setText(c.format_watt(out_w))

        gain: Optional[float] = None
        if act_in is not None and act_out is not None:
            gain = c.gain(act_out, act_in)
        self._res_gain.setText(c.format_db(gain))

        analyzer_raw = self._get_analyzer_value()
        act_ana: Optional[float] = None
        dbc_val: Optional[float] = None
        if analyzer_raw is not None and cal4 is not None:
            act_ana = c.actual_spur_or_harmonic(analyzer_raw, cal4.s12_db)
            if act_out is not None:
                dbc_val = c.relative_dbc(act_ana, act_out)
        self._res_analyzer.setText(c.format_dbm(act_ana))
        self._res_dbc.setText(c.format_db(dbc_val))

        target = self._target_input.value()
        if act_out is not None:
            # Keep display sign consistent with auto-level control logic:
            # positive => still below target and needs to increase.
            err = target - act_out
            self._target_error_label.setText(f"{err:+.2f} dB")
            color = "#a6e3a1" if abs(err) < 0.5 else "#f38ba8"
            self._target_error_label.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 14px;"
            )
        else:
            self._target_error_label.setText("---")

    def _get_analyzer_value(self) -> Optional[float]:
        val = self._analyzer_input.value()
        if val <= -199.9:
            return None
        return val

    def _build_current_row(self) -> Optional[ResultRow]:
        if self._current_freq_ghz is None:
            return None

        cal1 = self._offsets.get("cal1")
        cal2 = self._offsets.get("cal2")
        cal3 = self._offsets.get("cal3")
        cal4 = self._offsets.get("cal4")
        c = self._calc
        analyzer_raw = self._get_analyzer_value()

        act_in = None
        if self._input_meter_dbm is not None and cal1 and cal2:
            act_in = c.actual_input_power(self._input_meter_dbm, cal1.s12_db, cal2.s12_db)

        act_out = None
        if self._output_meter_dbm is not None and cal3:
            act_out = c.actual_output_power(self._output_meter_dbm, cal3.s12_db)

        act_ana = None
        if analyzer_raw is not None and cal4:
            act_ana = c.actual_spur_or_harmonic(analyzer_raw, cal4.s12_db)

        gain = None
        if act_in is not None and act_out is not None:
            gain = c.gain(act_out, act_in)

        out_w = c.dbm_to_watt(act_out) if act_out is not None else None

        return ResultRow(
            mode=self._mode,
            frequency_ghz=self._current_freq_ghz,
            input_meter_raw_dbm=self._input_meter_dbm,
            output_meter_raw_dbm=self._output_meter_dbm,
            analyzer_raw_dbm=analyzer_raw,
            cal1_matched_freq_ghz=cal1.matched_freq_ghz if cal1 else None,
            cal1_s12_db=cal1.s12_db if cal1 else None,
            cal2_matched_freq_ghz=cal2.matched_freq_ghz if cal2 else None,
            cal2_s12_db=cal2.s12_db if cal2 else None,
            cal3_matched_freq_ghz=cal3.matched_freq_ghz if cal3 else None,
            cal3_s12_db=cal3.s12_db if cal3 else None,
            cal4_matched_freq_ghz=cal4.matched_freq_ghz if cal4 else None,
            cal4_s12_db=cal4.s12_db if cal4 else None,
            actual_input_power_dbm=act_in,
            actual_output_power_dbm=act_out,
            actual_spur_or_harmonic_dbm=act_ana,
            gain_db=gain,
            output_power_w=out_w,
        )

    def _save_row(self) -> None:
        row = self._build_current_row()
        if row is None:
            QMessageBox.warning(
                self,
                "Missing Frequency",
                "Please set the test frequency first.",
            )
            return
        self._session_rows.append(row)
        self._refresh_table()

    def _copy_current_row(self) -> None:
        row = self._build_current_row()
        if row is None:
            return
        ExportService.copy_row(row)

    def _copy_all_rows(self) -> None:
        if not self._session_rows:
            return
        ExportService.copy_all_rows(self._session_rows)

    def _export_csv(self) -> None:
        if not self._session_rows:
            QMessageBox.information(
                self,
                "No Data",
                "There are no saved rows in this session.",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            ExportService.export_csv(self._session_rows, path)
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")

    def _delete_selected(self) -> None:
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self._session_rows):
                self._session_rows.pop(row)
        self._refresh_table()

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._session_rows))
        for i, row in enumerate(self._session_rows):
            vals = row.to_export_list()
            display = [
                vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6],
                vals[7], vals[8], vals[9], vals[10], vals[11], vals[12], vals[13],
            ]
            for col, text in enumerate(display):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(i, col, item)
