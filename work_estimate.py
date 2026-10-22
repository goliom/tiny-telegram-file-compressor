"""Approximate total remaining time from byte weights and observed progress."""
import math
import os
import time
from pathlib import Path

from archive_layout import is_link


def folder_weight(folder, stop_event=None):
    """Read file metadata only; an unreadable tree leaves the estimate unknown."""
    total = 0

    def scan_error(error):
        raise error

    try:
        for directory, folders, files in os.walk(folder, followlinks=False, onerror=scan_error):
            if stop_event is not None and stop_event.is_set():
                return None
            parent = Path(directory)
            folders[:] = [name for name in folders if not is_link(parent / name)]
            for name in files:
                path = parent / name
                if not is_link(path):
                    total += path.stat().st_size
        return max(1, total)
    except OSError:
        return None


class WorkEstimate:
    """UI-thread state; weights may grow as nested archives are discovered."""
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.reset()

    def reset(self):
        self.weights = {}
        self.fractions = {}
        self.finished = set()
        self.current = None
        self.started = None

    def add(self, weights):
        for key, weight in weights.items():
            self.weights[key] = weight
            self.fractions.setdefault(key, 0)

    def start(self, key):
        if key not in self.weights:
            self.add({key: None})
        self.current = key
        if self.started is None:
            self.started = self.clock()

    def update(self, percent):
        if self.current is not None:
            self.fractions[self.current] = max(self.fractions.get(self.current, 0), min(100, max(0, percent)) / 100)

    def finish(self, key, succeeded=True):
        if not succeeded:
            # Failed work contributes no measured throughput and no remaining work.
            self.weights[key] = 0
        self.fractions[key] = 1
        self.finished.add(key)
        if self.current == key:
            self.current = None

    def seconds_left(self, stop_after_current=False):
        if self.started is None:
            return None
        elapsed = self.clock() - self.started
        pending = [key for key in self.weights if key not in self.finished]
        if stop_after_current:
            pending = [self.current] if self.current is not None else []
        if any(self.weights[key] is None for key in pending):
            return None
        remaining = sum(self.weights[key] * (1 - self.fractions.get(key, 0)) for key in pending)
        if remaining <= 0:
            return 0
        measured = sum(weight * self.fractions.get(key, 0) for key, weight in self.weights.items() if weight is not None)
        if elapsed < 1 or measured <= 0:
            return None
        return remaining * elapsed / measured

    def progress_fraction(self):
        if not self.weights:
            return 0
        if all(weight is not None for weight in self.weights.values()):
            total = sum(self.weights.values())
            if total > 0:
                return sum(weight * self.fractions.get(key, 0) for key, weight in self.weights.items()) / total
        return sum(self.fractions.get(key, 0) for key in self.weights) / len(self.weights)

    def message(self, running, has_finished=False, stop_after_current=False):
        if not running:
            return ('eta_remaining', {'duration': '0 s'}) if has_finished else ('eta_idle', {})
        seconds = self.seconds_left(stop_after_current)
        if seconds is None:
            return 'eta_calculating', {}
        if seconds <= 0:
            return 'eta_finalizing', {}
        return 'eta_remaining', {'duration': duration(seconds)}


def duration(seconds):
    total = max(1, math.ceil(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f'{hours} h {minutes:02d} min {secs:02d} s'
    if minutes:
        return f'{minutes} min {secs:02d} s'
    return f'{secs} s'
