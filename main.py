"""RF Lambda Test Assistant — entry point.

Usage:
    python main.py              # normal mode (attempts VISA connection)
    python main.py --simulate   # simulation mode (no hardware required)
"""

import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main() -> None:
    simulate = "--simulate" in sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName("RF Lambda Test Assistant")

    window = MainWindow(simulate_meters=simulate)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
