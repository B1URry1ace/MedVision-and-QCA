#theme.py
from __future__ import annotations

from PySide6.QtWidgets import QApplication


ACCENT = "#0078d4"
ACCENT_DARK = "#005a9e"


LIGHT_QSS = """
QWidget {
    background-color: #f3f3f3;
    color: #1f1f1f;
    font-size: 10pt;
}
QMainWindow, QDialog { background-color: #f3f3f3; }
QMenuBar { background-color: #ffffff; border-bottom: 1px solid #d6d6d6; }
QMenuBar::item:selected { background-color: #e6e6e6; }
QMenu { background-color: #ffffff; border: 1px solid #d6d6d6; }
QMenu::item:selected { background-color: #e6e6e6; }
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 22px;
}
QPushButton:hover { background-color: #f0f0f0; border-color: #b0b0b0; }
QPushButton:pressed { background-color: #e0e0e0; }
QPushButton:checked {
    background-color: #0078d4;
    color: #ffffff;
    border-color: #005a9e;
}
QPushButton:disabled { color: #999999; background-color: #f0f0f0; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #0078d4;
}
QComboBox::drop-down { border: none; }
QListWidget, QListView, QTextBrowser {
    background-color: #ffffff;
    border: 1px solid #d6d6d6;
    border-radius: 4px;
}
QListWidget::item:selected, QListView::item:selected {
    background-color: #cfe4f7;
    color: #1f1f1f;
}
QTabWidget::pane { background: #ffffff; border: 1px solid #d6d6d6; }
QTabBar::tab {
    background: #f3f3f3;
    padding: 6px 14px;
    border: 1px solid #d6d6d6;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected { background: #ffffff; }
QTabBar::tab:hover:!selected { background: #e8e8e8; }
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #d6d6d6;
    border-radius: 6px;
}
QFrame#Card:hover { border-color: #b0b0b0; background-color: #fafafa; }
QStatusBar { background-color: #ffffff; border-top: 1px solid #d6d6d6; }
QSlider::groove:horizontal {
    height: 4px; background: #d6d6d6; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0078d4; width: 16px; height: 16px;
    margin: -6px 0; border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: #005a9e; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #999999; border-radius: 3px;
    background: #ffffff;
}
QCheckBox::indicator:checked { background: #0078d4; border-color: #005a9e; }
QScrollBar:vertical {
    background: #f0f0f0; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #c1c1c1; border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #a8a8a8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip {
    background-color: #ffffe1; color: #1f1f1f;
    border: 1px solid #888888; padding: 3px;
}
"""


DARK_QSS = """
QWidget {
    background-color: #1f1f1f;
    color: #f0f0f0;
    font-size: 10pt;
}
QMainWindow, QDialog { background-color: #1f1f1f; }
QMenuBar { background-color: #2d2d2d; border-bottom: 1px solid #404040; }
QMenuBar::item:selected { background-color: #3a3a3a; }
QMenu { background-color: #2d2d2d; border: 1px solid #404040; }
QMenu::item:selected { background-color: #3a3a3a; }
QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #505050;
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 22px;
    color: #f0f0f0;
}
QPushButton:hover { background-color: #3a3a3a; border-color: #707070; }
QPushButton:pressed { background-color: #4a4a4a; }
QPushButton:checked {
    background-color: #0078d4;
    color: #ffffff;
    border-color: #4a9be0;
}
QPushButton:disabled { color: #707070; background-color: #2a2a2a; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #505050;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
    color: #f0f0f0;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #0078d4;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background-color: #2d2d2d; color: #f0f0f0; }
QListWidget, QListView, QTextBrowser {
    background-color: #2a2a2a;
    border: 1px solid #404040;
    border-radius: 4px;
    color: #f0f0f0;
}
QListWidget::item:selected, QListView::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}
QTabWidget::pane { background: #2a2a2a; border: 1px solid #404040; }
QTabBar::tab {
    background: #1f1f1f;
    padding: 6px 14px;
    border: 1px solid #404040;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #d0d0d0;
}
QTabBar::tab:selected { background: #2a2a2a; color: #ffffff; }
QTabBar::tab:hover:!selected { background: #353535; }
QFrame#Card {
    background-color: #2a2a2a;
    border: 1px solid #404040;
    border-radius: 6px;
}
QFrame#Card:hover { border-color: #606060; background-color: #303030; }
QStatusBar { background-color: #2d2d2d; border-top: 1px solid #404040; color: #d0d0d0; }
QSlider::groove:horizontal {
    height: 4px; background: #505050; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0078d4; width: 16px; height: 16px;
    margin: -6px 0; border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: #4a9be0; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #707070; border-radius: 3px;
    background: #2d2d2d;
}
QCheckBox::indicator:checked { background: #0078d4; border-color: #4a9be0; }
QScrollBar:vertical {
    background: #2a2a2a; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #555555; border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #707070; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip {
    background-color: #404040; color: #f0f0f0;
    border: 1px solid #606060; padding: 3px;
}
"""


def apply_theme(name: str) -> None:
    app = QApplication.instance()
    if app is None:
        return
    qss = DARK_QSS if name == "dark" else LIGHT_QSS
    app.setStyleSheet(qss)
