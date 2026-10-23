import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive_tools import seven_zip
from compresser_dossiers import VOLUME_BYTES, compress_folder
from sevenzip_runner import run_sevenzip


class CompressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / 'archives'
        self.executable = seven_zip()

    def source(self, name='Collection - 2026-05', size=9000):
        folder = self.root / name
        folder.mkdir()
        (folder / 'sub').mkdir()
        (folder / 'sub/piece.bin').write_bytes(os.urandom(size))
        return folder

    def test_exact_telegram_2000_mib_limit(self):
        self.assertEqual(VOLUME_BYTES, 2_097_152_000)

    def test_four_selected_folders_produce_four_independent_split_archives(self):
        sources = [self.source(f'Collection - 2026-0{month}') for month in range(5, 10)]
        for source in sources[:4]:
            original = (source / 'sub/piece.bin').read_bytes()
            volumes = compress_folder(source, self.output, self.executable, volume_bytes=2048)
            self.assertGreater(len(volumes), 1)
            self.assertTrue(all(0 < path.stat().st_size <= 2048 for path in volumes))
            self.assertTrue(all(path.name.startswith(source.name + '.7z.') for path in volumes))
            restored = self.root / ('restored-' + source.name)
            subprocess.run([self.executable, 'x', '-y', '-bso0', f'-o{restored}', str(volumes[0])],
                           check=True, stdout=subprocess.DEVNULL)
            self.assertEqual((restored / source.name / 'sub/piece.bin').read_bytes(), original)
            self.assertEqual((source / 'sub/piece.bin').read_bytes(), original)
        self.assertFalse(any(self.output.glob(sources[4].name + '.7z*')))

    def test_small_folder_produces_readable_unnumbered_archive(self):
        source = self.source(size=16)
        values = []
        with patch('compresser_dossiers.run_sevenzip', wraps=run_sevenzip) as runner:
            volumes = compress_folder(source, self.output, self.executable, on_progress=values.append)
        self.assertIn('-mx=5', runner.call_args.args[0])
        self.assertIn('-v2097152000b', runner.call_args.args[0])
        self.assertEqual([path.name for path in volumes], [source.name + '.7z'])
        restored = self.root / 'restored-single'
        subprocess.run([self.executable, 'x', '-y', '-bso0', f'-o{restored}', str(volumes[0])],
                       check=True, stdout=subprocess.DEVNULL)
        self.assertEqual((restored / source.name / 'sub/piece.bin').read_bytes(),
                         (source / 'sub/piece.bin').read_bytes())
        self.assertTrue(source.is_dir())
        self.assertTrue(values)
        self.assertEqual(values[-1], 100)

    def test_existing_archive_is_not_updated_or_overwritten(self):
        source = self.source()
        self.output.mkdir()
        existing = self.output / (source.name + '.7z.001')
        existing.write_bytes(b'keep existing archive')
        with self.assertRaises(FileExistsError):
            compress_folder(source, self.output, self.executable)
        self.assertEqual(existing.read_bytes(), b'keep existing archive')
        self.assertFalse((self.output / (source.name + '.compression-en-cours')).exists())

    def test_existing_unnumbered_archive_is_preserved(self):
        source = self.source(size=16)
        self.output.mkdir()
        existing = self.output / (source.name + '.7z')
        existing.write_bytes(b'keep unnumbered archive')
        with self.assertRaises(FileExistsError):
            compress_folder(source, self.output, self.executable)
        self.assertEqual(existing.read_bytes(), b'keep unnumbered archive')
        self.assertFalse((self.output / (source.name + '.compression-en-cours')).exists())

    def test_single_volume_at_exact_limit_keeps_numbered_name(self):
        source = self.source(size=16)
        def exact_limit(arguments, label, **kwargs):
            archive = next(Path(arg) for arg in arguments if arg.endswith('.7z'))
            Path(str(archive) + '.001').write_bytes(b'x' * 2048)
        with patch('compresser_dossiers.run_sevenzip', side_effect=exact_limit):
            volumes = compress_folder(source, self.output, self.executable, volume_bytes=2048)
        self.assertEqual([path.name for path in volumes], [source.name + '.7z.001'])

    def test_single_archive_publication_failure_restores_numbered_staging_file(self):
        source = self.source(size=16)
        staging = self.output / (source.name + '.compression-en-cours')
        original_rmdir = Path.rmdir
        def interrupted_rmdir(path):
            if path == staging:
                raise PermissionError('simulated finalization interruption')
            return original_rmdir(path)
        with patch.object(Path, 'rmdir', interrupted_rmdir):
            with self.assertRaises(PermissionError):
                compress_folder(source, self.output, self.executable)
        self.assertTrue((staging / (source.name + '.7z.001')).is_file())
        self.assertFalse((self.output / (source.name + '.7z')).exists())
        self.assertTrue((source / 'sub/piece.bin').is_file())

    def test_destination_inside_source_is_refused_before_creating_it(self):
        source = self.source()
        with self.assertRaises(ValueError):
            compress_folder(source, source / 'archives', self.executable)
        self.assertFalse((source / 'archives').exists())

    def test_failed_compression_retains_staging_and_sources(self):
        source = self.source()
        def fail(arguments, label, **kwargs):
            archive = next(Path(arg) for arg in arguments if arg.endswith('.7z'))
            Path(str(archive) + '.001').write_bytes(b'incomplete volume')
            raise subprocess.CalledProcessError(2, arguments)
        with patch('compresser_dossiers.run_sevenzip', side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                compress_folder(source, self.output, self.executable)
        self.assertTrue((source / 'sub/piece.bin').is_file())
        self.assertTrue((self.output / (source.name + '.compression-en-cours')).is_dir())
        self.assertFalse(any(self.output.glob('*.7z.001')))

    def test_unexpected_volume_size_is_not_published(self):
        source = self.source()
        def too_large(arguments, label, **kwargs):
            archive = next(Path(arg) for arg in arguments if arg.endswith('.7z'))
            Path(str(archive) + '.001').write_bytes(b'x' * 2049)
        with patch('compresser_dossiers.run_sevenzip', side_effect=too_large):
            with self.assertRaisesRegex(RuntimeError, 'Taille de volume'):
                compress_folder(source, self.output, self.executable, volume_bytes=2048)
        self.assertFalse(any(self.output.glob('*.7z.001')))

    def test_publication_failure_restores_all_volumes_to_staging(self):
        source = self.source()
        staging = self.output / (source.name + '.compression-en-cours')
        original_rename = Path.rename
        calls = 0
        def interrupted_rename(path, target):
            nonlocal calls
            if path.parent == staging and Path(target).parent == self.output:
                calls += 1
                if calls == 2:
                    raise PermissionError('simulated publication interruption')
            return original_rename(path, target)
        with patch.object(Path, 'rename', interrupted_rename):
            with self.assertRaises(PermissionError):
                compress_folder(source, self.output, self.executable, volume_bytes=2048)
        self.assertGreater(len(list(staging.glob('*.7z.*'))), 1)
        self.assertFalse(any(self.output.glob('*.7z.*')))
        self.assertTrue((source / 'sub/piece.bin').is_file())


if __name__ == '__main__':
    unittest.main()
