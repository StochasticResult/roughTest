"""Dark-theme stylesheet optimised for bench / lab use.

High contrast, large text for readings, colour-coded sections.
"""

LIGHT_STYLESHEET = """
QWidget {
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #ced4da;
    border-radius: 4px;
    margin-top: 18px;
    padding-top: 15px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QPushButton {
    border: 1px solid #adb5bd;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #e9ecef; }
QPushButton:pressed { background-color: #dee2e6; }
QPushButton#save_big {
    background-color: #198754;
    color: white;
    font-weight: bold;
    font-size: 16px;
    padding: 10px;
    border: none;
    border-radius: 6px;
}
QPushButton#save_big:hover { background-color: #157347; }
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    border: 1px solid #adb5bd;
    border-radius: 4px;
    padding: 4px;
}
QLabel#app_title {
    font-size: 20px;
    font-weight: bold;
    color: #0d6efd;
}
QLabel#section_title {
    font-size: 14px;
    font-weight: bold;
    color: #0d6efd;
}
QLabel#metric_title {
    font-size: 13px;
    font-weight: bold;
}
QLabel#reading_big {
    font-size: 20px;
    font-weight: bold;
    color: #198754;
    font-family: "Consolas", monospace;
}
QLabel#reading_raw {
    font-size: 16px;
    font-weight: bold;
    color: #fd7e14;
    font-family: "Consolas", monospace;
}
QLabel#status_ok { color: #198754; font-weight: bold; }
QLabel#status_err { color: #dc3545; font-weight: bold; }
QLabel#status_warn { color: #fd7e14; font-weight: bold; }
QLabel#offset_val { color: #0d6efd; font-weight: bold; }

QFrame#panel_card, QFrame#metric_card {
    border: 1px solid #dee2e6;
    border-radius: 6px;
}
QFrame#sidebar {
    border-right: 1px solid #dee2e6;
}
QTableWidget {
    border: 1px solid #dee2e6;
}
"""
