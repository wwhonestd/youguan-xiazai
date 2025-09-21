# YouGuan XiaZai

A Tkinter-based graphical downloader around the bundled `yt-dlp` binary for macOS. Paste a video or playlist URL, choose cookies (browser or file), pick download mode/quality, fetch playlists, batch subtitle downloads, and convert subtitles to plain text. Built from https://github.com/wwhonest/yt-dlp customizations.

## Features
- Video/audio/subtitle download modes with quality selector.
- Browser or file-based cookies, with automatic handling.
- Channel/playlist fetcher with checkbox selection, numbering, and batch subtitle download.
- Subtitle converter that strips timing/markup and removes duplicates, writing `.txt` files.
- Packaged macOS app via PyInstaller.

## Running the GUI
```
python3 gui_downloader.py
```
Ensure the `yt-dlp_macos` binary in this directory is executable (`chmod +x yt-dlp_macos` if needed).

## Building the macOS App Bundle
```
python3 -m PyInstaller --noconfirm --windowed --name "YouTubeDownloader" --add-binary yt-dlp_macos:. gui_downloader.py
```
The built app appears under `dist/YouTubeDownloader.app`. Gatekeeper may require "Open Anyway" on first launch because the app is unsigned.

## Subtitle Conversion
Use the `Convert Subtitles…` button to select downloaded `.srt`, `.vtt`, `.ass`, `.sbv`, `.ttml`, or `.json` subtitle files. The tool removes timing cues/HTML, deduplicates identical lines, and writes a `.txt` sibling file.

## Repository Layout
- `gui_downloader.py` — Tkinter GUI source.
- `yt-dlp_macos` — bundled yt-dlp universal binary.
- `YouTubeDownloader.spec` — PyInstaller specification.
- `README.md` — project documentation.

Optional directories `build/` and `dist/` are ignored by Git; regenerate them when rebuilding the macOS bundle.
