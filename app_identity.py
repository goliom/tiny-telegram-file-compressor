"""Shared application name and Windows/Tk icons."""
import os
from pathlib import Path

APP_NAME = 'Tiny Telegram File Compressor'
APP_VERSION = '1.2.0'
ASSETS = Path(__file__).resolve().parent / 'assets'


def configure_app_id():
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Tiny.Telegram.FileCompressor')


def apply_identity(window, subtitle=None):
    import tkinter as tk
    window.title(APP_NAME + (' — ' + subtitle if subtitle else ''))
    icon = ASSETS / 'tiny-telegram-file-compressor.ico'
    if icon.is_file() and os.name == 'nt':
        window.iconbitmap(str(icon))
    png = ASSETS / 'tiny-telegram-file-compressor.png'
    if png.is_file():
        window._tiny_app_icon = tk.PhotoImage(master=window, file=str(png))
        window.iconphoto(True, window._tiny_app_icon)
