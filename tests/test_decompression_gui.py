import threading
import zipfile
from unittest.mock import patch

from gui_helpers import AppGuiTest


class ExtractionGuiTest(AppGuiTest):
    def test_policy_warning_follows_selection_and_language(self):
        panel = self.app.extraction
        self.assertIn('seront supprimées', panel.policy_notice.cget('text'))
        panel.keep_radio.invoke()
        self.assertIn('seront conservées', panel.policy_notice.cget('text'))
        self.app.change_language('en')
        self.assertEqual(panel.policy_notice.cget('text'), 'Source archives will be kept.')
        panel.delete_radio.invoke()
        self.assertIn('will be deleted', panel.policy_notice.cget('text'))

    def test_keep_then_delete_with_real_archives_and_same_name_folders(self):
        panel = self.app.extraction
        paths = [self.directory / 'Model/Model.zip', self.directory / 'other/Image.zip']
        for path in paths:
            path.parent.mkdir(parents=True)
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(f'{path.stem}/{path.stem}/piece.stl', b'exact payload')
        self.app.change_language('es')
        self.app.notebook.select(panel)
        self.assertEqual(panel.policy_var.get(), 'delete')
        panel.keep_radio.invoke()
        self.assertEqual(panel.policy_var.get(), 'keep')
        with patch('decompression_gui.filedialog.askdirectory', return_value=str(self.directory)):
            panel.browse.invoke()
        panel.start_button.invoke()
        self.pump_until(lambda: not panel.running)
        self.assertTrue(all(path.is_file() for path in paths))
        self.assertEqual((self.directory / 'Model/piece.stl').read_bytes(), b'exact payload')
        self.assertFalse((self.directory / 'Model/Model').exists())
        self.assertFalse((self.directory / 'other/Image/Image').exists())
        self.assertTrue(panel.monitor.status_var.get().startswith('Finalizado: 2 archivo(s)'))
        self.assertEqual(float(panel.monitor.total_bar.cget('value')), 100)
        self.assertEqual(str(panel.open_button.cget('state')), 'normal')
        self.app.change_language('it')
        self.assertIn('archivi conservati', panel.monitor.log.get('1.0', 'end'))
        panel.delete_radio.invoke()
        self.assertEqual(panel.policy_var.get(), 'delete')
        with patch('decompresser_tout.run_sevenzip') as extraction:
            panel.start_button.invoke()
            self.pump_until(lambda: not panel.running)
            extraction.assert_not_called()
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertIn('archivi eliminati', panel.monitor.log.get('1.0', 'end'))

    def test_progress_languages_and_application_close_wait_for_archive(self):
        panel = self.app.extraction
        panel.root_var.set(str(self.directory))
        release = threading.Event()
        self.releases.append(release)
        observed = {}
        now = [0.0]
        panel.monitor.estimate.clock = lambda: now[0]

        def worker(root, executable, delete_archives, stop_event, on_event):
            observed.update(delete=delete_archives, stop=stop_event)
            on_event('weights', weights={'model.zip': 100, 'later.zip': 300})
            on_event('current', name='model.zip', index=1, total=2)
            on_event('percent', percent=25)
            if not release.wait(5):
                raise RuntimeError('UI did not display progress')
            on_event('archive_done', name='model.zip', status='kept', completed=1, total=2)
            on_event('finished', completed=1, reused=0, errors=0, stopped=stop_event.is_set())

        with patch('decompression_gui.process_locked', side_effect=worker), \
             patch('decompression_gui.seven_zip', return_value='fake-7z'):
            panel.start_button.invoke()
            self.pump_until(lambda: float(panel.monitor.current_bar.cget('value')) == 25)
            self.assertTrue(observed['delete'])
            self.assertAlmostEqual(float(panel.monitor.total_bar.cget('value')), 6.25)
            self.assertEqual(str(panel.delete_radio.cget('state')), 'disabled')
            now[0] = 10
            for code in ('fr', 'en', 'es', 'it'):
                self.app.change_language(code)
                self.assertIn('2 min 30 s', panel.monitor.eta_var.get())
                self.assertEqual(panel.root_var.get(), str(self.directory))
                self.assertEqual(panel.policy_var.get(), 'delete')
            self.app.request_close()
            self.assertTrue(observed['stop'].is_set())
            self.assertFalse(self.app.destroyed)
            release.set()
            self.pump_until(lambda: self.app.destroyed)

    def test_empty_root_stops_scanning_indicator(self):
        panel = self.app.extraction
        panel.root_var.set(str(self.directory))
        panel.start_button.invoke()
        self.pump_until(lambda: not panel.running)
        self.assertEqual(str(panel.monitor.current_bar.cget('mode')), 'determinate')
        self.assertTrue(panel.monitor.status_var.get().startswith('Terminé : 0 archive(s)'))

    def test_fatal_error_keeps_summary_visible_and_controls_available(self):
        panel = self.app.extraction
        panel.root_var.set(str(self.directory))
        with patch('decompression_gui.process_locked', side_effect=RuntimeError('locked fixture')):
            panel.start_button.invoke()
            self.pump_until(lambda: not panel.running)
        self.assertIn('locked fixture', panel.monitor.status_var.get())
        self.assertEqual(str(panel.start_button.cget('state')), 'normal')
