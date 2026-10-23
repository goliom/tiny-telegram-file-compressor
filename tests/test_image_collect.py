import tempfile
import threading
import unittest
from pathlib import Path
from PIL import Image
from image_collect import collect_images


class ImageCollectionTest(unittest.TestCase):
    def test_conversion_disabled_preserves_bytes_extensions_and_repeat(self):
        for rename in (False, True):
            with self.subTest(rename=rename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'Model').mkdir()
                originals = {'a.avif': b'raw avif bytes', 'b.WEBP': b'raw webp bytes'}
                for name, content in originals.items():
                    (root/'Model'/name).write_bytes(content)
                events = []
                collect_images(root, threading.Event(), lambda k, **v: events.append((k, v)),
                               rename_by_folder=rename, convert_to_jpg=False)
                for index, (name, content) in enumerate(originals.items(), 1):
                    target = f'Model_{index}{Path(name).suffix}' if rename else name
                    self.assertEqual((root/target).read_bytes(), content)
                    self.assertEqual((root/'Model'/name).read_bytes(), content)
                self.assertEqual(events[-1][1]['copied'], 2)
                self.assertEqual(events[-1][1]['converted'], 0)
                self.assertEqual(events[-1][1]['errors'], 0)
                self.assertFalse(list(root.glob('*.jpg')))
                collect_images(root, threading.Event(), lambda k, **v: events.append((k, v)),
                               rename_by_folder=rename, convert_to_jpg=False)
                self.assertEqual(events[-1][1]['skipped'], 2)

    def test_folder_names_numbering_conflicts_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root/'Figurine'
            second = root/'nested/Figurine'
            first.mkdir()
            second.mkdir(parents=True)
            (first/'a.PNG').write_bytes(b'first')
            (first/'b.PNG').write_bytes(b'other')  # Same size, still a distinct numbered image.
            Image.new('RGB', (8, 8), 'red').save(first/'c.webp')
            (second/'a.gif').write_bytes(b'last')
            (root/'Figurine_1.PNG').write_bytes(b'existing different-size image')
            events = []
            collect_images(root, threading.Event(), lambda k, **v: events.append((k, v)),
                           rename_by_folder=True)
            self.assertEqual((root/'Figurine_1.PNG').read_bytes(), b'existing different-size image')
            self.assertEqual((root/'Figurine_2.PNG').read_bytes(), b'first')
            self.assertEqual((root/'Figurine_3.PNG').read_bytes(), b'other')
            with Image.open(root/'Figurine_4.jpg') as result:
                self.assertEqual(result.format, 'JPEG')
            self.assertEqual((root/'Figurine_5.gif').read_bytes(), b'last')
            self.assertTrue((first/'c.webp').is_file())
            self.assertEqual(events[-1][1]['copied'], 3)
            self.assertEqual(events[-1][1]['converted'], 1)
            before = sorted(p.name for p in root.iterdir())
            collect_images(root, threading.Event(), lambda k, **v: events.append((k, v)),
                           rename_by_folder=True)
            self.assertEqual(events[-1][1]['skipped'], 4)
            self.assertEqual(sorted(p.name for p in root.iterdir()), before)

    def test_folder_numbering_uses_immediate_parent_and_starts_at_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('Model/Previews', 'Other'):
                (root/folder).mkdir(parents=True)
                (root/folder/'original.jpeg').write_bytes(b'image')
            collect_images(root, threading.Event(), lambda *a, **k: None, rename_by_folder=True)
            self.assertEqual((root/'Previews_1.jpeg').read_bytes(), b'image')
            self.assertEqual((root/'Other_1.jpeg').read_bytes(), b'image')
            self.assertFalse((root/'Model_1.jpeg').exists())

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
