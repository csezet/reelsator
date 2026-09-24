"""Reelsator — Desktop Application Entry Point."""

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui.main_window import MainWindow


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
    app.setApplicationDisplayName("Reelsator — Instagram AI Photo Studio")
    app.setOrganizationName("csezet")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
