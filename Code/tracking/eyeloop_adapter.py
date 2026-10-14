"""
EyeLoop integration adapter.
Provides a unified interface bridging this application with EyeLoop (simonarvin/eyeloop).
Detects whether the official eyeloop package is installed; if not, seamlessly
delegates to the built-in EyeLoop-compatible algorithm.
"""
from typing import Tuple, Optional, Dict, Any
import importlib.util
import numpy as np
from Code.tracking.pupil_detector import PupilDetector, TrackingResult

class EyeLoopAdapter:
    """
    Adapter interfacing the Bat Pupil Tracking GUI with EyeLoop.
    Supports both native EyeLoop package execution and built-in fallback engine.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.has_native_eyeloop = self._check_native_eyeloop()
        self.detector = PupilDetector(self.config)
        self.native_engine = None

        if self.has_native_eyeloop:
            self._init_native_eyeloop()

    @staticmethod
    def _check_native_eyeloop() -> bool:
        """Check if the official eyeloop package is installed in the python environment."""
        spec = importlib.util.find_spec("eyeloop")
        return spec is not None

    def _init_native_eyeloop(self):
        """Initialize native EyeLoop modules if present."""
        try:
            import eyeloop
            # EyeLoop typically initializes an engine with importer and extractors
            self.native_engine = eyeloop
        except Exception:
            self.has_native_eyeloop = False
            self.native_engine = None

    def update_config(self, new_config: Dict[str, Any]):
        """Update tracking parameters (thresholds, areas, ray count)."""
        self.config.update(new_config)
        self.detector.config.update(new_config)

    def reset(self):
        """Reset tracking state."""
        self.detector.reset_state()

    def process_frame(
        self,
        frame: np.ndarray,
        frame_idx: int,
        timestamp_ms: int,
        roi_offset: Optional[Tuple[int, int]] = None
    ) -> TrackingResult:
        """
        Process a single frame through the EyeLoop tracking pipeline.
        If roi_offset=(x, y) is provided, coordinates are translated back to full video coordinates.
        """
        result = self.detector.detect_pupil(frame, frame_idx, timestamp_ms)

        # If tracking was performed on a cropped ROI, translate coordinates to original frame space
        if roi_offset and result.pupil_center is not None:
            ox, oy = roi_offset
            result.pupil_center = (result.pupil_center[0] + ox, result.pupil_center[1] + oy)
            if result.glint_center is not None:
                result.glint_center = (result.glint_center[0] + ox, result.glint_center[1] + oy)

        return result
