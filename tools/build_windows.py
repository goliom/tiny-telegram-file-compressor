"""Build and verify the versioned Windows x64 release assets."""
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_identity import APP_VERSION


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    paths = sorted(set(name for name in raw.decode('utf-8').split('\0') if name))
    for name in paths:
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError('Unexpected source file: ' + name)
    return paths


def write_zip(path, files, prefix):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, source in sorted(files.items()):
            archive.write(source, prefix + '/' + relative)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Release ZIP integrity check failed')


def runtime_licenses(target):
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', target / 'Python-LICENSE.txt')
    distribution = importlib.metadata.distribution('PyInstaller')
    copying = next(path for path in distribution.files if str(path).endswith('licenses/COPYING.txt'))
    shutil.copy2(distribution.locate_file(copying), target / 'PyInstaller-COPYING.txt')
    # Tk 9 can store its library and license inside a DLL's zip filesystem.
    import tkinter
    window = tkinter.Tk()
    window.withdraw()
    try:
        for name, command in [('Tcl', 'info library'), ('Tk', 'set tk_library')]:
            library = window.tk.eval(command)
            handle = window.tk.call('open', library + '/license.terms', 'r')
            try:
                content = window.tk.call('read', handle)
            finally:
                window.tk.call('close', handle)
            (target / (name + '-license.terms')).write_text(str(content), encoding='utf-8')
    finally:
        window.destroy()


def main():
    if os.name != 'nt' or struct.calcsize('P') != 8 or platform.machine().lower() not in {'amd64', 'x86_64'}:
        raise SystemExit('Build this release on Windows x64 with 64-bit Python.')
    build = ROOT / 'build/windows'
    destination = ROOT / 'dist' / ('v' + APP_VERSION)
    build.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'], cwd=ROOT, check=True)
    licenses = build / 'licenses'
    runtime_licenses(licenses)
    shutil.copy2(ROOT / 'LICENSE', licenses / 'Application-MIT.txt')
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', licenses / 'THIRD_PARTY_NOTICES.md')
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed', '--noupx',
        '--name', 'TinyTelegramFileCompressor', '--icon', str(ROOT / 'assets/tiny-telegram-file-compressor.ico'),
        '--add-data', str(ROOT / 'assets/tiny-telegram-file-compressor.png') + ':assets',
        '--add-data', str(ROOT / 'assets/tiny-telegram-file-compressor.ico') + ':assets',
        '--add-data', str(licenses) + ':licenses',
        '--version-file', str(ROOT / 'packaging/windows-version.txt'),
        '--distpath', str(build / 'dist'), '--workpath', str(build / 'work'),
        '--specpath', str(build / 'spec'), str(ROOT / 'tiny_telegram.py')
    ], cwd=ROOT, check=True)
    executable = build / 'dist/TinyTelegramFileCompressor.exe'
    report = build / 'smoke-test.json'
    if report.exists():
        report.unlink()
    subprocess.run([str(executable), '--self-test', str(report)], cwd=build, check=True, timeout=120)
    smoke = json.loads(report.read_text(encoding='utf-8'))
    if not smoke.get('success') or not smoke.get('frozen'):
        raise RuntimeError('Compiled executable smoke test failed: ' + str(smoke))
    files = source_files()
    revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain']))
    info = {
        'application_version': APP_VERSION,
        'platform': 'windows-x64',
        'python_version': platform.python_version(),
        'pyinstaller_version': importlib.metadata.version('PyInstaller'),
        'source_revision': revision,
        'working_tree_changed': dirty,
        'source_files_sha256': {name: digest(ROOT / name) for name in files},
        'frozen_smoke_test': smoke,
    }
    (destination / 'BUILDINFO.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    portable_name = 'TinyTelegramFileCompressor-v' + APP_VERSION + '-windows-x64'
    public_executable = destination / (portable_name + '.exe')
    shutil.copy2(executable, public_executable)
    portable_files = {
        'TinyTelegramFileCompressor.exe': public_executable,
        'README-WINDOWS.txt': ROOT / 'packaging/README-WINDOWS.txt',
        'LICENSE': ROOT / 'LICENSE',
        'THIRD_PARTY_NOTICES.md': ROOT / 'THIRD_PARTY_NOTICES.md',
        'RELEASE_NOTES.md': ROOT / 'releases/v1.0.0.md',
        'BUILDINFO.json': destination / 'BUILDINFO.json',
    }
    portable_files.update({'licenses/' + path.name: path for path in licenses.iterdir() if path.is_file()})
    write_zip(destination / (portable_name + '.zip'), portable_files, portable_name)
    source_name = 'tiny-telegram-file-compressor-v' + APP_VERSION + '-source'
    write_zip(destination / (source_name + '.zip'), {name: ROOT / name for name in files}, source_name)
    products = [public_executable, destination / (portable_name + '.zip'),
                destination / (source_name + '.zip'), destination / 'BUILDINFO.json']
    (destination / 'SHA256SUMS.txt').write_text(''.join(digest(path) + '  ' + path.name + '\n' for path in products), encoding='ascii')
    print('Release assets verified in', destination, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
