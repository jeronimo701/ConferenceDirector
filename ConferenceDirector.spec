# Generated build recipe; works with the found original source. Not an original author build recipe.
from pathlib import Path
project_root = Path(SPECPATH)
a = Analysis([str(project_root / 'conference_director.py')], pathex=[str(project_root)], binaries=[], datas=[], hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ConferenceDirector', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False, disable_windowed_traceback=False, argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None, contents_directory='director_core')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ConferenceDirector')
