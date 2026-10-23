from gui_helpers import AppGuiTest


class ImageGuiTest(AppGuiTest):
    def test_collection_and_language_switch(self):
        panel=self.app.images
        (self.directory/'child').mkdir()
        (self.directory/'child/a.png').write_bytes(b'image')
        panel.root_var.set(str(self.directory))
        panel.start_button.invoke()
        self.assertEqual(str(self.app.compression.start_button.cget('state')), 'disabled')
        self.pump_until(lambda: not panel.running)
        self.assertEqual((self.directory/'a.png').read_bytes(), b'image')
        self.assertEqual(panel.message[0], 'images_done')
        self.assertEqual(panel.message[1]['copied'], 1)
        self.app.change_language('nl')
        self.assertIn('Voltooid', panel.status.cget('text'))
