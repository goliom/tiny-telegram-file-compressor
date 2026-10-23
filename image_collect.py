"""Collect images from descendants without modifying sources or replacing files."""
import os
import shutil
import tempfile
from pathlib import Path
from archive_layout import is_link

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif', '.ico'}


def collect_images(root, stop_event, on_event):
    root = Path(root).absolute()
    if is_link(root) or not root.is_dir():
        raise ValueError('Invalid root folder')
    root = root.resolve()
    counts = dict(copied=0, converted=0, skipped=0, errors=0)
    images = []
    def scan_error(error):
        counts['errors'] += 1
        on_event('log', message=str(error))
    for directory, folders, files in os.walk(root, followlinks=False, onerror=scan_error):
        if stop_event.is_set():
            break
        parent = Path(directory)
        folders[:] = sorted(name for name in folders if not is_link(parent / name))
        if parent == root:
            continue
        for name in sorted(files):
            source = parent / name
            if source.suffix.lower() in EXTENSIONS and not is_link(source):
                images.append(source)
    total = len(images)
    for index, source in enumerate(images, 1):
        if stop_event.is_set():
            break
        temporary = None
        try:
            if is_link(source) or not source.resolve().is_relative_to(root):
                raise ValueError('Source outside root: ' + str(source))
            convert = source.suffix.lower() == '.avif'
            suffix = '.jpg' if convert else source.suffix
            fd, name = tempfile.mkstemp(prefix='.image-copy-', dir=root)
            os.close(fd)
            temporary = Path(name)
            if convert:
                from PIL import Image, ImageOps
                with Image.open(source) as original:
                    image = ImageOps.exif_transpose(original).convert('RGBA')
                    background = Image.new('RGB', image.size, 'white')
                    background.paste(image, mask=image.getchannel('A'))
                    background.save(temporary, format='JPEG', quality=95)
            else:
                shutil.copyfile(source, temporary)
            size = temporary.stat().st_size
            number = 0
            while True:
                target = root / (source.stem + (f'_{number}' if number else '') + suffix)
                if target.exists() or is_link(target):
                    if not is_link(target) and target.is_file() and target.stat().st_size == size:
                        counts['skipped'] += 1
                        break
                    number += 1
                    continue
                try:
                    if os.name == 'nt':
                        temporary.rename(target)
                    else:
                        os.link(temporary, target)
                    counts['converted' if convert else 'copied'] += 1
                    break
                except FileExistsError:
                    continue
            on_event('log', message=f'{source.relative_to(root)} → {target.name}')
        except Exception as error:
            counts['errors'] += 1
            on_event('log', message=f'{source}: {error}')
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        on_event('progress', done=index, total=total)
    on_event('finished', stopped=stop_event.is_set(), **counts)
