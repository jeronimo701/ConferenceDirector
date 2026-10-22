from dataclasses import dataclass
from pathlib import Path
from .paths import (IMAGE_EXTS, PRESENTATION_EXTS, ROOT, VIDEO_EXTS)
IGNORED_PROJECT_DIRS = {'director_core'}

@dataclass
class Project:
    path: Path
    presentations: list[Path]
    images: list[Path]
    videos: list[Path]

def list_project_dirs(base_dir=None):
    base_dir = Path(base_dir) if base_dir else ROOT
    if not base_dir.exists():
        return []
    projects = [path for path in base_dir.iterdir() if path.is_dir() if path.name not in IGNORED_PROJECT_DIRS if not path.name.startswith('.') if not path.name.startswith('__')]
    return sorted(projects, key=(lambda item: item.name.lower()))

def scan_project(project_path):
    project_path = Path(project_path)
    files = [path for path in sorted(project_path.iterdir(), key=(lambda item: item.name.lower())) if path.is_file()]
    return Project(path=project_path, presentations=[path for path in files if path.suffix.lower() in PRESENTATION_EXTS], images=[path for path in files if path.suffix.lower() in IMAGE_EXTS], videos=[path for path in files if path.suffix.lower() in VIDEO_EXTS])

