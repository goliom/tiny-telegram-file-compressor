# Third-party notices

## 7-Zip

This application invokes an independently installed copy of [7-Zip](https://www.7-zip.org/).
No 7-Zip executable or source code is included in this repository. See the [upstream license information](https://www.7-zip.org/license.txt) for that separate program.

## Python and Tk

When running the source code, Python and Tkinter/Tcl/Tk are installed separately. Their interpreters and installers are not stored in this source repository.

The compiled Windows executable includes the Python and Tcl/Tk runtime. Its recommended Windows ZIP includes copies of their license texts in `licenses/`.

## PyInstaller

Windows executables are produced with [PyInstaller](https://pyinstaller.org/). The build tool is a development dependency, and its bootloader is included in the executable. The Windows ZIP includes the PyInstaller license and bootloader exception in `licenses/PyInstaller-COPYING.txt`.

## Telegram and application icon

This is an independent utility for preparing multipart archives for sharing. It is not an official Telegram or 7-Zip product and does not require access to a Telegram account.

The application icon was generated with an AI image-generation tool using a Telegram-style paper airplane and a `7z` badge. See [assets/README.txt](assets/README.txt) for provenance.

Telegram, 7-Zip and other third-party names and marks belong to their respective owners. The MIT license for this project's code does not grant rights to third-party marks or external software.
