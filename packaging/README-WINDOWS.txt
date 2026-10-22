Tiny Telegram File Compressor v1.1.0 - Windows x64
================================================

1. Extract this ZIP into a normal folder.
2. Install 7-Zip from https://www.7-zip.org/ if it is not already installed.
3. Double-click TinyTelegramFileCompressor.exe.
4. Select English, French, Spanish, Italian, German or Dutch in the language menu.

Python and Tk are included in the executable. No Python installation is needed.
7-Zip is an external dependency and is not included.
The executable is unsigned.

COMPRESS
Add folders, check the ones to process, choose a shared destination, then start.
Each folder gets its own 7z archive set with 2 GB maximum per part and
Normal compression. Source folders are kept.
A single volume smaller than 2 GB is named .7z. Split archives keep numbered
parts (.7z.001, .002, etc.). 2 GB means exactly 2,000,000,000 bytes.

EXTRACT
Choose a root folder. Subfolders and nested archives are scanned automatically.
Keep archives is selected by default. Delete after success removes only the
archives whose extraction completed successfully. Existing content is never
overwritten. Failed archives are kept and reported.

Progress, approximate time remaining and an expandable log are shown in the app.
Stop lets the current item finish before skipping remaining work.

Source code and documentation:
https://github.com/goliom/tiny-telegram-file-compressor

License: MIT for the application code. Runtime licenses are in licenses/.
See THIRD_PARTY_NOTICES.md for Python, Tk, PyInstaller and third-party names.
