"""
Audio control widget providing loudness volume slider, percentage readout, and mute button.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSlider, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

class AudioControls(QWidget):
    """
    Dedicated audio control widget providing loudness volume slider and mute button.
    """

    volume_changed = Signal(int)   # 0 to 100
    mute_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.is_muted: bool = False
        self.last_volume: int = 80
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(6)

        # Mute button
        self.btn_mute = QPushButton("🔊 Mute")
        self.btn_mute.setToolTip("Toggle audio mute (bat echolocation audio track)")
        self.btn_mute.setFixedWidth(76)
        self.btn_mute.clicked.connect(self._on_mute_clicked)

        # Loudness slider (0 to 100)
        self.loudness_label = QLabel("Vol:")
        self.loudness_label.setStyleSheet("color: #94a3b8; font-weight: 600;")

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMinimumWidth(60)
        self.volume_slider.setMaximumWidth(85)
        self.volume_slider.setToolTip("Acoustic Audio Volume")
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)

        # Percent label badge
        self.percent_label = QLabel("80%")
        self.percent_label.setMinimumWidth(44)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percent_label.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 4px; color: #38bdf8; "
            "font-family: Consolas; font-weight: bold;"
        )

        layout.addWidget(self.btn_mute)
        layout.addWidget(self.loudness_label)
        layout.addWidget(self.volume_slider)
        layout.addWidget(self.percent_label)

    def set_volume(self, val: int):
        val = max(0, min(val, 100))
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(val)
        self.volume_slider.blockSignals(False)
        self.percent_label.setText(f"{val}%")
        if not self.is_muted:
            self.last_volume = val

    def set_muted(self, muted: bool):
        self.is_muted = muted
        if muted:
            self.btn_mute.setText("🔇 Unmute")
            self.btn_mute.setStyleSheet("background-color: #7f1d1d; border-color: #b91c1c; color: #fecaca;")
            self.percent_label.setText("Muted")
            self.percent_label.setStyleSheet(
                "background-color: #191b26; border: 1px solid #7f1d1d; "
                "border-radius: 4px; padding: 2px 4px; color: #f87171; "
                "font-family: Consolas; font-weight: bold;"
            )
        else:
            self.btn_mute.setText("🔊 Mute")
            self.btn_mute.setStyleSheet("")
            self.percent_label.setText(f"{self.volume_slider.value()}%")
            self.percent_label.setStyleSheet(
                "background-color: #191b26; border: 1px solid #2e3245; "
                "border-radius: 4px; padding: 2px 4px; color: #38bdf8; "
                "font-family: Consolas; font-weight: bold;"
            )

    def _on_volume_slider_changed(self, val: int):
        self.percent_label.setText(f"{val}%")
        if self.is_muted and val > 0:
            self.set_muted(False)
            self.mute_toggled.emit(False)
        self.last_volume = val
        self.volume_changed.emit(val)

    def _on_mute_clicked(self):
        new_mute = not self.is_muted
        self.set_muted(new_mute)
        self.mute_toggled.emit(new_mute)
