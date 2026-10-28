# -*- coding: utf-8 -*-
import sys
import threading
from datetime import datetime
from colorama import Fore, Style
from ui.colors import GREEN, RED, WHITE, YELLOW, ORANGE, CYAN, RESET

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class RegistrationCounter:
    def __init__(self):
        self.lock = threading.Lock()
        self.success_count = 0
        self.failed_count = 0
        self.error_count = 0
        self.total = 0

    def update(self, status: str, number: str = '', message: str = '', color: str = ''):
        with self.lock:
            self.total += 1
            norm_status = (status or '').lower().strip()
            if norm_status in ('success', 'ok', 'done'):
                self.success_count += 1
                tag_color = GREEN
                tag_text = 'SUCCESS'
            elif norm_status in ('failed', 'fail', 'checkpoint'):
                self.failed_count += 1
                tag_color = YELLOW
                tag_text = 'FAILED'
            else:
                self.error_count += 1
                tag_color = RED if not color else color
                tag_text = 'ERROR'

            ts = datetime.now().strftime('%H:%M:%S')
            stat_line = f"{CYAN}[{ts}]{RESET} [{Fore.GREEN}OK: {self.success_count}{RESET} / {Fore.YELLOW}Fail: {self.failed_count}{RESET} / {Fore.RED}Err: {self.error_count}{RESET}]"
            num_tag = f"{Fore.WHITE}[{number}]{RESET} " if number else ""
            msg_color = color or tag_color
            out_str = f"{stat_line} {tag_color}[{tag_text}]{RESET} {num_tag}{msg_color}{message}{RESET}"
            try:
                print(out_str)
            except UnicodeEncodeError:
                safe_str = out_str.encode('ascii', errors='replace').decode('ascii')
                print(safe_str)
            sys.stdout.flush()

    def get_stats(self):
        with self.lock:
            return {
                'success': self.success_count,
                'failed': self.failed_count,
                'error': self.error_count,
                'total': self.total,
            }

Counter = RegistrationCounter
