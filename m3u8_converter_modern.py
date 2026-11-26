import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import json
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from hls_conversion import HLS_INPUT_OPTIONS, PROCESS_OPTIONS


APP_TITLE = "StreamForge Converter"
APP_SUBTITLE = "M3U8 / TS / TTS / MKV to MP4"
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ICON_PATH = BASE_DIR / "assets" / "m3u8_converter_icon.ico"
LOGO_PATH = BASE_DIR / "assets" / "m3u8_converter_logo_48.png"
TAB_CONVERTER_ICON_PATH = BASE_DIR / "assets" / "tab_converter.png"
TAB_YOUTUBE_ICON_PATH = BASE_DIR / "assets" / "tab_youtube.png"
SEG_RANGE_PREFIX = "seg-range-json:"

COLORS = {
    "bg": "#171717",
    "surface": "#202020",
    "panel": "#242424",
    "panel_2": "#2a2a2a",
    "field": "#181818",
    "line": "#3a3a3a",
    "text": "#f5f5f5",
    "muted": "#b8c0cc",
    "accent": "#3b82f6",
    "accent_2": "#2563eb",
    "accent_soft": "#17325f",
    "danger": "#ef4444",
    "success": "#22c55e",
    "warn": "#f59e0b",
}


class ModernM3U8Converter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE} - SunBae")
        self.geometry("1100x1000")
        self.minsize(1040, 900)
        self.configure(bg=COLORS["bg"])

        if ICON_PATH.exists():
            try:
                self.iconbitmap(str(ICON_PATH))
            except tk.TclError:
                pass

        self.ffmpeg = shutil.which("ffmpeg")
        self.ytdlp = shutil.which("yt-dlp")
        self.selected_files: list[str] = []
        self.url_headers: dict[str, dict[str, str]] = {}
        self.output_directory = ""
        self.current_process: subprocess.Popen | None = None
        self.is_converting = False
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.start_time = 0.0
        self.current_file_started = 0.0
        self.progress_mode = "determinate"

        self.delete_original = tk.BooleanVar(value=False)
        self.filename_format = tk.StringVar(value="original_date")
        self.conversion_mode = tk.StringVar(value="separate")
        self.url_var = tk.StringVar()
        self.range_pattern_var = tk.StringVar()
        self.range_text_var = tk.StringVar()
        self.range_ext_var = tk.StringVar(value="auto")
        self.range_workers_var = tk.StringVar(value="6")
        self.range_output_name_var = tk.StringVar()
        self.youtube_url_var = tk.StringVar()
        self.youtube_format_var = tk.StringVar(value="Best (Video+Audio)")
        self.youtube_use_cookies = tk.BooleanVar(value=True)
        self.youtube_cookie_browser = tk.StringVar(value="chrome")
        self.youtube_title_var = tk.StringVar(value="No video loaded")
        self.youtube_meta_var = tk.StringVar(value="Paste a YouTube URL and fetch metadata.")
        self.active_tab = tk.StringVar(value="converter")
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.detail_var = tk.StringVar(value="Select stream files and an output folder.")
        self.elapsed_var = tk.StringVar(value="00:00")
        self.file_count_var = tk.StringVar(value="0 files")
        self.logo_image = None
        self.tab_converter_image = None
        self.tab_youtube_image = None
        self.tab_buttons: dict[str, tk.Button] = {}

        self.setup_styles()
        self.build_ui()
        self.after(100, self.process_events)

    def setup_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Panel2.TFrame", background=COLORS["panel_2"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI Semibold", 22))
        style.configure("Subtitle.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("TButton", padding=(12, 7), font=("Segoe UI Semibold", 10))
        style.configure("Accent.TButton", background=COLORS["accent_2"], foreground="#ffffff", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#34445f")])
        style.configure("Ghost.TButton", background=COLORS["panel_2"], foreground=COLORS["text"], borderwidth=0)
        style.map("Ghost.TButton", background=[("active", "#333333"), ("disabled", "#2d2d2d")])
        style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("TRadiobutton", background=COLORS["panel"], foreground=COLORS["text"])
        style.map(
            "TCheckbutton",
            background=[("active", COLORS["panel"]), ("selected", COLORS["panel"]), ("disabled", COLORS["panel"])],
            foreground=[("active", COLORS["text"]), ("selected", COLORS["text"]), ("disabled", COLORS["muted"])],
        )
        style.map(
            "TRadiobutton",
            background=[("active", COLORS["panel"]), ("selected", COLORS["panel"]), ("disabled", COLORS["panel"])],
            foreground=[("active", COLORS["text"]), ("selected", COLORS["text"]), ("disabled", COLORS["muted"])],
        )
        style.configure("Blue.Horizontal.TProgressbar", troughcolor="#111111", background=COLORS["accent"], thickness=10)
        style.configure("TEntry", fieldbackground=COLORS["field"], foreground=COLORS["text"], bordercolor=COLORS["line"])

    def build_ui(self) -> None:
        shell = ttk.Frame(self, padding=20, style="App.TFrame")
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(3, weight=1)

        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)

        brand = ttk.Frame(header, style="App.TFrame")
        brand.grid(row=0, column=0, rowspan=2, sticky="w")
        if LOGO_PATH.exists():
            self.logo_image = tk.PhotoImage(file=str(LOGO_PATH))
            tk.Label(brand, image=self.logo_image, bg=COLORS["bg"], borderwidth=0, highlightthickness=0).pack(
                side="left", padx=(0, 12)
            )
        else:
            self.logo_fallback(brand)
        title_stack = ttk.Frame(brand, style="App.TFrame")
        title_stack.pack(side="left")
        ttk.Label(title_stack, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_stack, text=APP_SUBTITLE, style="Subtitle.TLabel").pack(anchor="w", pady=(1, 0))
        self.ffmpeg_badge = self.status_chip(header, "FFmpeg ready" if self.ffmpeg else "FFmpeg missing", bool(self.ffmpeg))
        self.ffmpeg_badge.grid(row=0, column=1, rowspan=2, sticky="e")

        metrics = ttk.Frame(shell, style="App.TFrame")
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for idx in range(3):
            metrics.columnconfigure(idx, weight=1)
        self.metric_card(metrics, 0, self.file_count_var, "Queue")
        self.metric_card(metrics, 1, self.status_var, "Status")
        self.metric_card(metrics, 2, self.elapsed_var, "Elapsed")

        self.tab_bar = ttk.Frame(shell, style="App.TFrame")
        self.tab_bar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.build_tab_bar(self.tab_bar)

        self.content = ttk.Frame(shell, style="App.TFrame")
        self.content.grid(row=3, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.converter_body = ttk.Frame(self.content, style="App.TFrame")
        self.converter_body.grid(row=0, column=0, sticky="nsew")
        self.converter_body.columnconfigure(0, weight=3)
        self.converter_body.columnconfigure(1, weight=2)
        self.converter_body.rowconfigure(0, weight=1)

        left = self.panel(self.converter_body, 0, 0)
        right = self.panel(self.converter_body, 0, 1)
        self.build_file_panel(left)
        self.build_control_panel(right)

        self.youtube_body = ttk.Frame(self.content, style="App.TFrame")
        self.youtube_body.columnconfigure(0, weight=3)
        self.youtube_body.columnconfigure(1, weight=2)
        self.youtube_body.rowconfigure(0, weight=1)
        self.build_youtube_panel(self.youtube_body)

        log_panel = self.panel(shell, 4, 0, pady=(12, 0))
        self.build_log_panel(log_panel)

    def build_tab_bar(self, parent: ttk.Frame) -> None:
        if TAB_CONVERTER_ICON_PATH.exists():
            self.tab_converter_image = tk.PhotoImage(file=str(TAB_CONVERTER_ICON_PATH))
        if TAB_YOUTUBE_ICON_PATH.exists():
            self.tab_youtube_image = tk.PhotoImage(file=str(TAB_YOUTUBE_ICON_PATH))
        self.tab_buttons["converter"] = tk.Button(
            parent,
            text="Converter",
            image=self.tab_converter_image,
            compound="left",
            padx=18,
            command=lambda: self.switch_tab("converter"),
            bg=COLORS["accent_2"],
            fg=COLORS["text"],
            activebackground="#1d4ed8",
            activeforeground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
            # padx above also gives the icon/text enough breathing room inside the tab.
            pady=8,
        )
        self.tab_buttons["converter"].pack(side="left")
        self.tab_buttons["youtube"] = tk.Button(
            parent,
            text="YouTube",
            image=self.tab_youtube_image,
            compound="left",
            padx=18,
            command=lambda: self.switch_tab("youtube"),
            bg=COLORS["panel_2"],
            fg=COLORS["text"],
            activebackground="#333333",
            activeforeground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
            # padx above also gives the icon/text enough breathing room inside the tab.
            pady=8,
        )
        self.tab_buttons["youtube"].pack(side="left", padx=(8, 0))
        self.update_tab_buttons()

    def switch_tab(self, tab: str) -> None:
        self.active_tab.set(tab)
        self.update_tab_buttons()
        if tab == "youtube":
            self.converter_body.grid_remove()
            self.youtube_body.grid(row=0, column=0, sticky="nsew")
        else:
            self.youtube_body.grid_remove()
            self.converter_body.grid(row=0, column=0, sticky="nsew")

    def update_tab_buttons(self) -> None:
        for name, button in self.tab_buttons.items():
            selected = self.active_tab.get() == name
            button.config(
                bg=COLORS["accent_2"] if selected else COLORS["panel_2"],
                fg=COLORS["text"],
                activebackground="#1d4ed8" if selected else "#333333",
                activeforeground=COLORS["text"],
            )

    def status_chip(self, parent: ttk.Frame, text: str, ok: bool) -> tk.Frame:
        width = 154 if ok else 168
        height = 38
        fill = COLORS["accent_soft"] if ok else "#3b2415"
        outline = COLORS["accent"] if ok else COLORS["warn"]
        chip = tk.Canvas(parent, width=width, height=height, bg=COLORS["bg"], highlightthickness=0, bd=0)
        self._rounded_rect(chip, 1, 1, width - 1, height - 1, radius=18, fill=fill, outline=outline, width=1)
        inner = tk.Frame(chip, bg=fill)
        tk.Label(
            inner,
            text="●",
            bg=fill,
            fg=COLORS["success"] if ok else COLORS["warn"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(0, 7))
        tk.Label(
            inner,
            text=text,
            bg=fill,
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 10),
        ).pack(side="left")
        chip.create_window(width // 2, height // 2, window=inner)
        return chip

    def logo_fallback(self, parent: ttk.Frame) -> None:
        logo = tk.Canvas(parent, width=48, height=48, bg=COLORS["bg"], highlightthickness=0, bd=0)
        logo.pack(side="left", padx=(0, 12))
        self._rounded_rect(logo, 2, 2, 46, 46, radius=12, fill="#111111", outline=COLORS["line"], width=1)
        logo.create_text(24, 24, text="↓", fill=COLORS["accent"], font=("Segoe UI", 24, "bold"))

    @staticmethod
    def _rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> int:
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def metric_card(self, parent: ttk.Frame, column: int, variable: tk.StringVar, caption: str) -> None:
        card = tk.Frame(parent, bg=COLORS["panel_2"], highlightbackground=COLORS["line"], highlightthickness=1)
        card.grid(row=0, column=column, sticky="ew", padx=(0, 12) if column < 2 else 0)
        tk.Label(
            card,
            textvariable=variable,
            bg=COLORS["panel_2"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 15),
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(
            card,
            text=caption,
            bg=COLORS["panel_2"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(2, 12))

    def panel(self, parent: ttk.Frame, row: int, column: int, padx=(0, 16), pady=0) -> ttk.Frame:
        outer = tk.Frame(parent, bg=COLORS["line"], padx=1, pady=1)
        outer.grid(row=row, column=column, sticky="nsew", padx=padx if column == 0 else 0, pady=pady)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        panel = ttk.Frame(outer, padding=16, style="Panel.TFrame")
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        return panel

    def build_file_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Files", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="Add one file, multiple files, or scan a folder.", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 10)
        )

        buttons = ttk.Frame(parent, style="Panel.TFrame")
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(buttons, text="Add File", command=self.select_single_file, style="Accent.TButton").pack(side="left")
        ttk.Button(buttons, text="Add Many", command=self.select_multiple_files, style="Ghost.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Scan Folder", command=self.select_folder, style="Ghost.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Remove", command=self.remove_selected_file, style="Ghost.TButton").pack(side="right")

        url_row = ttk.Frame(parent, style="Panel.TFrame")
        url_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        url_row.columnconfigure(0, weight=1)
        self.url_entry = tk.Entry(
            url_row,
            textvariable=self.url_var,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), ipady=7)
        self.url_entry.insert(0, "Paste URL here (supports v0_0000.seg ~ v0_0483.seg)")
        self.url_entry.bind("<FocusIn>", self.clear_url_placeholder)
        ttk.Button(url_row, text="Add URL", command=self.add_url, style="Ghost.TButton").grid(row=0, column=1)

        range_box = ttk.Frame(parent, style="Panel.TFrame")
        range_box.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        range_box.columnconfigure(0, weight=1)
        range_box.columnconfigure(1, weight=0)
        range_box.columnconfigure(2, weight=0)
        range_box.columnconfigure(3, weight=0)
        ttk.Label(range_box, text="Range download", style="Panel.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        self.range_pattern_entry = tk.Entry(
            range_box,
            textvariable=self.range_pattern_var,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.range_pattern_entry.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(7, 0), ipady=7)
        self.range_pattern_entry.insert(0, "First segment URL, e.g. https://host/path/v0_0000.mpx")
        self.range_pattern_entry.bind("<FocusIn>", self.clear_range_pattern_placeholder)
        self.range_text_entry = tk.Entry(
            range_box,
            textvariable=self.range_text_var,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.range_text_entry.grid(row=2, column=0, sticky="ew", pady=(8, 0), padx=(0, 8), ipady=7)
        self.range_text_entry.insert(0, "Last number, e.g. 0483 or auto")
        self.range_text_entry.bind("<FocusIn>", self.clear_range_text_placeholder)
        self.range_ext_entry = tk.Entry(
            range_box,
            textvariable=self.range_ext_var,
            width=7,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.range_ext_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0), padx=(0, 8), ipady=7)
        self.range_workers_entry = tk.Entry(
            range_box,
            textvariable=self.range_workers_var,
            width=7,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.range_workers_entry.grid(row=2, column=2, sticky="ew", pady=(8, 0), padx=(0, 8), ipady=7)
        ttk.Button(range_box, text="Add Range", command=self.add_range_download, style="Ghost.TButton").grid(
            row=2, column=3, sticky="ew", pady=(8, 0)
        )
        self.range_output_name_entry = tk.Entry(
            range_box,
            textvariable=self.range_output_name_var,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.range_output_name_entry.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0), ipady=7)
        self.range_output_name_entry.insert(0, "Output name prefix, e.g. episode_10")
        self.range_output_name_entry.bind("<FocusIn>", self.clear_range_output_name_placeholder)
        self.range_headers_text = tk.Text(
            range_box,
            height=5,
            wrap=tk.WORD,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Consolas", 9),
        )
        self.range_headers_text.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.range_headers_text.insert(tk.END, self.default_range_headers_text())

        list_wrap = tk.Frame(parent, bg=COLORS["line"], padx=1, pady=1)
        list_wrap.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        parent.rowconfigure(5, weight=1)
        list_wrap.columnconfigure(0, weight=1)
        list_wrap.rowconfigure(0, weight=1)
        self.file_listbox = tk.Listbox(
            list_wrap,
            height=10,
            selectmode=tk.EXTENDED,
            bg=COLORS["field"],
            fg=COLORS["text"],
            selectbackground=COLORS["accent_2"],
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.file_listbox.grid(row=0, column=0, sticky="nsew")
        self.file_listbox.bind("<Delete>", self.remove_selected_file)
        self.file_listbox.bind("<BackSpace>", self.remove_selected_file)
        scrollbar = tk.Scrollbar(
            list_wrap,
            orient=tk.VERTICAL,
            command=self.file_listbox.yview,
            bg=COLORS["panel_2"],
            troughcolor=COLORS["field"],
            activebackground=COLORS["line"],
            width=12,
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_listbox.configure(yscrollcommand=scrollbar.set)

    def build_control_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Output", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="Choose destination and conversion behavior.", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 10)
        )

        output_row = ttk.Frame(parent, style="Panel.TFrame")
        output_row.grid(row=2, column=0, sticky="ew")
        output_row.columnconfigure(0, weight=1)
        self.output_entry = tk.Entry(
            output_row,
            textvariable=self.output_var,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), ipady=7)
        ttk.Button(output_row, text="Browse", command=self.select_output_directory, style="Ghost.TButton").grid(row=0, column=1)

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        self.convert_button = ttk.Button(actions, text="Start Conversion", command=self.start_conversion, style="Accent.TButton")
        self.convert_button.grid(row=0, column=0, sticky="ew")
        self.stop_button = ttk.Button(actions, text="Stop", command=self.stop_conversion, state="disabled", style="Ghost.TButton")
        self.stop_button.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        ttk.Button(actions, text="Open Output Folder", command=self.open_output_folder, style="Ghost.TButton").grid(
            row=2, column=0, sticky="ew", pady=(7, 0)
        )

        options = ttk.Frame(parent, style="Panel.TFrame")
        options.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(options, text="Mode", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.dark_radio(
            options,
            "Convert separately",
            self.conversion_mode,
            "separate",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.dark_radio(
            options,
            "Merge selected TS/TTS into one MP4",
            self.conversion_mode,
            "merge",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        ttk.Label(options, text="File name", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(
            row=3, column=0, sticky="w", pady=(14, 0)
        )
        self.dark_radio(
            options,
            "Original name + timestamp",
            self.filename_format,
            "original_date",
        ).grid(
            row=4, column=0, sticky="w", pady=(8, 0)
        )
        self.dark_radio(
            options,
            "Timestamp only",
            self.filename_format,
            "date_only",
        ).grid(
            row=5, column=0, sticky="w", pady=(6, 0)
        )
        tk.Checkbutton(
            options,
            text="Delete original source file after successful conversion",
            variable=self.delete_original,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["field"],
            font=("Segoe UI", 10),
            borderwidth=0,
            highlightthickness=0,
        ).grid(
            row=6, column=0, sticky="w", pady=(10, 0)
        )

        progress = ttk.Frame(parent, style="Panel.TFrame")
        progress.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        progress.columnconfigure(0, weight=1)
        ttk.Label(progress, textvariable=self.detail_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.current_progress = ttk.Progressbar(progress, mode="determinate", style="Blue.Horizontal.TProgressbar")
        self.current_progress.grid(row=1, column=0, sticky="ew")

    def build_youtube_panel(self, parent: ttk.Frame) -> None:
        left = self.panel(parent, 0, 0)
        right = self.panel(parent, 0, 1)

        ttk.Label(left, text="YouTube", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="Fetch metadata, choose a format, then download.", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 12)
        )

        url_row = ttk.Frame(left, style="Panel.TFrame")
        url_row.grid(row=2, column=0, sticky="ew")
        url_row.columnconfigure(0, weight=1)
        self.youtube_url_entry = tk.Entry(
            url_row,
            textvariable=self.youtube_url_var,
            bg=COLORS["field"],
            fg=COLORS["muted"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )
        self.youtube_url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), ipady=7)
        self.set_youtube_placeholder()
        self.youtube_url_entry.bind("<FocusIn>", self.clear_youtube_placeholder)
        self.youtube_url_entry.bind("<FocusOut>", self.restore_youtube_placeholder)
        ttk.Button(url_row, text="Preview", command=self.fetch_youtube_metadata, style="Accent.TButton").grid(row=0, column=1)

        meta = tk.Frame(left, bg=COLORS["field"], highlightbackground=COLORS["line"], highlightthickness=1)
        meta.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        left.rowconfigure(3, weight=1)
        tk.Label(meta, textvariable=self.youtube_title_var, bg=COLORS["field"], fg=COLORS["text"], font=("Segoe UI Semibold", 14), anchor="w", wraplength=560).pack(
            anchor="w", fill="x", padx=16, pady=(16, 4)
        )
        tk.Label(meta, textvariable=self.youtube_meta_var, bg=COLORS["field"], fg=COLORS["muted"], font=("Segoe UI", 10), anchor="w", justify="left", wraplength=560).pack(
            anchor="w", fill="x", padx=16, pady=(0, 16)
        )

        ttk.Label(right, text="Download", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="Saved into the selected output folder.", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 12))

        yt_out = ttk.Frame(right, style="Panel.TFrame")
        yt_out.grid(row=2, column=0, sticky="ew")
        yt_out.columnconfigure(0, weight=1)
        tk.Entry(
            yt_out,
            textvariable=self.output_var,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8), ipady=7)
        ttk.Button(yt_out, text="Browse", command=self.select_output_directory, style="Ghost.TButton").grid(row=0, column=1)

        formats = ttk.Frame(right, style="Panel.TFrame")
        formats.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        ttk.Label(formats, text="Format", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        for row, (label, value) in enumerate(
            [
                ("Best video + audio", "Best (Video+Audio)"),
                ("1080p", "1080p"),
                ("720p", "720p"),
                ("480p", "480p"),
                ("Audio only MP3", "Audio Only (MP3)"),
            ],
            start=1,
        ):
            self.dark_radio(formats, label, self.youtube_format_var, value).grid(row=row, column=0, sticky="w", pady=(7 if row == 1 else 5, 0))

        auth = ttk.Frame(right, style="Panel.TFrame")
        auth.grid(row=4, column=0, sticky="ew", pady=(18, 0))
        ttk.Label(auth, text="YouTube sign-in", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.dark_check(auth, "Use browser cookies", self.youtube_use_cookies).grid(row=1, column=0, sticky="w", pady=(7, 0))
        browser_row = ttk.Frame(auth, style="Panel.TFrame")
        browser_row.grid(row=2, column=0, sticky="w", pady=(6, 0))
        for col, (label, value) in enumerate([("Chrome", "chrome"), ("Edge", "edge"), ("Firefox", "firefox")]):
            self.dark_radio(browser_row, label, self.youtube_cookie_browser, value).grid(row=0, column=col, sticky="w", padx=(0, 14))

        progress = ttk.Frame(right, style="Panel.TFrame")
        progress.grid(row=5, column=0, sticky="ew", pady=(18, 0))
        progress.columnconfigure(0, weight=1)
        ttk.Label(progress, textvariable=self.detail_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.youtube_progress = ttk.Progressbar(progress, mode="determinate", style="Blue.Horizontal.TProgressbar")
        self.youtube_progress.grid(row=1, column=0, sticky="ew")

        self.youtube_download_button = ttk.Button(right, text="Download YouTube", command=self.start_youtube_download, style="Accent.TButton")
        self.youtube_download_button.grid(
            row=6, column=0, sticky="ew", pady=(22, 0)
        )
        self.youtube_stop_button = ttk.Button(right, text="Stop", command=self.stop_conversion, state="disabled", style="Ghost.TButton")
        self.youtube_stop_button.grid(row=7, column=0, sticky="ew", pady=(8, 0))

    def dark_radio(self, parent: ttk.Frame, text: str, variable: tk.StringVar, value: str) -> tk.Radiobutton:
        return tk.Radiobutton(
            parent,
            text=text,
            variable=variable,
            value=value,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["field"],
            font=("Segoe UI", 10),
            borderwidth=0,
            highlightthickness=0,
        )

    def dark_check(self, parent: ttk.Frame, text: str, variable: tk.BooleanVar) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["field"],
            font=("Segoe UI", 10),
            borderwidth=0,
            highlightthickness=0,
        )

    def build_log_panel(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="Live Log", style="Panel.TLabel", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.log_text = scrolledtext.ScrolledText(
            parent,
            height=6,
            wrap=tk.WORD,
            bg="#111111",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            font=("Consolas", 10),
            relief="flat",
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

    def select_single_file(self) -> None:
        path = filedialog.askopenfilename(title="Select stream file", filetypes=self.stream_filetypes())
        if path:
            self.selected_files = [os.path.abspath(path)]
            self.apply_default_output_directory([path])
            self.update_file_list()
            self.write_log(f"Added file: {os.path.basename(path)}")

    def clear_url_placeholder(self, _event=None) -> None:
        if self.url_var.get().startswith("Paste URL here"):
            self.url_var.set("")

    def clear_range_pattern_placeholder(self, _event=None) -> None:
        if self.range_pattern_var.get().startswith(("URL pattern", "First segment URL")):
            self.range_pattern_var.set("")

    def clear_range_text_placeholder(self, _event=None) -> None:
        if self.range_text_var.get().startswith(("Range,", "Last number")):
            self.range_text_var.set("")

    def clear_range_output_name_placeholder(self, _event=None) -> None:
        if self.range_output_name_var.get().startswith("Output name prefix"):
            self.range_output_name_var.set("")

    def set_youtube_placeholder(self) -> None:
        self.youtube_url_var.set("Paste YouTube URL here")
        if hasattr(self, "youtube_url_entry"):
            self.youtube_url_entry.config(fg=COLORS["muted"])

    def clear_youtube_placeholder(self, _event=None) -> None:
        if self.youtube_url_var.get() == "Paste YouTube URL here":
            self.youtube_url_var.set("")
            self.youtube_url_entry.config(fg=COLORS["text"])

    def restore_youtube_placeholder(self, _event=None) -> None:
        if not self.youtube_url_var.get().strip():
            self.set_youtube_placeholder()

    def get_youtube_url(self) -> str:
        value = self.youtube_url_var.get().strip()
        return "" if value == "Paste YouTube URL here" else value

    def add_url(self) -> None:
        url = self.url_var.get().strip()
        if not url or url.startswith("Paste URL here"):
            messagebox.showwarning("No URL", "Paste a URL first.")
            return
        seg_range = self.parse_seg_range_text(url)
        if seg_range:
            headers = {}
            if hasattr(self, "range_headers_text"):
                headers = self.parse_request_headers(self.range_headers_text.get("1.0", tk.END))
            self.selected_files.append(self.make_seg_range_item(*seg_range, headers=headers))
            if not self.output_directory:
                default_dir = str(Path.home() / "Downloads")
                self.output_directory = default_dir
                self.output_var.set(default_dir)
                self.write_log(f"Output folder auto-set: {default_dir}")
            self.url_var.set("")
            self.update_file_list()
            action = "Queued" if self.is_converting else "Added"
            self.write_log(f"{action} segment range: {seg_range[0]} -> {seg_range[1]}")
            return
        if not self.is_url(url):
            messagebox.showwarning("Invalid URL", "URL must start with http:// or https://.")
            return
        self.selected_files.append(url)
        if hasattr(self, "range_headers_text"):
            headers = self.parse_request_headers(self.range_headers_text.get("1.0", tk.END))
            if headers:
                self.url_headers[url] = headers
        if not self.output_directory:
            default_dir = str(Path.home() / "Downloads")
            self.output_directory = default_dir
            self.output_var.set(default_dir)
            self.write_log(f"Output folder auto-set: {default_dir}")
        self.url_var.set("")
        self.update_file_list()
        action = "Queued" if self.is_converting else "Added"
        header_note = " with request headers" if self.url_headers.get(url) else ""
        self.write_log(f"{action} URL{header_note}: {url}")

    def add_range_download(self) -> None:
        first_url = self.range_pattern_var.get().strip()
        last_number = self.range_text_var.get().strip()
        extension = self.normalize_optional_extension(self.range_ext_var.get())
        workers = self.parse_parallel_workers(self.range_workers_var.get())
        if not first_url or first_url.startswith(("URL pattern", "First segment URL")):
            messagebox.showwarning("No URL", "Enter the first segment URL first.")
            return
        auto_discover = (not last_number) or last_number.startswith(("Range,", "Last number")) or last_number.lower() == "auto"
        if auto_discover:
            seg_range = self.build_auto_range_from_first_url(first_url, extension)
        elif "{n}" in first_url:
            seg_range = self.build_range_from_pattern(first_url, last_number, extension or ".seg")
        else:
            seg_range = self.build_range_from_first_url(first_url, last_number, extension)
        if not seg_range:
            messagebox.showwarning(
                "Invalid input",
                "Use the first segment URL and the last number. Example: first URL v0_0000.mpx, last number 0483.",
            )
            return
        headers = self.parse_request_headers(self.range_headers_text.get("1.0", tk.END))
        output_name = self.range_output_name_var.get().strip()
        if output_name.startswith("Output name prefix"):
            output_name = ""
        self.selected_files.append(
            self.make_seg_range_item(
                *seg_range,
                headers=headers,
                workers=workers,
                auto_discover=auto_discover,
                output_name=output_name,
            )
        )
        if not self.output_directory:
            default_dir = str(Path.home() / "Downloads")
            self.output_directory = default_dir
            self.output_var.set(default_dir)
            self.write_log(f"Output folder auto-set: {default_dir}")
        self.range_pattern_var.set("")
        self.range_text_var.set("")
        self.range_output_name_var.set("")
        self.update_file_list()
        action = "Queued" if self.is_converting else "Added"
        self.write_log(f"{action} range download: {seg_range[0]} -> {seg_range[1]}")

    def select_multiple_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Select stream files", filetypes=self.stream_filetypes())
        if paths:
            self.selected_files.extend(os.path.abspath(path) for path in paths)
            self.apply_default_output_directory(paths)
            self.update_file_list()
            self.write_log(f"Added {len(paths)} files")

    def select_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder containing stream files")
        if not folder:
            return
        found = []
        for root, _, files in os.walk(folder):
            for file_name in files:
                if Path(file_name).suffix.lower() in {".m3u8", ".ts", ".tts", ".mkv", ".mp4", ".seg", ".mpx"}:
                    found.append(os.path.abspath(os.path.join(root, file_name)))
        if not found:
            messagebox.showwarning("No files", "No M3U8, TS, TTS, SEG, MPX, MKV, or MP4 files were found in the selected folder.")
            return
        self.selected_files.extend(found)
        self.apply_default_output_directory(found)
        self.update_file_list()
        self.write_log(f"Scanned folder: {len(found)} stream files found")

    @staticmethod
    def stream_filetypes() -> list[tuple[str, str]]:
        return [
            ("Supported files", "*.m3u8 *.ts *.tts *.mkv *.mp4 *.seg *.mpx"),
            ("Video files", "*.mkv *.mp4"),
            ("M3U8 playlists", "*.m3u8"),
            ("Transport streams", "*.ts *.tts *.seg *.mpx"),
            ("All files", "*.*"),
        ]

    def apply_default_output_directory(self, paths) -> None:
        if self.output_directory or not paths:
            return
        first = str(paths[0])
        if self.is_url(first):
            default_dir = str(Path.home() / "Downloads")
        else:
            first_path = os.path.abspath(first)
            default_dir = first_path if os.path.isdir(first_path) else os.path.dirname(first_path)
        self.output_directory = default_dir
        self.output_var.set(default_dir)
        self.write_log(f"Output folder auto-set: {default_dir}")

    def remove_selected_file(self, event=None) -> str | None:
        selection = self.file_listbox.curselection()
        if not selection:
            return "break" if event else None
        for index in reversed(selection):
            removed = self.selected_files[index]
            self.url_headers.pop(removed, None)
            del self.selected_files[index]
        self.update_file_list()
        return "break" if event else None

    def select_output_directory(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_directory = os.path.abspath(folder)
            self.output_var.set(self.output_directory)
            self.write_log(f"Output folder: {self.output_directory}")

    def update_file_list(self) -> None:
        self.file_listbox.delete(0, tk.END)
        for path in self.selected_files:
            self.file_listbox.insert(tk.END, self.display_name(path))
        self.file_count_var.set(f"{len(self.selected_files)} files")

    @staticmethod
    def is_url(value: str) -> bool:
        return value.lower().startswith(("http://", "https://"))

    @staticmethod
    def is_seg_range_item(value: str) -> bool:
        return value.startswith(SEG_RANGE_PREFIX)

    @staticmethod
    def make_seg_range_item(
        start_url: str,
        end_url: str,
        headers: dict[str, str] | None = None,
        workers: int = 6,
        auto_discover: bool = False,
        output_name: str = "",
    ) -> str:
        return SEG_RANGE_PREFIX + json.dumps(
            {
                "start_url": start_url,
                "end_url": end_url,
                "headers": headers or {},
                "workers": workers,
                "auto_discover": auto_discover,
                "output_name": ModernM3U8Converter.sanitize_filename_stem(output_name),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def seg_range_info(value: str) -> dict:
        return json.loads(value[len(SEG_RANGE_PREFIX) :])

    @staticmethod
    def parse_seg_url_parts(url: str) -> tuple[str, int, int, str] | None:
        match = re.match(r"^(https?://.*?)(\d+)(\.[^/?#]+(?:[?#].*)?)$", url.strip(), re.IGNORECASE)
        if not match:
            return None
        prefix, number_text, suffix = match.groups()
        return prefix, int(number_text), len(number_text), suffix

    @staticmethod
    def parse_range_numbers(value: str) -> tuple[int, int, int] | None:
        parts = [part.strip() for part in re.split(r"\s*(?:~|-|to)\s*", value, maxsplit=1, flags=re.IGNORECASE)]
        if len(parts) != 2:
            return None
        start_match = re.search(r"(\d+)(?!.*\d)", parts[0])
        end_match = re.search(r"(\d+)(?!.*\d)", parts[1])
        if not start_match or not end_match:
            return None
        start_text = start_match.group(1)
        end_text = end_match.group(1)
        start_number = int(start_text)
        end_number = int(end_text)
        if end_number < start_number:
            return None
        return start_number, end_number, max(len(start_text), len(end_text))

    @staticmethod
    def parse_parallel_workers(value: str) -> int:
        try:
            workers = int(value.strip())
        except (TypeError, ValueError):
            return 6
        return max(1, min(16, workers))

    @staticmethod
    def sanitize_filename_stem(value: str) -> str:
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value.strip())
        stem = re.sub(r"\s+", " ", stem).strip(" .")
        return stem[:120]

    @staticmethod
    def normalize_extension(value: str) -> str:
        extension = value.strip().lower()
        if not extension:
            return ".seg"
        if not extension.startswith("."):
            extension = "." + extension
        if not re.fullmatch(r"\.[a-z0-9][a-z0-9_-]{0,15}", extension):
            return ".seg"
        return extension

    @classmethod
    def normalize_optional_extension(cls, value: str) -> str | None:
        extension = value.strip().lower()
        if not extension or extension == "auto":
            return None
        normalized = cls.normalize_extension(extension)
        return normalized

    @classmethod
    def build_range_from_first_url(cls, first_url: str, last_number_text: str, extension: str | None = None) -> tuple[str, str] | None:
        first_parts = cls.parse_seg_url_parts(first_url)
        range_numbers = cls.parse_range_numbers(f"{first_parts[1] if first_parts else '0'}-{last_number_text}") if first_parts else None
        if not first_parts or not range_numbers:
            return None
        prefix, start_number, url_width, suffix = first_parts
        _, end_number, input_width = range_numbers
        if end_number < start_number:
            return None
        width = max(url_width, input_width)
        start_url = f"{prefix}{start_number:0{width}d}{suffix}"
        end_url = f"{prefix}{end_number:0{width}d}{suffix}"
        if extension:
            start_url = cls.replace_url_extension(start_url, extension)
            end_url = cls.replace_url_extension(end_url, extension)
        return start_url, end_url

    @classmethod
    def build_auto_range_from_first_url(cls, first_url: str, extension: str | None = None) -> tuple[str, str] | None:
        first_parts = cls.parse_seg_url_parts(first_url)
        if not first_parts:
            return None
        prefix, start_number, width, suffix = first_parts
        start_url = f"{prefix}{start_number:0{width}d}{suffix}"
        if extension:
            start_url = cls.replace_url_extension(start_url, extension)
        return start_url, start_url

    @classmethod
    def build_range_from_pattern(cls, pattern: str, range_text: str, extension: str = ".seg") -> tuple[str, str] | None:
        range_numbers = cls.parse_range_numbers(range_text)
        if not range_numbers:
            return None
        start_number, end_number, width = range_numbers
        extension = cls.normalize_extension(extension)
        pattern = pattern.strip().replace("{ext}", extension.lstrip("."))
        if "{n}" in pattern:
            start_url = pattern.replace("{n}", f"{start_number:0{width}d}")
            end_url = pattern.replace("{n}", f"{end_number:0{width}d}")
            if extension:
                start_url = cls.replace_url_extension(start_url, extension)
                end_url = cls.replace_url_extension(end_url, extension)
            if not cls.parse_seg_url_parts(start_url) or not cls.parse_seg_url_parts(end_url):
                return None
            return start_url, end_url
        pattern_parts = cls.parse_seg_url_parts(pattern)
        if not pattern_parts:
            return None
        prefix, _, pattern_width, suffix = pattern_parts
        width = max(width, pattern_width)
        start_url = f"{prefix}{start_number:0{width}d}{suffix}"
        end_url = f"{prefix}{end_number:0{width}d}{suffix}"
        if extension:
            start_url = cls.replace_url_extension(start_url, extension)
            end_url = cls.replace_url_extension(end_url, extension)
        return start_url, end_url

    @staticmethod
    def replace_url_extension(url: str, extension: str) -> str:
        parsed = urlparse(url)
        path = parsed.path
        new_path = re.sub(r"\.[^/.?#]+$", extension, path)
        if new_path == path and not path.lower().endswith(extension):
            new_path = path + extension
        return parsed._replace(path=new_path).geturl()

    @staticmethod
    def default_range_headers_text() -> str:
        return "\n".join(
            [
                "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0",
                "Accept: */*",
                "Accept-Language: en-US,en;q=0.9",
                "Accept-Encoding: identity",
                "Origin: https://ygking3.com",
                "Referer: https://ygking3.com/",
                "Sec-Fetch-Dest: empty",
                "Sec-Fetch-Mode: cors",
                "Sec-Fetch-Site: cross-site",
            ]
        )

    @staticmethod
    def parse_request_headers(value: str) -> dict[str, str]:
        headers: dict[str, str] = {}
        blocked = {"connection", "host", "te", "content-length"}
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line or line.upper().startswith(("GET ", "POST ", "HEAD ", "HTTP/")):
                continue
            if ":" not in line:
                continue
            key, header_value = line.split(":", 1)
            key = key.strip()
            if not key or key.lower() in blocked:
                continue
            headers[key] = header_value.strip()
        return headers

    @staticmethod
    def default_download_headers() -> dict[str, str]:
        return ModernM3U8Converter.parse_request_headers(ModernM3U8Converter.default_range_headers_text())

    @staticmethod
    def ffmpeg_header_text(headers: dict[str, str]) -> str:
        safe_headers = []
        for key, value in headers.items():
            if not key or "\r" in key or "\n" in key or "\r" in value or "\n" in value:
                continue
            safe_headers.append(f"{key}: {value}")
        return "\r\n".join(safe_headers) + ("\r\n" if safe_headers else "")

    @classmethod
    def parse_seg_range_text(cls, value: str) -> tuple[str, str] | None:
        if "~" not in value:
            return None
        left, right = [part.strip() for part in value.split("~", 1)]
        left_parts = cls.parse_seg_url_parts(left)
        if not left_parts:
            return None
        prefix, start_number, width, suffix = left_parts
        if cls.is_url(right):
            right_parts = cls.parse_seg_url_parts(right)
            if not right_parts:
                return None
            end_number = right_parts[1]
            end_url = right
        else:
            end_match = re.search(r"(\d+)(?:\.[^/?#]+)?(?:[?#].*)?$", right, re.IGNORECASE)
            if not end_match:
                return None
            end_number = int(end_match.group(1))
            end_url = f"{prefix}{end_number:0{width}d}{suffix}"
        if end_number < start_number:
            return None
        return left, end_url

    @staticmethod
    def display_name(value: str) -> str:
        if ModernM3U8Converter.is_seg_range_item(value):
            info = ModernM3U8Converter.seg_range_info(value)
            start_name = Path(urlparse(info["start_url"]).path).name
            end_name = Path(urlparse(info["end_url"]).path).name
            return f"{start_name} ~ {end_name}"
        if ModernM3U8Converter.is_url(value):
            parsed = urlparse(value)
            name = Path(parsed.path).name
            return name or parsed.netloc or value
        return os.path.basename(value)

    def start_conversion(self) -> None:
        if not self.ffmpeg:
            messagebox.showerror("FFmpeg missing", "FFmpeg was not found in PATH.")
            return
        if not self.selected_files:
            messagebox.showwarning("No files", "Add at least one stream file.")
            return
        if not self.output_directory:
            messagebox.showwarning("No output", "Choose an output folder.")
            return
        if self.conversion_mode.get() == "merge":
            unsupported = [
                item
                for item in self.selected_files
                if self.is_url(item) or self.is_seg_range_item(item) or Path(item).suffix.lower() not in {".ts", ".tts", ".seg", ".mpx"}
            ]
            if unsupported:
                messagebox.showwarning("Merge unavailable", "Merge mode supports local .ts, .tts, .seg, and .mpx files only.")
                return
            if len(self.selected_files) < 2:
                messagebox.showwarning("Need more files", "Merge mode needs at least two stream segment files.")
                return
        self.is_converting = True
        self.start_time = time.time()
        self.convert_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("Running")
        self.detail_var.set("Preparing conversion...")
        self.current_progress.config(mode="indeterminate")
        self.current_progress.start(10)
        self.worker = threading.Thread(target=self.conversion_worker, daemon=True)
        self.worker.start()

    def fetch_youtube_metadata(self) -> None:
        url = self.get_youtube_url()
        if not self.validate_youtube_url(url):
            return
        if not self.ensure_ytdlp():
            return
        self.status_var.set("Preview")
        self.youtube_title_var.set("Loading metadata...")
        self.youtube_meta_var.set("Running yt-dlp metadata lookup.")
        self.write_log(f"YouTube metadata lookup: {url}")
        threading.Thread(
            target=self.youtube_metadata_worker,
            args=(url, self.youtube_use_cookies.get(), self.youtube_cookie_browser.get()),
            daemon=True,
        ).start()

    def youtube_metadata_worker(self, url: str, use_cookies: bool, cookie_browser: str) -> None:
        command = self.ytdlp_command() + [
            "--dump-single-json",
            "--skip-download",
            "--no-playlist",
            "--no-warnings",
            "--extractor-args",
            "youtube:player_client=android,web",
            "--force-ipv4",
        ]
        if use_cookies:
            command += ["--cookies-from-browser", cookie_browser]
        command.append(url)
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=90)
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "Metadata lookup failed").strip()
                self.events.put(("youtube_meta", ("Metadata lookup failed", detail[:900])))
                self.events.put(("log", f"YouTube metadata error: {detail[:900]}"))
                return
            import json

            info = json.loads(completed.stdout)
            title = info.get("title") or "Untitled video"
            duration = self.format_duration(info.get("duration"))
            uploader = info.get("uploader") or info.get("channel") or "Unknown channel"
            best_height = self.best_height(info.get("formats") or [])
            meta = f"Channel: {uploader}\nDuration: {duration}\nBest height: {best_height or 'Unknown'}"
            self.events.put(("youtube_meta", (title, meta)))
            self.events.put(("log", f"YouTube metadata loaded: {title}"))
        except Exception as exc:
            self.events.put(("youtube_meta", ("Metadata lookup failed", str(exc))))
            self.events.put(("log", f"YouTube metadata error: {exc}"))

    def start_youtube_download(self) -> None:
        url = self.get_youtube_url()
        if not self.validate_youtube_url(url):
            return
        if not self.ensure_ytdlp():
            return
        if not self.output_directory:
            default_dir = str(Path.home() / "Downloads")
            self.output_directory = default_dir
            self.output_var.set(default_dir)
            self.write_log(f"Output folder auto-set: {default_dir}")
        self.is_converting = True
        self.start_time = time.time()
        self.status_var.set("YouTube")
        self.detail_var.set("Starting YouTube download...")
        self.current_progress.config(mode="indeterminate")
        self.current_progress["value"] = 0
        self.current_progress.start(10)
        if hasattr(self, "youtube_progress"):
            self.youtube_progress.config(mode="indeterminate")
            self.youtube_progress["value"] = 0
            self.youtube_progress.start(10)
        if hasattr(self, "youtube_download_button"):
            self.youtube_download_button.config(state="disabled")
        if hasattr(self, "youtube_stop_button"):
            self.youtube_stop_button.config(state="normal")
        threading.Thread(
            target=self.youtube_download_worker,
            args=(url, self.youtube_format_var.get(), self.youtube_use_cookies.get(), self.youtube_cookie_browser.get()),
            daemon=True,
        ).start()

    def youtube_download_worker(self, url: str, format_choice: str, use_cookies: bool, cookie_browser: str) -> None:
        output_template = str(Path(self.output_directory) / "%(title).180B [%(id)s].%(ext)s")
        command = self.ytdlp_command() + [
            "--newline",
            "--no-playlist",
            "--force-ipv4",
            "--extractor-args",
            "youtube:player_client=android,web",
            "--merge-output-format",
            "mp4",
            "-f",
            self.youtube_format_selector(format_choice),
            "-o",
            output_template,
        ]
        if use_cookies:
            command += ["--cookies-from-browser", cookie_browser]
        if format_choice == "Audio Only (MP3)":
            command += ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "192K"]
        command.append(url)
        self.events.put(("log", "yt-dlp: " + subprocess.list2cmdline(command)))
        success = self.run_ytdlp_command(command)
        if success:
            self.events.put(("detail", "YouTube download complete."))
            self.events.put(("message", "YouTube download complete."))
        else:
            self.events.put(("detail", "YouTube download failed. See log."))
        self.events.put(("finish", None))

    def run_ytdlp_command(self, command: list[str]) -> bool:
        popen_args = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "universal_newlines": True,
        }
        if sys.platform == "win32":
            popen_args["encoding"] = "utf-8"
            popen_args["errors"] = "ignore"
            popen_args["creationflags"] = subprocess.CREATE_NO_WINDOW
        self.current_process = subprocess.Popen(command, **popen_args)
        assert self.current_process.stdout is not None
        for raw_line in self.current_process.stdout:
            if not self.is_converting:
                break
            line = raw_line.strip()
            if not line:
                continue
            match = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", line)
            if match:
                value = min(100.0, max(0.0, float(match.group(1))))
                self.events.put(("progress", value))
                self.events.put(("detail", f"YouTube download... {value:.1f}%"))
            elif any(token in line.lower() for token in ("error", "warning", "failed", "unable", "sign in")):
                self.events.put(("log", f"yt-dlp: {line}"))
                if "sign in to confirm" in line.lower() or "not a bot" in line.lower():
                    self.events.put(
                        (
                            "log",
                            "YouTube sign-in required. Keep browser cookies enabled and make sure the selected browser is logged into YouTube.",
                        )
                    )
            elif line.startswith(("[download]", "[Merger]", "[ExtractAudio]", "[Metadata]")):
                self.events.put(("log", line))
        return_code = self.current_process.wait()
        self.current_process = None
        return self.is_converting and return_code == 0

    def ensure_ytdlp(self) -> bool:
        if self.ytdlp or self.can_run_python_ytdlp():
            return True
        messagebox.showerror("yt-dlp missing", "yt-dlp is required for YouTube downloads. Install it with: python -m pip install yt-dlp")
        return False

    def ytdlp_command(self) -> list[str]:
        if self.ytdlp:
            return [self.ytdlp]
        return [sys.executable, "-m", "yt_dlp"]

    @staticmethod
    def can_run_python_ytdlp() -> bool:
        try:
            import yt_dlp  # noqa: F401

            return True
        except Exception:
            return False

    @staticmethod
    def validate_youtube_url(url: str) -> bool:
        if not url:
            messagebox.showwarning("No URL", "Paste a YouTube URL first.")
            return False
        if not url.lower().startswith(("http://", "https://")):
            messagebox.showwarning("Invalid URL", "URL must start with http:// or https://.")
            return False
        return True

    @staticmethod
    def youtube_format_selector(choice: str) -> str:
        return {
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "Audio Only (MP3)": "bestaudio",
        }.get(choice, "bestvideo+bestaudio/best")

    @staticmethod
    def best_height(formats: list[dict]) -> str | None:
        heights = [fmt.get("height") for fmt in formats if fmt.get("vcodec") != "none" and isinstance(fmt.get("height"), int)]
        return f"{max(heights)}p" if heights else None

    @staticmethod
    def format_duration(value) -> str:
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return "Unknown"
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def stop_conversion(self) -> None:
        self.is_converting = False
        if self.current_process and self.current_process.poll() is None:
            self.current_process.kill()
        self.events.put(("log", "Conversion stopped."))
        self.events.put(("finish", None))

    def conversion_worker(self) -> None:
        if self.conversion_mode.get() == "merge":
            self.merge_worker()
            return

        success_count = 0
        fail_count = 0
        index = 0
        while index < len(self.selected_files):
            if not self.is_converting:
                break
            input_path = self.selected_files[index]
            display_index = index + 1
            index += 1
            output_path = self.output_path_for(input_path)
            self.current_file_started = time.time()
            self.events.put(("status", "Running"))
            self.events.put(("detail", f"Converting {display_index}/{len(self.selected_files)}: {self.display_name(input_path)}"))
            self.events.put(("log", f"Start: {input_path}"))
            if self.is_seg_range_item(input_path):
                success = self.download_seg_range_and_merge(input_path, output_path)
            elif self.is_local_mp4_input(input_path):
                success = self.copy_mp4_with_timestamp(input_path, output_path)
            else:
                success = self.convert_one(input_path, output_path, self.url_headers.get(input_path))
            if success:
                success_count += 1
                self.events.put(("log", f"Success: {output_path}"))
                auto_delete_suffixes = {".tts", ".mkv"}
                should_delete_source = (not self.is_url(input_path)) and (
                    not self.is_seg_range_item(input_path)
                ) and (
                    self.delete_original.get() or Path(input_path).suffix.lower() in auto_delete_suffixes
                )
                if should_delete_source:
                    try:
                        os.remove(input_path)
                        self.events.put(("log", f"Deleted original: {input_path}"))
                    except OSError as exc:
                        self.events.put(("log", f"Original delete failed: {exc}"))
            else:
                fail_count += 1
                self.events.put(("log", f"Failed: {input_path}"))
        self.events.put(("detail", f"Done. Success {success_count}, failed {fail_count}."))
        self.events.put(("finish", None))
        if success_count:
            self.events.put(("message", f"Conversion complete\nSuccess: {success_count}\nFailed: {fail_count}"))

    def merge_worker(self) -> None:
        stamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        output_path = str(Path(self.output_directory) / f"merged_{stamp}.mp4")
        self.events.put(("status", "Merging"))
        self.events.put(("detail", f"Merging {len(self.selected_files)} files into one MP4..."))
        self.events.put(("log", f"Merge output: {output_path}"))
        success = self.merge_ts_files(self.selected_files, output_path)
        if success:
            self.events.put(("log", f"Merge success: {output_path}"))
            for input_path in self.selected_files:
                if Path(input_path).suffix.lower() == ".tts":
                    try:
                        os.remove(input_path)
                        self.events.put(("log", f"Deleted original: {input_path}"))
                    except OSError as exc:
                        self.events.put(("log", f"Original delete failed: {exc}"))
            self.events.put(("detail", "Merge done. Success 1, failed 0."))
            self.events.put(("message", f"Merge complete\n{output_path}"))
        else:
            self.events.put(("detail", "Merge failed. See log."))
        self.events.put(("finish", None))

    def output_path_for(self, input_path: str) -> str:
        stamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        if self.filename_format.get() == "original_date":
            if self.is_seg_range_item(input_path):
                info = self.seg_range_info(input_path)
                stem = self.sanitize_filename_stem(info.get("output_name", ""))
                if not stem:
                    start_stem = Path(urlparse(info["start_url"]).path).stem or "segments"
                    end_stem = Path(urlparse(info["end_url"]).path).stem or "end"
                    stem = f"{start_stem}_to_{end_stem}"
            elif self.is_url(input_path):
                parsed = urlparse(input_path)
                stem = Path(parsed.path).stem or "download"
            else:
                stem = Path(input_path).stem
            filename = f"{stem}_{stamp}.mp4"
        else:
            filename = f"{stamp}.mp4"
        return str(Path(self.output_directory) / filename)

    @staticmethod
    def is_local_mp4_input(input_path: str) -> bool:
        return (not ModernM3U8Converter.is_url(input_path)) and Path(input_path).suffix.lower() == ".mp4"

    def copy_mp4_with_timestamp(self, input_path: str, output_path: str) -> bool:
        try:
            source = Path(input_path)
            destination = Path(output_path)
            if source.resolve() == destination.resolve():
                destination = destination.with_name(f"{destination.stem}_copy{destination.suffix}")
            self.events.put(("progress_mode", "determinate"))
            self.events.put(("detail", f"Copying MP4 with timestamp: {source.name}"))
            shutil.copy2(source, destination)
            self.events.put(("progress", 100.0))
            return True
        except OSError as exc:
            self.events.put(("log", f"MP4 copy failed: {exc}"))
            return False

    def convert_one(self, input_path: str, output_path: str, headers: dict[str, str] | None = None) -> bool:
        input_summary = self.probe_media_summary(input_path, headers)
        copy_video_map = self.analyze_copy_plan(input_summary)
        if copy_video_map:
            self.events.put(("log", f"Copy map selected: {copy_video_map}"))
        final_path = Path(output_path)
        staged_path = final_path.with_name(f"{final_path.stem}.part{final_path.suffix}")
        try:
            staged_path.unlink(missing_ok=True)
            self.events.put(("log", f"Temporary output: {staged_path}"))
            success = self._convert_one(
                input_path,
                str(staged_path),
                force_reencode=False,
                copy_video_map=copy_video_map,
                input_summary=input_summary,
                headers=headers,
            )
            if not success:
                return False
            os.replace(staged_path, final_path)
            self.events.put(("progress", 100.0))
            self.events.put(("log", "Playback validation passed. Final MP4 is ready."))
            return True
        except OSError as exc:
            self.events.put(("log", f"Final output creation failed: {exc}"))
            return False
        finally:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _convert_one(
        self,
        input_path: str,
        output_path: str,
        force_reencode: bool,
        copy_video_map: str | None = None,
        input_summary: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        command = [
            self.ffmpeg,
            "-hide_banner",
            "-stats_period",
            "1",
        ]
        if self.is_m3u8_input(input_path):
            command.extend(HLS_INPUT_OPTIONS)
        if self.is_url(input_path) and headers:
            header_text = self.ffmpeg_header_text(headers)
            if header_text:
                command += ["-headers", header_text]
                self.events.put(("log", f"Applying request headers: {', '.join(headers.keys())}"))
        command += [
            "-i",
            input_path,
        ]
        if force_reencode:
            video_map = self.analyze_copy_plan(input_summary) or self.pick_video_stream_for_reencode(input_path)
            if video_map:
                self.events.put(("log", f"Re-encode video map selected: {video_map}"))
                command += ["-map", video_map]
            else:
                command += ["-map", "0:V:0" if self.is_m3u8_input(input_path) else "0:v?"]
            command += ["-map", "0:a?"]
            command += [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-y",
            ]
        else:
            if copy_video_map:
                command += ["-map", copy_video_map]
            elif self.is_m3u8_input(input_path):
                command += ["-map", "0:V:0"]
            command += ["-map", "0:a?"]
            command += [
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                "-movflags",
                "+faststart",
            ]
            if not self.is_m3u8_input(input_path):
                command += ["-avoid_negative_ts", "make_zero"]
            command += ["-y"]
        command += ["-progress", "pipe:1", "-nostats", output_path]
        self.events.put(("log", "FFmpeg: " + subprocess.list2cmdline(command)))
        popen_args = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "universal_newlines": True,
        }
        if sys.platform == "win32":
            popen_args["encoding"] = "utf-8"
            popen_args["errors"] = "ignore"
            popen_args["creationflags"] = subprocess.CREATE_NO_WINDOW

        self.current_process = subprocess.Popen(command, **popen_args)
        assert self.current_process.stdout is not None
        duration = float(input_summary.get("duration") or 0.0) if input_summary else 0.0
        hls_segment_total = len(self.local_hls_segment_urls(input_path))
        opened_hls_segments: set[str] = set()
        reported_progress = 0.0
        last_state_log = 0.0
        retry_needed = False
        if duration > 0:
            self.events.put(("progress_mode", "determinate"))
            self.events.put(("log", f"Duration detected: {duration:.2f}s"))
        if hls_segment_total:
            self.events.put(("log", f"HLS playlist segments: {hls_segment_total}"))
        for raw_line in self.current_process.stdout:
            if not self.is_converting:
                break
            line = raw_line.strip()
            if not line:
                continue
            if hls_segment_total and "Opening '" in line:
                opening_match = re.search(r"Opening '([^']+)'", line)
                if opening_match:
                    opened_hls_segments.add(opening_match.group(1))
                    segment_count = min(len(opened_hls_segments), hls_segment_total)
                    segment_progress = min(97.0, segment_count / hls_segment_total * 97.0)
                    if segment_progress > reported_progress:
                        reported_progress = segment_progress
                        self.events.put(("progress", reported_progress))
                        self.events.put(
                            (
                                "detail",
                                f"Downloading HLS segments... {segment_count}/{hls_segment_total} ({reported_progress:.1f}%)",
                            )
                        )
            elif "Duration:" in line and duration == 0:
                match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
                if match:
                    h, m, s, ms = map(int, match.groups())
                    duration = h * 3600 + m * 60 + s + ms / 100
                    self.events.put(("progress_mode", "determinate"))
                    self.events.put(("log", f"Duration detected: {duration:.2f}s"))
            elif line.startswith("out_time_ms="):
                try:
                    seconds = int(line.split("=", 1)[1]) / 1_000_000
                    if duration > 0:
                        time_progress = min(97.0, seconds / duration * 97.0)
                        if time_progress > reported_progress:
                            reported_progress = time_progress
                            self.events.put(("progress", reported_progress))
                    if not hls_segment_total:
                        self.events.put(("detail", f"Processing... media time {seconds:.1f}s"))
                except ValueError:
                    pass
            elif line.startswith("speed="):
                now = time.time()
                if now - last_state_log >= 5:
                    self.events.put(("log", f"Status: {line}"))
                    last_state_log = now
            elif line.startswith("progress=end"):
                self.events.put(("progress", 98.0))
                self.events.put(("detail", "Finalizing MP4 and checking playback..."))
                self.events.put(("log", "FFmpeg completed stream processing."))
            elif any(
                token in line.lower()
                for token in ("error", "invalid", "failed", "denied", "not found", "403", "404", "could not find tag", "not muxable")
            ):
                if any(token in line.lower() for token in ("invalid", "not muxable", "could not find tag")):
                    retry_needed = True
                self.events.put(("log", f"FFmpeg error: {line}"))
            elif line.startswith("Stream #") and "video:" in line.lower() and "png" in line.lower():
                retry_needed = True
                self.events.put(("log", f"Source stream may need re-encode: {line}"))
            elif line.startswith(("Input #", "Output #", "Stream #")):
                self.events.put(("log", line))
        return_code = self.current_process.wait()
        self.current_process = None
        if self.is_converting and return_code == 0:
            output_summary = self.probe_media_summary(output_path)
            input_has_video = bool(input_summary and input_summary.get("has_video", False))
            input_max_area = int(input_summary.get("max_video_area", 0)) if input_summary else 0
            output_has_video = bool(output_summary and output_summary.get("has_video", False))
            output_max_area = int(output_summary.get("max_video_area", 0)) if output_summary else 0
            if input_has_video or self.is_m3u8_input(input_path):
                if not output_has_video or (input_max_area > 64 and output_max_area <= 64):
                    if not force_reencode:
                        self.events.put(("log", "Converted output has no usable video stream, retrying with re-encode."))
                        return self._convert_one(
                            input_path,
                            output_path,
                            force_reencode=True,
                            copy_video_map=None,
                            input_summary=input_summary,
                            headers=headers,
                        )
                    self.events.put(("log", "Converted output has no usable video stream."))
                    return False
            output_summary = self.remove_severely_truncated_audio(output_path, output_summary)
            if not output_summary:
                return False
            if not self.validate_output_playback(output_path, output_summary):
                if not force_reencode:
                    self.events.put(("log", "MP4 playback validation failed, retrying with H.264/AAC re-encode."))
                    return self._convert_one(
                        input_path,
                        output_path,
                        force_reencode=True,
                        copy_video_map=None,
                        input_summary=input_summary,
                        headers=headers,
                    )
                self.events.put(("log", "Re-encoded MP4 failed playback validation."))
                return False
        if self.is_converting and return_code != 0 and not force_reencode and retry_needed:
            self.events.put(("log", "Copy failed for MP4 muxing, retrying with H.264/AAC re-encode."))
            return self._convert_one(
                input_path,
                output_path,
                force_reencode=True,
                copy_video_map=None,
                input_summary=input_summary,
                headers=headers,
            )
        return self.is_converting and return_code == 0

    def probe_media_summary(self, input_path: str, headers: dict[str, str] | None = None) -> dict | None:
        ffprobe_path = self.get_ffprobe_path()
        if not ffprobe_path:
            return None
        try:
            command = [ffprobe_path, "-v", "error"]
            if self.is_m3u8_input(input_path):
                command.extend(HLS_INPUT_OPTIONS)
            if self.is_url(input_path) and headers:
                header_text = self.ffmpeg_header_text(headers)
                if header_text:
                    command += ["-headers", header_text]
            command += ["-print_format", "json", "-show_streams", "-show_format", input_path]
            completed = subprocess.run(
                command,
                **PROCESS_OPTIONS,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=20,
            )
            if completed.returncode != 0:
                return None
            return self.media_summary_from_info(json.loads(completed.stdout or "{}"))
        except Exception as exc:
            self.events.put(("log", f"Media probe failed: {exc}"))
            return None

    def media_summary_from_info(self, info: dict) -> dict:
        summary = {
            "streams": [],
            "has_video": False,
            "has_audio": False,
            "max_video_area": 0,
            "duration": 0.0,
            "format_name": "",
        }
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                summary["has_video"] = True
                width = int(stream.get("width") or 0)
                height = int(stream.get("height") or 0)
                area = width * height if width and height else 0
                if area > summary["max_video_area"]:
                    summary["max_video_area"] = area
            if stream.get("codec_type") == "audio":
                summary["has_audio"] = True
            summary["streams"].append(stream)
        format_info = info.get("format") or {}
        summary["format_name"] = str(format_info.get("format_name") or "")
        try:
            summary["duration"] = max(0.0, float(format_info.get("duration") or 0.0))
        except (TypeError, ValueError):
            summary["duration"] = 0.0
        return summary

    @staticmethod
    def longest_stream_duration(media_summary: dict | None, codec_type: str) -> float:
        durations = []
        for stream in (media_summary or {}).get("streams", []):
            if stream.get("codec_type") != codec_type:
                continue
            try:
                durations.append(max(0.0, float(stream.get("duration") or 0.0)))
            except (TypeError, ValueError):
                continue
        return max(durations, default=0.0)

    def remove_severely_truncated_audio(self, output_path: str, media_summary: dict | None) -> dict | None:
        if not media_summary or not media_summary.get("has_video") or not media_summary.get("has_audio"):
            return media_summary

        media_duration = float(media_summary.get("duration") or 0.0)
        audio_duration = self.longest_stream_duration(media_summary, "audio")
        if media_duration < 12.0:
            return media_summary
        if audio_duration >= media_duration * 0.25 or media_duration - audio_duration < 5.0:
            return media_summary

        self.events.put(
            (
                "log",
                f"Source audio is severely truncated ({audio_duration:.1f}s / {media_duration:.1f}s). "
                "Creating a playable video-only MP4.",
            )
        )
        source = Path(output_path)
        video_only_path = source.with_name(f"{source.stem}.video-only{source.suffix}")
        command = [
            self.ffmpeg,
            "-hide_banner",
            "-v",
            "warning",
            "-i",
            output_path,
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            "-movflags",
            "+faststart",
            "-y",
            str(video_only_path),
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if completed.returncode != 0:
                details = (completed.stdout or "").strip().splitlines()
                reason = details[-1] if details else f"FFmpeg exit code {completed.returncode}"
                self.events.put(("log", f"Video-only recovery failed: {reason}"))
                return None
            os.replace(video_only_path, source)
            recovered_summary = self.probe_media_summary(output_path)
            if not recovered_summary or not recovered_summary.get("has_video"):
                self.events.put(("log", "Video-only recovery produced no readable video stream."))
                return None
            self.events.put(("log", "Incomplete source audio removed. Video-only MP4 recovered."))
            return recovered_summary
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.events.put(("log", f"Video-only recovery failed: {exc}"))
            return None
        finally:
            try:
                video_only_path.unlink(missing_ok=True)
            except OSError:
                pass

    def stream_has_packets_at(self, output_path: str, selector: str, position: float) -> bool:
        ffprobe_path = self.get_ffprobe_path()
        if not ffprobe_path:
            return True
        command = [
            ffprobe_path,
            "-v",
            "error",
            "-read_intervals",
            f"{position:.3f}%+1.5",
            "-select_streams",
            selector,
            "-show_entries",
            "packet=pts_time",
            "-of",
            "csv=p=0",
            output_path,
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if completed.returncode != 0:
                return False
            packet_times = []
            for line in (completed.stdout or "").splitlines():
                try:
                    packet_times.append(float(line.strip().split(",", 1)[0]))
                except (TypeError, ValueError):
                    continue
            lower_bound = max(0.0, position - 5.0)
            upper_bound = position + 5.0
            return any(lower_bound <= packet_time <= upper_bound for packet_time in packet_times)
        except (OSError, subprocess.TimeoutExpired):
            return False

    def validate_output_playback(self, output_path: str, media_summary: dict | None) -> bool:
        if not media_summary or not (media_summary.get("has_video") or media_summary.get("has_audio")):
            self.events.put(("log", "Playback validation failed: no readable audio or video stream."))
            return False

        duration = float(media_summary.get("duration") or 0.0)
        positions = [0.0]
        if duration >= 12.0:
            positions.extend([duration / 2.0, max(0.0, duration - 4.0)])
        positions = list(dict.fromkeys(round(position, 3) for position in positions))
        null_output = "NUL" if sys.platform == "win32" else os.devnull

        for position in positions:
            selectors = []
            if media_summary.get("has_video"):
                selectors.append(("v:0", "video"))
            if media_summary.get("has_audio"):
                selectors.append(("a:0", "audio"))
            for selector, label in selectors:
                if not self.stream_has_packets_at(output_path, selector, position):
                    self.events.put(("log", f"Playback validation failed: no {label} packets near {position:.1f}s."))
                    return False

            command = [
                self.ffmpeg,
                "-hide_banner",
                "-v",
                "error",
                "-xerror",
                "-ss",
                f"{position:.3f}",
                "-i",
                output_path,
                "-t",
                "1.5",
            ]
            if media_summary.get("has_video"):
                command += ["-map", "0:v:0"]
            if media_summary.get("has_audio"):
                command += ["-map", "0:a:0"]
            command += ["-f", "null", null_output]
            try:
                completed = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.events.put(("log", f"Playback validation error at {position:.1f}s: {exc}"))
                return False
            if completed.returncode != 0:
                details = (completed.stdout or "").strip().splitlines()
                reason = details[-1] if details else f"FFmpeg exit code {completed.returncode}"
                self.events.put(("log", f"Playback validation failed at {position:.1f}s: {reason}"))
                return False

        self.events.put(("log", f"Playback validation succeeded at {len(positions)} sample point(s)."))
        return True

    def analyze_copy_plan(self, media_summary: dict | None) -> str | None:
        if not media_summary:
            return None
        best_index = None
        best_area = 64
        for stream in media_summary.get("streams", []):
            if stream.get("codec_type") != "video":
                continue
            idx = stream.get("index")
            if idx is None:
                continue
            codec = (stream.get("codec_name") or "").lower()
            if codec in {"png", "apng", "gif", "bmp"}:
                continue
            is_attached = bool(stream.get("disposition", {}).get("attached_pic"))
            if is_attached:
                continue
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            area = width * height if width and height else 0
            if area > best_area:
                best_area = area
                best_index = idx
        return f"0:{best_index}" if best_index is not None else None

    def pick_video_stream_for_reencode(self, input_path: str) -> str | None:
        ffprobe_path = self.get_ffprobe_path()
        if not ffprobe_path:
            return None
        try:
            command = [ffprobe_path, "-v", "error", "-print_format", "json", "-show_streams", input_path]
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=20,
            )
            if completed.returncode != 0:
                return None
            info = json.loads(completed.stdout or "{}")
            best_index = None
            best_area = 0
            for stream in info.get("streams", []):
                if stream.get("codec_type") != "video":
                    continue
                idx = stream.get("index")
                if idx is None:
                    continue
                codec_name = (stream.get("codec_name") or "").lower()
                is_attached = bool(stream.get("disposition", {}).get("attached_pic"))
                width = int(stream.get("width") or 0)
                height = int(stream.get("height") or 0)
                area = width * height if width and height else 0
                if codec_name in {"png", "apng", "gif", "bmp"} or is_attached:
                    continue
                if area > best_area:
                    best_area = area
                    best_index = idx
            if best_index is not None:
                return f"0:{best_index}"
        except Exception as exc:
            self.events.put(("log", f"Video probe failed: {exc}"))
        return None

    def get_ffprobe_path(self) -> str | None:
        ffprobe_path = None
        if self.ffmpeg:
            ffprobe_candidate = Path(self.ffmpeg).with_name("ffprobe")
            if ffprobe_candidate.exists():
                ffprobe_path = str(ffprobe_candidate)
            else:
                ffprobe_candidate = Path(self.ffmpeg).with_name("ffprobe.exe")
                if ffprobe_candidate.exists():
                    ffprobe_path = str(ffprobe_candidate)
        if ffprobe_path and Path(ffprobe_path).exists():
            return ffprobe_path
        return shutil.which("ffprobe")

    @staticmethod
    def is_m3u8_input(input_path: str) -> bool:
        if ModernM3U8Converter.is_url(input_path):
            return Path(urlparse(input_path).path).suffix.lower() == ".m3u8" or ".m3u8" in input_path.lower()
        return Path(input_path).suffix.lower() == ".m3u8"

    @staticmethod
    def local_hls_segment_urls(input_path: str) -> list[str]:
        if ModernM3U8Converter.is_url(input_path) or Path(input_path).suffix.lower() != ".m3u8":
            return []
        try:
            lines = Path(input_path).read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            return []
        return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]

    def generate_seg_urls(self, start_url: str, end_url: str) -> list[str]:
        start_parts = self.parse_seg_url_parts(start_url)
        end_parts = self.parse_seg_url_parts(end_url)
        if not start_parts or not end_parts:
            return []
        start_prefix, start_number, width, start_suffix = start_parts
        end_prefix, end_number, _, end_suffix = end_parts
        if start_prefix != end_prefix or start_suffix != end_suffix or end_number < start_number:
            return []
        return [f"{start_prefix}{number:0{width}d}{start_suffix}" for number in range(start_number, end_number + 1)]

    def download_seg_range_and_merge(self, item: str, output_path: str) -> bool:
        info = self.seg_range_info(item)
        headers = info.get("headers") or self.default_download_headers()
        workers = self.parse_parallel_workers(str(info.get("workers", self.range_workers_var.get())))
        start_url = info["start_url"]
        end_url = info["end_url"]
        if info.get("auto_discover"):
            self.events.put(("detail", "Finding last segment number..."))
            self.events.put(("log", f"Auto-discovering segment range from: {start_url}"))
            discovered = self.discover_segment_end_url(start_url, headers)
            if not discovered:
                self.events.put(("log", "Could not discover the last segment number."))
                return False
            end_url = discovered
            self.events.put(("log", f"Auto-discovered last segment: {Path(urlparse(end_url).path).name}"))
        urls = self.generate_seg_urls(start_url, end_url)
        if not urls:
            self.events.put(("log", "Invalid segment range. Start and end URL must share the same prefix and suffix."))
            return False
        temp_dir = tempfile.mkdtemp(prefix="streamforge_seg_")
        downloaded_paths: list[str | None] = [None] * len(urls)
        try:
            total = len(urls)
            self.events.put(("progress_mode", "determinate"))
            self.events.put(("log", f"Downloading {total} segment files with {workers} workers."))

            def download_one(index: int, url: str) -> tuple[int, str]:
                parsed = urlparse(url)
                filename = Path(parsed.path).name or f"segment_{index + 1:04d}.seg"
                local_path = str(Path(temp_dir) / filename)
                self.download_url_to_file(url, local_path, headers)
                return index, local_path

            completed_count = 0
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(download_one, index, url): (index, url) for index, url in enumerate(urls)}
                for future in as_completed(futures):
                    if not self.is_converting:
                        for pending in futures:
                            pending.cancel()
                        return False
                    future_index, future_url = futures[future]
                    try:
                        path_index, local_path = future.result()
                    except (HTTPError, URLError, TimeoutError, OSError) as exc:
                        self.events.put(("log", f"Segment download failed ({future_index + 1}/{total}): {future_url}"))
                        self.events.put(("log", f"Download error: {exc}"))
                        return False
                    downloaded_paths[path_index] = local_path
                    completed_count += 1
                    self.events.put(("progress", min(95.0, completed_count / total * 95.0)))
                    self.events.put(("detail", f"Downloading segments... {completed_count}/{total}"))
                    if completed_count == 1 or completed_count == total or completed_count % 25 == 0:
                        self.events.put(("log", f"Downloaded segment {completed_count}/{total}"))
            ordered_paths = [path for path in downloaded_paths if path]
            if len(ordered_paths) != total:
                self.events.put(("log", "Segment download incomplete. Merge skipped."))
                return False
            self.events.put(("detail", f"Merging {len(ordered_paths)} segment files into MP4..."))
            self.events.put(("log", f"Segment merge output: {output_path}"))
            success = self.merge_ts_files(ordered_paths, output_path)
            if success:
                self.events.put(("progress", 100.0))
            return success
        finally:
            try:
                shutil.rmtree(temp_dir)
            except OSError as exc:
                self.events.put(("log", f"Temporary segment cleanup failed: {exc}"))

    def discover_segment_end_url(self, start_url: str, headers: dict[str, str]) -> str | None:
        parts = self.parse_seg_url_parts(start_url)
        if not parts:
            return None
        prefix, start_number, width, suffix = parts

        def make_url(number: int) -> str:
            return f"{prefix}{number:0{width}d}{suffix}"

        if not self.segment_url_exists(make_url(start_number), headers):
            return None

        max_probe = start_number + 10000
        low = start_number
        high = start_number + 1
        while high <= max_probe and self.is_converting and self.segment_url_exists(make_url(high), headers):
            low = high
            high = min(max_probe + 1, high * 2 - start_number + 1)
            self.events.put(("detail", f"Finding last segment... checked {low:0{width}d}"))

        if high > max_probe:
            self.events.put(("log", f"Auto-discovery limit reached at {max_probe:0{width}d}."))
            return make_url(low)

        left = low + 1
        right = high - 1
        last_existing = low
        while left <= right and self.is_converting:
            mid = (left + right) // 2
            if self.segment_url_exists(make_url(mid), headers):
                last_existing = mid
                left = mid + 1
            else:
                right = mid - 1
        return make_url(last_existing)

    @staticmethod
    def segment_url_exists(url: str, headers: dict[str, str]) -> bool:
        try:
            request = Request(url, headers=headers, method="HEAD")
            with urlopen(request, timeout=12) as response:
                return 200 <= response.status < 400
        except HTTPError as exc:
            if exc.code in {403, 405}:
                try:
                    probe_headers = dict(headers)
                    probe_headers["Range"] = "bytes=0-0"
                    request = Request(url, headers=probe_headers)
                    with urlopen(request, timeout=12) as response:
                        return 200 <= response.status < 400
                except (HTTPError, URLError, TimeoutError, OSError):
                    return False
            return False
        except (URLError, TimeoutError, OSError):
            return False

    @staticmethod
    def download_url_to_file(url: str, output_path: str, headers: dict[str, str] | None = None) -> None:
        request = Request(
            url,
            headers=headers or ModernM3U8Converter.default_download_headers(),
        )
        with urlopen(request, timeout=30) as response, open(output_path, "wb") as output_file:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                output_file.write(chunk)

    def merge_ts_files(self, input_paths: list[str], output_path: str) -> bool:
        list_file_path = ""
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as list_file:
                list_file_path = list_file.name
                for input_path in input_paths:
                    escaped = input_path.replace("\\", "/").replace("'", "'\\''")
                    list_file.write(f"file '{escaped}'\n")
            command = [
                self.ffmpeg,
                "-hide_banner",
                "-stats_period",
                "1",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file_path,
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                "-y",
                "-progress",
                "pipe:1",
                "-nostats",
                output_path,
            ]
            return self.run_ffmpeg_command(command)
        finally:
            if list_file_path:
                try:
                    os.remove(list_file_path)
                except OSError:
                    pass

    def run_ffmpeg_command(self, command: list[str]) -> bool:
        self.events.put(("log", "FFmpeg: " + subprocess.list2cmdline(command)))
        popen_args = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "universal_newlines": True,
        }
        if sys.platform == "win32":
            popen_args["encoding"] = "utf-8"
            popen_args["errors"] = "ignore"
            popen_args["creationflags"] = subprocess.CREATE_NO_WINDOW

        self.current_process = subprocess.Popen(command, **popen_args)
        assert self.current_process.stdout is not None
        last_state_log = 0.0
        for raw_line in self.current_process.stdout:
            if not self.is_converting:
                break
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("out_time_ms="):
                try:
                    seconds = int(line.split("=", 1)[1]) / 1_000_000
                    self.events.put(("detail", f"Processing... media time {seconds:.1f}s"))
                except ValueError:
                    pass
            elif line.startswith("speed="):
                now = time.time()
                if now - last_state_log >= 5:
                    self.events.put(("log", f"Status: {line}"))
                    last_state_log = now
            elif line.startswith("progress=end"):
                self.events.put(("log", "FFmpeg completed stream processing."))
            elif any(token in line.lower() for token in ("error", "invalid", "failed", "denied", "not found", "403", "404")):
                self.events.put(("log", f"FFmpeg error: {line}"))
            elif line.startswith(("Input #", "Output #", "Stream #")):
                self.events.put(("log", line))
        return_code = self.current_process.wait()
        self.current_process = None
        return self.is_converting and return_code == 0

    def process_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.write_log(str(value))
                elif kind == "status":
                    self.status_var.set(str(value))
                elif kind == "detail":
                    self.detail_var.set(str(value))
                elif kind == "progress_mode":
                    self.current_progress.stop()
                    self.current_progress.config(mode=str(value))
                    if hasattr(self, "youtube_progress"):
                        self.youtube_progress.stop()
                        self.youtube_progress.config(mode=str(value))
                elif kind == "progress":
                    if self.current_progress["mode"] != "determinate":
                        self.current_progress.stop()
                        self.current_progress.config(mode="determinate")
                    self.current_progress["value"] = float(value)
                    if hasattr(self, "youtube_progress"):
                        if self.youtube_progress["mode"] != "determinate":
                            self.youtube_progress.stop()
                            self.youtube_progress.config(mode="determinate")
                        self.youtube_progress["value"] = float(value)
                elif kind == "message":
                    messagebox.showinfo("Complete", str(value))
                elif kind == "youtube_meta":
                    title, meta = value
                    self.youtube_title_var.set(str(title))
                    self.youtube_meta_var.set(str(meta))
                    self.status_var.set("Ready")
                elif kind == "finish":
                    self.finish_ui()
        except queue.Empty:
            pass

        if self.is_converting:
            elapsed = int(time.time() - self.start_time)
            self.elapsed_var.set(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        self.after(100, self.process_events)

    def finish_ui(self) -> None:
        self.is_converting = False
        self.current_progress.stop()
        self.current_progress.config(mode="determinate")
        self.current_progress["value"] = 100
        if hasattr(self, "youtube_progress"):
            self.youtube_progress.stop()
            self.youtube_progress.config(mode="determinate")
            self.youtube_progress["value"] = 100
        self.status_var.set("Done")
        self.convert_button.config(state="normal")
        self.stop_button.config(state="disabled")
        if hasattr(self, "youtube_download_button"):
            self.youtube_download_button.config(state="normal")
        if hasattr(self, "youtube_stop_button"):
            self.youtube_stop_button.config(state="disabled")

    def write_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def open_output_folder(self) -> None:
        if self.output_directory and Path(self.output_directory).exists():
            os.startfile(self.output_directory)


if __name__ == "__main__":
    app = ModernM3U8Converter()
    app.write_log("StreamForge Converter started.")
    app.mainloop()
