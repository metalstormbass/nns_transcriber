# MCCP

A desktop chart utility for writing and previewing Nashville Number charts.

## Project structure

```text
nns_transcriber/
  main.py
  requirements.txt
  transcriber/
    __init__.py
    app.py
    main_window.py
    constants.py
```

## Current behavior

- Working-directory-based song library and project storage
- Three-pane workflow: markdown editor, rendered preview, song library
- Single link field per song (YouTube or Spotify)
- Reader Mode toggle with `Esc` exit
- Auto format toggle for bar spacing
- Add/remove songs with buttons and right-click menu
- Save Project As and export defaults to the working directory
- Export rendered chart and raw markdown
- Undo/redo with standard shortcuts

## macOS setup

Install Python 3.11+.

```bash
cd nns_transcriber
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

If macOS says Python is missing, install a current Python from python.org or Homebrew.

## Notes

- This project is chart-only and does not include audio decoding or analysis.
