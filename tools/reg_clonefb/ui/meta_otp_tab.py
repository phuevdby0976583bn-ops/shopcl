# -*- coding: utf-8 -*-
"""
ui.meta_otp_tab - Dedicated GUI Tab for Meta AI Auto OTP Automation.
Cleanly decoupled as a mixin for RegFacebookGUI.
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.meta_otp import (
    MetaOtpService,
    read_numbers,
    clean_and_validate,
    USER_AGENT_PROFILES,
)
from ui.theme import AppTheme


class MetaOtpTabMixin:
    """Mixin class providing the full Meta AI Auto OTP GUI tab implementation."""

    def build_meta_otp_tab(self, parent_frame: tk.Frame):
        """Construct the entire Meta AI Auto OTP tab UI."""
        from app_gui import AppTheme

        self.meta_otp_service = MetaOtpService(
            event_callback=self._meta_otp_service_callback
        )
        self._meta_otp_row_items = {}
        self._meta_otp_success_phones = []
        self._meta_otp_failed_phones = []

        container = tk.Frame(parent_frame, bg=AppTheme.BG_DARK)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # PanedWindow: Trái (Cấu hình & Nhập SĐT 40%) - Phải (Giám sát & Bảng 60%)
        paned = tk.PanedWindow(container, orient=tk.HORIZONTAL, bg=AppTheme.BG_DARK, bd=0, sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)
        right_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)

        paned.add(left_frame, minsize=420)
        paned.add(right_frame, minsize=540)

        self._build_meta_otp_left_panel(left_frame, AppTheme)
        self._build_meta_otp_right_panel(right_frame, AppTheme)

    def _build_meta_otp_left_panel(self, parent: tk.Frame, AppTheme):
        """Construct the left configuration and number input panel."""
        # Card 1: Danh sách số điện thoại
        card_input = tk.LabelFrame(
            parent,
            text=" 📱 1. Danh Sách Số Điện Thoại Nhận OTP ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief=tk.SOLID
        )
        card_input.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 6))

        # Thanh công cụ nhập liệu
        tools_row = tk.Frame(card_input, bg=AppTheme.BG_CARD)
        tools_row.pack(fill=tk.X, padx=6, pady=(4, 2))

        btn_import = tk.Button(
            tools_row,
            text="📁 Chọn File (.txt/.csv/.xlsx)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.ACCENT,
            relief=tk.FLAT,
            command=self._import_meta_otp_file
        )
        btn_import.pack(side=tk.LEFT, padx=(0, 4))

        btn_paste = tk.Button(
            tools_row,
            text="📋 Dán Clipboard",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.ACCENT,
            relief=tk.FLAT,
            command=self._paste_meta_otp_clipboard
        )
        btn_paste.pack(side=tk.LEFT, padx=(0, 4))

        btn_clear = tk.Button(
            tools_row,
            text="🧹 Xóa SĐT",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.DANGER,
            activebackground=AppTheme.DANGER,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            command=self._clear_meta_otp_input
        )
        btn_clear.pack(side=tk.LEFT)

        self.lbl_meta_otp_count = tk.Label(
            tools_row,
            text="Tổng: 0 số",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS
        )
        self.lbl_meta_otp_count.pack(side=tk.RIGHT)

        # Khung văn bản nhập SĐT
        self.txt_meta_otp_numbers = scrolledtext.ScrolledText(
            card_input,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.ACCENT,
            font=AppTheme.FONT_CODE,
            bd=1,
            relief=tk.SOLID,
            height=9
        )
        self.txt_meta_otp_numbers.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.txt_meta_otp_numbers.bind("<KeyRelease>", self._on_meta_otp_text_change)
        self.txt_meta_otp_numbers.bind("<FocusOut>", self._on_meta_otp_text_change)

        # Card 2: Cấu hình gửi OTP
        card_settings = tk.LabelFrame(
            parent,
            text=" ⚙️ 2. Cài Đặt Gửi OTP & Hệ Thống ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief=tk.SOLID
        )
        card_settings.pack(fill=tk.X, padx=4, pady=(0, 6))

        # Phương thức gửi
        mode_row = tk.Frame(card_settings, bg=AppTheme.BG_CARD)
        mode_row.pack(fill=tk.X, padx=6, pady=3)
        tk.Label(mode_row, text="Phương thức:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)

        self.var_meta_otp_mode = tk.StringVar(value="api")
        rb_api = tk.Radiobutton(
            mode_row,
            text="⚡ API (Siêu tốc - Fast HTTP)",
            value="api",
            variable=self.var_meta_otp_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD,
            command=self._on_meta_otp_mode_change
        )
        rb_api.pack(side=tk.LEFT, padx=(8, 4))

        rb_sel = tk.Radiobutton(
            mode_row,
            text="🌐 Selenium (Trình duyệt)",
            value="selenium",
            variable=self.var_meta_otp_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY,
            command=self._on_meta_otp_mode_change
        )
        rb_sel.pack(side=tk.LEFT)

        # Cài đặt trình duyệt (Khi chọn Selenium)
        self.frame_meta_otp_browser = tk.Frame(card_settings, bg=AppTheme.BG_CARD)
        self.frame_meta_otp_browser.pack(fill=tk.X, padx=6, pady=2)

        tk.Label(self.frame_meta_otp_browser, text="Trình duyệt:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT)
        self.cb_meta_otp_browser = ttk.Combobox(
            self.frame_meta_otp_browser,
            values=["chrome", "edge", "brave", "firefox", "opera"],
            width=10,
            state="readonly"
        )
        self.cb_meta_otp_browser.set("chrome")
        self.cb_meta_otp_browser.pack(side=tk.LEFT, padx=6)

        self.var_meta_otp_headless = tk.BooleanVar(value=True)
        cb_head = tk.Checkbutton(
            self.frame_meta_otp_browser,
            text="Ẩn trình duyệt (Headless)",
            variable=self.var_meta_otp_headless,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL
        )
        cb_head.pack(side=tk.LEFT, padx=6)
        self.frame_meta_otp_browser.pack_forget()  # Ẩn mặc định khi chọn API

        # Luồng & Resend
        params_row = tk.Frame(card_settings, bg=AppTheme.BG_CARD)
        params_row.pack(fill=tk.X, padx=6, pady=3)

        tk.Label(params_row, text="Số luồng:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.spn_meta_otp_threads = tk.Spinbox(params_row, from_=1, to=100, width=5, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN)
        self.spn_meta_otp_threads.delete(0, tk.END)
        self.spn_meta_otp_threads.insert(0, "10")
        self.spn_meta_otp_threads.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(params_row, text="Resend OTP:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.spn_meta_otp_resend = tk.Spinbox(params_row, from_=0, to=10, width=4, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN)
        self.spn_meta_otp_resend.delete(0, tk.END)
        self.spn_meta_otp_resend.insert(0, "1")
        self.spn_meta_otp_resend.pack(side=tk.LEFT, padx=(4, 6))
        tk.Label(params_row, text="(lần gửi lại)", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT)

        # User-Agent Profile
        ua_row = tk.Frame(card_settings, bg=AppTheme.BG_CARD)
        ua_row.pack(fill=tk.X, padx=6, pady=3)
        tk.Label(ua_row, text="User-Agent:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_meta_otp_ua = ttk.Combobox(
            ua_row,
            values=list(USER_AGENT_PROFILES.values()),
            width=32,
            state="readonly"
        )
        self.cb_meta_otp_ua.current(0)
        self.cb_meta_otp_ua.pack(side=tk.LEFT, padx=6)

        # Nguồn Proxy
        proxy_row = tk.Frame(card_settings, bg=AppTheme.BG_CARD)
        proxy_row.pack(fill=tk.X, padx=6, pady=3)
        tk.Label(proxy_row, text="Proxy:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_meta_otp_proxy = ttk.Combobox(
            proxy_row,
            values=[
                "🎲 Kế thừa Proxy từ Cài Đặt Tool (Kiot/Free/List)",
                "⚡ Mạng Direct (Không dùng proxy)",
                "📁 Danh sách Proxy (proxy.txt)",
                "✍️ Nhập Proxy tùy chỉnh..."
            ],
            width=35,
            state="readonly"
        )
        self.cb_meta_otp_proxy.current(0)
        self.cb_meta_otp_proxy.pack(side=tk.LEFT, padx=6)
        self.cb_meta_otp_proxy.bind("<<ComboboxSelected>>", self._on_meta_otp_proxy_source_change)

        # Ô nhập Proxy tùy chỉnh (ẩn mặc định)
        self.frame_meta_otp_custom_proxy = tk.Frame(card_settings, bg=AppTheme.BG_CARD)
        self.frame_meta_otp_custom_proxy.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(self.frame_meta_otp_custom_proxy, text="Proxy URL:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT)
        self.entry_meta_otp_custom_proxy = tk.Entry(self.frame_meta_otp_custom_proxy, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, font=AppTheme.FONT_CODE)
        self.entry_meta_otp_custom_proxy.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.frame_meta_otp_custom_proxy.pack_forget()

        # Action Buttons Control Bar
        action_row = tk.Frame(parent, bg=AppTheme.BG_DARK)
        action_row.pack(fill=tk.X, padx=4, pady=6)

        self.btn_meta_otp_start = tk.Button(
            action_row,
            text="▶️ BẮT ĐẦU GỬI OTP",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.ACCENT,
            fg="#000000",
            activebackground=AppTheme.ACCENT_HOVER,
            relief=tk.FLAT,
            height=2,
            command=self.on_meta_otp_start
        )
        self.btn_meta_otp_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_meta_otp_stop = tk.Button(
            action_row,
            text="⏹️ DỪNG TIẾN TRÌNH",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BORDER,
            fg="#ffffff",
            activebackground=AppTheme.DANGER,
            state=tk.DISABLED,
            relief=tk.FLAT,
            height=2,
            command=self.on_meta_otp_stop
        )
        self.btn_meta_otp_stop.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def _build_meta_otp_right_panel(self, parent: tk.Frame, AppTheme):
        """Construct the right real-time monitoring, result table, and live log panel."""
        # Top Metrics Cards Frame
        kpi_frame = tk.Frame(parent, bg=AppTheme.BG_DARK)
        kpi_frame.pack(fill=tk.X, padx=4, pady=(0, 6))

        def _make_metric_box(p, title, init_val, color):
            box = tk.Frame(p, bg=AppTheme.BG_CARD, bd=1, relief=tk.SOLID)
            box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
            lbl_t = tk.Label(box, text=title, font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED)
            lbl_t.pack(anchor="w", padx=6, pady=(4, 0))
            lbl_v = tk.Label(box, text=init_val, font=AppTheme.FONT_TITLE, bg=AppTheme.BG_CARD, fg=color)
            lbl_v.pack(anchor="w", padx=6, pady=(0, 4))
            return lbl_v

        self.lbl_meta_otp_stat_total = _make_metric_box(kpi_frame, "📊 Tổng SĐT", "0", AppTheme.TEXT_MAIN)
        self.lbl_meta_otp_stat_success = _make_metric_box(kpi_frame, "✅ Thành Công", "0", AppTheme.SUCCESS)
        self.lbl_meta_otp_stat_failed = _make_metric_box(kpi_frame, "❌ Thất Bại", "0", AppTheme.DANGER)
        self.lbl_meta_otp_stat_running = _make_metric_box(kpi_frame, "🔄 Đang Xử Lý", "0", AppTheme.INFO)

        # Quick Actions Bar for Table
        table_bar = tk.Frame(parent, bg=AppTheme.BG_DARK)
        table_bar.pack(fill=tk.X, padx=4, pady=(2, 4))

        tk.Button(
            table_bar,
            text="💾 Xuất DS Thành Công",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            relief=tk.FLAT,
            command=self.meta_otp_export_success
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            table_bar,
            text="💾 Xuất DS Thất Bại",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.DANGER,
            relief=tk.FLAT,
            command=self.meta_otp_export_failed
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            table_bar,
            text="📋 Sao Chép Số Thành Công",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            relief=tk.FLAT,
            command=self.meta_otp_copy_success
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            table_bar,
            text="🧹 Xóa Bảng",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
            relief=tk.FLAT,
            command=self.meta_otp_clear_results
        ).pack(side=tk.RIGHT)

        # Result Treeview Table
        table_frame = tk.Frame(parent, bg=AppTheme.BG_DARK)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        columns = ("stt", "phone", "mode", "worker", "status", "proxy", "time")
        self.tree_meta_otp = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="extended"
        )
        self.tree_meta_otp.heading("stt", text="STT")
        self.tree_meta_otp.heading("phone", text="Số Điện Thoại")
        self.tree_meta_otp.heading("mode", text="Chế Độ")
        self.tree_meta_otp.heading("worker", text="Luồng")
        self.tree_meta_otp.heading("status", text="Trạng Thái Gửi OTP")
        self.tree_meta_otp.heading("proxy", text="Proxy")
        self.tree_meta_otp.heading("time", text="Thời Gian")

        self.tree_meta_otp.column("stt", width=45, anchor="center")
        self.tree_meta_otp.column("phone", width=140, anchor="w")
        self.tree_meta_otp.column("mode", width=70, anchor="center")
        self.tree_meta_otp.column("worker", width=65, anchor="center")
        self.tree_meta_otp.column("status", width=240, anchor="w")
        self.tree_meta_otp.column("proxy", width=130, anchor="w")
        self.tree_meta_otp.column("time", width=80, anchor="center")

        self.tree_meta_otp.tag_configure("success", foreground=AppTheme.SUCCESS)
        self.tree_meta_otp.tag_configure("failed", foreground=AppTheme.DANGER)
        self.tree_meta_otp.tag_configure("running", foreground=AppTheme.INFO)
        self.tree_meta_otp.tag_configure("error", foreground=AppTheme.WARNING)

        tree_scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree_meta_otp.yview)
        self.tree_meta_otp.configure(yscrollcommand=tree_scroll_y.set)
        self.tree_meta_otp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Live Activity Console Log
        log_frame = tk.LabelFrame(
            parent,
            text=" 📜 Nhật Ký Hoạt Động (Live Activity Log) ",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
            bd=1,
            relief=tk.SOLID
        )
        log_frame.pack(fill=tk.BOTH, expand=False, padx=4, pady=(4, 0))

        self.txt_meta_otp_log = scrolledtext.ScrolledText(
            log_frame,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            height=6,
            bd=0
        )
        self.txt_meta_otp_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.txt_meta_otp_log.tag_configure("info", foreground=AppTheme.INFO)
        self.txt_meta_otp_log.tag_configure("success", foreground=AppTheme.SUCCESS)
        self.txt_meta_otp_log.tag_configure("warning", foreground=AppTheme.WARNING)
        self.txt_meta_otp_log.tag_configure("error", foreground=AppTheme.DANGER)

    def _meta_otp_service_callback(self, event_type: str, data: Dict[str, Any]):
        """Callback from MetaOtpService in background threads; routes to GUI event queue."""
        if hasattr(self, "event_queue"):
            self.event_queue.put((f"meta_otp_{event_type}", data))

    def _on_meta_otp_text_change(self, event=None):
        """Update loaded phone numbers counter based on text area input."""
        txt = self.txt_meta_otp_numbers.get("1.0", tk.END).strip()
        lines = [x.strip() for x in txt.splitlines() if x.strip()]
        valid_cnt = sum(1 for x in lines if clean_and_validate(x))
        self.lbl_meta_otp_count.config(text=f"Tổng: {valid_cnt} số")

    def _import_meta_otp_file(self):
        """Open file dialog to load numbers from .txt, .csv, .xlsx."""
        path = filedialog.askopenfilename(
            title="Chọn file chứa danh sách số điện thoại",
            filetypes=[
                ("File danh sách SĐT", "*.txt *.csv *.xlsx *.xls"),
                ("Text File (*.txt)", "*.txt"),
                ("CSV File (*.csv)", "*.csv"),
                ("Excel File (*.xlsx)", "*.xlsx"),
                ("Tất cả tập tin", "*.*")
            ]
        )
        if not path:
            return

        numbers = read_numbers(path)
        if not numbers:
            messagebox.showwarning("Thông báo", f"Không tìm thấy số điện thoại hợp lệ trong file: {os.path.basename(path)}")
            return

        self.txt_meta_otp_numbers.delete("1.0", tk.END)
        self.txt_meta_otp_numbers.insert("1.0", "\n".join(numbers))
        self._on_meta_otp_text_change()
        self.meta_otp_log(f"Đã nạp thành công {len(numbers)} SĐT từ {os.path.basename(path)}", "success")

    def _paste_meta_otp_clipboard(self):
        """Paste phone numbers from clipboard."""
        try:
            cb_text = self.root.clipboard_get()
            if not cb_text:
                return
            nums = read_numbers(cb_text)
            if nums:
                current_txt = self.txt_meta_otp_numbers.get("1.0", tk.END).strip()
                new_txt = (current_txt + "\n" + "\n".join(nums)).strip() if current_txt else "\n".join(nums)
                self.txt_meta_otp_numbers.delete("1.0", tk.END)
                self.txt_meta_otp_numbers.insert("1.0", new_txt)
                self._on_meta_otp_text_change()
                self.meta_otp_log(f"Đã dán thêm {len(nums)} SĐT từ Clipboard", "info")
            else:
                messagebox.showinfo("Thông báo", "Không tìm thấy số điện thoại hợp lệ trong Clipboard!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đọc Clipboard: {e}")

    def _clear_meta_otp_input(self):
        """Clear phone numbers input area."""
        self.txt_meta_otp_numbers.delete("1.0", tk.END)
        self._on_meta_otp_text_change()

    def _on_meta_otp_mode_change(self):
        """Show or hide browser settings when toggling API vs Selenium."""
        m = self.var_meta_otp_mode.get()
        if m == "selenium":
            self.frame_meta_otp_browser.pack(fill=tk.X, padx=6, pady=2, after=self.spn_meta_otp_threads.master)
        else:
            self.frame_meta_otp_browser.pack_forget()

    def _on_meta_otp_proxy_source_change(self, event=None):
        """Show or hide custom proxy entry."""
        choice = self.cb_meta_otp_proxy.get()
        if "Nhập Proxy" in choice:
            self.frame_meta_otp_custom_proxy.pack(fill=tk.X, padx=6, pady=2, after=self.cb_meta_otp_proxy.master)
        else:
            self.frame_meta_otp_custom_proxy.pack_forget()

    def on_meta_otp_start(self):
        """Start Meta AI Auto OTP batch thread."""
        from app_gui import AppTheme

        raw_txt = self.txt_meta_otp_numbers.get("1.0", tk.END).strip()
        lines = [x.strip() for x in raw_txt.splitlines() if x.strip()]
        valid_numbers = [clean_and_validate(x) for x in lines if clean_and_validate(x)]

        if not valid_numbers:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập hoặc nạp ít nhất 1 số điện thoại hợp lệ để gửi OTP!")
            return

        try:
            threads = int(self.spn_meta_otp_threads.get())
        except Exception:
            threads = 10

        try:
            resend = int(self.spn_meta_otp_resend.get())
        except Exception:
            resend = 1

        mode = self.var_meta_otp_mode.get()
        browser = self.cb_meta_otp_browser.get() if hasattr(self, "cb_meta_otp_browser") else "chrome"
        headless = self.var_meta_otp_headless.get() if hasattr(self, "var_meta_otp_headless") else True

        # Map User Agent profile
        ua_label = self.cb_meta_otp_ua.get()
        ua_prof = "random"
        for k, v in USER_AGENT_PROFILES.items():
            if v == ua_label:
                ua_prof = k
                break

        # Map Proxy
        proxy_choice = self.cb_meta_otp_proxy.get()
        custom_proxies = None
        proxy_provider = "none"

        if "Kế thừa" in proxy_choice:
            tool_provider = self.get_selected_proxy_provider() if hasattr(self, "get_selected_proxy_provider") else "none"
            proxy_provider = tool_provider
            if tool_provider == "proxyvn" and hasattr(self, "get_proxyvn_keys"):
                pvn_keys = self.get_proxyvn_keys()
                if pvn_keys:
                    from core.proxy_manager import ProxyVNClient
                    custom_proxies = []
                    for k in pvn_keys:
                        inf = ProxyVNClient(k).get_current_proxy()
                        if inf.get("http"):
                            custom_proxies.append(inf["http"])
            elif tool_provider in ("kiotproxy", "kiotproxy_current") and hasattr(self, "get_kiotproxy_keys"):
                kiot_keys = self.get_kiotproxy_keys()
                if kiot_keys:
                    from core.proxy_manager import KiotProxyClient
                    custom_proxies = []
                    for k in kiot_keys:
                        inf = KiotProxyClient(k).get_current_proxy()
                        if inf.get("http"):
                            custom_proxies.append(inf["http"])
        elif "Danh sách Proxy" in proxy_choice:
            proxy_provider = "proxy_list"
        elif "Nhập Proxy" in proxy_choice:
            custom_p = self.entry_meta_otp_custom_proxy.get().strip()
            if custom_p:
                custom_proxies = [custom_p]
                proxy_provider = "custom"
        else:
            proxy_provider = "none"

        self.btn_meta_otp_start.config(state=tk.DISABLED, bg=AppTheme.BORDER)
        self.btn_meta_otp_stop.config(state=tk.NORMAL, bg=AppTheme.DANGER)

        self._meta_otp_row_items.clear()
        self._meta_otp_success_phones.clear()
        self._meta_otp_failed_phones.clear()

        # Nạp các hàng ban đầu vào bảng
        for itm in self.tree_meta_otp.get_children():
            self.tree_meta_otp.delete(itm)

        for idx, num in enumerate(valid_numbers, 1):
            row_id = self.tree_meta_otp.insert(
                "",
                tk.END,
                values=(idx, num, mode.upper(), "-", "⏳ Đang chờ lượt...", "-", "-"),
                tags=("running",)
            )
            self._meta_otp_row_items[num] = row_id

        self.meta_otp_log(f"BẮT ĐẦU: Gửi OTP cho {len(valid_numbers)} SĐT | {threads} Luồng | Chế độ: {mode.upper()} | Resend: {resend}", "info")

        def run_thread():
            try:
                self.meta_otp_service.run_batch(
                    numbers=valid_numbers,
                    mode=mode,
                    threads=threads,
                    user_agent_profile=ua_prof,
                    resend_count=resend,
                    browser=browser,
                    headless=headless,
                    proxy_provider=proxy_provider,
                    custom_proxies=custom_proxies
                )
            except Exception as e:
                self.meta_otp_log(f"Lỗi tiến trình Meta OTP: {e}", "error")
            finally:
                if hasattr(self, "event_queue"):
                    self.event_queue.put(("meta_otp_done", {}))

        t = threading.Thread(target=run_thread, daemon=True)
        t.start()

    def on_meta_otp_stop(self):
        """Signal stop to running Meta OTP threads."""
        if hasattr(self, "meta_otp_service"):
            self.meta_otp_service.stop()
        self.meta_otp_log("Đã gửi yêu cầu dừng tới các luồng Meta OTP...", "warning")

    def meta_otp_log(self, message: str, tag: str = "info"):
        """Append log message with timestamp to Live Activity Log."""
        if not hasattr(self, "txt_meta_otp_log") or not self.txt_meta_otp_log.winfo_exists():
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_meta_otp_log.insert(tk.END, f"[{ts}] {message}\n", tag)
        if not hasattr(self, "_meta_otp_line_count"):
            self._meta_otp_line_count = 0
        self._meta_otp_line_count += 1
        if self._meta_otp_line_count > 1000:
            try:
                self.txt_meta_otp_log.delete("1.0", "201.0")
                self._meta_otp_line_count -= 200
            except Exception:
                pass
        try:
            y_pos = self.txt_meta_otp_log.yview()
            if len(y_pos) >= 2 and y_pos[1] >= 0.85:
                self.txt_meta_otp_log.see(tk.END)
        except Exception:
            pass

    def meta_otp_update_task(self, data: Dict[str, Any]):
        """Update real-time row status in Treeview."""
        phone = str(data.get("phone", "")).strip()
        if not phone or phone not in self._meta_otp_row_items:
            return
        item_id = self._meta_otp_row_items[phone]
        if not self.tree_meta_otp.exists(item_id):
            return

        cur_v = list(self.tree_meta_otp.item(item_id, "values"))
        if len(cur_v) >= 7:
            if "worker_id" in data:
                cur_v[3] = f"#{data['worker_id']}"
            if "status" in data:
                cur_v[4] = str(data["status"])
            if "proxy" in data:
                cur_v[5] = str(data["proxy"])
            if "elapsed" in data:
                cur_v[6] = f"{data['elapsed']}s"

            tag = data.get("tag", "running")
            self.tree_meta_otp.item(item_id, values=cur_v, tags=(tag,))

            if tag == "success" and phone not in self._meta_otp_success_phones:
                self._meta_otp_success_phones.append(phone)
            elif tag in ("failed", "error") and phone not in self._meta_otp_failed_phones:
                self._meta_otp_failed_phones.append(phone)

    def meta_otp_update_stats(self, data: Dict[str, Any]):
        """Update KPI metric boxes on top."""
        if hasattr(self, "lbl_meta_otp_stat_total"):
            self.lbl_meta_otp_stat_total.config(text=str(data.get("total", 0)))
            self.lbl_meta_otp_stat_success.config(text=str(data.get("success", 0)))
            self.lbl_meta_otp_stat_failed.config(text=str(data.get("failed", 0)))
            self.lbl_meta_otp_stat_running.config(text=str(data.get("running", 0)))

    def meta_otp_on_done(self, data: Dict[str, Any]):
        """Handle completion of Meta OTP batch."""
        from app_gui import AppTheme
        if hasattr(self, "btn_meta_otp_start"):
            self.btn_meta_otp_start.config(state=tk.NORMAL, bg=AppTheme.ACCENT)
            self.btn_meta_otp_stop.config(state=tk.DISABLED, bg=AppTheme.BORDER)
        self.meta_otp_log("Tiến trình Meta OTP đã kết thúc.", "info")

    def meta_otp_export_success(self):
        """Export successful phone numbers to a text file."""
        if not self._meta_otp_success_phones and os.path.exists("Success_Numbers.txt"):
            try:
                with open("Success_Numbers.txt", "r", encoding="utf-8") as f:
                    self._meta_otp_success_phones = [x.strip() for x in f if x.strip()]
            except Exception:
                pass

        if not self._meta_otp_success_phones:
            messagebox.showinfo("Thông báo", "Chưa có số điện thoại nhận OTP thành công nào để xuất!")
            return

        save_p = filedialog.asksaveasfilename(
            title="Lưu danh sách SĐT thành công",
            defaultextension=".txt",
            filetypes=[("Text File (*.txt)", "*.txt")]
        )
        if save_p:
            with open(save_p, "w", encoding="utf-8") as f:
                f.write("\n".join(self._meta_otp_success_phones) + "\n")
            messagebox.showinfo("Thành công", f"Đã lưu {len(self._meta_otp_success_phones)} số thành công vào {save_p}")

    def meta_otp_export_failed(self):
        """Export failed phone numbers to a text file."""
        if not self._meta_otp_failed_phones and os.path.exists("Failed_Numbers.txt"):
            try:
                with open("Failed_Numbers.txt", "r", encoding="utf-8") as f:
                    self._meta_otp_failed_phones = [x.strip() for x in f if x.strip()]
            except Exception:
                pass

        if not self._meta_otp_failed_phones:
            messagebox.showinfo("Thông báo", "Chưa có số điện thoại thất bại nào để xuất!")
            return

        save_p = filedialog.asksaveasfilename(
            title="Lưu danh sách SĐT thất bại",
            defaultextension=".txt",
            filetypes=[("Text File (*.txt)", "*.txt")]
        )
        if save_p:
            with open(save_p, "w", encoding="utf-8") as f:
                f.write("\n".join(self._meta_otp_failed_phones) + "\n")
            messagebox.showinfo("Thành công", f"Đã lưu {len(self._meta_otp_failed_phones)} số thất bại vào {save_p}")

    def meta_otp_copy_success(self):
        """Copy successful numbers to clipboard."""
        if not self._meta_otp_success_phones:
            messagebox.showinfo("Thông báo", "Chưa có số điện thoại thành công nào để sao chép!")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(self._meta_otp_success_phones))
        messagebox.showinfo("Thành công", f"Đã sao chép {len(self._meta_otp_success_phones)} số điện thoại thành công vào Clipboard!")

    def meta_otp_clear_results(self):
        """Clear result table, logs, and counters."""
        for itm in self.tree_meta_otp.get_children():
            self.tree_meta_otp.delete(itm)
        self._meta_otp_row_items.clear()
        self._meta_otp_success_phones.clear()
        self._meta_otp_failed_phones.clear()
        self.txt_meta_otp_log.delete("1.0", tk.END)
        self.meta_otp_update_stats({"total": 0, "success": 0, "failed": 0, "running": 0})
