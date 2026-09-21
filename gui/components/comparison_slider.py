"""Interactive Before / After Split-Screen Comparison Widget."""

import math
from typing import Optional, Tuple
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QMouseEvent, QPainterPath
from PIL import Image


def format_aspect_ratio(w: int, h: int) -> str:
    """Returns human-readable aspect ratio string (e.g. 1:1, 4:5, 9:16)."""
    if w <= 0 or h <= 0:
        return ""
    ratio = w / h
    if abs(ratio - 1.0) < 0.02:
        return "1:1"
    elif abs(ratio - 4 / 5) < 0.02:
        return "4:5"
    elif abs(ratio - 5 / 4) < 0.02:
        return "5:4"
    elif abs(ratio - 9 / 16) < 0.02:
        return "9:16"
    elif abs(ratio - 16 / 9) < 0.02:
        return "16:9"

    gcd = math.gcd(w, h)
    rw, rh = w // gcd, h // gcd
    if rw < 20 and rh < 20:
        return f"{rw}:{rh}"
    return f"{ratio:.2f}:1"


def compute_fitted_rect(img_size: QSize, container_w: int, container_h: int) -> QRect:
    """Computes a centered QRect fitting img_size into container dimensions preserving aspect ratio."""
    img_w, img_h = img_size.width(), img_size.height()
    if img_w <= 0 or img_h <= 0 or container_w <= 0 or container_h <= 0:
        return QRect(0, 0, max(0, container_w), max(0, container_h))

    ratio = min(container_w / img_w, container_h / img_h)
    new_w = int(img_w * ratio)
    new_h = int(img_h * ratio)
    x = (container_w - new_w) // 2
    y = (container_h - new_h) // 2
    return QRect(x, y, new_w, new_h)


def compute_slider_geometry(
    before_size: QSize,
    after_size: Optional[QSize],
    container_w: int,
    container_h: int,
    split_ratio: float = 0.5,
) -> Tuple[QRect, Optional[QRect], QRect, int]:
    """Computes pure layout geometry for split comparison viewer.

    Returns:
        (rect_before, rect_after, union_rect, split_x)
    """
    rect_before = compute_fitted_rect(before_size, container_w, container_h)
    if after_size is not None and not after_size.isEmpty():
        rect_after = compute_fitted_rect(after_size, container_w, container_h)
        union_rect = rect_before.united(rect_after)
    else:
        rect_after = None
        union_rect = rect_before

    clamped_ratio = max(0.02, min(0.98, split_ratio))
    split_x = int(union_rect.left() + union_rect.width() * clamped_ratio)
    return rect_before, rect_after, union_rect, split_x


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

    def _compute_fitted_rect(self, img_size: QSize, container_w: int, container_h: int) -> QRect:
        """Instance helper preserving API compatibility."""
        return compute_fitted_rect(img_size, container_w, container_h)

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

        after_size = self._pixmap_after.size() if self._pixmap_after else None
        rect_before, rect_after, union_rect, split_x = compute_slider_geometry(
            self._pixmap_before.size(),
            after_size,
            w,
            h,
            self._split_ratio,
        )

        bw, bh = self._pixmap_before.width(), self._pixmap_before.height()
        ar_before = format_aspect_ratio(bw, bh)
        badge_before = f"До: {bw}×{bh} ({ar_before})"

        if not self._pixmap_after or rect_after is None:
            # Single preview (before only)
            painter.drawPixmap(rect_before, self._pixmap_before)
            self._draw_badge(painter, rect_before.left() + 14, rect_before.top() + 14, badge_before, "#2d1b1b", "#fca5a5")
            return

        aw, ah = self._pixmap_after.width(), self._pixmap_after.height()
        ar_after = format_aspect_ratio(aw, ah)
        badge_after = f"После: {aw}×{ah} ({ar_after})"

        # Draw subtle framing indicator if aspect ratios differ
        if rect_before != rect_after:
            framing_pen = QPen(QColor(255, 255, 255, 30), 1, Qt.DashLine)
            painter.setPen(framing_pen)
            painter.drawRect(rect_after)

        # 1. Draw "After" (Instagram Ready) clipped to the right of divider
        painter.save()
        clip_right = QRect(split_x, 0, w - split_x, h)
        painter.setClipRect(clip_right)
        painter.drawPixmap(rect_after, self._pixmap_after)
        painter.restore()

        # 2. Draw "Before" (Original) clipped to the left of divider
        painter.save()
        clip_left = QRect(0, 0, split_x, h)
        painter.setClipRect(clip_left)
        painter.drawPixmap(rect_before, self._pixmap_before)
        painter.restore()

        # 3. Draw Divider Line across union height
        divider_pen = QPen(QColor("#ffffff"), 2)
        painter.setPen(divider_pen)
        painter.drawLine(split_x, union_rect.top(), split_x, union_rect.bottom())

        # 4. Draw Center Drag Handle
        handle_y = union_rect.top() + union_rect.height() // 2
        painter.setBrush(QColor("#6366f1"))
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawEllipse(QPoint(split_x, handle_y), 14, 14)

        # Handle arrow glyphs (< >)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(QRect(split_x - 12, handle_y - 12, 24, 24), Qt.AlignCenter, "◀ ▶")

        # 5. Draw Info Badges with dimensions & aspect ratios
        self._draw_badge(painter, rect_before.left() + 14, rect_before.top() + 14, badge_before, "#2d1b1b", "#fca5a5")
        self._draw_badge(painter, rect_after.right() - 14, rect_after.top() + 14, badge_after, "#142c23", "#6ee7b7", align_right=True)

    def _draw_badge(self, painter: QPainter, x: int, y: int, text: str, bg_color: str, text_color: str, align_right: bool = False):
        painter.save()
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        font_metrics = painter.fontMetrics()
        text_w = font_metrics.horizontalAdvance(text)
        badge_w = text_w + 16
        badge_h = 24

        actual_x = x - badge_w if align_right else x
        badge_rect = QRect(actual_x, y, badge_w, badge_h)
        path = QPainterPath()
        path.addRoundedRect(badge_rect, 6, 6)
        painter.fillPath(path, QColor(bg_color))
        painter.setPen(QColor(text_color))
        painter.drawText(badge_rect, Qt.AlignCenter, text)
        painter.restore()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._pixmap_after:
            self._is_dragging = True
            self._update_split_from_mouse(event.pos().x())

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging:
            self._update_split_from_mouse(event.pos().x())
        else:
            if self._pixmap_after and self._pixmap_before:
                _, _, union_rect, split_x = compute_slider_geometry(
                    self._pixmap_before.size(),
                    self._pixmap_after.size(),
                    self.width(),
                    self.height(),
                    self._split_ratio,
                )
                if abs(event.pos().x() - split_x) < 15:
                    self.setCursor(Qt.SplitHCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False

    def _update_split_from_mouse(self, mouse_x: int):
        if not self._pixmap_before:
            return
        after_size = self._pixmap_after.size() if self._pixmap_after else None
        _, _, union_rect, _ = compute_slider_geometry(
            self._pixmap_before.size(),
            after_size,
            self.width(),
            self.height(),
            self._split_ratio,
        )

        if union_rect.width() > 0:
            rel_x = mouse_x - union_rect.left()
            self._split_ratio = max(0.02, min(0.98, rel_x / union_rect.width()))
            self.update()
