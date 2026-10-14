"""
Range selector widget for specifying start and end frames of interest for bat analysis.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSpinBox,
    QCheckBox, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from Code.utils.helpers import frame_to_timestamp

class RangeSelector(QWidget):
    """
    Allows researchers to designate the active experimental segment (start and end frames).
    """

    range_changed = Signal(int, int, bool)   # start_frame, end_frame, loop
    export_clip_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.fps: float = 30.0
        self.total_frames: int = 0
        self.current_frame: int = 0

        self._init_ui()

    def _create_vdivider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #2b2f42; margin: 1px 4px;")
        return line

    def _init_ui(self):
        group = QGroupBox("Video Range && Trimming (Bat Event Segment)")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(8, 6, 8, 6)
        group_layout.setSpacing(6)

        # Row 1: Start and End frame anchors + Length summary
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self.btn_set_start = QPushButton("⚑ Set Start")
        self.btn_set_start.setToolTip("Set start frame to current playback position")
        self.btn_set_start.clicked.connect(self._on_set_start_clicked)

        lbl_start = QLabel("Start:")
        lbl_start.setStyleSheet("color: #94a3b8; font-weight: 600;")

        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 0)
        self.spin_start.setValue(0)
        self.spin_start.setMinimumWidth(70)
        self.spin_start.setMaximumWidth(85)
        self.spin_start.setToolTip("Start frame index")
        self.spin_start.valueChanged.connect(self._on_range_inputs_changed)

        self.lbl_start_time = QLabel("00:00:00.000")
        self.lbl_start_time.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 6px; color: #38bdf8; font-family: Consolas;"
        )
        self.lbl_start_time.setToolTip("Start Timestamp")

        row1.addWidget(self.btn_set_start)
        row1.addWidget(lbl_start)
        row1.addWidget(self.spin_start)
        row1.addWidget(self.lbl_start_time)

        row1.addWidget(self._create_vdivider())

        self.btn_set_end = QPushButton("🏁 Set End")
        self.btn_set_end.setToolTip("Set end frame to current playback position")
        self.btn_set_end.clicked.connect(self._on_set_end_clicked)

        lbl_end = QLabel("End:")
        lbl_end.setStyleSheet("color: #94a3b8; font-weight: 600;")

        self.spin_end = QSpinBox()
        self.spin_end.setRange(0, 0)
        self.spin_end.setValue(0)
        self.spin_end.setMinimumWidth(70)
        self.spin_end.setMaximumWidth(85)
        self.spin_end.setToolTip("End frame index")
        self.spin_end.valueChanged.connect(self._on_range_inputs_changed)

        self.lbl_end_time = QLabel("00:00:00.000")
        self.lbl_end_time.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 6px; color: #38bdf8; font-family: Consolas;"
        )
        self.lbl_end_time.setToolTip("End Timestamp")

        row1.addWidget(self.btn_set_end)
        row1.addWidget(lbl_end)
        row1.addWidget(self.spin_end)
        row1.addWidget(self.lbl_end_time)
        row1.addStretch()

        group_layout.addLayout(row1)

        # Row 2: Length summary badge, Loop checkbox, Reset Range, Export Trimmed Video
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.lbl_summary = QLabel("Length: 0 frames (0.00s)")
        self.lbl_summary.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 8px; color: #a7f3d0; font-weight: bold; font-family: Consolas;"
        )
        self.lbl_summary.setToolTip("Active Trimming Segment Length")
        row2.addWidget(self.lbl_summary)

        row2.addWidget(self._create_vdivider())

        self.chk_loop = QCheckBox("Loop Range Playback")
        self.chk_loop.setToolTip("Automatically loop playback within the selected start and end frames")
        self.chk_loop.toggled.connect(self._on_range_inputs_changed)
        row2.addWidget(self.chk_loop)

        self.btn_reset = QPushButton("↺ Reset Full Video")
        self.btn_reset.setToolTip("Reset start and end frames to span the entire video")
        self.btn_reset.clicked.connect(self.reset_range)
        row2.addWidget(self.btn_reset)

        self.btn_export_clip = QPushButton("💾 Export Trimmed Video (MP4)")
        self.btn_export_clip.setToolTip("Export the selected range and bat head crop to MP4 clip")
        self.btn_export_clip.setStyleSheet("background-color: #047857; border-color: #059669; color: #ffffff; font-weight: 600; padding: 4px 12px;")
        self.btn_export_clip.clicked.connect(self.export_clip_requested.emit)
        row2.addWidget(self.btn_export_clip)
        row2.addStretch()

        group_layout.addLayout(row2)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(group)

    def set_media_metadata(self, fps: float, total_frames: int):
        """Initialize frame bounds when video is loaded."""
        self.fps = fps if fps > 0 else 30.0
        self.total_frames = max(0, total_frames)

        self.spin_start.blockSignals(True)
        self.spin_end.blockSignals(True)

        max_idx = max(0, self.total_frames - 1)
        self.spin_start.setRange(0, max_idx)
        self.spin_end.setRange(0, max_idx)

        # Default: initialized to start and end of the video
        self.spin_start.setValue(0)
        self.spin_end.setValue(max_idx)

        self.spin_start.blockSignals(False)
        self.spin_end.blockSignals(False)

        self._update_labels()
        self.range_changed.emit(0, max_idx, self.chk_loop.isChecked())

    def update_current_frame(self, frame_idx: int):
        self.current_frame = frame_idx

    def _on_set_start_clicked(self):
        val = min(self.current_frame, self.spin_end.value())
        self.spin_start.setValue(val)

    def _on_set_end_clicked(self):
        val = max(self.current_frame, self.spin_start.value())
        self.spin_end.setValue(val)

    def reset_range(self):
        """Reset to full duration."""
        self.spin_start.setValue(0)
        self.spin_end.setValue(max(0, self.total_frames - 1))

    def _on_range_inputs_changed(self):
        start = self.spin_start.value()
        end = self.spin_end.value()
        if start > end:
            # Prevent start from exceeding end
            self.spin_end.blockSignals(True)
            self.spin_end.setValue(start)
            self.spin_end.blockSignals(False)
            end = start

        self._update_labels()
        self.range_changed.emit(start, end, self.chk_loop.isChecked())

    def _update_labels(self):
        start = self.spin_start.value()
        end = self.spin_end.value()
        self.lbl_start_time.setText(frame_to_timestamp(start, self.fps))
        self.lbl_end_time.setText(frame_to_timestamp(end, self.fps))

        count = max(0, end - start + 1)
        seconds = count / self.fps if self.fps > 0 else 0.0
        self.lbl_summary.setText(f"Length: {count} frames ({seconds:.2f}s)")
