"""One split 7z archive per directory; source cleanup is optional and verified."""
import argparse
import os
import re
import shutil
from pathlib import Path

from archive_layout import is_link
from archive_tools import seven_zip
from compression_i18n import text
from sevenzip_runner import run_sevenzip

VOLUME_BYTES = 2000 * 1024**2  # 2,000 MiB: 4,000 Telegram chunks of 524,288 bytes.


def existing_archives(destination, name):
    pattern = re.compile(re.escape(name) + r'\.7z(?:\.\d+)?$', re.I)
    return [path for path in destination.iterdir() if pattern.fullmatch(path.name)]


def validate_folder(source, destination, language='fr'):
    if is_link(source) or not source.is_dir() or not source.name:
        raise ValueError(text('invalid_source', language, path=source))
    source = source.resolve()
    if destination == source or destination.is_relative_to(source):
        raise ValueError(text('source_destination', language, path=source))
    def scan_error(error):
        raise error
    for directory, folders, files in os.walk(source, followlinks=False, onerror=scan_error):
        for name in folders + files:
            path = Path(directory) / name
            if is_link(path):
                raise ValueError(text('source_link', language, path=path))
    return source


def source_snapshot(source):
    """Detect source changes before allowing optional destructive cleanup."""
    snapshot = {}
    def record(path):
        if is_link(path):
            raise RuntimeError('Source contains a link: ' + str(path))
        stat = path.stat()
        snapshot[str(path.relative_to(source))] = (stat.st_dev, stat.st_ino, stat.st_mode,
                                                 stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    record(source)
    def scan_error(error):
        raise error
    for directory, folders, files in os.walk(source, followlinks=False, onerror=scan_error):
        for name in folders + files:
            record(Path(directory) / name)
    return snapshot


def compress_folder(source, destination, executable, volume_bytes=VOLUME_BYTES, on_progress=None, language='fr',
                    delete_sources=False):
    """Create all volumes in staging, then publish without replacing existing files."""
    source, destination = Path(source).absolute(), Path(destination).resolve()
    source = validate_folder(source, destination, language)
    original_snapshot = source_snapshot(source) if delete_sources else None
    if type(volume_bytes) is not int or volume_bytes <= 0:
        raise ValueError(text('invalid_volume', language))
    destination.mkdir(parents=True, exist_ok=True)
    if existing_archives(destination, source.name):
        raise FileExistsError(text('archive_exists', language, name=source.name))
    staging = destination / (source.name + '.compression-en-cours')
    if staging.exists() or is_link(staging):
        raise FileExistsError(text('staging_exists', language, path=staging))
    if not staging.resolve().is_relative_to(destination):
        raise ValueError(text('staging_outside', language))
    staging.mkdir()
    archive = staging / (source.name + '.7z')
    run_sevenzip([executable, 'a', '-t7z', '-mx=5', '-mmt=on', '-spd',
                  f'-v{volume_bytes}b', str(archive), '--', '.' + os.sep + source.name],
                 f'Compression : {source.name}', cwd=str(source.parent), on_progress=on_progress)
    pattern = re.compile(re.escape(source.name) + r'\.7z\.(\d+)$', re.I)
    volumes = []
    for path in staging.iterdir():
        match = pattern.fullmatch(path.name)
        if not match or not path.is_file() or is_link(path):
            raise RuntimeError(text('unexpected_file', language, path=path))
        if not 0 < path.stat().st_size <= volume_bytes:
            raise RuntimeError(text('volume_size', language, path=path))
        volumes.append((int(match[1]), path))
    volumes.sort()
    if not volumes or [number for number, path in volumes] != list(range(1, len(volumes) + 1)):
        raise RuntimeError(text('incomplete_volumes', language))
    if existing_archives(destination, source.name):
        raise FileExistsError(text('archive_appeared', language))
    published = []
    single_archive = len(volumes) == 1 and volumes[0][1].stat().st_size < volume_bytes
    try:
        for number, path in volumes:
            target = destination / (archive.name if single_archive else path.name)
            # Check both resolved absolute paths before moving any directory/file.
            if not path.resolve().is_relative_to(staging.resolve()) or not target.resolve().is_relative_to(destination):
                raise RuntimeError(text('publication_outside', language))
            if os.name == 'nt':
                path.rename(target)  # Windows refuses to overwrite an existing target.
            else:
                os.link(path, target)
                path.unlink()
            published.append((path, target))
        staging.rmdir()
    except Exception:
        # Restore the complete staging set if publishing any volume failed.
        for path, target in reversed(published):
            if not path.exists() and target.exists():
                if os.name == 'nt':
                    target.rename(path)
                else:
                    os.link(target, path)
                    target.unlink()
        raise
    result = [target for path, target in published]
    if delete_sources:
        # Test the published archive (all volumes) before touching the source.
        run_sevenzip([executable, 't', '-spd', '--', str(result[0])],
                     text('verify_before_delete', language, name=source.name))
        if is_link(source) or source.resolve() != source or source_snapshot(source) != original_snapshot:
            raise RuntimeError(text('compression_source_changed', language))
        # The validated absolute source is outside the destination and is exactly
        # the directory selected for this archive; junctions/links were rejected.
        shutil.rmtree(source)
    return result


def launch_gui():
    from desktop_app import launch_gui as launch_desktop
    return launch_desktop()


def main():
    parser = argparse.ArgumentParser(description='Une archive 7z par dossier, compression Normale, en volumes de 2000 MiB maximum.')
    parser.add_argument('dossiers', nargs='*')
    parser.add_argument('--destination')
    parser.add_argument('--apercu', action='store_true')
    args = parser.parse_args()
    if not args.dossiers:
        return launch_gui()
    sources = [Path(path).expanduser().resolve() for path in args.dossiers]
    parents = {source.parent for source in sources}
    if not args.destination and len(parents) != 1:
        parser.error('Indiquez --destination si les dossiers ont des parents différents.')
    destination = Path(args.destination).expanduser().resolve() if args.destination else sources[0].parent
    for source in sources:
        print(f'{source} -> {destination / (source.name + ".7z")} (2000 MiB maximum par volume, .001/.002 si nécessaire, compression Normale)')
    if args.apercu:
        return 0
    errors = 0
    executable = seven_zip()
    for source in sources:
        try:
            volumes = compress_folder(source, destination, executable)
            print(f'OK : {source.name}, {len(volumes)} volume(s). Sources conservées.')
        except Exception as error:
            errors += 1
            print(f'ERREUR {source} : {error}')
    print(f'Terminé : {len(sources) - errors} dossier(s) compressé(s), {errors} erreur(s).')
    return 1 if errors else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nCompression arrêtée. Sources et volumes provisoires conservés.')
