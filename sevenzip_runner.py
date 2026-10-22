"""Keep 7-Zip progress visible and report long-running operations."""
import subprocess
import time
import codecs
import re
import sys
import threading


def run_sevenzip(arguments, label, heartbeat=15, cwd=None, on_progress=None):
    print(f"\n{label}", flush=True)
    started = time.monotonic()
    # -bsp1 sends percent progress to stdout. Inherit it instead of hiding it.
    insertion = arguments.index('--') if '--' in arguments else len(arguments)
    switches = ['-bsp1', '-bso0'] + (['-sccUTF-8'] if on_progress else [])
    command = [*arguments[:insertion], *switches, *arguments[insertion:]]
    capture = {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT} if on_progress else {}
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, cwd=cwd, **capture)
    reader = None
    reader_errors = []
    if on_progress:
        def read_progress():
            decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
            buffer = ''
            last = -1
            try:
                while chunk := process.stdout.read1(4096):
                    text = decoder.decode(chunk)
                    try:
                        sys.stdout.write(text)
                    except UnicodeEncodeError:
                        encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
                        sys.stdout.write(text.encode(encoding, errors='replace').decode(encoding))
                    sys.stdout.flush()
                    buffer += text
                    # 7-Zip refreshes the same console line with backspaces/CR.
                    for match in re.finditer(r'(?:^|[\r\n\b])\s*(\d{1,3})%(?=\s|$)', buffer):
                        percent = int(match[1])
                        if last < percent <= 100:
                            on_progress(percent)  # Worker callback; no Tk calls here.
                            last = percent
                    buffer = buffer[-512:]
            except BaseException as error:
                reader_errors.append(error)
        reader = threading.Thread(target=read_progress, daemon=True)
        reader.start()
    try:
        while True:
            try:
                result = process.wait(timeout=heartbeat)
                break
            except subprocess.TimeoutExpired:
                elapsed = int(time.monotonic() - started)
                print(f"\n{label} — {elapsed} s écoulées, 7-Zip est toujours actif.", flush=True)
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    finally:
        if reader:
            reader.join()
            process.stdout.close()
    if reader_errors:
        raise RuntimeError('Lecture de la progression 7-Zip impossible') from reader_errors[0]
    if result:
        raise subprocess.CalledProcessError(result, command)
    if on_progress:
        on_progress(100)
    print(f"\n{label} : terminé en {time.monotonic() - started:.1f} s.", flush=True)
