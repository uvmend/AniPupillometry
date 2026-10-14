"""
Interactive video viewport widget.
Handles video frame rendering, aspect-ratio scaling, interactive ROI cropping for bat head,
zoom-in view mode, and tracking overlay rendering.
"""
from typing import Optional, Tuple, Dict, Any
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, Signal, Slot
from PySide6.QtGui import (
    QPainter, QImage, QPen, QColor, QBrush, QFont, QPainterPath,
    QMouseEvent, QPaintEvent
)
import numpy as np
import cv2

from Code.utils.helpers import clamp_roi, frame_to_timestamp
from Code.core.video_processor import VideoProcessor
from Code.tracking.pupil_detector import TrackingResult

class VideoPlayerWidget(QWidget):
    """
    Renders the current video frame with interactive ROI selection,
    aspect ratio preservation, zoom cropping, and computer vision overlays.
    """

    roi_changed = Signal(tuple)          # (x, y, w, h) in original frame coords
    roi_cleared = Signal()
    seek_relative_requested = Signal(float) # seconds

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #0d0e14;")

        # Active frames
        self.current_qimage: Optional[QImage] = None
        self.current_frame_np: Optional[np.ndarray] = None
        self.frame_idx: int = 0
        self.fps: float = 30.0
        self.total_frames: int = 0
        self.duration_ms: int = 0

        # Bat head crop ROI: (x, y, w, h) in original frame coordinates
        self.crop_roi: Optional[Tuple[int, int, int, int]] = None
        self.is_cropped_view: bool = False

        # Interactive mouse dragging for ROI
        self.is_drawing_roi: bool = False
        self.roi_drag_start: Optional[QPoint] = None
        self.roi_drag_current: Optional[QPoint] = None

        # Display transform parameters (cached on resize/paint)
        self.display_rect: QRect = QRect()
        self.scale_factor: float = 1.0

        # Processing & Tracking overlays
        self.processing_params: Dict[str, Any] = {}
        self.tracking_result: Optional[TrackingResult] = None
        self.show_tracking_overlay: bool = True
        self.ellipse_color: QColor = QColor("#ec4899")  # High-contrast Electric Magenta (default for green IR footage)

    def set_ellipse_color(self, color: str | QColor):
        """Set high-contrast color used for rendering the tracked pupil ellipse."""
        if isinstance(color, str):
            self.ellipse_color = QColor(color)
        else:
            self.ellipse_color = color
        self.update()

    def set_processing_params(self, params: Dict[str, Any]):
        """Update live processing filters (contrast, brightness, CLAHE, etc.)."""
        self.processing_params = params
        self.update()

    def set_tracking_result(self, result: Optional[TrackingResult]):
        """Update tracked pupil ellipse and glint markers to render."""
        self.tracking_result = result
        self.update()

    def set_cropped_view(self, enabled: bool):
        """Toggle zoom/crop mode into the bat head ROI."""
        self.is_cropped_view = enabled
        self.update()

    def set_crop_roi(self, roi: Optional[Tuple[int, int, int, int]]):
        """Set bat head crop ROI manually or from session."""
        self.crop_roi = roi
        self.update()

    def clear_crop_roi(self):
        """Reset crop ROI to full frame."""
        self.crop_roi = None
        self.is_cropped_view = False
        self.roi_cleared.emit()
        self.update()

    @Slot(QImage, int)
    def update_frame(self, image: QImage, frame_idx: int):
        """Receive a new video frame from the media engine."""
        self.current_qimage = image
        self.frame_idx = frame_idx
        self.current_frame_np = None # Lazily convert to numpy when needed
        self.update()

    def get_current_numpy_frame(self) -> Optional[np.ndarray]:
        """Convert current QImage to BGR numpy array for OpenCV processing."""
        if self.current_frame_np is not None:
            return self.current_frame_np
        if self.current_qimage is None or self.current_qimage.isNull():
            return None

        img = self.current_qimage.convertToFormat(QImage.Format.Format_BGR888)
        w, h = img.width(), img.height()
        ptr = img.constBits()
        arr = np.ndarray(shape=(h, w, 3), buffer=ptr, dtype=np.uint8, strides=(img.bytesPerLine(), 3, 1))
        self.current_frame_np = arr.copy()
        return self.current_frame_np

    def set_video_metadata(self, fps: float, total_frames: int, duration_ms: int):
        self.fps = fps
        self.total_frames = total_frames
        self.duration_ms = duration_ms

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not self.is_cropped_view:
            pos = event.position().toPoint()
            if self.display_rect.contains(pos):
                self.is_drawing_roi = True
                self.roi_drag_start = pos
                self.roi_drag_current = pos
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_drawing_roi:
            self.roi_drag_current = event.position().toPoint()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing_roi:
            self.is_drawing_roi = False
            if self.roi_drag_start and self.roi_drag_current:
                # Convert widget coordinates to video frame coordinates
                p1 = self._widget_to_video_coords(self.roi_drag_start)
                p2 = self._widget_to_video_coords(self.roi_drag_current)
                if p1 and p2 and self.current_qimage:
                    x = min(p1[0], p2[0])
                    y = min(p1[1], p2[1])
                    w = abs(p2[0] - p1[0])
                    h = abs(p2[1] - p1[1])
                    if w > 10 and h > 10:
                        clamped = clamp_roi(x, y, w, h, self.current_qimage.width(), self.current_qimage.height())
                        self.crop_roi = clamped
                        self.roi_changed.emit(clamped)
            self.roi_drag_start = None
            self.roi_drag_current = None
            self.update()
        super().mouseReleaseEvent(event)

    def _widget_to_video_coords(self, pt: QPoint) -> Optional[Tuple[int, int]]:
        """Map mouse point within widget to original video pixel coordinate."""
        if not self.display_rect.contains(pt) or self.scale_factor <= 0 or not self.current_qimage:
            return None
        rel_x = pt.x() - self.display_rect.left()
        rel_y = pt.y() - self.display_rect.top()
        vid_x = int(rel_x / self.scale_factor)
        vid_y = int(rel_y / self.scale_factor)
        return (vid_x, vid_y)

    def _video_to_widget_rect(self, x: int, y: int, w: int, h: int) -> QRect:
        """Map video pixel rect to screen display rect."""
        wx = int(self.display_rect.left() + x * self.scale_factor)
        wy = int(self.display_rect.top() + y * self.scale_factor)
        ww = int(w * self.scale_factor)
        wh = int(h * self.scale_factor)
        return QRect(wx, wy, ww, wh)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0d0e14"))

        if self.current_qimage is None or self.current_qimage.isNull():
            # Render polished empty state placeholder
            center_x = self.width() // 2
            center_y = self.height() // 2

            # Bat / Eye Icon Glyph
            painter.setPen(QPen(QColor("#2d3248"), 2))
            painter.setBrush(QBrush(QColor("#151824")))
            painter.drawRoundedRect(center_x - 180, center_y - 80, 360, 160, 10, 10)

            painter.setPen(QColor("#60a5fa"))
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.drawText(
                QRect(center_x - 170, center_y - 65, 340, 30),
                Qt.AlignmentFlag.AlignCenter,
                "🦇 Bat Pupil Tracking System"
            )

            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                QRect(center_x - 170, center_y - 30, 340, 45),
                Qt.AlignmentFlag.AlignCenter,
                "Open a video recording to begin tracking.\n(Use File > Open Video or Datasets menu)"
            )

            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Consolas", 9))
            painter.drawText(
                QRect(center_x - 170, center_y + 25, 340, 25),
                Qt.AlignmentFlag.AlignCenter,
                "Drag mouse to select Bat Head ROI"
            )
            return

        # Prepare image (crop or full, with image processing filters applied)
        frame_np = self.get_current_numpy_frame()
        if frame_np is not None:
            processed_np = VideoProcessor.process_frame(
                frame_np,
                self.processing_params,
                roi=self.crop_roi,
                apply_crop=self.is_cropped_view
            )
            h, w = processed_np.shape[:2]
            rgb = cv2.cvtColor(processed_np, cv2.COLOR_BGR2RGB)
            display_img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        else:
            display_img = self.current_qimage

        # Compute letterboxing / aspect ratio fit
        widget_w = self.width()
        widget_h = self.height()
        img_w = display_img.width()
        img_h = display_img.height()

        if img_w <= 0 or img_h <= 0:
            return

        aspect_img = img_w / img_h
        aspect_widget = widget_w / widget_h

        if aspect_widget > aspect_img:
            # Widget is wider than image: scale to height
            render_h = widget_h
            render_w = int(widget_h * aspect_img)
            offset_x = (widget_w - render_w) // 2
            offset_y = 0
            self.scale_factor = render_h / img_h
        else:
            # Widget is taller than image: scale to width
            render_w = widget_w
            render_h = int(widget_w / aspect_img)
            offset_x = 0
            offset_y = (widget_h - render_h) // 2
            self.scale_factor = render_w / img_w

        self.display_rect = QRect(offset_x, offset_y, render_w, render_h)
        painter.drawImage(self.display_rect, display_img)

        # Draw ROI selection rectangle if not in cropped view
        if not self.is_cropped_view:
            # Draw existing active crop ROI
            if self.crop_roi:
                rx, ry, rw, rh = self.crop_roi
                rect = self._video_to_widget_rect(rx, ry, rw, rh)
                pen = QPen(QColor("#00e5ff"), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(rect)
                
                # Draw dimension tag badge
                tag = f"Bat Head ROI: {rw}x{rh} @ ({rx}, {ry})"
                painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
                fm = painter.fontMetrics()
                tag_w = fm.horizontalAdvance(tag) + 12
                tag_h = 20

                # Ensure tag remains within display bounds
                tag_x = max(rect.left(), self.display_rect.left())
                tag_y = rect.top() - tag_h - 4
                if tag_y < self.display_rect.top() + 40:
                    tag_y = rect.top() + 6

                tag_rect = QRect(tag_x, tag_y, tag_w, tag_h)
                painter.setPen(QColor("#00e5ff"))
                painter.setBrush(QBrush(QColor(15, 23, 42, 220)))
                painter.drawRoundedRect(tag_rect, 4, 4)

                painter.setPen(QColor("#ffffff"))
                painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag)

            # Draw dragging rectangle
            if self.is_drawing_roi and self.roi_drag_start and self.roi_drag_current:
                drag_rect = QRect(self.roi_drag_start, self.roi_drag_current).normalized()
                drag_rect = drag_rect.intersected(self.display_rect)
                pen = QPen(QColor("#facc15"), 2, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(250, 204, 21, 35)))
                painter.drawRect(drag_rect)

        # Draw Pupil Tracking Overlays if enabled
        if self.show_tracking_overlay and self.tracking_result and not self.tracking_result.blink:
            res = self.tracking_result
            if res.pupil_center:
                # If currently in cropped view, adjust coordinates relative to crop origin
                px, py = res.pupil_center
                if self.is_cropped_view and self.crop_roi:
                    px -= self.crop_roi[0]
                    py -= self.crop_roi[1]

                screen_x = float(self.display_rect.left()) + px * self.scale_factor
                screen_y = float(self.display_rect.top()) + py * self.scale_factor

                # Draw pupil center dot
                painter.setPen(QPen(QColor("#ffffff"), 1))
                painter.setBrush(QBrush(self.ellipse_color))
                painter.drawEllipse(QPointF(screen_x, screen_y), 3.0, 3.0)

                # Draw pupil ellipse with sub-pixel floating-point radii
                if res.major_axis > 0 and res.minor_axis > 0:
                    painter.save()
                    painter.translate(QPointF(screen_x, screen_y))
                    painter.rotate(res.angle)
                    painter.setPen(QPen(self.ellipse_color, 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    rad_x = (res.major_axis / 2.0) * self.scale_factor
                    rad_y = (res.minor_axis / 2.0) * self.scale_factor
                    painter.drawEllipse(QPointF(0.0, 0.0), float(rad_x), float(rad_y))
                    painter.restore()

            # Draw corneal reflection glint
            if res.glint_center:
                gx, gy = res.glint_center
                if self.is_cropped_view and self.crop_roi:
                    gx -= self.crop_roi[0]
                    gy -= self.crop_roi[1]
                scr_gx = int(self.display_rect.left() + gx * self.scale_factor)
                scr_gy = int(self.display_rect.top() + gy * self.scale_factor)
                painter.setPen(QPen(QColor("#f43f5e"), 2))
                painter.drawLine(scr_gx - 6, scr_gy, scr_gx + 6, scr_gy)
                painter.drawLine(scr_gx, scr_gy - 6, scr_gx, scr_gy + 6)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPoint(scr_gx, scr_gy), 3, 3)

        # Draw polished HUD info pill banner (top left)
        time_str = frame_to_timestamp(self.frame_idx, self.fps)
        mode_str = "🔍 ZOOM VIEW (Bat Head)" if self.is_cropped_view else "📐 FULL VIEW (Drag to Crop Bat Head)"
        hud_text = f"Frame: {self.frame_idx} / {self.total_frames} ({time_str})  •  {mode_str}"

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        fm = painter.fontMetrics()
        hud_w = fm.horizontalAdvance(hud_text) + 20
        hud_h = 26

        hud_rect = QRect(12, 12, hud_w, hud_h)
        painter.setPen(QColor("#2d3248"))
        painter.setBrush(QBrush(QColor(15, 17, 26, 215)))
        painter.drawRoundedRect(hud_rect, 6, 6)

        painter.setPen(QColor("#38bdf8") if not self.is_cropped_view else QColor("#22d3ee"))
        painter.drawText(hud_rect, Qt.AlignmentFlag.AlignCenter, hud_text)
