"""
Image processing pipeline for bat pupil video enhancement.
Includes CLAHE, Gamma, Brightness/Contrast, Inversion, and Glint Masking.
"""
from typing import Tuple, Optional, Dict, Any
import cv2
import numpy as np

class VideoProcessor:
    """Provides fast OpenCV image transformations and enhancements for bat eye videos."""

    @staticmethod
    def adjust_gamma(image: np.ndarray, gamma: float = 1.0) -> np.ndarray:
        """Apply non-linear gamma correction via lookup table."""
        if abs(gamma - 1.0) < 0.01:
            return image
        gamma = max(0.1, min(gamma, 3.0))
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
        return cv2.LUT(image, table)

    @staticmethod
    def apply_clahe(image: np.ndarray, clip_limit: float = 2.0, grid_size: int = 8) -> np.ndarray:
        """Apply Contrast Limited Adaptive Histogram Equalization to boost local pupil boundaries."""
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
        if len(image.shape) == 2:
            eq = clahe.apply(image)
            # Blend 70% CLAHE + 30% original and keep non-glint tissue from saturating to 255
            blended = cv2.addWeighted(eq, 0.70, image, 0.30, 0)
            non_glint = image < 230
            blended[non_glint] = np.minimum(blended[non_glint], 232)
            return blended
        elif len(image.shape) == 3:
            # Convert to LAB color space, apply CLAHE to L-channel, and convert back
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l_clahe = clahe.apply(l)
            l_blended = cv2.addWeighted(l_clahe, 0.70, l, 0.30, 0)
            non_glint = l < 230
            l_blended[non_glint] = np.minimum(l_blended[non_glint], 232)
            merged = cv2.merge((l_blended, a, b))
            return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        return image

    @staticmethod
    def crop_roi(image: np.ndarray, roi: Optional[Tuple[int, int, int, int]]) -> np.ndarray:
        """Extract rectangular region [x, y, w, h] from image."""
        if roi is None:
            return image
        x, y, w, h = roi
        img_h, img_w = image.shape[:2]
        x1 = max(0, min(x, img_w - 1))
        y1 = max(0, min(y, img_h - 1))
        x2 = max(x1 + 1, min(x + w, img_w))
        y2 = max(y1 + 1, min(y + h, img_h))
        return image[y1:y2, x1:x2].copy()

    @classmethod
    def process_frame(
        cls,
        frame: np.ndarray,
        params: Dict[str, Any],
        roi: Optional[Tuple[int, int, int, int]] = None,
        apply_crop: bool = False
    ) -> np.ndarray:
        """
        Run the full enhancement pipeline on a video frame according to configuration parameters.
        Returns the processed BGR or RGB image.
        """
        if frame is None or frame.size == 0:
            return frame

        out = frame.copy()

        # Step 1: Crop to bat head if crop view is active
        if apply_crop and roi is not None:
            out = cls.crop_roi(out, roi)

        brightness = params.get("brightness", 0)
        contrast = params.get("contrast", 1.0)
        gamma = params.get("gamma", 1.0)
        clahe_enabled = params.get("clahe_enabled", False)
        clahe_clip = params.get("clahe_clip", 2.0)
        clahe_grid = params.get("clahe_grid", 8)
        invert = params.get("invert", False)
        grayscale = params.get("grayscale", False)
        show_threshold = params.get("show_threshold", False)
        threshold_val = params.get("threshold_val", 45)

        # Preserve original specular glint mask (>= 238) so enhancements never wash out the IR glint
        orig_gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY) if len(out.shape) == 3 else out
        non_specular = orig_gray < 232

        # Step 2: Median-Pivoted Brightness and Contrast (darkens pupil < median, brightens iris > median)
        if brightness != 0 or abs(contrast - 1.0) > 0.01:
            orig_g = orig_gray.astype(np.float32)
            pivot = float(np.median(orig_g))
            target_g = (orig_g - pivot) * float(contrast) + pivot + float(brightness)
            target_g = np.clip(target_g, 0.0, 255.0)
            target_g[non_specular] = np.minimum(target_g[non_specular], 232.0)
            if len(out.shape) == 3:
                scale = target_g / np.maximum(orig_g, 1.0)
                out = np.clip(out.astype(np.float32) * scale[:, :, np.newaxis], 0, 255).astype(np.uint8)
            else:
                out = target_g.astype(np.uint8)

        # Step 3: Gamma Correction
        if abs(gamma - 1.0) > 0.01:
            out = cls.adjust_gamma(out, gamma)

        # Step 4: CLAHE (boosts IR bat eye details)
        if clahe_enabled:
            out = cls.apply_clahe(out, clip_limit=clahe_clip, grid_size=int(clahe_grid))

        # Step 5: Invert
        if invert:
            out = cv2.bitwise_not(out)

        # Step 6: Grayscale
        if grayscale:
            if len(out.shape) == 3:
                gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
                out = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # Step 7: Orientation (Rotation and Flipping for hanging bats)
        rotation = params.get("rotation", 0)
        if rotation == 90:
            out = cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            out = cv2.rotate(out, cv2.ROTATE_180)
        elif rotation == 270:
            out = cv2.rotate(out, cv2.ROTATE_90_COUNTERCLOCKWISE)

        flip_h = params.get("flip_h", False)
        flip_v = params.get("flip_v", False)
        if flip_h and flip_v:
            out = cv2.flip(out, -1)
        elif flip_h:
            out = cv2.flip(out, 1)
        elif flip_v:
            out = cv2.flip(out, 0)

        # Step 8: Threshold preview overlay
        if show_threshold:
            if len(out.shape) == 3:
                gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
            else:
                gray = out
            # Pupil is dark in IR footage, so pixels <= threshold_val are pupil candidates
            _, binary_mask = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY_INV)
            colored_mask = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            # Tint detected pupil pixels with bright cyan (B=255, G=255, R=0)
            colored_mask[binary_mask > 0] = [255, 255, 0]
            out = cv2.addWeighted(out if len(out.shape) == 3 else cv2.cvtColor(out, cv2.COLOR_GRAY2BGR), 0.5, colored_mask, 0.5, 0)

        return out
