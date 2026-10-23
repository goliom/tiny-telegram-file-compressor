# Changelog

## 1.2.4

- Optional compression source cleanup, unchecked by default, after archive publication, 7-Zip integrity verification and unchanged source metadata checks.
- The folder chosen in Extract is added to compression step 1; its parent is the output destination in step 2. Automatically added suggestions are replaced when choosing another folder; manually added folders remain.

## 1.2.3

- Clearer task-specific descriptions, live image naming examples, explicit copy destination and deletion warnings, and more visible completion summaries in all nine languages.

- Moved the version number into the Windows title bar, removing it from the in-app heading.

- The folder selected in Extract supplies the Images root and compression defaults, while allowing later independent changes in each tab.

- AVIF/WebP to JPG conversion can be disabled in Images; enabled by default. Original-format copying also supports source-folder renaming.

- Optional image renaming using the immediate source folder name and numbered suffixes starting at 1. Originals and existing output files are preserved.
- Added the option in all nine interface languages.

## 1.2.2

- Extraction now selects **Delete after success** by default; **Keep archives** remains available. Failed archives are always kept.
- The Images tab converts WebP as well as AVIF to JPG while preserving originals, handling transparency on white and avoiding overwrites.

## 1.2.1

- Raised the archive-part limit to 2,000 MiB (2,097,152,000 bytes), matching Telegram's documented free-account ceiling.
- Updated all nine interface languages, command-line help and documentation to show MiB explicitly.

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
