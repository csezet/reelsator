"""Batch File Queue List and Status Table Widget."""

import os
from typing import List, Dict, Optional
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


class BatchListWidget(QFrame):
    """Displays queued images, status badges, and processing stats."""

    file_selected = Signal(str)  # Emitted when user clicks a row in the table
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardPanel")
        self.setMinimumHeight(140)
        self.setMaximumHeight(220)

        self._file_paths: List[str] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Header row
        hdr = QHBoxLayout()
        self.lbl_title = QLabel("ОЧЕРЕДЬ ОБРАБОТКИ (0)", self)
        self.lbl_title.setObjectName("sectionHeader")

        self.btn_clear = QPushButton("Очистить", self)
        self.btn_clear.setFixedHeight(26)
        self.btn_clear.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.btn_clear.clicked.connect(self._on_clear)

        hdr.addWidget(self.lbl_title)
        hdr.addStretch()
        hdr.addWidget(self.btn_clear)
        layout.addLayout(hdr)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Файл", "Размер", "Статус", "Путь"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1b22;
                border: 1px solid #2b2d38;
                border-radius: 8px;
                color: #e5e7eb;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #22242f;
            }
            QTableWidget::item:selected {
                background-color: #3730a3;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #21232d;
                color: #9ca3af;
                font-weight: 600;
                font-size: 11px;
                border: none;
                padding: 6px;
            }
        """)
        self.table.itemClicked.connect(self._on_row_clicked)
        layout.addWidget(self.table)

    def set_files(self, paths: List[str]):
        self._file_paths = paths
        self.table.setRowCount(len(paths))
        self.lbl_title.setText(f"ОЧЕРЕДЬ ОБРАБОТКИ ({len(paths)})")

        for row, p in enumerate(paths):
            name = os.path.basename(p)
            size_mb = f"{os.path.getsize(p) / (1024 * 1024):.1f} MB" if os.path.exists(p) else "0 MB"

            item_name = QTableWidgetItem(name)
            item_size = QTableWidgetItem(size_mb)
            item_status = QTableWidgetItem("⏳ В очереди")
            item_status.setForeground(QColor("#9ca3af"))
            item_path = QTableWidgetItem(p)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_size)
            self.table.setItem(row, 2, item_status)
            self.table.setItem(row, 3, item_path)

        if paths:
            self.table.selectRow(0)

    def update_item_status(self, index: int, is_success: bool, error_msg: Optional[str] = None):
        if 0 <= index < self.table.rowCount():
            status_item = self.table.item(index, 2)
            if status_item:
                if is_success:
                    status_item.setText("✅ Готово (Instagram Ready)")
                    status_item.setForeground(QColor("#34d399"))
                else:
                    status_item.setText(f"❌ Ошибка: {error_msg or 'Сбой'}")
                    status_item.setForeground(QColor("#f87171"))

    def mark_in_progress(self, index: int):
        if 0 <= index < self.table.rowCount():
            status_item = self.table.item(index, 2)
            if status_item:
                status_item.setText("⚙️ Обработка...")
                status_item.setForeground(QColor("#818cf8"))

    def _on_row_clicked(self, item: QTableWidgetItem):
        row = item.row()
        if 0 <= row < len(self._file_paths):
            self.file_selected.emit(self._file_paths[row])

    def _on_clear(self):
        self._file_paths.clear()
        self.table.setRowCount(0)
        self.lbl_title.setText("ОЧЕРЕДЬ ОБРАБОТКИ (0)")
        self.clear_requested.emit()

    def get_file_paths(self) -> List[str]:
        return self._file_paths
