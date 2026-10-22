"""Exercise the actual GUI and 7-Zip in a compiled Windows build."""
import gc
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

from app_identity import APP_VERSION, ASSETS
from compression_i18n import LANGUAGES
from desktop_app import DesktopApp


def run(report_path):
    report = Path(report_path).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    results = {'version': APP_VERSION, 'frozen': bool(getattr(sys, 'frozen', False)), 'success': False}
    temporary = tempfile.TemporaryDirectory(prefix='ttfc-smoke-', dir=report.parent)
    root = Path(temporary.name)
    source = root / 'Model'
    (source / 'nested').mkdir(parents=True)
    payload = bytes(range(256)) * 4096
    (source / 'nested/piece.bin').write_bytes(payload)
    output = root / 'archives'
    app = DesktopApp()
    app.root.withdraw()
    deadline = time.monotonic() + 90

    def finish():
        app.destroy()

    def fail(error):
        results.update(error=str(error), traceback=traceback.format_exc())
        if any(panel.running for panel in app.panels):
            for panel in app.panels:
                panel.request_stop()
            app.root.after(50, finish_when_idle)
        else:
            finish()

    def finish_when_idle():
        if any(panel.running for panel in app.panels):
            app.root.after(50, finish_when_idle)
        else:
            finish()

    def guarded(function):
        try:
            function()
        except Exception as error:
            fail(error)

    def wait_for(panel, function):
        def poll():
            if time.monotonic() > deadline:
                raise TimeoutError('Frozen application smoke test timed out')
            if panel.running:
                app.root.after(50, lambda: guarded(poll))
            else:
                function()
        app.root.after(50, lambda: guarded(poll))

    def start():
        assert app.root._tiny_app_icon.width() > 0, 'Bundled icon missing'
        if getattr(sys, 'frozen', False):
            for name in ('Application-MIT.txt', 'Python-LICENSE.txt', 'Tcl-license.terms', 'Tk-license.terms', 'PyInstaller-COPYING.txt'):
                assert (ASSETS.parent / 'licenses' / name).is_file(), 'Bundled license missing: ' + name
            results['runtime_licenses'] = 'included'
        assert len(app.notebook.tabs()) == 2
        for language in LANGUAGES:
            app.change_language(language)
        results.update(icon_loaded=True, languages=list(LANGUAGES))
        app.compression.add_paths([source])
        app.compression.destination_var.set(str(output))
        app.compression.start()
        assert app.compression.running, 'Compression did not start'
        wait_for(app.compression, compressed)

    def compressed():
        assert app.compression.monitor.status_message[0] == 'done'
        assert app.compression.monitor.status_message[1]['success'] == 1
        assert (output / 'Model.7z.001').is_file()
        results['compression'] = 'passed'
        app.extraction.root_var.set(str(output))
        assert app.extraction.policy_var.get() == 'keep'
        app.extraction.start()
        assert app.extraction.running, 'Extraction did not start'
        wait_for(app.extraction, extracted)

    def extracted():
        assert app.extraction.monitor.status_message[0] == 'extract_done'
        assert app.extraction.monitor.status_message[1]['errors'] == 0
        assert (output / 'Model/nested/piece.bin').read_bytes() == payload
        assert not (output / 'Model/Model').exists()
        assert (output / 'Model.7z.001').is_file()
        results['extract_keep'] = 'passed'
        app.extraction.policy_var.set('delete')
        app.extraction.start()
        wait_for(app.extraction, deleted)

    def deleted():
        assert app.extraction.monitor.status_message[1]['errors'] == 0
        assert not (output / 'Model.7z.001').exists()
        assert (output / 'Model/nested/piece.bin').read_bytes() == payload
        assert (source / 'nested/piece.bin').read_bytes() == payload
        results.update(extract_delete='passed', source_preserved=True, success=True)
        finish()

    try:
        app.root.after(50, lambda: guarded(start))
        app.root.mainloop()
    finally:
        if not app.destroyed:
            app.destroy()
        app = None
        gc.collect()
        temporary.cleanup()
        report.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    return 0 if results['success'] else 1
