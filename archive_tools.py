"""Locate 7-Zip without requiring a browser or Playwright."""
import shutil
import os
import subprocess
from pathlib import Path


def subprocess_options():
    """Keep external 7-Zip windows hidden when launched from the desktop app."""
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def seven_zip():
    for candidate in [shutil.which("7z"), shutil.which("7za"),
                      r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"]:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("7-Zip introuvable. Installez-le depuis https://www.7-zip.org/")
