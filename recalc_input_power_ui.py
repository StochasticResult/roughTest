"""Simple UI tool to recalculate corrected Actual Input Power.

Workflow:
1) Load historical cal1 and cal2 files (the ones used when values were wrong).
2) Enter legacy wrong "Actual Input Power" for each fixed frequency row.
3) Read corrected value from the output column.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from services.s2p_parser import S2PData, parse_s2p

FREQUENCIES_GHZ = [6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]


def corrected_from_wrong_actual(
    wrong_actual_input_dbm: float, cal1_offset_db: float, cal2_offset_db: float
) -> float:
    """Convert legacy wrong Actual Input Power to corrected value.

    wrong = input_raw + cal2 - cal1
    correct = input_raw - cal2 + cal1
    => correct = wrong + 2 * (cal1 - cal2)
    """
    return wrong_actual_input_dbm + 2.0 * (cal1_offset_db - cal2_offset_db)


@dataclass
class RowWidgets:
    freq_ghz: float
    wrong_var: tk.StringVar
    corrected_var: tk.StringVar
    cal1_var: tk.StringVar
    cal2_var: tk.StringVar


class RecalcInputPowerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Recalc Correct Input Power")
        self.geometry("980x460")
        self.minsize(920, 420)

        self._cal1_data: S2PData | None = None
        self._cal2_data: S2PData | None = None
        self._cal1_path_var = tk.StringVar(value="Cal1: not loaded")
        self._cal2_path_var = tk.StringVar(value="Cal2: not loaded")
        self._rows: list[RowWidgets] = []

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        top = ttk.LabelFrame(root, text="Calibration Files", padding=10)
        top.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(top, text="Load Cal1 File", command=self._load_cal1).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        ttk.Label(top, textvariable=self._cal1_path_var).grid(
            row=0, column=1, sticky="w"
        )

        ttk.Button(top, text="Load Cal2 File", command=self._load_cal2).grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(6, 0)
        )
        ttk.Label(top, textvariable=self._cal2_path_var).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        hint = ttk.Label(
            top,
            text=(
                "Each row uses nearest-frequency offsets from cal1/cal2. "
                "Enter legacy wrong Actual Input Power, get corrected value."
            ),
        )
        hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        table = ttk.LabelFrame(root, text="Frequency Rows", padding=10)
        table.pack(fill=tk.BOTH, expand=True)

        headers = [
            "Freq (GHz)",
            "Legacy Wrong Input (dBm)",
            "Corrected Input (dBm)",
            "cal1 used (dB)",
            "cal2 used (dB)",
        ]
        for col, text in enumerate(headers):
            ttk.Label(table, text=text).grid(row=0, column=col, sticky="w", padx=6)

        for i, freq in enumerate(FREQUENCIES_GHZ, start=1):
            wrong_var = tk.StringVar()
            corrected_var = tk.StringVar(value="---")
            cal1_var = tk.StringVar(value="---")
            cal2_var = tk.StringVar(value="---")

            row = RowWidgets(
                freq_ghz=freq,
                wrong_var=wrong_var,
                corrected_var=corrected_var,
                cal1_var=cal1_var,
                cal2_var=cal2_var,
            )
            self._rows.append(row)

            ttk.Label(table, text=f"{freq:.1f}").grid(
                row=i, column=0, sticky="w", padx=6, pady=4
            )
            e = ttk.Entry(table, textvariable=wrong_var, width=20)
            e.grid(row=i, column=1, sticky="w", padx=6, pady=4)
            e.bind("<KeyRelease>", lambda _evt, r=row: self._recalc_one(r))

            ttk.Label(table, textvariable=corrected_var).grid(
                row=i, column=2, sticky="w", padx=6, pady=4
            )
            ttk.Label(table, textvariable=cal1_var).grid(
                row=i, column=3, sticky="w", padx=6, pady=4
            )
            ttk.Label(table, textvariable=cal2_var).grid(
                row=i, column=4, sticky="w", padx=6, pady=4
            )

        btns = ttk.Frame(root)
        btns.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btns, text="Recalculate All", command=self._recalc_all).pack(
            side=tk.LEFT
        )
        ttk.Button(btns, text="Clear Inputs", command=self._clear_inputs).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(
            btns,
            text="Copy Corrected Outputs (newline)",
            command=self._copy_corrected_outputs,
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _pick_file(self, title: str) -> str | None:
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("S2P files", "*.s2p"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        return path or None

    def _load_cal1(self) -> None:
        path = self._pick_file("Select historical cal1 file")
        if not path:
            return
        self._load_cal(which="cal1", path=path)

    def _load_cal2(self) -> None:
        path = self._pick_file("Select historical cal2 file")
        if not path:
            return
        self._load_cal(which="cal2", path=path)

    def _load_cal(self, which: str, path: str) -> None:
        try:
            data = parse_s2p(path)
        except Exception as exc:
            messagebox.showerror("Load failed", f"Cannot parse file:\n{path}\n\n{exc}")
            return

        short = str(Path(path))
        if which == "cal1":
            self._cal1_data = data
            self._cal1_path_var.set(f"Cal1: {short}")
        else:
            self._cal2_data = data
            self._cal2_path_var.set(f"Cal2: {short}")

        self._recalc_all()

    def _offsets_for_freq(self, freq_ghz: float) -> tuple[float, float] | None:
        if self._cal1_data is None or self._cal2_data is None:
            return None
        cal1 = self._cal1_data.find_nearest(freq_ghz)[1]
        cal2 = self._cal2_data.find_nearest(freq_ghz)[1]
        return (float(cal1), float(cal2))

    def _recalc_one(self, row: RowWidgets) -> None:
        offsets = self._offsets_for_freq(row.freq_ghz)
        if offsets is None:
            row.cal1_var.set("---")
            row.cal2_var.set("---")
            row.corrected_var.set("Load cal1 and cal2 first")
            return

        cal1, cal2 = offsets
        row.cal1_var.set(f"{cal1:+.3f}")
        row.cal2_var.set(f"{cal2:+.3f}")

        txt = row.wrong_var.get().strip()
        if not txt:
            row.corrected_var.set("---")
            return

        try:
            wrong = float(txt)
        except ValueError:
            row.corrected_var.set("Invalid input")
            return

        corrected = corrected_from_wrong_actual(wrong, cal1, cal2)
        row.corrected_var.set(f"{corrected:+.4f}")

    def _recalc_all(self) -> None:
        for row in self._rows:
            self._recalc_one(row)

    def _clear_inputs(self) -> None:
        for row in self._rows:
            row.wrong_var.set("")
            row.corrected_var.set("---")

    def _copy_corrected_outputs(self) -> None:
        """Copy corrected output column as one value per line for Excel paste."""
        lines: list[str] = []
        for row in self._rows:
            text = row.corrected_var.get().strip()
            try:
                value = float(text)
                lines.append(f"{value:+.4f}")
            except ValueError:
                # Keep row alignment for Excel: blank line if row not computed yet.
                lines.append("")

        payload = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.update_idletasks()


def main() -> None:
    app = RecalcInputPowerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
