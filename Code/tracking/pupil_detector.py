"""
Bat pupil and corneal reflection (glint) tracking engine.
Implements the core algorithms of EyeLoop (Arvin et al.):
1. Corneal Reflection (CR) / Glint isolation and inpainting
2. Inner dark-pupil segmentation with darkness and circularity scoring
3. EyeLoop ray-projection walk-out boundary detection and ellipse fitting
4. Temporal smoothing and blink/occlusion detection
"""
from typing import Tuple, Optional, Dict, Any, List
import math
import cv2
import numpy as np

class TrackingResult:
    """Stores the tracking metrics for a single frame."""
    def __init__(
        self,
        frame_idx: int,
        timestamp_ms: int,
        pupil_center: Optional[Tuple[float, float]] = None,
        major_axis: float = 0.0,
        minor_axis: float = 0.0,
        angle: float = 0.0,
        area: float = 0.0,
        aspect_ratio: float = 1.0,
        glint_center: Optional[Tuple[float, float]] = None,
        confidence: float = 0.0,
        blink: bool = False,
        boundary_points: Optional[np.ndarray] = None
    ):
        self.frame_idx = frame_idx
        self.timestamp_ms = timestamp_ms
        self.pupil_center = pupil_center
        self.major_axis = major_axis
        self.minor_axis = minor_axis
        self.angle = angle
        self.area = area
        self.aspect_ratio = aspect_ratio
        self.glint_center = glint_center
        self.confidence = confidence
        self.blink = blink
        self.boundary_points = boundary_points

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame": self.frame_idx,
            "timestamp_ms": self.timestamp_ms,
            "time_sec": round(self.timestamp_ms / 1000.0, 4),
            "pupil_x": round(self.pupil_center[0], 2) if self.pupil_center else None,
            "pupil_y": round(self.pupil_center[1], 2) if self.pupil_center else None,
            "major_axis": round(self.major_axis, 2),
            "minor_axis": round(self.minor_axis, 2),
            "diameter_avg": round((self.major_axis + self.minor_axis) / 2.0, 2),
            "angle_deg": round(self.angle, 2),
            "area_px": round(self.area, 2),
            "aspect_ratio": round(self.aspect_ratio, 3),
            "glint_x": round(self.glint_center[0], 2) if self.glint_center else None,
            "glint_y": round(self.glint_center[1], 2) if self.glint_center else None,
            "confidence": round(self.confidence, 3),
            "blink": self.blink
        }

class PupilDetector:
    """
    EyeLoop-compatible pupil tracking detector.
    Extracts pupil ellipse parameters and corneal reflection coordinates.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            "algorithm": "eyeloop_rays", # 'eyeloop_rays' or 'contour_ellipse'
            "pupil_threshold": 82,
            "min_pupil_area": 15,
            "max_pupil_area": 3500,      # Constrained to true pupil range
            "min_circularity": 0.20,
            "cr_removal": True,
            "cr_threshold": 185,
            "max_glint_area": 140,       # Glints are small specular reflections
            "cr_dilate_radius": 4,
            "ray_count": 36,
            "max_ray_radius": 60,
            "boundary_offset": 0.0,      # Sub-pixel radial offset adjustment (-5.0 to +5.0 px)
            "temporal_smoothing": True,
            "smoothing_factor": 0.35
        }
        if config:
            self.config.update(config)

        # Previous frame state for temporal continuity
        self.prev_pupil_center: Optional[Tuple[float, float]] = None
        self.prev_axes: Optional[Tuple[float, float]] = None

    def reset_state(self):
        """Reset temporal state between videos or video seeks."""
        self.prev_pupil_center = None
        self.prev_axes = None

    def detect_corneal_reflection(
        self,
        gray: np.ndarray,
        pupil_hint: Optional[Tuple[float, float]] = None
    ) -> Tuple[Optional[Tuple[float, float]], np.ndarray]:
        """
        Locate bright infrared LED corneal reflection (glint) on the cornea and generate
        a halo-complete inpainting mask so bright glint halos do not shrink the pupil contour.
        """
        h, w = gray.shape
        cr_thresh_val = self.config.get("cr_threshold", 185)
        max_glint_area = self.config.get("max_glint_area", 140)

        # Local background estimation to catch both saturated (>200) and moderate (165-199) IR glints
        ksize = min(25, (min(h, w) // 3) | 1)
        if ksize < 5:
            ksize = 5
        local_bg = cv2.GaussianBlur(gray, (ksize, ksize), 0)
        diff = gray.astype(np.int16) - local_bg.astype(np.int16)

        p98 = float(np.percentile(gray, 98.5))
        adaptive_cr_thresh = max(160, min(cr_thresh_val, int(p98 - 5)))
        cr_peaks = ((gray >= adaptive_cr_thresh) & (diff >= 24)) | (gray >= max(210, cr_thresh_val))
        cr_binary = (cr_peaks.astype(np.uint8)) * 255

        contours, _ = cv2.findContours(cr_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        glint_center = None
        selected_glint_mask = np.zeros_like(gray, dtype=np.uint8)

        # If no pupil_hint is available yet, estimate the darkest interior region that is enclosed by brighter tissue
        ocular_hint = pupil_hint
        if ocular_hint is None and h > 16 and w > 16:
            blur_dark = cv2.GaussianBlur(gray, (9, 9), 0)
            bg_wide = cv2.GaussianBlur(gray, (31, 31), 0)
            # True eye is a local dark region inside a brighter head (bg_wide > median)
            dip_map = bg_wide.astype(np.float32) - blur_dark.astype(np.float32)
            margin_y, margin_x = max(6, h // 7), max(6, w // 7)
            roi_dip = dip_map[margin_y:h - margin_y, margin_x:w - margin_x]
            if roi_dip.size > 0:
                max_idx = int(np.argmax(roi_dip))
                dy, dx = divmod(max_idx, roi_dip.shape[1])
                ocular_hint = (float(dx + margin_x), float(dy + margin_y))

        if contours:
            valid_cr = []
            for c in contours:
                area = cv2.contourArea(c)
                if 1 <= area <= max_glint_area:
                    bx, by, bw, bh = cv2.boundingRect(c)
                    # Reject specular noise right on the border of the crop
                    if bx <= 4 or by <= 4 or (bx + bw) >= w - 4 or (by + bh) >= h - 4:
                        continue
                    m = cv2.moments(c)
                    if m["m00"] > 0:
                        gx = m["m10"] / m["m00"]
                        gy = m["m01"] / m["m00"]
                    else:
                        gx = bx + bw / 2.0
                        gy = by + bh / 2.0

                    # Check peak prominence above local background and proximity to dark ocular tissue
                    ix, iy = min(w - 1, max(0, int(round(gx)))), min(h - 1, max(0, int(round(gy))))
                    eye_patch = gray[max(0, iy - 12):min(h, iy + 13), max(0, ix - 12):min(w, ix + 13)]
                    if eye_patch.size > 0 and float(np.percentile(eye_patch, 15)) > float(np.percentile(gray, 35)) + 6.0:
                        continue
                    prominence = float(diff[iy, ix])
                    dist = 0.0
                    if ocular_hint is not None:
                        dist = math.hypot(gx - ocular_hint[0], gy - ocular_hint[1])
                    valid_cr.append(((gx, gy), area, dist, prominence, c))

            if valid_cr:
                if ocular_hint is not None:
                    close_glints = [g for g in valid_cr if g[2] <= max(45.0, min(w, h) * 0.35)]
                    if close_glints:
                        # Sort by distance to ocular hint, weighted by glint prominence
                        close_glints.sort(key=lambda g: g[2] - 0.35 * g[3])
                        best_g = close_glints[0]
                    else:
                        valid_cr.sort(key=lambda g: g[2] - 0.35 * g[3])
                        best_g = valid_cr[0]
                else:
                    valid_cr.sort(key=lambda g: math.hypot(g[0][0] - w / 2.0, g[0][1] - h / 2.0))
                    best_g = valid_cr[0]

                glint_center = best_g[0]
                cv2.drawContours(selected_glint_mask, [best_g[4]], -1, 255, -1)

        if glint_center is None or cv2.countNonZero(selected_glint_mask) == 0:
            return None, np.zeros_like(gray, dtype=np.uint8)

        # Expand mask to cover the unsaturated optical halo around the primary glint (3px radius)
        radius = max(2, int(self.config.get("cr_dilate_radius", 3)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        cr_mask = cv2.dilate(selected_glint_mask, kernel)

        # Include immediately adjacent halo pixels that are still significantly brighter than local background
        halo_zone = cv2.dilate(cr_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        halo_pixels = (halo_zone > 0) & (diff >= 12)
        cr_mask[halo_pixels] = 255

        return glint_center, cr_mask

    @staticmethod
    def _normalize_ellipse(
        ellipse: Tuple[Tuple[float, float], Tuple[float, float], float]
    ) -> Tuple[float, float, float, float, float]:
        """
        Convert cv2.fitEllipse output ((cx, cy), (w, h), angle) into a consistent
        (cx, cy, major_axis, minor_axis, angle_deg) where angle_deg is ALWAYS the
        orientation of major_axis.
        """
        (cx, cy), (axis1, axis2), angle = ellipse
        if axis1 >= axis2:
            major_axis = float(axis1)
            minor_axis = float(axis2)
            norm_angle = float(angle) % 180.0
        else:
            major_axis = float(axis2)
            minor_axis = float(axis1)
            norm_angle = (float(angle) + 90.0) % 180.0
        return float(cx), float(cy), major_axis, minor_axis, norm_angle

    def eyeloop_ray_walkout(
        self,
        gray: np.ndarray,
        seed_x: float,
        seed_y: float,
        min_r: int = 2,
        max_r: int = 50,
        num_rays: int = 36,
        cr_mask: Optional[np.ndarray] = None,
        expected_r: Optional[float] = None,
        iris_hint: Optional[float] = None
    ) -> Tuple[Optional[Tuple[Tuple[float, float], Tuple[float, float], float]], List[Tuple[float, float]]]:
        """
        Sub-pixel EyeLoop radial ray-casting edge detector:
        1. Samples radial intensity profiles at 0.5px bilinear steps from (seed_x, seed_y).
        2. Smooths with edge-replicated padding (avoiding zero-padding boundary artifacts).
        3. Identifies the true pupil-to-iris transition using both radial gradient peak and
           local core-to-iris adaptive threshold crossing.
        4. Rejects glint-corrupted and outlier rays via MAD (Median Absolute Deviation) and
           iterative ellipse residual filtering.
        """
        h, w = gray.shape
        step = 0.5
        max_r = max(min_r + 6, min(max_r, int(min(w, h) * 0.48)))

        # Estimate core pupil intensity around seed center
        y0, x0 = int(round(seed_y)), int(round(seed_x))
        r_core = 3
        patch = gray[max(0, y0 - r_core):min(h, y0 + r_core + 1), max(0, x0 - r_core):min(w, x0 + r_core + 1)]
        core_intensity = float(np.percentile(patch, 30)) if patch.size > 0 else float(gray[min(h - 1, max(0, y0)), min(w - 1, max(0, x0))])

        # User threshold sensitivity adjustment: default is 82.
        # Higher pupil_threshold slightly expands the transition fraction toward the iris; lower tightens it.
        user_thresh = float(self.config.get("pupil_threshold", 82))
        thresh_bias = np.clip((user_thresh - 82.0) / 150.0, -0.18, 0.18)
        transition_frac = float(np.clip(0.68 + thresh_bias, 0.45, 0.84))
        boundary_offset = float(self.config.get("boundary_offset", 0.0))

        # Dilate glint mask slightly so rays grazing the glint halo are flagged
        glint_avoid = None
        if cr_mask is not None and cv2.countNonZero(cr_mask) > 0:
            glint_avoid = cv2.dilate(cr_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

        ray_angles = []
        ray_radii = []
        ray_glint_hit = []

        radii_grid = np.arange(0.0, float(max_r) + step, step, dtype=np.float32)
        min_idx = max(2, int(round(min_r / step)))

        for i in range(num_rays):
            angle = 2.0 * math.pi * i / num_rays
            dx = math.cos(angle)
            dy = math.sin(angle)

            xs = seed_x + radii_grid * dx
            ys = seed_y + radii_grid * dy

            # Keep only steps inside image bounds
            valid_mask = (xs >= 1.0) & (xs < w - 2.0) & (ys >= 1.0) & (ys < h - 2.0)
            if not np.all(valid_mask):
                first_invalid = int(np.argmin(valid_mask))
                if first_invalid <= min_idx + 6:
                    continue
                xs = xs[:first_invalid]
                ys = ys[:first_invalid]
            cur_steps = len(xs)
            if cur_steps <= min_idx + 6:
                continue

            # Bilinear interpolation along the ray
            map_x = xs.reshape(1, -1).astype(np.float32)
            map_y = ys.reshape(1, -1).astype(np.float32)
            sampled = cv2.remap(gray, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).ravel().astype(np.float32)

            # Check if ray intersects the corneal reflection mask
            hit_glint_idx = None
            if glint_avoid is not None:
                gx_idx = np.clip(np.round(xs).astype(np.int32), 0, w - 1)
                gy_idx = np.clip(np.round(ys).astype(np.int32), 0, h - 1)
                glint_hits = np.where(glint_avoid[gy_idx, gx_idx] > 0)[0]
                glint_hits = glint_hits[glint_hits >= min_idx]
                if len(glint_hits) > 0:
                    hit_glint_idx = int(glint_hits[0])

            # Edge-replicated smoothing (prevents the zero-padding jump at index 0!)
            padded = np.pad(sampled, 2, mode="edge")
            smoothed = np.convolve(padded, [0.1, 0.2, 0.4, 0.2, 0.1], mode="valid")

            # Central difference derivative dI / dr (per pixel)
            grads = np.gradient(smoothed) / step

            # Estimate local iris plateau intensity in the immediate circum-pupillary ring
            iris_start = min(cur_steps - 1, max(min_idx + 3, int(round(5.5 / step))))
            iris_end = min(cur_steps, int(round(18.0 / step)))
            if expected_r is not None and expected_r > 3.5:
                iris_start = min(cur_steps - 1, max(min_idx + 2, int(round((expected_r * 0.85) / step))))
                iris_end = min(cur_steps, int(round((expected_r * 1.55 + 3.5) / step)))

            if iris_end <= iris_start + 2:
                iris_end = cur_steps

            ray_window = smoothed[iris_start:iris_end]
            # Exclude bright specular/eyelid jumps when estimating iris intensity
            non_bright = ray_window[ray_window < core_intensity + 55.0]
            if len(non_bright) >= 3:
                iris_intensity = float(np.percentile(non_bright, 58))
            else:
                iris_intensity = float(np.median(ray_window)) if len(ray_window) > 0 else (core_intensity + 16.0)

            # Constrain iris_intensity with the measured immediate iris ring around the seed contour
            # so bright eyelids/fur further out never inflate target_intensity above the iris plateau
            if iris_hint is not None and iris_hint > core_intensity + 4.0:
                iris_intensity = float(np.clip(
                    0.55 * iris_intensity + 0.45 * iris_hint,
                    core_intensity + 5.0,
                    iris_hint + 7.0
                ))

            contrast = iris_intensity - core_intensity
            if contrast < 4.0:
                if iris_hint is not None and (iris_hint - core_intensity) >= 4.0:
                    iris_intensity = iris_hint
                    contrast = iris_intensity - core_intensity
                else:
                    continue

            # Target intensity at the outer pupil boundary (where dark pupil meets iris plateau)
            target_intensity = core_intensity + transition_frac * contrast
            max_pupil_foot = core_intensity + 0.82 * contrast

            # Search limit for the pupil boundary (before outer iris-to-eyelid border)
            max_pupil_r = 20.0
            if expected_r is not None and expected_r > 3.5:
                max_pupil_r = max(12.0, min(32.0, expected_r * 1.75 + 3.5))
            search_end = min(cur_steps - 3, int(round(max_pupil_r / step)))

            # Find the true pupil-to-iris exit:
            # Require that after crossing target_intensity, the profile remains in the iris
            # for at least ~2.5 pixels (avoiding brief internal lens reflexes inside the pupil).
            cross_idx = None
            sustain_steps = max(3, int(round(2.5 / step)))
            for k in range(min_idx, search_end):
                if smoothed[k] <= target_intensity and smoothed[k + 1] >= target_intensity:
                    ahead = smoothed[k + 1:min(cur_steps, k + 1 + sustain_steps)]
                    if len(ahead) >= 2:
                        if float(np.min(ahead)) >= target_intensity - 2.0 and float(np.mean(ahead)) >= core_intensity + 0.50 * contrast:
                            cross_idx = k
                            break

            # Fallback if sustain check was too strict near ray end
            if cross_idx is None:
                for k in range(min_idx, search_end):
                    if smoothed[k] <= target_intensity and smoothed[k + 1] >= target_intensity:
                        lookahead = smoothed[k + 1:min(cur_steps, k + 5)]
                        if float(np.mean(lookahead)) >= core_intensity + 0.45 * contrast:
                            cross_idx = k
                            break

            # Also find the local positive gradient peak near the sustained crossing
            grad_idx = None
            min_grad = max(0.8, 0.08 * contrast)
            g_start = max(min_idx, (cross_idx - 4) if cross_idx is not None else min_idx)
            g_end = min(search_end, (cross_idx + 5) if cross_idx is not None else search_end)
            for k in range(g_start, g_end):
                if grads[k] >= min_grad and grads[k] >= grads[k - 1] and grads[k] >= grads[k + 1]:
                    foot_val = smoothed[max(0, k - 2)]
                    top_val = smoothed[min(cur_steps - 1, k + 3)]
                    if foot_val <= max_pupil_foot and top_val >= core_intensity + 0.45 * contrast:
                        grad_idx = k
                        break

            if cross_idx is None and grad_idx is None:
                continue

            # Compute sub-pixel radius from crossing and gradient peak
            r_cross = None
            if cross_idx is not None:
                denom = float(smoothed[cross_idx + 1] - smoothed[cross_idx])
                frac = (target_intensity - float(smoothed[cross_idx])) / denom if abs(denom) > 1e-5 else 0.0
                r_cross = (cross_idx + float(np.clip(frac, 0.0, 1.0))) * step

            r_grad = None
            if grad_idx is not None:
                g_m1 = float(grads[grad_idx - 1])
                g_0 = float(grads[grad_idx])
                g_p1 = float(grads[grad_idx + 1])
                denom = g_m1 - 2.0 * g_0 + g_p1
                delta = 0.5 * (g_m1 - g_p1) / denom if abs(denom) > 1e-5 else 0.0
                # Outer pupil margin is ~0.85px beyond the steepest midpoint inflection
                r_grad = (grad_idx + float(np.clip(delta, -0.5, 0.5))) * step + 0.85

            if r_cross is not None and r_grad is not None:
                if abs(r_cross - r_grad) <= 2.5:
                    r_est = 0.70 * max(r_cross, r_grad) + 0.30 * min(r_cross, r_grad)
                else:
                    r_est = r_cross
            elif r_cross is not None:
                r_est = r_cross
            else:
                r_est = r_grad

            r_est = max(float(min_r), r_est + boundary_offset)

            is_glint_ray = False
            if hit_glint_idx is not None and abs(r_est / step - hit_glint_idx) <= 4.0:
                is_glint_ray = True

            ray_angles.append(angle)
            ray_radii.append(r_est)
            ray_glint_hit.append(is_glint_ray)

        if len(ray_radii) < 6:
            return None, []

        angles_arr = np.array(ray_angles, dtype=np.float64)
        radii_arr = np.array(ray_radii, dtype=np.float64)
        glint_arr = np.array(ray_glint_hit, dtype=bool)

        # Stage 1 Outlier Rejection: Median & MAD filtering on radii (preferring non-glint rays)
        clean_pool = radii_arr[~glint_arr] if np.sum(~glint_arr) >= 6 else radii_arr
        med_r = float(np.percentile(clean_pool, 60))
        mad_r = float(np.median(np.abs(clean_pool - med_r))) * 1.4826
        tol_r = max(2.5, min(med_r * 0.38, 2.2 * mad_r + 1.4))

        inlier_mask = (np.abs(radii_arr - med_r) <= tol_r) & (~glint_arr | (radii_arr >= med_r - 1.2))
        if np.sum(inlier_mask) < 5:
            inlier_mask = np.abs(radii_arr - med_r) <= max(3.5, med_r * 0.45)

        inlier_angles = angles_arr[inlier_mask]
        inlier_radii = radii_arr[inlier_mask]

        edge_pts = [
            (float(seed_x + r * math.cos(a)), float(seed_y + r * math.sin(a)))
            for a, r in zip(inlier_angles, inlier_radii)
        ]

        if len(edge_pts) >= 5:
            pts = np.array(edge_pts, dtype=np.float32).reshape((-1, 1, 2))
            try:
                ellipse1 = cv2.fitEllipse(pts)
                # Stage 2 Outlier Rejection: Refine ellipse by trimming points with large radial residual
                ecx, ecy, maj, min_ax, eang = self._normalize_ellipse(ellipse1)
                if maj > 0 and min_ax > 0:
                    cos_a = math.cos(math.radians(eang))
                    sin_a = math.sin(math.radians(eang))
                    a_semi = maj / 2.0
                    b_semi = min_ax / 2.0

                    refined_pts = []
                    for px, py in edge_pts:
                        dx_e = px - ecx
                        dy_e = py - ecy
                        ux = dx_e * cos_a + dy_e * sin_a
                        uy = -dx_e * sin_a + dy_e * cos_a
                        norm_d = math.hypot(ux / max(1e-3, a_semi), uy / max(1e-3, b_semi))
                        approx_r = math.hypot(dx_e, dy_e)
                        radial_err = abs(approx_r * (1.0 - 1.0 / max(1e-3, norm_d))) if norm_d > 0 else 99.0
                        if radial_err <= max(1.8, 0.18 * ((a_semi + b_semi) / 2.0)):
                            refined_pts.append((px, py))

                    if len(refined_pts) >= 5:
                        pts2 = np.array(refined_pts, dtype=np.float32).reshape((-1, 1, 2))
                        ellipse2 = cv2.fitEllipse(pts2)
                        return ellipse2, refined_pts
                return ellipse1, edge_pts
            except Exception:
                pass

        return None, edge_pts

    def detect_pupil(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
        timestamp_ms: int = 0
    ) -> TrackingResult:
        """
        Execute pupil detection on the input frame (crop or full).
        """
        if frame is None or frame.size == 0:
            return TrackingResult(frame_idx, timestamp_ms, blink=True, confidence=0.0)

        # Ensure single-channel grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        h, w = gray.shape
        if h < 10 or w < 10:
            return TrackingResult(frame_idx, timestamp_ms, blink=True, confidence=0.0)

        # Step 1: Detect and inpaint corneal reflection glint (including its bright halo)
        glint_center = None
        cr_mask = np.zeros_like(gray, dtype=np.uint8)
        if self.config.get("cr_removal", True):
            glint_center, cr_mask = self.detect_corneal_reflection(gray, self.prev_pupil_center)
            if cv2.countNonZero(cr_mask) > 0:
                perim_ring = cv2.subtract(
                    cv2.dilate(cr_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))),
                    cr_mask
                )
                ring_vals = gray[perim_ring > 0]
                if ring_vals.size > 0:
                    fill_val = int(np.percentile(ring_vals, 22))
                    gray_filled = gray.copy()
                    gray_filled[cr_mask > 0] = fill_val
                    gray_inpainted = cv2.inpaint(gray, cr_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
                    gray = np.minimum(gray_inpainted, cv2.GaussianBlur(gray_filled, (3, 3), 0))
                else:
                    gray = cv2.inpaint(gray, cr_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

        # Mild smoothing for noise suppression
        smooth_gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # Step 2: Multi-threshold + Local-Depression Candidate Segmentation
        user_thresh = int(self.config.get("pupil_threshold", 82))
        min_area = self.config.get("min_pupil_area", 15)
        max_area = self.config.get("max_pupil_area", 3500)
        min_circ = self.config.get("min_circularity", 0.20)

        bg_k = min(35, max(15, (min(h, w) // 3) | 1))
        local_bg = cv2.GaussianBlur(smooth_gray, (bg_k, bg_k), 0)
        local_dip = local_bg.astype(np.float32) - smooth_gray.astype(np.float32)

        my, mx = max(4, h // 8), max(4, w // 8)
        interior = smooth_gray[my:h - my, mx:w - mx]
        if interior.size > 0:
            p3 = int(np.percentile(interior, 3))
            p8 = int(np.percentile(interior, 8))
            p15 = int(np.percentile(interior, 15))
        else:
            p3, p8, p15 = user_thresh, user_thresh + 10, user_thresh + 20

        binary_masks = []
        thresh_list = [
            user_thresh,
            max(15, user_thresh - 8),
            min(240, user_thresh + 10),
            min(240, p3 + 6),
            min(240, p8 + 6),
            min(240, p15 + 4)
        ]
        if glint_center is not None:
            gx_i, gy_i = int(round(glint_center[0])), int(round(glint_center[1]))
            g_patch = smooth_gray[max(0, gy_i - 12):min(h, gy_i + 13), max(0, gx_i - 12):min(w, gx_i + 13)]
            if g_patch.size > 0:
                gp10 = int(np.percentile(g_patch, 10))
                gp20 = int(np.percentile(g_patch, 20))
                gp35 = int(np.percentile(g_patch, 35))
                thresh_list.extend([
                    min(240, gp10 + 2),
                    min(240, gp20 + 2),
                    min(240, gp20 + 4),
                    min(240, gp35 + 3)
                ])

        for th in sorted(set(thresh_list)):
            _, b_mask = cv2.threshold(smooth_gray, th, 255, cv2.THRESH_BINARY_INV)
            binary_masks.append(b_mask)

        for dip_th in [7.0, 11.0, 16.0]:
            b_dip = ((local_dip >= dip_th) & (smooth_gray <= max(user_thresh + 70, p15 + 20))).astype(np.uint8) * 255
            binary_masks.append(b_dip)

        morph_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        ring_k_outer = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        ring_k_inner = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

        raw_candidates = []
        compass_dirs = [
            (math.cos(a), math.sin(a))
            for a in [i * math.pi / 4.0 for i in range(8)]
        ]

        for b_raw in binary_masks:
            binary = cv2.morphologyEx(b_raw, cv2.MORPH_OPEN, morph_k)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, morph_k)
            contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

            for c in contours:
                area = cv2.contourArea(c)
                if area < min_area or area > max_area:
                    continue

                bx, by, bw, bh = cv2.boundingRect(c)
                if bx <= 3 or by <= 3 or (bx + bw) >= w - 3 or (by + bh) >= h - 3:
                    continue

                aspect_bb = float(min(bw, bh)) / float(max(1, max(bw, bh)))
                if aspect_bb < 0.45:
                    continue

                perim = cv2.arcLength(c, True)
                if perim <= 0:
                    continue
                circ = 4.0 * math.pi * area / (perim * perim)
                if circ < max(min_circ, 0.30):
                    continue

                m = cv2.moments(c)
                if m["m00"] <= 0:
                    continue
                cx = m["m10"] / m["m00"]
                cy = m["m01"] / m["m00"]

                c_mask = np.zeros_like(smooth_gray, dtype=np.uint8)
                cv2.drawContours(c_mask, [c], -1, 255, -1)
                mean_inside = float(cv2.mean(smooth_gray, mask=c_mask)[0])

                outer_ring = cv2.subtract(cv2.dilate(c_mask, ring_k_outer), cv2.dilate(c_mask, ring_k_inner))
                if cv2.countNonZero(cr_mask) > 0:
                    outer_ring = cv2.subtract(outer_ring, cr_mask)
                if cv2.countNonZero(outer_ring) < 8:
                    continue
                mean_ring = float(cv2.mean(smooth_gray, mask=outer_ring)[0])
                ring_contrast = mean_ring - mean_inside

                if ring_contrast < 4.5:
                    continue

                cand_r = math.sqrt(area / math.pi)
                r_probe_min = max(5, int(round(cand_r * 1.25)))
                r_probe_max = max(r_probe_min + 4, int(round(cand_r * 2.1 + 4)))
                enclosed_dirs = 0
                for cdx, cdy in compass_dirs:
                    dir_vals = []
                    for rp in range(r_probe_min, r_probe_max + 1, 2):
                        px_i = int(round(cx + rp * cdx))
                        py_i = int(round(cy + rp * cdy))
                        if 1 <= px_i < w - 1 and 1 <= py_i < h - 1:
                            dir_vals.append(float(smooth_gray[py_i, px_i]))
                    if len(dir_vals) >= 2 and max(dir_vals) >= mean_inside + 3.5 and np.mean(dir_vals) >= mean_inside + 1.8:
                        enclosed_dirs += 1
                if enclosed_dirs < 6:
                    continue

                dist_prev = 0.0
                if self.prev_pupil_center is not None:
                    dist_prev = math.hypot(cx - self.prev_pupil_center[0], cy - self.prev_pupil_center[1])

                dist_glint = 999.0
                if glint_center is not None:
                    dist_glint = math.hypot(cx - glint_center[0], cy - glint_center[1])

                if glint_center is None and (circ < 0.62 or aspect_bb < 0.65 or ring_contrast < 9.5):
                    continue

                capped_contrast = min(ring_contrast, 20.0)
                score = (
                    (mean_inside * 3.0)
                    - (capped_contrast * 1.8)
                    - (circ * 65.0)
                    + (area * 0.045)
                )
                if self.prev_pupil_center is not None:
                    score += dist_prev * 1.8
                if glint_center is not None:
                    # Corneal reflection physically originates on/near the pupil surface;
                    # strongly favor candidates that enclose or sit closest to the glint.
                    if dist_glint <= max(8.0, cand_r * 1.25):
                        score -= 45.0 - dist_glint * 2.2
                    elif dist_glint <= max(22.0, cand_r * 1.8):
                        score -= 20.0 - dist_glint * 2.2
                    else:
                        score += dist_glint * 2.5

                raw_candidates.append([score, c, (cx, cy), area, circ, mean_inside, ring_contrast, dist_prev])

        if not raw_candidates:
            return TrackingResult(
                frame_idx, timestamp_ms,
                glint_center=glint_center,
                confidence=0.0,
                blink=True
            )

        candidates = []
        for item in raw_candidates:
            score, c, (cx, cy), area, circ, mean_inside, ring_contrast, dist_prev = item
            is_inner_pupil = False
            for other in raw_candidates:
                o_area = other[3]
                o_cx, o_cy = other[2]
                o_mean = other[5]
                if o_area > area * 1.8 and math.hypot(cx - o_cx, cy - o_cy) <= math.sqrt(o_area / math.pi) * 0.65:
                    if mean_inside <= o_mean + 2.0:
                        is_inner_pupil = True
                        break
            if is_inner_pupil:
                score -= 45.0
            candidates.append((score, c, (cx, cy), area, circ, mean_inside, ring_contrast, dist_prev))

        candidates.sort(key=lambda item: item[0])
        best_score, best_contour, (seed_cx, seed_cy), c_area, c_circ, c_mean, c_contrast, dist_p = candidates[0]

        # Refine seed center to the centroid of the darkest 55% core pixels inside best_contour
        c_mask = np.zeros_like(smooth_gray, dtype=np.uint8)
        cv2.drawContours(c_mask, [best_contour], -1, 255, -1)
        cy_pts, cx_pts = np.where(c_mask > 0)
        if len(cx_pts) >= 5:
            vals = smooth_gray[cy_pts, cx_pts]
            cutoff_50 = float(np.percentile(vals, 55))
            core_sel = vals <= cutoff_50
            if np.sum(core_sel) >= 3:
                weights = (cutoff_50 + 5.0 - vals[core_sel]).astype(np.float64)
                seed_cx = float(np.average(cx_pts[core_sel], weights=weights))
                seed_cy = float(np.average(cy_pts[core_sel], weights=weights))

        # Step 4: Boundary Fitting (EyeLoop Ray Walkout or Direct Contour Ellipse)
        use_rays = (self.config.get("algorithm", "eyeloop_rays") == "eyeloop_rays")
        fitted_ellipse = None
        boundary_points = best_contour
        expected_r = math.sqrt(c_area / math.pi)
        iris_hint_val = c_mean + c_contrast

        if use_rays:
            max_r = int(min(self.config.get("max_ray_radius", 60), max(28, expected_r * 2.8)))
            num_rays = int(self.config.get("ray_count", 36))
            ray_ellipse, ray_pts = self.eyeloop_ray_walkout(
                smooth_gray,
                seed_cx,
                seed_cy,
                min_r=2,
                max_r=max_r,
                num_rays=num_rays,
                cr_mask=cr_mask,
                expected_r=expected_r,
                iris_hint=iris_hint_val
            )
            if ray_ellipse is not None:
                # Pass 2: Re-center ray origin to the initial fitted ellipse center
                ecx1, ecy1, maj1, min1, _ = self._normalize_ellipse(ray_ellipse)
                if 0.6 <= math.hypot(ecx1 - seed_cx, ecy1 - seed_cy) <= 6.0 and 2 <= ecx1 < w - 2 and 2 <= ecy1 < h - 2:
                    exp_r2 = (maj1 + min1) / 4.0
                    ray_ellipse2, ray_pts2 = self.eyeloop_ray_walkout(
                        smooth_gray,
                        ecx1,
                        ecy1,
                        min_r=2,
                        max_r=max_r,
                        num_rays=num_rays,
                        cr_mask=cr_mask,
                        expected_r=exp_r2,
                        iris_hint=iris_hint_val
                    )
                    if ray_ellipse2 is not None:
                        ray_ellipse, ray_pts = ray_ellipse2, ray_pts2

                fitted_ellipse = ray_ellipse
                boundary_points = np.array(np.round(ray_pts), dtype=np.int32).reshape((-1, 1, 2))
        else:
            # In Direct Contour Ellipse mode, also grow the contour to the local pupil-iris half-contrast threshold
            # so that a low fixed threshold doesn't underestimate the pupil size
            local_thresh = c_mean + 0.62 * c_contrast + np.clip((user_thresh - 82.0) * 0.25, -6.0, 6.0)
            roi_r = int(min(max(24, expected_r * 2.5), min(w, h) * 0.45))
            x1, y1 = max(2, int(seed_cx - roi_r)), max(2, int(seed_cy - roi_r))
            x2, y2 = min(w - 2, int(seed_cx + roi_r)), min(h - 2, int(seed_cy + roi_r))
            sub = smooth_gray[y1:y2, x1:x2]
            if sub.size > 0:
                _, sub_bin = cv2.threshold(sub, int(round(local_thresh)), 255, cv2.THRESH_BINARY_INV)
                sub_bin = cv2.morphologyEx(sub_bin, cv2.MORPH_CLOSE, morph_k)
                sub_cnts, _ = cv2.findContours(sub_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
                local_pt = (seed_cx - x1, seed_cy - y1)
                for sc in sub_cnts:
                    if len(sc) >= 5 and cv2.pointPolygonTest(sc, local_pt, False) >= -2.0:
                        sc_area = cv2.contourArea(sc)
                        if min_area <= sc_area <= max_area:
                            best_contour = sc + np.array([[[x1, y1]]], dtype=sc.dtype)
                            c_area = sc_area
                            break

        # Fallback to direct contour ellipse if rays were not used or failed
        if fitted_ellipse is None and len(best_contour) >= 5:
            try:
                fitted_ellipse = cv2.fitEllipse(best_contour)
            except Exception:
                fitted_ellipse = None

        if fitted_ellipse is None:
            raw_cx, raw_cy = seed_cx, seed_cy
            major_axis = 2.0 * math.sqrt(c_area / math.pi)
            minor_axis = major_axis
            angle = 0.0
        else:
            raw_cx, raw_cy, major_axis, minor_axis, angle = self._normalize_ellipse(fitted_ellipse)

        if not use_rays:
            boundary_offset = float(self.config.get("boundary_offset", 0.0))
            if abs(boundary_offset) > 1e-3:
                major_axis = max(2.0, major_axis + 2.0 * boundary_offset)
                minor_axis = max(2.0, minor_axis + 2.0 * boundary_offset)

        ellipse_area = math.pi * (major_axis / 2.0) * (minor_axis / 2.0)

        # Guard against zero, NaN, or implausible aspect ratios
        if major_axis <= 0 or minor_axis <= 0 or math.isnan(raw_cx) or math.isnan(raw_cy):
            return TrackingResult(frame_idx, timestamp_ms, blink=True, confidence=0.0)

        aspect_ratio = minor_axis / major_axis
        if aspect_ratio < 0.35 or ellipse_area < min_area or ellipse_area > max_area * 1.5:
            return TrackingResult(frame_idx, timestamp_ms, glint_center=glint_center, blink=True, confidence=0.0)

        # Step 5: Temporal smoothing (both center and axes for smooth tracking)
        if self.config.get("temporal_smoothing", True) and self.prev_pupil_center is not None:
            alpha = self.config.get("smoothing_factor", 0.35)
            smooth_cx = (1.0 - alpha) * self.prev_pupil_center[0] + alpha * raw_cx
            smooth_cy = (1.0 - alpha) * self.prev_pupil_center[1] + alpha * raw_cy
            pupil_center = (smooth_cx, smooth_cy)
            if self.prev_axes is not None:
                major_axis = (1.0 - alpha) * self.prev_axes[0] + alpha * major_axis
                minor_axis = (1.0 - alpha) * self.prev_axes[1] + alpha * minor_axis
                ellipse_area = math.pi * (major_axis / 2.0) * (minor_axis / 2.0)
                aspect_ratio = minor_axis / major_axis
        else:
            pupil_center = (raw_cx, raw_cy)

        self.prev_pupil_center = pupil_center
        self.prev_axes = (major_axis, minor_axis)

        # Step 6: Confidence metric (circularity, local contrast, and aspect ratio)
        conf_circ = min(1.0, c_circ / 0.75)
        conf_contrast = min(1.0, c_contrast / 18.0)
        conf = min(1.0, max(0.25, 0.45 * conf_circ + 0.55 * conf_contrast))

        return TrackingResult(
            frame_idx=frame_idx,
            timestamp_ms=timestamp_ms,
            pupil_center=pupil_center,
            major_axis=major_axis,
            minor_axis=minor_axis,
            angle=angle,
            area=ellipse_area,
            aspect_ratio=aspect_ratio,
            glint_center=glint_center,
            confidence=conf,
            blink=False,
            boundary_points=boundary_points
        )
