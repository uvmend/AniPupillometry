"""
Frame-accurate video reader and exporter using OpenCV.
Handles video metadata extraction, random-access frame seeking, and trimmed/cropped clip export.
"""
from typing import Tuple, Optional, Generator, Callable, Dict, Any
import cv2
import numpy as np
import os

class FrameReader:
    """Manages OpenCV VideoCapture instance for precise frame seeking and batch operations."""

    def __init__(self, video_path: Optional[str] = None):
        self.video_path: Optional[str] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.fps: float = 30.0
        self.frame_count: int = 0
        self.width: int = 0
        self.height: int = 0
        self.duration_ms: int = 0

        if video_path:
            self.open(video_path)

    def open(self, video_path: str) -> bool:
        """Open a video file and extract metadata."""
        self.close()
        if not os.path.exists(video_path):
            return False

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            self.cap = None
            return False

        self.video_path = video_path
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0 or np.isnan(self.fps):
            self.fps = 30.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration_ms = int((self.frame_count / self.fps) * 1000.0) if self.fps > 0 else 0
        return True

    def is_open(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def get_frame(self, frame_idx: int) -> Tuple[bool, Optional[np.ndarray]]:
        """Seek directly to a specific frame number and read it."""
        if not self.is_open():
            return False, None
        frame_idx = max(0, min(frame_idx, self.frame_count - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        success, frame = self.cap.read()
        return success, frame

    def iterate_range(
        self,
        start_frame: int,
        end_frame: int
    ) -> Generator[Tuple[int, np.ndarray], None, None]:
        """Generator yielding (frame_index, frame) across the specified range."""
        if not self.is_open():
            return
        start = max(0, min(start_frame, self.frame_count - 1))
        end = max(start, min(end_frame, self.frame_count - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        current = start
        while current <= end:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                break
            yield current, frame
            current += 1

    def export_clip(
        self,
        output_path: str,
        start_frame: int,
        end_frame: int,
        roi: Optional[Tuple[int, int, int, int]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        Export a trimmed and optionally cropped video to an MP4 file.
        """
        if not self.is_open():
            return False

        start = max(0, min(start_frame, self.frame_count - 1))
        end = max(start, min(end_frame, self.frame_count - 1))
        total_frames_to_write = end - start + 1
        if total_frames_to_write <= 0:
            return False

        # Determine output dimensions
        out_w = roi[2] if roi else self.width
        out_h = roi[3] if roi else self.height

        # Ensure dimensions are even numbers for H264/mp4v codec compatibility
        out_w = out_w - (out_w % 2)
        out_h = out_h - (out_h % 2)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, self.fps, (out_w, out_h))

        if not writer.isOpened():
            # Fallback to AVI / XVID if mp4v is not supported on the system
            alt_path = os.path.splitext(output_path)[0] + ".avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            writer = cv2.VideoWriter(alt_path, fourcc, self.fps, (out_w, out_h))
            if not writer.isOpened():
                return False

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        written = 0

        for frame_idx in range(start, end + 1):
            ret, frame = self.cap.read()
            if not ret or frame is None:
                break
            if roi:
                rx, ry, rw, rh = roi
                frame = frame[ry:ry+rh, rx:rx+rw]
            # Resize slightly if odd pixel was trimmed
            if frame.shape[1] != out_w or frame.shape[0] != out_h:
                frame = cv2.resize(frame, (out_w, out_h))

            writer.write(frame)
            written += 1
            if progress_callback:
                progress_callback(written, total_frames_to_write)

        writer.release()
        return True

    def close(self):
        """Release video capture resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.video_path = None
