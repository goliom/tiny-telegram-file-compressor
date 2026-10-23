from gui_helpers import AppGuiTest
from compression_i18n import LANGUAGES
from compression_i18n import text
from app_identity import APP_NAME, APP_VERSION
from unittest.mock import patch


class DesktopLayoutTest(AppGuiTest):
    def test_task_descriptions_follow_tab_and_language(self):
        for language in LANGUAGES:
            self.app.change_language(language)
            for panel, key in ((self.app.extraction, 'intro_extract'),
                               (self.app.images, 'intro_images'),
                               (self.app.compression, 'intro_compress')):
                self.app.notebook.select(panel)
                self.root.update()
                self.assertEqual(self.app.description.cget('text'), text(key, language))

    def test_images_guidance_and_controls_fit_small_window(self):
        self.root.geometry('800x620+0+0')
        self.root.deiconify()
        panel = self.app.images
        self.app.notebook.select(panel)
        for language in LANGUAGES:
            self.app.change_language(language)
            self.root.update_idletasks()
            for widget in (panel.entry, panel.browse, panel.rename_check, panel.convert_check,
                           panel.example, panel.start_button, panel.open_button, panel.status, panel.log):
                with self.subTest(language=language, widget=widget):
                    self.assertGreater(widget.winfo_height(), 1)
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         self.root.winfo_rootx() + self.root.winfo_width())
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height())
        self.root.withdraw()

    def test_extraction_folder_supplies_other_tab_defaults(self):
        folder = str(self.directory)
        with patch('decompression_gui.filedialog.askdirectory', return_value=folder):
            self.app.extraction.browse.invoke()
        self.assertEqual(self.app.images.root_var.get(), folder)
        self.assertEqual(self.app.compression.destination_var.get(), str(self.directory.parent))
        self.assertEqual(self.app.compression.default_folder, folder)
        self.assertEqual([row.path for row in self.app.compression.rows.values()], [self.directory])
        for action in (self.app.compression.add_folder, self.app.compression.add_children,
                       self.app.compression.choose_destination, self.app.images.choose):
            with patch('tkinter.filedialog.askdirectory', return_value='') as dialog:
                action()
                self.assertEqual(dialog.call_args.kwargs['initialdir'], str(self.directory.parent) if action == self.app.compression.choose_destination else folder)
        other = self.directory/'Other'
        other.mkdir()
        manual = self.directory/'Manual'
        manual.mkdir()
        self.app.compression.add_paths([manual])
        self.app.images.root_var.set(str(other))
        self.app.compression.destination_var.set(str(other))
        self.app.change_language('en')
        self.assertEqual(self.app.images.root_var.get(), str(other))
        self.assertEqual(self.app.compression.destination_var.get(), str(other))
        self.app.extraction.root_var.set(str(other))
        self.assertEqual(self.app.compression.default_folder, str(other))
        self.assertEqual({row.path for row in self.app.compression.rows.values()}, {other, manual})
        self.assertEqual(self.app.compression.destination_var.get(), str(other.parent))
        self.app.extraction.root_var.set(str(other))
        self.assertEqual(len(self.app.compression.rows), 2)
        self.app.extraction.root_var.set(str(other/'missing'))
        self.assertEqual(self.app.images.root_var.get(), str(other))
        self.app.extraction.root_var.set('')
        self.assertEqual(self.app.compression.destination_var.get(), str(self.directory))

    def test_tabs_global_language_and_description(self):
        self.assertEqual(self.root.title(), f'{APP_NAME} v{APP_VERSION}')
        self.assertEqual(len(self.app.notebook.tabs()), 3)
        self.assertEqual([self.app.notebook.tab(tab, 'text') for tab in self.app.notebook.tabs()],
                         ['D\u00e9compresser', 'Images', 'Compresser'])
        self.assertIn('Extrait les archives', self.app.description.cget('text'))
        self.assertLessEqual(self.root.minsize()[1], 620)
        for code, name in LANGUAGES.items():
            self.app.change_language(code)
            self.assertEqual(self.app.language_button.cget('text'), name)
            self.assertEqual(self.app.compression.language, code)
            self.assertEqual(self.app.extraction.language, code)
            self.assertEqual(self.root.title(), f'{APP_NAME} v{APP_VERSION}')
        self.assertFalse(any(widget.winfo_class() == 'Toplevel' for widget in self.root.winfo_children()))

    def test_controls_fit_on_a_portable_display_in_each_language(self):
        self.root.geometry('800x668+0+0')
        self.root.deiconify()
        for code in LANGUAGES:
            self.app.change_language(code)
            for panel in self.app.panels[:2]:
                self.app.notebook.select(panel)
                self.root.update_idletasks()
                for widget in [panel.start_button, panel.stop_button, panel.open_button,
                               panel.monitor.details_button, panel.monitor.summary]:
                    with self.subTest(language=code, panel=type(panel).__name__, widget=widget):
                        self.assertTrue(widget.winfo_ismapped())
                        self.assertGreaterEqual(widget.winfo_rooty(), self.root.winfo_rooty())
                        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                             self.root.winfo_rooty() + self.root.winfo_height())
                        self.assertGreaterEqual(widget.winfo_rootx(), self.root.winfo_rootx())
                        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                             self.root.winfo_rootx() + self.root.winfo_width())
                if panel is self.app.compression:
                    self.assertGreater(panel.tree.winfo_height(), 40)
        self.root.withdraw()

    def test_expanded_details_and_source_controls_remain_reachable(self):
        self.root.geometry('800x620+0+0')
        self.root.deiconify()
        for code in LANGUAGES:
            self.app.change_language(code)
            for panel in self.app.panels[:2]:
                self.app.notebook.select(panel)
                panel.monitor.toggle_details()
                self.root.update_idletasks()
                controls = list(panel.inputs) + [panel.monitor.log, panel.monitor.details_button]
                if panel is self.app.compression:
                    controls.append(panel.remove_button)
                for widget in controls:
                    with self.subTest(language=code, panel=type(panel).__name__, widget=widget):
                        self.assertGreater(widget.winfo_height(), 1)
                        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                             self.root.winfo_rooty() + self.root.winfo_height())
                        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                             self.root.winfo_rootx() + self.root.winfo_width())
                panel.monitor.toggle_details()
        self.root.withdraw()
