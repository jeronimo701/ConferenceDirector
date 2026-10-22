import sys
from pathlib import Path
if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).resolve().parent
    bundle_root = Path(getattr(sys, '_MEIPASS', ROOT))
    package_in_bundle = bundle_root / 'director_core'
    APP_PACKAGE = package_in_bundle if package_in_bundle.exists() else bundle_root
else:
    APP_PACKAGE = Path(__file__).resolve().parent
    ROOT = APP_PACKAGE.parent
SETTINGS_DIR = ROOT / 'director_core'
SETTINGS_PATH = SETTINGS_DIR / 'conference_director_settings.json'
PRESENTATION_EXTS = {'.pdf', '.pps', '.ppt', '.ppsx', '.pptx'}
IMAGE_EXTS = {'.bmp', '.gif', '.jpg', '.png', '.jpeg', '.webp'}
VIDEO_EXTS = {'.avi', '.m4v', '.mkv', '.mov', '.mp4', '.wmv', '.webm'}
