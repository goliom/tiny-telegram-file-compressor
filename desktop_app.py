"""Single-window, bilingual/multilingual notebook application."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from app_identity import APP_NAME, apply_identity, configure_app_id
from compression_i18n import LANGUAGES, text
from compression_gui import CompressionPanel
from decompression_gui import ExtractionPanel
from image_gui import ImagePanel


class DesktopApp:
    def __init__(self, root=None):
        configure_app_id()
        self.root = root if root is not None else tk.Tk()
        apply_identity(self.root)
        self.language = 'fr'
        self.closing = False
        self.destroyed = False
        height = min(740, max(620, self.root.winfo_screenheight() - 100))
        self.root.geometry(f'960x{height}')
        self.root.minsize(800, 620)
        shell = ttk.Frame(self.root, padding=12)
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x')
        self.language_button = ttk.Menubutton(header, text=LANGUAGES['fr'])
        self.language_button.pack(side='right', padx=(8, 0))
        self.language_var = tk.StringVar(master=self.root, value='fr')
        menu = tk.Menu(self.language_button, tearoff=False)
        for code, name in LANGUAGES.items():
            menu.add_radiobutton(label=name, variable=self.language_var, value=code,
                                 command=lambda chosen=code: self.change_language(chosen))
        self.language_button.configure(menu=menu)
        ttk.Label(header, text=APP_NAME, font=('Segoe UI', 15, 'bold')).pack(side='left')
        self.description = ttk.Label(shell, text=text('intro_extract'), wraplength=900)
        self.description.pack(fill='x', pady=(4, 8))
        shell.bind('<Configure>', lambda event: self.description.configure(wraplength=max(500, event.width - 24)))
        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill='both', expand=True)
        self.compression = CompressionPanel(self.notebook, on_state=self.update_busy)
        self.extraction = ExtractionPanel(self.notebook, on_state=self.update_busy)
        self.images = ImagePanel(self.notebook, on_state=self.update_busy)
        self.panels = [self.compression, self.extraction, self.images]
        self.folder_trace = self.extraction.root_var.trace_add('write', self.share_extraction_folder)
        self.notebook.add(self.extraction, text=text('tab_extract'))
        self.notebook.add(self.images, text=text('tab_images'))
        self.notebook.add(self.compression, text=text('tab_compress'))
        self.notebook.bind('<<NotebookTabChanged>>', self.update_description)
        self.root.protocol('WM_DELETE_WINDOW', self.request_close)

    def share_extraction_folder(self, *_):
        folder = self.extraction.root_var.get().strip()
        if not folder:
            return
        try:
            if not Path(folder).expanduser().is_dir():
                return
        except OSError:
            return
        self.images.root_var.set(folder)
        self.compression.set_default_source(Path(folder).expanduser().resolve())

    def update_description(self, *_):
        selected = self.notebook.select()
        key = ('intro_images' if selected == str(self.images) else
               'intro_compress' if selected == str(self.compression) else 'intro_extract')
        self.description.configure(text=text(key, self.language))

    def change_language(self, language):
        self.language = language
        self.language_var.set(language)
        self.language_button.configure(text=LANGUAGES[language])
        self.update_description()
        for panel in self.panels:
            panel.change_language(language)
        self.notebook.tab(self.compression, text=text('tab_compress', language))
        self.notebook.tab(self.extraction, text=text('tab_extract', language))
        self.notebook.tab(self.images, text=text('tab_images', language))

    def update_busy(self):
        busy = any(panel.running for panel in self.panels)
        for panel in self.panels:
            panel.set_available(not busy)
        if self.closing and not busy:
            self.root.after_idle(self.destroy)

    def request_close(self):
        self.closing = True
        if any(panel.running for panel in self.panels):
            for panel in self.panels:
                panel.request_stop()
        else:
            self.destroy()

    def destroy(self):
        if self.destroyed:
            return
        self.destroyed = True
        self.extraction.root_var.trace_remove('write', self.folder_trace)
        for panel in self.panels:
            panel.shutdown()
        self.root.destroy()


def launch_gui():
    app = DesktopApp()
    try:
        app.root.mainloop()
    except KeyboardInterrupt:
        app.request_close()
        if not app.destroyed:
            app.root.mainloop()
    return 0
