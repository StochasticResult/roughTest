"""R&S SMB100A Signal Generator communication via PyVISA."""

from __future__ import annotations

import queue
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot


class _SigGenWorker(QObject):
    """Worker that runs in a dedicated QThread to poll and control the SigGen."""

    state_ready = Signal(float, float, bool)  # freq_ghz, power_dbm, rf_on
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, resource_string: str, poll_interval_s: float = 1.0) -> None:
        super().__init__()
        self._resource = resource_string
        self._poll_interval = poll_interval_s
        self._running = False
        self._instrument = None
        self._cmd_queue: queue.Queue[str] = queue.Queue()

    @Slot()
    def start(self) -> None:
        self._running = True

        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            
            # Print resources for debugging if connected fails
            print(f"Connecting to SigGen: {self._resource}")
            
            self._instrument = rm.open_resource(self._resource)
            self._instrument.timeout = 2000
            
            try:
                idn = self._instrument.query("*IDN?").strip()
                # Try to grab the model name from the IDN string
                parts = idn.split(",")
                model = parts[1] if len(parts) > 1 else "Unknown SigGen"
                self.status_changed.emit(f"Connected: {model}")
                print(f"SigGen successfully connected: {model}")
            except Exception as idn_exc:
                print(f"SigGen IDN query failed (but connected): {idn_exc}")
                self.status_changed.emit("Connected (No IDN)")
                try:
                    self._instrument.clear()
                except:
                    pass
                    
        except Exception as exc:
            self.status_changed.emit(f"Connection failed: {exc}")
            self.error_occurred.emit(str(exc))
            print(f"SigGen connection error: {exc}")
            self._running = False
            return

        while self._running:
            # 1. Process all pending commands
            while not self._cmd_queue.empty():
                cmd = self._cmd_queue.get()
                try:
                    self._instrument.write(cmd)
                except Exception as exc:
                    self.error_occurred.emit(f"Write error: {exc}")

            # 2. Poll the current state
            try:
                freq_raw = self._instrument.query("SOURce:FREQuency:CW?").strip()
                power_raw = self._instrument.query("SOURce:POWer:LEVel:IMMediate:AMPLitude?").strip()
                state_raw = self._instrument.query("OUTPut:STATe?").strip()

                freq_ghz = float(freq_raw) / 1e9
                power_dbm = float(power_raw)
                rf_on = (state_raw == "1")

                self.state_ready.emit(freq_ghz, power_dbm, rf_on)
            except Exception as exc:
                self.error_occurred.emit(f"Poll error: {exc}")
                # Don't fail silently if instrument connection dropped
                if "VI_ERROR" in str(exc):
                    self.status_changed.emit("Disconnected (Error)")

            QThread.msleep(int(self._poll_interval * 1000))

        if self._instrument:
            try:
                self._instrument.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._running = False

    def enqueue_command(self, cmd: str) -> None:
        self._cmd_queue.put(cmd)


class SigGenService(QObject):
    """Service to interact with the R&S SMB100A Signal Generator."""

    state_ready = Signal(float, float, bool)
    status_changed = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[_SigGenWorker] = None

    def connect_device(self, resource_string: str) -> None:
        self.disconnect_device()

        self._thread = QThread()
        self._worker = _SigGenWorker(resource_string)
        self._worker.moveToThread(self._thread)

        self._worker.state_ready.connect(self.state_ready.emit)
        self._worker.status_changed.connect(self.status_changed.emit)
        
        self._thread.started.connect(self._worker.start)
        self._thread.start()

    def disconnect_device(self) -> None:
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(2000)
        self._worker = None
        self._thread = None
        self.status_changed.emit("Disconnected")

    def set_frequency(self, freq_ghz: float) -> None:
        """Set the CW frequency in GHz."""
        if self._worker:
            self._worker.enqueue_command(f"SOURce:FREQuency:CW {freq_ghz} GHz")

    def set_power(self, power_dbm: float) -> None:
        """Set the RF output power level in dBm."""
        if self._worker:
            self._worker.enqueue_command(f"SOURce:POWer:LEVel:IMMediate:AMPLitude {power_dbm}")

    def set_rf_state(self, enabled: bool) -> None:
        """Turn the RF output ON or OFF."""
        if self._worker:
            state_val = "1" if enabled else "0"
            self._worker.enqueue_command(f"OUTPut:STATe {state_val}")
