"""R&S SMB100A Signal Generator communication via PyVISA."""

from __future__ import annotations

import queue
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

_RLST_LOCAL = "SYSTem:COMMunicate:GPIB:RLSTate LOCal"


def _discover_smb100a_usb(rm) -> Optional[str]:
    """在 VISA 枚举的 USB 资源里找 Rohde&Schwarz SMB100A（解决保存的旧序列号/插口变化导致连不上）。"""
    try:
        resources = rm.list_resources()
    except Exception:
        return None
    for res in resources:
        if "USB" not in res.upper():
            continue
        inst = None
        try:
            inst = rm.open_resource(res)
            inst.timeout = 3000
            idn = inst.query("*IDN?").strip()
            if "SMB100A" in idn.upper():
                return res
        except Exception:
            pass
        finally:
            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    pass
    return None


def _is_io_link_lost(exc: BaseException) -> bool:
    """USB 拔除、会话失效等：关闭 VISA 并结束轮询。"""
    s = str(exc).upper()
    if "VI_ERROR" in s:
        return True
    if "INSTRUMENT CLOSED" in s or ("RESOURCE" in s and "INVALID" in s):
        return True
    return False


class _SigGenWorker(QObject):
    """Worker that runs in a dedicated QThread to poll and control the SigGen."""

    state_ready = Signal(float, float, bool)  # freq_ghz, power_dbm, rf_on
    status_changed = Signal(str)
    error_occurred = Signal(str)
    resource_resolved = Signal(str)  # 自动发现地址时发出，供界面更新输入框

    def __init__(self, resource_string: str, poll_interval_s: float = 1.0) -> None:
        super().__init__()
        self._resource = resource_string
        self._poll_interval = poll_interval_s
        self._running = False
        self._instrument = None
        self._cmd_queue: queue.Queue[str] = queue.Queue()

    def _close_session(self, release_local: bool) -> None:
        inst = self._instrument
        self._instrument = None
        if inst is None:
            return
        if release_local:
            try:
                inst.write(_RLST_LOCAL)
            except Exception:
                pass
        try:
            inst.close()
        except Exception:
            pass

    @Slot()
    def start(self) -> None:
        self._running = True

        try:
            import pyvisa
            rm = pyvisa.ResourceManager()

            want = (self._resource or "").strip()
            print(f"Connecting to SigGen: {want or '(auto-discover SMB100A USB)'}")

            self._instrument = None
            last_err: Optional[BaseException] = None

            if want:
                try:
                    self._instrument = rm.open_resource(want)
                except Exception as exc:
                    last_err = exc
                    print(f"SigGen open failed for {want!r}: {exc}")

            if self._instrument is None:
                discovered = _discover_smb100a_usb(rm)
                if discovered:
                    try:
                        self._instrument = rm.open_resource(discovered)
                        if discovered != want:
                            self._resource = discovered
                            self.resource_resolved.emit(discovered)
                        last_err = None
                    except Exception as exc:
                        last_err = exc
                        print(f"SigGen open failed for discovered {discovered!r}: {exc}")

            if self._instrument is None:
                msg = (
                    f"Connection failed: {last_err}"
                    if last_err
                    else "No SMB100A found on USB. Check cable, driver (NI-VISA), and that no other app holds the device."
                )
                self.status_changed.emit(msg)
                self.error_occurred.emit(str(last_err) if last_err else msg)
                print(f"SigGen connection error: {msg}")
                self._running = False
                return

            self._instrument.timeout = 2000

            try:
                idn = self._instrument.query("*IDN?").strip()
                parts = idn.split(",")
                model = parts[1] if len(parts) > 1 else "Unknown SigGen"
                self.status_changed.emit(f"Connected: {model}")
                print(f"SigGen successfully connected: {model}")
            except Exception as idn_exc:
                print(f"SigGen IDN query failed (but connected): {idn_exc}")
                self.status_changed.emit("Connected (No IDN)")
                try:
                    self._instrument.clear()
                except Exception:
                    pass

        except Exception as exc:
            self.status_changed.emit(f"Connection failed: {exc}")
            self.error_occurred.emit(str(exc))
            print(f"SigGen connection error: {exc}")
            self._running = False
            return

        while self._running:
            try:
                link_dead = False
                while not self._cmd_queue.empty():
                    cmd = self._cmd_queue.get()
                    try:
                        self._instrument.write(cmd)
                    except Exception as exc:
                        self.error_occurred.emit(f"Write error: {exc}")
                        if _is_io_link_lost(exc):
                            self.status_changed.emit("Disconnected (USB / link lost)")
                            self._close_session(release_local=False)
                            link_dead = True
                            break
                if link_dead:
                    break

                try:
                    freq_raw = self._instrument.query("SOURce:FREQuency:CW?").strip()
                    power_raw = self._instrument.query(
                        "SOURce:POWer:LEVel:IMMediate:AMPLitude?"
                    ).strip()
                    state_raw = self._instrument.query("OUTPut:STATe?").strip()

                    freq_ghz = float(freq_raw) / 1e9
                    power_dbm = float(power_raw)
                    rf_on = state_raw == "1"

                    self.state_ready.emit(freq_ghz, power_dbm, rf_on)
                except Exception as exc:
                    self.error_occurred.emit(f"Poll error: {exc}")
                    if _is_io_link_lost(exc):
                        self.status_changed.emit("Disconnected (USB / link lost)")
                        self._close_session(release_local=False)
                        break

                QThread.msleep(int(self._poll_interval * 1000))

            except Exception as loop_exc:
                self.error_occurred.emit(str(loop_exc))
                if _is_io_link_lost(loop_exc):
                    self.status_changed.emit("Disconnected (USB / link lost)")
                    self._close_session(release_local=False)
                    break
                QThread.msleep(int(self._poll_interval * 1000))

        self._close_session(release_local=True)

    def stop(self) -> None:
        self._running = False

    def enqueue_command(self, cmd: str) -> None:
        self._cmd_queue.put(cmd)


class SigGenService(QObject):
    """Service to interact with the R&S SMB100A Signal Generator."""

    state_ready = Signal(float, float, bool)
    status_changed = Signal(str)
    resource_discovered = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[_SigGenWorker] = None

    def connect_device(self, resource_string: str) -> None:
        self.disconnect_device()

        resource_string = (resource_string or "").strip()

        self._thread = QThread()
        self._worker = _SigGenWorker(resource_string)
        self._worker.moveToThread(self._thread)

        self._worker.state_ready.connect(self.state_ready.emit)
        self._worker.status_changed.connect(self.status_changed.emit)
        self._worker.resource_resolved.connect(self.resource_discovered.emit)

        self._thread.started.connect(self._worker.start)
        self._thread.start()

    def disconnect_device(self) -> None:
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
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

    def release_to_local_panel(self) -> None:
        """SCPI 交还前面板（Local），不改变其它逻辑。"""
        if self._worker:
            self._worker.enqueue_command(_RLST_LOCAL)
