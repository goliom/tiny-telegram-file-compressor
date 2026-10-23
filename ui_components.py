"""Shared compact, localized controls for both application tabs."""
import math
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk

from compression_i18n import text
from work_estimate import WorkEstimate


def size_text(value, language='fr'):
    if value is None:
        return text('size_pending', language)
    scaled = float(value)
    unit = 'B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if scaled < 1000 or unit == 'TB':
            break
        scaled /= 1000
    number = f'{scaled:.1f}' if unit != 'B' else str(int(scaled))
    if language != 'en':
        number = number.replace('.', ',')
    return f'{number} {unit}'


def open_folder(path, parent, language):
    try:
        os.startfile(str(path))
    except OSError as error:
        messagebox.showerror(text('destination_title', language), text('open_error', language, error=error), parent=parent)


class LocalizedFrame(ttk.Frame):
    def __init__(self, parent, language='fr', **kwargs):
        super().__init__(parent, **kwargs)
        self.language = language
        self.localized_widgets = []

    def tr(self, key, **values):
        return text(key, self.language, **values)

    def local(self, widget, key):
        self.localized_widgets.append((widget, key))
        widget.configure(text=self.tr(key))
        return widget

    def translate_widgets(self, language):
        self.language = language
        for widget, key in self.localized_widgets:
            widget.configure(text=self.tr(key))


class TaskMonitor(LocalizedFrame):
    def __init__(self, parent, language='fr'):
        super().__init__(parent, language)
        self.estimate = WorkEstimate()
        self.running = self.finished = False
        self.stop_requested = False
        self.current_message = ('waiting', {})
        self.status_message = ('ready', {})
        self.completed = self.total = 0
        self.entries = []
        self.current_info = None
        self.item_started = 0
        self.details_visible = False
        self.current_var = tk.StringVar(master=self)
        self.total_var = tk.StringVar(master=self)
        self.eta_var = tk.StringVar(master=self)
        self.status_var = tk.StringVar(master=self)
        ttk.Label(self, textvariable=self.current_var, wraplength=730).pack(anchor='w')
        self.current_bar = ttk.Progressbar(self, maximum=100)
        self.current_bar.pack(fill='x', pady=(2, 4))
        ttk.Label(self, textvariable=self.total_var).pack(anchor='w')
        self.total_bar = ttk.Progressbar(self, maximum=100)
        self.total_bar.pack(fill='x', pady=(2, 4))
        ttk.Label(self, textvariable=self.eta_var).pack(anchor='w')
        self.summary = ttk.Label(self, textvariable=self.status_var, wraplength=730, font=('Segoe UI', 9, 'bold'))
        self.summary.pack(anchor='w', pady=(2, 0))
        self.details_button = ttk.Button(self, command=self.toggle_details)
        self.details_button.pack(anchor='w', pady=(4, 0))
        self.details_frame = ttk.Frame(self)
        self.log = tk.Text(self.details_frame, height=3, wrap='word', state='disabled')
        scroll = ttk.Scrollbar(self.details_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.log.pack(side='left', fill='both', expand=True)
        self.render()

    def begin(self, total=0):
        self.estimate.reset()
        self.running, self.finished, self.stop_requested = True, False, False
        self.completed, self.total = 0, total
        self.current_message = ('waiting', {})
        self.current_info = None
        self.status_message = ('eta_sizing', {})
        self.summary.configure(foreground='')
        self.current_bar.stop()
        self.current_bar.configure(mode='indeterminate', value=0)
        self.current_bar.start(20)
        self.render()

    def start_item(self, key, name, index, total):
        self.estimate.start(key)
        self.current_info = (name, index, total)
        self.item_started = time.monotonic()
        self.total = total
        self.current_message = ('analyzing', {})
        self.status_message = ('running', {'name': f'{index}/{total} : {name}', 'phase': self.tr('scan_phase'), 'seconds': 0})
        self.current_bar.stop()
        self.current_bar.configure(mode='indeterminate', value=0)
        self.current_bar.start(20)

    def percent(self, value):
        self.estimate.update(value)
        self.current_message = ('extract_percent', {'percent': value})
        self.current_bar.stop()
        self.current_bar.configure(mode='determinate', value=value)

    def end_item(self, key, succeeded, completed, total):
        self.estimate.finish(key, succeeded)
        self.completed, self.total = completed, total
        self.current_bar.stop()
        self.current_bar.configure(mode='determinate', value=100 if succeeded else 0)
        self.current_message = ('extract_percent', {'percent': 100}) if succeeded else ('folder_failed', {})

    def finish(self, key, **values):
        self.running, self.finished = False, True
        self.status_message = (key, values)
        if str(self.current_bar.cget('mode')) == 'indeterminate':
            self.current_bar.stop()
            self.current_bar.configure(mode='determinate', value=0)
        self.add_log(key, **values)
        errors = values.get('errors', values.get('failures', 0))
        self.summary.configure(foreground='#b3261e' if errors or key == 'extract_failed' else '#237344')
        self.render()

    def add_log(self, key, **values):
        self.entries.append((key, values))
        self.log.configure(state='normal')
        self.log.insert('end', self.tr(key, **values) + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def toggle_details(self):
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.details_frame.pack(fill='both', expand=True, pady=(4, 0))
        else:
            self.details_frame.pack_forget()
        self.render()

    def change_language(self, language):
        self.language = language
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        for key, values in self.entries:
            self.log.insert('end', self.tr(key, **values) + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')
        self.render()

    def render(self):
        self.current_var.set(self.tr(self.current_message[0], **self.current_message[1]))
        if self.running and self.current_info and self.status_message[0] == 'running':
            name, index, total = self.current_info
            phase = (f'{self.current_message[1]["percent"]} %' if self.current_message[0] == 'extract_percent'
                     else self.tr('scan_phase'))
            self.status_var.set(self.tr('running', name=f'{index}/{total} : {name}', phase=phase,
                                        seconds=int(time.monotonic() - self.item_started)))
        else:
            self.status_var.set(self.tr(self.status_message[0], **self.status_message[1]))
        fraction = self.estimate.progress_fraction()
        if self.finished and self.completed == self.total:
            fraction = 1
        percentage = min(100, math.floor(fraction * 100 + 1e-8))
        self.total_bar.configure(value=fraction * 100)
        self.total_var.set(self.tr('total_progress', percent=percentage, done=self.completed, total=self.total))
        key, values = self.estimate.message(self.running, self.finished, self.stop_requested)
        self.eta_var.set(self.tr(key, **values))
        self.details_button.configure(text=self.tr('hide_details' if self.details_visible else 'show_details'))

    def shutdown(self):
        self.current_bar.stop()
