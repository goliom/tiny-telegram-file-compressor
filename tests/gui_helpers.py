import sys
import gc
import tempfile
import time
import unittest
from pathlib import Path
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_app import DesktopApp


class AppGuiTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = DesktopApp(self.root)
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.directory = Path(self.temp.name).resolve()
        self.releases = []

    def tearDown(self):
        for event in self.releases:
            event.set()
        if not self.app.destroyed:
            for panel in self.app.panels:
                panel.request_stop()
            self.pump_until(lambda: not any(panel.running for panel in self.app.panels))
            self.app.destroy()
        self.temp.cleanup()
        self.app = None
        self.root = None
        gc.collect()  # Release Tk cycles on the UI thread before the next worker starts.

    def pump_until(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(condition(), 'The UI worker did not finish in time')
