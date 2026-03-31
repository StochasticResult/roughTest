"""R&S NRP-Z85 power meter communication via PyVISA.

Supports explicit discovery, user-initiated connect / disconnect,
and an optional simulation mode for development without hardware.
"""

from __future__ import annotations

import random
import subprocess
import ctypes
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

INPUT_METER_SERIAL = "102073"
OUTPUT_METER_SERIAL = "101823"


@dataclass
class WindowsUsbDevice:
    """A Windows-detected USB power sensor."""

    friendly_name: str
    instance_id: str
    status: str
    serial: str


class _MeterPoller(QObject):
    """Worker that runs in a dedicated QThread and polls a VISA/NRP resource."""

    reading_ready = Signal(float, str)   # value_dbm, timestamp_iso
    status_changed = Signal(str)         # status text
    error_occurred = Signal(str)

    def __init__(
        self,
        resource_string: Optional[str],
        poll_interval_s: float = 0.5,
        simulate: bool = False,
        sim_center: float = 0.0,
    ) -> None:
        super().__init__()
        self._resource = resource_string
        self._poll_interval = poll_interval_s
        self._simulate = simulate
        self._sim_center = sim_center
        self._running = False
        
        self._instrument = None
        self._is_nrp_dll = False
        self._nrp_session = None
        self._nrp_dll = None

    @Slot()
    def start(self) -> None:
        self._running = True

        if self._simulate:
            self.status_changed.emit("Simulation mode")
            self._poll_simulated()
            return

        if not self._resource:
            self.status_changed.emit("Device not found")
            return

        # Attempt to use R&S NRP legacy DLL for direct USB sensor communication
        if "0x0083" in self._resource or "0x83" in self._resource or "NRP" in self._resource.upper():
            try:
                self._nrp_dll = ctypes.cdll.LoadLibrary("rsnrpz_64.dll")
                session = ctypes.c_int32(0)
                
                # DLL initialization might need the raw resource string like "USB::..."
                res_str = self._resource
                # Some basic cleanup just in case
                res_str = res_str.replace("::INSTR", "")
                if res_str.startswith("USB0::"):
                    res_str = res_str.replace("USB0::", "USB::")
                    
                res_bytes = res_str.encode("utf-8")
                status = self._nrp_dll.rsnrpz_init(res_bytes, 1, 1, ctypes.byref(session))
                if status == 0:
                    self._nrp_session = session
                    self._is_nrp_dll = True
                    self.status_changed.emit("Connected (NRP DLL)")
                    self._poll_real()
                    return
            except Exception as e:
                print(f"Failed to init rsnrpz_64.dll: {e}")

        # Fallback to standard PyVISA
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            self._instrument = rm.open_resource(self._resource)
            self._instrument.timeout = 3000
            idn = self._instrument.query("*IDN?").strip()
            self.status_changed.emit(f"Connected: {idn}")
            try:
                self._instrument.write("INIT:CONT ON")
            except Exception:
                pass
        except Exception as exc:
            self.status_changed.emit(f"Connection failed: {exc}")
            self.error_occurred.emit(str(exc))
            return

        self._poll_real()

    def stop(self) -> None:
        self._running = False

    def _poll_real(self) -> None:
        while self._running:
            try:
                if self._is_nrp_dll and self._nrp_session:
                    meas_val = ctypes.c_double(0)
                    stat = self._nrp_dll.rsnrpz_meass_readMeasurement(
                        self._nrp_session, 1, 5000, ctypes.byref(meas_val)
                    )
                    if stat == 0:
                        value_w = meas_val.value
                        if value_w > 0:
                            value_dbm = 10.0 * math.log10(value_w) + 30.0
                            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            self.reading_ready.emit(value_dbm, ts)
                        else:
                            # It's returning 0 or negative W, probably just noise floor
                            # Don't overwrite a good reading with -200 if it's just intermittent zero
                            pass
                    else:
                        self.status_changed.emit(f"NRP Read error code: {stat}")
                else:
                    raw = self._instrument.query("FETCH?").strip()
                    value_w = float(raw)
                    if value_w > 0:
                        value_dbm = 10.0 * math.log10(value_w) + 30.0
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        self.reading_ready.emit(value_dbm, ts)
                    else:
                        pass
            except Exception as exc:
                self.error_occurred.emit(str(exc))
                self.status_changed.emit(f"Read error: {exc}")
            QThread.msleep(int(self._poll_interval * 1000))

        if self._is_nrp_dll and self._nrp_session:
            try:
                self._nrp_dll.rsnrpz_close(self._nrp_session)
            except Exception:
                pass
        elif self._instrument:
            try:
                self._instrument.close()
            except Exception:
                pass

    def _poll_simulated(self) -> None:
        self.status_changed.emit("Simulation mode")
        while self._running:
            value = self._sim_center + random.gauss(0, 0.05)
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.reading_ready.emit(round(value, 3), ts)
            QThread.msleep(int(self._poll_interval * 1000))


class PowerMeterService(QObject):
    """Manages input and output power meter connections and polling."""

    input_reading = Signal(float, str)    # dBm, timestamp
    output_reading = Signal(float, str)
    input_status = Signal(str)
    output_status = Signal(str)
    discovery_complete = Signal(str)

    def __init__(
        self,
        poll_interval_s: float = 0.5,
        simulate: bool = False,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._poll_interval = poll_interval_s
        self._simulate = simulate

        self._input_thread: Optional[QThread] = None
        self._output_thread: Optional[QThread] = None
        self._input_worker: Optional[_MeterPoller] = None
        self._output_worker: Optional[_MeterPoller] = None

        self._input_resource: Optional[str] = None
        self._output_resource: Optional[str] = None

        self._running = False

        if simulate:
            self.input_status.emit("Simulation mode")
            self.output_status.emit("Simulation mode")
        else:
            self.input_status.emit("Disconnected")
            self.output_status.emit("Disconnected")

    def set_manual_resources(
        self,
        input_resource: Optional[str],
        output_resource: Optional[str],
    ) -> None:
        """Override the auto-discovered VISA resources."""
        self._input_resource = input_resource or None
        self._output_resource = output_resource or None

    def _list_visa_resources(self) -> list[str]:
        """Return all VISA resources visible to PyVISA."""
        try:
            import pyvisa

            rm = pyvisa.ResourceManager()
            return list(rm.list_resources())
        except Exception:
            return []

    def _list_windows_usb_devices(self) -> list[WindowsUsbDevice]:
        """Return Windows-visible R&S NRP sensors using PowerShell."""
        command = (
            "Get-PnpDevice | "
            "Where-Object { $_.InstanceId -match 'VID_0AAD&PID_0083' } | "
            "Select-Object Status,FriendlyName,InstanceId | ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return []

        if result.returncode != 0 or not result.stdout.strip():
            return []

        try:
            import json

            data = json.loads(result.stdout)
        except Exception:
            return []

        if isinstance(data, dict):
            data = [data]

        devices: list[WindowsUsbDevice] = []
        for item in data:
            instance_id = str(item.get("InstanceId", ""))
            serial = instance_id.split("\\")[-1] if "\\" in instance_id else ""
            devices.append(
                WindowsUsbDevice(
                    friendly_name=str(item.get("FriendlyName", "")),
                    instance_id=instance_id,
                    status=str(item.get("Status", "")),
                    serial=serial,
                )
            )
        return devices

    def discover_meters(self) -> dict[str, Optional[str]]:
        """Search VISA resources for NRP-Z85 sensors by serial number."""
        self._input_resource = None
        self._output_resource = None
        visa_resources = self._list_visa_resources()
        windows_devices = self._list_windows_usb_devices()

        try:
            import pyvisa

            rm = pyvisa.ResourceManager()
        except Exception as exc:
            message = f"VISA discovery failed: {exc}"
            self.discovery_complete.emit(message)
            self.input_status.emit("Discovery failed")
            self.output_status.emit("Discovery failed")
            return {
                "input": None,
                "output": None,
                "visa_resources": [],
                "windows_usb_devices": windows_devices,
            }

        for res in visa_resources:
            res_upper = res.upper()
            if INPUT_METER_SERIAL in res_upper:
                self._input_resource = res
            elif OUTPUT_METER_SERIAL in res_upper:
                self._output_resource = res

        # If PyVISA didn't find them but Windows did, manually construct the resource strings
        # so the fallback NRP DLL can still talk to them!
        if self._input_resource is None:
            for d in windows_devices:
                if INPUT_METER_SERIAL in d.serial:
                    self._input_resource = f"USB::0x0AAD::0x0083::{INPUT_METER_SERIAL}"
        if self._output_resource is None:
            for d in windows_devices:
                if OUTPUT_METER_SERIAL in d.serial:
                    self._output_resource = f"USB::0x0AAD::0x0083::{OUTPUT_METER_SERIAL}"

        if self._input_resource is None or self._output_resource is None:
            for res in visa_resources:
                if "USB" not in res.upper() and "TCPIP" not in res.upper():
                    continue
                try:
                    inst = rm.open_resource(res)
                    inst.timeout = 2000
                    idn = inst.query("*IDN?").strip()
                    inst.close()
                    if INPUT_METER_SERIAL in idn and self._input_resource is None:
                        self._input_resource = res
                    elif OUTPUT_METER_SERIAL in idn and self._output_resource is None:
                        self._output_resource = res
                except Exception:
                    continue

        input_state = self._input_resource or "not found"
        output_state = self._output_resource or "not found"

        visa_summary = ", ".join(visa_resources) if visa_resources else "(none)"
        windows_summary = (
            ", ".join(f"{d.friendly_name} [{d.serial}]" for d in windows_devices)
            if windows_devices
            else "(none)"
        )
        message = (
            f"Discovery complete | Input: {input_state} | Output: {output_state}\n"
            f"VISA resources: {visa_summary}\n"
            f"Windows USB sensors: {windows_summary}"
        )

        if windows_devices and not any("USB" in resource.upper() for resource in visa_resources):
            message += (
                "\nWindows can see the sensors, but VISA cannot. "
                "Install the R&S NRP Toolkit and NRP NI-VISA Passport, then reboot."
            )

        self.discovery_complete.emit(message)
        if self._input_resource is None:
            self.input_status.emit("Input meter not found")
        else:
            self.input_status.emit("Input meter ready")
        if self._output_resource is None:
            self.output_status.emit("Output meter not found")
        else:
            self.output_status.emit("Output meter ready")

        return {
            "input": self._input_resource,
            "output": self._output_resource,
            "visa_resources": visa_resources,
            "windows_usb_devices": windows_devices,
        }

    def connect_meters(self) -> None:
        """Start polling both meters in background threads."""
        self.stop()
        self._running = True
        if not self._simulate and self._input_resource is None and self._output_resource is None:
            self.discover_meters()

        self._start_worker(
            "input",
            self._input_resource,
            sim_center=-10.0,
        )
        self._start_worker(
            "output",
            self._output_resource,
            sim_center=15.0,
        )

    def set_simulate(self, enabled: bool) -> None:
        """Switch between real hardware and simulation mode."""
        self._simulate = enabled
        self.stop()
        if enabled:
            self.input_status.emit("Simulation mode")
            self.output_status.emit("Simulation mode")
        else:
            self.input_status.emit("Disconnected")
            self.output_status.emit("Disconnected")

    def _start_worker(
        self, role: str, resource: Optional[str], sim_center: float
    ) -> None:
        if not self._simulate and not resource:
            if role == "input":
                self.input_status.emit("Input meter not available")
            else:
                self.output_status.emit("Output meter not available")
            return

        thread = QThread()
        worker = _MeterPoller(
            resource_string=resource,
            poll_interval_s=self._poll_interval,
            simulate=self._simulate,
            sim_center=sim_center,
        )
        worker.moveToThread(thread)

        if role == "input":
            worker.reading_ready.connect(self.input_reading.emit)
            worker.status_changed.connect(self.input_status.emit)
            self._input_thread = thread
            self._input_worker = worker
        else:
            worker.reading_ready.connect(self.output_reading.emit)
            worker.status_changed.connect(self.output_status.emit)
            self._output_thread = thread
            self._output_worker = worker

        thread.started.connect(worker.start)
        thread.start()

    def stop(self) -> None:
        """Stop polling and clean up threads."""
        self._running = False
        for worker, thread in [
            (self._input_worker, self._input_thread),
            (self._output_worker, self._output_thread),
        ]:
            if worker:
                worker.stop()
            if thread:
                thread.quit()
                thread.wait(2000)
        self._input_worker = None
        self._output_worker = None
        self._input_thread = None
        self._output_thread = None

        if self._simulate:
            self.input_status.emit("Simulation mode")
            self.output_status.emit("Simulation mode")
        else:
            self.input_status.emit("Disconnected")
            self.output_status.emit("Disconnected")

    def set_poll_interval(self, seconds: float) -> None:
        self._poll_interval = seconds
        for w in (self._input_worker, self._output_worker):
            if w:
                w._poll_interval = seconds
