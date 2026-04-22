"""Main application window with calibration panel and Small/Large Signal tabs."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.calibration_service import CalibrationService
from services.power_meter_service import PowerMeterService
from services.siggen_service import SigGenService

from .calibration_panel import CalibrationPanel
from .test_tab import TestTab
from .styles import LIGHT_STYLESHEET


class MainWindow(QMainWindow):
    """Top-level window for the RF Lambda Test Assistant."""

    def __init__(
        self,
        simulate_meters: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("RF Lambda Test Assistant - RFLUPA06G12GD")
        self.setMinimumSize(1480, 920)
        self.setStyleSheet(LIGHT_STYLESHEET)

        self._cal_service = CalibrationService(self)
        self._siggen_service = SigGenService(self, simulate=simulate_meters)
        
        # Initialize the Power Meter Service
        self._pm_service = PowerMeterService(simulate=simulate_meters, parent=self)

        self._build_ui()
        
        self._restore_settings()
        
        # Start looking for meters in the background
        # Move this after UI is built so that TestTabs can receive the initial status signals!
        self._pm_service.connect_meters()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(15)

        # Left Sidebar for Calibration
        self._sidebar = QFrame()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(400)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(20)

        app_title = QLabel("RF Lambda\nTest Assistant")
        app_title.setObjectName("app_title")
        sidebar_layout.addWidget(app_title)

        self._cal_panel = CalibrationPanel(self._cal_service)
        sidebar_layout.addWidget(self._cal_panel)
        
        self._cal_summary = QLabel("")
        self._cal_summary.setObjectName("cal_summary")
        sidebar_layout.addWidget(self._cal_summary)
        
        sidebar_layout.addStretch()
        root.addWidget(self._sidebar)

        # Main Workspace Area
        workspace = QVBoxLayout()
        
        # Top bar with toggle button
        top_bar = QHBoxLayout()
        self._btn_toggle_sidebar = QPushButton("◀ Hide Calibration")
        self._btn_toggle_sidebar.setFixedWidth(160)
        self._btn_toggle_sidebar.clicked.connect(self._toggle_sidebar)
        top_bar.addWidget(self._btn_toggle_sidebar)
        top_bar.addStretch()
        workspace.addLayout(top_bar)
        
        self._tabs = QTabWidget()
        self._small_tab = TestTab("small_signal", self._cal_service, self._siggen_service, self._pm_service)
        self._large_tab = TestTab("large_signal", self._cal_service, self._siggen_service, self._pm_service)
        self._tabs.addTab(self._small_tab, "Small Signal")
        self._tabs.addTab(self._large_tab, "Large Signal")
        self._siggen_service.resource_discovered.connect(self._small_tab.set_siggen_resource_string)
        self._siggen_service.resource_discovered.connect(self._large_tab.set_siggen_resource_string)
        workspace.addWidget(self._tabs, 1)
        root.addLayout(workspace, 1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(
            "Ready | Manual input mode is enabled for both power meters."
        )
        self._cal_service.calibration_changed.connect(self._update_calibration_summary)
        self._update_calibration_summary()

    def _update_calibration_summary(self) -> None:
        loaded = sum(
            1 for key in self._cal_service.CAL_LABELS if self._cal_service.is_loaded(key)
        )
        total = len(self._cal_service.CAL_LABELS)
        self._cal_summary.setText(f"{loaded}/{total} calibration files loaded.")

    def _toggle_sidebar(self) -> None:
        if self._sidebar.isVisible():
            self._sidebar.hide()
            self._btn_toggle_sidebar.setText("▶ Show Calibration")
        else:
            self._sidebar.show()
            self._btn_toggle_sidebar.setText("◀ Hide Calibration")

    def _restore_settings(self) -> None:
        settings = QSettings("RFLambda", "TestAssistant")
        
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
            
        for key in ["cal1", "cal2", "cal3", "cal4"]:
            path = settings.value(f"cal_{key}")
            if path:
                self._cal_panel.load_cal_file(key, str(path))
                
        self._small_tab.restore_settings(settings, "small")
        self._large_tab.restore_settings(settings, "large")

        visa = self._small_tab.siggen_resource_string()
        if not visa:
            visa = "USB0::0x0AAD::0x0054::181367::INSTR"
        self._siggen_service.connect_device(visa)

    def closeEvent(self, event) -> None:
        settings = QSettings("RFLambda", "TestAssistant")
        settings.setValue("geometry", self.saveGeometry())
        
        for key in ["cal1", "cal2", "cal3", "cal4"]:
            path = self._cal_service.get_loaded_path(key)
            if path:
                settings.setValue(f"cal_{key}", path)
                
        self._small_tab.save_settings(settings, "small")
        self._large_tab.save_settings(settings, "large")

        # Ensure meter polling threads are fully released on window close.
        self._pm_service.stop()
        self._siggen_service.disconnect_device()

        event.accept()
