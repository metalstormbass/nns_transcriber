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

## Continuous integration

This repository runs CI on [Chainguard Checks](https://edu.chainguard.dev/chainguard/checks/overview/): each check runs in its own fresh Chainguard OS microVM with no credentials and no network access beyond the hosts it declares. Configuration lives in `.chainguard/ci/`.

**On every pull request (presubmit):**

- `compile` — byte-compiles every Python source file (no network at all)
- `lint` — ruff correctness rules over `main.py` and `transcriber/`; runs when Python sources or CI config change
- `format` — advisory ruff format drift report (never blocks a merge)
- `deps` — installs `requirements.txt`, publishes the frozen dependency set to downstream checks, and posts it as a summary on the GitHub check
- `smoke` — imports PySide6 under the `offscreen` and `minimal` Qt platform plugins, one microVM per variation (advisory)

**After a merge to `main` (postsubmit):**

- `compile` runs again on the merged commit, reported as **Chainguard Checks (postsubmit)**

**On request:**

- `deep-audit` — full dependency install plus a `pip-audit` CVE scan; add the `ci/run:deep-audit` label to a PR to run it

Inspect results from a terminal with:

```bash
chainctl checks status "metalstormbass/nns_transcriber#<PR>"
chainctl checks failures "metalstormbass/nns_transcriber#<PR>"
chainctl checks logs "metalstormbass/nns_transcriber#<PR>" --check <check> --errors
```

## Notes

- This project is chart-only and does not include audio decoding or analysis.
