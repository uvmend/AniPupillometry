"""
Data export utilities for pupil tracking results.
Generates CSV tables, matplotlib dilation plots, and annotated video clips.
"""
from typing import List, Dict, Any, Optional
import os
import pandas as pd
import matplotlib.pyplot as plt
import cv2
import numpy as np
from Code.tracking.pupil_detector import TrackingResult

class DataExporter:
    """Exports tracked kinematics and visual overlays."""

    @staticmethod
    def export_csv(results: List[TrackingResult], output_csv_path: str) -> bool:
        """Export frame-by-frame tracking metrics to a CSV file."""
        if not results:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
        rows = [r.to_dict() for r in results]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv_path, index=False)
        return True

    @staticmethod
    def export_summary_plot(results: List[TrackingResult], output_plot_path: str, title: str = "Bat Pupil Dynamics"):
        """Generate high-resolution PNG plots of pupil area, coordinates, and blinks."""
        if not results:
            return
        os.makedirs(os.path.dirname(os.path.abspath(output_plot_path)), exist_ok=True)
        
        times = [r.timestamp_ms / 1000.0 for r in results]
        areas = [r.area if not r.blink else np.nan for r in results]
        diameters = [(r.major_axis + r.minor_axis) / 2.0 if not r.blink else np.nan for r in results]
        xs = [r.pupil_center[0] if (r.pupil_center and not r.blink) else np.nan for r in results]
        ys = [r.pupil_center[1] if (r.pupil_center and not r.blink) else np.nan for r in results]
        blinks = [r.blink for r in results]

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
        fig.suptitle(title, fontsize=14, fontweight='bold')

        # Subplot 1: Pupil Area
        ax1.plot(times, areas, color='#1a73e8', lw=1.5, label='Pupil Area (px²)')
        ax1.set_ylabel('Area (px²)')
        ax1.grid(True, linestyle='--', alpha=0.5)
        ax1.legend(loc='upper right')

        # Subplot 2: Average Diameter
        ax2.plot(times, diameters, color='#0f9d58', lw=1.5, label='Mean Diameter (px)')
        ax2.set_ylabel('Diameter (px)')
        ax2.grid(True, linestyle='--', alpha=0.5)
        ax2.legend(loc='upper right')

        # Subplot 3: Coordinates X and Y
        ax3.plot(times, xs, color='#d93025', lw=1.2, label='Pupil X (px)')
        ax3.plot(times, ys, color='#f4b400', lw=1.2, label='Pupil Y (px)')
        ax3.set_xlabel('Time (seconds)')
        ax3.set_ylabel('Position (px)')
        ax3.grid(True, linestyle='--', alpha=0.5)
        ax3.legend(loc='upper right')

        plt.tight_layout()
        plt.savefig(output_plot_path, dpi=200)
        plt.close(fig)

    @staticmethod
    def hex_to_bgr(hex_str: str, default: tuple = (153, 72, 236)) -> tuple:
        """Convert a CSS hex color string (#RRGGBB) to an OpenCV BGR tuple."""
        try:
            clean = hex_str.lstrip("#")
            if len(clean) == 6:
                r = int(clean[0:2], 16)
                g = int(clean[2:4], 16)
                b = int(clean[4:6], 16)
                return (b, g, r)
        except Exception:
            pass
        return default

    @classmethod
    def draw_tracking_overlay(
        cls,
        image: np.ndarray,
        result: TrackingResult,
        show_labels: bool = True,
        ellipse_color: str | tuple = "#ec4899"
    ) -> np.ndarray:
        """Draw tracked ellipse, center dot, glint marker, and metrics overlay on image."""
        out = image.copy()
        if result.blink:
            if show_labels:
                cv2.putText(
                    out, "BLINK / OCCLUSION", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
                )
            return out

        bgr_color = cls.hex_to_bgr(ellipse_color) if isinstance(ellipse_color, str) else ellipse_color

        # Draw pupil ellipse
        if result.pupil_center and result.major_axis > 0 and result.minor_axis > 0:
            cx, cy = int(round(result.pupil_center[0])), int(round(result.pupil_center[1]))
            axes = (int(round(result.major_axis / 2.0)), int(round(result.minor_axis / 2.0)))
            cv2.ellipse(out, (cx, cy), axes, result.angle, 0, 360, bgr_color, 2)
            cv2.circle(out, (cx, cy), 3, (255, 255, 255), -1)

        # Draw corneal reflection glint
        if result.glint_center:
            gx, gy = int(round(result.glint_center[0])), int(round(result.glint_center[1]))
            cv2.drawMarker(out, (gx, gy), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)

        # Draw text HUD
        if show_labels and result.pupil_center:
            text = f"Pupil: ({result.pupil_center[0]:.1f}, {result.pupil_center[1]:.1f}) | Area: {result.area:.0f}px | Conf: {result.confidence:.2f}"
            cv2.putText(out, text, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, bgr_color, 1, cv2.LINE_AA)

        return out
