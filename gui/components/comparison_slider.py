"""Interactive Before / After Split-Screen Comparison Widget."""

from typing import Optional
from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QMouseEvent, QPainterPath
from PIL import Image
import numpy as np


class ComparisonSliderWidget(QWidget):
    """Interactive split-view comparison widget with draggable divider."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 380)
        self.setMouseTracking(True)

        self._pixmap_before: Optional[QPixmap] = None
        self._pixmap_after: Optional[QPixmap] = None
        self._split_ratio: float = 0.5  # 0.0 to 1.0 (divider position)
        self._is_dragging: bool = False

        self._badge_before_text = "Оригинал (ChatGPT)"
        self._badge_after_text = "Instagram Ready (4:5)"

    def set_images(self, before_img: Image.Image, after_img: Optional[Image.Image] = None):
        """Sets PIL images for before and after display."""
        self._pixmap_before = self._pil_to_pixmap(before_img)
        self._pixmap_after = self._pil_to_pixmap(after_img) if after_img else None
        self.update()

    def set_after_image(self, after_img: Image.Image):
        """Updates only the processed (after) image."""
        self._pixmap_after = self._pil_to_pixmap(after_img)
        self.update()

    @staticmethod
    def _pil_to_pixmap(pil_img: Image.Image) -> QPixmap:
        """Converts PIL Image to QPixmap efficiently."""
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        im_data = pil_img.tobytes("raw", "RGB")
        from PySide6.QtGui import QImage
        qimg = QImage(im_data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()

        # Fill background
        painter.fillRect(0, 0, w, h, QColor("#121316"))

        if not self._pixmap_before:
            # Placeholder text
            painter.setPen(QColor("#6b7280"))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "Нет активного предпросмотра")
            return

        # Target rectangle maintaining aspect ratio
        target_rect = self._compute_fitted_rect(self._pixmap_before.size(), w, h)

        if not self._pixmap_after:
            # Single preview (before only)
            painter.drawPixmap(target_rect, self._pixmap_before)
            self._draw_badge(painter, target_rect.left() + 16, target_rect.top() + 16, "Оригинал (ChatGPT ИИ)", "#3b1e1e", "#f87171")
            return

        # Both before and after are present: render split view
        split_x = int(target_rect.left() + target_rect.width() * self._split_ratio)

        # 1. Draw "After" (Instagram Ready) on full target rect
        painter.drawPixmap(target_rect, self._pixmap_after)

        # 2. Draw "Before" (Original) clipped to left of split line
        clip_left_rect = QRect(target_rect.left(), target_rect.top(), split_x - target_rect.left(), target_rect.height())
        painter.save()
        painter.setClipRect(clip_left_rect)
        painter.drawPixmap(target_rect, self._pixmap_before)
        painter.restore()

        # 3. Draw Divider Line
        divider_pen = QPen(QColor("#ffffff"), 2)
        painter.setPen(divider_pen)
        painter.drawLine(split_x, target_rect.top(), split_x, target_rect.bottom())

        # 4. Draw Center Drag Handle
        handle_y = target_rect.top() + target_rect.height() // 2
        painter.setBrush(QColor("#6366f1"))
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawEllipse(QPoint(split_x, handle_y), 14, 14)

        # Handle arrow glyphs (< >)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(QRect(split_x - 12, handle_y - 12, 24, 24), Qt.AlignCenter, "◀ ▶")

        # 5. Draw Info Badges
        self._draw_badge(painter, target_rect.left() + 14, target_rect.top() + 14, "До (ChatGPT ИИ)", "#2d1b1b", "#fca5a5")
        self._draw_badge(painter, target_rect.right() - 170, target_rect.top() + 14, "После (Instagram Ready)", "#142c23", "#6ee7b7")

    def _draw_badge(self, painter: QPainter, x: int, y: int, text: str, bg_color: str, text_color: str):
        painter.save()
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        font_metrics = painter.fontMetrics()
        text_w = font_metrics.horizontalAdvance(text)
        badge_w = text_w + 16
        badge_h = 24

        badge_rect = QRect(x, y, badge_w, badge_h)
        path = QPainterPath()
        path.addRoundedRect(badge_rect, 6, 6)
        painter.fillPath(path, QColor(bg_color))
        painter.setPen(QColor(text_color))
        painter.drawText(badge_rect, Qt.AlignCenter, text)
        painter.restore()

    def _compute_fitted_rect(self, img_size: QSize, container_w: int, container_h: int) -> QRect:
        img_w, img_h = img_size.width(), img_size.height()
        if img_w == 0 or img_h == 0:
            return QRect(0, 0, container_w, container_h)

        ratio = min(container_w / img_w, container_h / img_h)
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)
        x = (container_w - new_w) // 2
        y = (container_h - new_h) // 2
        return QRect(x, y, new_w, new_h)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._pixmap_after:
            self._is_dragging = True
            self._update_split_from_mouse(event.pos().x())

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging:
            self._update_split_from_mouse(event.pos().x())
        else:
            # Change cursor to horizontal resize when near divider
            w = self.width()
            split_x = int(w * self._split_ratio)
            if abs(event.pos().x() - split_x) < 15 and self._pixmap_after:
                self.setCursor(Qt.SplitHCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False

    def _update_split_from_mouse(self, mouse_x: int):
        target_rect = self._compute_fitted_rect(self._pixmap_before.size(), self.width(), self.height())
        if target_rect.width() > 0:
            rel_x = mouse_x - target_rect.left()
            self._split_ratio = max(0.02, min(0.98, rel_x / target_rect.width()))
            self.update()
