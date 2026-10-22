import os
from pathlib import Path
from shutil import which

def existing_exe(configured_path, exe_names, extra_paths=()):
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path))
    for name in exe_names:
        found = which(name)
        if found:
            candidates.append(Path(found))
    candidates.extend((Path(path) for path in extra_paths))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return exe_names[0]

def edge_extra_paths():
    names = ('Microsoft/Edge/Application/msedge.exe', 'Microsoft/Edge Beta/Application/msedge.exe')
    bases = os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')
    return [Path(base) / name for base in bases if base for name in names]

def powerpoint_extra_paths():
    roots = []
    for base in os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)'):
        if base:
            roots.extend(Path(base).glob('Microsoft Office/root/Office*/POWERPNT.EXE'))
            roots.extend(Path(base).glob('Microsoft Office/Office*/POWERPNT.EXE'))
    return roots

