import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive_tools import seven_zip
from decompresser_tout import JOURNAL, discover, extract_one, process, process_locked


class RecursiveExtractionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.sevenzip = seven_zip()

    def zip(self, relative, members=None):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, 'w') as content:
            for name, data in (members or {'piece.stl': b'keep exact data'}).items():
                content.writestr(name, data)
        return path

    def split(self, kind='7z'):
        source = self.root / 'source.bin'
        source.write_bytes(os.urandom(9000))
        archive = self.root / ('split.' + kind)
        subprocess.run([self.sevenzip, 'a', '-t' + kind, '-v2k', '-mx=0', str(archive), str(source)],
                       check=True, stdout=subprocess.DEVNULL)
        return list(sorted(self.root.glob('split.' + kind + '.*'))), source.read_bytes()

    def test_recursive_and_embedded_archives_are_extracted_and_deleted(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, 'w') as content:
            content.writestr('inner/piece.stl', b'payload')
        first = self.zip('sub/outer.zip', {'inner.zip': inner.getvalue()})
        second = self.zip('other/standalone.zip')
        self.assertEqual(process(self.root, self.sevenzip), 0)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        self.assertEqual((self.root / 'sub/outer/inner/piece.stl').read_bytes(), b'payload')
        self.assertFalse((self.root / 'sub/outer/inner.zip').exists())

    def test_existing_destination_preserves_archive_and_original_content(self):
        archive = self.zip('model.zip')
        output = self.root / 'model'
        output.mkdir()
        (output / 'important.txt').write_text('keep')
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(archive.exists())
        self.assertEqual((output / 'important.txt').read_text(), 'keep')

    def test_keep_archives_recursively_and_skip_them_on_next_run(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, 'w') as content:
            content.writestr('inner/inner/piece.stl', b'payload')
        outer = self.zip('sub/outer.zip', {'outer/outer/inner.zip': inner.getvalue()})
        events = []
        self.assertEqual(process(self.root, self.sevenzip, delete_archives=False,
                                 on_event=lambda kind, **values: events.append((kind, values))), 0)
        self.assertTrue(outer.is_file())
        self.assertTrue((self.root / 'sub/outer/inner.zip').is_file())
        self.assertEqual((self.root / 'sub/outer/inner/piece.stl').read_bytes(), b'payload')
        self.assertFalse((self.root / 'sub/outer/outer').exists())
        self.assertFalse((self.root / 'sub/outer/inner/inner').exists())
        self.assertTrue(any(kind == 'percent' for kind, _ in events))
        self.assertEqual(events[-1][1]['completed'], 2)
        with patch('decompresser_tout.run_sevenzip') as extraction:
            self.assertEqual(process(self.root, self.sevenzip, delete_archives=False), 0)
            extraction.assert_not_called()
        journal = json.loads((self.root / JOURNAL).read_text(encoding='utf-8'))
        self.assertEqual({record['state'] for record in journal.values()}, {'kept'})

    def test_delete_previously_kept_archives_without_extracting_again(self):
        volumes, expected = self.split()
        self.assertEqual(process(self.root, self.sevenzip, delete_archives=False), 0)
        self.assertTrue(all(path.is_file() for path in volumes))
        with patch('decompresser_tout.run_sevenzip') as extraction:
            self.assertEqual(process(self.root, self.sevenzip, delete_archives=True), 0)
            extraction.assert_not_called()
        self.assertTrue(all(not path.exists() for path in volumes))
        self.assertEqual((self.root / 'split/source.bin').read_bytes(), expected)

    def test_changed_kept_archive_is_never_deleted(self):
        archive = self.zip('model.zip')
        self.assertEqual(process(self.root, self.sevenzip, delete_archives=False), 0)
        archive.write_bytes(b'replacement archive')
        self.assertEqual(process(self.root, self.sevenzip, delete_archives=True), 1)
        self.assertEqual(archive.read_bytes(), b'replacement archive')

    def test_keep_mode_does_not_resume_pending_deletion(self):
        archive = self.zip('model.zip')
        with patch('decompresser_tout.delete_sources', side_effect=PermissionError('interrupted')):
            with self.assertRaises(PermissionError):
                extract_one(discover(self.root)[0], self.root, self.sevenzip, {})
        with patch('decompresser_tout.delete_sources') as deletion:
            self.assertEqual(process(self.root, self.sevenzip, delete_archives=False), 0)
            deletion.assert_not_called()
        self.assertTrue(archive.is_file())

    def test_same_name_parent_is_reused_without_double_directory(self):
        for delete_archives in (False, True):
            name = 'Model' + str(delete_archives)
            archive = self.zip(f'{name}/{name}.zip', {f'{name}/{name}/piece.stl': b'payload'})
            self.assertEqual(process(self.root, self.sevenzip, delete_archives=delete_archives), 0)
            self.assertEqual((archive.parent / 'piece.stl').read_bytes(), b'payload')
            self.assertFalse((archive.parent / name).exists())
            self.assertEqual(archive.exists(), not delete_archives)

    def test_root_with_same_name_as_archive_is_reused(self):
        archive = self.zip(self.root.name + '.zip', {f'{self.root.name}/piece.stl': b'payload'})
        self.assertEqual(process(self.root, self.sevenzip), 0)
        self.assertEqual((self.root / 'piece.stl').read_bytes(), b'payload')
        self.assertFalse((self.root / self.root.name).exists())
        self.assertFalse(archive.exists())

    def test_parent_merge_conflict_does_not_move_any_file_or_delete_archive(self):
        archive = self.zip('Model/Model.zip', {'Model/new.stl': b'new', 'Model/keep.stl': b'replacement'})
        existing = archive.parent / 'keep.stl'
        existing.write_bytes(b'original')
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(archive.is_file())
        self.assertEqual(existing.read_bytes(), b'original')
        self.assertFalse((archive.parent / 'new.stl').exists())

    def test_parent_merge_move_failure_rolls_back_all_moves(self):
        archive = self.zip('Model/Model.zip', {'Model/a.stl': b'a', 'Model/b.stl': b'b'})
        original_rename = Path.rename

        def fail_second(path, target):
            if Path(target) == archive.parent / 'b.stl':
                raise PermissionError('simulated publication failure')
            return original_rename(path, target)

        with patch.object(Path, 'rename', fail_second):
            self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(archive.is_file())
        self.assertFalse((archive.parent / 'a.stl').exists())
        self.assertFalse((archive.parent / 'b.stl').exists())
        self.assertEqual((archive.parent / (archive.name + '.extraction-en-cours') / 'Model/a.stl').read_bytes(), b'a')

    def test_stop_finishes_current_archive_and_leaves_the_rest(self):
        first = self.zip('a.zip')
        second = self.zip('b.zip')
        stop = threading.Event()
        events = []

        def event(kind, **values):
            events.append((kind, values))
            if kind == 'percent':
                stop.set()

        self.assertEqual(process(self.root, self.sevenzip, on_event=event, stop_event=stop), 0)
        self.assertFalse(first.exists())
        self.assertTrue(second.is_file())
        self.assertFalse((self.root / 'b').exists())
        self.assertTrue(events[-1][1]['stopped'])

    def test_keep_mode_preserves_crc_damaged_archive_and_continues(self):
        bad = self.zip('bad.zip')
        data = bytearray(bad.read_bytes())
        offset = 30 + int.from_bytes(data[26:28], 'little') + int.from_bytes(data[28:30], 'little')
        data[offset] ^= 1
        bad.write_bytes(data)
        good = self.zip('good.zip')
        self.assertEqual(process(self.root, self.sevenzip, delete_archives=False), 1)
        self.assertTrue(bad.exists())
        self.assertTrue(good.exists())
        self.assertFalse((self.root / 'bad').exists())
        self.assertTrue((self.root / 'good/piece.stl').is_file())

    def test_existing_lock_prevents_a_second_extraction(self):
        import msvcrt
        archive = self.zip('model.zip')
        with (self.root / '.decompression-tout.lock').open('w+b') as lock:
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                with self.assertRaisesRegex(RuntimeError, 'déjà ce dossier'):
                    process_locked(self.root, self.sevenzip)
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        self.assertTrue(archive.is_file())
        self.assertFalse((self.root / JOURNAL).exists())

    def test_corrupted_archive_is_preserved_and_other_archives_continue(self):
        bad = self.root / 'bad.zip'
        bad.write_bytes(b'invalid archive')
        good = self.zip('good.zip')
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(bad.exists())
        self.assertFalse(good.exists())
        self.assertTrue((self.root / 'decompression-erreurs.txt').is_file())

    def test_split_zip_and_7z_delete_all_volumes_only_after_success(self):
        for kind in ['zip', '7z']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=self.root) as temp:
                original = self.root
                self.root = Path(temp)
                try:
                    volumes, expected = self.split(kind)
                    self.assertGreater(len(volumes), 1)
                    self.assertEqual(len(discover(self.root)), 1)
                    self.assertEqual(process(self.root, self.sevenzip), 0)
                    self.assertTrue(all(not path.exists() for path in volumes))
                    self.assertEqual((self.root / 'split/source.bin').read_bytes(), expected)
                finally:
                    self.root = original

    def test_missing_middle_volume_preserves_the_remaining_set(self):
        volumes, _ = self.split()
        volumes[1].unlink()
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(volumes[0].exists())
        self.assertTrue(volumes[-1].exists())

    def test_missing_last_volume_detected_by_7zip_does_not_delete_sources(self):
        volumes, _ = self.split()
        volumes[-1].unlink()
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(all(path.exists() for path in volumes[:-1]))

    def test_unrelated_old_zip_volume_is_not_deleted(self):
        archive = self.zip('model.zip')
        extra = self.root / 'model.z01'
        extra.write_bytes(b'unrelated file')
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(archive.exists())
        self.assertEqual(extra.read_bytes(), b'unrelated file')

    def test_rar_volume_naming_groups_once_and_flags_orphans(self):
        names = ['a.part01.rar', 'a.part02.rar', 'b.rar', 'b.r00', 'b.r01', 'c.part2.rar']
        for name in names:
            (self.root / name).write_bytes(b'fixture')
        groups = discover(self.root)
        self.assertEqual(len(groups), 3)
        by_name = {archive.destination.name: archive for archive in groups}
        self.assertEqual(len(by_name['a'].volumes), 2)
        self.assertEqual(len(by_name['b'].volumes), 3)
        self.assertTrue(by_name['c'].error)

    def test_partial_extraction_folders_are_not_scanned(self):
        self.zip('model.extraction-en-cours/inner.zip')
        self.zip('normal/archive.zip')
        self.assertEqual(len(discover(self.root)), 1)

    def test_cleanup_resumes_even_when_first_volume_was_already_deleted(self):
        volumes, expected = self.split()
        group = discover(self.root)[0]
        journal = {}
        with patch('decompresser_tout.delete_sources', side_effect=PermissionError('simulated interruption')):
            with self.assertRaises(PermissionError):
                extract_one(group, self.root, self.sevenzip, journal)
        volumes[0].unlink()
        self.assertEqual(process(self.root, self.sevenzip), 0)
        self.assertTrue(all(not path.exists() for path in volumes))
        self.assertEqual((self.root / 'split/source.bin').read_bytes(), expected)

    def test_changed_volume_is_not_deleted_after_successful_extraction(self):
        archive = self.zip('model.zip')
        group = discover(self.root)[0]
        journal = {}
        with patch('decompresser_tout.delete_sources', side_effect=PermissionError('interrupted')):
            with self.assertRaises(PermissionError):
                extract_one(group, self.root, self.sevenzip, journal)
        archive.write_bytes(b'new archive data')
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertEqual(archive.read_bytes(), b'new archive data')

    def test_preview_creates_no_journal_and_leaves_archive(self):
        archive = self.zip('model.zip')
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'decompresser_tout.py'),
                                 str(self.root), '--apercu'], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(archive.exists())
        self.assertFalse((self.root / JOURNAL).exists())

    def test_crc_error_during_extraction_preserves_archive(self):
        archive = self.zip('damaged.zip')
        data = bytearray(archive.read_bytes())
        offset = 30 + int.from_bytes(data[26:28], 'little') + int.from_bytes(data[28:30], 'little')
        data[offset] ^= 1
        archive.write_bytes(data)
        self.assertEqual(process(self.root, self.sevenzip), 1)
        self.assertTrue(archive.exists())
        self.assertFalse((self.root / 'damaged').exists())

    def test_password_archive_fails_without_waiting_for_hidden_input(self):
        source = self.root / 'secret.txt'
        source.write_text('test fixture, not a real secret')
        archive = self.root / 'encrypted.zip'
        subprocess.run([self.sevenzip, 'a', '-tzip', '-pfixture', str(archive), str(source)],
                       check=True, stdout=subprocess.DEVNULL)
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'decompresser_tout.py'),
                                 str(self.root), '--appliquer'], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(archive.exists())
        self.assertFalse((self.root / 'encrypted').exists())


if __name__ == '__main__':
    unittest.main()
