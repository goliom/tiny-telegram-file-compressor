# Changelog

## 1.2.0

- Added recursive image collection in a third tab, with nine interface languages.
- Added Russian, Hindi and Simplified Chinese translations.
- AVIF images are converted to JPG copies; all source images are preserved.
- Same-name and same-size outputs are skipped; different sizes receive numbered suffixes without overwriting existing files.
- Bundled Pillow and AVIF codecs in the Windows executable.

## 1.1.0

- Added German (Deutsch) and Dutch (Nederlands) throughout both interface tabs.
- Single-volume archives smaller than 2 GB now use `.7z` instead of `.7z.001`.
- Multipart archives retain numbered parts and a maximum of 2 GB (2,000,000,000 bytes) per file. The byte limit is unchanged from 1.0.0; labels now use GB.
- Updated the Windows executable and verified all six languages, compression, extraction and archive cleanup.

## 1.0.0

- Windows x64 executable with embedded Python/Tk, application icon and version information.
- Windowed-mode handling and hidden 7-Zip subprocess windows.
- Verified binary smoke test covering the GUI, languages, compression, extraction and cleanup.
- Versioned Windows/source ZIPs, runtime licenses, build metadata and SHA-256 checksums.
- Manual GitHub Actions build workflow and English release notes.

### Initial application features

- Independent Windows application with Compress and Extract tabs.
- Separate multipart 7z archive sets, limited to 2,000 MB per part, using Normal compression.
- Folder checkboxes, locations, background size calculation and per-folder status.
- Recursive ZIP/RAR/7z extraction with multipart support and redundant same-name wrapper handling.
- Keep/delete-after-success choices and a journal for resuming extraction cleanup.
- Weighted overall progress, estimated remaining time, expandable logs and final destination access.
- French, English, Spanish and Italian interfaces.
- Telegram/7z-inspired application icon and Windows launcher.
