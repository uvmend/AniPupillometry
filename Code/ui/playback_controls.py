"""
Playback control bar widget with Play, Pause, Stop, Step, Seek, Speed, and Head Zoom controls.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel,
    QComboBox, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from Code.utils.helpers import format_timestamp

class PlaybackControls(QWidget):
    """
    Control toolbar for video playback navigation, seeking, speed adjustments, and frame stepping.
    """

    play_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    step_frames_requested = Signal(int)       # -1 or +1
    seek_relative_requested = Signal(float)   # seconds (-5.0, +5.0)
    seek_ms_requested = Signal(int)           # absolute millisecond position
    speed_changed = Signal(float)             # playback rate (0.25 to 2.0)
    toggle_crop_view_requested = Signal(bool) # zoom crop toggle
    reset_crop_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.fps: float = 30.0
        self.duration_ms: int = 0
        self.total_frames: int = 0
        self.is_user_scrubbing: bool = False
        self.is_cropped: bool = False

        self._init_ui()

    def _create_vdivider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #2b2f42; margin: 2px 4px;")
        return line

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 2, 4, 4)
        main_layout.setSpacing(4)

        # 1. Timeline seek slider row
        seek_row = QHBoxLayout()
        seek_row.setSpacing(8)

        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setFont(QFont("Consolas", 10))
        self.time_label.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 8px; color: #38bdf8;"
        )
        self.time_label.setToolTip("Current Playback Time / Total Video Duration")

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setToolTip("Seek video position (drag or click)")
        self.seek_slider.sliderPressed.connect(self._on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self._on_slider_released)
        self.seek_slider.sliderMoved.connect(self._on_slider_moved)

        self.frame_label = QLabel("Frame: 0 / 0")
        self.frame_label.setFont(QFont("Consolas", 10))
        self.frame_label.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 8px; color: #94a3b8;"
        )
        self.frame_label.setToolTip("Current Frame Index / Total Frame Count")

        seek_row.addWidget(self.time_label)
        seek_row.addWidget(self.seek_slider, 1)
        seek_row.addWidget(self.frame_label)
        main_layout.addLayout(seek_row)

        # 2. Buttons row: Transport, Stepping, Speed, Head Zoom
        btn_row = QHBoxLayout()
        btn_row.setSpacing(5)

        # Transport Navigation buttons
        self.btn_back_5s = QPushButton("-5s")
        self.btn_back_5s.setFixedWidth(40)
        self.btn_back_5s.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_back_5s.setToolTip("Seek 5 seconds backward (Shift + Left)")
        self.btn_back_5s.clicked.connect(lambda: self.seek_relative_requested.emit(-5.0))

        self.btn_step_back = QPushButton("|◀")
        self.btn_step_back.setFixedWidth(36)
        self.btn_step_back.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_step_back.setToolTip("Step 1 frame backward (Left Arrow)")
        self.btn_step_back.clicked.connect(lambda: self.step_frames_requested.emit(-1))

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("primaryButton")
        self.btn_play.setFixedWidth(42)
        self.btn_play.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_play.setToolTip("Start playback (Space)")
        self.btn_play.clicked.connect(self.play_requested.emit)

        self.btn_pause = QPushButton("⏸")
        self.btn_pause.setFixedWidth(38)
        self.btn_pause.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_pause.setToolTip("Pause playback (Space)")
        self.btn_pause.clicked.connect(self.pause_requested.emit)

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setObjectName("stopButton")
        self.btn_stop.setFixedWidth(38)
        self.btn_stop.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_stop.setToolTip("Stop playback and reset to start")
        self.btn_stop.clicked.connect(self.stop_requested.emit)

        self.btn_step_fwd = QPushButton("▶|")
        self.btn_step_fwd.setFixedWidth(36)
        self.btn_step_fwd.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_step_fwd.setToolTip("Step 1 frame forward (Right Arrow)")
        self.btn_step_fwd.clicked.connect(lambda: self.step_frames_requested.emit(1))

        self.btn_fwd_5s = QPushButton("+5s")
        self.btn_fwd_5s.setFixedWidth(40)
        self.btn_fwd_5s.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_fwd_5s.setToolTip("Seek 5 seconds forward (Shift + Right)")
        self.btn_fwd_5s.clicked.connect(lambda: self.seek_relative_requested.emit(5.0))

        # Playback Speed selector
        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("color: #94a3b8; font-weight: 500;")
        speed_label.setFixedWidth(38)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.1x", "0.25x", "0.5x", "0.75x", "1.0x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.setFixedWidth(64)
        self.speed_combo.setToolTip("Playback Rate (Slow motion for millisecond bat head saccades)")
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        # Head Crop / Zoom toggle
        self.btn_crop_zoom = QPushButton("🔍 Zoom")
        self.btn_crop_zoom.setCheckable(True)
        self.btn_crop_zoom.setFixedWidth(72)
        self.btn_crop_zoom.setToolTip("Toggle zoomed-in view on bat head ROI (Ctrl+Z)")
        self.btn_crop_zoom.clicked.connect(self._on_crop_zoom_toggled)

        self.btn_reset_crop = QPushButton("↺ Reset")
        self.btn_reset_crop.setFixedWidth(64)
        self.btn_reset_crop.setToolTip("Reset crop ROI back to full frame (Ctrl+R)")
        self.btn_reset_crop.clicked.connect(self.reset_crop_requested.emit)

        # Add to layout
        btn_row.addWidget(self.btn_back_5s)
        btn_row.addWidget(self.btn_step_back)
        btn_row.addWidget(self.btn_play)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_step_fwd)
        btn_row.addWidget(self.btn_fwd_5s)
        
        btn_row.addWidget(self._create_vdivider())
        btn_row.addWidget(speed_label)
        btn_row.addWidget(self.speed_combo)
        
        btn_row.addWidget(self._create_vdivider())
        btn_row.addWidget(self.btn_crop_zoom)
        btn_row.addWidget(self.btn_reset_crop)
        btn_row.addStretch()

        main_layout.addLayout(btn_row)

    def set_media_metadata(self, fps: float, duration_ms: int, total_frames: int):
        """Update playback bounds when a new video is loaded."""
        self.fps = fps if fps > 0 else 30.0
        self.duration_ms = duration_ms
        self.total_frames = total_frames
        self.seek_slider.setRange(0, max(1, duration_ms))
        self.update_position(0)

    @Slot(int)
    def update_position(self, current_ms: int):
        """Update timeline slider and time label from playback engine."""
        if not self.is_user_scrubbing:
            self.seek_slider.setValue(current_ms)

        cur_str = format_timestamp(current_ms)
        dur_str = format_timestamp(self.duration_ms)
        self.time_label.setText(f"{cur_str} / {dur_str}")

        current_frame = int(round((current_ms / 1000.0) * self.fps))
        self.frame_label.setText(f"Frame: {current_frame} / {self.total_frames}")

    def _on_slider_pressed(self):
        self.is_user_scrubbing = True

    def _on_slider_released(self):
        self.is_user_scrubbing = False
        self.seek_ms_requested.emit(self.seek_slider.value())

    def _on_slider_moved(self, value: int):
        cur_str = format_timestamp(value)
        dur_str = format_timestamp(self.duration_ms)
        self.time_label.setText(f"{cur_str} / {dur_str}")
        current_frame = int(round((value / 1000.0) * self.fps))
        self.frame_label.setText(f"Frame: {current_frame} / {self.total_frames}")

    def _on_speed_changed(self):
        text = self.speed_combo.currentText()
        try:
            rate = float(text.replace("x", ""))
            self.speed_changed.emit(rate)
        except ValueError:
            pass

    def _on_crop_zoom_toggled(self, checked: bool):
        self.is_cropped = checked
        if checked:
            self.btn_crop_zoom.setText("🔍 Full")
            self.btn_crop_zoom.setStyleSheet("background-color: #0369a1; border-color: #38bdf8; color: #ffffff;")
        else:
            self.btn_crop_zoom.setText("🔍 Zoom")
            self.btn_crop_zoom.setStyleSheet("")
        self.toggle_crop_view_requested.emit(checked)
