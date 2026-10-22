"""Source and frozen Windows application entry point."""
import argparse
import os
import sys

from app_identity import APP_NAME, APP_VERSION


def main():
    # Pythonw and PyInstaller --windowed do not provide standard output streams.
    for name in ('stdout', 'stderr'):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, 'w', encoding='utf-8'))
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument('--version', action='version', version=APP_NAME + ' ' + APP_VERSION)
    parser.add_argument('--self-test', metavar='REPORT_JSON', help='Run a temporary GUI/archive smoke test and write a JSON report')
    args = parser.parse_args()
    if args.self_test:
        from frozen_smoke import run
        return run(args.self_test)
    from desktop_app import launch_gui
    return launch_gui()


if __name__ == '__main__':
    raise SystemExit(main())
