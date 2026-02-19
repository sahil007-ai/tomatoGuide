"""
Configuration Module for Focus Guard AI Pomodoro Timer

This module contains all configuration constants and settings for the
Focus Guard application. Centralized configuration makes it easy to
adjust settings without modifying the main codebase.
"""

import os
from pathlib import Path

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

APP_NAME = "Focus Guard"
APP_VERSION = "1.0.0"
AUTHOR = "Your Name/Team"

# ============================================================================
# FILE PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"

# Create directories if they don't exist
ASSETS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

MEMORY_PATH = DATA_DIR / "focus_memory.txt"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "focus_guard.log"

# Sound files
SOUND_SESSION_END = ASSETS_DIR / "session_end.mp3"
SOUND_FOCUS_ALERT = ASSETS_DIR / "focus_alert.mp3"

# ============================================================================
# TIMER SETTINGS (in minutes)
# ============================================================================

WORK_MIN = 25  # Default work session duration
SHORT_BREAK_MIN = 5  # Short break duration
LONG_BREAK_MIN = 20  # Long break duration
SESSIONS_BEFORE_LONG_BREAK = 4  # Sessions before long break

# ============================================================================
# FOCUS DETECTION SETTINGS
# ============================================================================

# MediaPipe Face Mesh Configuration
MAX_FACES = 1
REFINE_LANDMARKS = True
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

# Alert Thresholds (in frames)
VISUAL_WARNING_THRESHOLD_FRAMES = 15  # Show warning after this many frames
SOUND_ALERT_THRESHOLD_FRAMES = 45  # Play sound after this many frames
DISTRACTION_PENALTY_COOLDOWN = 10  # Seconds between distraction counts

# ============================================================================
# GUI SETTINGS
# ============================================================================

WINDOW_WIDTH = 400
WINDOW_HEIGHT = 760
APP_TITLE = f"{APP_NAME} - AI-Powered Pomodoro Timer"
RESIZABLE = False

# Colors
COLOR_TEXT = "#FFFFFF"
COLOR_WARN = "#FFCC00"
COLOR_SUCCESS = "#00FF00"
COLOR_GOLD = "#FFD700"

# Fonts
FONT_TITLE = ("Helvetica", 24, "bold")
FONT_LARGE = ("Helvetica", 80, "bold")
FONT_NORMAL = ("Helvetica", 14)
FONT_LABEL = ("Helvetica", 12, "bold")
FONT_SMALL = ("Helvetica", 11)
FONT_BUTTON = ("Helvetica", 12)

# ============================================================================
# ALGORITHM SETTINGS
# ============================================================================

# AI Algorithm constraint: Maximum change per session (as percentage)
AI_MAX_CHANGE_PERCENT = 0.25  # ±25% constraint

# Default total focus goal (in minutes)
DEFAULT_TOTAL_FOCUS_GOAL = 100  # 4 sessions of 25 mins

# ============================================================================
# WEBCAM SETTINGS
# ============================================================================

WEBCAM_INDEX = 0  # Primary webcam device
WEBCAM_FRAME_SIZE = (360, 270)  # Display size
WEBCAM_UPDATE_INTERVAL = 10  # ms between frame updates

# ============================================================================
# LOGGING SETTINGS
# ============================================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# ERROR HANDLING
# ============================================================================

SHOW_ERROR_DIALOGS = True  # Show error messages in GUI
SAVE_ERROR_LOGS = True  # Save errors to log file
