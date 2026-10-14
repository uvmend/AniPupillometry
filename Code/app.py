"""
Main entry point for the Bat Pupil Tracking Application.
Initializes the Qt application, applies styles, and launches the MainWindow.
"""
import sys
import os

# Ensure the root directory is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from Code.ui.main_window import MainWindow
from Code.utils.helpers import DARK_THEME_QSS

def main():
    # Set high DPI policy for modern displays
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Bat Pupil Tracker")
    app.setOrganizationName("BatResearch")

    # Apply modern scientific dark stylesheet
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()

    # If a video path was passed via CLI, auto-load it
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        window.load_video(sys.argv[1])
    elif os.path.exists(os.path.join(PROJECT_ROOT, "Data", "bat_pupil_sample.mp4")):
        # Auto-load generated sample bat video for immediate out-of-the-box experience
        window.load_video(os.path.join(PROJECT_ROOT, "Data", "bat_pupil_sample.mp4"))

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
