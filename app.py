"""Reelsator — Desktop Application Entry Point."""

import sys
import os
import json
import tempfile
from pathlib import Path
from dataclasses import replace
from core.version import APP_VERSION

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from gui.main_window import MainWindow


def get_resource_path(relative_path: str) -> str:
    """Resolve absolute path for local development and PyInstaller bundled environments."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def run_smoke_test(report_path=None) -> int:
    """Headless verification of GUI initialization, OpenCV cascades, assets, and processing pipeline."""
    report = {"version": APP_VERSION, "frozen": bool(getattr(sys, "frozen", False)), "checks": [], "status": "failed"}

    def record(message):
        report["checks"].append(message)
        if sys.stdout is not None:
            print(f"[SMOKE-TEST] {message}")

    test_folder = tempfile.TemporaryDirectory(prefix="reelsator-smoke-")
    window = None
    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication.instance() or QApplication([sys.argv[0], "-platform", "offscreen"])
        app.setApplicationName("Reelsator")
        app.setOrganizationName("csezet")

        # 1. Verify assets
        record("Checking application assets...")
        icon_path = get_resource_path(os.path.join("assets", "icon.ico"))
        if not os.path.exists(icon_path):
            icon_path = get_resource_path(os.path.join("assets", "icon.png"))
        if not os.path.exists(icon_path):
            raise RuntimeError(f"Application icon not found: {icon_path}")
        else:
            record("Application icon found.")

        # 2. Verify MainWindow instantiation
        record("Initializing MainWindow in offscreen mode...")
        from core.user_presets import PresetStore, recipe_config
        store = PresetStore(Path(test_folder.name) / "presets.json")
        window = MainWindow(preset_store=store)
        if not window:
            raise RuntimeError("Failed to instantiate MainWindow")
        record("MainWindow initialized successfully.")

        # 3. Verify OpenCV Face Cascade
        record("Verifying SmartCropper face cascade detector...")
        from core.smart_cropper import SmartCropper
        cropper = SmartCropper()
        if not cropper.frontal_face_cascade or cropper.frontal_face_cascade.empty():
            raise RuntimeError(f"Required OpenCV face cascade failed to load from: {cropper.frontal_cascade_path}")
        record("Frontal face cascade loaded successfully.")
        if not cropper.profile_face_cascade or cropper.profile_face_cascade.empty():
            raise RuntimeError("Required profile face cascade failed to load")
        record("Profile face cascade loaded successfully.")

        # 4. Verify InstaOptimizer pipeline for all metadata modes
        record("Running synthetic image through InstaOptimizer...")
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
            record(f"Mode {mode.value} passed (output size: {out_img.size}, exif bytes: {len(exif_bytes)}).")

        source = Path(test_folder.name) / "source.png"
        test_img.save(source)
        outputs = []
        for name, button, factory in (
            ("soft-flash", window.settings_panel.btn_preset_soft_flash, ProcessingConfig.soft_flash),
            ("digicam-flash", window.settings_panel.btn_preset_digicam_flash, ProcessingConfig.digicam_flash),
        ):
            button.click()
            if window.settings_panel.get_current_config() != factory():
                raise RuntimeError(f"GUI preset mismatch: {name}")
            cfg = replace(factory(), random_seed=1729)
            preview = optimizer.process_preview_file(str(source), cfg)
            destination = Path(test_folder.name) / f"{name}.jpg"
            optimizer.process_file(str(source), str(destination), cfg)
            with Image.open(destination) as saved:
                exported = saved.convert("RGB")
            if exported.tobytes() != preview.jpeg.tobytes() or destination.stat().st_size != preview.jpeg_size_bytes:
                raise RuntimeError(f"JPEG preview/export mismatch: {name}")
            outputs.append(exported.tobytes())
            record(f"{name}: GUI controls and JPEG preview/export passed.")
        if outputs[0] == outputs[1]:
            raise RuntimeError("Flash preset outputs must be different")
        window.settings_panel.slider_jpeg.setValue(93)
        if not window.settings_panel.btn_reset_profile.isEnabled():
            raise RuntimeError("Edited preset must allow reset")
        personal = recipe_config(window.settings_panel.get_current_config())
        store.save("Smoke Flash", personal)
        if PresetStore(store.path).read().get("Smoke Flash") != personal:
            raise RuntimeError("User preset persistence mismatch")
        window.settings_panel._refresh_user_presets(selected="Smoke Flash")
        window.settings_panel._on_user_preset_selected(window.settings_panel.combo_user_presets.currentIndex())
        if window.settings_panel.get_current_config() != personal:
            raise RuntimeError("User preset GUI loading mismatch")
        record("User preset disk round-trip and GUI loading passed.")
        report["status"] = "passed"
        record("ALL SMOKE-TEST CHECKS PASSED SUCCESSFULLY!")
        return 0
    except Exception as e:
        import traceback
        report["error"] = str(e)
        report["traceback"] = traceback.format_exc()
        if sys.stderr is not None:
            print(f"[SMOKE-TEST] FAILURE: {e}", file=sys.stderr)
            traceback.print_exc()
        return 1
    finally:
        if window is not None:
            window.close()
        test_folder.cleanup()
        if report_path is not None:
            destination = Path(report_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    if "--smoke-test" in sys.argv:
        report_path = None
        if "--smoke-test-report" in sys.argv:
            index = sys.argv.index("--smoke-test-report")
            if index + 1 >= len(sys.argv):
                sys.exit(2)
            report_path = sys.argv[index + 1]
        code = run_smoke_test(report_path)
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
