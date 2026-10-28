# -*- coding: utf-8 -*-
"""
ui.colors
ANSI and colorama terminal colors and formatting.
"""

import colorama
from colorama import Fore, Style, Back

colorama.init(autoreset=True)

# ANSI color codes for terminal output
WHITE = "[1;97m"
GREEN = "[1;92m"
RED = "[1;91m"
DARK_GREEN = "[1;32m"
LIGHT_GRAY = "[1;37m"
CYAN = "[1;96m"
YELLOW = "[1;93m"
BLUE = "[1;94m"
MAGENTA = "[1;95m"
ORANGE = "[38;5;208m"
GOLD = "[38;5;220m"
VIOLET = "[38;5;141m"
TOXIC = "[38;2;170;200;0m"
PURPLE = "[38;2;150;80;200m"
RESET = "[0m"
BOLD = "[1m"

# Reusable UI elements
LINE = f"{CYAN}•{'?' * 47}•"
EKL = f"{CYAN}:{WHITE}"

# Format a menu option number with colored brackets
def opt(num):
    return f"{GREEN}[{RED}{str(num).zfill(2)}{GREEN}]"

__all__ = [
    "WHITE", "GREEN", "RED", "DARK_GREEN", "LIGHT_GRAY", "CYAN", "YELLOW",
    "BLUE", "MAGENTA", "ORANGE", "GOLD", "VIOLET", "TOXIC", "PURPLE",
    "RESET", "BOLD", "LINE", "EKL", "opt"
]
