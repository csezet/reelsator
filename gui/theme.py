"""Windows 11 Fluent Dark Theme QSS stylesheet and color palette for Reelsator."""

import os

DARK_THEME_QSS = """
/* Global Window & Typography */
QMainWindow, QDialog {
    background-color: #121316;
}

QWidget {
    color: #e5e7eb;
    font-family: "Segoe UI Variable Text", "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

QWidget#centralWidget {
    background-color: #121316;
}

/* Card Containers & Panels */
QFrame#cardPanel, QFrame#sidebarPanel {
    background-color: #1e1f26;
    border: 1px solid #2b2d38;
    border-radius: 12px;
}

QFrame#previewCard {
    background-color: #181920;
    border: 1px solid #2b2d38;
    border-radius: 12px;
}

/* Sleek Windows 11 Fluent Scrollbars */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 4px 1px 4px 0px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.16);
    min-height: 36px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(99, 102, 241, 0.7);
}
QScrollBar::handle:vertical:pressed {
    background: #6366f1;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    border: none;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 6px;
    margin: 0px 4px 1px 4px;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.16);
    min-width: 36px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(99, 102, 241, 0.7);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    border: none;
    background: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    border: none;
    background: none;
}

/* Scroll Area Backgrounds */
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}

/* Push Buttons */
QPushButton {
    background-color: #2b2d38;
    color: #f3f4f6;
    border: 1px solid #373946;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #373946;
    border-color: #4b4e5f;
}
QPushButton:pressed {
    background-color: #22232c;
}
QPushButton:disabled {
    background-color: #1a1b22;
    color: #525565;
    border-color: #22242f;
}

/* Primary Accent CTA Button */
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
}
QPushButton#primaryButton:pressed {
    background: #4338ca;
}
QPushButton#primaryButton:disabled {
    background: #2b2d38;
    color: #6b7280;
}

/* Preset Pill Buttons */
QPushButton#pillButton {
    background-color: #232530;
    color: #9ca3af;
    border: 1px solid #2f3241;
    border-radius: 16px;
    padding: 6px 14px;
    font-size: 12px;
    text-align: left;
}
QPushButton#pillButton:hover {
    background-color: #2b2e3c;
    color: #e5e7eb;
}
QPushButton#pillButton:checked {
    background-color: #3730a3;
    color: #e0e7ff;
    border-color: #6366f1;
    font-weight: 600;
}

/* ComboBox */
QComboBox {
    background-color: #242632;
    border: 1px solid #323544;
    border-radius: 8px;
    padding: 6px 12px;
    color: #f3f4f6;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #6366f1;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
}
QComboBox QAbstractItemView {
    background-color: #1e1f28;
    border: 1px solid #323544;
    border-radius: 8px;
    color: #f3f4f6;
    selection-background-color: #4f46e5;
    padding: 4px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #2b2d38;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #6366f1;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #f3f4f6;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
    border: 2px solid #6366f1;
}
QSlider::handle:horizontal:hover {
    background: #ffffff;
}

/* CheckBox */
QCheckBox {
    color: #e5e7eb;
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #373946;
    background: #242632;
}
QCheckBox::indicator:hover {
    border-color: #6366f1;
}
QCheckBox::indicator:checked {
    background: #6366f1;
    border-color: #6366f1;
    image: none;
}

/* Progress Bar */
QProgressBar {
    background-color: #22242e;
    border: 1px solid #2b2d38;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #ec4899);
    border-radius: 5px;
}

/* Labels - Strictly Transparent to Eliminate Background Boxes */
QLabel {
    background-color: transparent;
    border: none;
    color: #e5e7eb;
}
QLabel#titleLabel {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    background-color: transparent;
}
QLabel#subtitleLabel {
    font-size: 12px;
    color: #9ca3af;
    background-color: transparent;
}
QLabel#sectionHeader {
    font-size: 13px;
    font-weight: 600;
    color: #c7d2fe;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background-color: transparent;
}
QLabel#valueLabel {
    font-size: 12px;
    color: #818cf8;
    font-weight: 600;
    background-color: transparent;
}
QLabel#badgeOk {
    background-color: #064e3b;
    color: #6ee7b7;
    border: 1px solid #059669;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#badgeWarn {
    background-color: #451a03;
    color: #fcd34d;
    border: 1px solid #b45309;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}
"""


def apply_windows_dark_titlebar(hwnd: int, bg_color: int = 0x00161312, hide_title_text: bool = True):
    """
    Apply native Windows 11 immersive dark mode and seamless caption coloring.

    Args:
        hwnd: Native OS window handle (int(winId())).
        bg_color: Color in COLORREF format (0x00BBGGRR). Default 0x00161312 matches #121316.
        hide_title_text: If True, sets title text color to bg_color so top bar merges cleanly.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwmapi = ctypes.windll.dwmapi
        # DWMWA_USE_IMMERSIVE_DARK_MODE (20)
        dark = wintypes.BOOL(True)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        # DWMWA_CAPTION_COLOR (35)
        caption = wintypes.DWORD(bg_color)
        dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
        # DWMWA_TEXT_COLOR (36)
        text_color = wintypes.DWORD(bg_color if hide_title_text else 0x00EBE7E5)
        dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))
        # DWMWA_BORDER_COLOR (34)
        border = wintypes.DWORD(bg_color)
        dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border), ctypes.sizeof(border))
    except Exception:
        pass
