"""
Synthetic bat video generator with synchronized echolocation audio chirps.
Creates a realistic infrared bat eye test sequence for end-to-end verification.
"""
import os
import math
import subprocess
import wave
import struct
import numpy as np
import cv2

def generate_synthetic_bat_video(
    output_path: str = "Data/bat_pupil_sample.mp4",
    duration_sec: float = 6.0,
    fps: int = 30,
    width: int = 640,
    height: int = 480
):
    """
    Synthesize an infrared video of a bat head with dilating pupil, saccadic drift,
    corneal glint, and an acoustic echolocation audio track.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_video = os.path.splitext(output_path)[0] + "_temp.mp4"
    temp_audio = os.path.splitext(output_path)[0] + "_temp.wav"

    total_frames = int(duration_sec * fps)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

    # Eye center anchor within the frame
    eye_cx, eye_cy = 340, 240

    for i in range(total_frames):
        t = i / fps
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # 1. Infrared background gradient (dark room)
        for y in range(height):
            val = int(25 + 15 * math.sin(y / height * math.pi))
            frame[y, :] = [val, val, val]

        # 2. Draw bat head profile
        # Bat snout / head contour
        head_pts = np.array([
            [eye_cx - 150, eye_cy + 30],  # snout tip
            [eye_cx - 90, eye_cy - 40],   # muzzle top
            [eye_cx - 20, eye_cy - 120],  # ear base front
            [eye_cx - 10, eye_cy - 190],  # ear tip
            [eye_cx + 70, eye_cy - 130],  # ear base back
            [eye_cx + 170, eye_cy - 30],  # back of head
            [eye_cx + 150, eye_cy + 130], # neck / shoulder
            [eye_cx - 20, eye_cy + 110],  # jaw
            [eye_cx - 100, eye_cy + 80]   # chin
        ], dtype=np.int32)
        cv2.fillPoly(frame, [head_pts], (65, 60, 58)) # Bat fur (dark brownish-gray)
        cv2.polylines(frame, [head_pts], True, (50, 45, 42), 2)

        # Ear interior detail
        ear_inner = np.array([
            [eye_cx - 5, eye_cy - 120],
            [eye_cx, eye_cy - 175],
            [eye_cx + 50, eye_cy - 130]
        ], dtype=np.int32)
        cv2.fillPoly(frame, [ear_inner], (85, 75, 72))

        # 3. Bat Eye Region (Iris / Sclera)
        # Almond eye contour
        cv2.ellipse(frame, (eye_cx, eye_cy), (55, 38), -10, 0, 360, (135, 130, 125), -1)
        cv2.ellipse(frame, (eye_cx, eye_cy), (55, 38), -10, 0, 360, (40, 35, 30), 2)

        # 4. Bat Pupil Dynamics (Dilation & Saccades)
        # Saccade jumps every 1.5 seconds + slight high-frequency tremor
        saccade_x = 4.0 * math.sin(2.0 * math.pi * 0.7 * t) + 1.5 * math.sin(2.0 * math.pi * 3.5 * t)
        saccade_y = 3.0 * math.cos(2.0 * math.pi * 0.7 * t) + 1.2 * math.cos(2.0 * math.pi * 3.5 * t)
        
        # Periodic pupillary light reflex (dilation & constriction)
        dilation_factor = 0.5 + 0.5 * math.sin(2.0 * math.pi * 0.4 * t)
        pupil_rx = int(14 + 18 * dilation_factor) # 14px to 32px
        pupil_ry = int(12 + 15 * dilation_factor) # 12px to 27px

        pupil_center = (int(eye_cx + saccade_x), int(eye_cy + saccade_y))

        # Check for simulated blink at t ~ 3.0 to 3.2s
        is_blinking = (3.0 <= t <= 3.2)
        if not is_blinking:
            # Draw dark pupil
            cv2.ellipse(frame, pupil_center, (pupil_rx, pupil_ry), -5, 0, 360, (22, 20, 20), -1)

            # 5. Corneal Reflection (IR LED Specular Glint)
            glint_x = eye_cx + 12
            glint_y = eye_cy - 8
            cv2.circle(frame, (glint_x, glint_y), 4, (245, 245, 250), -1)
            cv2.circle(frame, (glint_x, glint_y), 5, (180, 180, 190), 1)
        else:
            # Draw closed eyelid
            cv2.line(frame, (eye_cx - 50, eye_cy), (eye_cx + 50, eye_cy), (45, 40, 38), 4)

        # Add slight camera sensor noise (Gaussian)
        noise = np.random.normal(0, 3, frame.shape).astype(np.int16)
        noisy_frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        out.write(noisy_frame)

    out.release()

    # Generate synchronized audio track (Bat echolocation chirps)
    sample_rate = 44100
    total_samples = int(duration_sec * sample_rate)
    audio_data = []

    chirp_interval = int(0.4 * sample_rate) # Chirp every 400ms
    chirp_len = int(0.04 * sample_rate)     # 40ms chirp length

    for s in range(total_samples):
        pos_in_period = s % chirp_interval
        if pos_in_period < chirp_len:
            # Frequency modulated downward sweep (3500 Hz down to 800 Hz)
            tau = pos_in_period / chirp_len
            freq = 3500 - 2700 * tau
            env = math.sin(math.pi * tau) # Hanning envelope
            val = int(24000 * env * math.sin(2.0 * math.pi * freq * (pos_in_period / sample_rate)))
        else:
            val = 0
        audio_data.append(val)

    # Write WAV file
    with wave.open(temp_audio, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(sample_rate)
        packed = struct.pack(f'<{len(audio_data)}h', *audio_data)
        wav_file.writeframes(packed)

    # Multiplex video and audio using ffmpeg
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", temp_video,
            "-i", temp_audio,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception:
        # If ffmpeg multiplexing fails, fallback to keeping the raw video
        if os.path.exists(temp_video):
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_video, output_path)
    finally:
        # Clean up temp files if output was created
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            if os.path.exists(temp_video):
                os.remove(temp_video)
            if os.path.exists(temp_audio):
                os.remove(temp_audio)

    print(f"Sample bat video generated successfully at: {output_path}")

if __name__ == "__main__":
    generate_synthetic_bat_video()
