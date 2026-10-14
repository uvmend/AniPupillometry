# Bat Pupil Tracking Application

A specialized desktop application for bat pupil and corneal reflection tracking with synchronized video and audio playback, interactive bat head cropping, frame range trimming, infrared image enhancement, and EyeLoop tracking integration.

---

## Quick Start

### 1. Launch the Application
You can launch the application with a single click using the provided launcher scripts or via terminal:

#### Using Command Prompt:
```bat
run.bat
```

#### Using PowerShell:
```powershell
.\run.ps1
```

#### Directly with Python:
```powershell
.\.venv\Scripts\python.exe Code\app.py
```

Upon launch, the application automatically loads the included sample bat video (`Data/bat_pupil_sample.mp4`) with synchronized echolocation audio chirps so you can test all features immediately!

### 2. Loading Custom Bat Recordings
Use **File → Open Video...** (`Ctrl+O`) to load your own infrared bat recordings (`.mp4`, `.avi`, `.mkv`, `.mov`, `.wmv`).

For infrared / night-vision recordings, you can select the calibrated **"Bat Dataset (Dilation / Night Vision)"** preset in the **Video Enhancement Tools** panel (`Contrast = 1.40`, `Gamma = 0.80`, `Brightness = -5`, and `Pupil Threshold = 82`).

---

## Core Features
- **Audiovisual Synchronization**: Smooth video playback with synchronized audio output and immediate first-frame decode upon video loading.
- **Transport Controls**: Pure-icon navigation controls (`▶`, `⏸`, `⏹`, `|◀`, `▶|`, `-5s`, `+5s`) eliminating label truncation, timeline scrubbing with timecode & frame badges, and Playback Speed regulation (0.1x to 2.0x).
- **Audio Controls**: Loudness volume slider (0-100%) and Mute toggle with anti-clipping dynamic indicators (`🔊 Mute` / `🔇 Unmute`).
- **Interactive Head Cropping**: Drag a rectangular box over the video to set the bat head ROI with clamped dimension tags, and click **"🔍 Zoom"** to toggle smooth magnification.
- **Orientation & Rotation Controls**: 0°, 90°, 180°, and 270° rotation, plus horizontal/vertical flips for upside-down hanging bats.
- **Range Selection & Trimming**: Structured 2-row trimming interface to set Start and End frames with one click, loop the selected range, and export trimmed video clips without horizontal compression.
- **Infrared Video Processing Tools**: CLAHE (Adaptive Histogram Equalization), Gamma correction, Brightness/Contrast, Inversion, anti-clipping numeric value badges, and live Pupil Threshold Mask preview.
- **EyeLoop Pupil Tracking & High-Contrast Overlays**: Pinpoint corneal glint masking, darkness & circularity candidate scoring, radial ray walk-out boundary detection, sub-pixel ellipse fitting, temporal smoothing, background batch processing with real-time FPS telemetry, and high-contrast ellipse styling defaulting to Electric Magenta (the optical complement to green IR / night-vision footage) with customizable palette presets (Magenta, Coral, Cyan, Yellow, Green, Custom).
- **Kinematics Export**: Export tracked parameters to CSV, generate publication-grade Matplotlib plots, and save project sessions to JSON.
- **Modern Scientific UI**: Dark slate theme (`DARK_THEME_QSS`) with vector SVG indicators, translucent viewport HUD overlays, and coordinated dock widths.

---

## Documentation
- **[Architecture.md](Architecture.md)**: Comprehensive architectural diagrams, class designs, and file-by-file specifications.
- **[Project_Overview.md](Project_Overview.md)**: In-depth discussion of the app idea, bat neurobiology, implementation details, crucial video processing tools, and future directions.

---

## Recent Engineering Upgrades: True-Boundary Pupil Fitting & IR Video Enhancement

To resolve the issue where tracked ellipses on real infrared bat recordings were consistently smaller than the anatomical pupil, the tracking and enhancement pipelines were upgraded with the following enhancements:

1. **Eliminated Zero-Padding Convolution Spike (`6.2 px` Circle Bug)** in [`Code/tracking/pupil_detector.py`](Code/tracking/pupil_detector.py):
   - Replaced zero-padded `np.convolve(..., mode='same')` with edge-replicated padding (`np.pad(..., mode='edge')`) along `0.5 px` bilinear sub-pixel rays (`36` rays, 2-pass re-centered walk-out).
   - Added sustained iris-plateau exit verification (`sustain_steps`) and circum-pupillary `iris_hint` clamping so rays bypass faint internal lens reflexes inside the pupil and stop cleanly at the true pupil-to-iris margin without overshooting into outer eyelids.
2. **Primary Corneal Glint + Optical Halo Inpainting**:
   - Upgraded `detect_corneal_reflection` to isolate the primary corneal glint contour adjacent to dark ocular tissue, dilate by a `3 px` halo mask, and fill with the dark pupil floor (`22nd` percentile of the perimeter ring) prior to segmentation and ray casting.
3. **Median-Pivoted Contrast & Highlight-Preserving CLAHE** in [`Code/core/video_processor.py`](Code/core/video_processor.py):
   - Replaced zero-anchored `cv2.convertScaleAbs` (which previously blew out bright fur/iris to `255` and erased the corneal reflection glint when Contrast was increased) with **median-pivoted contrast** (`(I - median) * contrast + median + brightness`) and highlight soft-clamping (`<= 232` for non-specular tissue).
   - Increasing Contrast (`1.40x`) and lowering Gamma (`0.80`) now darkens the pupil (`< median`) while brightening the surrounding iris (`> median`), directly boosting pupil tracking confidence.
4. **Interactive `Boundary Offset (px)` & Sub-Pixel `QPointF` Rendering**:
   - Added a **`Boundary Offset (px)`** spinbox (`-5.0` to `+10.0 px`, step `0.5 px`) in [`Code/ui/tracking_panel.py`](Code/ui/tracking_panel.py), sub-pixel `QPointF` ellipse rendering in [`Code/ui/video_player_widget.py`](Code/ui/video_player_widget.py), and immediate temporal-smoothing reset upon parameter/ROI changes in [`Code/ui/main_window.py`](Code/ui/main_window.py).

### Benchmark Results Across All 6 Bat Dataset Videos (`frame = 100`)

| Dataset Video | Old Detector (`mode='same'` bug) | New Detector (Raw Default) | New Detector + **"Bat Dataset" IR Preset** (`Contrast=1.40, Gamma=0.80, Bright=-5`) |
| :--- | :---: | :---: | :---: |
| **`bat2_1(3t2).wmv`** | `6.2 x 6.1 px` | `17.7 x 13.6 px` (`conf=1.00`) | **`17.3 x 13.1 px` (`conf=1.00`)** |
| **`bat2_5(3t2).wmv`** | `6.2 x 6.1 px` | `17.1 x 13.7 px` (`conf=1.00`) | **`17.1 x 13.6 px` (`conf=1.00`)** |
| **`bat4_1(t3).wmv`** | `6.2 x 6.1 px` | `17.9 x 14.8 px` (`conf=0.87`) | **`18.0 x 14.5 px` (`conf=0.94`)** |
| **`bat4_1(t4).wmv`** | `6.2 x 6.1 px` | `15.8 x 13.9 px` (`conf=0.90`) | **`14.8 x 13.8 px` (`conf=1.00`)** |
| **`bat4_3(t4).wmv`** | `6.2 x 6.1 px` | `16.6 x 15.5 px` (`conf=0.71`) | **`16.7 x 15.2 px` (`conf=0.87`)** |
| **`bat4_4(t3).wmv`** | `6.2 x 6.1 px` | `18.4 x 14.1 px` (`conf=1.00`) | **`19.1 x 14.2 px` (`conf=1.00`)** |

![Pupil Tracking Comparison Across All 6 Bat Videos](Results/pupil_tracking_comparison.png)

### Multi-Frame Timeline Verification (`bat4_1(t3).wmv`)

![Timeline Tracking Verification on bat4_1(t3)](Results/bat4_1_dilation_timeline.png)

