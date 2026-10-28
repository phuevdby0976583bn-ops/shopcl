# -*- coding: utf-8 -*-
"""
ui.theme
Centralized UI theme constants, color palette, and font definitions for GUI.
"""


class AppTheme:
    BG_DARK = "#12131c"
    BG_CARD = "#1c1d2d"
    BG_CARD_LIGHT = "#24263a"
    BG_INPUT = "#292a40"
    BORDER = "#3b3d5c"
    ACCENT = "#00adb5"
    ACCENT_HOVER = "#00c4cc"
    TEXT_MAIN = "#f8fafc"
    TEXT_MUTED = "#94a3b8"
    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    DANGER = "#ef4444"
    ERROR = "#ef4444"
    INFO = "#38bdf8"
    FONT_TITLE = ("Segoe UI", 12, "bold")
    FONT_HEADER = ("Segoe UI", 10, "bold")
    FONT_BODY = ("Segoe UI", 9)
    FONT_BODY_BOLD = ("Segoe UI", 9, "bold")
    FONT_SMALL = ("Segoe UI", 8)
    FONT_SMALL_BOLD = ("Segoe UI", 8, "bold")
    FONT_MINI = ("Segoe UI", 8)
    FONT_MINI_BOLD = ("Segoe UI", 8, "bold")
    FONT_CODE = ("Consolas", 9)


__all__ = ["AppTheme"]