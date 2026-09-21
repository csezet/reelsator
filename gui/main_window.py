"""Main Application Window for Reelsator with Windows 11 Fluent interface."""

import os
import subprocess
from typing import List, Optional
from PIL import Image

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QProgressBar, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QIcon


from core.insta_optimizer import InstaOptimizer, ProcessingConfig
from core.pipeline import BatchPipeline, ProcessItemResult
from gui.theme import DARK_THEME_QSS
from gui.components.drop_zone import DropZoneWidget
from gui.components.comparison_slider import ComparisonSliderWidget
from gui.components.settings_panel import SettingsPanelWidget
from gui.components.batch_list import BatchListWidget


import logging

logger = logging.getLogger(__name__)


class PreviewWorker(QThread):
    """Generates processed preview for the comparison slider in background."""

    preview_ready = Signal(int, object)  # (generation_id, PIL.Image)
    preview_failed = Signal(int, str)    # (generation_id, error_message)

    def __init__(self, optimizer: InstaOptimizer, image_path: str, config: ProcessingConfig, generation: int):
        super().__init__()
        self.optimizer = optimizer
        self.image_path = image_path
        self.config = config
        self.generation = generation

    def run(self):
        try:
            with Image.open(self.image_path) as src:
                src.load()
                # Downscale for instant preview responsiveness if original is huge
                w, h = src.size
                if max(w, h) > 1600:
                    scale = 1600 / max(w, h)
                    src_preview = src.resize((int(w * scale), int(h * scale)), Image.BILINEAR)
                else:
                    src_preview = src.copy()

                processed_img, _ = self.optimizer.process_pil(src_preview, self.config)
                self.preview_ready.emit(self.generation, processed_img)
        except Exception as e:
            logger.exception("PreviewWorker generation %d failed for %s: %s", self.generation, self.image_path, e)
            self.preview_failed.emit(self.generation, str(e))


class BatchProcessWorker(QThread):
    """Processes queued images in background thread with cooperative cancellation."""

    item_progress = Signal(int, int, str, bool, str)  # current, total, filename, success, error_msg
    batch_finished = Signal(list)  # list of ProcessItemResult

    def __init__(self, pipeline: BatchPipeline, files: List[str], output_dir: str, config: ProcessingConfig):
        super().__init__()
        self.pipeline = pipeline
        self.files = files
        self.output_dir = output_dir
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        def on_step(current, total, filename, is_success, error_msg=""):
            self.item_progress.emit(current, total, filename, is_success, error_msg)

        results = self.pipeline.process_batch(
            self.files,
            self.output_dir,
            config=self.config,
            progress_callback=on_step,
            cancel_check=lambda: self._is_cancelled,
        )
        self.batch_finished.emit(results)



class MainWindow(QMainWindow):
    """Primary application window for Reelsator."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reelsator — Instagram AI Photo Studio & Anti-Detection (Windows 11)")
        self.resize(1260, 840)
        self.setMinimumSize(1020, 680)

        self.setStyleSheet(DARK_THEME_QSS)

        self.optimizer = InstaOptimizer()
        self.pipeline = BatchPipeline(self.optimizer)

        self._active_files: List[str] = []
        self._current_preview_file: Optional[str] = None
        self._preview_generation: int = 0
        self._current_preview_worker: Optional[PreviewWorker] = None
        self._pending_preview: bool = False
        self._batch_worker: Optional[BatchProcessWorker] = None

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(200)
        self._preview_timer.timeout.connect(self._run_preview_worker)

        self._init_ui()



    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(14)

        # 1. Top Header Bar
        root_layout.addLayout(self._create_header())

        # 2. Main Content (Splitter: Left Preview/DropZone + Right Settings)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        # Left Container (Preview / DropZone + Batch List)
        left_container = QWidget(self)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(12)

        # Interactive Comparison / Preview Card
        self.preview_card = QFrame(self)
        self.preview_card.setObjectName("previewCard")
        preview_card_layout = QVBoxLayout(self.preview_card)
        preview_card_layout.setContentsMargins(8, 8, 8, 8)

        self.drop_zone = DropZoneWidget(self)
        self.drop_zone.files_selected.connect(self._on_files_added)

        self.comparison_slider = ComparisonSliderWidget(self)
        self.comparison_slider.setVisible(False)

        preview_card_layout.addWidget(self.drop_zone)
        preview_card_layout.addWidget(self.comparison_slider)
        left_layout.addWidget(self.preview_card, stretch=5)

        # Bottom Batch Queue List
        self.batch_list = BatchListWidget(self)
        self.batch_list.file_selected.connect(self._on_queue_item_selected)
        self.batch_list.clear_requested.connect(self._on_clear_queue)
        left_layout.addWidget(self.batch_list, stretch=2)

        splitter.addWidget(left_container)

        # Right Container (Settings Sidebar + CTA)
        right_container = QWidget(self)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(12)

        self.settings_panel = SettingsPanelWidget(self)
        self.settings_panel.config_changed.connect(self._on_config_changed)
        right_layout.addWidget(self.settings_panel, stretch=1)

        # CTA Actions Section
        action_card = QFrame(self)
        action_card.setObjectName("cardPanel")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(14, 14, 14, 14)
        action_layout.setSpacing(10)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Перетащите фото из ChatGPT для начала", self)
        self.lbl_status.setStyleSheet("font-size: 12px; color: #9ca3af;")
        action_layout.addWidget(self.lbl_status)

        self.btn_process = QPushButton("⚡ Подготовить для Instagram", self)
        self.btn_process.setObjectName("primaryButton")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self._start_batch_processing)
        action_layout.addWidget(self.btn_process)

        self.btn_cancel = QPushButton("⛔ Отменить обработку", self)
        self.btn_cancel.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_batch_processing)
        action_layout.addWidget(self.btn_cancel)

        self.btn_open_folder = QPushButton("📂 Открыть папку с готовыми фото", self)
        self.btn_open_folder.setVisible(False)
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        action_layout.addWidget(self.btn_open_folder)


        right_layout.addWidget(action_card)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        root_layout.addWidget(splitter)

    def _create_header(self) -> QHBoxLayout:
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("REELSATOR", self)
        title.setObjectName("titleLabel")

        subtitle = QLabel("Instagram AI Photo Preparation & Anti-Detection Studio", self)
        subtitle.setObjectName("subtitleLabel")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        hdr.addLayout(title_box)

        hdr.addStretch()

        # Badges
        badge_c2pa = QLabel("C2PA STRIPPER: АКТИВЕН", self)
        badge_c2pa.setObjectName("badgeOk")
        hdr.addWidget(badge_c2pa)

        badge_exif = QLabel("IPHONE 15/16 PRO EXIF: ГОТОВ", self)
        badge_exif.setObjectName("badgeOk")
        hdr.addWidget(badge_exif)

        btn_github = QPushButton("GitHub Репозиторий", self)
        btn_github.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        btn_github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/csezet/reelsator")))
        hdr.addWidget(btn_github)

        return hdr

    def _on_files_added(self, file_paths: List[str]):
        """Triggered when files are dropped or selected."""
        # Merge unique files
        existing = set(self._active_files)
        new_files = [p for p in file_paths if p not in existing]
        self._active_files.extend(new_files)

        if not self._active_files:
            return

        self.batch_list.set_files(self._active_files)

        # Set default output dir in the folder of first image
        first_dir = os.path.dirname(self._active_files[0])
        default_out = os.path.join(first_dir, "_ready_for_instagram")
        self.settings_panel.set_output_dir(default_out)

        # Show comparison view
        self.drop_zone.setVisible(False)
        self.comparison_slider.setVisible(True)

        self.btn_process.setEnabled(True)
        self.lbl_status.setText(f"Загружено файлов: {len(self._active_files)}. Готовы к обработке.")

        # Load first image for interactive comparison preview
        self._load_preview(self._active_files[0])

    def _on_queue_item_selected(self, file_path: str):
        """User clicked a row in batch table to inspect."""
        self._load_preview(file_path)

    def _on_clear_queue(self):
        self._active_files.clear()
        self._current_preview_file = None
        self.comparison_slider.setVisible(False)
        self.drop_zone.setVisible(True)
        self.btn_process.setEnabled(False)
        self.btn_open_folder.setVisible(False)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("Перетащите фото из ChatGPT для начала")

    def _load_preview(self, file_path: str):
        if not os.path.exists(file_path):
            return

        self._current_preview_file = file_path
        try:
            with Image.open(file_path) as img:
                self.comparison_slider.set_images(img.copy())
            self._trigger_preview_update()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка чтения", f"Не удалось открыть файл:\n{e}")

    def _on_config_changed(self, cfg: ProcessingConfig):
        """Settings or preset changed: update live preview."""
        if self._current_preview_file:
            self._trigger_preview_update()

    def _trigger_preview_update(self):
        if not self._current_preview_file:
            return
        # Debounce slider changes (200 ms)
        self._preview_timer.start()

    def _run_preview_worker(self):
        if not self._current_preview_file:
            return

        # If previous worker is currently running, schedule next execution upon completion
        if self._current_preview_worker and self._current_preview_worker.isRunning():
            self._pending_preview = True
            return

        self._pending_preview = False
        self._preview_generation += 1
        gen = self._preview_generation
        cfg = self.settings_panel.get_current_config()

        worker = PreviewWorker(self.optimizer, self._current_preview_file, cfg, gen)
        self._current_preview_worker = worker
        worker.preview_ready.connect(self._on_preview_ready)
        worker.preview_failed.connect(self._on_preview_failed)
        worker.finished.connect(lambda w=worker: self._cleanup_preview_worker(w))
        worker.start()

    def _cleanup_preview_worker(self, worker: PreviewWorker):
        if self._current_preview_worker is worker:
            self._current_preview_worker = None
        worker.deleteLater()

        # If a newer configuration arrived while worker was executing, run it now
        if self._pending_preview and self._current_preview_file:
            self._pending_preview = False
            self._run_preview_worker()

    @Slot(int, object)
    def _on_preview_ready(self, generation: int, processed_img):
        if generation == self._preview_generation:
            self.comparison_slider.set_after_image(processed_img)

    @Slot(int, str)
    def _on_preview_failed(self, generation: int, error_msg: str):
        if generation == self._preview_generation:
            self.lbl_status.setText(f"Ошибка предпросмотра: {error_msg}")

    def _start_batch_processing(self):
        if not self._active_files:
            return

        out_dir = self.settings_panel.get_output_dir()
        if not out_dir:
            QMessageBox.warning(self, "Ошибка", "Укажите папку сохранения.")
            return

        self.btn_process.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)
        self.btn_open_folder.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self._active_files))
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Обработка изображений...")

        cfg = self.settings_panel.get_current_config()
        self._batch_worker = BatchProcessWorker(self.pipeline, self._active_files, out_dir, cfg)
        self._batch_worker.item_progress.connect(self._on_batch_item_progress)
        self._batch_worker.batch_finished.connect(self._on_batch_finished)
        self._batch_worker.start()

    def _cancel_batch_processing(self):
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.cancel()
            self.lbl_status.setText("Отмена обработки... Завершение текущего файла.")
            self.btn_cancel.setEnabled(False)

    @Slot(int, int, str, bool, str)
    def _on_batch_item_progress(self, current: int, total: int, filename: str, success: bool, error: str):
        self.progress_bar.setValue(current)
        if success:
            self.lbl_status.setText(f"Обработано {current} из {total}: {filename}")
        else:
            self.lbl_status.setText(f"Статус {filename}: {error}")
        self.batch_list.update_item_status(current - 1, success, error)

    @Slot(list)
    def _on_batch_finished(self, results: List[ProcessItemResult]):
        self.btn_process.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_open_folder.setVisible(True)

        success_count = sum(1 for r in results if r.success)
        cancelled_count = sum(1 for r in results if r.error_message == "Отменено пользователем")
        failed_count = len(results) - success_count - cancelled_count

        if cancelled_count > 0:
            status_text = f"🛑 Отменено: успешно {success_count} из {len(results)} ({cancelled_count} отменено)."
            self.lbl_status.setText(status_text)
            QMessageBox.information(
                self,
                "Обработка прервана",
                f"Обработка очереди была отменена пользователем.\n\n"
                f"Успешно обработано: {success_count} из {len(results)}\n"
                f"Отменено: {cancelled_count}\n"
                f"Ошибок: {failed_count}\n\n"
                f"Папка сохранения:\n{self.settings_panel.get_output_dir()}",
            )
        else:
            status_text = f"🎉 Готово! Успешно: {success_count} из {len(results)} фото."
            if failed_count > 0:
                status_text += f" (Ошибок: {failed_count})"
            self.lbl_status.setText(status_text)
            QMessageBox.information(
                self,
                "Обработка завершена",
                f"Успешно обработано: {success_count} из {len(results)} файлов.\n"
                f"Ошибок: {failed_count}\n\n"
                f"Папка сохранения:\n{self.settings_panel.get_output_dir()}",
            )



    def _open_output_folder(self):
        folder = self.settings_panel.get_output_dir()
        if os.path.exists(folder):
            if os.name == "nt":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])
        else:
            QMessageBox.warning(self, "Папка не найдена", f"Папка не существует:\n{folder}")
