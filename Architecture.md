# Bat Pupil Tracking Application — Architecture Documentation

This document describes the system architecture, component relationships, data flow, and file-by-file specification of the Bat Pupil Tracking Application.

---

## 1. System Overview & Architecture

The application is structured into four decoupled layers:
1. **User Interface (`Code/ui/`)**: Qt6-based graphical interface providing high-resolution video viewing, interactive bat head region-of-interest (ROI) cropping, transport controls, audio management, frame range selection, and image enhancement panels.
2. **Core Multimedia & Processing (`Code/core/`)**: Bridges hardware-accelerated video/sound playback (via `PySide6.QtMultimedia`) with frame-accurate OpenCV image processing, non-linear enhancements, orientation adjustments (rotation & flipping for hanging bats), and persistence.
3. **Pupil & Corneal Tracking (`Code/tracking/`)**: Implements the EyeLoop tracking algorithms (glint inpainting, boundary ray-casting, least-squares ellipse fitting, temporal smoothing) and kinematics export.
4. **Utilities & Tooling (`Code/utils/`)**: High-DPI styling, geometry math, timestamp formatting, and synthetic bat video/echolocation audio generation.

```mermaid
graph TD
    subgraph UI_Layer [User Interface Layer (Code/ui)]
        MW[MainWindow]
        VPW[VideoPlayerWidget - Viewport & Interactive Crop]
        PBC[PlaybackControls - Transport, Speed, Seek]
        AC[AudioControls - Loudness & Mute]
        RS[RangeSelector - Start/End Trimming]
        PP[ProcessingPanel - CLAHE, Gamma, Contrast]
        TP[TrackingPanel - EyeLoop Params & Batch]
    end

    subgraph Core_Layer [Core Engine Layer (Code/core)]
        ME[MediaEngine - PySide6 QMediaPlayer + QAudioOutput + QVideoSink]
        FR[FrameReader - OpenCV Random-Access Frame I/O]
        VP[VideoProcessor - CLAHE, Gamma, Brightness, Crop]
        PS[ProjectSession - JSON Config & State]
    end

    subgraph Tracking_Layer [Tracking Layer (Code/tracking)]
        EA[EyeLoopAdapter - EyeLoop Module Bridge]
        PD[PupilDetector - CR Glint Masking & Ellipse Fitting]
        DE[DataExporter - CSV & Matplotlib Plots]
    end

    subgraph Output_Data [Outputs]
        VID_OUT[Trimmed / Cropped Video (MP4)]
        CSV_OUT[Kinematics Data (CSV)]
        PNG_OUT[Pupil Dynamics Plots (PNG)]
        JSON_OUT[Project Configuration (JSON)]
    end

    MW --> VPW
    MW --> PBC
    MW --> AC
    MW --> RS
    MW --> PP
    MW --> TP

    PBC --> ME
    AC --> ME
    RS --> ME
    RS --> PS
    PP --> VP
    TP --> EA

    ME -->|Frames (QVideoSink)| VPW
    VPW -->|Selected Bat Head ROI| PS
    VP -->|Enhanced Image| VPW

    EA --> PD
    PD --> DE

    FR --> VID_OUT
    DE --> CSV_OUT
    DE --> PNG_OUT
    PS --> JSON_OUT
```

---

## 2. Directory Structure

```text
PupilTrackingApp/
├── .venv/                         # Python virtual environment (Python 3.12, PySide6, OpenCV)
├── Code/                          # Source code root
│   ├── app.py                     # Main application entry point
│   ├── core/                      # Media playback, OpenCV reader, and image processor
│   │   ├── __init__.py
│   │   ├── frame_reader.py        # OpenCV frame reader and video export engine
│   │   ├── media_engine.py        # PySide6 QtMultimedia synchronized audio/video engine
│   │   ├── project_session.py     # State management, ROI, trimming bounds, JSON serialization
│   │   └── video_processor.py     # CLAHE, gamma, brightness, contrast, thresholding filters
│   ├── tracking/                  # Pupil tracking subsystem (EyeLoop integration)
│   │   ├── __init__.py
│   │   ├── data_exporter.py       # CSV metrics generator, Matplotlib plots, overlay painter
│   │   ├── eyeloop_adapter.py     # Adapter layer for simonarvin/eyeloop compatibility
│   │   └── pupil_detector.py      # Glint removal, boundary edge detection, ellipse fitting
│   ├── ui/                        # PySide6 user interface components
│   │   ├── __init__.py
│   │   ├── audio_controls.py      # Loudness volume slider, percentage readout, mute button
│   │   ├── main_window.py         # Main window, menu bar, status bar, background worker
│   │   ├── playback_controls.py   # Transport buttons, frame stepping, speed, head zoom
│   │   ├── processing_panel.py    # Video enhancement dock (CLAHE, gamma, invert, presets)
│   │   ├── range_selector.py      # Frame trimming controls (Start/End frames, looping)
│   │   ├── tracking_panel.py      # EyeLoop tracking dock, live preview, batch runner
│   │   └── video_player_widget.py # Video rendering viewport with interactive mouse drag ROI
│   └── utils/                     # Utility modules
│       ├── __init__.py
│       ├── generate_test_video.py # Synthetic bat IR video and echolocation audio generator
│       └── helpers.py             # Timestamp math, ROI boundary clamps, dark QSS stylesheet
├── Configs/                       # Project configuration and preset files
│   └── default_config.json        # Default tracking and video processing configuration
├── Data/                          # Sample and input video storage
│   └── bat_pupil_sample.mp4       # Generated synthetic bat video with sound
├── Results/                       # Output metrics, plots, and trimmed video clips
│   ├── bat_pupil_kinematics.csv   # Tracked pupil coordinates, axes, areas, and confidence
│   └── bat_pupil_plot.png         # High-resolution kinematic summary plot
├── Architecture.md                # System architecture documentation (this file)
├── Project_Overview.md            # App concept, features, implementation, future directions
├── requirements.txt               # Pinned dependencies
├── run.bat                        # Windows CMD launcher
└── run.ps1                        # PowerShell launcher
```

---

## 3. Module & File Specifications

### 3.1 Entry Point

#### [`Code/app.py`](Code/app.py)
- **Role**: Application bootstrap.
- **Responsibilities**:
  - Initializes `QApplication` with High-DPI scaling pass-through.
  - Applies global dark scientific stylesheet (`DARK_THEME_QSS`).
  - Sets application metadata (`Bat Pupil Tracker`).
  - Instantiates and displays [`MainWindow`](Code/ui/main_window.py).
  - Automatically loads CLI-provided video path or default sample (`Data/bat_pupil_sample.mp4`).

---

### 3.2 Core Pipeline (`Code/core/`)

#### [`Code/core/project_session.py`](Code/core/project_session.py)
- **Class**: `ProjectSession`
- **Role**: Data model holding the active session state.
- **Key Attributes**:
  - `video_path`: Path to active video.
  - `fps`, `total_frames`, `duration_ms`, `frame_width`, `frame_height`.
  - `start_frame`, `end_frame`, `loop_range`: Trimming parameters.
  - `crop_roi`: Tuple `(x, y, w, h)` defining the bat head bounding box.
  - `is_cropped_view`: Boolean indicating whether zoom-to-head is active.
  - `processing_params`: Dictionary of image filter parameters (brightness, contrast, gamma, CLAHE, invert, threshold).
  - `tracking_params`: Dictionary of EyeLoop detection settings (thresholds, circularity, area bounds, ray count).
- **Methods**: `save_to_json(path)`, `load_from_json(path)`, `to_dict()`, `from_dict()`.

#### [`Code/core/media_engine.py`](Code/core/media_engine.py)
- **Class**: `MediaEngine(QObject)`
- **Role**: Coordinates synchronized audio and video playback using Qt6 `QtMultimedia`.
- **Components**:
  - `QMediaPlayer`: Controls playback transport, decoding, and positioning.
  - `QAudioOutput`: Manages audio stream routing, volume level, and mute states.
  - `QVideoSink`: Captures raw decoded video frames (`QVideoFrame`) for image processing and UI rendering.
- **Signals**:
  - `position_changed(int)`: Current position in milliseconds.
  - `duration_changed(int)`: Total duration in milliseconds.
  - `frame_ready(QImage, int)`: Emitted whenever a new frame is decoded.
  - `volume_changed(int)`, `mute_changed(bool)`, `state_changed(PlaybackState)`.
- **Key Methods**: `play()`, `pause()`, `stop()`, `seek_ms()`, `seek_frame()`, `step_frames(delta)`, `seek_relative(seconds)`, `set_volume(0-100)`, `set_muted(bool)`, `set_playback_rate(float)`.

#### [`Code/core/frame_reader.py`](Code/core/frame_reader.py)
- **Class**: `FrameReader`
- **Role**: OpenCV-based frame-accurate video reader and clip exporter.
- **Responsibilities**:
  - Queries exact video properties (FPS, resolution, codec, frame count).
  - Provides random-access frame retrieval via `get_frame(frame_idx)`.
  - Generates frame iterators (`iterate_range(start, end)`) for batch tracking.
  - Exports trimmed and cropped video clips to MP4 via `cv2.VideoWriter`.

#### [`Code/core/video_processor.py`](Code/core/video_processor.py)
- **Class**: `VideoProcessor`
- **Role**: Fast image enhancement routines optimized for bat infrared recordings.
- **Algorithms**:
  - `adjust_gamma(image, gamma)`: Non-linear luminance lookup table.
  - `apply_clahe(image, clip_limit, grid_size)`: Contrast Limited Adaptive Histogram Equalization on L-channel (LAB color space) or grayscale.
  - `crop_roi(image, roi)`: Slices sub-array `[y:y+h, x:x+w]` with boundary safety clamping.
  - Orientation Transforms: 0°, 90°, 180°, and 270° rotation (`cv2.rotate`) and horizontal/vertical flips (`cv2.flip`) for upside-down hanging bats.
  - `process_frame(frame, params, roi, apply_crop)`: Chains adjustments (crop, contrast, gamma, CLAHE, invert, grayscale, orientation, and threshold overlay).

---

### 3.3 Tracking & EyeLoop Integration (`Code/tracking/`)

#### [`Code/tracking/pupil_detector.py`](Code/tracking/pupil_detector.py)
- **Classes**: `TrackingResult`, `PupilDetector`
- **Role**: High-speed pupil and corneal reflection (glint) tracking engine implementing EyeLoop algorithms.
- **Key Methods & Algorithm Steps**:
  1. **Corneal Reflection (CR) Glint Detection (`detect_corneal_reflection`)**:
     - Constrains glint candidates to genuine pinpoint specular reflections ($1 \le \text{area} \le 120\,\text{px}$) under infrared illumination (`cr_threshold >= 200`).
     - Prioritizes glints adjacent to the pupil/cornea ($\le 60\,\text{px}$ from the pupil center), discarding non-ocular artifacts on fur or recording apparatus.
     - Inpaints the glint with surrounding pupil texture via `cv2.inpaint` so specular highlights do not breach the pupil contour.
  2. **Candidate Segmentation & Darkness Scoring**:
     - Dark-region binarization (`cv2.THRESH_BINARY_INV`) followed by morphological opening and closing.
     - Hierarchical contour extraction (`cv2.RETR_TREE`) to capture inner nested pupil contours without merging into dark room backgrounds.
     - Rejects background artifacts touching frame borders.
     - Calculates the **mean pixel intensity** $\mu$ inside each candidate contour mask.
     - Scores candidates by:
       $$\text{Score} = (\mu \times 2.5) - (\text{Circularity} \times 60.0) + (\text{Area} \times 0.003) + (\Delta d_{\text{prev}} \times 1.8)$$
       This ensures the detector always locks onto the **darkest, roundest inner structure** (the true pupil) rather than larger outer eyeball or eyelid contours.
  3. **EyeLoop Radial Ray Walk-Out (`eyeloop_ray_walkout`)**:
     - Projects $N$ radial rays (default 32 rays) outward from the seed pupil center up to a maximum search radius $R_{\max}$.
     - Along each ray, applies a 3-tap Gaussian filter and computes the radial gradient $\frac{dI}{dr}$.
     - Identifies the boundary edge at the peak positive gradient step (transition from dark pupil to lighter iris).
     - Fits a least-squares 2D ellipse through the ray intersection points with `cv2.fitEllipse`.
  4. **Direct Contour Ellipse Fallback**:
     - If ray edge points are insufficient ($< 5$), fits an ellipse directly to the best candidate contour.
  5. **Temporal Continuity Smoothing**:
     - Applies exponential smoothing to pupil center coordinates between successive frames ($\alpha = 0.35$).
     - Flags blinks or occlusions when candidate confidence drops.

#### [`Code/tracking/eyeloop_adapter.py`](Code/tracking/eyeloop_adapter.py)
- **Class**: `EyeLoopAdapter`
- **Role**: Standardized adapter for [`simonarvin/eyeloop`](https://github.com/simonarvin/eyeloop).
- **Behavior**:
  - Inspects the environment for native `eyeloop` installation.
  - Translates video ROI and frames into EyeLoop data structures.
  - Transforms coordinates from cropped bat head space back into global video coordinate space.

#### [`Code/tracking/data_exporter.py`](Code/tracking/data_exporter.py)
- **Class**: `DataExporter`
- **Responsibilities**:
  - `export_csv(results, path)`: Outputs tabular CSV with frame indices, timestamps, pupil $(X, Y)$, major/minor diameters, area, aspect ratio, glint $(X, Y)$, confidence, and blink flags.
  - `export_summary_plot(results, path)`: Generates publication-ready 3-panel Matplotlib figures (Pupil Area vs. Time, Mean Diameter vs. Time, Trajectory Position $X/Y$ vs. Time).
  - `draw_tracking_overlay(image, result)`: Draws tracked green ellipses, yellow center points, and red glint markers for live visualization.

---

### 3.4 User Interface Components (`Code/ui/`)

#### [`Code/ui/video_player_widget.py`](Code/ui/video_player_widget.py)
- **Class**: `VideoPlayerWidget(QWidget)`
- **Role**: Hardware-accelerated viewport with interactive mouse ROI tools.
- **Features**:
  - Aspect ratio preservation with centered letterboxing.
  - Immediate first-frame rendering upon loading video files (eliminating blank/placeholder states).
  - Mouse click-and-drag bounding box selection for the bat head.
  - Clamped ROI dimension callout tag rendered in a high-contrast pill that dynamically stays within viewport bounds.
  - Zoom-to-ROI mode (`is_cropped_view`): Crops directly to the bat head and scales it smoothly to fill the viewport.
  - Real-time overlay of sub-pixel pupil ellipses in customizable high-contrast colors (defaulting to Electric Magenta `#ec4899` as the optical complement to green IR footage), pupil center points, and red corneal reflection (CR) glint crosshairs.
  - Polished translucent HUD pill badge in the top-left displaying frame index, millisecond timestamp, and active view mode (`Frame: X / N (HH:MM:SS.mmm) • Mode`).

#### [`Code/ui/playback_controls.py`](Code/ui/playback_controls.py)
- **Class**: `PlaybackControls(QWidget)`
- **Role**: Video transport navigation toolbar.
- **Controls**:
  - **Universal Pure-Icon Transport Navigation**: `▶` (Play), `⏸` (Pause), `⏹` (Stop), `|◀` and `▶|` (single-frame stepping), `-5s` and `+5s` (seek jumping), avoiding text truncation or missing button labels.
  - Interactive timeline seek slider with monospace timecode pill (`HH:MM:SS.mmm / HH:MM:SS.mmm`) and frame index readout pill (`Frame: X / N`).
  - Playback speed dropdown (`0.1x` to `2.0x`).
  - Viewport mode buttons: `🔍 Zoom` / `🔍 Full` toggle and `↺ Reset` crop.

#### [`Code/ui/audio_controls.py`](Code/ui/audio_controls.py)
- **Class**: `AudioControls(QWidget)`
- **Role**: Audio management.
- **Controls**:
  - Horizontal audio loudness slider (0% to 100%).
  - Percentage readout badge sized to prevent clipping (`80%`, `Muted`, `100%`).
  - Toggle **Mute** button with dynamic state icon and text (`🔊 Mute` / `🔇 Unmute`) and persistent volume memory.

#### [`Code/ui/range_selector.py`](Code/ui/range_selector.py)
- **Class**: `RangeSelector(QWidget)`
- **Role**: Experimental event window selection.
- **Features**:
  - Structured **two-row event trimming layout** preventing horizontal compression:
    - **Row 1 (Anchors & Timecodes)**: Start anchor (`⚑ Set Start`), start frame spinbox, timestamp badge; End anchor (`🏁 Set End`), end frame spinbox, timestamp badge.
    - **Row 2 (Summary & Actions)**: Active segment length badge (`Length: X frames (Y.YYs)`), `Loop Range Playback` checkbox, `↺ Reset Full Video` button, and prominent `💾 Export Trimmed Video (MP4)` button.

#### [`Code/ui/processing_panel.py`](Code/ui/processing_panel.py)
- **Class**: `ProcessingPanel(QWidget)`
- **Role**: Video enhancement dock.
- **Controls**:
  - Anti-clipping dynamic numeric value badges (`_create_value_badge`) for Brightness, Contrast, Gamma, and Pupil Cutoff.
  - Literal ampersands in section titles (`Intensity & Contrast`, `Binarization & Threshold Preview`, `Bat Orientation & Rotation`).
  - Brightness slider ($-100$ to $100$).
  - Contrast slider ($0.1\times$ to $3.0\times$).
  - Gamma slider ($0.1$ to $3.0$).
  - CLAHE toggle, clip limit spinbox, and tile grid size.
  - Invert video toggle.
  - Grayscale toggle.
  - Pupil threshold preview toggle and cutoff slider ($0$ to $255$).
  - Bat IR illumination presets (Default, Bat Dataset, Low-Contrast IR, High-Contrast IR, Dark Fur / Deep Shadow, Strong Glint).
  - Rotation (0°, 90°, 180°, 270°) and horizontal/vertical flip controls.
  - Reset video filters button.
  - Guaranteed minimum dock width (`270px`) preventing horizontal truncation.

#### [`Code/ui/tracking_panel.py`](Code/ui/tracking_panel.py)
- **Class**: `TrackingPanel(QWidget)`
- **Role**: Pupil tracking configuration and batch execution dock.
- **Controls**:
  - Algorithm selector (`EyeLoop Walk-Out` vs. `Direct Contour Ellipse`).
  - Live preview toggle on the current video frame.
  - High-contrast Ellipse Color dropdown and swatch picker with presets optimized for green IR video (Electric Magenta `#ec4899`, Neon Coral `#f97316`, Electric Cyan `#06b6d4`, Vibrant Yellow `#facc15`, Classic Green `#10b981`, and Custom Color picker).
  - Anti-clipping numeric value badge for Pupil Threshold ($5$ to $255$).
  - Min/Max pupil area and circularity spinboxes.
  - Corneal reflection removal and temporal smoothing toggles.
  - "Track Bat Pupil (Selected Range)" primary execution button.
  - Asynchronous progress bar with percentage readout and live processing speed (`FPS`).
  - Status readout label and cancellation button.
  - CSV and Plot export buttons.
  - Guaranteed minimum dock width (`280px`) preventing horizontal truncation.

#### [`Code/ui/main_window.py`](Code/ui/main_window.py)
- **Class**: `MainWindow(QMainWindow)`, `BatchTrackingWorker(QThread)`
- **Role**: Top-level orchestration.
- **Responsibilities**:
  - Assembles central viewport, bottom playback/audio/range bars, and left/right docks.
  - Immediate first-frame rendering upon loading video files.
  - Coordinated dock geometry management with startup `resizeDocks()` ensuring sidebars never pinch below minimum legible widths.
  - Modern status bar chips (`📹 video specs`, `🎯 Bat Head ROI`).
  - Connects Qt signals and slots across media, UI, and tracking engines.
  - Manages asynchronous background batch tracking via `BatchTrackingWorker` to keep the UI 100% responsive.
  - Provides menu actions (File, View, Tools, Help).

---

### 3.5 Utilities (`Code/utils/`)

#### [`Code/utils/helpers.py`](Code/utils/helpers.py)
- Functions: `format_timestamp(ms)`, `frame_to_timestamp(frame, fps)`, `timestamp_to_frame(ms, fps)`, `clamp_roi(x, y, w, h, max_w, max_h)`.
- Global Stylesheet: `DARK_THEME_QSS` (modern scientific deep slate theme `#12131a` / `#181a24` with embedded SVG vector indicators for combobox down-arrows and checkbox checkmarks, styled item popups, and high-contrast tooltips).

#### [`Code/utils/generate_test_video.py`](Code/utils/generate_test_video.py)
- Function: `generate_synthetic_bat_video(path, duration, fps, width, height)`.
- Generates a synthetic bat video featuring infrared background illumination, realistic bat head silhouette, almond eye, saccading and dilating pupil, bright corneal glint, and an acoustic echolocation chirp audio track multiplexed via `ffmpeg`.

---

## 4. Pupil Boundary Accuracy & Video Enhancement Engineering Upgrades

### 4.1 Root-Cause Diagnosis on Real Bat IR Recordings
Testing across all six experimental recordings (`bat2_1(3t2).wmv`, `bat2_5(3t2).wmv`, `bat4_1(t3).wmv`, `bat4_1(t4).wmv`, `bat4_3(t4).wmv`, `bat4_4(t3).wmv`) identified five architectural bottlenecks that previously caused the fitted ellipse to underestimate pupil size (`6.2 x 6.1 px`):
1. **Zero-Padding Convolution Boundary Spike (`r = 3 px` Lock Bug)**:
   - In [`PupilDetector.eyeloop_ray_walkout`](Code/tracking/pupil_detector.py), `np.convolve(intensities, [0.25, 0.5, 0.25], mode='same')` padded the endpoints of each radial intensity profile with `0.0`. Because real bat pupils in IR recordings have grayscale intensity $I_0 \in [77, 140]$, `smoothed[0]` became $0.75\,I_0$ and `smoothed[1]` became $1.0\,I_0$, creating an artificial gradient spike $\frac{dI}{dr}\big|_{r=3} = +20\text{ to }+35$ that always beat the real pupil-to-iris transition ($+4\text{ to }+12$) and locked every ray at $r = 3\text{ px}$ (`6.2 px` diameter).
2. **Internal Lens Reflex vs. True Iris Plateau**:
   - In recordings such as `bat4_1(t3).wmv`, a subtle internal lens reflex inside the pupil ($I \approx 92\text{--}97$ at $r=6\text{ px}$) dips back to $86\text{--}88$ before reaching the true iris plateau ($102+$ at $r=14\text{ px}$).
3. **Corneal Glint Optical Halo Pinching**:
   - When the IR LED corneal glint sits directly on the pupil rim (`bat2_1(3t2)`, `bat2_5(3t2)`, `bat4_1(t4)`, `bat4_4(t3)`), an under-dilated glint mask left a bright unsaturated halo ($I \approx 140\text{--}190$) that pinched the contour and ray walk-out inward, while an over-dilated mask swallowed the adjacent iris border.
4. **Zero-Anchored Contrast Clipping in `VideoProcessor`**:
   - Previously, `cv2.convertScaleAbs(out, alpha=contrast, beta=brightness)` scaled intensities from `0` ($\alpha I + \beta$). Increasing Contrast above `1.2` brightened the entire ROI, clipping the iris and surrounding fur to `255` white, erasing the corneal reflection glint prominence, and causing `blink=True` dropouts.
5. **Axis/Angle Normalization & Integer Rendering Truncation**:
   - `cv2.fitEllipse` returns `((cx, cy), (w, h), angle)` where `w` can be smaller than `h`, causing `angle` to be rotated by $90^\circ$ when swapping `major = max(w, h)`, and `VideoPlayerWidget.paintEvent` previously truncated floating-point ellipse radii via `int(rad_x)`.

### 4.2 Architectural Solutions Implemented

- **Edge-Padded Sub-Pixel Ray Walk-Out (`0.5 px` Bilinear Steps)** ([`Code/tracking/pupil_detector.py`](Code/tracking/pupil_detector.py)):
  - Samples `36` radial rays at `0.5 px` steps via `cv2.remap(..., cv2.INTER_LINEAR)` and pads endpoints with `np.pad(sampled, 2, mode="edge")` prior to 5-tap smoothing `[0.1, 0.2, 0.4, 0.2, 0.1]`.
  - Requires the radial profile to sustain the local iris plateau (`target_intensity = core_intensity + 0.62 * contrast`) for `sustain_steps` ($\sim 2.5\text{ px}$), bypassing internal lens reflexes while constraining `iris_intensity` via the measured circum-pupillary ring (`iris_hint = c_mean + c_contrast`) so rays never overshoot thin irises into bright eyelids.
  - Executes a **2-pass re-centered walk-out** (re-casting rays from the Pass 1 ellipse center), followed by 2-stage MAD and radial-residual outlier rejection and `_normalize_ellipse` axis-angle alignment.
- **Ocular-Verified Primary Glint + `3 px` Halo Inpainting** ([`Code/tracking/pupil_detector.py`](Code/tracking/pupil_detector.py)):
  - Verifies that corneal reflection candidates sit adjacent to dark ocular tissue (`percentile(eye_patch, 15) <= percentile(gray, 35) + 6`), masks the primary glint contour with a `3 px` halo dilation + local `diff >= 12` halo ring, and inpaints with the `22nd` percentile of the surrounding dark pupil floor.
- **Multi-Threshold + Local-Depression Candidate Scoring with 8-Compass Enclosure** ([`Code/tracking/pupil_detector.py`](Code/tracking/pupil_detector.py)):
  - Evaluates multiple adaptive thresholds and local depression maps (`local_bg - smooth_gray`), requires enclosure in at least 6 of 8 compass directions, applies a continuous glint-proximity bonus, and prioritizes inner nested pupil contours over outer iris disks.
- **Median-Pivoted Contrast & Highlight-Safe CLAHE** ([`Code/core/video_processor.py`](Code/core/video_processor.py)):
  - Pivots Contrast around the frame median:
    $$I_{\text{target}} = \operatorname{clip}\!\big((I - \operatorname{median}(I)) \cdot \alpha + \operatorname{median}(I) + \beta,\; 0,\; 255\big)$$
    while clamping non-specular tissue ($\le 232$) and scaling BGR channels proportionally so green IR hue is preserved and the `240–255` corneal glint remains prominent.
- **UI Controls & Sub-Pixel Rendering** ([`Code/ui/tracking_panel.py`](Code/ui/tracking_panel.py), [`Code/ui/processing_panel.py`](Code/ui/processing_panel.py), [`Code/ui/video_player_widget.py`](Code/ui/video_player_widget.py), [`Code/ui/main_window.py`](Code/ui/main_window.py)):
  - Added **`Boundary Offset (px)`** (`-5.0` to `+10.0 px`, step `0.5 px`) in `TrackingPanel`, calibrated the 5 IR presets in `ProcessingPanel`, upgraded `VideoPlayerWidget` to `QPointF` floating-point ellipse rendering, and connected `eyeloop_adapter.reset()` on parameter/ROI changes.

### 4.3 Quantitative Verification & Visual Benchmarks

#### Table 1: Old vs. New Pupil Detector & Calibrated IR Enhancement (`frame = 100`)

| Dataset Video | Eye ROI `(x, y, w, h)` | Old Detector (`mode='same'`) | New Detector (Raw Default) | New Detector + **"Bat Dataset" IR Preset** (`Contrast=1.40, Gamma=0.80, Bright=-5`) |
| :--- | :---: | :---: | :---: | :---: |
| **`bat2_1(3t2).wmv`** | `(345, 250, 100, 100)` | `6.2 x 6.1 px` | `17.7 x 13.6 px` (`conf=1.00`) | **`17.3 x 13.1 px` (`conf=1.00`)** |
| **`bat2_5(3t2).wmv`** | `(340, 230, 95, 95)` | `6.2 x 6.1 px` | `17.1 x 13.7 px` (`conf=1.00`) | **`17.1 x 13.6 px` (`conf=1.00`)** |
| **`bat4_1(t3).wmv`** | `(670, 410, 140, 140)` | `6.2 x 6.1 px` | `17.9 x 14.8 px` (`conf=0.87`) | **`18.0 x 14.5 px` (`conf=0.94`)** |
| **`bat4_1(t4).wmv`** | `(730, 560, 140, 140)` | `6.2 x 6.1 px` | `15.8 x 13.9 px` (`conf=0.90`) | **`14.8 x 13.8 px` (`conf=1.00`)** |
| **`bat4_3(t4).wmv`** | `(780, 650, 140, 140)` | `6.2 x 6.1 px` | `16.6 x 15.5 px` (`conf=0.71`) | **`16.7 x 15.2 px` (`conf=0.87`)** |
| **`bat4_4(t3).wmv`** | `(700, 450, 140, 140)` | `6.2 x 6.1 px` | `18.4 x 14.1 px` (`conf=1.00`) | **`19.1 x 14.2 px` (`conf=1.00`)** |

#### Table 2: Video Enhancement Pipeline Comparison (Zero-Anchored vs. Median-Pivoted Contrast)

| Video Recording | Old Zero-Anchored `Contrast=1.5` (`cv2.convertScaleAbs`) | New Median-Pivoted `Contrast=1.4, Gamma=0.8, Bright=-5` |
| :--- | :---: | :---: |
| **`bat2_1(3t2).wmv`** | `BLINK / LOST` (`0.0 x 0.0 px`, `conf=0.00`) | **`17.3 x 13.1 px` (`conf=1.00`)** |
| **`bat2_5(3t2).wmv`** | `BLINK / LOST` (`0.0 x 0.0 px`, `conf=0.00`) | **`17.1 x 13.6 px` (`conf=1.00`)** |
| **`bat4_1(t3).wmv`** | `17.8 x 14.8 px` (`conf=1.00`) | **`18.0 x 14.5 px` (`conf=0.94`)** |
| **`bat4_1(t4).wmv`** | `14.3 x 8.7 px` (`conf=0.81`) | **`14.8 x 13.8 px` (`conf=1.00`)** |
| **`bat4_3(t4).wmv`** | `BLINK / LOST` (`0.0 x 0.0 px`, `conf=0.00`) | **`16.7 x 15.2 px` (`conf=0.87`)** |
| **`bat4_4(t3).wmv`** | `21.0 x 17.7 px` (`conf=1.00`) | **`19.1 x 14.2 px` (`conf=1.00`)** |

![Pupil Tracking Comparison Grid](Results/pupil_tracking_comparison.png)

![Timeline Tracking Verification on bat4_1(t3)](Results/bat4_1_dilation_timeline.png)

