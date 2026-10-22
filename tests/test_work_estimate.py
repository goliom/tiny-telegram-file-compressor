import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from work_estimate import WorkEstimate, duration, folder_weight


class EstimateTest(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.estimate = WorkEstimate(clock=lambda: self.now)

    def test_total_eta_uses_bytes_instead_of_folder_count(self):
        self.estimate.add({'small': 100, 'large': 900})
        self.estimate.start('small')
        self.estimate.update(50)
        self.now = 10
        self.assertAlmostEqual(self.estimate.seconds_left(), 190)
        self.assertAlmostEqual(self.estimate.progress_fraction(), 0.05)
        self.assertAlmostEqual(self.estimate.seconds_left(stop_after_current=True), 10)
        self.estimate.finish('small')
        self.estimate.start('large')
        self.now = 20
        self.estimate.update(50)
        self.assertAlmostEqual(self.estimate.seconds_left(), 450 * 20 / 550)

    def test_nested_archives_extend_the_remaining_work(self):
        self.estimate.add({'outer': 100})
        self.estimate.start('outer')
        self.now = 10
        self.estimate.finish('outer')
        self.assertEqual(self.estimate.message(True)[0], 'eta_finalizing')
        self.estimate.add({'inner': 300})
        self.estimate.start('inner')
        self.assertAlmostEqual(self.estimate.seconds_left(), 30)

    def test_no_estimate_before_progress_or_for_unknown_pending_size(self):
        self.estimate.add({'known': 100, 'unknown': None})
        self.estimate.start('known')
        self.now = 10
        self.assertIsNone(self.estimate.seconds_left())
        self.estimate.update(50)
        self.assertIsNone(self.estimate.seconds_left())
        self.assertEqual(self.estimate.message(True)[0], 'eta_calculating')
        self.assertAlmostEqual(self.estimate.seconds_left(stop_after_current=True), 10)
        self.estimate.finish('unknown', succeeded=False)
        self.assertAlmostEqual(self.estimate.seconds_left(), 10)

    def test_failed_and_cleanup_tasks_do_not_count_as_measured_throughput(self):
        self.estimate.add({'cleanup': 0, 'failed': 1000, 'next': 100})
        self.estimate.start('cleanup')
        self.estimate.finish('cleanup')
        self.estimate.start('failed')
        self.estimate.update(90)
        self.estimate.finish('failed', succeeded=False)
        self.estimate.start('next')
        self.now = 10
        self.assertIsNone(self.estimate.seconds_left())
        self.estimate.update(50)
        self.assertAlmostEqual(self.estimate.seconds_left(), 10)

    def test_completion_finalization_and_reset_are_distinct(self):
        self.assertEqual(self.estimate.message(False)[0], 'eta_idle')
        self.estimate.start('file')
        self.estimate.add({'file': 100})
        self.estimate.update(100)
        self.assertEqual(self.estimate.message(True)[0], 'eta_finalizing')
        self.assertEqual(self.estimate.message(False, has_finished=True), ('eta_remaining', {'duration': '0 s'}))
        self.estimate.reset()
        self.assertIsNone(self.estimate.seconds_left())

    def test_folder_sizes_include_nested_files_using_metadata(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            root = Path(temporary)
            (root / 'nested').mkdir()
            (root / 'a.bin').write_bytes(b'a' * 100)
            (root / 'nested/b.bin').write_bytes(b'b' * 900)
            self.assertEqual(folder_weight(root), 1000)

    def test_duration_format(self):
        self.assertEqual(duration(0.2), '1 s')
        self.assertEqual(duration(61), '1 min 01 s')
        self.assertEqual(duration(3661), '1 h 01 min 01 s')


if __name__ == '__main__':
    unittest.main()
