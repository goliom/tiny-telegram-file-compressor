# Building a Windows release

The executable is built on Windows x64 with 64-bit Python 3.14, Tkinter, Git, a separate 7-Zip installation and PyInstaller. It includes Python and Tk; 7-Zip remains external.

## Local build

From a clone of this repository:

```powershell
py -3.14 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe tools\build_windows.py
```

The build script runs the unit/integration tests, builds a windowed one-file executable with the application icon and Windows version information, and launches the resulting executable in self-test mode.

That test exercises the compiled application itself: Tk startup, bundled icon loading, all interface languages, real folder compression, recursive extraction while keeping archives, subsequent archive cleanup and source preservation.

Verified assets are written to `dist/v1.0.0/`:

- `TinyTelegramFileCompressor-v1.0.0-windows-x64.exe`
- `TinyTelegramFileCompressor-v1.0.0-windows-x64.zip`
- `tiny-telegram-file-compressor-v1.0.0-source.zip`
- `BUILDINFO.json`
- `SHA256SUMS.txt`

The recommended Windows ZIP includes the executable, quick-start instructions, the MIT license, third-party notices and Python/Tk/PyInstaller runtime license texts. Build tools, temporary test folders and the virtual environment are excluded from the source ZIP.
License texts are also embedded in the one-file executable.

`BUILDINFO.json` records the Python and PyInstaller versions, the source revision, whether the working tree contained changes, source-file hashes and the compiled smoke-test result. A changed working tree is recorded explicitly rather than being attributed to an older commit.

To repeat the compiled smoke test:

```powershell
& '.\dist\v1.0.0\TinyTelegramFileCompressor-v1.0.0-windows-x64.exe' --self-test '.\build\windows\recheck.json'
Get-Content '.\build\windows\recheck.json'
```

The test uses temporary sample data beside its report and removes the sample data afterwards.

## Build on GitHub Actions

After committing and pushing the build files, open **Actions → Build Windows release → Run workflow**.
The workflow builds and tests the application, then uploads the assets as a workflow artifact. It does not publish a release automatically.

Download the workflow artifact and attach its contents to a draft release with tag `v1.0.0`. Use [releases/v1.0.0.md](releases/v1.0.0.md) as the release description.

## Changing the version

Keep `APP_VERSION` in `app_identity.py`, `packaging/windows-version.txt`, the release notes and the version-specific documentation consistent before making a new release.

The executable is not code-signed. Signing credentials and certificates are not stored in this repository.

Build references: [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html), [runtime data paths](https://pyinstaller.org/en/stable/runtime-information.html) and [windowed standard streams](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html).
