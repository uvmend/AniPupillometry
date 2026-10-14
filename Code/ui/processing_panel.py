"""
Video processing sidebar panel for bat video enhancement.
Provides brightness, contrast, gamma, CLAHE, inversion, orientation, and pupil threshold previews.
"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox,
    QPushButton, QGroupBox, QComboBox, QDoubleSpinBox, QSpinBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal

class ProcessingPanel(QWidget):
    """
    Control dock widget for adjusting image filters to optimize pupil edge detection.
    """

    parameters_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self._init_ui()

    def _create_value_badge(self, initial_text: str = "0") -> QLabel:
        """Create a high-contrast numeric value badge that never truncates."""
        lbl = QLabel(initial_text)
        lbl.setMinimumWidth(44)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 1px 4px; color: #38bdf8; "
            "font-family: Consolas; font-weight: bold; font-size: 11px;"
        )
        return lbl

    def _init_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Preset selector
        preset_group = QGroupBox("Bat IR Illumination Presets")
        preset_layout = QVBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Default (No Filter)",
            "Bat Dataset (Dilation / Night Vision)",
            "Low-Contrast IR Video",
            "High-Contrast IR Video",
            "Dark Fur / Deep Shadow",
            "Strong Corneal Glint"
        ])
        self.preset_combo.setToolTip("Quick-apply calibrated enhancement profiles for bat infrared footage")
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        preset_layout.addWidget(self.preset_combo)
        layout.addWidget(preset_group)

        # 1. Basic Adjustments (Brightness, Contrast, Gamma)
        basic_group = QGroupBox("Intensity && Contrast")
        basic_layout = QVBoxLayout(basic_group)

        # Brightness
        b_row = QHBoxLayout()
        lbl_b = QLabel("Brightness:")
        lbl_b.setStyleSheet("color: #e2e8f0;")
        self.lbl_brightness = self._create_value_badge("0")
        b_row.addWidget(lbl_b)
        b_row.addStretch()
        b_row.addWidget(self.lbl_brightness)
        basic_layout.addLayout(b_row)

        self.slider_brightness = QSlider(Qt.Orientation.Horizontal)
        self.slider_brightness.setRange(-100, 100)
        self.slider_brightness.setValue(0)
        self.slider_brightness.setToolTip("Adjust overall luminance (-100 to +100)")
        self.slider_brightness.valueChanged.connect(self._on_slider_changed)
        basic_layout.addWidget(self.slider_brightness)

        # Contrast
        c_row = QHBoxLayout()
        lbl_c = QLabel("Contrast:")
        lbl_c.setStyleSheet("color: #e2e8f0;")
        self.lbl_contrast = self._create_value_badge("1.00")
        c_row.addWidget(lbl_c)
        c_row.addStretch()
        c_row.addWidget(self.lbl_contrast)
        basic_layout.addLayout(c_row)

        self.slider_contrast = QSlider(Qt.Orientation.Horizontal)
        self.slider_contrast.setRange(10, 300) # 0.1x to 3.0x
        self.slider_contrast.setValue(100)
        self.slider_contrast.setToolTip("Scale dynamic range (0.1x to 3.0x)")
        self.slider_contrast.valueChanged.connect(self._on_slider_changed)
        basic_layout.addWidget(self.slider_contrast)

        # Gamma
        g_row = QHBoxLayout()
        lbl_g = QLabel("Gamma:")
        lbl_g.setStyleSheet("color: #e2e8f0;")
        self.lbl_gamma = self._create_value_badge("1.00")
        g_row.addWidget(lbl_g)
        g_row.addStretch()
        g_row.addWidget(self.lbl_gamma)
        basic_layout.addLayout(g_row)

        self.slider_gamma = QSlider(Qt.Orientation.Horizontal)
        self.slider_gamma.setRange(10, 300) # 0.1 to 3.0
        self.slider_gamma.setValue(100)
        self.slider_gamma.setToolTip("Non-linear luminance adjustment (essential for bat shadow detail)")
        self.slider_gamma.valueChanged.connect(self._on_slider_changed)
        basic_layout.addWidget(self.slider_gamma)

        layout.addWidget(basic_group)

        # 2. Advanced Enhancement: CLAHE
        clahe_group = QGroupBox("Adaptive Enhancement (CLAHE)")
        clahe_layout = QVBoxLayout(clahe_group)

        self.chk_clahe = QCheckBox("Enable CLAHE")
        self.chk_clahe.setToolTip("Contrast Limited Adaptive Histogram Equalization - boosts iris/pupil boundary")
        self.chk_clahe.toggled.connect(self._on_slider_changed)
        clahe_layout.addWidget(self.chk_clahe)

        clip_row = QHBoxLayout()
        lbl_clip = QLabel("Clip Limit:")
        lbl_clip.setStyleSheet("color: #94a3b8;")
        self.spin_clahe_clip = QDoubleSpinBox()
        self.spin_clahe_clip.setRange(1.0, 10.0)
        self.spin_clahe_clip.setSingleStep(0.5)
        self.spin_clahe_clip.setValue(2.0)
        self.spin_clahe_clip.setMinimumWidth(65)
        self.spin_clahe_clip.setToolTip("Threshold for contrast limiting in local tiles")
        self.spin_clahe_clip.valueChanged.connect(self._on_slider_changed)
        clip_row.addWidget(lbl_clip)
        clip_row.addStretch()
        clip_row.addWidget(self.spin_clahe_clip)
        clahe_layout.addLayout(clip_row)

        grid_row = QHBoxLayout()
        lbl_grid = QLabel("Tile Grid Size:")
        lbl_grid.setStyleSheet("color: #94a3b8;")
        self.spin_clahe_grid = QSpinBox()
        self.spin_clahe_grid.setRange(2, 32)
        self.spin_clahe_grid.setSingleStep(2)
        self.spin_clahe_grid.setValue(8)
        self.spin_clahe_grid.setMinimumWidth(65)
        self.spin_clahe_grid.setToolTip("Number of grid tiles for contextual equalization")
        self.spin_clahe_grid.valueChanged.connect(self._on_slider_changed)
        grid_row.addWidget(lbl_grid)
        grid_row.addStretch()
        grid_row.addWidget(self.spin_clahe_grid)
        clahe_layout.addLayout(grid_row)

        layout.addWidget(clahe_group)

        # 3. Color & Thresholding Tools
        thresh_group = QGroupBox("Binarization && Threshold Preview")
        thresh_layout = QVBoxLayout(thresh_group)

        self.chk_invert = QCheckBox("Invert Video (Negatives)")
        self.chk_invert.setToolTip("Invert pixel intensities (useful if pupil appears brighter than surrounding tissue)")
        self.chk_invert.toggled.connect(self._on_slider_changed)
        thresh_layout.addWidget(self.chk_invert)

        self.chk_grayscale = QCheckBox("Grayscale Mode")
        self.chk_grayscale.setToolTip("Convert frame to single-channel luminance")
        self.chk_grayscale.toggled.connect(self._on_slider_changed)
        thresh_layout.addWidget(self.chk_grayscale)

        self.chk_show_thresh = QCheckBox("Preview Pupil Threshold Mask")
        self.chk_show_thresh.setToolTip("Highlights detected pupil candidate pixels in bright cyan on the video player")
        self.chk_show_thresh.toggled.connect(self._on_slider_changed)
        thresh_layout.addWidget(self.chk_show_thresh)

        th_row = QHBoxLayout()
        lbl_th = QLabel("Pupil Cutoff:")
        lbl_th.setStyleSheet("color: #e2e8f0;")
        self.lbl_thresh_val = self._create_value_badge("45")
        th_row.addWidget(lbl_th)
        th_row.addStretch()
        th_row.addWidget(self.lbl_thresh_val)
        thresh_layout.addLayout(th_row)

        self.slider_thresh = QSlider(Qt.Orientation.Horizontal)
        self.slider_thresh.setRange(0, 255)
        self.slider_thresh.setValue(45)
        self.slider_thresh.setToolTip("Pixel intensity threshold cutoff (0 to 255)")
        self.slider_thresh.valueChanged.connect(self._on_slider_changed)
        thresh_layout.addWidget(self.slider_thresh)

        layout.addWidget(thresh_group)

        # 4. Orientation & Geometry (for hanging bats)
        orient_group = QGroupBox("Bat Orientation && Rotation")
        orient_layout = QVBoxLayout(orient_group)

        rot_row = QHBoxLayout()
        lbl_rot = QLabel("Rotate:")
        lbl_rot.setStyleSheet("color: #e2e8f0;")
        self.combo_rotation = QComboBox()
        self.combo_rotation.addItems([
            "0° (Normal)",
            "90° CW",
            "180° (Upside-Down Bat)",
            "270° CW"
        ])
        self.combo_rotation.setToolTip("Rotate video orientation for hanging roosting bats")
        self.combo_rotation.currentIndexChanged.connect(self._on_slider_changed)
        rot_row.addWidget(lbl_rot)
        rot_row.addWidget(self.combo_rotation, 1)
        orient_layout.addLayout(rot_row)

        flip_row = QHBoxLayout()
        self.chk_flip_h = QCheckBox("Flip Horizontal")
        self.chk_flip_h.setToolTip("Mirror frame horizontally")
        self.chk_flip_h.toggled.connect(self._on_slider_changed)
        self.chk_flip_v = QCheckBox("Flip Vertical")
        self.chk_flip_v.setToolTip("Mirror frame vertically")
        self.chk_flip_v.toggled.connect(self._on_slider_changed)
        flip_row.addWidget(self.chk_flip_h)
        flip_row.addWidget(self.chk_flip_v)
        orient_layout.addLayout(flip_row)

        layout.addWidget(orient_group)

        # Reset button
        self.btn_reset = QPushButton("↺ Reset Video Filters")
        self.btn_reset.setToolTip("Restore all enhancement filters to neutral defaults")
        self.btn_reset.clicked.connect(self.reset_parameters)
        layout.addWidget(self.btn_reset)

        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _get_rotation_degrees(self) -> int:
        idx = self.combo_rotation.currentIndex()
        if idx == 1:
            return 90
        elif idx == 2:
            return 180
        elif idx == 3:
            return 270
        return 0

    def get_parameters(self) -> Dict[str, Any]:
        """Return the current dictionary of image processing parameters."""
        return {
            "brightness": self.slider_brightness.value(),
            "contrast": self.slider_contrast.value() / 100.0,
            "gamma": self.slider_gamma.value() / 100.0,
            "clahe_enabled": self.chk_clahe.isChecked(),
            "clahe_clip": self.spin_clahe_clip.value(),
            "clahe_grid": self.spin_clahe_grid.value(),
            "invert": self.chk_invert.isChecked(),
            "grayscale": self.chk_grayscale.isChecked(),
            "show_threshold": self.chk_show_thresh.isChecked(),
            "threshold_val": self.slider_thresh.value(),
            "rotation": self._get_rotation_degrees(),
            "flip_h": self.chk_flip_h.isChecked(),
            "flip_v": self.chk_flip_v.isChecked()
        }

    def set_parameters(self, params: Dict[str, Any]):
        """Populate GUI widgets from dictionary."""
        self.blockSignals(True)
        self.slider_brightness.setValue(params.get("brightness", 0))
        self.slider_contrast.setValue(int(params.get("contrast", 1.0) * 100))
        self.slider_gamma.setValue(int(params.get("gamma", 1.0) * 100))
        self.chk_clahe.setChecked(params.get("clahe_enabled", False))
        self.spin_clahe_clip.setValue(params.get("clahe_clip", 2.0))
        self.spin_clahe_grid.setValue(params.get("clahe_grid", 8))
        self.chk_invert.setChecked(params.get("invert", False))
        self.chk_grayscale.setChecked(params.get("grayscale", False))
        self.chk_show_thresh.setChecked(params.get("show_threshold", False))
        self.slider_thresh.setValue(params.get("threshold_val", 45))
        
        rot = params.get("rotation", 0)
        rot_idx = 0
        if rot == 90:
            rot_idx = 1
        elif rot == 180:
            rot_idx = 2
        elif rot == 270:
            rot_idx = 3
        self.combo_rotation.setCurrentIndex(rot_idx)
        self.chk_flip_h.setChecked(params.get("flip_h", False))
        self.chk_flip_v.setChecked(params.get("flip_v", False))

        self.blockSignals(False)
        self._update_readout_labels()

    def reset_parameters(self):
        """Restore all image enhancement parameters to neutral defaults."""
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)

        self.slider_brightness.setValue(0)
        self.slider_contrast.setValue(100)
        self.slider_gamma.setValue(100)
        self.chk_clahe.setChecked(False)
        self.chk_invert.setChecked(False)
        self.chk_grayscale.setChecked(False)
        self.chk_show_thresh.setChecked(False)
        self.slider_thresh.setValue(45)
        self.combo_rotation.setCurrentIndex(0)
        self.chk_flip_h.setChecked(False)
        self.chk_flip_v.setChecked(False)
        self._on_slider_changed()

    def _apply_preset(self, index: int):
        if index == 0:  # Default
            self.reset_parameters()
            return

        self.blockSignals(True)
        for w in (
            self.slider_brightness, self.slider_contrast, self.slider_gamma,
            self.chk_clahe, self.spin_clahe_clip, self.spin_clahe_grid, self.slider_thresh
        ):
            w.blockSignals(True)

        if index == 1:  # Bat Dataset (Dilation / Night Vision)
            self.slider_brightness.setValue(-5)
            self.slider_contrast.setValue(140)
            self.slider_gamma.setValue(80)
            self.chk_clahe.setChecked(False)
            self.spin_clahe_clip.setValue(1.8)
            self.spin_clahe_grid.setValue(6)
            self.slider_thresh.setValue(82)
        elif index == 2:  # Low-Contrast IR
            self.slider_brightness.setValue(-10)
            self.slider_contrast.setValue(155)
            self.slider_gamma.setValue(75)
            self.chk_clahe.setChecked(True)
            self.spin_clahe_clip.setValue(1.6)
            self.spin_clahe_grid.setValue(6)
            self.slider_thresh.setValue(82)
        elif index == 3:  # High-Contrast IR
            self.slider_brightness.setValue(-5)
            self.slider_contrast.setValue(125)
            self.slider_gamma.setValue(90)
            self.chk_clahe.setChecked(False)
            self.slider_thresh.setValue(75)
        elif index == 4:  # Dark Fur / Deep Shadow
            self.slider_brightness.setValue(5)
            self.slider_contrast.setValue(145)
            self.slider_gamma.setValue(82)
            self.chk_clahe.setChecked(True)
            self.spin_clahe_clip.setValue(1.8)
            self.spin_clahe_grid.setValue(6)
            self.slider_thresh.setValue(78)
        elif index == 5:  # Strong Corneal Glint
            self.slider_brightness.setValue(-8)
            self.slider_contrast.setValue(135)
            self.slider_gamma.setValue(82)
            self.chk_clahe.setChecked(False)
            self.slider_thresh.setValue(80)

        for w in (
            self.slider_brightness, self.slider_contrast, self.slider_gamma,
            self.chk_clahe, self.spin_clahe_clip, self.spin_clahe_grid, self.slider_thresh
        ):
            w.blockSignals(False)
        self.blockSignals(False)
        self._on_slider_changed()

    def _update_readout_labels(self):
        self.lbl_brightness.setText(str(self.slider_brightness.value()))
        self.lbl_contrast.setText(f"{self.slider_contrast.value() / 100.0:.2f}")
        self.lbl_gamma.setText(f"{self.slider_gamma.value() / 100.0:.2f}")
        self.lbl_thresh_val.setText(str(self.slider_thresh.value()))

    def _on_slider_changed(self):
        self._update_readout_labels()
        self.parameters_changed.emit(self.get_parameters())
