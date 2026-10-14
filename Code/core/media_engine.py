"""
Media engine coordinating synchronized video and audio playback using PySide6 QtMultimedia.
Provides video sink frame extraction, audio volume/mute control, seeking, and frame stepping.
"""
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, Slot, QUrl, Qt
from PySide6.QtMultimedia import (
    QMediaPlayer,
    QAudioOutput,
    QVideoSink,
    QVideoFrame
)
from PySide6.QtGui import QImage
import os

class MediaEngine(QObject):
    """
    Coordinates QtMultimedia video and audio playback pipelines.
    Extracts frames via QVideoSink for computer vision processing and renders audio via QAudioOutput.
    """

    position_changed = Signal(int)          # ms
    duration_changed = Signal(int)          # ms
    frame_ready = Signal(QImage, int)       # QImage, estimated frame index
    state_changed = Signal(QMediaPlayer.PlaybackState)
    volume_changed = Signal(int)            # 0 to 100
    mute_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.video_sink = QVideoSink(self)

        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoSink(self.video_sink)

        # Playback configuration
        self.fps: float = 30.0
        self.total_frames: int = 0
        self.duration_ms: int = 0
        self.current_frame_idx: int = 0
        self.current_ms: int = 0

        # Trimming & Loop bounds
        self.start_frame: int = 0
        self.end_frame: int = 0
        self.loop_range: bool = False

        # Audio initial defaults
        self.audio_output.setVolume(0.8) # 80% default volume

        # Connect Qt signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.errorOccurred.connect(self._on_error)
        self.video_sink.videoFrameChanged.connect(self._on_video_frame_changed)

    def load_media(self, file_path: str, fps: float = 30.0, total_frames: int = 0) -> bool:
        """Load a video file for audio and video playback."""
        if not os.path.exists(file_path):
            self.error_occurred.emit(f"File not found: {file_path}")
            return False

        self.fps = fps if fps > 0 else 30.0
        self.total_frames = total_frames
        self.start_frame = 0
        self.end_frame = max(0, total_frames - 1)

        url = QUrl.fromLocalFile(os.path.abspath(file_path))
        self.player.setSource(url)
        return True

    def play(self):
        """Start or resume playback."""
        # If currently at or past end_frame, seek to start_frame first
        current_frame = self.get_current_frame()
        if self.end_frame > self.start_frame and current_frame >= self.end_frame:
            self.seek_frame(self.start_frame)
        self.player.play()

    def pause(self):
        """Pause playback."""
        self.player.pause()

    def stop(self):
        """Stop playback and seek back to the start frame."""
        self.player.stop()
        self.seek_frame(self.start_frame)

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def is_paused(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState

    def get_playback_state(self) -> QMediaPlayer.PlaybackState:
        return self.player.playbackState()

    def seek_ms(self, ms: int):
        """Seek player to millisecond position."""
        ms = max(0, min(ms, self.duration_ms))
        self.player.setPosition(ms)

    def seek_frame(self, frame_idx: int):
        """Seek player to exact frame index."""
        if self.fps <= 0:
            return
        frame_idx = max(0, min(frame_idx, max(0, self.total_frames - 1)))
        target_ms = int((frame_idx / self.fps) * 1000.0)
        self.seek_ms(target_ms)

    def step_frames(self, delta: int):
        """Step playback by delta frames (+1 forward, -1 backward)."""
        self.pause()
        current_frame = self.get_current_frame()
        target_frame = current_frame + delta
        if self.total_frames > 0:
            target_frame = max(0, min(target_frame, self.total_frames - 1))
        self.seek_frame(target_frame)

    def seek_relative(self, seconds: float):
        """Seek forward or backward by a number of seconds."""
        delta_ms = int(seconds * 1000.0)
        target_ms = max(0, min(self.current_ms + delta_ms, self.duration_ms))
        self.seek_ms(target_ms)

    def set_volume(self, volume_percent: int):
        """Set audio loudness from 0 to 100%."""
        volume_percent = max(0, min(volume_percent, 100))
        # QAudioOutput volume is normalized 0.0 to 1.0
        self.audio_output.setVolume(volume_percent / 100.0)
        self.volume_changed.emit(volume_percent)

    def get_volume(self) -> int:
        return int(round(self.audio_output.volume() * 100.0))

    def set_muted(self, muted: bool):
        """Mute or unmute audio output."""
        self.audio_output.setMuted(muted)
        self.mute_changed.emit(muted)

    def is_muted(self) -> bool:
        return self.audio_output.isMuted()

    def toggle_mute(self):
        """Toggle audio mute state."""
        self.set_muted(not self.is_muted())

    def set_playback_rate(self, rate: float):
        """Set playback rate (e.g. 0.25x, 0.5x, 1.0x, 2.0x)."""
        rate = max(0.1, min(rate, 4.0))
        self.player.setPlaybackRate(rate)

    def set_range(self, start_frame: int, end_frame: int, loop: bool = False):
        """Set trimming range boundaries and loop behavior."""
        self.start_frame = max(0, start_frame)
        self.end_frame = max(self.start_frame, end_frame)
        self.loop_range = loop

    def get_current_frame(self) -> int:
        """Calculate current frame index from timestamp and FPS."""
        if self.fps <= 0:
            return 0
        return int(round((self.current_ms / 1000.0) * self.fps))

    @Slot(int)
    def _on_position_changed(self, position_ms: int):
        self.current_ms = position_ms
        self.current_frame_idx = self.get_current_frame()
        self.position_changed.emit(position_ms)

        # Check trimming end boundary during playback
        if self.is_playing() and self.end_frame > self.start_frame:
            end_ms = int((self.end_frame / self.fps) * 1000.0)
            if position_ms >= end_ms:
                if self.loop_range:
                    self.seek_frame(self.start_frame)
                else:
                    self.pause()
                    self.seek_frame(self.end_frame)

    @Slot(int)
    def _on_duration_changed(self, duration_ms: int):
        self.duration_ms = duration_ms
        if self.fps > 0 and self.total_frames == 0:
            self.total_frames = int(round((duration_ms / 1000.0) * self.fps))
            if self.end_frame == 0:
                self.end_frame = max(0, self.total_frames - 1)
        self.duration_changed.emit(duration_ms)

    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        self.state_changed.emit(state)

    @Slot(QMediaPlayer.Error, str)
    def _on_error(self, error: QMediaPlayer.Error, error_string: str):
        self.error_occurred.emit(f"Media Error ({error}): {error_string}")

    @Slot(QVideoFrame)
    def _on_video_frame_changed(self, video_frame: QVideoFrame):
        """Extract frame image as QImage and emit frame_ready signal."""
        if not video_frame.isValid():
            return
        image = video_frame.toImage()
        if not image.isNull():
            self.frame_ready.emit(image, self.current_frame_idx)
