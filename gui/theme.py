"""Windows 11 Fluent Dark Theme QSS stylesheet and color palette for Reelsator."""

DARK_THEME_QSS = """
/* Global Window & Fonts */
QWidget {
    background-color: #16171b;
    color: #e5e7eb;
    font-family: "Segoe UI Variable Text", "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

/* Card Containers & Panels */
QFrame#cardPanel, QFrame#sidebarPanel {
    background-color: #1e1f26;
    border: 1px solid #2b2d38;
    border-radius: 12px;
}

QFrame#previewCard {
    background-color: #121316;
    border: 1px solid #2b2d38;
    border-radius: 12px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #373946;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #4b4e5f;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
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
    transform: scale(1.1);
}

/* CheckBox */
QCheckBox {
    color: #e5e7eb;
    spacing: 8px;
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

/* Labels */
QLabel {
    color: #e5e7eb;
}
QLabel#titleLabel {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
}
QLabel#subtitleLabel {
    font-size: 12px;
    color: #9ca3af;
}
QLabel#sectionHeader {
    font-size: 13px;
    font-weight: 600;
    color: #c7d2fe;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#valueLabel {
    font-size: 12px;
    color: #818cf8;
    font-weight: 600;
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
