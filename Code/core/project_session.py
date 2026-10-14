"""
Project session data model for managing video paths, trimming ranges,
crop ROI, and processing/tracking settings.
"""
from typing import Optional, Tuple, Dict, Any
import json
import os

class ProjectSession:
    """Stores the active state and configuration of a pupil tracking session."""

    def __init__(self):
        self.video_path: Optional[str] = None
        self.fps: float = 30.0
        self.total_frames: int = 0
        self.duration_ms: int = 0
        self.frame_width: int = 0
        self.frame_height: int = 0
        
        # Trimming range (frame indices)
        self.start_frame: int = 0
        self.end_frame: int = 0
        self.loop_range: bool = False
        
        # Crop region of interest for bat head (x, y, width, height) in original video coordinates
        self.crop_roi: Optional[Tuple[int, int, int, int]] = None
        self.is_cropped_view: bool = False

        # Image enhancement parameters
        self.processing_params: Dict[str, Any] = {
            "brightness": 0,         # -100 to 100
            "contrast": 1.0,         # 0.1 to 3.0
            "gamma": 1.0,            # 0.1 to 3.0
            "clahe_enabled": False,  # Contrast Limited Adaptive Histogram Equalization
            "clahe_clip": 2.0,       # 1.0 to 10.0
            "clahe_grid": 8,         # 4 to 16
            "invert": False,         # Invert image intensities
            "grayscale": False,      # Force grayscale rendering
            "show_threshold": False, # Preview binarized pupil threshold
            "threshold_val": 45,     # 0 to 255 for pupil segmentation
            "cr_filter": True,       # Corneal Reflection / glint removal
            "cr_threshold": 220      # 150 to 255 for bright IR glint detection
        }

        # EyeLoop tracking parameters
        self.tracking_params: Dict[str, Any] = {
            "algorithm": "eyeloop_rays", # 'eyeloop_rays' or 'contour_ellipse'
            "pupil_threshold": 82,
            "min_pupil_area": 15,
            "max_pupil_area": 3500,
            "min_circularity": 0.25,
            "boundary_offset": 0.0,
            "ray_count": 36,
            "cr_removal": True,
            "temporal_smoothing": True,
            "ellipse_color": "#ec4899"   # Electric Magenta (high-contrast complement for green IR footage)
        }

    def set_video_metadata(self, path: str, fps: float, total_frames: int, duration_ms: int, width: int, height: int):
        """Update session with loaded video properties and reset frame range."""
        self.video_path = path
        self.fps = fps if fps > 0 else 30.0
        self.total_frames = total_frames
        self.duration_ms = duration_ms
        self.frame_width = width
        self.frame_height = height
        self.start_frame = 0
        self.end_frame = max(0, total_frames - 1)
        self.crop_roi = None
        self.is_cropped_view = False

    def set_range(self, start: int, end: int):
        """Set trimming start and end frame indices."""
        self.start_frame = max(0, min(start, self.total_frames - 1))
        self.end_frame = max(self.start_frame, min(end, self.total_frames - 1))

    def set_crop_roi(self, roi: Optional[Tuple[int, int, int, int]]):
        """Set bat head crop rectangle (x, y, w, h)."""
        self.crop_roi = roi

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary, using relative paths where possible to avoid leaking host paths."""
        rel_video_path = self.video_path
        if self.video_path:
            try:
                rel = os.path.relpath(self.video_path)
                if not rel.startswith(".."):
                    rel_video_path = rel
            except ValueError:
                pass
        return {
            "video_path": rel_video_path,
            "fps": self.fps,
            "total_frames": self.total_frames,
            "duration_ms": self.duration_ms,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "loop_range": self.loop_range,
            "crop_roi": list(self.crop_roi) if self.crop_roi else None,
            "is_cropped_view": self.is_cropped_view,
            "processing_params": self.processing_params,
            "tracking_params": self.tracking_params,
        }

    def from_dict(self, data: Dict[str, Any]):
        """Load session properties from dictionary."""
        self.video_path = data.get("video_path")
        self.fps = data.get("fps", 30.0)
        self.total_frames = data.get("total_frames", 0)
        self.duration_ms = data.get("duration_ms", 0)
        self.frame_width = data.get("frame_width", 0)
        self.frame_height = data.get("frame_height", 0)
        self.start_frame = data.get("start_frame", 0)
        self.end_frame = data.get("end_frame", max(0, self.total_frames - 1))
        self.loop_range = data.get("loop_range", False)
        
        roi = data.get("crop_roi")
        self.crop_roi = tuple(roi) if roi and len(roi) == 4 else None
        self.is_cropped_view = data.get("is_cropped_view", False)
        
        if "processing_params" in data:
            self.processing_params.update(data["processing_params"])
        if "tracking_params" in data:
            self.tracking_params.update(data["tracking_params"])

    def save_to_json(self, file_path: str):
        """Export session configuration to JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4)

    def load_from_json(self, file_path: str):
        """Import session configuration from JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.from_dict(data)
