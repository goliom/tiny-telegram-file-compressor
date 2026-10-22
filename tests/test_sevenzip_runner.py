import io
import subprocess
import sys
import unittest
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sevenzip_runner import run_sevenzip


class ProgressTest(unittest.TestCase):
    @patch('sevenzip_runner.subprocess.Popen')
    def test_progress_and_long_running_heartbeat(self, popen):
        process = popen.return_value
        process.wait.side_effect = [subprocess.TimeoutExpired('7z', 15), 0]
        output = io.StringIO()
        with redirect_stdout(output):
            run_sevenzip(['7z', 't', 'archive.zip'], 'Vérification')
        self.assertIn('-bsp1', popen.call_args.args[0])
        self.assertNotIn('stdout', popen.call_args.kwargs)
        self.assertEqual(popen.call_args.kwargs['stdin'], subprocess.DEVNULL)
        self.assertIn('toujours actif', output.getvalue())
        self.assertIn('terminé en', output.getvalue())

    @patch('sevenzip_runner.subprocess.Popen')
    def test_failures_propagate_for_archive_preservation(self, popen):
        popen.return_value.wait.return_value = 2
        with redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            run_sevenzip(['7z', 't', 'archive.zip'], 'Vérification')

    @patch('sevenzip_runner.subprocess.Popen')
    def test_keyboard_interrupt_stops_child_process(self, popen):
        process = popen.return_value
        process.wait.side_effect = [KeyboardInterrupt(), 0]
        process.poll.return_value = None
        with redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            run_sevenzip(['7z', 'x', 'archive.zip'], 'Extraction')
        process.terminate.assert_called_once()

    def test_streams_percentages_split_across_output_chunks(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            script = Path(temp) / 'progress_fixture.py'
            script.write_text("""import sys,time
for chunk in [b'  0%', b' file\\n\\b\\b 3', b'7% file\\n', b'\\b\\b 82% file\\n']:
    sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()
    time.sleep(0.05)
""", encoding='utf-8')
            values = []
            with redirect_stdout(io.StringIO()):
                run_sevenzip([sys.executable, str(script)], 'Progression', on_progress=values.append)
            self.assertEqual(values, [0, 37, 82, 100])

    def test_failed_process_does_not_report_completion(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            script = Path(temp) / 'failed_fixture.py'
            script.write_text("import sys\nsys.stdout.buffer.write(b' 37% file\\n');sys.stdout.flush();sys.exit(2)\n", encoding='utf-8')
            values = []
            with redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
                run_sevenzip([sys.executable, str(script)], 'Progression', on_progress=values.append)
            self.assertEqual(values, [37])


if __name__ == '__main__':
    unittest.main()
