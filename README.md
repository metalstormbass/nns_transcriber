# NNS Transcriber

A small desktop transcription workstation focused on Nashville Number System charts.

## Current MVP

- Load WAV/MP3/M4A/FLAC/OGG/etc. through Qt Multimedia
- Play/pause
- Loop playback
- Drag loop boundaries on the waveform
- Variable playback speed control
- Timestamped labeled markers
- Keyboard shortcuts:
  - Space = play/pause
  - L = loop
  - M = marker
  - Left/right = seek
- Editable NNS chart table
- Save/open `.nns.json` projects
- Export a Markdown chart suitable for Obsidian, Apple Notes, Notion, etc.

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

## Next development targets

1. Decode the actual waveform instead of the placeholder waveform.
2. Add a real spectrogram.
3. Add pitch-preserving time stretching.
4. Make chart cells semantic NNS objects instead of plain strings.
5. Add sections/repeats/time signatures.
6. Link every chart bar/chord to an audio time range.
7. Add chord/key/BPM analysis.
8. Add Obsidian/Markdown live project integration.
