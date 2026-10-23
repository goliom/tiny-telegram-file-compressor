"""Recursive extraction tab with explicit keep/delete policy."""
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from archive_layout import is_link
from archive_tools import seven_zip
from decompresser_tout import process_locked
from ui_components import LocalizedFrame, TaskMonitor, open_folder


class ExtractionPanel(LocalizedFrame):
    def __init__(self, parent, language='fr', on_state=None):
        super().__init__(parent, language, padding=10)
        self.on_state = on_state or (lambda: None)
        self.running = False
        self.available = True
        self.stop = threading.Event()
        self.events = queue.Queue()
        self.destination = None
        self.root_var = tk.StringVar(master=self)
        self.policy_var = tk.StringVar(master=self, value='delete')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        source = self.local(ttk.LabelFrame(self, padding=8), 'step_extract_root')
        source.grid(row=0, column=0, sticky='ew')
        source.columnconfigure(0, weight=1)
        self.source_entry = ttk.Entry(source, textvariable=self.root_var)
        self.source_entry.grid(row=0, column=0, sticky='ew')
        self.browse = self.local(ttk.Button(source, command=self.choose_folder), 'browse')
        self.browse.grid(row=0, column=1, padx=(6, 0))
        self.local(ttk.Label(source, wraplength=720), 'extract_formats').grid(row=1, column=0, columnspan=2, sticky='w', pady=(6, 0))

        policy = self.local(ttk.LabelFrame(self, padding=8), 'step_policy')
        policy.grid(row=1, column=0, sticky='ew', pady=6)
        choices = ttk.Frame(policy)
        choices.pack(fill='x')
        self.keep_radio = self.local(ttk.Radiobutton(choices, variable=self.policy_var, value='keep'), 'keep_archives')
        self.keep_radio.pack(side='left')
        self.delete_radio = self.local(ttk.Radiobutton(choices, variable=self.policy_var, value='delete'), 'delete_archives')
        self.delete_radio.pack(side='left', padx=(20, 0))
        self.local(ttk.Label(policy, wraplength=720), 'policy_hint').pack(anchor='w', pady=(6, 0))

        work = self.local(ttk.LabelFrame(self, padding=8), 'step_run')
        work.grid(row=2, column=0, sticky='ew')
        buttons = ttk.Frame(work)
        buttons.pack(fill='x', pady=(0, 5))
        self.start_button = self.local(ttk.Button(buttons, command=self.start), 'extract_start')
        self.start_button.pack(side='left')
        self.stop_button = self.local(ttk.Button(buttons, command=self.request_stop, state='disabled'), 'extract_stop')
        self.stop_button.pack(side='left', padx=6)
        self.open_button = self.local(ttk.Button(buttons, command=self.open_destination, state='disabled'), 'open_destination')
        self.open_button.pack(side='right')
        self.monitor = TaskMonitor(work, language)
        self.monitor.pack(fill='both', expand=True)
        self.inputs = [self.source_entry, self.browse, self.keep_radio, self.delete_radio, self.start_button]
        self.timer = self.after(150, self.refresh)

    def choose_folder(self):
        selected = filedialog.askdirectory(parent=self, title=self.tr('extract_choose'), mustexist=True)
        if selected:
            self.root_var.set(selected)

    def set_available(self, enabled):
        self.available = enabled
        for widget in self.inputs:
            widget.configure(state='normal' if enabled and not self.running else 'disabled')
        self.stop_button.configure(state='normal' if self.running and not self.stop.is_set() else 'disabled')

    def start(self):
        if self.running or not self.available:
            return
        source = Path(self.root_var.get().strip()).expanduser()
        if not self.root_var.get().strip() or is_link(source) or not source.is_dir():
            messagebox.showerror(self.tr('folder_error'), self.tr('invalid_source', path=source), parent=self)
            return
        root = source.resolve()
        try:
            executable = seven_zip()
        except RuntimeError:
            messagebox.showerror('7-Zip', self.tr('sevenzip_missing'), parent=self)
            return
        delete_archives = self.policy_var.get() == 'delete'
        self.destination = root
        self.open_button.configure(state='disabled')
        self.running = True
        self.stop.clear()
        self.monitor.begin()
        self.monitor.status_message = ('extract_scanning', {})
        self.set_available(self.available)
        self.on_state()
        output_events, cancel = self.events, self.stop

        def work():
            try:
                process_locked(root, executable, delete_archives=delete_archives, stop_event=cancel,
                               on_event=lambda kind, **values: output_events.put((kind, values)))
            except Exception as error:
                output_events.put(('fatal', {'error': str(error)}))
            finally:
                output_events.put(('worker_done', {}))

        threading.Thread(target=work, daemon=False).start()

    def request_stop(self):
        if self.running and not self.stop.is_set():
            self.stop.set()
            self.monitor.stop_requested = True
            self.monitor.add_log('extract_stop_requested')
            self.set_available(self.available)

    def open_destination(self):
        if self.destination:
            open_folder(self.destination, self, self.language)

    def change_language(self, language):
        self.translate_widgets(language)
        self.monitor.change_language(language)

    def refresh(self):
        try:
            while True:
                kind, values = self.events.get_nowait()
                if kind == 'weights':
                    self.monitor.estimate.add(values['weights'])
                elif kind == 'scan':
                    self.monitor.status_message = ('extract_scanning', {})
                elif kind == 'current':
                    self.monitor.start_item(values['name'], **values)
                    self.monitor.add_log('extract_current', **values)
                elif kind == 'percent':
                    self.monitor.percent(values['percent'])
                elif kind == 'archive_done':
                    succeeded = values['status'] != 'error'
                    self.monitor.end_item(values['name'], succeeded, values['completed'], values['total'])
                    if succeeded:
                        self.monitor.add_log('extract_' + values['status'], name=values['name'])
                    else:
                        self.monitor.add_log('error', name=values['name'], error=values['error'])
                elif kind == 'finished':
                    key = 'extract_stopped' if values.pop('stopped') else 'extract_done'
                    self.monitor.finish(key, **values)
                elif kind == 'fatal':
                    self.monitor.finish('extract_failed', **values)
                elif kind == 'worker_done':
                    self.running = False
                    self.open_button.configure(state='normal' if self.destination.is_dir() else 'disabled')
                    self.set_available(self.available)
                    self.on_state()
        except queue.Empty:
            pass
        self.monitor.render()
        self.timer = self.after(150, self.refresh)

    def shutdown(self):
        self.after_cancel(self.timer)
        self.monitor.shutdown()
