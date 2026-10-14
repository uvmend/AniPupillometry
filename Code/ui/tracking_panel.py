"""
Pupil tracking control panel.
Provides EyeLoop parameter tuning, live preview toggle, batch tracking execution,
progress visualization, and CSV/Plot export buttons.
"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox,
    QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QComboBox, QScrollArea, QColorDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

class TrackingPanel(QWidget):
    """
    Control dock widget for configuring and running the EyeLoop pupil tracking pipeline.
    """

    parameters_changed = Signal(dict)
    preview_toggled = Signal(bool)
    ellipse_color_changed = Signal(str)
    start_tracking_requested = Signal()
    cancel_tracking_requested = Signal()
    export_csv_requested = Signal()
    export_plot_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumWidth(270)
        self._current_ellipse_color: str = "#ec4899"
        self._init_ui()

    def _create_value_badge(self, initial_text: str = "45") -> QLabel:
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

        # 1. Algorithm Selection
        algo_group = QGroupBox("Pupil Tracking Engine (EyeLoop)")
        algo_layout = QVBoxLayout(algo_group)

        self.combo_algo = QComboBox()
        self.combo_algo.addItems([
            "EyeLoop Boundary Walk-Out (Recommended)",
            "Direct Contour Ellipse Fitting"
        ])
        self.combo_algo.setToolTip("Select pupil edge detection algorithm")
        self.combo_algo.currentIndexChanged.connect(self._on_params_changed)
        algo_layout.addWidget(self.combo_algo)

        self.chk_preview = QCheckBox("Live Viewport Tracking Preview")
        self.chk_preview.setChecked(True)
        self.chk_preview.setToolTip("Overlay pupil ellipse, center dot, and corneal reflection glint on video")
        self.chk_preview.toggled.connect(self.preview_toggled.emit)
        algo_layout.addWidget(self.chk_preview)

        # High-contrast Ellipse Overlay Color Selector (essential for green IR video)
        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        lbl_color = QLabel("Ellipse Color:")
        lbl_color.setStyleSheet("color: #e2e8f0; font-size: 11px;")

        self.combo_color = QComboBox()
        self.combo_color.addItem("🌸 Magenta (Best for Green IR)", "#ec4899")
        self.combo_color.addItem("🔥 Neon Coral / Orange", "#f97316")
        self.combo_color.addItem("💎 Electric Cyan", "#06b6d4")
        self.combo_color.addItem("🌟 Vibrant Yellow", "#facc15")
        self.combo_color.addItem("🟢 Classic Green (Grayscale IR)", "#10b981")
        self.combo_color.addItem("🎨 Pick Custom Color...", "custom")
        self.combo_color.setToolTip("Select high-contrast ellipse color (Electric Magenta is optimal for green IR video)")
        self.combo_color.currentIndexChanged.connect(self._on_color_combo_changed)

        self.btn_color_swatch = QPushButton()
        self.btn_color_swatch.setFixedSize(26, 22)
        self.btn_color_swatch.setStyleSheet(
            f"background-color: {self._current_ellipse_color}; border: 1px solid #475569; border-radius: 3px;"
        )
        self.btn_color_swatch.setToolTip("Click to choose a custom color")
        self.btn_color_swatch.clicked.connect(self._pick_custom_color)

        color_row.addWidget(lbl_color)
        color_row.addWidget(self.combo_color, 1)
        color_row.addWidget(self.btn_color_swatch)
        algo_layout.addLayout(color_row)

        layout.addWidget(algo_group)

        # 2. EyeLoop Detection Parameters
        param_group = QGroupBox("EyeLoop Thresholds && Geometry")
        param_layout = QVBoxLayout(param_group)

        # Pupil intensity cutoff
        p_row = QHBoxLayout()
        lbl_p = QLabel("Pupil Threshold:")
        lbl_p.setStyleSheet("color: #e2e8f0;")
        self.lbl_thresh = self._create_value_badge("82")
        p_row.addWidget(lbl_p)
        p_row.addStretch()
        p_row.addWidget(self.lbl_thresh)
        param_layout.addLayout(p_row)

        self.slider_thresh = QSlider(Qt.Orientation.Horizontal)
        self.slider_thresh.setRange(5, 255)
        self.slider_thresh.setValue(82)
        self.slider_thresh.setToolTip("Dark binarization threshold cutoff for pupil segmentation")
        self.slider_thresh.valueChanged.connect(self._on_params_changed)
        param_layout.addWidget(self.slider_thresh)

        # Min and Max Area
        area_row = QHBoxLayout()
        lbl_min_a = QLabel("Min Area:")
        lbl_min_a.setStyleSheet("color: #94a3b8;")
        self.spin_min_area = QSpinBox()
        self.spin_min_area.setRange(5, 5000)
        self.spin_min_area.setValue(15)
        self.spin_min_area.setMinimumWidth(60)
        self.spin_min_area.setToolTip("Minimum pupil contour area in pixels")
        self.spin_min_area.valueChanged.connect(self._on_params_changed)
        area_row.addWidget(lbl_min_a)
        area_row.addWidget(self.spin_min_area)
        area_row.addSpacing(6)

        lbl_max_a = QLabel("Max Area:")
        lbl_max_a.setStyleSheet("color: #94a3b8;")
        self.spin_max_area = QSpinBox()
        self.spin_max_area.setRange(50, 50000)
        self.spin_max_area.setValue(3500)
        self.spin_max_area.setMinimumWidth(70)
        self.spin_max_area.setToolTip("Maximum pupil contour area in pixels")
        self.spin_max_area.valueChanged.connect(self._on_params_changed)
        area_row.addWidget(lbl_max_a)
        area_row.addWidget(self.spin_max_area)
        param_layout.addLayout(area_row)

        # Circularity
        circ_row = QHBoxLayout()
        lbl_circ = QLabel("Min Circularity:")
        lbl_circ.setStyleSheet("color: #94a3b8;")
        self.spin_circ = QDoubleSpinBox()
        self.spin_circ.setRange(0.05, 1.0)
        self.spin_circ.setSingleStep(0.05)
        self.spin_circ.setValue(0.25)
        self.spin_circ.setMinimumWidth(65)
        self.spin_circ.setToolTip("Minimum circularity metric 4*pi*area/perimeter^2")
        self.spin_circ.valueChanged.connect(self._on_params_changed)
        circ_row.addWidget(lbl_circ)
        circ_row.addStretch()
        circ_row.addWidget(self.spin_circ)
        param_layout.addLayout(circ_row)

        # Boundary Offset (fine-tune ellipse radius in pixels)
        offset_row = QHBoxLayout()
        lbl_offset = QLabel("Boundary Offset (px):")
        lbl_offset.setStyleSheet("color: #94a3b8;")
        self.spin_boundary_offset = QDoubleSpinBox()
        self.spin_boundary_offset.setRange(-5.0, 10.0)
        self.spin_boundary_offset.setSingleStep(0.5)
        self.spin_boundary_offset.setValue(0.0)
        self.spin_boundary_offset.setMinimumWidth(65)
        self.spin_boundary_offset.setToolTip("Expand (+) or shrink (-) fitted pupil ellipse radius in pixels")
        self.spin_boundary_offset.valueChanged.connect(self._on_params_changed)
        offset_row.addWidget(lbl_offset)
        offset_row.addStretch()
        offset_row.addWidget(self.spin_boundary_offset)
        param_layout.addLayout(offset_row)

        # Corneal Reflection Removal
        self.chk_cr_removal = QCheckBox("Remove Corneal Glint (IR LED)")
        self.chk_cr_removal.setChecked(True)
        self.chk_cr_removal.setToolTip("Isolate and inpaint bright specular IR reflection before ellipse fitting")
        self.chk_cr_removal.toggled.connect(self._on_params_changed)
        param_layout.addWidget(self.chk_cr_removal)

        # Temporal Smoothing
        self.chk_smoothing = QCheckBox("Temporal Continuity Smoothing")
        self.chk_smoothing.setChecked(True)
        self.chk_smoothing.setToolTip("Smooths jitter between consecutive frames and flags blinks/occlusions")
        self.chk_smoothing.toggled.connect(self._on_params_changed)
        param_layout.addWidget(self.chk_smoothing)

        layout.addWidget(param_group)

        # 3. Batch Tracking Execution
        exec_group = QGroupBox("Batch Tracking Execution")
        exec_layout = QVBoxLayout(exec_group)

        self.btn_track_range = QPushButton("🚀 Track Bat Pupil (Selected Range)")
        self.btn_track_range.setObjectName("primaryButton")
        self.btn_track_range.setFixedHeight(36)
        self.btn_track_range.setToolTip("Run asynchronous EyeLoop tracking over the selected frame range")
        self.btn_track_range.clicked.connect(self.start_tracking_requested.emit)
        exec_layout.addWidget(self.btn_track_range)

        self.btn_cancel = QPushButton("⏹ Cancel Tracking")
        self.btn_cancel.setObjectName("stopButton")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setToolTip("Halt background tracking worker")
        self.btn_cancel.clicked.connect(self.cancel_tracking_requested.emit)
        exec_layout.addWidget(self.btn_cancel)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)
        exec_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready to track")
        self.lbl_status.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 4px 6px; color: #94a3b8; font-size: 11px;"
        )
        self.lbl_status.setWordWrap(True)
        exec_layout.addWidget(self.lbl_status)

        layout.addWidget(exec_group)

        # 4. Data Export
        export_group = QGroupBox("Export && Analysis")
        export_layout = QVBoxLayout(export_group)

        self.btn_export_csv = QPushButton("📊 Export Kinematics (CSV)")
        self.btn_export_csv.setToolTip("Export frame-by-frame pupil coordinates, area, axes, and glint to CSV")
        self.btn_export_csv.clicked.connect(self.export_csv_requested.emit)
        export_layout.addWidget(self.btn_export_csv)

        self.btn_export_plot = QPushButton("📈 Export Dilation Plot (PNG)")
        self.btn_export_plot.setToolTip("Generate and save 3-panel Matplotlib kinematic summary plots")
        self.btn_export_plot.clicked.connect(self.export_plot_requested.emit)
        export_layout.addWidget(self.btn_export_plot)

        layout.addWidget(export_group)

        layout.addStretch()

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_color_combo_changed(self, index: int):
        data = self.combo_color.itemData(index)
        if data == "custom":
            self._pick_custom_color()
        elif data:
            self._current_ellipse_color = data
            self._update_color_swatch(data)
            self.ellipse_color_changed.emit(data)
            self._on_params_changed()

    def _pick_custom_color(self):
        col = QColorDialog.getColor(QColor(self._current_ellipse_color), self, "Select Pupil Ellipse Color")
        if col.isValid():
            hex_col = col.name()
            self._current_ellipse_color = hex_col
            custom_idx = self.combo_color.findData("custom")
            if custom_idx >= 0:
                self.combo_color.setItemText(custom_idx, f"🎨 Custom ({hex_col.upper()})")
                self.combo_color.blockSignals(True)
                self.combo_color.setCurrentIndex(custom_idx)
                self.combo_color.blockSignals(False)
            self._update_color_swatch(hex_col)
            self.ellipse_color_changed.emit(hex_col)
            self._on_params_changed()

    def _update_color_swatch(self, hex_color: str):
        self.btn_color_swatch.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #475569; border-radius: 3px;"
        )

    def get_parameters(self) -> Dict[str, Any]:
        """Get tracking configuration dictionary."""
        return {
            "pupil_threshold": self.slider_thresh.value(),
            "min_pupil_area": self.spin_min_area.value(),
            "max_pupil_area": self.spin_max_area.value(),
            "min_circularity": self.spin_circ.value(),
            "boundary_offset": self.spin_boundary_offset.value(),
            "cr_removal": self.chk_cr_removal.isChecked(),
            "temporal_smoothing": self.chk_smoothing.isChecked(),
            "algorithm": "eyeloop_rays" if self.combo_algo.currentIndex() == 0 else "contour_ellipse",
            "ellipse_color": self._current_ellipse_color
        }

    def set_parameters(self, params: Dict[str, Any]):
        """Populate GUI parameters from dictionary."""
        self.blockSignals(True)
        self.slider_thresh.setValue(params.get("pupil_threshold", 82))
        self.spin_min_area.setValue(params.get("min_pupil_area", 15))
        self.spin_max_area.setValue(params.get("max_pupil_area", 3500))
        self.spin_circ.setValue(params.get("min_circularity", 0.25))
        self.spin_boundary_offset.setValue(float(params.get("boundary_offset", 0.0)))
        self.chk_cr_removal.setChecked(params.get("cr_removal", True))
        self.chk_smoothing.setChecked(params.get("temporal_smoothing", True))
        algo = params.get("algorithm", "eyeloop_rays")
        self.combo_algo.setCurrentIndex(0 if algo == "eyeloop_rays" else 1)

        color = params.get("ellipse_color", "#ec4899")
        self._current_ellipse_color = color
        idx = self.combo_color.findData(color)
        if idx >= 0:
            self.combo_color.setCurrentIndex(idx)
        else:
            custom_idx = self.combo_color.findData("custom")
            if custom_idx >= 0:
                self.combo_color.setItemText(custom_idx, f"🎨 Custom ({color.upper()})")
                self.combo_color.setCurrentIndex(custom_idx)
        self._update_color_swatch(color)

        self.blockSignals(False)
        self.lbl_thresh.setText(str(self.slider_thresh.value()))

    def set_tracking_in_progress(self, in_progress: bool):
        """Toggle UI controls when batch tracking begins or finishes."""
        self.btn_track_range.setEnabled(not in_progress)
        self.btn_cancel.setEnabled(in_progress)
        if not in_progress:
            self.progress_bar.setValue(100)

    def update_progress(self, current: int, total: int, fps_speed: float = 0.0):
        """Update progress bar and status text."""
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            speed_txt = f" ({fps_speed:.1f} fps)" if fps_speed > 0 else ""
            self.lbl_status.setText(f"Tracking frame {current}/{total} ({pct}%){speed_txt}")

    def set_status_text(self, text: str):
        self.lbl_status.setText(text)

    def _on_params_changed(self):
        self.lbl_thresh.setText(str(self.slider_thresh.value()))
        self.parameters_changed.emit(self.get_parameters())
