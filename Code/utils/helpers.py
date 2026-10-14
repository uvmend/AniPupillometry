"""
Utility helper functions, styles, and geometry calculations for the Bat Pupil Tracking Application.
"""
from typing import Tuple, Optional
import os

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #12131a;
    color: #f1f5f9;
}
QWidget {
    background-color: #12131a;
    color: #e2e8f0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
    font-size: 12px;
}
QGroupBox {
    border: 1px solid #2e3245;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 14px;
    padding-bottom: 8px;
    padding-left: 8px;
    padding-right: 8px;
    background-color: #181a24;
    font-weight: 600;
    color: #93c5fd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    background-color: #181a24;
}
QPushButton {
    background-color: #242738;
    border: 1px solid #3a3f58;
    border-radius: 5px;
    padding: 4px 8px;
    color: #f1f5f9;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #30344a;
    border-color: #60a5fa;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #1b1d2a;
    border-color: #2563eb;
}
QPushButton:disabled {
    background-color: #151620;
    color: #555b72;
    border-color: #232533;
}
QPushButton#primaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background-color: #3b82f6;
    border-color: #60a5fa;
}
QPushButton#primaryButton:pressed {
    background-color: #1d4ed8;
}
QPushButton#stopButton {
    background-color: #b91c1c;
    border-color: #991b1b;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#stopButton:hover {
    background-color: #dc2626;
    border-color: #ef4444;
}
QPushButton#stopButton:pressed {
    background-color: #991b1b;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #252839;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #2563eb;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #f8fafc;
    border: 2px solid #2563eb;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #ffffff;
    border-color: #60a5fa;
}
QSlider::groove:vertical {
    width: 6px;
    background: #252839;
    border-radius: 3px;
}
QSlider::sub-page:vertical {
    background: #2563eb;
    border-radius: 3px;
}
QSlider::handle:vertical {
    background: #f8fafc;
    border: 2px solid #2563eb;
    height: 14px;
    margin-left: -5px;
    margin-right: -5px;
    border-radius: 7px;
}
QSlider::handle:vertical:hover {
    background: #ffffff;
    border-color: #60a5fa;
}
QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #202331;
    border: 1px solid #363b52;
    border-radius: 4px;
    padding: 3px 6px;
    color: #f8fafc;
    selection-background-color: #2563eb;
}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: #60a5fa;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 16px;
    border-left: 1px solid #363b52;
    border-bottom: 1px solid #363b52;
    background-color: #272b3c;
    border-top-right-radius: 4px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: #383e57;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='8' height='4' viewBox='0 0 8 4'><polygon points='0,4 8,4 4,0' fill='%2394a3b8'/></svg>");
    width: 8px;
    height: 4px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 16px;
    border-left: 1px solid #363b52;
    background-color: #272b3c;
    border-bottom-right-radius: 4px;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #383e57;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='8' height='4' viewBox='0 0 8 4'><polygon points='0,0 8,0 4,4' fill='%2394a3b8'/></svg>");
    width: 8px;
    height: 4px;
}
QComboBox {
    background-color: #202331;
    border: 1px solid #363b52;
    border-radius: 4px;
    padding: 4px 8px;
    color: #f8fafc;
}
QComboBox:focus, QComboBox:hover {
    border-color: #60a5fa;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left-width: 0px;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}
QComboBox::down-arrow {
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='0,0 10,0 5,6' fill='%2394a3b8'/></svg>");
    width: 10px;
    height: 6px;
    margin-right: 6px;
}
QComboBox::down-arrow:hover {
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><polygon points='0,0 10,0 5,6' fill='%2360a5fa'/></svg>");
}
QComboBox QAbstractItemView {
    background-color: #191b26;
    color: #f1f5f9;
    border: 1px solid #363b52;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 3px 8px;
    border-radius: 3px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #282c3f;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
QCheckBox {
    spacing: 8px;
    color: #e2e8f0;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    background-color: #202331;
    border: 1px solid #3d435d;
    border-radius: 3px;
}
QCheckBox::indicator:hover {
    border-color: #60a5fa;
    background-color: #272b3c;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #3b82f6;
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'><polyline points='2,6 5,9 10,3' stroke='white' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
}
QScrollBar:vertical {
    background: #12131a;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #2b2f42;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #3e445e;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #12131a;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #2b2f42;
    min-width: 24px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #3e445e;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QDockWidget {
    color: #f1f5f9;
    font-weight: 600;
}
QDockWidget::title {
    background: #181a24;
    padding: 7px 10px;
    border-bottom: 1px solid #2e3245;
    color: #93c5fd;
    font-size: 12px;
}
QStatusBar {
    background: #0f1016;
    color: #94a3b8;
    border-top: 1px solid #222533;
    padding: 2px 6px;
}
QMenuBar {
    background: #0f1016;
    color: #e2e8f0;
    border-bottom: 1px solid #222533;
    padding: 2px 4px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
    background: transparent;
}
QMenuBar::item:selected {
    background: #242738;
    color: #ffffff;
}
QMenu {
    background: #181a24;
    color: #f1f5f9;
    border: 1px solid #2e3245;
    padding: 4px;
    border-radius: 6px;
}
QMenu::item {
    padding: 6px 20px 6px 10px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #2563eb;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #282b3b;
    margin: 4px 6px;
}
QProgressBar {
    border: 1px solid #2e3245;
    border-radius: 4px;
    text-align: center;
    background-color: #181a24;
    color: #ffffff;
    font-weight: 600;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 3px;
}
QToolTip {
    background-color: #141620;
    color: #f8fafc;
    border: 1px solid #3d435d;
    padding: 6px 10px;
    border-radius: 5px;
    font-size: 11px;
}
"""

def format_timestamp(ms: int) -> str:
    """Format milliseconds into HH:MM:SS.mmm string."""
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    millis = ms % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

def frame_to_timestamp(frame_idx: int, fps: float) -> str:
    """Convert frame number to formatted timestamp string."""
    if fps <= 0:
        return "00:00:00.000"
    ms = int((frame_idx / fps) * 1000.0)
    return format_timestamp(ms)

def timestamp_to_frame(ms: int, fps: float) -> int:
    """Convert millisecond timestamp to closest frame index."""
    if fps <= 0:
        return 0
    return max(0, int(round((ms / 1000.0) * fps)))

def clamp_roi(
    x: int, y: int, w: int, h: int,
    max_w: int, max_h: int, min_size: int = 10
) -> Tuple[int, int, int, int]:
    """
    Ensure ROI coordinates lie completely within image dimensions [max_w, max_h]
    and satisfy minimum size constraints.
    """
    x = max(0, min(x, max_w - min_size))
    y = max(0, min(y, max_h - min_size))
    w = max(min_size, min(w, max_w - x))
    h = max(min_size, min(h, max_h - y))
    return int(x), int(y), int(w), int(h)
