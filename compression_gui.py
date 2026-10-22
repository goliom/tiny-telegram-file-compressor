"""Compression tab: checkbox rows, metadata, destination and job monitoring."""
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from archive_layout import is_link
from archive_tools import seven_zip
from compresser_dossiers import compress_folder
from ui_components import LocalizedFrame, TaskMonitor, open_folder, size_text
from work_estimate import folder_weight


@dataclass
class FolderRow:
    path: Path
    checked: bool = True
    size: int | None = None
    state: str = 'row_ready'


def read_metadata_jobs(jobs, events, stop):
    """Do not retain any Tk widget in the metadata worker."""
    while not stop.is_set():
        job = jobs.get()
        if job is None:
            return
        row_id, path = job
        size = folder_weight(path, stop)
        events.put(('metadata', {'key': row_id, 'size': size}))


class CompressionPanel(LocalizedFrame):
    def __init__(self, parent, language='fr', on_state=None):
        super().__init__(parent, language, padding=10)
        self.on_state = on_state or (lambda: None)
        self.running = False
        self.available = True
        self.stop = threading.Event()
        self.metadata_stop = threading.Event()
        self.events = queue.Queue()
        self.metadata_jobs = queue.Queue()
        self.rows = {}
        self.next_id = 0
        self.destination = None
        self.destination_var = tk.StringVar(master=self)
        self.selection_var = tk.StringVar(master=self)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1, minsize=125)

        sources = self.local(ttk.LabelFrame(self, padding=6), 'step_sources')
        sources.grid(row=0, column=0, sticky='nsew')
        sources.columnconfigure(0, weight=1)
        sources.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(sources)
        toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 4))
        self.add_button = self.local(ttk.Button(toolbar, command=self.add_folder), 'add_folder')
        self.add_button.pack(side='left')
        self.children_button = self.local(ttk.Button(toolbar, command=self.add_children), 'add_children')
        self.children_button.pack(side='left', padx=(6, 0))
        table = ttk.Frame(sources)
        table.grid(row=1, column=0, sticky='nsew')
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=('folder', 'location', 'size', 'state'),
                                 show='tree headings', selectmode='extended', height=4)
        self.tree.column('#0', width=34, minwidth=34, stretch=False)
        for column, width, stretch in [('folder', 180, True), ('location', 230, True),
                                       ('size', 90, False), ('state', 100, False)]:
            self.tree.column(column, width=width, minwidth=65, stretch=stretch)
        yscroll = ttk.Scrollbar(table, command=self.tree.yview)
        xscroll = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        self.tree.bind('<Button-1>', self.click_checkbox)
        self.tree.bind('<space>', self.toggle_highlighted)
        self.tree.bind('<<TreeviewSelect>>', lambda event: self.update_controls())
        self.tree.heading('#0', command=self.toggle_all)
        self.tree.tag_configure('row_done', foreground='#237344')
        self.tree.tag_configure('row_error', foreground='#b3261e')
        actions = ttk.Frame(sources)
        actions.grid(row=2, column=0, sticky='ew', pady=(4, 0))
        self.all_button = self.local(ttk.Button(actions, command=lambda: self.set_all(True)), 'select_all')
        self.all_button.pack(side='left')
        self.none_button = self.local(ttk.Button(actions, command=lambda: self.set_all(False)), 'select_none')
        self.none_button.pack(side='left', padx=4)
        self.remove_button = self.local(ttk.Button(actions, command=self.remove_highlighted), 'remove_rows')
        self.remove_button.pack(side='left')
        ttk.Label(actions, textvariable=self.selection_var).pack(side='right')

        destination = self.local(ttk.LabelFrame(self, padding=6), 'step_destination')
        destination.grid(row=1, column=0, sticky='ew', pady=6)
        destination.columnconfigure(0, weight=1)
        self.destination_entry = ttk.Entry(destination, textvariable=self.destination_var)
        self.destination_entry.grid(row=0, column=0, sticky='ew')
        self.browse = self.local(ttk.Button(destination, command=self.choose_destination), 'browse')
        self.browse.grid(row=0, column=1, padx=(6, 0))
        self.local(ttk.Label(destination), 'settings_summary').grid(row=1, column=0, columnspan=2, sticky='w', pady=(3, 0))

        work = self.local(ttk.LabelFrame(self, padding=6), 'step_run')
        work.grid(row=2, column=0, sticky='ew')
        buttons = ttk.Frame(work)
        buttons.pack(fill='x', pady=(0, 5))
        self.start_button = self.local(ttk.Button(buttons, command=self.start), 'start_compact')
        self.start_button.pack(side='left')
        self.stop_button = self.local(ttk.Button(buttons, command=self.request_stop, state='disabled'), 'stop')
        self.stop_button.pack(side='left', padx=6)
        self.open_button = self.local(ttk.Button(buttons, command=self.open_destination, state='disabled'), 'open_destination')
        self.open_button.pack(side='right')
        self.monitor = TaskMonitor(work, language)
        self.monitor.pack(fill='both', expand=True)
        self.inputs = [self.add_button, self.children_button, self.all_button, self.none_button,
                       self.destination_entry, self.browse]
        self.change_language(language)
        self.timer = self.after(150, self.refresh)
        threading.Thread(target=read_metadata_jobs,
                         args=(self.metadata_jobs, self.events, self.metadata_stop), daemon=True).start()

    def add_paths(self, paths, check_existing=False):
        if not self.available or self.running:
            return
        existing = {row.path: key for key, row in self.rows.items()}
        for path in paths:
            path = Path(path).resolve()
            if path in existing:
                if check_existing:
                    self.rows[existing[path]].checked = True
                    self.render_row(existing[path])
                continue
            self.next_id += 1
            key = str(self.next_id)
            self.rows[key] = FolderRow(path)
            existing[path] = key
            self.tree.insert('', 'end', iid=key)
            self.render_row(key)
            self.metadata_jobs.put((key, path))
        if self.rows and not self.destination_var.get().strip():
            self.destination_var.set(str(next(iter(self.rows.values())).path.parent))
        self.update_controls()

    def add_folder(self):
        selected = filedialog.askdirectory(parent=self, title=self.tr('folder_dialog'), mustexist=True)
        if not selected:
            return
        path = Path(selected).absolute()
        if is_link(path) or not path.is_dir() or not path.name:
            messagebox.showerror(self.tr('folder_error'), self.tr('invalid_source', path=path), parent=self)
            return
        self.add_paths([path], check_existing=True)

    def add_children(self):
        selected = filedialog.askdirectory(parent=self, title=self.tr('parent_dialog'), mustexist=True)
        if not selected:
            return
        try:
            paths = sorted((path for path in Path(selected).resolve().iterdir() if path.is_dir() and not is_link(path)
                            and not path.name.endswith('.compression-en-cours')
                            and '.extraction-en-cours' not in path.name), key=lambda path: path.name.casefold())
        except OSError as error:
            messagebox.showerror(self.tr('read_error'), str(error), parent=self)
            return
        self.add_paths(paths)

    def choose_destination(self):
        selected = filedialog.askdirectory(parent=self, title=self.tr('destination_dialog'))
        if selected:
            self.destination_var.set(selected)

    def render_row(self, key):
        row = self.rows[key]
        self.tree.item(key, text='☑' if row.checked else '☐', tags=(row.state,),
                       values=(row.path.name, str(row.path.parent), size_text(row.size, self.language), self.tr(row.state)))

    def click_checkbox(self, event):
        if self.running or not self.available or self.tree.identify_region(event.x, event.y) not in {'tree', 'cell'}:
            return
        key = self.tree.identify_row(event.y)
        if key and self.tree.identify_column(event.x) == '#0':
            self.tree.focus_set()
            self.tree.focus(key)
            self.tree.selection_set(key)
            self.rows[key].checked = not self.rows[key].checked
            self.render_row(key)
            self.update_controls()
            return 'break'

    def toggle_highlighted(self, event=None):
        if self.available and not self.running:
            for key in self.tree.selection():
                self.rows[key].checked = not self.rows[key].checked
                self.render_row(key)
            self.update_controls()
        return 'break'

    def toggle_all(self):
        self.set_all(not self.rows or not all(row.checked for row in self.rows.values()))

    def set_all(self, checked):
        if self.available and not self.running:
            for key, row in self.rows.items():
                row.checked = checked
                self.render_row(key)
            self.update_controls()

    def remove_highlighted(self):
        if self.available and not self.running:
            for key in self.tree.selection():
                self.rows.pop(key)
                self.tree.delete(key)
            self.update_controls()

    def update_controls(self):
        enabled = self.available and not self.running
        for widget in self.inputs:
            widget.configure(state='normal' if enabled else 'disabled')
        self.start_button.configure(state='normal' if enabled and any(row.checked for row in self.rows.values()) else 'disabled')
        self.remove_button.configure(state='normal' if enabled and self.tree.selection() else 'disabled')
        self.stop_button.configure(state='normal' if self.running and not self.stop.is_set() else 'disabled')
        self.selection_var.set(self.tr('selection_count', selected=sum(row.checked for row in self.rows.values()), total=len(self.rows)))
        self.tree.heading('#0', text='☑' if self.rows and all(row.checked for row in self.rows.values()) else '☐')

    def set_available(self, enabled):
        self.available = enabled
        self.update_controls()

    def start(self):
        if self.running or not self.available:
            return
        chosen = [(key, row) for key, row in self.rows.items() if row.checked]
        if not chosen:
            return
        if not self.destination_var.get().strip():
            messagebox.showinfo(self.tr('destination_title'), self.tr('choose_destination'), parent=self)
            return
        destination = Path(self.destination_var.get()).expanduser().resolve()
        names = {}
        for key, row in chosen:
            source = row.path
            if source.name.casefold() in names:
                messagebox.showerror(self.tr('duplicate_title'),
                                     self.tr('duplicate_names', first=names[source.name.casefold()], second=source), parent=self)
                return
            names[source.name.casefold()] = source
            if destination == source or destination.is_relative_to(source):
                messagebox.showerror(self.tr('destination_title'), self.tr('destination_outside'), parent=self)
                return
        try:
            executable = seven_zip()
        except RuntimeError:
            messagebox.showerror('7-Zip', self.tr('sevenzip_missing'), parent=self)
            return
        self.destination = destination
        self.open_button.configure(state='disabled')
        self.running = True
        self.stop.clear()
        self.monitor.begin(len(chosen))
        for key, row in chosen:
            row.state = 'row_ready'
            self.render_row(key)
        sources = [(key, row.path, row.size) for key, row in chosen]
        self.update_controls()
        self.on_state()
        output_events, cancel, job_language = self.events, self.stop, self.language

        def work():
            success = failures = 0
            weights = {}
            for key, source, cached_size in sources:
                if cancel.is_set():
                    break
                weights[key] = cached_size if cached_size is not None else folder_weight(source, cancel)
            output_events.put(('weights', {'weights': weights}))
            for index, (key, source, _) in enumerate(sources, 1):
                if cancel.is_set():
                    break
                output_events.put(('current', {'key': key, 'name': source.name, 'index': index, 'total': len(sources)}))
                succeeded = False
                try:
                    volumes = compress_folder(source, destination, executable, language=job_language,
                                              on_progress=lambda percent: output_events.put(('percent', {'value': percent})))
                    success += 1
                    succeeded = True
                    output_events.put(('log', {'key': 'success', 'name': source.name, 'count': len(volumes)}))
                except Exception as error:
                    failures += 1
                    output_events.put(('log', {'key': 'error', 'name': source.name, 'error': str(error)}))
                output_events.put(('item_done', {'key': key, 'success': succeeded, 'completed': index, 'total': len(sources)}))
            output_events.put(('done', {'success': success, 'failures': failures, 'stopped': cancel.is_set()}))

        threading.Thread(target=work, daemon=False).start()

    def request_stop(self):
        if self.running and not self.stop.is_set():
            self.stop.set()
            self.monitor.stop_requested = True
            self.monitor.add_log('stop_requested')
            self.update_controls()

    def open_destination(self):
        if self.destination:
            open_folder(self.destination, self, self.language)

    def change_language(self, language):
        self.translate_widgets(language)
        for column in ('folder', 'location', 'size', 'state'):
            self.tree.heading(column, text=self.tr(column + '_column'))
        for key in self.rows:
            self.render_row(key)
        self.monitor.change_language(language)
        self.update_controls()

    def refresh(self):
        try:
            while True:
                kind, values = self.events.get_nowait()
                if kind == 'metadata':
                    if values['key'] in self.rows:
                        self.rows[values['key']].size = values['size']
                        self.render_row(values['key'])
                elif kind == 'weights':
                    self.monitor.estimate.add(values['weights'])
                    for key, size in values['weights'].items():
                        if key in self.rows:
                            self.rows[key].size = size
                            self.render_row(key)
                elif kind == 'current':
                    self.rows[values['key']].state = 'row_running'
                    self.render_row(values['key'])
                    self.monitor.start_item(**values)
                    self.monitor.add_log('compressing', name=values['name'])
                elif kind == 'percent':
                    self.monitor.percent(values['value'])
                elif kind == 'log':
                    key = values.pop('key')
                    self.monitor.add_log(key, **values)
                elif kind == 'item_done':
                    self.rows[values['key']].state = 'row_done' if values['success'] else 'row_error'
                    self.render_row(values['key'])
                    self.monitor.end_item(values['key'], values['success'], values['completed'], values['total'])
                elif kind == 'done':
                    self.running = False
                    key = 'stopped' if values.pop('stopped') else 'done'
                    self.monitor.finish(key, **values)
                    self.open_button.configure(state='normal' if self.destination.is_dir() else 'disabled')
                    self.update_controls()
                    self.on_state()
        except queue.Empty:
            pass
        self.monitor.render()
        self.timer = self.after(150, self.refresh)

    def shutdown(self):
        self.after_cancel(self.timer)
        self.metadata_stop.set()
        self.metadata_jobs.put(None)
        self.monitor.shutdown()
