from gui_helpers import AppGuiTest
from compression_i18n import LANGUAGES
from app_identity import APP_NAME


class DesktopLayoutTest(AppGuiTest):
    def test_tabs_global_language_and_description(self):
        self.assertEqual(self.root.title(), APP_NAME)
        self.assertEqual(len(self.app.notebook.tabs()), 2)
        self.assertEqual([self.app.notebook.tab(tab, 'text') for tab in self.app.notebook.tabs()],
                         ['Compresser', 'Décompresser'])
        self.assertIn('archives multiples de 2 000 MB maximum', self.app.description.cget('text'))
        self.assertLessEqual(self.root.minsize()[1], 620)
        for code, name in LANGUAGES.items():
            self.app.change_language(code)
            self.assertEqual(self.app.language_button.cget('text'), name)
            self.assertEqual(self.app.compression.language, code)
            self.assertEqual(self.app.extraction.language, code)
            self.assertEqual(self.root.title(), APP_NAME)
        self.assertFalse(any(widget.winfo_class() == 'Toplevel' for widget in self.root.winfo_children()))

    def test_controls_fit_on_a_portable_display_in_each_language(self):
        self.root.geometry('800x668+0+0')
        self.root.deiconify()
        for code in LANGUAGES:
            self.app.change_language(code)
            for panel in self.app.panels:
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
            for panel in self.app.panels:
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
