import ctypes
import os
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QApplication


def screen_title(screen, index):
    geometry = screen.geometry()
    return (
        f"Монитор {index + 1}: {screen.name()} "
        f"({geometry.width()}x{geometry.height()} @ {geometry.x()},{geometry.y()})"
    )


def app_screens():
    return QApplication.screens()


def screen_index_of_widget(widget):
    handle = widget.windowHandle()
    screen = handle.screen() if handle else QApplication.screenAt(widget.frameGeometry().center())
    screens = app_screens()
    if screen in screens:
        return screens.index(screen)
    return 0


def move_widget_to_screen(widget, screen):
    geometry = screen.availableGeometry()
    size = widget.size()
    x = geometry.x() + max(0, (geometry.width() - size.width()) // 2)
    y = geometry.y() + max(0, (geometry.height() - size.height()) // 2)
    widget.windowHandle().setScreen(screen)
    widget.move(x, y)


def display_switch(mode):
    exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "DisplaySwitch.exe"
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(exe),
        mode,
        None,
        1,
    )
    if result <= 32:
        raise OSError(f"DisplaySwitch failed with ShellExecute code {result}")
    return result
