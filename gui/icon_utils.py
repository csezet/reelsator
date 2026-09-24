"""Vector and Raster Icon Utility for Reelsator GUI."""

import os
import sys
from typing import Optional
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QSize
from PySide6.QtSvg import QSvgRenderer


def get_asset_path(subpath: str) -> str:
    """Resolve asset path for development and PyInstaller bundled environments."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", subpath)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "assets", subpath)


def get_app_pixmap(name: str, color: str = "accent", size: int = 16) -> QPixmap:
    """Return a crisp QPixmap for an icon by name, color, and size."""
    # Check pre-rendered PNG first
    png_path = get_asset_path(os.path.join("icons", "png", f"{name}_{color}_{size}px.png"))
    if os.path.exists(png_path):
        pix = QPixmap(png_path)
        if not pix.isNull():
            return pix

    # Fallback to dynamic SVG render
    svg_path = get_asset_path(os.path.join("icons", f"{name}.svg"))
    if os.path.exists(svg_path):
        try:
            with open(svg_path, "r", encoding="utf-8") as f:
                raw_svg = f.read()

            color_map = {
                "accent": "#818cf8",
                "white": "#ffffff",
                "muted": "#9ca3af",
                "indigo": "#6366f1",
                "emerald": "#34d399",
            }
            hex_color = color_map.get(color, color)
            svg_data = raw_svg.replace("currentColor", hex_color)

            renderer = QSvgRenderer(svg_data.encode("utf-8"))
            pixmap = QPixmap(size, size)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return pixmap
        except Exception:
            pass

    # Empty transparent fallback
    empty = QPixmap(size, size)
    empty.fill(QColor(0, 0, 0, 0))
    return empty


def get_app_icon(name: str, color: str = "white", size: int = 16) -> QIcon:
    """Return a QIcon for buttons, menus, and actions."""
    pix = get_app_pixmap(name, color=color, size=size)
    return QIcon(pix)


def create_header_widget(icon_name: str, title: str, color: str = "accent", icon_size: int = 16, parent: Optional[QWidget] = None) -> QWidget:
    """Create a unified section header widget with vector icon and title label."""
    w = QWidget(parent)
    w.setStyleSheet("background: transparent; border: none;")
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    icon_lbl = QLabel(w)
    icon_lbl.setStyleSheet("background: transparent; border: none;")
    pix = get_app_pixmap(icon_name, color=color, size=icon_size)
    icon_lbl.setPixmap(pix)
    icon_lbl.setFixedSize(icon_size, icon_size)

    text_lbl = QLabel(title, w)
    text_lbl.setObjectName("sectionHeader")
    text_lbl.setStyleSheet("background: transparent; border: none;")

    layout.addWidget(icon_lbl)
    layout.addWidget(text_lbl)
    layout.addStretch()
    return w
