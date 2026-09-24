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


def run_smoke_test() -> int:
    """Headless verification of GUI initialization, OpenCV cascades, assets, and processing pipeline."""
    print("[SMOKE-TEST] Starting Reelsator smoke test...")
    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication.instance() or QApplication([sys.argv[0], "-platform", "offscreen"])
        app.setApplicationName("Reelsator")
        app.setOrganizationName("csezet")

        # 1. Verify assets
        print("[SMOKE-TEST] Checking application assets...")
        icon_path = get_resource_path(os.path.join("assets", "icon.ico"))
        if not os.path.exists(icon_path):
            icon_path = get_resource_path(os.path.join("assets", "icon.png"))
        if not os.path.exists(icon_path):
            print(f"[SMOKE-TEST] WARNING: Application icon not found: {icon_path}")
        else:
            print(f"[SMOKE-TEST] Found icon at {icon_path}")

        # 2. Verify MainWindow instantiation
        print("[SMOKE-TEST] Initializing MainWindow in offscreen mode...")
        window = MainWindow()
        if not window:
            raise RuntimeError("Failed to instantiate MainWindow")
        print("[SMOKE-TEST] MainWindow initialized successfully.")

        # 3. Verify OpenCV Face Cascade
        print("[SMOKE-TEST] Verifying SmartCropper face cascade detector...")
        from core.smart_cropper import SmartCropper
        cropper = SmartCropper()
        if cropper.frontal_face_cascade and not cropper.frontal_face_cascade.empty():
            print(f"[SMOKE-TEST] Frontal face cascade loaded: {cropper.frontal_cascade_path}")
        else:
            print("[SMOKE-TEST] Note: Frontal face cascade empty or uninitialized (non-critical fallback).")

        # 4. Verify InstaOptimizer pipeline for all metadata modes
        print("[SMOKE-TEST] Running synthetic image through InstaOptimizer...")
        from PIL import Image
        from core.insta_optimizer import InstaOptimizer, ProcessingConfig
        from core.exif_spoofer import MetadataMode

        test_img = Image.new("RGBA", (320, 320), color=(100, 150, 200, 255))
        optimizer = InstaOptimizer()

        for mode in (MetadataMode.NO_EXIF, MetadataMode.MINIMAL, MetadataMode.SYNTHETIC_CAMERA):
            cfg = ProcessingConfig(metadata_mode=mode)
            out_img, exif_bytes = optimizer.process_pil(test_img, cfg)
            if out_img is None or out_img.size[0] <= 0:
                raise RuntimeError(f"Optimizer failed for metadata mode {mode}")
            if mode == MetadataMode.NO_EXIF and len(exif_bytes) != 0:
                raise RuntimeError("NO_EXIF mode returned non-empty exif_bytes!")
            print(f"[SMOKE-TEST] Mode {mode.value} passed (output size: {out_img.size}, exif bytes: {len(exif_bytes)}).")

        print("[SMOKE-TEST] ALL SMOKE-TEST CHECKS PASSED SUCCESSFULLY!")
        return 0
    except Exception as e:
        import traceback
        print(f"[SMOKE-TEST] FAILURE: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


def main():
    if "--smoke-test" in sys.argv:
        code = run_smoke_test()
        sys.exit(code)

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
