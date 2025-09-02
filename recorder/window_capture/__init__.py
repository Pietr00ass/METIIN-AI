"""Platform-specific WindowCapture factory."""
import sys

if sys.platform.startswith("win"):
    from .window_capture_win import WindowCapture
elif sys.platform == "darwin":
    from .window_capture_macos import WindowCapture
else:
    from .window_capture_x11 import WindowCapture

__all__ = ["WindowCapture"]
