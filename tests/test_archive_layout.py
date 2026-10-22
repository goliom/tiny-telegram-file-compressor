import sys
import tempfile
import subprocess
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive_layout import flatten_existing
from archive_tools import seven_zip
from decompresser_tout import discover, extract_one


def extract_archive(archive, destination, executable):
    group = next(item for item in discover(archive.parent) if item.first == archive)
    extract_one(group, archive.parent, executable, {})


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def extract(self, members):
        archive = self.root / 'Modele.zip'
        with zipfile.ZipFile(archive, 'w') as content:
            for name in members:
                content.writestr(name, name)
        destination = archive.with_suffix('')
        extract_archive(archive, destination, seven_zip())
        self.assertFalse(archive.exists())
        return destination

    def test_single_matching_folder_is_not_duplicated(self):
        result = self.extract(['Modele/Base/piece.stl', 'Modele/Standard/piece.stl'])
        self.assertTrue((result / 'Base/piece.stl').is_file())
        self.assertFalse((result / 'Modele').exists())

    def test_multiple_identical_wrappers_are_removed(self):
        result = self.extract(['Modele/Modele/Base/piece.stl'])
        self.assertTrue((result / 'Base/piece.stl').is_file())

    def test_different_named_folder_is_preserved(self):
        result = self.extract(['Versions/Base/piece.stl'])
        self.assertTrue((result / 'Versions/Base/piece.stl').is_file())

    def test_wrapper_with_sibling_file_is_preserved(self):
        result = self.extract(['Modele/Base/piece.stl', 'notice.txt'])
        self.assertTrue((result / 'Modele/Base/piece.stl').is_file())
        self.assertTrue((result / 'notice.txt').is_file())

    def test_existing_duplicates_repaired_without_changing_output_folder(self):
        output = self.root / 'collection/figure/Modele'
        piece = output / 'Modele/Modele/Base/piece.stl'
        piece.parent.mkdir(parents=True)
        piece.write_bytes(b'keep this exact content')
        self.assertTrue(flatten_existing(output, self.root))
        self.assertEqual((output / 'Base/piece.stl').read_bytes(), b'keep this exact content')
        self.assertFalse(flatten_existing(output, self.root))
        self.assertFalse(any(output.parent.glob('*.doublon-en-cours-*')))

    def test_existing_content_with_siblings_is_unchanged(self):
        folder = self.root / 'Modele'
        (folder / 'Modele').mkdir(parents=True)
        (folder / 'notice.txt').write_text('keep')
        self.assertFalse(flatten_existing(folder, self.root))
        self.assertTrue((folder / 'Modele').is_dir())

    def test_boundary_is_checked_before_any_move(self):
        folder = self.root / 'Modele'
        (folder / 'Modele').mkdir(parents=True)
        with self.assertRaises(ValueError):
            flatten_existing(folder, self.root / 'other')
        self.assertTrue((folder / 'Modele').is_dir())

    def test_extraction_detects_crc_damage_without_preliminary_test(self):
        archive = self.root / 'Damaged.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as content:
            content.writestr('piece.stl', b'original bytes with a known CRC')
        data = bytearray(archive.read_bytes())
        # Change the payload while retaining the original CRC in both ZIP headers.
        offset = 30 + int.from_bytes(data[26:28], 'little') + int.from_bytes(data[28:30], 'little')
        data[offset] ^= 1
        archive.write_bytes(data)
        with self.assertRaises(subprocess.CalledProcessError):
            extract_archive(archive, archive.with_suffix(''), seven_zip())
        self.assertTrue(archive.exists())
        self.assertFalse(archive.with_suffix('').exists())


if __name__ == '__main__':
    unittest.main()
