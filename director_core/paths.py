import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    bundle_root = Path(getattr(sys, "_MEIPASS", ROOT))
    package_in_bundle = bundle_root / "director_core"
    APP_PACKAGE = package_in_bundle if package_in_bundle.exists() else bundle_root
else:
    APP_PACKAGE = Path(__file__).resolve().parent
    ROOT = APP_PACKAGE.parent

SETTINGS_DIR = ROOT / "director_core"
SETTINGS_PATH = SETTINGS_DIR / "conference_director_settings.json"

PRESENTATION_EXTS = {".ppt", ".pptx", ".pps", ".ppsx", ".pdf"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".m4v", ".webm"}
