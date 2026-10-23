import tempfile
import threading
import unittest
from pathlib import Path
from PIL import Image
from image_collect import collect_images


class ImageCollectionTest(unittest.TestCase):
    def test_webp_conversion_conflicts_transparency_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'sub/deep').mkdir(parents=True)
            source = root/'sub/deep/render.WEBP'
            Image.new('RGBA', (10, 12), (0, 0, 0, 0)).save(source, format='WEBP', lossless=True)
            original = source.read_bytes()
            (root/'render.jpg').write_bytes(b'existing image')
            events = []
            collect_images(root, threading.Event(), lambda kind, **v: events.append((kind, v)))
            self.assertEqual(events[-1][1]['converted'], 1)
            self.assertEqual(events[-1][1]['errors'], 0)
            self.assertEqual((root/'render.jpg').read_bytes(), b'existing image')
            with Image.open(root/'render_1.jpg') as result:
                self.assertEqual(result.format, 'JPEG')
                self.assertEqual(result.size, (10, 12))
                self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((root/'render.WEBP').exists())
            collect_images(root, threading.Event(), lambda kind, **v: events.append((kind, v)))
            self.assertEqual(events[-1][1]['skipped'], 1)
            self.assertFalse((root/'render_2.jpg').exists())
            self.assertFalse(list(root.glob('.image-copy-*')))

    def test_recursive_conflicts_conversion_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'a/deep').mkdir(parents=True)
            (root/'b').mkdir()
            (root/'photo.png').write_bytes(b'original')
            (root/'a/photo.png').write_bytes(b'new')
            (root/'b/photo.png').write_bytes(b'new')
            (root/'a/deep/other.jpg').write_bytes(b'copy')
            original = root/'b/render.avif'
            Image.new('RGBA', (10, 12), (255,0,0,128)).save(original)
            before = original.read_bytes()
            events = []
            collect_images(root, threading.Event(), lambda kind, **v: events.append((kind,v)))
            self.assertEqual((root/'photo.png').read_bytes(), b'original')
            self.assertEqual((root/'photo_1.png').read_bytes(), b'new')
            self.assertFalse((root/'photo_2.png').exists())
            self.assertEqual((root/'other.jpg').read_bytes(), b'copy')
            with Image.open(root/'render.jpg') as result:
                self.assertEqual(result.format, 'JPEG')
                self.assertEqual(result.size, (10,12))
            self.assertEqual(original.read_bytes(), before)
            count = len(list(root.iterdir()))
            collect_images(root, threading.Event(), lambda *a, **k: None)
            self.assertEqual(len(list(root.iterdir())), count)
            self.assertFalse(list(root.glob('.image-copy-*')))

    def test_conversion_error_preserves_existing_and_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'sub').mkdir()
            (root/'sub/bad.avif').write_bytes(b'not avif')
            (root/'sub/good.png').write_bytes(b'preserve')
            events=[]
            collect_images(root, threading.Event(), lambda k, **v: events.append((k,v)))
            self.assertEqual(events[-1][1]['errors'], 1)
            self.assertEqual((root/'good.png').read_bytes(), b'preserve')
            self.assertFalse((root/'bad.jpg').exists())
            self.assertFalse(list(root.glob('.image-copy-*')))

    def test_stop_does_not_create_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'sub').mkdir()
            (root/'sub/a.png').write_bytes(b'a')
            stop=threading.Event()
            stop.set()
            collect_images(root, stop, lambda *a, **k: None)
            self.assertFalse((root/'a.png').exists())
