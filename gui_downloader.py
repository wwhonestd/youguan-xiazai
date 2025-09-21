#!/usr/bin/env python3
"""Simple Tkinter wrapper around yt-dlp_macos for pasting URLs and cookies."""
import html
import json
import os
import re
import shlex
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
YT_DLP_EXEC = os.path.join(BASE_DIR, "yt-dlp_macos")
DEFAULT_COOKIES = os.path.join(BASE_DIR, "cookies.txt")
VIDEO_QUALITY_OPTIONS = {
    "Best available": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
}

COOKIES_BROWSER_CHOICES = {
    "Chrome": "chrome",
    "Brave": "brave",
    "Edge": "edge",
    "Firefox": "firefox",
    "Safari": "safari",
}


class DownloaderUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("640x560")
        self.is_running = False
        self.is_fetching = False
        self.worker: Optional[threading.Thread] = None

        main = ttk.Frame(root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        self.url_var = tk.StringVar()
        self.cookies_var = tk.StringVar(value=DEFAULT_COOKIES if os.path.exists(DEFAULT_COOKIES) else "")
        self.output_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="video")
        self.quality_var = tk.StringVar()
        self.quality_var.set(next(iter(VIDEO_QUALITY_OPTIONS)))
        self.cookies_mode_var = tk.StringVar(value="browser")
        self.browser_var = tk.StringVar()
        if COOKIES_BROWSER_CHOICES:
            self.browser_var.set(next(iter(COOKIES_BROWSER_CHOICES)))
        self.playlist_videos: list[dict[str, str]] = []
        self.playlist_item_urls: dict[str, str] = {}
        self.playlist_checks: dict[str, bool] = {}
        self.checkbox_images = {
            False: self._create_checkbox_image(False),
            True: self._create_checkbox_image(True),
        }

        ttk.Label(main, text="YouTube URL:").grid(row=0, column=0, sticky=tk.W)
        url_entry = ttk.Entry(main, textvariable=self.url_var, width=60)
        url_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=(0, 4))
        url_entry.focus()
        self.fetch_button = ttk.Button(main, text="Fetch Videos", command=self.fetch_playlist, width=14)
        self.fetch_button.grid(row=0, column=3, sticky=tk.E, padx=(4, 0))

        cookies_frame = ttk.LabelFrame(main, text="Cookies", padding=8)
        cookies_frame.grid(row=1, column=0, columnspan=4, sticky=tk.EW, pady=(8, 0))
        cookies_frame.columnconfigure(1, weight=1)

        ttk.Radiobutton(
            cookies_frame,
            text="Use browser cookies",
            value="browser",
            variable=self.cookies_mode_var,
            command=self.update_cookies_state,
        ).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(
            cookies_frame,
            text="Use cookies.txt",
            value="file",
            variable=self.cookies_mode_var,
            command=self.update_cookies_state,
        ).grid(row=0, column=1, sticky=tk.W, padx=(12, 0))

        self.cookies_entry = ttk.Entry(cookies_frame, textvariable=self.cookies_var, width=45)
        self.cookies_entry.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=(0, 4), pady=(8, 0))
        self.cookies_button = ttk.Button(cookies_frame, text="Browse", command=self.pick_cookies)
        self.cookies_button.grid(row=1, column=2, sticky=tk.E, pady=(8, 0))

        ttk.Label(cookies_frame, text="Browser:").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        self.browser_combo = ttk.Combobox(
            cookies_frame,
            textvariable=self.browser_var,
            values=list(COOKIES_BROWSER_CHOICES.keys()),
            state="readonly" if COOKIES_BROWSER_CHOICES else "disabled",
            width=20,
        )
        self.browser_combo.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

        ttk.Label(main, text="Output folder:").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        output_entry = ttk.Entry(main, textvariable=self.output_var, width=45)
        output_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=(0, 4), pady=(8, 0))
        ttk.Button(main, text="Browse", command=self.pick_output_dir).grid(row=2, column=3, sticky=tk.E, pady=(8, 0))

        options_frame = ttk.LabelFrame(main, text="Download Options", padding=8)
        options_frame.grid(row=3, column=0, columnspan=4, sticky=tk.EW, pady=(12, 0))
        options_frame.columnconfigure(1, weight=1)

        ttk.Radiobutton(
            options_frame,
            text="Video",
            value="video",
            variable=self.mode_var,
            command=self.update_quality_state,
        ).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(
            options_frame,
            text="Audio",
            value="audio",
            variable=self.mode_var,
            command=self.update_quality_state,
        ).grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(
            options_frame,
            text="Subtitles",
            value="subs",
            variable=self.mode_var,
            command=self.update_quality_state,
        ).grid(row=0, column=2, sticky=tk.W)

        ttk.Label(options_frame, text="Video quality:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.quality_box = ttk.Combobox(
            options_frame,
            textvariable=self.quality_var,
            values=list(VIDEO_QUALITY_OPTIONS.keys()),
            state="readonly",
            width=18,
        )
        self.quality_box.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=(8, 0))

        self.playlist_frame = ttk.LabelFrame(main, text="Playlist Videos", padding=8)
        self.playlist_frame.grid(row=4, column=0, columnspan=4, sticky=tk.NSEW, pady=(12, 0))
        self.playlist_frame.columnconfigure(0, weight=1)
        self.playlist_frame.rowconfigure(0, weight=1)

        self.playlist_tree = ttk.Treeview(
            self.playlist_frame,
            columns=("title",),
            show="tree headings",
            selectmode="none",
            height=6,
        )
        self.playlist_tree.heading("#0", text="#")
        self.playlist_tree.column("#0", width=48, anchor=tk.CENTER, stretch=False)
        self.playlist_tree.heading("title", text="Video title")
        self.playlist_tree.column("title", anchor=tk.W)
        self.playlist_tree.grid(row=0, column=0, columnspan=3, sticky=tk.NSEW)
        self.playlist_tree.bind("<Button-1>", self.on_playlist_click)
        self.playlist_tree.bind("<Return>", self.on_playlist_key_toggle)
        self.playlist_tree.bind("<space>", self.on_playlist_key_toggle)

        playlist_scroll = ttk.Scrollbar(self.playlist_frame, command=self.playlist_tree.yview)
        playlist_scroll.grid(row=0, column=3, sticky=tk.NS)
        self.playlist_tree.configure(yscrollcommand=playlist_scroll.set)

        self.playlist_status = ttk.Label(self.playlist_frame, text="Fetch a channel to list videos.")
        self.playlist_status.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        ttk.Button(
            self.playlist_frame,
            text="Select All",
            command=self.select_all_playlist,
            width=12,
        ).grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Button(
            self.playlist_frame,
            text="Clear Selection",
            command=self.clear_playlist_selection,
            width=16,
        ).grid(row=2, column=1, sticky=tk.W, pady=(8, 0))
        ttk.Button(
            self.playlist_frame,
            text="Convert Subtitles…",
            command=self.convert_subtitles,
            width=20,
        ).grid(row=2, column=2, sticky=tk.E, pady=(8, 0))

        self.playlist_frame.grid_remove()

        self.download_button = ttk.Button(main, text="Download", command=self.start_download, width=18)
        self.download_button.grid(row=5, column=0, columnspan=4, pady=12)

        self.output_text = tk.Text(main, height=12, state=tk.DISABLED)
        self.output_text.grid(row=6, column=0, columnspan=4, sticky=tk.NSEW)

        scrollbar = ttk.Scrollbar(main, command=self.output_text.yview)
        scrollbar.grid(row=6, column=4, sticky=tk.NS)
        self.output_text.configure(yscrollcommand=scrollbar.set)

        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=0)
        main.rowconfigure(6, weight=1)

        self.update_cookies_state()
        self.update_quality_state()

        if not os.path.isfile(YT_DLP_EXEC):
            messagebox.showerror("Missing binary", f"Cannot find yt-dlp executable at {YT_DLP_EXEC}")
            self.download_button.state(["disabled"])

    def pick_cookies(self) -> None:
        path = filedialog.askopenfilename(title="Select cookies.txt", filetypes=[("Text files", "*.txt"), ("All files", "*")])
        if path:
            self.cookies_var.set(path)
            self.cookies_mode_var.set("file")
            self.update_cookies_state()

    def pick_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Select download folder")
        if path:
            self.output_var.set(path)

    def start_download(self) -> None:
        if self.is_running:
            return
        url = self.url_var.get().strip()
        mode = self.mode_var.get()
        cookies_mode = self.cookies_mode_var.get()
        cookies = self.cookies_var.get().strip()
        output_dir = self.output_var.get().strip()

        target_urls: list[str]

        selection_urls = [self.playlist_item_urls[item] for item, checked in self.playlist_checks.items() if checked]
        selected_from_playlist = bool(selection_urls)

        if mode == "subs":
            if selection_urls:
                target_urls = selection_urls
            elif url:
                target_urls = [url]
            else:
                messagebox.showwarning("No videos selected", "Select videos in the playlist or provide a URL.")
                return
        else:
            if not url:
                messagebox.showwarning("Missing URL", "Please paste a YouTube URL.")
                return
            target_urls = [url]

        cmd = [YT_DLP_EXEC, "--newline"]
        if cookies_mode == "browser":
            browser_key = COOKIES_BROWSER_CHOICES.get(self.browser_var.get())
            if browser_key:
                cmd.extend(["--cookies-from-browser", browser_key])
        else:
            if not cookies and os.path.isfile(DEFAULT_COOKIES):
                cookies = DEFAULT_COOKIES
                self.cookies_var.set(DEFAULT_COOKIES)
            if cookies:
                if not os.path.isfile(cookies):
                    messagebox.showwarning("Cookies file missing", f"Cannot find cookies file at {cookies}.")
                    return
                cmd.extend(["--cookies", cookies])
        if output_dir:
            cmd.extend(["-P", output_dir])

        if mode == "video":
            quality = self.quality_var.get()
            format_selector = VIDEO_QUALITY_OPTIONS.get(quality)
            if format_selector:
                cmd.extend(["-f", format_selector])
        elif mode == "audio":
            cmd.extend(["-f", "bestaudio/best", "-x", "--audio-format", "mp3"])
        elif mode == "subs":
            cmd.extend(["--skip-download", "--write-subs", "--write-auto-subs", "--sub-format", "best"])
            if selected_from_playlist:
                cmd.append("--no-playlist")

        cmd.extend(target_urls)

        self.is_running = True
        self.download_button.state(["disabled"])
        display_cmd = " ".join(shlex.quote(part) for part in cmd)
        self.append_output(f"Running: {display_cmd}\n")

        def worker() -> None:
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            except FileNotFoundError:
                self.append_output("Failed to start yt-dlp. Check the executable path.\n")
                self.finish_download()
                return

            for line in process.stdout or []:
                self.append_output(line)
            return_code = process.wait()
            if return_code == 0:
                self.append_output("\nDownload completed successfully.\n")
            else:
                self.append_output(f"\nyt-dlp exited with code {return_code}.\n")
            self.finish_download()

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def finish_download(self) -> None:
        self.is_running = False
        self.root.after(0, lambda: self.download_button.state(["!disabled"]))

    def append_output(self, message: str) -> None:
        def write() -> None:
            self.output_text.configure(state=tk.NORMAL)
            self.output_text.insert(tk.END, message)
            self.output_text.see(tk.END)
            self.output_text.configure(state=tk.DISABLED)

        self.root.after(0, write)

    def update_quality_state(self) -> None:
        state = "readonly" if self.mode_var.get() == "video" else "disabled"
        self.quality_box.configure(state=state)

    def update_cookies_state(self) -> None:
        mode = self.cookies_mode_var.get()
        file_state = "normal" if mode == "file" else "disabled"
        browser_state = "readonly" if mode == "browser" else "disabled"
        self.cookies_entry.configure(state=file_state)
        self.cookies_button.state(["!disabled"] if mode == "file" else ["disabled"])
        self.browser_combo.configure(state=browser_state)

    def fetch_playlist(self) -> None:
        if self.is_running or self.is_fetching:
            return
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please paste a YouTube channel or playlist URL.")
            return

        self.is_fetching = True
        self.fetch_button.state(["disabled"])
        self.playlist_frame.grid()
        self.playlist_status.configure(text="Fetching video list...")
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)
        self.playlist_checks.clear()
        self.playlist_item_urls.clear()

        def worker() -> None:
            try:
                process = subprocess.Popen(
                    [YT_DLP_EXEC, "--flat-playlist", "--dump-json", url],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except FileNotFoundError:
                self.root.after(0, lambda: self.finish_fetch([], 1, "yt-dlp executable not found."))
                return

            videos: list[dict[str, str]] = []
            for line in process.stdout or []:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("_type") == "url":
                    raw_url = data.get("url") or ""
                    if raw_url.startswith("http"):
                        video_url = raw_url
                    else:
                        video_url = f"https://www.youtube.com/watch?v={raw_url}"
                    title = data.get("title") or video_url
                    videos.append({"title": title, "url": video_url})

            stderr_text = process.stderr.read() if process.stderr else ""
            return_code = process.wait()
            self.root.after(0, lambda: self.finish_fetch(videos, return_code, stderr_text))

        threading.Thread(target=worker, daemon=True).start()

    def finish_fetch(self, videos: list[dict[str, str]], return_code: int, stderr_text: str) -> None:
        self.is_fetching = False
        self.fetch_button.state(["!disabled"])
        self.playlist_videos = videos
        self.playlist_item_urls.clear()
        self.playlist_checks.clear()
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)

        if return_code != 0:
            self.playlist_status.configure(text="Failed to fetch videos. See log for details.")
            if stderr_text:
                self.append_output(stderr_text + "\n")
            messagebox.showerror("Fetch failed", "Unable to fetch playlist information. Check the log for details.")
            if not videos:
                self.playlist_frame.grid()
            return

        if not videos:
            self.playlist_status.configure(text="No videos found in this playlist/channel.")
            return

        for index, video in enumerate(videos, start=1):
            item_id = self.playlist_tree.insert(
                "",
                tk.END,
                text=f"{index}",
                image=self.checkbox_images[False],
                values=(video["title"],),
            )
            self.playlist_item_urls[item_id] = video["url"]
            self.playlist_checks[item_id] = False
        self.playlist_status.configure(text=f"Fetched {len(videos)} videos. Select the ones you need.")

    def select_all_playlist(self) -> None:
        for item in self.playlist_tree.get_children():
            self._set_playlist_item_checked(item, True)

    def clear_playlist_selection(self) -> None:
        for item in self.playlist_tree.get_children():
            self._set_playlist_item_checked(item, False)

    def on_playlist_click(self, event: tk.Event) -> str | None:
        region = self.playlist_tree.identify("region", event.x, event.y)
        if region not in {"tree", "cell"}:
            return None
        item = self.playlist_tree.identify_row(event.y)
        if not item:
            return None
        self._toggle_playlist_item(item)
        return "break"

    def on_playlist_key_toggle(self, event: tk.Event) -> str:
        focused = self.playlist_tree.focus()
        if focused:
            self._toggle_playlist_item(focused)
        return "break"

    def _toggle_playlist_item(self, item_id: str) -> None:
        current = self.playlist_checks.get(item_id, False)
        self._set_playlist_item_checked(item_id, not current)

    def _set_playlist_item_checked(self, item_id: str, checked: bool) -> None:
        if item_id not in self.playlist_item_urls:
            return
        self.playlist_checks[item_id] = checked
        self.playlist_tree.item(item_id, image=self.checkbox_images[checked])

    def _create_checkbox_image(self, checked: bool) -> tk.PhotoImage:
        size = 14
        img = tk.PhotoImage(width=size, height=size)
        bg = "#ffffff"
        border = "#555555"
        check = "#1a7f37"

        for x in range(size):
            img.put(border, to=(x, 0))
            img.put(border, to=(x, size - 1))
        for y in range(size):
            img.put(border, to=(0, y))
            img.put(border, to=(size - 1, y))
        for x in range(1, size - 1):
            img.put(bg, to=(x, 1, x + 1, size - 1))

        if checked:
            check_pixels = [
                (3, size - 6),
                (4, size - 5),
                (5, size - 4),
                (6, size - 5),
                (7, size - 6),
                (8, size - 7),
                (9, size - 8),
            ]
            for x, y in check_pixels:
                img.put(check, to=(x, y, x + 1, y + 1))
                img.put(check, to=(x, y - 1, x + 1, y))

        return img

    def convert_subtitles(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select subtitle files",
            filetypes=[
                ("Subtitle files", "*.srt *.vtt *.ass *.sbv *.ttml *.json"),
                ("All files", "*"),
            ],
        )
        if not paths:
            return

        self.append_output(f"Converting {len(paths)} subtitle file(s) to text…\n")

        def worker() -> None:
            success = 0
            failures: list[tuple[str, Exception]] = []
            for path in paths:
                try:
                    output_path = self._subtitle_to_text(path)
                except Exception as exc:  # noqa: BLE001
                    failures.append((path, exc))
                    self.append_output(f"Failed: {path} -> {exc}\n")
                else:
                    success += 1
                    self.append_output(f"Converted: {path} -> {output_path}\n")

            def finish() -> None:
                if failures:
                    messagebox.showwarning(
                        "Conversion finished",
                        f"Converted {success} file(s) with {len(failures)} failure(s).",
                    )
                else:
                    messagebox.showinfo(
                        "Conversion finished",
                        f"Converted {success} subtitle file(s) to plain text.",
                    )

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _subtitle_to_text(self, path: str) -> str:
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw_lines = fh.readlines()

        text_lines: list[str] = []
        for raw in raw_lines:
            line = raw.strip()
            if not line:
                if text_lines and text_lines[-1] != "":
                    text_lines.append("")
                continue
            upper = line.upper()
            if ext in {".srt", ".vtt", ".sbv", ".ttml"}:
                if line.isdigit():
                    continue
                if "-->" in line:
                    continue
                if upper.startswith("WEBVTT") or upper.startswith("NOTE"):
                    continue
            line = re.sub(r"<[^>]+>", "", line)
            line = html.unescape(line)
            if line:
                text_lines.append(line)

        cleaned: list[str] = []
        previous_blank = False
        seen_lines: set[str] = set()
        for line in text_lines:
            normalized = line.strip().lower()
            if not line:
                if previous_blank:
                    continue
                previous_blank = True
            else:
                previous_blank = False
                if normalized in seen_lines:
                    continue
                seen_lines.add(normalized)
            cleaned.append(line)

        output_text = "\n".join(cleaned).strip() + "\n"
        output_path = os.path.splitext(path)[0] + ".txt"
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(output_text)
        return output_path


def main() -> None:
    root = tk.Tk()
    DownloaderUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
