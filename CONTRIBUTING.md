# Contributing

Use Windows with Python 3.12 or newer, Tkinter and a separate 7-Zip installation.
Install image support before running the application or tests: `py -3 -m pip install -r requirements.txt`.

Run the application:

```powershell
py -3 compresser_dossiers.py
```

Run the tests from the repository root:

```powershell
py -3 -m unittest discover -s tests -p "test_*.py"
```

GUI tests require a desktop session. Archive fixtures are generated inside temporary repository folders and removed after testing.

Keep user content protected: compression must preserve source folders, extraction must keep failed archives, and output publication must not overwrite existing content.

Update all nine interface languages together when changing text. Include a useful regression test for changes to archive grouping, extraction layout, image collection, publication, deletion or resume behavior.

When reporting an issue, include your Python and 7-Zip versions, the selected language, steps to reproduce, and relevant log lines. Replace personal paths and filenames before posting logs or screenshots.
