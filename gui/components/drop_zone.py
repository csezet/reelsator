"""Drag-and-Drop Image Input Widget with Windows 11 aesthetics."""

import os
from typing import List
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QFileDialog
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


class DropZoneWidget(QFrame):
    """Interactive drag and drop zone for single or batch images."""

    files_selected = Signal(list)  # Emits list of file paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(240)

        self._is_drag_over = False
        self._init_ui()
        self._update_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self.icon_label = QLabel("📥", self)
        self.icon_label.setStyleSheet("font-size: 42px; background: transparent;")
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("Перетащите фото из ChatGPT сюда", self)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #f3f4f6; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.sub_label = QLabel("или нажмите в любом месте для выбора файлов\nПоддерживает JPG, PNG, WEBP • Пакетная загрузка", self)
        self.sub_label.setStyleSheet("font-size: 12px; color: #9ca3af; background: transparent;")
        self.sub_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.sub_label)

    def _update_style(self):
        if self._is_drag_over:
            self.setStyleSheet("""
                QFrame#dropZone {
                    background-color: #242636;
                    border: 2px dashed #6366f1;
                    border-radius: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#dropZone {
                    background-color: #1a1b22;
                    border: 2px dashed #323544;
                    border-radius: 12px;
                }
                QFrame#dropZone:hover {
                    background-color: #1f202a;
                    border-color: #4f46e5;
                }
            """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._is_drag_over = True
            self._update_style()

    def dragLeaveEvent(self, event):
        self._is_drag_over = False
        self._update_style()

    def dropEvent(self, event: QDropEvent):
        self._is_drag_over = False
        self._update_style()

        urls = event.mimeData().urls()
        valid_files = []

        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path):
                if os.path.splitext(path)[1].lower() in SUPPORTED_EXTS:
                    valid_files.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS:
                            valid_files.append(os.path.join(root, f))

        if valid_files:
            self.files_selected.emit(sorted(list(set(valid_files))))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Выберите фотографии для подготовки к Instagram",
                "",
                "Изображения (*.jpg *.jpeg *.png *.webp *.bmp *.tiff);;Все файлы (*.*)",
            )
            if files:
                self.files_selected.emit(files)
