"""Reelsator — Desktop Application Entry Point."""

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from gui.main_window import MainWindow


def get_resource_path(relative_path: str) -> str:
    """Resolve absolute path for local development and PyInstaller bundled environments."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def main():
    # Windows taskbar icon grouping support
    if os.name == "nt":
        try:
            import ctypes
            myappid = "csezet.reelsator.instagram_cleaner.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            # Ensure GUI attaches to the user's interactive desktop if launched from background/sandbox
            h_desk = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                ctypes.windll.user32.SetThreadDesktop(h_desk)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Reelsator")
    app.setApplicationDisplayName("")
    app.setOrganizationName("csezet")

    # Set application icon
    icon_path = get_resource_path(os.path.join("assets", "icon.ico"))
    if not os.path.exists(icon_path):
        icon_path = get_resource_path(os.path.join("assets", "icon.png"))
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    # Apply Windows 11 dark seamless titlebar
    try:
        from gui.theme import apply_windows_dark_titlebar
        apply_windows_dark_titlebar(int(window.winId()), bg_color=0x00161312, hide_title_text=True)
    except Exception:
        pass

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
