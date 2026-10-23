from gui_helpers import AppGuiTest


class ImageGuiTest(AppGuiTest):
    def test_example_follows_options_and_language(self):
        panel = self.app.images
        self.assertIn('photo.png → photo.png', panel.example.cget('text'))
        panel.rename_check.invoke()
        self.assertIn('Figurine_1.png', panel.example.cget('text'))
        panel.convert_check.invoke()
        self.assertIn('Format d’origine conservé', panel.example.cget('text'))
        self.app.change_language('en')
        self.assertIn('Figure_1.png', panel.example.cget('text'))
        self.assertIn('Original format preserved', panel.example.cget('text'))

    def test_disable_conversion_copies_original_formats(self):
        panel = self.app.images
        self.assertTrue(panel.convert_var.get())
        (self.directory/'child').mkdir()
        (self.directory/'child/a.avif').write_bytes(b'original avif')
        (self.directory/'child/b.webp').write_bytes(b'original webp')
        panel.convert_check.invoke()
        self.assertFalse(panel.convert_var.get())
        self.app.change_language('en')
        self.assertIn('Convert AVIF and WebP copies', panel.convert_check.cget('text'))
        self.assertFalse(panel.convert_var.get())
        panel.root_var.set(str(self.directory))
        panel.start_button.invoke()
        self.assertEqual(str(panel.convert_check.cget('state')), 'disabled')
        self.pump_until(lambda: not panel.running)
        self.assertEqual((self.directory/'a.avif').read_bytes(), b'original avif')
        self.assertEqual((self.directory/'b.webp').read_bytes(), b'original webp')
        self.assertEqual(panel.message[1]['copied'], 2)
        self.assertEqual(panel.message[1]['converted'], 0)
        self.assertEqual(str(panel.convert_check.cget('state')), 'normal')

    def test_folder_rename_option_and_language_switch(self):
        panel = self.app.images
        self.assertFalse(panel.rename_var.get())
        (self.directory/'Model').mkdir()
        (self.directory/'Model/a.png').write_bytes(b'first')
        (self.directory/'Model/b.png').write_bytes(b'other')
        panel.rename_check.invoke()
        self.assertTrue(panel.rename_var.get())
        self.app.change_language('en')
        self.assertIn('source folder', panel.rename_check.cget('text'))
        self.assertTrue(panel.rename_var.get())
        panel.root_var.set(str(self.directory))
        panel.start_button.invoke()
        self.assertEqual(str(panel.rename_check.cget('state')), 'disabled')
        self.pump_until(lambda: not panel.running)
        self.assertEqual((self.directory/'Model_1.png').read_bytes(), b'first')
        self.assertEqual((self.directory/'Model_2.png').read_bytes(), b'other')
        self.assertEqual(str(panel.rename_check.cget('state')), 'normal')

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
