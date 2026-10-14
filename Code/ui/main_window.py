"""
Main application window for the Bat Pupil Tracking Application.
Coordinates the video player, audio controls, range trimming, image processing,
and EyeLoop pupil tracking subsystems.
"""
from typing import Optional, List, Dict, Any, Tuple
import os
import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QDockWidget,
    QFileDialog, QMessageBox, QStatusBar, QLabel, QProgressDialog
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon, QImage
import cv2

from Code.core.project_session import ProjectSession
from Code.core.media_engine import MediaEngine
from Code.core.frame_reader import FrameReader
from Code.core.video_processor import VideoProcessor
from Code.tracking.eyeloop_adapter import EyeLoopAdapter
from Code.tracking.pupil_detector import TrackingResult
from Code.tracking.data_exporter import DataExporter

from Code.ui.video_player_widget import VideoPlayerWidget
from Code.ui.playback_controls import PlaybackControls
from Code.ui.audio_controls import AudioControls
from Code.ui.range_selector import RangeSelector
from Code.ui.processing_panel import ProcessingPanel
from Code.ui.tracking_panel import TrackingPanel

class BatchTrackingWorker(QThread):
    """Background worker thread for batch processing frames with EyeLoop."""

    progress = Signal(int, int, float)        # current, total, fps_speed
    finished = Signal(list)                   # list of TrackingResult
    error = Signal(str)

    def __init__(
        self,
        video_path: str,
        start_frame: int,
        end_frame: int,
        roi: Optional[Tuple[int, int, int, int]],
        tracking_config: Dict[str, Any],
        processing_params: Dict[str, Any],
        fps: float
    ):
        super().__init__()
        self.video_path = video_path
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.roi = roi
        self.tracking_config = tracking_config
        self.processing_params = processing_params
        self.fps = fps
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            reader = FrameReader(self.video_path)
            if not reader.is_open():
                self.error.emit(f"Failed to open video file: {self.video_path}")
                return

            adapter = EyeLoopAdapter(self.tracking_config)
            adapter.reset()

            results: List[TrackingResult] = []
            total_frames = self.end_frame - self.start_frame + 1
            processed = 0
            start_time = time.time()

            roi_offset = (self.roi[0], self.roi[1]) if self.roi else None

            # Prepare enhancement parameters without UI preview overlay
            enh_params = None
            if self.processing_params:
                enh_params = self.processing_params.copy()
                enh_params["show_threshold"] = False

            for frame_idx, frame in reader.iterate_range(self.start_frame, self.end_frame):
                if self._is_cancelled:
                    break

                # Extract bat head crop if ROI is active
                if self.roi:
                    proc_frame = VideoProcessor.crop_roi(frame, self.roi)
                else:
                    proc_frame = frame

                # Apply active video enhancements (CLAHE, gamma, brightness, contrast, invert, rotation)
                if enh_params:
                    proc_frame = VideoProcessor.process_frame(
                        proc_frame, enh_params, roi=None, apply_crop=False
                    )

                timestamp_ms = int((frame_idx / self.fps) * 1000.0) if self.fps > 0 else 0
                res = adapter.process_frame(proc_frame, frame_idx, timestamp_ms, roi_offset=roi_offset)
                results.append(res)

                processed += 1
                if processed % 5 == 0 or processed == total_frames:
                    elapsed = max(0.001, time.time() - start_time)
                    speed = processed / elapsed
                    self.progress.emit(processed, total_frames, speed)

            reader.close()
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    """
    Main application window integrating all video, audio, processing,
    and tracking components for bat researchers.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bat Pupil Tracking System (EyeLoop Integration)")
        self.resize(1400, 880)
        self.setMinimumSize(1080, 640)

        # Core state models and engines
        self.session = ProjectSession()
        self.media_engine = MediaEngine(self)
        self.frame_reader = FrameReader()
        self.eyeloop_adapter = EyeLoopAdapter(self.session.tracking_params)
        self.last_tracking_results: List[TrackingResult] = []
        self.tracking_worker: Optional[BatchTrackingWorker] = None

        self._init_ui()
        self._create_menus()
        self._connect_signals()

    def _init_ui(self):
        # Central Video Player Viewport
        self.video_player = VideoPlayerWidget(self)

        # Bottom Control Panels
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(4, 2, 4, 4)
        bottom_layout.setSpacing(2)

        # Row with Playback Controls and Audio Controls
        transport_row = QHBoxLayout()
        transport_row.setContentsMargins(0, 0, 0, 0)
        transport_row.setSpacing(4)
        self.playback_controls = PlaybackControls(self)
        self.audio_controls = AudioControls(self)
        transport_row.addWidget(self.playback_controls, 1)
        transport_row.addWidget(self.audio_controls)
        bottom_layout.addLayout(transport_row)

        # Range Trimming Row
        self.range_selector = RangeSelector(self)
        bottom_layout.addWidget(self.range_selector)

        # Set central widget
        central_container = QWidget()
        central_layout = QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.video_player, 1)
        central_layout.addWidget(bottom_widget)
        self.setCentralWidget(central_container)

        # Left Dock: Video Processing Tools (CLAHE, Gamma, Contrast, etc.)
        self.processing_panel = ProcessingPanel(self)
        self.dock_processing = QDockWidget("Video Enhancement Tools", self)
        self.dock_processing.setWidget(self.processing_panel)
        self.dock_processing.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.dock_processing.setMinimumWidth(270)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_processing)

        # Right Dock: Pupil Tracking Controls (EyeLoop)
        self.tracking_panel = TrackingPanel(self)
        self.dock_tracking = QDockWidget("Pupil Tracking (EyeLoop)", self)
        self.dock_tracking.setWidget(self.tracking_panel)
        self.dock_tracking.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.dock_tracking.setMinimumWidth(280)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_tracking)

        self.resizeDocks([self.dock_processing, self.dock_tracking], [270, 280], Qt.Orientation.Horizontal)
        self.video_player.set_ellipse_color(self.session.tracking_params.get("ellipse_color", "#ec4899"))
        self.tracking_panel.set_parameters(self.session.tracking_params)

        # Status Bar with modern chip badges
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.lbl_status_info = QLabel("📹 Ready | No video loaded")
        self.lbl_status_info.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 8px; color: #94a3b8; font-family: Consolas;"
        )
        self.lbl_status_roi = QLabel("🎯 Bat Head ROI: None (Full Frame)")
        self.lbl_status_roi.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 8px; color: #94a3b8; font-family: Consolas;"
        )
        self.status_bar.addWidget(self.lbl_status_info, 1)
        self.status_bar.addPermanentWidget(self.lbl_status_roi)

    def _create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Video...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.action_open_video)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_session_action = QAction("&Save Project Session...", self)
        save_session_action.setShortcut(QKeySequence.StandardKey.Save)
        save_session_action.triggered.connect(self.action_save_session)
        file_menu.addAction(save_session_action)

        load_session_action = QAction("&Load Project Session...", self)
        load_session_action.triggered.connect(self.action_load_session)
        file_menu.addAction(load_session_action)

        file_menu.addSeparator()

        export_video_action = QAction("Export &Trimmed Video (MP4)...", self)
        export_video_action.triggered.connect(self.action_export_trimmed_video)
        file_menu.addAction(export_video_action)

        export_csv_action = QAction("Export Tracking &Data (CSV)...", self)
        export_csv_action.triggered.connect(self.action_export_csv)
        file_menu.addAction(export_csv_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.dock_processing.toggleViewAction())
        view_menu.addAction(self.dock_tracking.toggleViewAction())
        view_menu.addSeparator()

        toggle_zoom_action = QAction("Toggle &Zoom to Bat Head", self)
        toggle_zoom_action.setShortcut(QKeySequence("Ctrl+Z"))
        toggle_zoom_action.triggered.connect(lambda: self.playback_controls.btn_crop_zoom.click())
        view_menu.addAction(toggle_zoom_action)

        reset_crop_action = QAction("&Reset Bat Head Crop", self)
        reset_crop_action.setShortcut(QKeySequence("Ctrl+R"))
        reset_crop_action.triggered.connect(self.video_player.clear_crop_roi)
        view_menu.addAction(reset_crop_action)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        gen_sample_action = QAction("Generate &Bat Test Video with Sound...", self)
        gen_sample_action.triggered.connect(self.action_generate_sample_video)
        tools_menu.addAction(gen_sample_action)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        arch_action = QAction("&Architecture & Documentation", self)
        arch_action.triggered.connect(self.action_show_architecture_help)
        help_menu.addAction(arch_action)

        about_action = QAction("&About Bat Pupil Tracker", self)
        about_action.triggered.connect(self.action_show_about)
        help_menu.addAction(about_action)

    def _connect_signals(self):
        # Media Engine <-> Video Player & Playback Controls
        self.media_engine.frame_ready.connect(self.video_player.update_frame)
        self.media_engine.frame_ready.connect(self._on_frame_ready_for_tracking)
        self.media_engine.position_changed.connect(self.playback_controls.update_position)
        self.media_engine.position_changed.connect(self._on_position_changed)
        self.media_engine.error_occurred.connect(self._on_media_error)

        # Playback Controls -> Media Engine
        self.playback_controls.play_requested.connect(self.media_engine.play)
        self.playback_controls.pause_requested.connect(self.media_engine.pause)
        self.playback_controls.stop_requested.connect(self.media_engine.stop)
        self.playback_controls.step_frames_requested.connect(self.media_engine.step_frames)
        self.playback_controls.seek_relative_requested.connect(self.media_engine.seek_relative)
        self.playback_controls.seek_ms_requested.connect(self.media_engine.seek_ms)
        self.playback_controls.speed_changed.connect(self.media_engine.set_playback_rate)
        self.playback_controls.toggle_crop_view_requested.connect(self.video_player.set_cropped_view)
        self.playback_controls.reset_crop_requested.connect(self.video_player.clear_crop_roi)

        # Audio Controls -> Media Engine
        self.audio_controls.volume_changed.connect(self.media_engine.set_volume)
        self.audio_controls.mute_toggled.connect(self.media_engine.set_muted)

        # Range Selector -> Media Engine & Session
        self.range_selector.range_changed.connect(self._on_range_changed)
        self.range_selector.export_clip_requested.connect(self.action_export_trimmed_video)

        # Video Player ROI -> Session & Tracking
        self.video_player.roi_changed.connect(self._on_roi_changed)
        self.video_player.roi_cleared.connect(self._on_roi_cleared)

        # Processing Panel -> Video Player
        self.processing_panel.parameters_changed.connect(self._on_processing_params_changed)

        # Tracking Panel -> Tracking Pipeline
        self.tracking_panel.parameters_changed.connect(self._on_tracking_params_changed)
        self.tracking_panel.ellipse_color_changed.connect(self._on_ellipse_color_changed)
        self.tracking_panel.preview_toggled.connect(self._on_tracking_preview_toggled)
        self.tracking_panel.start_tracking_requested.connect(self.start_batch_tracking)
        self.tracking_panel.cancel_tracking_requested.connect(self.cancel_batch_tracking)
        self.tracking_panel.export_csv_requested.connect(self.action_export_csv)
        self.tracking_panel.export_plot_requested.connect(self.action_export_plot)

    def load_video(self, file_path: str):
        """Open a video file, load metadata, and configure playback and tracking."""
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "Error", f"Video file not found:\n{file_path}")
            return

        success = self.frame_reader.open(file_path)
        if not success:
            QMessageBox.critical(self, "Error", f"Failed to read video with OpenCV:\n{file_path}")
            return

        fps = self.frame_reader.fps
        total_frames = self.frame_reader.frame_count
        duration_ms = self.frame_reader.duration_ms
        width = self.frame_reader.width
        height = self.frame_reader.height

        # Initialize session state
        self.session.set_video_metadata(file_path, fps, total_frames, duration_ms, width, height)
        self.eyeloop_adapter.reset()

        # Initialize UI components
        self.video_player.set_video_metadata(fps, total_frames, duration_ms)
        self.video_player.clear_crop_roi()
        self.playback_controls.set_media_metadata(fps, duration_ms, total_frames)
        self.range_selector.set_media_metadata(fps, total_frames)

        # Load into QtMultimedia engine for synchronized audio and video playback
        self.media_engine.load_media(file_path, fps, total_frames)

        # Fetch initial frame for immediate viewport display
        ret, frame = self.frame_reader.get_frame(0)
        if ret and frame is not None:
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
            self.video_player.update_frame(qimg, 0)
            # Trigger tracking preview on first frame if active
            self._update_tracking_preview(frame, 0, 0)

        filename = os.path.basename(file_path)
        self.lbl_status_info.setText(
            f"📹 {filename}  •  {width}x{height} @ {fps:.2f} FPS  •  {total_frames} frames ({duration_ms/1000.0:.2f}s)"
        )
        self.lbl_status_roi.setText("🎯 Bat Head ROI: None (Full Frame)")
        self.lbl_status_roi.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 8px; color: #94a3b8; font-family: Consolas;"
        )

    def _on_frame_ready_for_tracking(self, image, frame_idx: int):
        """Whenever a frame is rendered, optionally compute live EyeLoop pupil tracking."""
        if not self.tracking_panel.chk_preview.isChecked():
            return
        frame_np = self.video_player.get_current_numpy_frame()
        if frame_np is not None:
            ms = self.media_engine.current_ms
            self._update_tracking_preview(frame_np, frame_idx, ms)

    def _update_tracking_preview(self, frame_np, frame_idx: int, ms: int):
        """Run single-frame EyeLoop detection on enhanced frame and send result to video viewport."""
        roi = self.session.crop_roi
        if roi:
            proc_frame = VideoProcessor.crop_roi(frame_np, roi)
            offset = (roi[0], roi[1])
        else:
            proc_frame = frame_np
            offset = None

        # Apply active video enhancements (CLAHE, gamma, brightness, contrast, invert, rotation)
        if self.session.processing_params:
            enh_params = self.session.processing_params.copy()
            enh_params["show_threshold"] = False  # Never bake threshold mask into tracking input
            proc_frame = VideoProcessor.process_frame(
                proc_frame, enh_params, roi=None, apply_crop=False
            )

        res = self.eyeloop_adapter.process_frame(proc_frame, frame_idx, ms, roi_offset=offset)
        self.video_player.set_tracking_result(res)

    @Slot(int)
    def _on_position_changed(self, current_ms: int):
        frame_idx = self.media_engine.get_current_frame()
        self.range_selector.update_current_frame(frame_idx)

    @Slot(int, int, bool)
    def _on_range_changed(self, start_frame: int, end_frame: int, loop: bool):
        self.session.set_range(start_frame, end_frame)
        self.session.loop_range = loop
        self.media_engine.set_range(start_frame, end_frame, loop)

    @Slot(tuple)
    def _on_roi_changed(self, roi: Tuple[int, int, int, int]):
        self.session.set_crop_roi(roi)
        self.eyeloop_adapter.reset()
        rx, ry, rw, rh = roi
        self.lbl_status_roi.setText(f"🎯 Bat Head ROI: {rw}x{rh} @ ({rx}, {ry})")
        self.lbl_status_roi.setStyleSheet(
            "background-color: #191b26; border: 1px solid #0284c7; "
            "border-radius: 4px; padding: 2px 8px; color: #38bdf8; font-family: Consolas;"
        )
        # Trigger immediate preview update
        frame_np = self.video_player.get_current_numpy_frame()
        if frame_np is not None:
            self._update_tracking_preview(frame_np, self.video_player.frame_idx, self.media_engine.current_ms)

    @Slot()
    def _on_roi_cleared(self):
        self.session.set_crop_roi(None)
        self.eyeloop_adapter.reset()
        self.lbl_status_roi.setText("🎯 Bat Head ROI: None (Full Frame)")
        self.lbl_status_roi.setStyleSheet(
            "background-color: #191b26; border: 1px solid #2e3245; "
            "border-radius: 4px; padding: 2px 8px; color: #94a3b8; font-family: Consolas;"
        )
        frame_np = self.video_player.get_current_numpy_frame()
        if frame_np is not None:
            self._update_tracking_preview(frame_np, self.video_player.frame_idx, self.media_engine.current_ms)

    @Slot(dict)
    def _on_processing_params_changed(self, params: Dict[str, Any]):
        self.session.processing_params = params
        self.video_player.set_processing_params(params)
        self.eyeloop_adapter.reset()
        # Immediately re-run tracking preview with the new enhanced image pixels!
        frame_np = self.video_player.get_current_numpy_frame()
        if frame_np is not None:
            self._update_tracking_preview(frame_np, self.video_player.frame_idx, self.media_engine.current_ms)

    @Slot(dict)
    def _on_tracking_params_changed(self, params: Dict[str, Any]):
        self.session.tracking_params = params
        self.eyeloop_adapter.update_config(params)
        self.eyeloop_adapter.reset()
        color = params.get("ellipse_color")
        if color:
            self.video_player.set_ellipse_color(color)
        frame_np = self.video_player.get_current_numpy_frame()
        if frame_np is not None:
            self._update_tracking_preview(frame_np, self.video_player.frame_idx, self.media_engine.current_ms)

    @Slot(str)
    def _on_ellipse_color_changed(self, color_hex: str):
        self.session.tracking_params["ellipse_color"] = color_hex
        self.video_player.set_ellipse_color(color_hex)
        frame_np = self.video_player.get_current_numpy_frame()
        if frame_np is not None:
            self._update_tracking_preview(frame_np, self.video_player.frame_idx, self.media_engine.current_ms)

    @Slot(bool)
    def _on_tracking_preview_toggled(self, enabled: bool):
        self.video_player.show_tracking_overlay = enabled
        if not enabled:
            self.video_player.set_tracking_result(None)
        else:
            frame_np = self.video_player.get_current_numpy_frame()
            if frame_np is not None:
                self._update_tracking_preview(frame_np, self.video_player.frame_idx, self.media_engine.current_ms)

    @Slot(str)
    def _on_media_error(self, err: str):
        self.lbl_status_info.setText(f"Media Engine: {err}")

    # --- Batch Tracking Worker Management ---
    def start_batch_tracking(self):
        """Launch background worker thread to track the designated range with EyeLoop."""
        if not self.session.video_path:
            QMessageBox.warning(self, "No Video", "Please load a video file first.")
            return

        self.media_engine.pause()
        self.tracking_panel.set_tracking_in_progress(True)
        self.tracking_panel.set_status_text("Tracking bat pupil in background...")

        self.tracking_worker = BatchTrackingWorker(
            video_path=self.session.video_path,
            start_frame=self.session.start_frame,
            end_frame=self.session.end_frame,
            roi=self.session.crop_roi,
            tracking_config=self.session.tracking_params,
            processing_params=self.session.processing_params,
            fps=self.session.fps
        )
        self.tracking_worker.progress.connect(self.tracking_panel.update_progress)
        self.tracking_worker.finished.connect(self._on_batch_tracking_finished)
        self.tracking_worker.error.connect(self._on_batch_tracking_error)
        self.tracking_worker.start()

    def cancel_batch_tracking(self):
        if self.tracking_worker and self.tracking_worker.isRunning():
            self.tracking_worker.cancel()
            self.tracking_panel.set_status_text("Cancelling tracking...")

    @Slot(list)
    def _on_batch_tracking_finished(self, results: List[TrackingResult]):
        self.tracking_panel.set_tracking_in_progress(False)
        self.last_tracking_results = results
        count = len(results)
        valid = sum(1 for r in results if not r.blink and r.confidence > 0.3)
        blinks = count - valid
        self.tracking_panel.set_status_text(f"Done! {count} frames tracked ({valid} valid, {blinks} blinks)")

        # Auto-prompt or notify user
        reply = QMessageBox.information(
            self,
            "Tracking Complete",
            f"Successfully processed {count} frames!\n"
            f"Valid pupil detections: {valid}\n"
            f"Blinks/Occlusions: {blinks}\n\n"
            "Would you like to export results to CSV and plot now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.action_export_csv()
            self.action_export_plot()

    @Slot(str)
    def _on_batch_tracking_error(self, err_msg: str):
        self.tracking_panel.set_tracking_in_progress(False)
        self.tracking_panel.set_status_text("Tracking failed.")
        QMessageBox.critical(self, "Tracking Error", f"An error occurred during tracking:\n{err_msg}")

    # --- Actions: File & Dialogs ---
    def action_open_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Bat Video File",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv);;All Files (*.*)"
        )
        if file_path:
            self.load_video(file_path)

    def action_save_session(self):
        if not self.session.video_path:
            QMessageBox.warning(self, "Warning", "No active video session to save.")
            return
        default_name = os.path.splitext(os.path.basename(self.session.video_path))[0] + "_session.json"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project Session",
            os.path.join("Configs", default_name),
            "JSON Files (*.json)"
        )
        if save_path:
            self.session.save_to_json(save_path)
            QMessageBox.information(self, "Success", f"Project session saved to:\n{save_path}")

    def action_load_session(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project Session",
            "Configs",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if file_path:
            self.session.load_from_json(file_path)
            if self.session.video_path and os.path.exists(self.session.video_path):
                self.load_video(self.session.video_path)
                self.processing_panel.set_parameters(self.session.processing_params)
                self.tracking_panel.set_parameters(self.session.tracking_params)
                self.video_player.set_ellipse_color(self.session.tracking_params.get("ellipse_color", "#ec4899"))
                if self.session.crop_roi:
                    self.video_player.set_crop_roi(self.session.crop_roi)
                self.video_player.set_cropped_view(self.session.is_cropped_view)
                self.playback_controls.btn_crop_zoom.setChecked(self.session.is_cropped_view)
                self.range_selector.spin_start.setValue(self.session.start_frame)
                self.range_selector.spin_end.setValue(self.session.end_frame)
                QMessageBox.information(self, "Success", "Session loaded successfully!")
            else:
                QMessageBox.warning(self, "Warning", "Session loaded, but video file was not found.")

    def action_export_trimmed_video(self):
        if not self.session.video_path:
            QMessageBox.warning(self, "Warning", "Please load a video first.")
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Trimmed Bat Clip",
            os.path.join("Results", "trimmed_bat_clip.mp4"),
            "MP4 Video (*.mp4);;AVI Video (*.avi)"
        )
        if not out_path:
            return

        prog = QProgressDialog("Exporting trimmed video...", "Cancel", 0, 100, self)
        prog.setWindowModality(Qt.WindowModality.WindowModal)

        def on_prog(written, total):
            prog.setValue(int((written / total) * 100))

        success = self.frame_reader.export_clip(
            output_path=out_path,
            start_frame=self.session.start_frame,
            end_frame=self.session.end_frame,
            roi=self.session.crop_roi if self.video_player.is_cropped_view else None,
            progress_callback=on_prog
        )
        prog.close()

        if success:
            QMessageBox.information(self, "Success", f"Trimmed clip saved to:\n{out_path}")
        else:
            QMessageBox.critical(self, "Error", "Failed to export video clip.")

    def action_export_csv(self):
        if not self.last_tracking_results:
            QMessageBox.warning(self, "No Data", "No tracking data available. Please run tracking first.")
            return

        csv_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tracking Metrics (CSV)",
            os.path.join("Results", "bat_pupil_kinematics.csv"),
            "CSV Files (*.csv)"
        )
        if csv_path:
            DataExporter.export_csv(self.last_tracking_results, csv_path)
            QMessageBox.information(self, "Export Successful", f"Pupil metrics exported to:\n{csv_path}")

    def action_export_plot(self):
        if not self.last_tracking_results:
            QMessageBox.warning(self, "No Data", "No tracking data available. Please run tracking first.")
            return

        plot_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Summary Dilation Plot (PNG)",
            os.path.join("Results", "bat_pupil_plot.png"),
            "PNG Image (*.png)"
        )
        if plot_path:
            DataExporter.export_summary_plot(self.last_tracking_results, plot_path)
            QMessageBox.information(self, "Plot Generated", f"Summary plot saved to:\n{plot_path}")

    def action_generate_sample_video(self):
        """Generates a synthetic bat video with pupil dilation and synchronized sound."""
        from Code.utils.generate_test_video import generate_synthetic_bat_video
        dest_video = os.path.join("Data", "bat_pupil_sample.mp4")
        generate_synthetic_bat_video(dest_video, duration_sec=5.0, fps=30)
        self.load_video(dest_video)
        QMessageBox.information(self, "Sample Generated", f"Bat sample video generated and loaded:\n{dest_video}")

    def action_show_architecture_help(self):
        QMessageBox.information(
            self,
            "Architecture Guide",
            "The application architecture documentation is available in:\nArchitecture.md\n\n"
            "Modules include UI, MediaEngine, VideoProcessor, EyeLoopAdapter, and DataExporter."
        )

    def action_show_about(self):
        QMessageBox.about(
            self,
            "About Bat Pupil Tracker",
            "<h3>Bat Pupil Tracking System</h3>"
            "<p>An agentic computer vision application designed for behavioral and neurobiological "
            "pupil tracking in bats.</p>"
            "<p><b>Core Technologies:</b> Python 3.12, PySide6 (QtMultimedia), OpenCV, NumPy, EyeLoop integration.</p>"
            "<p>Features synchronized video and audio playback, interactive bat head cropping, start/end frame trimming, "
            "CLAHE/gamma enhancement, corneal reflection removal, and kinematics export.</p>"
        )
