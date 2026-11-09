"""The system's folder picker, opened by the server on the user's machine (FE Maker runs locally): a web page cannot
give a folder's full path, and nobody should have to type one."""

from __future__ import annotations

import threading
from pathlib import Path

_lock = threading.Lock()   # one picker at a time


class PickerUnavailable(Exception):
    pass


def pick_folder(title: str, initial: str | None = None) -> str | None:
    """Show the folder picker in front of the browser and return the chosen folder, or None when cancelled."""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as e:   # a Python installed without Tk
        raise PickerUnavailable() from e
    start = initial if initial and Path(initial).is_dir() else None
    with _lock:
        try:
            root = tkinter.Tk()
        except tkinter.TclError as e:   # no display
            raise PickerUnavailable() from e
        try:
            root.withdraw()
            root.attributes("-topmost", True)   # above the browser that asked for it
            chosen = filedialog.askdirectory(parent=root, title=title, initialdir=start, mustexist=True)
        finally:
            root.destroy()
    return str(Path(chosen)) if chosen else None
