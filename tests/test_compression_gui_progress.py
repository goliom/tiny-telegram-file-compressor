import threading
from pathlib import Path
from unittest.mock import patch

from gui_helpers import AppGuiTest
from app_identity import APP_NAME
from compresser_dossiers import compress_folder


class CompressionGuiTest(AppGuiTest):
    def test_mouse_checkbox_changes_work_selection_without_removing_source(self):
        self.app.notebook.select(self.app.compression)
        panel = self.app.compression
        folder = self.directory / 'Model'
        folder.mkdir()
        panel.add_paths([folder])
        self.root.geometry('800x668+0+0')
        self.root.deiconify()
        self.root.update_idletasks()
        key = next(iter(panel.rows))
        x, y, width, height = panel.tree.bbox(key, '#0')
        panel.tree.event_generate('<Button-1>', x=x + width // 2, y=y + height // 2)
        self.root.update()
        self.assertFalse(panel.rows[key].checked)
        self.assertEqual(str(panel.start_button.cget('state')), 'disabled')
        self.assertEqual(panel.tree.selection(), (key,))
        panel.tree.event_generate('<Button-1>', x=x + width // 2, y=y + height // 2)
        self.root.update()
        self.assertTrue(panel.rows[key].checked)
        self.assertEqual(str(panel.start_button.cget('state')), 'normal')
        self.assertTrue(folder.is_dir())
        self.root.withdraw()

    def test_multilocation_checkboxes_remove_and_real_compression(self):
        panel = self.app.compression
        first_parent, second_parent = self.directory / 'disk-A', self.directory / 'disk-B'
        first, second = first_parent / 'Model A', second_parent / 'Model B'
        unused = first_parent / 'Unselected'
        for folder in (first, second, unused):
            folder.mkdir(parents=True)
            (folder / 'piece.bin').write_bytes(b'payload' * 100)
        with patch('compression_gui.filedialog.askdirectory', side_effect=[str(first_parent), str(second), str(second)]):
            panel.children_button.invoke()
            panel.add_button.invoke()
            panel.add_button.invoke()
        self.assertEqual(len(panel.rows), 3)
        keys = {row.path: key for key, row in panel.rows.items()}
        # Highlight and press Space to uncheck one row, independently of selection.
        panel.tree.selection_set(keys[unused])
        panel.toggle_highlighted()
        self.assertFalse(panel.rows[keys[unused]].checked)
        self.assertTrue(panel.rows[keys[first]].checked)
        self.pump_until(lambda: all(row.size is not None for row in panel.rows.values()))
        self.assertEqual(panel.rows[keys[first]].size, 700)
        panel.remove_button.invoke()
        self.assertTrue(unused.is_dir())
        self.assertNotIn(keys[unused], panel.rows)
        output = self.directory / 'archives'
        panel.destination_var.set(str(output))
        self.app.change_language('en')
        with patch('compression_gui.compress_folder', wraps=compress_folder) as compressor:
            panel.start_button.invoke()
            self.assertTrue(panel.running)
            self.pump_until(lambda: not panel.running)
        self.assertEqual([call.args[0] for call in compressor.call_args_list], [first, second])
        self.assertTrue(all(call.args[1] == output for call in compressor.call_args_list))
        self.assertEqual(sorted(path.name for path in output.iterdir()), ['Model A.7z', 'Model B.7z'])
        self.assertTrue(all(row.state == 'row_done' for row in panel.rows.values()))
        self.assertTrue(panel.monitor.status_var.get().startswith('Finished: 2 folder(s)'))
        self.assertEqual(float(panel.monitor.total_bar.cget('value')), 100)
        self.assertEqual(str(panel.open_button.cget('state')), 'normal')
        with patch('ui_components.os.startfile') as opener:
            panel.open_button.invoke()
            opener.assert_called_once_with(str(output))

    def test_weighted_progress_eta_language_and_collapsible_log_during_worker(self):
        panel = self.app.compression
        small, large = self.directory / 'small', self.directory / 'large'
        for path, size in [(small, 100), (large, 900)]:
            path.mkdir()
            (path / 'data').write_bytes(b'x' * size)
        panel.add_paths([small, large])
        self.pump_until(lambda: all(row.size is not None for row in panel.rows.values()))
        panel.destination_var.set(str(self.directory / 'archives'))
        now = [0.0]
        panel.monitor.estimate.clock = lambda: now[0]
        release = threading.Event()
        self.releases.append(release)

        def compress(source, destination, executable, on_progress, language):
            on_progress(50)
            if not release.wait(5):
                raise RuntimeError('GUI did not display progress')
            on_progress(100)
            return [Path(destination) / (source.name + '.7z.001')]

        with patch('compression_gui.compress_folder', side_effect=compress), \
             patch('compression_gui.seven_zip', return_value='fake-7z'):
            panel.start_button.invoke()
            self.pump_until(lambda: float(panel.monitor.current_bar.cget('value')) == 50)
            self.assertAlmostEqual(float(panel.monitor.total_bar.cget('value')), 5)
            self.assertEqual(str(self.app.extraction.start_button.cget('state')), 'disabled')
            now[0] = 10
            for code, prefix in [('fr', 'Temps restant estimé'), ('en', 'Estimated time remaining'),
                                 ('es', 'Tiempo restante estimado'), ('it', 'Tempo rimanente stimato')]:
                self.app.change_language(code)
                self.assertEqual(self.root.title(), APP_NAME)
                self.assertTrue(panel.monitor.eta_var.get().startswith(prefix))
                self.assertIn('3 min 10 s', panel.monitor.eta_var.get())
                self.assertAlmostEqual(float(panel.monitor.total_bar.cget('value')), 5)
                self.assertEqual(sum(row.checked for row in panel.rows.values()), 2)
            self.assertFalse(panel.monitor.details_visible)
            panel.monitor.details_button.invoke()
            self.assertTrue(panel.monitor.details_visible)
            self.assertIn('Compressione:', panel.monitor.log.get('1.0', 'end'))
            panel.monitor.details_button.invoke()
            self.assertFalse(panel.monitor.details_visible)
            panel.stop_button.invoke()
            release.set()
            self.pump_until(lambda: not panel.running)
            self.assertEqual(len([row for row in panel.rows.values() if row.state == 'row_done']), 1)
            self.assertIn('Interrotto:', panel.monitor.status_var.get())
            self.assertEqual(str(self.app.extraction.start_button.cget('state')), 'normal')

    def test_duplicate_names_are_reported_before_work(self):
        paths = [self.directory / 'a/Model', self.directory / 'b/Model']
        for path in paths:
            path.mkdir(parents=True)
        panel = self.app.compression
        panel.add_paths(paths)
        panel.destination_var.set(str(self.directory / 'archives'))
        with patch('compression_gui.messagebox.showerror') as error, patch('compression_gui.compress_folder') as compressor:
            panel.start_button.invoke()
            error.assert_called_once()
            compressor.assert_not_called()
        self.assertFalse(panel.running)
