"""Image collection tab; workers communicate exclusively through a queue."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from image_collect import collect_images
from ui_components import LocalizedFrame, open_folder


class ImagePanel(LocalizedFrame):
    def __init__(self, parent, on_state=None):
        super().__init__(parent, padding=12)
        self.on_state = on_state or (lambda: None)
        self.running = False
        self.available = True
        self.stop = threading.Event()
        self.events = queue.Queue()
        self.root_var = tk.StringVar(master=self)
        self.local(ttk.Label(self, wraplength=720), 'images_hint').pack(fill='x', pady=(0, 12))
        row = ttk.Frame(self)
        row.pack(fill='x')
        self.entry = ttk.Entry(row, textvariable=self.root_var)
        self.entry.pack(side='left', fill='x', expand=True)
        self.browse = self.local(ttk.Button(row, command=self.choose), 'browse')
        self.browse.pack(side='right', padx=6)
        buttons = ttk.Frame(self)
        buttons.pack(fill='x', pady=12)
        self.start_button = self.local(ttk.Button(buttons, command=self.start), 'images_start')
        self.start_button.pack(side='left')
        self.stop_button = self.local(ttk.Button(buttons, command=self.request_stop), 'images_stop')
        self.stop_button.pack(side='left', padx=6)
        self.open_button = self.local(ttk.Button(buttons, command=self.open_destination), 'open_destination')
        self.open_button.pack(side='right')
        self.bar = ttk.Progressbar(self, maximum=100)
        self.bar.pack(fill='x')
        self.status = ttk.Label(self, wraplength=720)
        self.status.pack(fill='x', pady=8)
        self.log = tk.Text(self, height=10, state='disabled', wrap='word')
        self.log.pack(fill='both', expand=True)
        self.message = ('ready', {})
        self.set_available(True)
        self.timer = self.after(100, self.refresh)

    def choose(self):
        chosen = filedialog.askdirectory(parent=self, mustexist=True)
        if chosen:
            self.root_var.set(chosen)

    def set_available(self, enabled):
        self.available = enabled
        for widget in (self.entry, self.browse, self.start_button):
            widget.configure(state='normal' if enabled and not self.running else 'disabled')
        self.stop_button.configure(state='normal' if self.running and not self.stop.is_set() else 'disabled')

    def start(self):
        if self.running or not self.available:
            return
        if not self.root_var.get().strip() or not Path(self.root_var.get()).is_dir():
            messagebox.showerror(self.tr('folder_error'), self.tr('choose_destination'), parent=self)
            return
        root = Path(self.root_var.get()).resolve()
        self.running = True
        self.stop.clear()
        self.bar.configure(mode='indeterminate', value=0)
        self.bar.start()
        self.message = ('images_scan', {})
        self.on_state()
        events, stop = self.events, self.stop
        def work():
            try:
                collect_images(root, stop, lambda kind, **values: events.put((kind, values)))
            except Exception as error:
                events.put(('fatal', {'error': str(error)}))
            finally:
                events.put(('worker_done', {}))
        threading.Thread(target=work, daemon=False).start()

    def request_stop(self):
        self.stop.set()
        self.set_available(self.available)

    def open_destination(self):
        if self.root_var.get():
            open_folder(Path(self.root_var.get()), self, self.language)

    def change_language(self, language):
        self.translate_widgets(language)
        self.status.configure(text=self.tr(self.message[0], **self.message[1]))

    def refresh(self):
        try:
            while True:
                kind, values = self.events.get_nowait()
                if kind == 'progress':
                    self.bar.stop()
                    self.bar.configure(mode='determinate', value=100 * values['done'] / values['total'])
                    self.message = ('total_progress', dict(percent=int(100 * values['done']/values['total']), **values))
                elif kind == 'log':
                    self.log.configure(state='normal')
                    self.log.insert('end', values['message'] + '\n')
                    self.log.see('end')
                    self.log.configure(state='disabled')
                elif kind == 'finished':
                    stopped = values.pop('stopped')
                    self.message = ('images_stopped' if stopped else 'images_done', values)
                elif kind == 'fatal':
                    self.message = ('extract_failed', values)
                elif kind == 'worker_done':
                    self.bar.stop()
                    self.bar.configure(mode='determinate')
                    self.running = False
                    self.on_state()
        except queue.Empty:
            pass
        self.status.configure(text=self.tr(self.message[0], **self.message[1]))
        self.timer = self.after(100, self.refresh)

    def shutdown(self):
        self.after_cancel(self.timer)
        self.bar.stop()
