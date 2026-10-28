# -*- coding: utf-8 -*-
"""
app_gui.py - Giao diện điều khiển Reg Facebook Đa Luồng VR OTP & NVR Engine
"""

import os
import re
import sys
import copy
import logging
import unicodedata

logger = logging.getLogger(__name__)
import time
import json
import random
import queue
import threading
import subprocess
import concurrent.futures
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from core.models import RegistrationInput, RegistrationResult, ProxyItem
from core.proxy_manager import ProxyManager, KiotProxyClient, ProxySocks5Client, MproxyClient, ProxyVNClient, ActiveIpRegistry, get_subnet_24, FreeProxyManager
from core.email_service import get_email_provider, Smail1sHotmailProvider, DongVanHotmailProvider, reset_hotmail_pool
from core.registration_service import RegistrationService
from core.name_manager import NameManager
from core.geo_manager import GeoTelephonyResolver, normalize_country_code
from ui.theme import AppTheme
from ui.meta_otp_tab import MetaOtpTabMixin
from ui.utilities_tab import UtilitiesTabMixin



_MASK_IP_CACHE = {}
_MASK_IP_CACHE_MAX = 4096
_RE_URL_AUTH = re.compile(r"://[^:]+:[^@]+@")
_RE_IPV4 = re.compile(r"(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}(:\d+)?")
_RE_API_KEY = re.compile(r"[a-zA-Z0-9_-]{28,}")

class RegFacebookGUI(MetaOtpTabMixin, UtilitiesTabMixin):
    PROXY_PROVIDERS_DISPLAY = [
        "🌐 Proxy Free Cào Mới (Tải & Lọc Mới 100% Từ Mạng)",
        "🎲 Proxy Free Kho Sẵn Có (Bốc Từ Cache Trong RAM/Đĩa)",
        "🔄 Proxy.vn (Proxy Xoay Đa Key - proxyxoay.shop)",
        "🎯 KiotProxy (Chỉ lấy IP Hiện Tại - Không xoay IP)",
        "KiotProxy (1 Luồng 1 Key xoay IP)",
        "ProxySocks5.vn (API xoay IP - Token Key)",
        "📱 mProxy.vn (Proxy 4G/5G xoay IP - Token API)",
        "📁 Danh sách Proxy (proxy.txt)",
        "⚡ Không dùng Proxy (Mạng Direct)",
    ]
    PROXY_PROVIDER_MAP = {
        "🔄 Proxy.vn (Proxy Xoay Đa Key - proxyxoay.shop)": "proxyvn",
        "Proxy.vn (Proxy Xoay Đa Key - proxyxoay.shop)": "proxyvn",
        "Proxy.vn (Proxy Xoay Đa Key)": "proxyvn",
        "Proxy.vn": "proxyvn",
        "proxyvn": "proxyvn",
        "proxy_vn": "proxyvn",
        "🎯 KiotProxy (Chỉ lấy IP Hiện Tại - Không xoay IP)": "kiotproxy_current",
        "kiotproxy_current": "kiotproxy_current",
        "KiotProxy (1 Luồng 1 Key xoay IP)": "kiotproxy",
        "ProxySocks5.vn (API xoay IP - Token Key)": "proxysocks5",
        "ProxySocks5.vn": "proxysocks5",
        "ProxySocks5": "proxysocks5",
        "proxysocks5": "proxysocks5",
        "📱 mProxy.vn (Proxy 4G/5G xoay IP - Token API)": "mproxy",
        "mProxy.vn (Proxy 4G/5G xoay IP - Token API)": "mproxy",
        "mProxy.vn": "mproxy",
        "mProxy": "mproxy",
        "mproxy": "mproxy",
        "🌐 Proxy Free Cào Mới (Tải & Lọc Mới 100% Từ Mạng)": "free_proxy",
        "🌐 Proxy Free Online (Tự cào mới trên mạng)": "free_proxy",
        "🌐 Proxy Free Online (Tự cào trên mạng)": "free_proxy",
        "Proxy Free Cào Mới": "free_proxy",
        "🎲 Proxy Free Kho Sẵn Có (Bốc Từ Cache Trong RAM/Đĩa)": "free_proxy_cached",
        "🎲 Proxy Free (Bốc ngẫu nhiên từ kho Cache)": "free_proxy_cached",
        "🎲 Tất Cả Proxy Free (Random Toàn Bộ Nguồn)": "free_proxy_cached",
        "Proxy Free Kho Cache": "free_proxy_cached",
        "Tất cả Proxy": "free_proxy_cached",
        "Tất cả proxy": "free_proxy_cached",
        "Tất cả Proxy Free": "free_proxy_cached",
        "all_proxy": "free_proxy_cached",
        "all_free_proxy": "free_proxy_cached",
        "📁 Danh sách Proxy (proxy.txt)": "proxy_list",
        "⚡ Không dùng Proxy (Mạng Direct)": "none",
        "kiotproxy": "kiotproxy",
        "free_proxy": "free_proxy",
        "free_proxy_live": "free_proxy",
        "free_proxy_cached": "free_proxy_cached",
        "proxy_list": "proxy_list",
        "none": "none",
    }

    PROXY_PROVIDER_REVERSE = {
        "proxyvn": "🔄 Proxy.vn (Proxy Xoay Đa Key - proxyxoay.shop)",
        "kiotproxy_current": "🎯 KiotProxy (Chỉ lấy IP Hiện Tại - Không xoay IP)",
        "kiotproxy": "KiotProxy (1 Luồng 1 Key xoay IP)",
        "proxysocks5": "ProxySocks5.vn (API xoay IP - Token Key)",
        "mproxy": "📱 mProxy.vn (Proxy 4G/5G xoay IP - Token API)",
        "free_proxy": "🌐 Proxy Free Cào Mới (Tải & Lọc Mới 100% Từ Mạng)",
        "free_proxy_live": "🌐 Proxy Free Cào Mới (Tải & Lọc Mới 100% Từ Mạng)",
        "free_proxy_cached": "🎲 Proxy Free Kho Sẵn Có (Bốc Từ Cache Trong RAM/Đĩa)",
        "proxy_list": "📁 Danh sách Proxy (proxy.txt)",
        "none": "⚡ Không dùng Proxy (Mạng Direct)",
    }

    BAIT_MODE_OPTIONS = [
        "📱 Mồi SĐT ngẫu nhiên hợp lệ (Mồi SĐT tạo phiên)",
        "📧 Mồi Gmail (random) để tạo phiên",
        "🚫 Không sử dụng mồi (Đăng ký trực tiếp bằng Email)",
    ]

    BAIT_MODE_MAP = {
        "📱 Mồi SĐT ngẫu nhiên hợp lệ (Mồi SĐT tạo phiên)": "phone",
        "📧 Mồi Gmail (random) để tạo phiên": "gmail",
        "🚫 Không sử dụng mồi (Đăng ký trực tiếp bằng Email)": "none",
        "phone": "phone",
        "gmail": "gmail",
        "none": "none",
    }

    REVERSE_BAIT_MODE_MAP = {
        "phone": "📱 Mồi SĐT ngẫu nhiên hợp lệ (Mồi SĐT tạo phiên)",
        "gmail": "📧 Mồi Gmail (random) để tạo phiên",
        "none": "🚫 Không sử dụng mồi (Đăng ký trực tiếp bằng Email)",
    }

    LEGACY_VERIFY_OPTIONS = [
        "🚫 NV (Không OTP - No-Verify)",
        "⚙️ XM theo setting (Mail / SĐT)",
    ]

    LEGACY_VERIFY_MAP = {
        "🚫 NV (Không OTP - No-Verify)": "none",
        "⚙️ XM theo setting (Mail / SĐT)": "setting",
        "🚫 Không xác minh (Bypass / NV như hiện tại)": "none",
        "📧 Xác minh Email (VR OTP Email theo Hòm thư)": "setting",
        "📱 Xác minh Số điện thoại (VR OTP SĐT qua SMS / Metaking)": "setting",
        "none": "none",
        "nv": "none",
        "setting": "setting",
        "verify": "setting",
        "email": "setting",
        "phone": "setting",
    }

    REVERSE_LEGACY_VERIFY_MAP = {
        "none": "🚫 NV (Không OTP - No-Verify)",
        "nv": "🚫 NV (Không OTP - No-Verify)",
        "setting": "⚙️ XM theo setting (Mail / SĐT)",
        "verify": "⚙️ XM theo setting (Mail / SĐT)",
        "email": "⚙️ XM theo setting (Mail / SĐT)",
        "phone": "⚙️ XM theo setting (Mail / SĐT)",
    }

    DASH_LEGACY_VERIFY_OPTIONS = [
        "🚫 NV (Không OTP)",
        "⚙️ XM theo setting",
    ]

    DASH_LEGACY_VERIFY_MAP = {
        "🚫 NV (Không OTP)": "none",
        "⚙️ XM theo setting": "setting",
        "none": "none",
        "nv": "none",
        "setting": "setting",
        "verify": "setting",
        "email": "setting",
        "phone": "setting",
    }

    REVERSE_DASH_LEGACY_VERIFY_MAP = {
        "none": "🚫 NV (Không OTP)",
        "nv": "🚫 NV (Không OTP)",
        "setting": "⚙️ XM theo setting",
        "verify": "⚙️ XM theo setting",
        "email": "⚙️ XM theo setting",
        "phone": "⚙️ XM theo setting",
    }


    SERVER_DOMAINS = [
        "m.facebook.com",
        "mbasic.facebook.com",
        "touch.facebook.com",
        "free.facebook.com",
        "m.alpha.facebook.com",
        "m.beta.facebook.com",
        "x.facebook.com",
        "limited.facebook.com",
        "iphone.facebook.com",
        "d.facebook.com",
    ]

    LEGACY_SERVER_OPTIONS = [
        "🎲 Random tất cả Server (1 - 10)",
        "🎛️ Random nhóm đã chọn (Custom Pool)",
        "01 - m.facebook.com (Chuẩn di động)",
        "02 - mbasic.facebook.com (HTML nhẹ)",
        "03 - touch.facebook.com (Touch)",
        "04 - free.facebook.com (Free Basics)",
        "05 - m.alpha.facebook.com (Alpha)",
        "06 - m.beta.facebook.com (Beta)",
        "07 - x.facebook.com (Data Saver)",
        "08 - limited.facebook.com (Băng thông thấp)",
        "09 - iphone.facebook.com (iOS Safari)",
        "10 - d.facebook.com (Feature Phone)",
    ]

    LEGACY_SERVER_MAP = {
        "🎲 Random tất cả Server (1 - 10)": "random",
        "01 - m.facebook.com (Chuẩn di động)": "m.facebook.com",
        "02 - mbasic.facebook.com (HTML nhẹ)": "mbasic.facebook.com",
        "03 - touch.facebook.com (Touch)": "touch.facebook.com",
        "04 - free.facebook.com (Free Basics)": "free.facebook.com",
        "05 - m.alpha.facebook.com (Alpha)": "m.alpha.facebook.com",
        "06 - m.beta.facebook.com (Beta)": "m.beta.facebook.com",
        "07 - x.facebook.com (Data Saver)": "x.facebook.com",
        "08 - limited.facebook.com (Băng thông thấp)": "limited.facebook.com",
        "09 - iphone.facebook.com (iOS Safari)": "iphone.facebook.com",
        "10 - d.facebook.com (Feature Phone)": "d.facebook.com",
    }

    REVERSE_LEGACY_SERVER_MAP = {
        "random": "🎲 Random tất cả Server (1 - 10)",
        "all": "🎲 Random tất cả Server (1 - 10)",
        "m.facebook.com": "01 - m.facebook.com (Chuẩn di động)",
        "mbasic.facebook.com": "02 - mbasic.facebook.com (HTML nhẹ)",
        "touch.facebook.com": "03 - touch.facebook.com (Touch)",
        "free.facebook.com": "04 - free.facebook.com (Free Basics)",
        "m.alpha.facebook.com": "05 - m.alpha.facebook.com (Alpha)",
        "m.beta.facebook.com": "06 - m.beta.facebook.com (Beta)",
        "x.facebook.com": "07 - x.facebook.com (Data Saver)",
        "limited.facebook.com": "08 - limited.facebook.com (Băng thông thấp)",
        "iphone.facebook.com": "09 - iphone.facebook.com (iOS Safari)",
        "d.facebook.com": "10 - d.facebook.com (Feature Phone)",
        "1": "01 - m.facebook.com (Chuẩn di động)",
        "2": "02 - mbasic.facebook.com (HTML nhẹ)",
        "3": "03 - touch.facebook.com (Touch)",
        "4": "04 - free.facebook.com (Free Basics)",
        "5": "05 - m.alpha.facebook.com (Alpha)",
        "6": "06 - m.beta.facebook.com (Beta)",
        "7": "07 - x.facebook.com (Data Saver)",
        "8": "08 - limited.facebook.com (Băng thông thấp)",
        "9": "09 - iphone.facebook.com (iOS Safari)",
        "10": "10 - d.facebook.com (Feature Phone)",
    }

    DASH_LEGACY_SERVER_OPTIONS = [
        "🎲 Random tất cả",
        "🎛️ Random nhóm (Custom)",
        "01 - m.facebook.com",
        "02 - mbasic.facebook.com",
        "03 - touch.facebook.com",
        "04 - free.facebook.com",
        "05 - m.alpha.facebook.com",
        "06 - m.beta.facebook.com",
        "07 - x.facebook.com",
        "08 - limited.facebook.com",
        "09 - iphone.facebook.com",
        "10 - d.facebook.com",
    ]

    DASH_LEGACY_SERVER_MAP = {
        "🎲 Random Server": "random",
        "01 - m.facebook.com": "m.facebook.com",
        "02 - mbasic.facebook.com": "mbasic.facebook.com",
        "03 - touch.facebook.com": "touch.facebook.com",
        "04 - free.facebook.com": "free.facebook.com",
        "05 - m.alpha.facebook.com": "m.alpha.facebook.com",
        "06 - m.beta.facebook.com": "m.beta.facebook.com",
        "07 - x.facebook.com": "x.facebook.com",
        "08 - limited.facebook.com": "limited.facebook.com",
        "09 - iphone.facebook.com": "iphone.facebook.com",
        "10 - d.facebook.com": "d.facebook.com",
    }

    REVERSE_DASH_LEGACY_SERVER_MAP = {
        "random": "🎲 Random Server",
        "all": "🎲 Random Server",
        "m.facebook.com": "01 - m.facebook.com",
        "mbasic.facebook.com": "02 - mbasic.facebook.com",
        "touch.facebook.com": "03 - touch.facebook.com",
        "free.facebook.com": "04 - free.facebook.com",
        "m.alpha.facebook.com": "05 - m.alpha.facebook.com",
        "m.beta.facebook.com": "06 - m.beta.facebook.com",
        "x.facebook.com": "07 - x.facebook.com",
        "limited.facebook.com": "08 - limited.facebook.com",
        "iphone.facebook.com": "09 - iphone.facebook.com",
        "d.facebook.com": "10 - d.facebook.com",
        "1": "01 - m.facebook.com",
        "2": "02 - mbasic.facebook.com",
        "3": "03 - touch.facebook.com",
        "4": "04 - free.facebook.com",
        "5": "05 - m.alpha.facebook.com",
        "6": "06 - m.beta.facebook.com",
        "7": "07 - x.facebook.com",
        "8": "08 - limited.facebook.com",
        "9": "09 - iphone.facebook.com",
        "10": "10 - d.facebook.com",
    }

    RETRY_EMAIL_SERVICES_DISPLAY = [
        "🔄 Dùng theo cấu hình chính (Setting)",
        "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus",
        "Mail Ảo Riêng: @smail1s.com (Smail1s Temp)",
        "Mail Ảo Riêng: @laoia.com (10MinuteMail)",
        "Mail Ảo Riêng: @smailwork.com (Smailwork - pqudx6448)",
        "Mail Ảo Riêng: @hotmailtrusted.com (Smail1s Hotmail)",
        "Mail Ảo Riêng: @mailto.plus (TempMail.Plus)",
        "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)",
        "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)",
        "Mail Ảo Free: InboxKitten (Không Giới Hạn - Nhanh)",
        "Mail Ảo Free: ThrowAwayMail (10+ Đuôi Mới)",
        "Mail Ảo Free: DisposableMail (10+ Đuôi Sạch)",
        "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)",
        "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)",
        "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)",
        "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)",
        "Mail Ảo Free: Temp-Mail.io (7+ Đuôi Mail)",
        "Mail Ảo Free: 10MinuteMail (@laoia.com - 1 Đuôi Sạch)",
        "Mail Ảo Free: Smail1s Temp (5+ Đuôi Mail)",
        "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)",
        "Mail Ảo Free: Mail.tm (Đa Đuôi REST API)",
        "Mail Ảo Free: TempMail.lol (Đa Đuôi API v2)",
        "Mail Ảo Free: Guerrilla Mail (8+ Đuôi Mail)",
        "Mail Ảo Free: Maildrop.cc (GraphQL)",
        "Mail Ảo Free: Mailnesia (Không giới hạn)",
        "Mail Ảo Free: 1SecMail (Random 7+ đuôi)",
        "Mail Ảo Free: Mohmal (5+ Đuôi Mail - Tự động)",
        "✉️ Dùng Hotmail Tự Nhập (Kho hotmails.txt)",
        "👑 Metaking: Thuê Hotmail (hotmail.com)",
        "👑 Metaking: Thuê Gmail (gmail.com)",
        "DongVanFB Tool API",
        "Smail1s Tool API",
    ]

    RETRY_EMAIL_SERVICE_MAP = {
        "🔄 Dùng theo cấu hình chính (Setting)": "as_setting",
        "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus": "clean_trio",
        "🎯 Bộ 3 Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com": "clean_trio",
        "clean_trio": "clean_trio",
        "clean_suite": "clean_trio",
        "trio": "clean_trio",
        "Mail Ảo Riêng: @smail1s.com (Smail1s Temp)": "smail1s_domain",
        "smail1s_domain": "smail1s_domain",
        "smail1s_only": "smail1s_domain",
        "Mail Ảo Riêng: @laoia.com (10MinuteMail)": "laoia_domain",
        "laoia_domain": "laoia_domain",
        "laoia_only": "laoia_domain",
        "Mail Ảo Riêng: @smailwork.com (Smailwork - pqudx6448)": "smailwork_domain",
        "smailwork_domain": "smailwork_domain",
        "smailwork_only": "smailwork_domain",
        "Mail Ảo Riêng: @hotmailtrusted.com (Smail1s Hotmail)": "hotmailtrusted_domain",
        "hotmailtrusted_domain": "hotmailtrusted_domain",
        "Mail Ảo Riêng: @mailto.plus (TempMail.Plus)": "mailtoplus_domain",
        "mailtoplus_domain": "mailtoplus_domain",
        "as_setting": "as_setting",
        "setting": "as_setting",
        "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)": "all_free",
        "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)": "auto_rotator",
        "Tất cả Mail Free": "all_free",
        "Tất cả mail free": "all_free",
        "tat_ca_mail_free": "all_free",
        "all_free": "all_free",
        "all_free_mail": "all_free",
        "auto_rotator": "auto_rotator",
        "Mail Ảo Free: InboxKitten (Không Giới Hạn - Nhanh)": "inboxkitten",
        "inboxkitten": "inboxkitten",
        "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)": "fakemailgenerator",
        "fakemailgenerator": "fakemailgenerator",
        "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)": "emailfake",
        "emailfake": "emailfake",
        "Mail Ảo Free: ThrowAwayMail (10+ Đuôi Mới)": "throwawaymail",
        "throwawaymail": "throwawaymail",
        "throwaway": "throwawaymail",
        "Mail Ảo Free: DisposableMail (10+ Đuôi Sạch)": "disposablemail",
        "disposablemail": "disposablemail",
        "disposable": "disposablemail",
        "Mail Ảo Free: ThrowAwayMail (10+ Đuôi Mới)": "throwawaymail",
        "throwawaymail": "throwawaymail",
        "throwaway": "throwawaymail",
        "Mail Ảo Free: DisposableMail (10+ Đuôi Sạch)": "disposablemail",
        "disposablemail": "disposablemail",
        "disposable": "disposablemail",
        "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)": "fakemailgenerator",
        "fakemailgenerator": "fakemailgenerator",
        "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)": "emailfake",
        "emailfake": "emailfake",
        "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)": "generator_email",
        "generator_email": "generator_email",
        "generator": "generator_email",
        "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)": "tempmail_plus",
        "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)": "generator_email",
        "generator_email": "generator_email",
        "generator": "generator_email",
        "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)": "tempmail_plus",
        "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)": "generator_email",
        "generator_email": "generator_email",
        "generator": "generator_email",
        "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)": "tempmail_plus",
        "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)": "generator_email",
        "generator_email": "generator_email",
        "generator": "generator_email",
        "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)": "tempmail_plus",
        "Mail Ảo Free: TempMail.Plus (9+ Đuôi Mail)": "tempmail_plus",
        "tempmail_plus": "tempmail_plus",
        "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)": "inboxes",
        "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)": "inboxes",
        "Mail Ảo Free: Inboxes.com (Miễn phí)": "inboxes",
        "inboxes": "inboxes",
        "Mail Ảo Free: Temp-Mail.io (7+ Đuôi Mail)": "tempmail_io",
        "Mail Ảo Free: Temp-Mail.io (Miễn phí - Đa đuôi mới)": "tempmail_io",
        "tempmail_io": "tempmail_io",
        "Mail Ảo Free: 10MinuteMail (@laoia.com - 1 Đuôi Sạch)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com / @fivermail.com - Khóa 2 Đuôi)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com / @fivermail.com - Khóa 2 Đuôi)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com / @fivermail.com)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com / @fivermail.com - Khóa 2 Đuôi)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (Đa đuôi - Tự động)": "10minutemail",
        "10minutemail": "10minutemail",
        "Mail Ảo Free: Smail1s Temp (5+ Đuôi Mail)": "smail1s_temp",
        "Mail Ảo Free: Smail1s Temp (Miễn phí)": "smail1s_temp",
        "smail1s_temp": "smail1s_temp",
        "Mail Ảo Free: Mail.tm (Đa Đuôi REST API)": "mailtm",
        "Mail Ảo Free: Mail.tm (Miễn phí - Đa đuôi)": "mailtm",
        "Mail Ảo Free: Mail.tm (Đa đuôi)": "mailtm",
        "mailtm": "mailtm",
        "Mail Ảo Free: TempMail.lol (Đa Đuôi API v2)": "tempmaillol",
        "Mail Ảo Free: TempMail.lol (Đa đuôi mail)": "tempmaillol",
        "tempmaillol": "tempmaillol",
        "Mail Ảo Free: Guerrilla Mail (8+ Đuôi Mail)": "guerrilla",
        "Mail Ảo Free: Guerrilla Mail (9+ đuôi mail)": "guerrilla",
        "guerrilla": "guerrilla",
        "Mail Ảo Free: Maildrop.cc (GraphQL)": "maildrop",
        "Mail Ảo Free: Maildrop.cc (Miễn phí - GraphQL)": "maildrop",
        "maildrop": "maildrop",
        "Mail Ảo Free: Mailnesia (Không giới hạn)": "mailnesia",
        "mailnesia": "mailnesia",
        "Mail Ảo Free: 1SecMail (Random 7+ đuôi)": "onesecmail",
        "onesecmail": "onesecmail",
        "Mail Ảo Free: Mohmal (5+ Đuôi Mail - Tự động)": "mohmal",
        "mohmal": "mohmal",
        "✉️ Dùng Hotmail Tự Nhập (Kho hotmails.txt)": "custom_hotmail",
        "custom_hotmail": "custom_hotmail",
        "👑 Metaking: Thuê Hotmail (hotmail.com)": "metaking_hotmail",
        "metaking_hotmail": "metaking_hotmail",
        "👑 Metaking: Thuê Gmail (gmail.com)": "metaking_gmail",
        "metaking_gmail": "metaking_gmail",
        "DongVanFB Tool API": "dongvanfb",
        "dongvanfb": "dongvanfb",
        "Smail1s Tool API": "smail1s",
        "smail1s": "smail1s",
    }

    RETRY_EMAIL_SERVICE_REVERSE = {
        "clean_trio": "🎯 Bộ 3 Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com",
        "smail1s_domain": "Mail Ảo Riêng: @smail1s.com (Smail1s Temp)",
        "laoia_domain": "Mail Ảo Riêng: @laoia.com (10MinuteMail)",
        "smailwork_domain": "Mail Ảo Riêng: @smailwork.com (Smailwork - pqudx6448)",
        "as_setting": "🔄 Dùng theo cấu hình chính (Setting)",
        "all_free": "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)",
        "auto_rotator": "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)",
        "inboxkitten": "Mail Ảo Free: InboxKitten (Không Giới Hạn - Nhanh)",
        "fakemailgenerator": "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)",
        "emailfake": "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)",
        "fakemailgenerator": "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)",
        "emailfake": "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)",
        "throwawaymail": "Mail Ảo Free: ThrowAwayMail (10+ Đuôi Mới)",
        "disposablemail": "Mail Ảo Free: DisposableMail (10+ Đuôi Sạch)",
        "tempmail_plus": "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)",
        "inboxes": "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)",
        "tempmail_io": "Mail Ảo Free: Temp-Mail.io (7+ Đuôi Mail)",
        "10minutemail": "Mail Ảo Free: 10MinuteMail (@laoia.com - 1 Đuôi Sạch)",
        "smail1s_temp": "Mail Ảo Free: Smail1s Temp (5+ Đuôi Mail)",
        "generator_email": "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)",
        "mailtm": "Mail Ảo Free: Mail.tm (Đa Đuôi REST API)",
        "tempmaillol": "Mail Ảo Free: TempMail.lol (Đa Đuôi API v2)",
        "guerrilla": "Mail Ảo Free: Guerrilla Mail (8+ Đuôi Mail)",
        "maildrop": "Mail Ảo Free: Maildrop.cc (GraphQL)",
        "mailnesia": "Mail Ảo Free: Mailnesia (Không giới hạn)",
        "onesecmail": "Mail Ảo Free: 1SecMail (Random 7+ đuôi)",
        "mohmal": "Mail Ảo Free: Mohmal (5+ Đuôi Mail - Tự động)",
        "custom_hotmail": "✉️ Dùng Hotmail Tự Nhập (Kho hotmails.txt)",
        "metaking_hotmail": "👑 Metaking: Thuê Hotmail (hotmail.com)",
        "metaking_gmail": "👑 Metaking: Thuê Gmail (gmail.com)",
        "dongvanfb": "DongVanFB Tool API",
        "smail1s": "Smail1s Tool API",
    }

    EMAIL_PROVIDERS_DISPLAY = [
        "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus",
        "Mail Ảo Riêng: @smail1s.com (Smail1s Temp)",
        "Mail Ảo Riêng: @laoia.com (10MinuteMail)",
        "Mail Ảo Riêng: @smailwork.com (Smailwork - pqudx6448)",
        "Mail Ảo Riêng: @hotmailtrusted.com (Smail1s Hotmail)",
        "Mail Ảo Riêng: @mailto.plus (TempMail.Plus)",
        "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)",
        "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)",
        "Mail Ảo Free: ThrowAwayMail (10+ Đuôi Mới)",
        "Mail Ảo Free: DisposableMail (10+ Đuôi Sạch)",
        "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)",
        "Mail Ảo Free: InboxKitten (Không Giới Hạn - Nhanh)",
        "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)",
        "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)",
        "👑 Metaking: Thuê Gmail (gmail.com)",
        "👑 Metaking: Thuê iCloud (icloud.com)",
        "👑 Metaking: Thuê Hotmail (hotmail.com)",
        "👑 Metaking: Thuê Outlook (outlook.com)",
        "👑 Metaking: Thuê SĐT SMS FB (Yemen / VN / US / Đa Quốc Gia)",
        "👑 Thuê OTP Metaking.top (Tùy Chọn Trong Cài Đặt)",
        "📧 Dùng Hotmail Tự Nhập (Kho hotmails.txt) (KHUYÊN DÙNG - Nhận OTP 100%)",
        "📎 Dùng Email Đi Kèm Acc (Nếu acc đã nạp có mail)",
        "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)",
        "Mail Ảo Free: Temp-Mail.io (Miễn phí - Đa đuôi mới)",
        "Mail Ảo Free: 10MinuteMail (@laoia.com - 1 Đuôi Sạch)",
        "Mail Ảo Free: 10MinuteMail (Đa đuôi - Tự động)",
        "Mail Ảo Free: Maildrop.cc (Miễn phí - GraphQL)",
        "Mail Ảo Free: Mail.tm (Miễn phí - Đa đuôi)",
        "Mail Ảo Free: TempMail.lol (Đa đuôi mail)",
        "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)",
        "Mail Ảo Free: Guerrilla Mail (9+ đuôi mail)",
        "Mail Ảo Free: Mailnesia (Không giới hạn)",
        "Mail Ảo Free: Smail1s Temp (Miễn phí)",
        "Mail Ảo Free: 1SecMail (Random 7+ đuôi)",
        "Mail Ảo Free: Mohmal (5+ Đuôi Mail - Tự động)",
        "DongVanFB Tool API",
        "Smail1s Tool API",
    ]

    EMAIL_PROVIDER_MAP = {
        "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus": "clean_trio",
        "🎯 Bộ 3 Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com (Tùy Chọn Đuôi)": "clean_trio",
        "clean_trio": "clean_trio",
        "clean_suite": "clean_trio",
        "trio": "clean_trio",
        "bo_3_mail": "clean_trio",
        "3_mail": "clean_trio",
        "Mail Ảo Riêng: @smail1s.com (Smail1s Temp)": "smail1s_domain",
        "smail1s_domain": "smail1s_domain",
        "smail1s_only": "smail1s_domain",
        "Mail Ảo Riêng: @laoia.com (10MinuteMail)": "laoia_domain",
        "laoia_domain": "laoia_domain",
        "laoia_only": "laoia_domain",
        "Mail Ảo Riêng: @smailwork.com (Smailwork - pqudx6448)": "smailwork_domain",
        "smailwork_domain": "smailwork_domain",
        "smailwork_only": "smailwork_domain",
        "Mail Ảo Riêng: @hotmailtrusted.com (Smail1s Hotmail)": "hotmailtrusted_domain",
        "hotmailtrusted_domain": "hotmailtrusted_domain",
        "Mail Ảo Riêng: @mailto.plus (TempMail.Plus)": "mailtoplus_domain",
        "mailtoplus_domain": "mailtoplus_domain",
        "Mail Ảo Free: ThrowAwayMail (10+ Đuôi Mới)": "throwawaymail",
        "throwawaymail": "throwawaymail",
        "throwaway": "throwawaymail",
        "Mail Ảo Free: DisposableMail (10+ Đuôi Sạch)": "disposablemail",
        "disposablemail": "disposablemail",
        "disposable": "disposablemail",
        "👑 Metaking: Thuê Gmail (gmail.com)": "metaking_gmail",
        "👑 Metaking: Thuê iCloud (icloud.com)": "metaking_icloud",
        "👑 Metaking: Thuê Hotmail (hotmail.com)": "metaking_hotmail",
        "👑 Metaking: Thuê Outlook (outlook.com)": "metaking_outlook",
        "👑 Metaking: Thuê SĐT SMS FB (Yemen / VN / US / Đa Quốc Gia)": "metaking_phone",
        "👑 Thuê OTP Metaking.top (Tùy Chọn Trong Cài Đặt)": "metaking",
        "👑 Thuê OTP Metaking.top (Gmail / iCloud / Hotmail / SĐT)": "metaking",
        "metaking_gmail": "metaking_gmail",
        "metaking_icloud": "metaking_icloud",
        "metaking_hotmail": "metaking_hotmail",
        "metaking_outlook": "metaking_outlook",
        "metaking": "metaking",
        "metaking_top": "metaking",
        "metaking_email": "metaking",
        "metaking_phone": "metaking_phone",
        "📎 Dùng Email Đi Kèm Acc (Nếu acc đã nạp có mail)": "account_email",
        "account_email": "account_email",
        "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)": "all_free",
        "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)": "auto_rotator",
        "Tất cả Mail Free": "all_free",
        "Tất cả mail free": "all_free",
        "tat_ca_mail_free": "all_free",
        "all_free": "all_free",
        "all_free_mail": "all_free",
        "auto_rotator": "auto_rotator",
        "Mail Ảo Free: InboxKitten (Không Giới Hạn - Nhanh)": "inboxkitten",
        "inboxkitten": "inboxkitten",
        "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)": "fakemailgenerator",
        "fakemailgenerator": "fakemailgenerator",
        "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)": "emailfake",
        "emailfake": "emailfake",
        "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)": "generator_email",
        "generator_email": "generator_email",
        "generator": "generator_email",
        "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)": "tempmail_plus",
        "Mail Ảo Free: TempMail.Plus (9+ Đuôi Mail)": "tempmail_plus",
        "tempmail_plus": "tempmail_plus",
        "tempmail.plus": "tempmail_plus",
        "📧 Dùng Hotmail Tự Nhập (Kho hotmails.txt) (KHUYÊN DÙNG - Nhận OTP 100%)": "custom_hotmail",
        "📧 Dùng Hotmail Tự Nhập (Kho hotmails.txt)": "custom_hotmail",
        "✍ Dùng Hotmail Tự Nhập (Kho hotmails.txt)": "custom_hotmail",
        "Hotmail Tự Nhập (Kho hotmails.txt)": "custom_hotmail",
        "Mail Ảo Free: Temp-Mail.io (Miễn phí - Đa đuôi mới)": "tempmail_io",
        "Mail Ảo: Temp-Mail.io (Miễn phí)": "tempmail_io",
        "Mail Ảo Free: 10MinuteMail (@laoia.com - 1 Đuôi Sạch)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com / @fivermail.com - Khóa 2 Đuôi)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (@laoia.com / @fivermail.com)": "10minutemail",
        "Mail Ảo Free: 10MinuteMail (Đa đuôi - Tự động)": "10minutemail",
        "Mail Ảo: 10MinuteMail (Miễn phí)": "10minutemail",
        "Mail Ảo Free: Maildrop.cc (Miễn phí - GraphQL)": "maildrop",
        "Mail Ảo: Maildrop.cc (Miễn phí)": "maildrop",
        "tempmail_io": "tempmail_io",
        "10minutemail": "10minutemail",
        "maildrop": "maildrop",
        "Mail Ảo Free: Mail.tm (Miễn phí - Đa đuôi)": "mailtm",
        "Mail Ảo Free: Mail.tm (Miễn phí)": "mailtm",
        "Mail Ảo: Mail.tm (Miễn phí)": "mailtm",
        "Mail Ảo Free: TempMail.lol (Đa đuôi mail)": "tempmaillol",
        "Mail Ảo: TempMail.lol (Miễn phí)": "tempmaillol",
        "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)": "inboxes",
        "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)": "inboxes",
        "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)": "inboxes",
        "Mail Ảo Free: Inboxes.com (Miễn phí)": "inboxes",
        "Mail Ảo: Inboxes.com (Miễn phí)": "inboxes",
        "Mail Ảo Free: Guerrilla Mail (9+ đuôi mail)": "guerrilla",
        "Mail Ảo: Guerrilla Mail (Miễn phí)": "guerrilla",
        "Mail Ảo Free: Mailnesia (Không giới hạn)": "mailnesia",
        "Mail Ảo: Mailnesia (Không giới hạn)": "mailnesia",
        "Mail Ảo Free: Smail1s Temp (Miễn phí)": "smail1s_temp",
        "Mail Ảo: Smail1s Temp (Miễn phí)": "smail1s_temp",
        "Mail Ảo Free: 1SecMail (Random 7+ đuôi)": "onesecmail",
        "Mail Ảo Free: Mohmal (5+ Đuôi Mail - Tự động)": "mohmal",
        "DongVanFB Tool API": "dongvanfb",
        "Smail1s Tool API": "smail1s",
        "custom_hotmail": "custom_hotmail",
        "dongvanfb": "dongvanfb",
        "smail1s": "smail1s",
        "smail1s_temp": "smail1s_temp",
        "mailtm": "mailtm",
        "inboxes": "inboxes",
        "tempmaillol": "tempmaillol",
        "guerrilla": "guerrilla",
        "mailnesia": "mailnesia",
        "onesecmail": "onesecmail",
        "mohmal": "mohmal",
    }

    EMAIL_PROVIDER_REVERSE = {
        "clean_trio": "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus",
        "clean_suite": "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus",
        "smail1s_domain": "Mail Ảo Riêng: @smail1s.com (Smail1s Temp)",
        "laoia_domain": "Mail Ảo Riêng: @laoia.com (10MinuteMail)",
        "smailwork_domain": "Mail Ảo Riêng: @smailwork.com (Smailwork - pqudx6448)",
        "hotmailtrusted_domain": "Mail Ảo Riêng: @hotmailtrusted.com (Smail1s Hotmail)",
        "mailtoplus_domain": "Mail Ảo Riêng: @mailto.plus (TempMail.Plus)",
        "inboxkitten": "Mail Ảo Free: InboxKitten (Không Giới Hạn - Nhanh)",
        "fakemailgenerator": "Mail Ảo Free: FakeMailGenerator (10+ Đuôi US)",
        "emailfake": "Mail Ảo Free: EmailFake.com (12+ Đuôi Sạch)",
        "throwawaymail": "Mail Ảo Free: ThrowAwayMail (10+ Đuôi Mới)",
        "disposablemail": "Mail Ảo Free: DisposableMail (10+ Đuôi Sạch)",
        "generator_email": "Mail Ảo Free: Generator.email (8+ Đuôi Mới - Nhanh)",
        "metaking_gmail": "👑 Metaking: Thuê Gmail (gmail.com)",
        "metaking_icloud": "👑 Metaking: Thuê iCloud (icloud.com)",
        "metaking_hotmail": "👑 Metaking: Thuê Hotmail (hotmail.com)",
        "metaking_outlook": "👑 Metaking: Thuê Outlook (outlook.com)",
        "metaking_phone": "👑 Metaking: Thuê SĐT SMS FB (Yemen / VN / US / Đa Quốc Gia)",
        "metaking": "👑 Thuê OTP Metaking.top (Tùy Chọn Trong Cài Đặt)",
        "metaking_top": "👑 Thuê OTP Metaking.top (Tùy Chọn Trong Cài Đặt)",
        "metaking_email": "👑 Thuê OTP Metaking.top (Tùy Chọn Trong Cài Đặt)",
        "account_email": "📎 Dùng Email Đi Kèm Acc (Nếu acc đã nạp có mail)",
        "all_free": "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)",
        "auto_rotator": "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)",
        "tempmail_plus": "Mail Ảo Free: TempMail.Plus (19+ Đuôi Mail)",
        "custom_hotmail": "📧 Dùng Hotmail Tự Nhập (Kho hotmails.txt) (KHUYÊN DÙNG - Nhận OTP 100%)",
        "dongvanfb": "📧 Dùng Hotmail Tự Nhập (Kho hotmails.txt) (KHUYÊN DÙNG - Nhận OTP 100%)",
        "smail1s": "Smail1s Tool API",
        "smail1s_temp": "Mail Ảo Free: Smail1s Temp (Miễn phí)",
        "tempmail_io": "Mail Ảo Free: Temp-Mail.io (Miễn phí - Đa đuôi mới)",
        "10minutemail": "Mail Ảo Free: 10MinuteMail (@laoia.com - 1 Đuôi Sạch)",
        "maildrop": "Mail Ảo Free: Maildrop.cc (Miễn phí - GraphQL)",
        "mailtm": "Mail Ảo Free: Mail.tm (Miễn phí - Đa đuôi)",
        "inboxes": "Mail Ảo Free: Inboxes.com (18+ Đuôi Mail)",
        "tempmaillol": "Mail Ảo Free: TempMail.lol (Đa đuôi mail)",
        "guerrilla": "Mail Ảo Free: Guerrilla Mail (9+ đuôi mail)",
        "mailnesia": "Mail Ảo Free: Mailnesia (Không giới hạn)",
        "onesecmail": "Mail Ảo Free: 1SecMail (Random 7+ đuôi)",
        "mohmal": "Mail Ảo Free: Mohmal (5+ Đuôi Mail - Tự động)",
    }

    def get_selected_proxy_provider(self) -> str:
        if not hasattr(self, "cb_proxy_provider"):
            return self.config.get("proxy_provider", "kiotproxy")
        val = self.cb_proxy_provider.get()
        return self.PROXY_PROVIDER_MAP.get(val, val)

    def get_selected_email_service(self) -> str:
        if not hasattr(self, "cb_email_provider"):
            return "custom_hotmail"
        val = self.cb_email_provider.get()
        return self.EMAIL_PROVIDER_MAP.get(val, val)

    CLEAN_DOMAINS_MAP = [
        ("smail1s.com", "var_domain_smail1s"),
        ("laoia.com", "var_domain_laoia"),
        ("smailwork.com", "var_domain_smailwork"),
        ("mailto.plus", "var_domain_mailtoplus"),
        ("hotmailtrusted.com", "var_domain_hotmailtrusted"),
        ("fexpost.com", "var_domain_fexpost"),
        ("mailbox.in.ua", "var_domain_mailboxinua"),
        ("rover.info", "var_domain_roverinfo"),
        ("tanpony.com", "var_domain_tanpony"),
    ]

    def select_quartet_custom_domains(self):
        quartet = ["smail1s.com", "laoia.com", "smailwork.com", "mailto.plus"]
        for dom, var_name in self.CLEAN_DOMAINS_MAP:
            v = getattr(self, var_name, None)
            if v:
                v.set(dom in quartet)
        self.on_custom_domains_changed()

    def select_top_clean_domains(self):
        top_two = ["laoia.com", "mailto.plus"]
        for dom, var_name in self.CLEAN_DOMAINS_MAP:
            v = getattr(self, var_name, None)
            if v:
                v.set(dom in top_two)
        self.on_custom_domains_changed()

    def get_selected_custom_domains(self) -> List[str]:
        doms = []
        for dom, var_name in self.CLEAN_DOMAINS_MAP:
            v = getattr(self, var_name, None)
            if v and v.get():
                doms.append(dom)
        if not doms:
            doms = [d for d, _ in self.CLEAN_DOMAINS_MAP]
        return doms

    def on_custom_domains_changed(self):
        doms = self.get_selected_custom_domains()
        self.config["selected_custom_domains"] = doms
        dom_str = ", ".join(["@" + d for d in doms])
        self.log(f"[*] Đã chọn đuôi mail sạch ({len(doms)}/{len(self.CLEAN_DOMAINS_MAP)} đuôi): {dom_str}", "info")

    def select_all_custom_domains(self):
        for _, var_name in self.CLEAN_DOMAINS_MAP:
            v = getattr(self, var_name, None)
            if v:
                v.set(True)
        self.on_custom_domains_changed()

    def deselect_all_custom_domains(self):
        for dom, var_name in self.CLEAN_DOMAINS_MAP:
            v = getattr(self, var_name, None)
            if v:
                v.set(dom == "laoia.com")
        self.on_custom_domains_changed()

    def get_selected_bait_mode(self) -> str:
        if not hasattr(self, "cb_bait_mode"):
            if "bait_mode" in self.config:
                return str(self.config.get("bait_mode", "phone")).lower().strip()
            if self.config.get("use_bait_gmail"):
                return "gmail"
            if self.config.get("use_bait_phone") is not None:
                return "phone" if bool(self.config.get("use_bait_phone")) else "none"
            return "phone" if bool(self.config.get("auto_gen_phone", True)) else "none"
        val = self.cb_bait_mode.get()
        return self.BAIT_MODE_MAP.get(val, "phone")

    def set_selected_bait_mode(self, mode: str):
        if not hasattr(self, "cb_bait_mode"):
            return
        m = str(mode).lower().strip()
        lbl = self.REVERSE_BAIT_MODE_MAP.get(m, self.BAIT_MODE_OPTIONS[0])
        self.cb_bait_mode.set(lbl)
        if hasattr(self, "var_auto_phone"):
            self.var_auto_phone.set(m == "phone")

    def on_bait_mode_changed(self, event=None):
        mode = self.get_selected_bait_mode()
        self.config["bait_mode"] = mode
        self.config["auto_gen_phone"] = (mode == "phone")
        self.config["use_bait_phone"] = (mode == "phone")
        self.config["use_bait_gmail"] = (mode == "gmail")
        if hasattr(self, "var_auto_phone"):
            self.var_auto_phone.set(mode == "phone")
        if mode == "phone":
            self.log("[*] Đã chọn phương thức mồi: SĐT ngẫu nhiên hợp lệ (Mồi SĐT tạo phiên).", "info")
        elif mode == "gmail":
            self.log("[*] Đã chọn phương thức mồi: Mồi Gmail (random) để tạo phiên.", "info")
        else:
            self.log("[*] Đã chọn phương thức mồi: Không sử dụng mồi (Đăng ký trực tiếp bằng Email).", "info")

    def get_selected_legacy_verify_mode(self) -> str:
        if hasattr(self, "cb_legacy_verify") and self.cb_legacy_verify:
            val = self.cb_legacy_verify.get().strip()
            if val in self.LEGACY_VERIFY_MAP:
                return self.LEGACY_VERIFY_MAP[val]
        if hasattr(self, "cb_dash_legacy_verify") and self.cb_dash_legacy_verify:
            val = self.cb_dash_legacy_verify.get().strip()
            if val in self.DASH_LEGACY_VERIFY_MAP:
                return self.DASH_LEGACY_VERIFY_MAP[val]
        return str(self.config.get("legacy_verify_mode", "none")).lower().strip()

    def set_selected_legacy_verify_mode(self, mode: str):
        mode_val = self.LEGACY_VERIFY_MAP.get(mode, mode or "none")
        self.config["legacy_verify_mode"] = mode_val
        lbl = self.REVERSE_LEGACY_VERIFY_MAP.get(mode_val, self.LEGACY_VERIFY_OPTIONS[0])
        if hasattr(self, "cb_legacy_verify") and self.cb_legacy_verify:
            self.cb_legacy_verify.set(lbl)
        dash_lbl = self.REVERSE_DASH_LEGACY_VERIFY_MAP.get(mode_val, self.DASH_LEGACY_VERIFY_OPTIONS[0])
        if hasattr(self, "cb_dash_legacy_verify") and self.cb_dash_legacy_verify:
            self.cb_dash_legacy_verify.set(dash_lbl)

    def on_legacy_verify_changed(self, event=None):
        mode_val = self.get_selected_legacy_verify_mode()
        self.set_selected_legacy_verify_mode(mode_val)
        if hasattr(self, "var_reg_mode") and self.var_reg_mode.get() in ("legacy_nv", "legacy"):
            self.on_reg_mode_changed()

    def _on_dash_legacy_verify_selected(self, event=None):
        val = self.cb_dash_legacy_verify.get().strip()
        mode_val = self.DASH_LEGACY_VERIFY_MAP.get(val, "none")
        self.set_selected_legacy_verify_mode(mode_val)
        if hasattr(self, "var_reg_mode"):
            if self.var_reg_mode.get() not in ("legacy_nv", "legacy"):
                self.var_reg_mode.set("legacy_nv")
            self.on_reg_mode_changed()

    def get_selected_server_pool(self) -> list:
        pool = self.config.get("server_pool")
        if not pool or not isinstance(pool, list):
            pool = ["m.facebook.com", "mbasic.facebook.com"]
        resolved = []
        for s in pool:
            dom = self.LEGACY_SERVER_MAP.get(str(s).strip(), str(s).strip())
            if dom in self.SERVER_DOMAINS and dom not in resolved:
                resolved.append(dom)
        return resolved or ["m.facebook.com", "mbasic.facebook.com"]

    def get_current_legacy_server_options(self) -> list:
        pool = self.get_selected_server_pool()
        cnt = len(pool)
        return [
            "🎲 Random tất cả Server (1 - 10)",
            f"🎛️ Random nhóm đã chọn ({cnt}/10 server)",
            "01 - m.facebook.com (Chuẩn di động)",
            "02 - mbasic.facebook.com (HTML nhẹ)",
            "03 - touch.facebook.com (Touch)",
            "04 - free.facebook.com (Free Basics)",
            "05 - m.alpha.facebook.com (Alpha)",
            "06 - m.beta.facebook.com (Beta)",
            "07 - x.facebook.com (Data Saver)",
            "08 - limited.facebook.com (Băng thông thấp)",
            "09 - iphone.facebook.com (iOS Safari)",
            "10 - d.facebook.com (Feature Phone)",
        ]

    def get_current_dash_server_options(self) -> list:
        pool = self.get_selected_server_pool()
        cnt = len(pool)
        return [
            "🎲 Random tất cả",
            f"🎛️ Random nhóm ({cnt} srv)",
            "01 - m.facebook.com",
            "02 - mbasic.facebook.com",
            "03 - touch.facebook.com",
            "04 - free.facebook.com",
            "05 - m.alpha.facebook.com",
            "06 - m.beta.facebook.com",
            "07 - x.facebook.com",
            "08 - limited.facebook.com",
            "09 - iphone.facebook.com",
            "10 - d.facebook.com",
        ]

    def get_selected_server_mode(self) -> str:
        if hasattr(self, "var_random_server") and self.var_random_server.get():
            return "random_all"
        if hasattr(self, "cb_legacy_server"):
            val = self.cb_legacy_server.get().strip()
            if "nhóm" in val.lower() or "subset" in val.lower() or "pool" in val.lower():
                return "subset"
            if "tất cả" in val.lower() or "all" in val.lower():
                return "random_all"
            return "single"
        mode = self.config.get("server_mode", "")
        if mode in ("random_all", "subset", "single"):
            return mode
        if self.config.get("random_server"):
            return "random_all"
        if self.config.get("random_subset"):
            return "subset"
        return "single"

    def get_selected_server(self) -> str:
        mode = self.get_selected_server_mode()
        if mode == "random_all":
            return "random"
        if mode == "subset":
            return "subset"
        if hasattr(self, "cb_legacy_server"):
            val = self.cb_legacy_server.get().strip()
            return self.LEGACY_SERVER_MAP.get(val, "m.facebook.com")
        return self.config.get("server", "m.facebook.com")

    def set_server_pool(self, selected_domains: list):
        if not selected_domains:
            selected_domains = ["m.facebook.com", "mbasic.facebook.com"]
        self.config["server_pool"] = selected_domains
        cnt = len(selected_domains)

        if hasattr(self, "var_random_server"):
            self.var_random_server.set(False)

        self.config["server_mode"] = "subset"
        self.config["random_server"] = False
        self.config["random_subset"] = True

        opt_list = self.get_current_legacy_server_options()
        dash_opt_list = self.get_current_dash_server_options()

        subset_lbl = opt_list[1]
        dash_subset_lbl = dash_opt_list[1]

        if hasattr(self, "cb_legacy_server"):
            self.cb_legacy_server["values"] = opt_list
            self.cb_legacy_server.config(state="readonly")
            self.cb_legacy_server.set(subset_lbl)

        if hasattr(self, "cb_dash_legacy_server"):
            self.cb_dash_legacy_server["values"] = dash_opt_list
            self.cb_dash_legacy_server.set(dash_subset_lbl)

        if hasattr(self, "btn_legacy_pool"):
            self.btn_legacy_pool.config(text=f"🎛️ Nhóm ({cnt}/10)")

        srv_names = ", ".join([d.replace(".facebook.com", "") for d in selected_domains])
        self.log(f"[Cấu hình Server] Đã kích hoạt chế độ Random trong nhóm {cnt}/10 server: [{srv_names}]", "success")
        self.save_config(show_toast=False)

    def open_server_pool_dialog(self):
        """Hộp thoại chọn nhóm server Facebook (subset) để random luân phiên trong luồng Legacy NV."""
        dlg = tk.Toplevel(self.root)
        dlg.title("🎛️ Chọn Nhóm Server Facebook Để Random Luân Phiên (Legacy NV)")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)
        dlg.lift()
        dlg.focus_force()
        dlg.grab_set()

        dlg.update_idletasks()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        dw, dh = 640, 530
        dlg.geometry(f"{dw}x{dh}+{rx + max(0, (rw - dw) // 2)}+{ry + max(0, (rh - dh) // 2)}")
        dlg.minsize(540, 450)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        top_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=14, pady=10)
        top_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            top_frame,
            text="🎛️ CHỌN NHÓM SERVER RANDOM (SUBSET POOL)",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        ).pack(anchor="w")

        tk.Label(
            top_frame,
            text="Chọn 1 số server mong muốn trong tổng số 10 máy chủ. Hệ thống sẽ CHỈ random luân phiên\ntrong các server bạn đã tick (Ví dụ: m, mbasic, touch) thay vì random toàn bộ 10 server.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        quick_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK, padx=12, pady=4)
        quick_frame.pack(fill=tk.X)

        servers_info = [
            ("1", "m.facebook.com", "Chuẩn di động, mượt mà & phổ biến nhất ⭐"),
            ("2", "mbasic.facebook.com", "Basic HTML siêu nhẹ, không JS, bóc token rất chuẩn ⭐"),
            ("3", "touch.facebook.com", "Giao diện Touch smartphone đời cũ ⭐"),
            ("4", "free.facebook.com", "Cổng Free Basics (Zero-rated data)"),
            ("5", "m.alpha.facebook.com", "Subdomain thử nghiệm Alpha của FB"),
            ("6", "m.beta.facebook.com", "Subdomain thử nghiệm Beta của FB"),
            ("7", "x.facebook.com", "Biến thể siêu tiết kiệm dữ liệu (Data Saver)"),
            ("8", "limited.facebook.com", "Cổng kết nối băng thông giới hạn"),
            ("9", "iphone.facebook.com", "Giao diện iOS Safari / WebKit cổ điển"),
            ("10", "d.facebook.com", "Giao diện Feature phone / màn hình nhỏ"),
        ]

        current_pool = self.get_selected_server_pool()
        check_vars = {}

        list_card = tk.LabelFrame(
            dlg,
            text=" Danh sách 10 máy chủ Facebook khả dụng: ",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        list_card.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 8))

        lbl_count = tk.Label(
            list_card,
            text="",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO
        )
        lbl_count.pack(anchor="w", pady=(0, 4))

        def update_count():
            sel_cnt = sum(1 for v in check_vars.values() if v.get())
            lbl_count.config(text=f"📌 Đã chọn: {sel_cnt}/10 máy chủ để random")

        for sid, domain, desc in servers_info:
            is_checked = (domain in current_pool) or (sid in current_pool)
            var = tk.BooleanVar(value=is_checked)
            check_vars[domain] = var

            row_f = tk.Frame(list_card, bg=AppTheme.BG_CARD)
            row_f.pack(fill=tk.X, pady=1)

            chk = tk.Checkbutton(
                row_f,
                text=f"[{sid.zfill(2)}] {domain}",
                variable=var,
                command=update_count,
                font=AppTheme.FONT_BODY_BOLD if int(sid) <= 3 else AppTheme.FONT_BODY,
                bg=AppTheme.BG_CARD,
                fg=AppTheme.ACCENT if int(sid) <= 3 else AppTheme.TEXT_MAIN,
                selectcolor=AppTheme.BG_INPUT,
                activebackground=AppTheme.BG_CARD,
                anchor="w",
                width=24
            )
            chk.pack(side=tk.LEFT)

            tk.Label(
                row_f,
                text=f"- {desc}",
                font=AppTheme.FONT_SMALL,
                bg=AppTheme.BG_CARD,
                fg=AppTheme.SUCCESS if int(sid) <= 3 else AppTheme.TEXT_MUTED
            ).pack(side=tk.LEFT, padx=(4, 0))

        def select_top3():
            for d, v in check_vars.items():
                v.set(d in ("m.facebook.com", "mbasic.facebook.com"))
            update_count()

        def select_all():
            for v in check_vars.values():
                v.set(True)
            update_count()

        def deselect_all():
            for v in check_vars.values():
                v.set(False)
            update_count()

        btn_top3 = tk.Button(
            quick_frame,
            text="⭐ Chọn Top 3 Ngon Nhất (m, mbasic, touch)",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=select_top3
        )
        btn_top3.pack(side=tk.LEFT, padx=(0, 6))

        btn_all = tk.Button(
            quick_frame,
            text="✅ Chọn Tất Cả (10)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=select_all
        )
        btn_all.pack(side=tk.LEFT, padx=(0, 6))

        btn_none = tk.Button(
            quick_frame,
            text="❌ Bỏ Chọn Hết",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MUTED,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=deselect_all
        )
        btn_none.pack(side=tk.LEFT)

        update_count()

        bot_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK, padx=12, pady=10)
        bot_bar.pack(fill=tk.X)

        def save_and_apply():
            selected_domains = [d for d, v in check_vars.items() if v.get()]
            if not selected_domains:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 server để đưa vào nhóm random!")
                return
            self.set_server_pool(selected_domains)
            dlg.destroy()

        btn_save = tk.Button(
            bot_bar,
            text="💾 ÁP DỤNG & LƯU NHÓM SERVER",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg=AppTheme.BG_DARK,
            activebackground=AppTheme.ACCENT_HOVER,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=save_and_apply
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn_cancel = tk.Button(
            bot_bar,
            text="Đóng",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=14,
            pady=8,
            cursor="hand2",
            command=dlg.destroy
        )
        btn_cancel.pack(side=tk.RIGHT)

    def set_selected_server(self, server_val: str, is_random: bool = False):
        if is_random or str(server_val).lower() in ("random", "all"):
            if hasattr(self, "var_random_server"):
                self.var_random_server.set(True)
            if hasattr(self, "cb_legacy_server"):
                self.cb_legacy_server.set("🎲 Random tất cả Server (1 - 10)")
                self.cb_legacy_server.config(state="disabled")
            if hasattr(self, "cb_dash_legacy_server"):
                self.cb_dash_legacy_server.set("🎲 Random tất cả")
            self.config["server_mode"] = "random_all"
            self.config["random_server"] = True
            self.config["random_subset"] = False
            self.config["server"] = "random"
        else:
            if hasattr(self, "var_random_server"):
                self.var_random_server.set(False)
            self.config["server_mode"] = "single"
            self.config["random_server"] = False
            self.config["random_subset"] = False
            lbl = self.REVERSE_LEGACY_SERVER_MAP.get(server_val, "01 - m.facebook.com (Chuẩn di động)")
            dash_lbl = self.REVERSE_DASH_LEGACY_SERVER_MAP.get(server_val, "01 - m.facebook.com")
            if hasattr(self, "cb_legacy_server"):
                self.cb_legacy_server.config(state="readonly")
                self.cb_legacy_server.set(lbl)
            if hasattr(self, "cb_dash_legacy_server"):
                self.cb_dash_legacy_server.set(dash_lbl)
            self.config["server"] = self.LEGACY_SERVER_MAP.get(lbl, server_val)

    def on_random_server_toggled(self):
        is_rand = self.var_random_server.get()
        if is_rand:
            self.config["server_mode"] = "random_all"
            self.config["random_server"] = True
            self.config["random_subset"] = False
            self.config["server"] = "random"
            if hasattr(self, "cb_legacy_server"):
                self.cb_legacy_server.set("🎲 Random tất cả Server (1 - 10)")
                self.cb_legacy_server.config(state="disabled")
            if hasattr(self, "cb_dash_legacy_server"):
                self.cb_dash_legacy_server.set("🎲 Random tất cả")
            self.log("[Cấu hình Server] Đã BẬT tự động Random tất cả 10 server Facebook cho mỗi lượt reg", "info")
        else:
            self.config["server_mode"] = "single"
            self.config["random_server"] = False
            self.config["random_subset"] = False
            cur_s = self.config.get("server", "m.facebook.com")
            if str(cur_s).lower() in ("random", "all", "subset"):
                cur_s = "m.facebook.com"
            self.config["server"] = cur_s
            lbl = self.REVERSE_LEGACY_SERVER_MAP.get(cur_s, "01 - m.facebook.com (Chuẩn di động)")
            dash_lbl = self.REVERSE_DASH_LEGACY_SERVER_MAP.get(cur_s, "01 - m.facebook.com")
            if hasattr(self, "cb_legacy_server"):
                self.cb_legacy_server.config(state="readonly")
                self.cb_legacy_server.set(lbl)
            if hasattr(self, "cb_dash_legacy_server"):
                self.cb_dash_legacy_server.set(dash_lbl)
            self.log(f"[Cấu hình Server] Đã TẮT Random server, sử dụng cố định: {cur_s}", "info")

    def on_legacy_server_changed(self, event=None):
        val = self.cb_legacy_server.get().strip()
        if "nhóm" in val.lower() or "subset" in val.lower() or "pool" in val.lower():
            pool = self.get_selected_server_pool()
            self.set_server_pool(pool)
        elif "tất cả" in val.lower() or "random" in val.lower():
            if hasattr(self, "var_random_server"):
                self.var_random_server.set(True)
            self.on_random_server_toggled()
        else:
            server_val = self.LEGACY_SERVER_MAP.get(val, "m.facebook.com")
            if hasattr(self, "var_random_server"):
                self.var_random_server.set(False)
            self.config["server_mode"] = "single"
            self.config["random_server"] = False
            self.config["random_subset"] = False
            self.config["server"] = server_val
            if hasattr(self, "cb_legacy_server"):
                self.cb_legacy_server.config(state="readonly")
            dash_lbl = self.REVERSE_DASH_LEGACY_SERVER_MAP.get(server_val, "01 - m.facebook.com")
            if hasattr(self, "cb_dash_legacy_server"):
                self.cb_dash_legacy_server.set(dash_lbl)
            self.log(f"[Cấu hình Server] Đã chọn cố định: {server_val}", "info")

    def _on_dash_legacy_server_selected(self, event=None):
        val = self.cb_dash_legacy_server.get().strip()
        if "nhóm" in val.lower() or "subset" in val.lower() or "srv" in val.lower():
            pool = self.get_selected_server_pool()
            self.set_server_pool(pool)
        elif "tất cả" in val.lower() or "random" in val.lower():
            if hasattr(self, "var_random_server"):
                self.var_random_server.set(True)
            self.on_random_server_toggled()
        else:
            server_val = self.DASH_LEGACY_SERVER_MAP.get(val, "m.facebook.com")
            if hasattr(self, "var_random_server"):
                self.var_random_server.set(False)
            self.config["server_mode"] = "single"
            self.config["random_server"] = False
            self.config["random_subset"] = False
            self.config["server"] = server_val
            lbl = self.REVERSE_LEGACY_SERVER_MAP.get(server_val, "01 - m.facebook.com (Chuẩn di động)")
            if hasattr(self, "cb_legacy_server"):
                self.cb_legacy_server.config(state="readonly")
                self.cb_legacy_server.set(lbl)
            self.log(f"[Cấu hình Server] Đã chọn cố định: {server_val}", "info")

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TOOL REG FB ĐA LUỒNG - VR OTP & NVR ENGINE")
        self.root.geometry("1360x880")
        self.root.minsize(1120, 720)
        self.root.configure(bg=AppTheme.BG_DARK)

        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.session_path = os.path.join(os.path.dirname(__file__), "table_session.json")
        self.config = self.load_config()

        # Quản lý KiotProxy keys và chế độ che/ẩn an toàn
        saved_keys = self.config.get("kiotproxy_keys", [])
        if isinstance(saved_keys, str):
            saved_keys = [k.strip() for k in saved_keys.splitlines() if k.strip()]
        if not saved_keys:
            saved_keys = [
                "Kf93750f36424428ebd93f4f8bb062327",
                "K5b126d6c1903450d835aa524892b2cff"
            ]
        self._raw_kiot_keys = list(saved_keys)

        # Quản lý ProxySocks5.vn keys và user token
        saved_psocks5_keys = self.config.get("proxysocks5_keys", [])
        if isinstance(saved_psocks5_keys, str):
            saved_psocks5_keys = [k.strip() for k in saved_psocks5_keys.splitlines() if k.strip()]
        self._raw_proxysocks5_keys = list(saved_psocks5_keys)
        self.proxysocks5_user_token = self.config.get("proxysocks5_user_token", "QosKHIjPqRnaoQgR6qs4UEkrC6EwXx")

        # Quản lý mProxy.vn (Proxy 4G/5G xoay IP)
        self.mproxy_token = self.config.get("mproxy_token", "CncgWVg-ppCxg7EwH7dFS6ICuv8hzXLaJdF-rzoXQAU")
        saved_mproxy_keys = self.config.get("mproxy_keys", [])
        if isinstance(saved_mproxy_keys, str):
            saved_mproxy_keys = [k.strip() for k in saved_mproxy_keys.splitlines() if k.strip()]
        self._raw_mproxy_keys = list(saved_mproxy_keys)

        # Quản lý Proxy.vn (proxyxoay.shop) keys
        saved_proxyvn_keys = self.config.get("proxyvn_keys", [])
        if isinstance(saved_proxyvn_keys, str):
            saved_proxyvn_keys = [k.strip() for k in saved_proxyvn_keys.splitlines() if k.strip()]
        if not saved_proxyvn_keys:
            saved_proxyvn_keys = ["LdeNrJVTorbBBmKBqoYdnO"]
        self._raw_proxyvn_keys = list(saved_proxyvn_keys)

        self._prev_proxy_provider = self.config.get("proxy_provider", "kiotproxy")
        self._auto_rotate_thread_running = False
        self._last_auto_rotate_time = time.time()

        self.keys_masked = False

        # Hỏi xác nhận khi tắt tool
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

        self.event_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.is_running = False
        self._row_full_lines = {}
        self._worker_proxy_map = {}
        self._tree_items_by_uid = {}
        self._worker_item_map = {}
        self._worker_target_map = {}
        self.nvr_accounts_queue = []

        self.stat_total = 0
        self.stat_success = 0
        self.stat_failed = 0
        self.stat_unverified = 0

        self.session_new_success = 0
        self.session_new_unver = 0
        self.session_new_failed = 0

        self.worker_threads = []
        self.row_counter = 0
        self._row_full_lines = {}
        self._file_save_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="AsyncFileSaver")
        self.var_bot_auto_upload = tk.BooleanVar(value=bool(self.config.get("bot_auto_upload", False)))
        self.var_enable_verry_pipeline = tk.BooleanVar(value=bool(self.config.get("enable_verry_pipeline", True)))
        self.var_verry_pipeline_delay = tk.StringVar(value=str(self.config.get("verry_pipeline_delay", "2 phút (Khuyến nghị)")))
        self.var_verry_pipeline_threads = tk.StringVar(value=str(self.config.get("verry_pipeline_threads", 50)))
        self.var_verry_pipeline_dir = tk.StringVar(value=str(self.config.get("verry_pipeline_dir", r"C:\Users\truon\Downloads\verry")))
        self.stat_bot_uploaded = 0
        self._cached_subcat_info = None
        self._bot_uploaded_uids = set()
        self._bot_upload_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="BotUploader")
        self._log_line_count = 0

        self.setup_styles()
        self.build_ui()
        self.build_context_menu()
        self.refresh_hotmail_count()
        self.load_table_session()

        # Không tự động nạp dữ liệu cũ vào bảng khi khởi động tool (tránh gây nhầm lẫn khi người dùng chưa thêm tài khoản)

        self._pipeline_ready_times = {}
        self.root.bind("<FocusIn>", self._on_window_focus)
        self.root.after(100, self.process_queue_events)
        self.root.after(1000, self._pipeline_sync_tick)
        if self.config.get("auto_rotate_proxy", False):
            self.root.after(2000, self._ensure_auto_rotate_daemon_running)

    def load_config(self) -> Dict[str, Any]:
        cfg = {
            "mode": "web",
            "reg_mode": "vr",
            "legacy_verify_mode": "none",
            "threads": 4,
            "max_accounts": 10,
            "enable_2fa": True,
            "auto_ttc_pipeline": False,
            "bait_mode": "phone",
            "enable_bait_retry": True,
            "bait_retries": 3,
            "use_bait_phone": True,
            "use_bait_gmail": False,
            "auto_gen_phone": True,
            "name_type": "vietnamese",
            "custom_name_file": "names.txt",
            "mix_file_names": False,
            "email_service": "dongvanfb",
            "proxy_provider": "kiotproxy",
            "proxy_alloc_mode": "dedicated",
            "kiotproxy_keys": ["Kf93750f36424428ebd93f4f8bb062327", "K5b126d6c1903450d835aa524892b2cff"],
            "proxysocks5_keys": [],
            "proxysocks5_user_token": "QosKHIjPqRnaoQgR6qs4UEkrC6EwXx",
            "mproxy_token": "CncgWVg-ppCxg7EwH7dFS6ICuv8hzXLaJdF-rzoXQAU",
            "mproxy_keys": [],
            "proxyvn_keys": ["LdeNrJVTorbBBmKBqoYdnO"],
            "auto_rotate_proxy": False,
            "auto_rotate_interval": "60s (1 phút)",
            "device_type": "mr_sxr",
            "save_format": "UID|PASS|2FA|COOKIE|TOKEN|EMAIL",
            "output_live_file": "accounts_live.txt",
            "output_die_file": "accounts_die.txt",
            "output_unver_file": "accounts_unverified.txt",
            "metaking_api_key": "",
            "metaking_service_type": "email",
            "metaking_server": 1,
            "metaking_domain": "gmail.com",
            "metaking_service_id": 67,
            "metaking_country_id": 154,
            "metaking_price": "low",
            "bot_auto_upload": False,
            "bot_media_id": "0AgACAgUAAxUAAWrdTEFel8nwqyfqdm-JW5tDEZQ-AAJmE2sbA8fhVvptkVWyk7XSAQADAgADYwADPQQ",
            "bot_api_url": "https://shopcl.onrender.com",
            "bot_api_key": "MatKhauAdminCuaBan123",
            "enable_verry_pipeline": True,
            "verry_pipeline_delay": "2 phút (Khuyến nghị)",
            "verry_pipeline_threads": 50,
            "verry_pipeline_dir": r"C:\Users\truon\Downloads\verry",
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                    cfg.update(data)
                    if "bait_mode" not in data:
                        if data.get("use_bait_gmail"):
                            cfg["bait_mode"] = "gmail"
                        elif data.get("use_bait_phone") is not None:
                            cfg["bait_mode"] = "phone" if bool(data.get("use_bait_phone")) else "none"
                        elif data.get("auto_gen_phone") is not None:
                            cfg["bait_mode"] = "phone" if bool(data.get("auto_gen_phone")) else "none"
                        else:
                            cfg["bait_mode"] = "phone" 
                    cfg["enable_bait_retry"] = bool(data.get("enable_bait_retry", True))
                    if "bait_retries" in data:
                        try:
                            cfg["bait_retries"] = max(1, min(10, int(data["bait_retries"])))
                        except Exception:
                            cfg["bait_retries"] = 3
                    if "kiotproxy_api_key" in data and not cfg.get("kiotproxy_keys"):
                        cfg["kiotproxy_keys"] = [data["kiotproxy_api_key"]]
                    if "proxysocks5_keys" in data:
                        if isinstance(data["proxysocks5_keys"], list):
                            cfg["proxysocks5_keys"] = data["proxysocks5_keys"]
                        elif isinstance(data["proxysocks5_keys"], str):
                            cfg["proxysocks5_keys"] = [k.strip() for k in data["proxysocks5_keys"].splitlines() if k.strip()]
                    if "proxysocks5_user_token" in data:
                        cfg["proxysocks5_user_token"] = str(data["proxysocks5_user_token"]).strip()
                    if "mproxy_token" in data:
                        cfg["mproxy_token"] = str(data["mproxy_token"]).strip()
                    if "mproxy_keys" in data:
                        if isinstance(data["mproxy_keys"], list):
                            cfg["mproxy_keys"] = data["mproxy_keys"]
                        elif isinstance(data["mproxy_keys"], str):
                            cfg["mproxy_keys"] = [k.strip() for k in data["mproxy_keys"].splitlines() if k.strip()]
                    if "proxyvn_keys" in data:
                        if isinstance(data["proxyvn_keys"], list):
                            cfg["proxyvn_keys"] = [k.strip() for k in data["proxyvn_keys"] if str(k).strip()]
                        elif isinstance(data["proxyvn_keys"], str):
                            cfg["proxyvn_keys"] = [k.strip() for k in data["proxyvn_keys"].splitlines() if k.strip()]
                    if "auto_rotate_proxy" in data:
                        cfg["auto_rotate_proxy"] = bool(data["auto_rotate_proxy"])
                    if "auto_rotate_interval" in data:
                        cfg["auto_rotate_interval"] = str(data["auto_rotate_interval"])
            except Exception:
                pass
        if cfg.get("max_accounts", 0) <= 0:
            cfg["max_accounts"] = 10
        return cfg

    @staticmethod
    def mask_key(k: str) -> str:
        k = (k or "").strip()
        if not k:
            return ""
        if len(k) <= 8:
            return "*" * len(k)
        return k[:4] + ("*" * (len(k) - 8)) + k[-4:]

    @staticmethod
    def mask_ip(text: str) -> str:
        if not text or text in ("Direct", "(Chờ cấp IP)", "N/A", "(Không proxy)"):
            return text
        s = str(text)
        cached = _MASK_IP_CACHE.get(s)
        if cached is not None:
            return cached

        res = s
        if "://" in res and "@" in res:
            res = _RE_URL_AUTH.sub(r"://***:***@", res)
        if "." in res:
            def _repl(m):
                prefix = m.group(1)
                port = m.group(2) or ""
                return f"{prefix}.***.***{port}"
            res = _RE_IPV4.sub(_repl, res)
        if len(res) >= 28:
            def _repl_key(m):
                k = m.group(0)
                return k[:4] + "*" * (len(k) - 8) + k[-4:]
            res = _RE_API_KEY.sub(_repl_key, res)

        if len(_MASK_IP_CACHE) >= _MASK_IP_CACHE_MAX:
            _MASK_IP_CACHE.clear()
        _MASK_IP_CACHE[s] = res
        return res

    def get_proxysocks5_keys(self) -> List[str]:
        raw_keys = getattr(self, "_raw_proxysocks5_keys", [])
        if not raw_keys:
            raw_keys = self.config.get("proxysocks5_keys", [])
            if isinstance(raw_keys, str):
                raw_keys = [k.strip() for k in raw_keys.splitlines() if k.strip()]
            self._raw_proxysocks5_keys = list(raw_keys)

        prov = self.get_selected_proxy_provider()
        if prov == "proxysocks5" and hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
            content = self.txt_proxy_keys.get("1.0", tk.END)
            c_lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
            if c_lines and not any("*" in l for l in c_lines):
                self._raw_proxysocks5_keys = c_lines
                self.config["proxysocks5_keys"] = c_lines

        return [k for k in self._raw_proxysocks5_keys if k and "*" not in k]

    def get_kiotproxy_keys(self) -> List[str]:
        raw_keys = getattr(self, "_raw_kiot_keys", [])
        if not raw_keys:
            raw_keys = self.config.get("kiotproxy_keys", [])
            if isinstance(raw_keys, str):
                raw_keys = [k.strip() for k in raw_keys.splitlines() if k.strip()]
            self._raw_kiot_keys = list(raw_keys)

        prov = self.get_selected_proxy_provider()
        if prov in ("kiotproxy", "kiotproxy_current") and hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
            content = self.txt_proxy_keys.get("1.0", tk.END)
            c_lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
            if c_lines and not any("*" in l for l in c_lines):
                self._raw_kiot_keys = c_lines
                self.config["kiotproxy_keys"] = c_lines
                if c_lines:
                    self.config["kiotproxy_api_key"] = c_lines[0]

        return [k for k in self._raw_kiot_keys if k and "*" not in k]

    def get_mproxy_token(self) -> str:
        tok = getattr(self, "mproxy_token", "") or self.config.get("mproxy_token", "CncgWVg-ppCxg7EwH7dFS6ICuv8hzXLaJdF-rzoXQAU")
        prov = self.get_selected_proxy_provider()
        if prov == "mproxy" and hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
            content = self.txt_proxy_keys.get("1.0", tk.END)
            c_lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
            for l in c_lines:
                if len(l) >= 25 and ("-" in l or "_" in l) and " " not in l and "*" not in l:
                    tok = l
                    self.mproxy_token = tok
                    self.config["mproxy_token"] = tok
                    break
        return tok

    def get_mproxy_keys(self) -> List[str]:
        raw_keys = getattr(self, "_raw_mproxy_keys", [])
        if not raw_keys:
            raw_keys = self.config.get("mproxy_keys", [])
            if isinstance(raw_keys, str):
                raw_keys = [k.strip() for k in raw_keys.splitlines() if k.strip()]
            self._raw_mproxy_keys = list(raw_keys)

        prov = self.get_selected_proxy_provider()
        if prov == "mproxy" and hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
            content = self.txt_proxy_keys.get("1.0", tk.END)
            c_lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
            valid_lines = [l for l in c_lines if "*" not in l]
            if valid_lines:
                for l in valid_lines:
                    if len(l) >= 25 and ("-" in l or "_" in l) and " " not in l:
                        self.mproxy_token = l
                        self.config["mproxy_token"] = l
                        break
                keys_only = [l for l in valid_lines if l != getattr(self, "mproxy_token", "")]
                if keys_only:
                    self._raw_mproxy_keys = keys_only
                    self.config["mproxy_keys"] = keys_only
                else:
                    self._raw_mproxy_keys = valid_lines
                    self.config["mproxy_keys"] = valid_lines

        # Lọc bỏ các key nhầm từ nhà cung cấp khác (KiotProxy K..., ProxySocks5 WHNP...)
        cleaned_mp_keys = []
        for k in getattr(self, "_raw_mproxy_keys", []):
            k_s = str(k).strip()
            if not k_s or "*" in k_s:
                continue
            if k_s.startswith("K") and len(k_s) == 33 and all(c in "0123456789abcdefABCDEF" for c in k_s[1:]):
                continue
            if len(k_s) == 21 and k_s.isalnum() and not (":" in k_s or "-" in k_s):
                continue
            cleaned_mp_keys.append(k_s)
        self._raw_mproxy_keys = cleaned_mp_keys

        res_keys = list(self._raw_mproxy_keys)
        tok = self.get_mproxy_token()
        if (not res_keys or len(res_keys) <= 1 or (len(res_keys) == 1 and res_keys[0] == tok)) and tok:
            try:
                fetched = MproxyClient.get_keys(tok)
                if fetched:
                    f_keys = []
                    for k_info in fetched:
                        srv_h = k_info.get("server_host") or "ip.mproxy.vn"
                        srv_p = k_info.get("server_port")
                        usr = k_info.get("user") or ""
                        pwd = k_info.get("password") or k_info.get("key_code") or ""
                        if srv_p:
                            f_keys.append(f"{srv_h}:{srv_p}:{usr}:{pwd}" if usr and pwd else f"{srv_h}:{srv_p}")
                        elif k_info.get("key_code"):
                            f_keys.append(str(k_info.get("key_code")))
                    if f_keys:
                        res_keys = f_keys
                        self._raw_mproxy_keys = f_keys
                        self.config["mproxy_keys"] = f_keys
            except Exception:
                pass

        return res_keys if res_keys else ([tok] if tok else [])

    def get_proxyvn_keys(self) -> List[str]:
        raw_keys = getattr(self, "_raw_proxyvn_keys", [])
        if not raw_keys:
            raw_keys = self.config.get("proxyvn_keys", [])
            if isinstance(raw_keys, str):
                raw_keys = [k.strip() for k in raw_keys.splitlines() if k.strip()]
            if not raw_keys:
                raw_keys = ["LdeNrJVTorbBBmKBqoYdnO"]
            self._raw_proxyvn_keys = list(raw_keys)

        prov = self.get_selected_proxy_provider()
        if prov == "proxyvn" and hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
            content = self.txt_proxy_keys.get("1.0", tk.END)
            c_lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
            if c_lines and not any("*" in l for l in c_lines):
                self._raw_proxyvn_keys = c_lines
                self.config["proxyvn_keys"] = c_lines

        return [k for k in self._raw_proxyvn_keys if k and "*" not in k]

    def get_proxy_file_path(self) -> str:
        if hasattr(self, "entry_proxy_filepath") and self.entry_proxy_filepath.winfo_exists():
            val = self.entry_proxy_filepath.get().strip().strip('"\'')
            if val:
                norm_p = os.path.normpath(val)
                self.config["proxy_file_path"] = norm_p
                return norm_p
        p = self.config.get("proxy_file_path", "proxy.txt")
        if not p or not str(p).strip():
            p = "proxy.txt"
        return os.path.normpath(str(p).strip().strip('"\''))

    def load_proxy_file_content(self) -> str:
        filepath = self.get_proxy_file_path()
        abs_path = filepath if os.path.isabs(filepath) else os.path.join(os.path.dirname(__file__), filepath)
        if not os.path.exists(abs_path):
            if os.path.exists("proxies.txt"):
                abs_path = "proxies.txt"
                self.config["proxy_file_path"] = "proxies.txt"
            else:
                saved = self.config.get("proxy_list", [])
                if saved:
                    return "\n".join(saved)
                return ""
        try:
            with open(abs_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Error reading proxy file {abs_path}: {e}")
            return ""

    def get_file_proxies(self) -> List[str]:
        filepath = self.get_proxy_file_path()
        abs_path = filepath if os.path.isabs(filepath) else os.path.join(os.path.dirname(__file__), filepath)
        if not os.path.exists(abs_path):
            if os.path.exists("proxy.txt"):
                abs_path = "proxy.txt"
                self.config["proxy_file_path"] = "proxy.txt"
            elif os.path.exists("proxies.txt"):
                abs_path = "proxies.txt"
                self.config["proxy_file_path"] = "proxies.txt"
            elif os.path.exists("free_proxies.txt"):
                abs_path = "free_proxies.txt"
                self.config["proxy_file_path"] = "free_proxies.txt"
            else:
                raw_cfg = self.config.get("proxy_list", [])
                clean_res = []
                seen_res = set()
                for p in raw_cfg:
                    s = str(p).replace("\ufeff", "").replace("\xa0", " ").strip()
                    for tok in re.split(r'[\s\t,;]+', s):
                        tok = tok.strip()
                        if "|" in tok:
                            tok = tok.split("|")[0].strip()
                        if tok and ":" in tok and not tok.startswith("#") and not tok.startswith("//"):
                            if tok not in seen_res:
                                seen_res.add(tok)
                                clean_res.append(tok)
                return clean_res

        try:
            clean_lines = []
            seen = set()
            with open(abs_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                for line in f:
                    s = line.lstrip("\ufeff").replace("\xa0", " ").strip()
                    if not s or s.startswith("#") or s.startswith("//"):
                        continue
                    if "|" in s:
                        s = s.split("|")[0].strip()
                    tokens = re.split(r'[\s\t,;]+', s)
                    for tok in tokens:
                        tok = tok.strip()
                        if tok and ":" in tok and not tok.startswith("#") and not tok.startswith("//"):
                            if tok not in seen:
                                seen.add(tok)
                                clean_lines.append(tok)
                    if len(clean_lines) >= 10000:
                        break
            if len(clean_lines) <= 200:
                self.config["proxy_list"] = clean_lines
            else:
                self.config["proxy_list"] = clean_lines[:200]
            return clean_lines
        except Exception as e:
            logger.warning(f"Error reading proxy file {abs_path}: {e}")
            return [p.strip() for p in self.config.get("proxy_list", []) if str(p).strip()]

    def on_proxy_filepath_entry_changed(self):
        if not hasattr(self, "entry_proxy_filepath"):
            return
        new_val = self.entry_proxy_filepath.get().strip()
        if not new_val:
            new_val = "proxy.txt"
            self.entry_proxy_filepath.delete(0, tk.END)
            self.entry_proxy_filepath.insert(0, new_val)
        self.config["proxy_file_path"] = new_val
        self.save_config()
        self.update_file_proxy_panel()
        try:
            from core.proxy_manager import FreeProxyManager
            FreeProxyManager().auto_save_file = new_val
        except Exception:
            pass

    def update_file_proxy_panel(self):
        if not hasattr(self, "panel_proxy_file"):
            return
        p_file = self.get_proxy_file_path()
        abs_p = p_file if os.path.isabs(p_file) else os.path.abspath(p_file)
        cnt = 0
        if os.path.exists(abs_p):
            try:
                with open(abs_p, "rb") as f_cnt:
                    cnt = sum(1 for line in f_cnt if line.strip() and not line.strip().startswith(b"#") and not line.strip().startswith(b"//"))
            except Exception:
                cnt = len(self.get_file_proxies())
        else:
            cnt = 0
        bname = os.path.basename(p_file)
        if hasattr(self, "entry_proxy_filepath"):
            self.entry_proxy_filepath.delete(0, tk.END)
            self.entry_proxy_filepath.insert(0, abs_p)
        if hasattr(self, "lbl_file_proxy_summary"):
            if bname in ("proxy_all_sources.txt", "all_scraped_proxies_raw.txt"):
                self.lbl_file_proxy_summary.config(
                    text=f"⚠️ File '{bname}' ({cnt} proxy) là KHO THÔ CHƯA LỌC. Hãy chọn 'proxy.txt' (Live FB) để chạy mượt!",
                    fg=AppTheme.WARNING
                )
            elif cnt > 0:
                self.lbl_file_proxy_summary.config(
                    text=f"📊 File '{bname}': Đã nạp thành công {cnt} proxy hợp lệ (Mỗi luồng tự động bốc ngẫu nhiên)",
                    fg=AppTheme.SUCCESS
                )
            else:
                self.lbl_file_proxy_summary.config(
                    text=f"⚠️ File '{bname}' đang rỗng hoặc chưa có proxy hợp lệ (Định dạng: ip:port hoặc ip:port:user:pass)",
                    fg=AppTheme.WARNING
                )
        if hasattr(self, "card_proxy"):
            self.card_proxy.config(text=f" 📁 2. Cấu hình Proxy (File: {bname}) ")
        if hasattr(self, "lbl_kiot_status"):
            self.lbl_kiot_status.config(text=f"📁 File '{bname}': {cnt} proxy khả dụng (Bốc ngẫu nhiên)", fg=AppTheme.INFO)

    def pick_random_proxy_preview(self):
        proxies = self.get_file_proxies()
        if not proxies:
            messagebox.showwarning("Thông báo", "File proxy rỗng hoặc không tìm thấy proxy hợp lệ!\nVui lòng chọn file có chứa proxy theo định dạng ip:port hoặc ip:port:user:pass (mỗi dòng 1 proxy).")
            return
        p_random = random.choice(proxies)
        messagebox.showinfo(
            "🎲 Bốc Thử Proxy Ngẫu Nhiên",
            f"🎲 Proxy ngẫu nhiên được chọn:\n\n👉  {p_random}\n\n"
            f"📦 Tổng kho proxy: {len(proxies)} proxy hợp lệ.\n\n"
            f"💡 Cơ chế hoạt động:\n"
            f"- Khi bạn bấm 'Bắt Đầu Tạo Nick', mỗi luồng ({self.spn_threads.get() if hasattr(self, 'spn_threads') else 'đa'} luồng) sẽ tự động bốc ngẫu nhiên 1 proxy từ file này.\n"
            f"- Các luồng chạy song song không bị trùng IP với nhau!"
        )


    def open_proxy_file(self):
        filename = self.get_proxy_file_path()
        filepath = filename if os.path.isabs(filename) else os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(filepath):
            try:
                with open(filepath, "w", encoding="utf-8-sig") as f:
                    f.write("# Danh sách Proxy (Mỗi dòng 1 proxy)\n# Hỗ trợ định dạng:\n# ip:port\n# user:pass@ip:port\n# socks5://ip:port\n# http://ip:port\n")
            except Exception as e:
                self.log(f"[Proxy List] ⚠️ Không thể tạo file {filename}: {e}", "error")
                return
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            else:
                subprocess.Popen(["xdg-open", filepath])
            self.log(f"[Proxy List] 📂 Đã mở file proxy: {filename}", "info")
        except Exception as e:
            self.log(f"[Proxy List] ⚠️ Lỗi mở file {filename}: {e}", "error")

    def open_bad_proxy_file(self):
        filename = "proxy_loi.txt"
        filepath = filename if os.path.isabs(filename) else os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(filepath):
            try:
                with open(filepath, "w", encoding="utf-8-sig") as f:
                    f.write("# Danh sách Proxy Lỗi / Chết (Tự động loại bỏ trong quá trình chạy)\n# Định dạng: ip:port # Lý do - Thời gian\n")
            except Exception as e:
                self.log(f"[Proxy Lỗi] ⚠️ Không thể tạo file {filename}: {e}", "error")
                return
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            else:
                subprocess.Popen(["xdg-open", filepath])
            self.log(f"[Proxy Lỗi] 📂 Đã mở file proxy lỗi: {filename}", "info")
        except Exception as e:
            self.log(f"[Proxy Lỗi] ⚠️ Lỗi mở file {filename}: {e}", "error")

    def _on_toggle_filter_bad_proxy(self):
        val = bool(self.var_filter_bad_proxy_from_file.get())
        self.config["filter_bad_proxy_from_file"] = val
        self.save_config()
        self.log(f"[Proxy List] {'🗑️ ĐÃ BẬT' if val else '⚪ ĐÃ TẮT'} chế độ tự động lọc bỏ Proxy lỗi khỏi file khi chạy", "info")

    def import_proxy_file(self):
        init_dir = os.path.dirname(os.path.abspath(__file__))
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Chọn file Proxy (.txt)",
            initialdir=init_dir,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if selected:
            try:
                rel = os.path.relpath(selected, init_dir)
                if not rel.startswith(".."):
                    selected = rel
            except Exception:
                pass
            self.config["proxy_file_path"] = selected
            self.save_config()
            try:
                from core.proxy_manager import FreeProxyManager
                FreeProxyManager().auto_save_file = selected
            except Exception:
                pass
            self.update_file_proxy_panel()
            self.reload_proxy_file()
            self.log(f"[Proxy List] 📥 Đã nạp thành công file proxy: {selected}", "success")

    def reload_proxy_file(self):
        filepath = self.get_proxy_file_path()
        abs_path = filepath if os.path.isabs(filepath) else os.path.join(os.path.dirname(__file__), filepath)
        if not os.path.exists(abs_path):
            if os.path.exists("proxies.txt"):
                abs_path = "proxies.txt"
                self.config["proxy_file_path"] = "proxies.txt"
                filepath = "proxies.txt"
            else:
                self.log(f"[Proxy List] ⚠️ Không tìm thấy file: {filepath}", "warning")
                return

        try:
            lines = self.get_file_proxies()
            bname = os.path.basename(filepath)
            cnt = len(lines)
            self.update_file_proxy_panel()
            self.log(f"[Proxy List] 🔄 Đã nạp thành công {cnt} proxy từ '{filepath}'!", "info")
        except Exception as e:
            self.log(f"[Proxy List] ⚠️ Lỗi khi tải file proxy {filepath}: {e}", "error")

    def save_proxies_to_file(self, show_msg: bool = True):
        if not hasattr(self, "txt_proxy_keys") or not self.txt_proxy_keys.winfo_exists():
            return
        content = self.txt_proxy_keys.get("1.0", tk.END).strip()
        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
        if not lines:
            if show_msg:
                self.log(f"[Proxy List] ⚠️ Ô nhập trống, không ghi đè làm trống file proxy!", "warning")
            return
        filepath = self.get_proxy_file_path()
        abs_path = filepath if os.path.isabs(filepath) else os.path.join(os.path.dirname(__file__), filepath)
        try:
            with open(abs_path, "w", encoding="utf-8-sig") as f:
                f.write(content + "\n")
            if len(lines) <= 200:
                self.config["proxy_list"] = lines
            else:
                self.config["proxy_list"] = lines[:200]
            self.config["proxy_file_path"] = filepath
            bname = os.path.basename(filepath)
            cnt = len(lines)
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=f" 📁 2. Cấu hình Proxy (File: {bname}) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text=f"Danh sách Proxy từ '{bname}' ({cnt} proxy):")
            if hasattr(self, "lbl_kiot_status"):
                self.lbl_kiot_status.config(text=f"📁 File '{bname}': {cnt} proxy khả dụng", fg=AppTheme.INFO)
            if show_msg:
                self.log(f"[Proxy List] 💾 Đã lưu thành công {cnt} proxy vào file '{filepath}'!", "success")
        except Exception as e:
            if show_msg:
                self.log(f"[Proxy List] ⚠️ Lỗi khi lưu file {filepath}: {e}", "error")

    def append_live_proxies_to_file(self, live_proxies) -> int:
        """
        Tự động lưu / nối các proxy LIVE vào file proxy đang được cấu hình trong settings.
        Đảm bảo định dạng chuẩn (host:port hoặc protocol://host:port) và không bị trùng lặp.
        """
        if not live_proxies:
            return 0

        target_file = self.get_proxy_file_path()
        abs_path = target_file if os.path.isabs(target_file) else os.path.join(os.path.dirname(__file__), target_file)

        existing_hosts_ports = set()
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8-sig", errors="ignore") as f_in:
                    for line in f_in:
                        s = line.strip()
                        if not s or s.startswith("#") or s.startswith("//"):
                            continue
                        m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[: ]+(\d{2,5})', s)
                        if m:
                            existing_hosts_ports.add(f"{m.group(1)}:{m.group(2)}")
            except Exception as e_read:
                logger.debug(f"Error reading existing proxy file: {e_read}")

        new_lines_to_add = []
        for p in live_proxies:
            raw_str = ""
            host_port = ""
            if hasattr(p, "to_standard_format"):
                raw_str = p.to_standard_format()
                host_port = f"{getattr(p, 'host', '')}:{getattr(p, 'port', '')}"
            elif isinstance(p, str):
                raw_str = p.strip()
                m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[: ]+(\d{2,5})', raw_str)
                if m:
                    host_port = f"{m.group(1)}:{m.group(2)}"
            elif isinstance(p, dict):
                raw_str = p.get("proxy") or f"{p.get('host')}:{p.get('port')}"
                host_port = f"{p.get('host')}:{p.get('port')}"

            if not raw_str:
                continue

            clean_proxy = raw_str
            for prefix in ("http://", "https://", "socks5://", "socks4://", "socks://"):
                if clean_proxy.lower().startswith(prefix):
                    clean_proxy = clean_proxy[len(prefix):]
                    break

            if "@" in clean_proxy:
                try:
                    cred, hp = clean_proxy.split("@", 1)
                    clean_proxy = f"{hp}:{cred}"
                except Exception:
                    pass

            clean_proxy = clean_proxy.split("?")[0].split("/")[0].split("#")[0].strip()

            if host_port and host_port in existing_hosts_ports:
                continue

            if host_port:
                existing_hosts_ports.add(host_port)
            new_lines_to_add.append(clean_proxy)

        if not new_lines_to_add:
            return 0

        try:
            need_newline = False
            if os.path.exists(abs_path) and os.path.getsize(abs_path) > 0:
                with open(abs_path, "rb") as f_chk:
                    f_chk.seek(-1, os.SEEK_END)
                    last_char = f_chk.read(1)
                    if last_char not in (b"\n", b"\r"):
                        need_newline = True

            with open(abs_path, "a", encoding="utf-8") as f_out:
                if need_newline:
                    f_out.write("\n")
                for p_line in new_lines_to_add:
                    f_out.write(f"{p_line}\n")
                f_out.flush()
                try:
                    os.fsync(f_out.fileno())
                except Exception:
                    pass

            bname = os.path.basename(abs_path)
            self.log(f"[Proxy Free] 💾 Đã tự động lưu {len(new_lines_to_add)} proxy LIVE mới vào '{bname}'!", "success")

            try:
                from core.proxy_manager import FreeProxyManager
                FreeProxyManager().auto_save_file = abs_path
            except Exception:
                pass

            try:
                self.safe_ui_call(self.update_file_proxy_panel)
            except Exception:
                pass

            return len(new_lines_to_add)
        except Exception as e_write:
            self.log(f"[Proxy Free] ⚠️ Lỗi khi tự động lưu proxy LIVE vào '{target_file}': {e_write}", "error")
            return 0

    def test_proxy_list_facebook_connection(self):
        """Hộp thoại kiểm định trực tiếp kết nối m.facebook.com cho danh sách Proxy từ file cấu hình."""
        from core.proxy_manager import FreeProxyManager
        p_file = self.get_proxy_file_path()
        proxies_to_test = self.get_file_proxies()

        if not proxies_to_test:
            messagebox.showwarning("Thông báo", f"Danh sách proxy trong '{p_file}' đang rỗng! Vui lòng thêm proxy trước khi test.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"⚡ Kiểm Tra Kết Nối Facebook - File '{os.path.basename(p_file)}'")
        dlg.geometry("980x620")
        dlg.minsize(820, 500)
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)

        header_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=14, pady=10)
        header_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            header_frame,
            text=f"⚡ KIỂM ĐỊNH KẾT NỐI FACEBOOK - FILE '{os.path.basename(p_file)}'",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING
        ).pack(anchor="w")

        tk.Label(
            header_frame,
            text=f"Kiểm tra trực tiếp kết nối tới m.facebook.com cho {len(proxies_to_test)} proxy trong file '{p_file}'.\nĐo lường độ trễ (latency), phát hiện IP bị chặn và cho phép lọc lưu lại chỉ các proxy LIVE.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        summary_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        summary_bar.pack(fill=tk.X, padx=12, pady=(2, 6))

        c_box_total = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_total.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_total, text="Tổng Proxy File", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_total = tk.Label(c_box_total, text=f"{len(proxies_to_test)} Proxy", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT)
        lbl_card_total.pack(anchor="w")

        c_box_live = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_live.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_live, text="Kết Nối Live FB", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_live = tk.Label(c_box_live, text="0 Live", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS)
        lbl_card_live.pack(anchor="w")

        c_box_die = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_die.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_die, text="FB Chặn / Lỗi", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_die = tk.Label(c_box_die, text="0 Lỗi", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.DANGER)
        lbl_card_die.pack(anchor="w")

        c_box_ping = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_ping.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_ping, text="Ping TB Live", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_ping = tk.Label(c_box_ping, text="-- s", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.WARNING)
        lbl_card_ping.pack(anchor="w")

        filter_bar = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=12, pady=6)
        filter_bar.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(filter_bar, text="Bộ lọc:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(0, 4))
        cb_filter = ttk.Combobox(filter_bar, values=["Tất cả", "Chỉ Live FB", "Bị Chặn / Lỗi"], state="readonly", width=12, font=AppTheme.FONT_SMALL)
        cb_filter.set("Tất cả")
        cb_filter.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(filter_bar, text="Timeout (s):", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(0, 4))
        cb_timeout = ttk.Combobox(filter_bar, values=["0.5", "0.8", "1.0", "1.5", "2.0", "3.0", "4.0", "5.0", "6.0", "8.0", "10.0"], width=5, font=AppTheme.FONT_SMALL)
        cb_timeout.set("4.0")
        cb_timeout.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(filter_bar, text="Tìm kiếm:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(0, 4))
        ent_search = tk.Entry(filter_bar, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, font=AppTheme.FONT_SMALL, width=16, insertbackground=AppTheme.TEXT_MAIN)
        ent_search.pack(side=tk.LEFT, padx=(0, 8))

        lbl_match_count = tk.Label(filter_bar, text="", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED)
        lbl_match_count.pack(side=tk.RIGHT)

        tbl_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        cols = ("idx", "proxy", "protocol", "latency", "country", "status")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=12)
        tree.heading("idx", text="#")
        tree.heading("proxy", text="Địa chỉ Proxy")
        tree.heading("protocol", text="Giao thức")
        tree.heading("latency", text="Ping")
        tree.heading("country", text="Quốc gia")
        tree.heading("status", text="Trạng thái Facebook")

        tree.column("idx", width=40, minwidth=35, anchor="center")
        tree.column("proxy", width=220, minwidth=160, anchor="w")
        tree.column("protocol", width=75, minwidth=55, anchor="center")
        tree.column("latency", width=80, minwidth=65, anchor="center")
        tree.column("country", width=80, minwidth=55, anchor="center")
        tree.column("status", width=360, minwidth=220, anchor="w")

        tree.tag_configure("live", foreground=AppTheme.SUCCESS)
        tree.tag_configure("die", foreground=AppTheme.DANGER)

        scroll_y = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL, command=tree.yview)
        scroll_x = ttk.Scrollbar(tbl_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(fill=tk.BOTH, expand=True)

        lbl_hint = tk.Label(
            dlg,
            text="💡 Mẹo: Nhấp đúp vào dòng để sao chép Proxy vào bộ nhớ tạm.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED
        )
        lbl_hint.pack(anchor="w", padx=14, pady=(0, 4))

        def on_row_double_click(event):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if vals and len(vals) >= 2:
                p_to_copy = vals[1]
                self.root.clipboard_clear()
                self.root.clipboard_append(p_to_copy)
                lbl_hint.config(text=f"📋 Đã sao chép Proxy: {p_to_copy}", fg=AppTheme.SUCCESS)

        tree.bind("<Double-1>", on_row_double_click)

        act_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=12, pady=8)
        act_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        test_results = []
        is_testing = [False]

        def refresh_table_view():
            for item in tree.get_children():
                tree.delete(item)
            f_mode = cb_filter.get().strip()
            kw = ent_search.get().strip().lower()

            matched = 0
            for idx, r in enumerate(test_results, 1):
                is_live = r.get("success", False)
                if f_mode == "Chỉ Live FB" and not is_live:
                    continue
                if f_mode == "Bị Chặn / Lỗi" and is_live:
                    continue
                p_text = r.get("proxy", "")
                proto = r.get("protocol", "")
                if kw and (kw not in p_text.lower() and kw not in proto.lower()):
                    continue

                lat_str = f"{r.get('latency', 0.0):.2f}s" if is_live else "--"
                tag = "live" if is_live else "die"
                tree.insert("", "end", values=(
                    idx,
                    p_text,
                    proto,
                    lat_str,
                    r.get("country", "US"),
                    r.get("status_text", "")
                ), tags=(tag,))
                matched += 1

            lbl_match_count.config(text=f"Hiển thị: {matched}/{len(test_results)} proxy")

        cb_filter.bind("<<ComboboxSelected>>", lambda e: refresh_table_view())
        ent_search.bind("<KeyRelease>", lambda e: refresh_table_view())

        def run_test_worker(to_val=4.0):
            btn_start.config(state="disabled", text="⏳ Đang test Facebook...")
            lbl_hint.config(text=f"🌐 Đang kiểm tra handshake TLS & Facebook (Timeout {to_val}s) cho {len(proxies_to_test)} proxy...", fg=AppTheme.INFO)

            fm = FreeProxyManager()
            results = fm.test_proxies_facebook_connectivity(proxies_list=proxies_to_test, timeout=to_val)

            test_results.clear()
            test_results.extend(results)

            total = len(results)
            live_cnt = sum(1 for r in results if r.get("success"))
            die_cnt = total - live_cnt
            avg_ping = (sum(r.get("latency", 0.0) for r in results if r.get("success")) / live_cnt) if live_cnt > 0 else 0.0

            live_list = [r["proxy"] for r in results if r.get("success")]
            if live_list:
                try:
                    self.append_live_proxies_to_file(live_list)
                except Exception:
                    pass

            def update_ui():
                lbl_card_total.config(text=f"{total} Proxy")
                lbl_card_live.config(text=f"{live_cnt} Live FB")
                lbl_card_die.config(text=f"{die_cnt} Lỗi/Chặn")
                lbl_card_ping.config(text=f"{avg_ping:.2f}s" if avg_ping > 0 else "--")
                lbl_hint.config(text=f"✅ Đã hoàn tất kiểm tra {total} proxy (Timeout {to_val}s): {live_cnt} LIVE Facebook!", fg=AppTheme.SUCCESS)
                btn_start.config(state="normal", text="🔄 Kiểm Tra Lại")
                btn_save_live.config(state="normal" if live_cnt > 0 else "disabled")
                btn_copy_live.config(state="normal" if live_cnt > 0 else "disabled")
                btn_remove_bad.config(state="normal" if die_cnt > 0 else "disabled")
                refresh_table_view()
                is_testing[0] = False

            self.safe_ui_call(update_ui)

        def start_test():
            if is_testing[0]:
                return
            is_testing[0] = True
            try:
                to_val = float(cb_timeout.get().strip().replace("s", ""))
            except Exception:
                to_val = 4.0
            btn_start.config(state="disabled", text="⏳ Đang test Facebook...")
            lbl_hint.config(text=f"🌐 Đang kiểm tra handshake TLS & Facebook (Timeout {to_val}s) cho {len(proxies_to_test)} proxy...", fg=AppTheme.INFO)
            threading.Thread(target=run_test_worker, args=(to_val,), daemon=True).start()

        def save_only_live_to_file():
            live_proxies = [r["proxy"] for r in test_results if r.get("success")]
            if not live_proxies:
                messagebox.showwarning("Thông báo", "Không có Proxy LIVE nào để lưu!", parent=dlg)
                return
            ans = messagebox.askyesno(
                "Xác nhận",
                f"Bạn có muốn ghi đè file '{p_file}' với {len(live_proxies)} proxy LIVE Facebook đạt chuẩn?",
                parent=dlg
            )
            if ans:
                content = f"# Danh sách Proxy LIVE Facebook ({len(live_proxies)} proxies) - Đã kiểm định kết nối m.facebook.com\n" + "\n".join(live_proxies) + "\n"
                abs_path = p_file if os.path.isabs(p_file) else os.path.join(os.path.dirname(__file__), p_file)
                try:
                    with open(abs_path, "w", encoding="utf-8-sig") as f:
                        f.write(content)
                    self.reload_proxy_file()
                    messagebox.showinfo("Thành công", f"Đã lưu {len(live_proxies)} proxy LIVE vào '{p_file}' và đồng bộ giao diện!", parent=dlg)
                except Exception as ex:
                    messagebox.showerror("Lỗi", f"Không thể ghi file: {ex}", parent=dlg)

        def copy_all_live():
            live_proxies = [r["proxy"] for r in test_results if r.get("success")]
            if live_proxies:
                self.root.clipboard_clear()
                self.root.clipboard_append("\n".join(live_proxies))
                lbl_hint.config(text=f"📋 Đã sao chép {len(live_proxies)} Proxy LIVE vào Clipboard!", fg=AppTheme.SUCCESS)

        btn_start = tk.Button(
            act_frame,
            cursor="hand2",
            text="🔄 Bắt Đầu Kiểm Tra",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.WARNING,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            command=start_test
        )
        btn_start.pack(side=tk.LEFT, padx=(0, 6))

        btn_save_live = tk.Button(
            act_frame,
            cursor="hand2",
            text="💾 Chỉ Giữ Proxy LIVE Vào File",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            state="disabled",
            command=save_only_live_to_file
        )
        btn_save_live.pack(side=tk.LEFT, padx=(0, 6))

        btn_copy_live = tk.Button(
            act_frame,
            cursor="hand2",
            text="📋 Copy Proxy LIVE",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=8,
            pady=4,
            state="disabled",
            command=copy_all_live
        )
        btn_copy_live.pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            act_frame,
            cursor="hand2",
            text="❌ Đóng",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MUTED,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=10,
            pady=4,
            command=dlg.destroy
        ).pack(side=tk.RIGHT)

        dlg.after(100, start_test)

    def _render_proxy_keys_display(self):
        if not hasattr(self, "txt_proxy_keys") or not self.txt_proxy_keys.winfo_exists():
            return
        self.txt_proxy_keys.delete("1.0", tk.END)
        prov = self.get_selected_proxy_provider()
        if prov == "proxysocks5":
            keys_to_render = getattr(self, "_raw_proxysocks5_keys", [])
            if not keys_to_render:
                saved = self.config.get("proxysocks5_keys", [])
                keys_to_render = [k.strip() for k in saved] if isinstance(saved, list) else [k.strip() for k in saved.splitlines() if k.strip()]
                self._raw_proxysocks5_keys = list(keys_to_render)

            if getattr(self, "keys_masked", True):
                masked_lines = [self.mask_key(k) for k in keys_to_render if k.strip()]
                self.txt_proxy_keys.insert("1.0", "\n".join(masked_lines))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="👁 Hiện Key", fg=AppTheme.ACCENT)
            else:
                self.txt_proxy_keys.insert("1.0", "\n".join(keys_to_render))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="🔒 Ẩn Key", fg=AppTheme.WARNING)

        elif prov == "proxyvn":
            keys_to_render = getattr(self, "_raw_proxyvn_keys", [])
            if not keys_to_render:
                saved = self.config.get("proxyvn_keys", [])
                keys_to_render = [k.strip() for k in saved] if isinstance(saved, list) else [k.strip() for k in saved.splitlines() if k.strip()]
                if not keys_to_render:
                    keys_to_render = ["LdeNrJVTorbBBmKBqoYdnO"]
                self._raw_proxyvn_keys = list(keys_to_render)

            if getattr(self, "keys_masked", True):
                masked_lines = [self.mask_key(k) for k in keys_to_render if k.strip()]
                self.txt_proxy_keys.insert("1.0", "\n".join(masked_lines))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="👁️ Hiện Key", fg=AppTheme.ACCENT)
            else:
                self.txt_proxy_keys.insert("1.0", "\n".join(keys_to_render))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="🔒 Ẩn Key", fg=AppTheme.WARNING)

        elif prov == "mproxy":
            keys_to_render = getattr(self, "_raw_mproxy_keys", [])
            tok = getattr(self, "mproxy_token", "") or self.config.get("mproxy_token", "CncgWVg-ppCxg7EwH7dFS6ICuv8hzXLaJdF-rzoXQAU")
            if not keys_to_render:
                saved = self.config.get("mproxy_keys", [])
                keys_to_render = [k.strip() for k in saved] if isinstance(saved, list) else [k.strip() for k in saved.splitlines() if k.strip()]
            if not keys_to_render and tok:
                keys_to_render = [tok]
            self._raw_mproxy_keys = list(keys_to_render)

            if getattr(self, "keys_masked", True):
                masked_lines = [self.mask_key(k) for k in keys_to_render if k.strip()]
                self.txt_proxy_keys.insert("1.0", "\n".join(masked_lines))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="👁️ Hiện Key", fg=AppTheme.ACCENT)
            else:
                self.txt_proxy_keys.insert("1.0", "\n".join(keys_to_render))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="🔒 Ẩn Key", fg=AppTheme.WARNING)

        elif prov == "proxy_list":
            self.update_file_proxy_panel()

        elif prov in ("free_proxy", "free_proxy_live", "free_proxy_cached"):
            from core.proxy_manager import FreeProxyManager
            total_srcs = FreeProxyManager.get_total_sources_count()
            info_msg = (
                f"# Chế độ Proxy Free Tự Động ({total_srcs} nguồn online)\n"
                f"# Hệ thống tự động quét, kiểm tra live Facebook và cấp cho từng luồng.\n"
                f"# Bấm 'Cào Proxy Free' hoặc 'Test Kết Nối FB' bên dưới để kiểm tra nguồn."
            )
            self.txt_proxy_keys.insert("1.0", info_msg)
            if hasattr(self, "btn_toggle_mask"):
                self.btn_toggle_mask.config(text="🌐 Free", fg=AppTheme.INFO)

        elif prov == "none":
            self.txt_proxy_keys.insert(
                "1.0",
                "# Chế độ Mạng Trực Tiếp (Direct IP)\n"
                "# Không sử dụng Proxy. Các luồng chạy trực tiếp qua IP máy tính hiện tại."
            )
            if hasattr(self, "btn_toggle_mask"):
                self.btn_toggle_mask.config(text="⚡ Direct", fg=AppTheme.WARNING)

        else: # kiotproxy
            keys_to_render = getattr(self, "_raw_kiot_keys", [])
            if not keys_to_render:
                saved = self.config.get("kiotproxy_keys", [])
                keys_to_render = [k.strip() for k in saved] if isinstance(saved, list) else [k.strip() for k in saved.splitlines() if k.strip()]
                self._raw_kiot_keys = list(keys_to_render)

            if getattr(self, "keys_masked", True):
                masked_lines = [self.mask_key(k) for k in keys_to_render if k.strip()]
                self.txt_proxy_keys.insert("1.0", "\n".join(masked_lines))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="👁 Hiện Key", fg=AppTheme.ACCENT)
            else:
                self.txt_proxy_keys.insert("1.0", "\n".join(keys_to_render))
                if hasattr(self, "btn_toggle_mask"):
                    self.btn_toggle_mask.config(text="🔒 Ẩn Key", fg=AppTheme.WARNING)

    def toggle_mask_proxy_keys(self):
        prov = self.get_selected_proxy_provider()
        if prov == "proxy_list":
            self.save_proxies_to_file()
            return
        if prov in ("free_proxy", "free_proxy_live", "free_proxy_cached", "none"):
            return

        if getattr(self, "keys_masked", True):
            raw_content = self.txt_proxy_keys.get("1.0", tk.END)
            new_keys = [k.strip() for k in raw_content.splitlines() if k.strip() and not k.startswith("#")]
            if new_keys and not any("*" in k for k in new_keys):
                if prov == "proxysocks5":
                    self._raw_proxysocks5_keys = new_keys
                    self.config["proxysocks5_keys"] = self._raw_proxysocks5_keys
                elif prov == "mproxy":
                    self._raw_mproxy_keys = new_keys
                    self.config["mproxy_keys"] = self._raw_mproxy_keys
                    if new_keys and len(new_keys[0]) >= 25 and ("-" in new_keys[0] or "_" in new_keys[0]):
                        self.mproxy_token = new_keys[0]
                        self.config["mproxy_token"] = new_keys[0]
                elif prov == "proxyvn":
                    self._raw_proxyvn_keys = new_keys
                    self.config["proxyvn_keys"] = self._raw_proxyvn_keys
                else:
                    self._raw_kiot_keys = new_keys
                    self.config["kiotproxy_keys"] = self._raw_kiot_keys
                    if self._raw_kiot_keys:
                        self.config["kiotproxy_api_key"] = self._raw_kiot_keys[0]

            self.keys_masked = False
            self._render_proxy_keys_display()
            self.log("[*] Đang hiển thị Key Proxy ở chế độ xem/sửa. Hãy bấm Ẩn Key sau khi xong!", "info")
        else:
            raw_content = self.txt_proxy_keys.get("1.0", tk.END)
            new_keys = [k.strip() for k in raw_content.splitlines() if k.strip() and not k.startswith("#")]
            if new_keys and not any("*" in k for k in new_keys):
                if prov == "proxysocks5":
                    self._raw_proxysocks5_keys = new_keys
                    self.config["proxysocks5_keys"] = self._raw_proxysocks5_keys
                elif prov == "mproxy":
                    self._raw_mproxy_keys = new_keys
                    self.config["mproxy_keys"] = self._raw_mproxy_keys
                    if new_keys and len(new_keys[0]) >= 25 and ("-" in new_keys[0] or "_" in new_keys[0]):
                        self.mproxy_token = new_keys[0]
                        self.config["mproxy_token"] = new_keys[0]
                elif prov == "proxyvn":
                    self._raw_proxyvn_keys = new_keys
                    self.config["proxyvn_keys"] = self._raw_proxyvn_keys
                else:
                    self._raw_kiot_keys = new_keys
                    self.config["kiotproxy_keys"] = self._raw_kiot_keys
                    if self._raw_kiot_keys:
                        self.config["kiotproxy_api_key"] = self._raw_kiot_keys[0]
            self.keys_masked = True
            self._render_proxy_keys_display()
            self.log("[*] Đã ẩn/bảo mật thông tin Key Proxy an toàn.", "success")


    def save_config(self, show_toast: bool = True):
        mode = self.var_reg_mode.get() if hasattr(self, "var_reg_mode") else "vr"
        self.config["reg_mode"] = mode
        self.config["legacy_verify_mode"] = self.get_selected_legacy_verify_mode()
        bait_mode = self.get_selected_bait_mode()
        self.config["bait_mode"] = bait_mode
        self.config["auto_gen_phone"] = (bait_mode == "phone")
        self.config["use_bait_phone"] = (bait_mode == "phone")
        self.config["use_bait_gmail"] = (bait_mode == "gmail")
        self.config["enable_bait_retry"] = self.var_enable_bait_retry.get() if hasattr(self, "var_enable_bait_retry") else True
        if hasattr(self, "spn_bait_retries"):
            try:
                self.config["bait_retries"] = max(1, min(10, int(self.spn_bait_retries.get())))
            except Exception:
                self.config["bait_retries"] = 3
        elif hasattr(self, "var_bait_retries"):
            self.config["bait_retries"] = max(1, min(10, int(self.var_bait_retries.get())))
        if hasattr(self, "spn_threads"):
            try:
                self.config["threads"] = int(self.spn_threads.get())
            except Exception:
                pass
        if hasattr(self, "spn_accounts"):
            try:
                self.config["max_accounts"] = int(self.spn_accounts.get())
            except Exception:
                pass
        self.config["enable_2fa"] = self.var_2fa.get() if hasattr(self, "var_2fa") else True
        self.config["auto_ttc_pipeline"] = bool(self.var_auto_ttc.get()) if hasattr(self, "var_auto_ttc") else False
        anti_cp_val = self.var_anti_cp.get() if hasattr(self, "var_anti_cp") else True
        self.config["anti_checkpoint_mode"] = anti_cp_val
        self.config["email_integrity_guard"] = anti_cp_val
        self.config["behavioral_delays"] = anti_cp_val
        self.config["session_warmup"] = anti_cp_val
        self.config["network_risk_check"] = anti_cp_val
        self.config["proxy_provider"] = self.get_selected_proxy_provider()
        if hasattr(self, "var_proxy_mode_shared") and self.var_proxy_mode_shared.get():
            self.config["proxy_alloc_mode"] = "shared"
        else:
            self.config["proxy_alloc_mode"] = "dedicated"
        if hasattr(self, "var_auto_rotate"):
            self.config["auto_rotate_proxy"] = bool(self.var_auto_rotate.get())
        if hasattr(self, "cb_auto_rotate_interval"):
            self.config["auto_rotate_interval"] = str(self.cb_auto_rotate_interval.get())

        if hasattr(self, "entry_fb_pwd"):
            self.config["default_password"] = self.entry_fb_pwd.get().strip()

        pvn_keys = self.get_proxyvn_keys()
        self.config["proxyvn_keys"] = pvn_keys
        keys = self.get_kiotproxy_keys()
        self.config["kiotproxy_keys"] = keys
        if keys:
            self.config["kiotproxy_api_key"] = keys[0]

        ps_keys = self.get_proxysocks5_keys()
        self.config["proxysocks5_keys"] = ps_keys
        self.config["proxysocks5_user_token"] = getattr(self, "proxysocks5_user_token", "QosKHIjPqRnaoQgR6qs4UEkrC6EwXx")

        mp_keys = self.get_mproxy_keys()
        self.config["mproxy_keys"] = mp_keys
        self.config["mproxy_token"] = getattr(self, "mproxy_token", "CncgWVg-ppCxg7EwH7dFS6ICuv8hzXLaJdF-rzoXQAU")

        self.config["proxy_file_path"] = self.get_proxy_file_path()
        if hasattr(self, "var_filter_bad_proxy_from_file"):
            self.config["filter_bad_proxy_from_file"] = self.var_filter_bad_proxy_from_file.get()
# Khong tu y xoa file proxy khi luu config

        if hasattr(self, "get_selected_server_mode"):
            srv_mode = self.get_selected_server_mode()
            self.config["server_mode"] = srv_mode
            self.config["random_server"] = (srv_mode == "random_all")
            self.config["random_subset"] = (srv_mode == "subset")
            self.config["server_pool"] = self.get_selected_server_pool()
            self.config["server"] = self.get_selected_server()

        if hasattr(self, "cb_name_type"):
            self.config["name_type"] = self.get_selected_name_type()
        if hasattr(self, "cb_device_type"):
            self.config["device_type"] = self.get_selected_device_type()
        if hasattr(self, "var_mix_names"):
            self.config["mix_file_names"] = self.var_mix_names.get()
        self.config["custom_name_file"] = getattr(self, "custom_name_file", "names.txt")

        if hasattr(self, "cb_save_format"):
            self.config["save_format"] = self.cb_save_format.get().strip() or "UID|PASS|2FA|COOKIE|TOKEN|EMAIL"

        if hasattr(self, "entry_metaking_key"):
            self.config["metaking_api_key"] = self.entry_metaking_key.get().strip()
        if hasattr(self, "var_metaking_service_type"):
            self.config["metaking_service_type"] = self.var_metaking_service_type.get()
        if hasattr(self, "cb_metaking_server"):
            raw_srv = self.cb_metaking_server.get()
            m_s = re.search(r'\d+', raw_srv)
            self.config["metaking_server"] = int(m_s.group(0)) if m_s else 1
        if hasattr(self, "cb_metaking_domain"):
            raw_dom = self.cb_metaking_domain.get().strip()
            m_dom = re.search(r'([a-zA-Z0-9.\-_]+\.[a-zA-Z]{2,})', raw_dom)
            self.config["metaking_domain"] = m_dom.group(1).lower() if m_dom else "gmail.com"
        if hasattr(self, "cb_metaking_country"):
            raw_c = self.cb_metaking_country.get().strip()
            m_c = re.search(r'\[?(\d+)\]?', raw_c)
            self.config["metaking_country_id"] = int(m_c.group(1)) if m_c else 154
        elif hasattr(self, "entry_metaking_country"):
            try:
                self.config["metaking_country_id"] = int(self.entry_metaking_country.get().strip())
            except Exception:
                self.config["metaking_country_id"] = 154
        if hasattr(self, "cb_metaking_price"):
            val_p = self.cb_metaking_price.get().lower()
            self.config["metaking_price"] = "high" if "high" in val_p else "low"

        self.config["email_service"] = self.get_selected_email_service()
        if hasattr(self, "get_selected_custom_domains"):
            self.config["selected_custom_domains"] = self.get_selected_custom_domains()

        if hasattr(self, "var_retry_on_nvr"):
            self.config["retry_on_nvr_with_new_mail"] = self.var_retry_on_nvr.get()
        if hasattr(self, "cb_retry_email_service"):
            raw_retry_choice = self.cb_retry_email_service.get()
            chosen_srv = self.RETRY_EMAIL_SERVICE_MAP.get(raw_retry_choice, "as_setting")
            self.config["retry_email_service"] = chosen_srv
            self.config["retry_use_free_mail"] = (chosen_srv == "auto_rotator")
        if hasattr(self, "spn_max_email_retries"):
            try:
                self.config["max_otp_email_retries"] = int(self.spn_max_email_retries.get())
            except Exception:
                self.config["max_otp_email_retries"] = 15
        if hasattr(self, "spn_otp_timeout"):
            try:
                self.config["otp_timeout"] = int(self.spn_otp_timeout.get())
            except Exception:
                self.config["otp_timeout"] = 20

        if hasattr(self, "var_bot_auto_upload"):
            self.config["bot_auto_upload"] = bool(self.var_bot_auto_upload.get())
        if hasattr(self, "entry_bot_media_id"):
            self.config["bot_media_id"] = str(self.entry_bot_media_id.get()).strip()
        if hasattr(self, "entry_bot_api_url"):
            self.config["bot_api_url"] = str(self.entry_bot_api_url.get()).strip()
        if hasattr(self, "entry_bot_api_key"):
            self.config["bot_api_key"] = str(self.entry_bot_api_key.get()).strip()
        if hasattr(self, "var_enable_verry_pipeline"):
            self.config["enable_verry_pipeline"] = bool(self.var_enable_verry_pipeline.get())
        if hasattr(self, "var_verry_pipeline_delay"):
            self.config["verry_pipeline_delay"] = str(self.var_verry_pipeline_delay.get()).strip()
        if hasattr(self, "var_verry_pipeline_threads"):
            self.config["verry_pipeline_threads"] = str(self.var_verry_pipeline_threads.get()).strip()
        if hasattr(self, "var_verry_pipeline_dir"):
            self.config["verry_pipeline_dir"] = str(self.var_verry_pipeline_dir.get()).strip()

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.save_table_session()
            if show_toast:
                self.log("[Cấu hình] Đã lưu thành công cài đặt & dữ liệu bảng!", "success")
                messagebox.showinfo("Thành công", "Đã lưu cài đặt vào config.json và phiên làm việc!")
        except Exception as e:
            self.log(f"[Cấu hình Lỗi] Không thể lưu: {e}", "error")
            if show_toast:
                messagebox.showerror("Lỗi", f"Không thể lưu cấu hình: {e}")

    def on_close_window(self):
        msg = "Tiến trình đang chạy! Bạn có chắc chắn muốn dừng và tắt tool không?" if self.is_running else "Bạn có chắc chắn muốn tắt tool không?"
        res = messagebox.askokcancel("Xác nhận tắt tool", msg)
        if res:
            try:
                self.stop_execution()
                self.save_config(show_toast=False)
                self.save_table_session()
                if hasattr(self, "_file_save_executor"):
                    self._file_save_executor.shutdown(wait=True)
            except Exception:
                pass
            self.root.destroy()

    def _get_tree_values(self, item_id: str) -> list:
        if not hasattr(self, "_tree_item_values"):
            self._tree_item_values = {}
        vals = self._tree_item_values.get(item_id)
        if vals is None:
            try:
                vals = list(self.tree.item(item_id, "values"))
                self._tree_item_values[item_id] = vals
            except Exception:
                vals = []
        return vals

    def _get_tree_tags(self, item_id: str) -> tuple:
        if not hasattr(self, "_tree_item_tags"):
            self._tree_item_tags = {}
        tgs = self._tree_item_tags.get(item_id)
        if tgs is None:
            try:
                tgs = tuple(self.tree.item(item_id, "tags") or ())
                self._tree_item_tags[item_id] = tgs
            except Exception:
                tgs = ()
        return tgs

    def _update_tree_item(self, item_id: str, values=None, tags=None):
        if not hasattr(self, "_tree_item_values"):
            self._tree_item_values = {}
        if not hasattr(self, "_tree_item_tags"):
            self._tree_item_tags = {}
        kwargs = {}
        if values is not None:
            v_list = list(values)
            cur_v = self._tree_item_values.get(item_id)
            if cur_v != v_list:
                self._tree_item_values[item_id] = v_list
                kwargs["values"] = v_list
        if tags is not None:
            t_tup = tuple(tags)
            cur_t = self._tree_item_tags.get(item_id)
            if cur_t != t_tup:
                self._tree_item_tags[item_id] = t_tup
                kwargs["tags"] = t_tup
        if kwargs and hasattr(self, "tree") and self.tree.winfo_exists():
            try:
                self.tree.item(item_id, **kwargs)
            except Exception:
                pass

    def save_table_session(self, force: bool = False):
        now_ts = time.time()
        if not force and hasattr(self, "_last_table_save_ts") and (now_ts - self._last_table_save_ts < 15.0):
            return
        self._last_table_save_ts = now_ts
        try:
            rows = []
            for item in self.tree.get_children():
                vals = self._get_tree_values(item)
                tags = list(self._get_tree_tags(item))
                full_l = getattr(self, "_row_full_lines", {}).get(item, "")
                rows.append({"values": vals, "tags": tags, "full_line": full_l})
            data = {
                "rows": rows,
                "stats": {
                    "total": self.stat_total,
                    "success": self.stat_success,
                    "failed": self.stat_failed,
                    "unverified": self.stat_unverified,
                }
            }
            if hasattr(self, "_file_save_executor"):
                self._file_save_executor.submit(self._write_table_session_file, data)
            else:
                self._write_table_session_file(data)
        except Exception as e:
            self.log(f"Lỗi lưu phiên bảng: {e}", "error")

    def _write_table_session_file(self, data: dict):
        try:
            tmp_path = self.session_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    import os
                    os.fsync(f.fileno())
                except Exception:
                    pass
            bak_path = self.session_path + ".bak"
            if not data.get("rows"):
                try:
                    with open(bak_path, "w", encoding="utf-8") as f_b:
                        json.dump(data, f_b, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            elif os.path.exists(self.session_path):
                try:
                    import shutil
                    shutil.copyfile(self.session_path, bak_path)
                except Exception:
                    pass
            import os
            os.replace(tmp_path, self.session_path)
        except Exception as e:
            logger.debug(f"Error writing session file: {e}")

    def recalculate_stats_from_tree(self):
        items = self.tree.get_children()
        self.stat_total = len(items)
        self.stat_success = 0
        self.stat_failed = 0
        self.stat_unverified = 0
        for item in items:
            tags = self._get_tree_tags(item)
            vals = self._get_tree_values(item)
            status_val = str(vals[9] if len(vals) > 9 else (vals[7] if len(vals) > 7 else "")).lower()

            is_die = any(t in tags for t in ("die", "failed", "danger")) or any(k in status_val for k in ("die", "282", "khóa", "vô hiệu", "checkpoint", "tạm ngưng", "ufac", "hết phiên"))
            is_live = (not is_die) and (any(t in tags for t in ("live", "success")) or "live" in status_val) and ("nvr" not in status_val and "chờ" not in status_val)

            if is_die:
                self.stat_failed += 1
            elif is_live:
                self.stat_success += 1
            else:
                self.stat_unverified += 1
        self.row_counter = len(items)
        self.update_stats_display()

    def load_table_session(self):
        bak_file = self.session_path + ".bak"
        if not os.path.exists(self.session_path) and not os.path.exists(bak_file):
            return
        data = None
        # 1. Thu doc file chinh
        if os.path.exists(self.session_path):
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e_main:
                logger.warning(f"Loi doc {self.session_path}: {e_main}")
                data = None

        # 2. Chi tu dong khoi phuc tu file backup .bak neu file chinh bi loi / khong ton tai VA file backup co chua rows
        if not data and os.path.exists(bak_file):
            try:
                with open(bak_file, "r", encoding="utf-8") as f:
                    bak_data = json.load(f)
                if isinstance(bak_data, dict) and bak_data.get("rows"):
                    data = bak_data
                    self.log(f"[*] Da tu dong khoi phuc phien lam viec tu file sao luu ({bak_file})!", "info")
            except Exception as e_bak:
                logger.warning(f"Loi doc file backup {bak_file}: {e_bak}")
                data = None

        # 3. Bo cuu ho regex neu file bi ngat cut dot ngot
        if not data:
            target_f = self.session_path if os.path.exists(self.session_path) else bak_file
            try:
                with open(target_f, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read()
                row_matches = re.findall(r'\{\s*"values":\s*\[[^\]]+\](?:,\s*"tags":\s*\[[^\]]*\])?(?:,\s*"full_line":\s*"[^"]*")?\s*\}', raw_text)
                if row_matches:
                    salvaged_rows = []
                    for m in row_matches:
                        try:
                            salvaged_rows.append(json.loads(m))
                        except Exception:
                            pass
                    if salvaged_rows:
                        data = {"rows": salvaged_rows}
                        self.log(f"[*] Cuu ho thanh cong {len(salvaged_rows)} dong tai khoan tu file phien bi gian doan!", "info")
            except Exception as e_salvage:
                logger.warning(f"Loi cuu ho du lieu: {e_salvage}")

        if not data:
            return

        try:
            rows = data.get("rows", [])
            if not rows:
                return

            curr_reg_mode = self.config.get("reg_mode", "")
            # Nếu đang ở Tool Reg (không phải verify_nvr), lọc bỏ triệt để các dòng "Chờ ngấu" bị lưu nhầm từ trước
            if curr_reg_mode != "verify_nvr":
                rows = [
                    r for r in rows
                    if "ngấu" not in str(r.get("values", [])).lower()
                    and "chờ xác minh (pipeline)" not in str(r.get("values", [])).lower()
                ]
                if not rows:
                    return
            if not hasattr(self, "_row_full_lines"):
                self._row_full_lines = {}
            if not hasattr(self, "_row_acc_data"):
                self._row_acc_data = {}
            from core.nvr_verifier import SmartAccountParser
            for r in rows:
                vals = r.get("values", [])
                tags = r.get("tags", ["running"])
                full_l = r.get("full_line", "")
                if vals:
                    if len(vals) == 9:
                        vals = vals[:6] + ["", ""] + vals[6:]
                    if len(vals) >= 11:
                        vals[8] = self.mask_ip(vals[8])
                        item_id = self.tree.insert("", "end", values=vals, tags=tuple(tags))
                        if hasattr(self, "_tree_item_values"):
                            self._tree_item_values[item_id] = list(vals)
                        if hasattr(self, "_tree_item_tags"):
                            self._tree_item_tags[item_id] = tuple(tags)
                        uid_str = str(vals[2]).strip()
                        if hasattr(self, "_tree_items_by_uid") and uid_str and uid_str != "N/A":
                            self._tree_items_by_uid[uid_str] = item_id
                        self._row_full_lines[item_id] = full_l or f"{vals[2]}|{vals[4]}|{vals[7]}|{vals[6]}"
                        parsed = SmartAccountParser.parse_line(full_l) if full_l else None
                        if not parsed:
                            parsed = {
                                "uid": str(vals[2]).strip(),
                                "password": str(vals[4]).strip(),
                                "two_factor_secret": str(vals[5]).strip(),
                                "cookie": str(vals[6]).strip(),
                                "token": str(vals[7]).strip(),
                                "email": str(vals[3]).strip() if "@" in str(vals[3]) else "",
                                "raw_line": full_l,
                            }
                        self._row_acc_data[item_id] = parsed
            self.row_counter = len(rows)
            self.recalculate_stats_from_tree()
            if rows:
                self.log(f"[*] Đã khôi phục {len(rows)} tài khoản từ phiên làm việc trước.", "info")
        except Exception as e:
            self.log(f"Lỗi tải phiên bảng: {e}", "error")

    def setup_styles(self):
        # 1. Cấu hình bảng chặn Tkinter Option Database toàn cục
        # Đảm bảo triệt để: Menu thả xuống (Popdown Listbox), Entry, Spinbox, Text KHÔNG BAO GIỜ bị nền trắng
        self.root.option_add("*TCombobox*Listbox.background", AppTheme.BG_INPUT)
        self.root.option_add("*TCombobox*Listbox.foreground", AppTheme.TEXT_MAIN)
        self.root.option_add("*TCombobox*Listbox.selectBackground", AppTheme.ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font", AppTheme.FONT_BODY)
        self.root.option_add("*TCombobox*Listbox.relief", "flat")
        self.root.option_add("*TCombobox*Listbox.borderWidth", 1)
        self.root.option_add("*TCombobox*Listbox.highlightThickness", 1)
        self.root.option_add("*TCombobox*Listbox.highlightColor", AppTheme.BORDER)
        self.root.option_add("*TCombobox*Listbox.highlightBackground", AppTheme.BORDER)

        self.root.option_add("*Listbox.background", AppTheme.BG_INPUT)
        self.root.option_add("*Listbox.foreground", AppTheme.TEXT_MAIN)
        self.root.option_add("*Listbox.selectBackground", AppTheme.ACCENT)
        self.root.option_add("*Listbox.selectForeground", "#ffffff")

        self.root.option_add("*Entry.background", AppTheme.BG_INPUT)
        self.root.option_add("*Entry.foreground", AppTheme.TEXT_MAIN)
        self.root.option_add("*Entry.readonlyBackground", AppTheme.BG_INPUT)
        self.root.option_add("*Entry.disabledBackground", AppTheme.BG_CARD)
        self.root.option_add("*Entry.disabledForeground", AppTheme.TEXT_MUTED)
        self.root.option_add("*Entry.insertBackground", AppTheme.TEXT_MAIN)
        self.root.option_add("*Entry.selectBackground", AppTheme.ACCENT)
        self.root.option_add("*Entry.selectForeground", "#ffffff")

        self.root.option_add("*Spinbox.background", AppTheme.BG_INPUT)
        self.root.option_add("*Spinbox.foreground", AppTheme.TEXT_MAIN)
        self.root.option_add("*Spinbox.readonlyBackground", AppTheme.BG_INPUT)
        self.root.option_add("*Spinbox.disabledBackground", AppTheme.BG_CARD)
        self.root.option_add("*Spinbox.disabledForeground", AppTheme.TEXT_MUTED)
        self.root.option_add("*Spinbox.insertBackground", AppTheme.TEXT_MAIN)
        self.root.option_add("*Spinbox.selectBackground", AppTheme.ACCENT)
        self.root.option_add("*Spinbox.selectForeground", "#ffffff")

        self.root.option_add("*Text.background", AppTheme.BG_INPUT)
        self.root.option_add("*Text.foreground", AppTheme.TEXT_MAIN)
        self.root.option_add("*Text.insertBackground", AppTheme.TEXT_MAIN)
        self.root.option_add("*Text.selectBackground", AppTheme.ACCENT)
        self.root.option_add("*Text.selectForeground", "#ffffff")

        # 2. Cấu hình ttk.Style với clam theme
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=AppTheme.BG_DARK, foreground=AppTheme.TEXT_MAIN)
        style.configure("Card.TFrame", background=AppTheme.BG_CARD)
        style.configure("Treeview",
            background=AppTheme.BG_CARD,
            foreground=AppTheme.TEXT_MAIN,
            fieldbackground=AppTheme.BG_CARD,
            rowheight=26,
            font=AppTheme.FONT_BODY,
            borderwidth=0
        )
        style.map("Treeview",
            background=[("selected", AppTheme.ACCENT)],
            foreground=[("selected", "#000000")]
        )
        style.configure("Treeview.Heading",
            background=AppTheme.BG_INPUT,
            foreground=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_HEADER,
            borderwidth=1,
            relief="flat"
        )

        # Cấu hình triệt để TCombobox: loại bỏ 100% tình trạng nền trắng chữ trắng ở mọi trạng thái (readonly/focus/hover/disabled)
        style.configure("TCombobox",
            fieldbackground=AppTheme.BG_INPUT,
            background=AppTheme.BG_CARD,
            foreground=AppTheme.TEXT_MAIN,
            arrowcolor=AppTheme.TEXT_MAIN,
            bordercolor=AppTheme.BORDER,
            lightcolor=AppTheme.BORDER,
            darkcolor=AppTheme.BORDER,
            padding=[6, 4],
            relief="flat",
            borderwidth=1,
            insertcolor=AppTheme.TEXT_MAIN,
            selectbackground=AppTheme.ACCENT,
            selectforeground="#ffffff",
        )
        style.map("TCombobox",
            fieldbackground=[
                ("readonly", "focus", AppTheme.BG_INPUT),
                ("readonly", "hover", AppTheme.BG_INPUT),
                ("readonly", AppTheme.BG_INPUT),
                ("disabled", AppTheme.BG_CARD),
                ("focus", AppTheme.BG_INPUT),
                ("!disabled", AppTheme.BG_INPUT),
            ],
            foreground=[
                ("readonly", "focus", AppTheme.TEXT_MAIN),
                ("readonly", "hover", AppTheme.TEXT_MAIN),
                ("readonly", AppTheme.TEXT_MAIN),
                ("disabled", AppTheme.TEXT_MUTED),
                ("focus", AppTheme.TEXT_MAIN),
                ("!disabled", AppTheme.TEXT_MAIN),
            ],
            background=[
                ("readonly", "pressed", AppTheme.BG_CARD_LIGHT),
                ("readonly", "hover", AppTheme.BG_CARD_LIGHT),
                ("readonly", AppTheme.BG_CARD),
                ("active", AppTheme.BG_CARD_LIGHT),
                ("pressed", AppTheme.BG_CARD_LIGHT),
                ("!disabled", AppTheme.BG_CARD),
            ],
            arrowcolor=[
                ("disabled", AppTheme.TEXT_MUTED),
                ("pressed", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("readonly", AppTheme.TEXT_MAIN),
                ("!disabled", AppTheme.TEXT_MAIN),
            ],
            bordercolor=[
                ("focus", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("!disabled", AppTheme.BORDER),
            ],
            lightcolor=[
                ("focus", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("!disabled", AppTheme.BORDER),
            ],
            darkcolor=[
                ("focus", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("!disabled", AppTheme.BORDER),
            ],
        )

        # Cấu hình TSpinbox: loại bỏ nền trắng chữ trắng
        style.configure("TSpinbox",
            fieldbackground=AppTheme.BG_INPUT,
            background=AppTheme.BG_CARD,
            foreground=AppTheme.TEXT_MAIN,
            arrowcolor=AppTheme.TEXT_MAIN,
            bordercolor=AppTheme.BORDER,
            lightcolor=AppTheme.BORDER,
            darkcolor=AppTheme.BORDER,
            insertcolor=AppTheme.TEXT_MAIN,
            selectbackground=AppTheme.ACCENT,
            selectforeground="#ffffff",
            padding=[4, 2],
        )
        style.map("TSpinbox",
            fieldbackground=[
                ("readonly", "focus", AppTheme.BG_INPUT),
                ("readonly", "hover", AppTheme.BG_INPUT),
                ("readonly", AppTheme.BG_INPUT),
                ("disabled", AppTheme.BG_CARD),
                ("focus", AppTheme.BG_INPUT),
                ("!disabled", AppTheme.BG_INPUT),
            ],
            foreground=[
                ("readonly", "focus", AppTheme.TEXT_MAIN),
                ("readonly", "hover", AppTheme.TEXT_MAIN),
                ("readonly", AppTheme.TEXT_MAIN),
                ("disabled", AppTheme.TEXT_MUTED),
                ("focus", AppTheme.TEXT_MAIN),
                ("!disabled", AppTheme.TEXT_MAIN),
            ],
            background=[
                ("readonly", "pressed", AppTheme.BG_CARD_LIGHT),
                ("readonly", "hover", AppTheme.BG_CARD_LIGHT),
                ("readonly", AppTheme.BG_CARD),
                ("active", AppTheme.BG_CARD_LIGHT),
                ("pressed", AppTheme.BG_CARD_LIGHT),
                ("!disabled", AppTheme.BG_CARD),
            ],
            arrowcolor=[
                ("disabled", AppTheme.TEXT_MUTED),
                ("pressed", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("readonly", AppTheme.TEXT_MAIN),
                ("!disabled", AppTheme.TEXT_MAIN),
            ],
            bordercolor=[
                ("focus", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("!disabled", AppTheme.BORDER),
            ],
            lightcolor=[
                ("focus", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("!disabled", AppTheme.BORDER),
            ],
            darkcolor=[
                ("focus", AppTheme.ACCENT),
                ("hover", AppTheme.ACCENT),
                ("!disabled", AppTheme.BORDER),
            ],
        )

        # Cấu hình TEntry
        style.configure("TEntry",
            fieldbackground=AppTheme.BG_INPUT,
            foreground=AppTheme.TEXT_MAIN,
            bordercolor=AppTheme.BORDER,
            lightcolor=AppTheme.BORDER,
            darkcolor=AppTheme.BORDER,
            insertcolor=AppTheme.TEXT_MAIN,
            selectbackground=AppTheme.ACCENT,
            selectforeground="#ffffff",
            padding=[4, 2],
        )
        style.map("TEntry",
            fieldbackground=[
                ("readonly", AppTheme.BG_INPUT),
                ("disabled", AppTheme.BG_CARD),
                ("focus", AppTheme.BG_INPUT),
                ("!disabled", AppTheme.BG_INPUT),
            ],
            foreground=[
                ("readonly", AppTheme.TEXT_MAIN),
                ("disabled", AppTheme.TEXT_MUTED),
                ("focus", AppTheme.TEXT_MAIN),
                ("!disabled", AppTheme.TEXT_MAIN),
            ],
            bordercolor=[
                ("focus", AppTheme.ACCENT),
                ("!disabled", AppTheme.BORDER),
            ],
        )

        style.configure("Vertical.TScrollbar",
            background=AppTheme.BG_INPUT,
            troughcolor=AppTheme.BG_DARK,
            bordercolor=AppTheme.BG_DARK,
            arrowcolor=AppTheme.TEXT_MUTED
        )
        style.configure("Horizontal.TScrollbar",
            background=AppTheme.BG_INPUT,
            troughcolor=AppTheme.BG_DARK,
            bordercolor=AppTheme.BG_DARK,
            arrowcolor=AppTheme.TEXT_MUTED
        )
        style.configure("TNotebook", background=AppTheme.BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab",
            background=AppTheme.BG_CARD,
            foreground=AppTheme.TEXT_MUTED,
            padding=[20, 10],
            font=AppTheme.FONT_HEADER,
            borderwidth=0
        )
        style.map("TNotebook.Tab",
            background=[("selected", AppTheme.BG_INPUT), ("active", AppTheme.BG_CARD_LIGHT)],
            foreground=[("selected", AppTheme.ACCENT), ("active", AppTheme.TEXT_MAIN)]
        )

    def on_email_service_changed(self, event=None):
        srv = self.get_selected_email_service()
        self.config["email_service"] = srv
        display_label = self.cb_email_provider.get()
        if srv in ("custom_hotmail", "dongvanfb", "smail1s", "hotmail"):
            count = self.refresh_hotmail_count()
            self.log(f"[*] Đã chọn: {display_label} -> Dùng kho hotmails.txt (Hiện có {count} mail).", "success")
        elif srv == "account_email":
            self.log(f"[*] Đã chọn: {display_label} -> Tự động dùng Email & Mật khẩu/OAuth đi kèm trong danh sách acc đã nhập.", "info")
        elif "metaking" in srv:
            if srv == "metaking_gmail":
                self.config["metaking_service_type"] = "email"
                self.config["metaking_domain"] = "gmail.com"
                if hasattr(self, "cb_metaking_domain"):
                    self.cb_metaking_domain.set("gmail.com (Gmail - 1,422đ)")
                if hasattr(self, "var_metaking_service_type"):
                    self.var_metaking_service_type.set("email")
                    self.on_metaking_service_type_changed()
                self.log("[*] Đã chọn: 👑 Metaking -> Thuê Gmail (gmail.com - 1,422đ) nhận OTP Facebook.", "success")
            elif srv == "metaking_icloud":
                self.config["metaking_service_type"] = "email"
                self.config["metaking_domain"] = "icloud.com"
                if hasattr(self, "cb_metaking_domain"):
                    self.cb_metaking_domain.set("icloud.com (iCloud - 417đ)")
                if hasattr(self, "var_metaking_service_type"):
                    self.var_metaking_service_type.set("email")
                    self.on_metaking_service_type_changed()
                self.log("[*] Đã chọn: 👑 Metaking -> Thuê iCloud (icloud.com - 417đ) nhận OTP Facebook.", "success")
            elif srv == "metaking_hotmail":
                self.config["metaking_service_type"] = "email"
                self.config["metaking_domain"] = "hotmail.com"
                if hasattr(self, "cb_metaking_domain"):
                    self.cb_metaking_domain.set("hotmail.com (Hotmail - 89đ)")
                if hasattr(self, "var_metaking_service_type"):
                    self.var_metaking_service_type.set("email")
                    self.on_metaking_service_type_changed()
                self.log("[*] Đã chọn: 👑 Metaking -> Thuê Hotmail (hotmail.com - 89đ) nhận OTP Facebook.", "success")
            elif srv == "metaking_outlook":
                self.config["metaking_service_type"] = "email"
                self.config["metaking_domain"] = "outlook.com"
                if hasattr(self, "cb_metaking_domain"):
                    self.cb_metaking_domain.set("outlook.com (Outlook - 89đ)")
                if hasattr(self, "var_metaking_service_type"):
                    self.var_metaking_service_type.set("email")
                    self.on_metaking_service_type_changed()
                self.log("[*] Đã chọn: 👑 Metaking -> Thuê Outlook (outlook.com - 89đ) nhận OTP Facebook.", "success")
            elif srv == "metaking_phone":
                self.config["metaking_service_type"] = "phone"
                if hasattr(self, "var_metaking_service_type"):
                    self.var_metaking_service_type.set("phone")
                    self.on_metaking_service_type_changed()
                c_id = self.config.get("metaking_country_id", 154)
                self.log(f"[*] Đã chọn: 👑 Metaking -> Thuê SĐT SMS Facebook (Quốc gia ID: {c_id}).", "success")
            else:
                self.log(f"[*] Đã chọn: {display_label} -> Thuê OTP qua API Metaking.top (Server {self.config.get('metaking_server', 1)}, Domain {self.config.get('metaking_domain', 'gmail.com')}).", "success")
        elif srv == "clean_trio":
            doms = self.get_selected_custom_domains()
            dom_str = ", ".join(["@" + d for d in doms])
            self.log(f"[*] Đã chọn: {display_label} -> Luân phiên ngẫu nhiên giữa {len(doms)} đuôi đã tick: {dom_str}.", "success")
        elif srv == "smail1s_domain":
            if hasattr(self, "var_domain_smail1s"):
                self.var_domain_smail1s.set(True)
                self.var_domain_laoia.set(False)
                self.var_domain_smailwork.set(False)
                self.config["selected_custom_domains"] = ["smail1s.com"]
            self.log(f"[*] Đã chọn: {display_label} -> Khóa cứng duy nhất 1 đuôi @smail1s.com.", "success")
        elif srv == "laoia_domain":
            if hasattr(self, "var_domain_laoia"):
                self.var_domain_smail1s.set(False)
                self.var_domain_laoia.set(True)
                self.var_domain_smailwork.set(False)
                self.config["selected_custom_domains"] = ["laoia.com"]
            self.log(f"[*] Đã chọn: {display_label} -> Khóa cứng duy nhất 1 đuôi @laoia.com.", "success")
        elif srv == "smailwork_domain":
            if hasattr(self, "var_domain_smailwork"):
                for d, var_name in self.CLEAN_DOMAINS_MAP:
                    v = getattr(self, var_name, None)
                    if v:
                        v.set(d == "smailwork.com")
                self.config["selected_custom_domains"] = ["smailwork.com"]
            self.log(f"[*] Đã chọn: {display_label} -> Khóa cứng duy nhất 1 đuôi @smailwork.com (pqudx6448).", "success")
        elif srv == "hotmailtrusted_domain":
            for d, var_name in self.CLEAN_DOMAINS_MAP:
                v = getattr(self, var_name, None)
                if v:
                    v.set(d == "hotmailtrusted.com")
            self.config["selected_custom_domains"] = ["hotmailtrusted.com"]
            self.log(f"[*] Đã chọn: {display_label} -> Khóa cứng duy nhất 1 đuôi @hotmailtrusted.com.", "success")
        elif srv == "mailtoplus_domain":
            for d, var_name in self.CLEAN_DOMAINS_MAP:
                v = getattr(self, var_name, None)
                if v:
                    v.set(d == "mailto.plus")
            self.config["selected_custom_domains"] = ["mailto.plus"]
            self.log(f"[*] Đã chọn: {display_label} -> Khóa cứng duy nhất 1 đuôi @mailto.plus.", "success")
        elif srv == "auto_rotator":
            self.log(f"[*] Đã chọn: {display_label} -> Lấy ngẫu nhiên (Random) từ tất cả các nguồn mail ảo tồn tại (11 nguồn), không lấy lần lượt.", "success")
        else:
            self.log(f"[*] Đã chọn: {display_label} -> Hòm thư ảo tạo tự động, không trừ kho Hotmail.", "info")

    def on_reg_mode_changed(self):
        mode = self.var_reg_mode.get()
        self.config["reg_mode"] = mode
        if mode == "vr":
            if hasattr(self, "cb_bait_mode"):
                self.cb_bait_mode.config(state="readonly")
            self.log("[*] Đã chọn chế độ VR OTP: Bắt buộc xác minh mã OTP gửi về Email (Acc LIVE chuẩn có Email & 2FA).", "success")
            if hasattr(self, "frame_nvr_management"):
                self.frame_nvr_management.pack_forget()
            if hasattr(self, "frame_reg_settings") and hasattr(self, "spn_frame"):
                self.frame_reg_settings.pack(fill=tk.X, pady=(2, 4), before=self.spn_frame)
            if hasattr(self, "lbl_accounts_target"):
                self.lbl_accounts_target.config(text="Số acc cần tạo:")
            if hasattr(self, "btn_start"):
                self.btn_start.config(text="▶ BẮT ĐẦU REG TÀI KHOẢN")
        elif mode == "verify_nvr":
            self.log("[*] Đã chọn chế độ XÁC MINH ACC NVR: Gắn Email mới & Xác thực mã OTP cho danh sách acc đã nhập.", "info")
            if hasattr(self, "frame_reg_settings"):
                self.frame_reg_settings.pack_forget()
            if hasattr(self, "frame_nvr_management") and hasattr(self, "spn_frame"):
                self.frame_nvr_management.pack(fill=tk.X, pady=(2, 4), before=self.spn_frame)
            if hasattr(self, "lbl_accounts_target"):
                self.lbl_accounts_target.config(text="Số acc cần XM:")
            
            # Tự động nạp tài khoản vào bảng nếu bảng đang trống
            if hasattr(self, "tree") and not self.tree.get_children():
                self.populate_table_with_nvr_accounts()
            else:
                count = len(self.tree.get_children()) if hasattr(self, "tree") else len(getattr(self, "nvr_accounts_queue", []))
                if hasattr(self, "btn_start"):
                    self.btn_start.config(text=f"▶ BẮT ĐẦU XÁC MINH ({count} ACC NVR)")
        elif mode in ("ios_bloks", "bloks_ios", "regfb"):
            curr_srv = self.get_selected_email_service() if hasattr(self, "get_selected_email_service") else self.config.get("email_service", "")
            disp_name = self.EMAIL_PROVIDER_REVERSE.get(curr_srv, curr_srv) if hasattr(self, "EMAIL_PROVIDER_REVERSE") else curr_srv
            curr_bm = self.get_selected_bait_mode()
            bm_lbl = "Mồi Gmail" if curr_bm == "gmail" else ("Mồi SĐT" if curr_bm == "phone" else "Email trực tiếp")
            self.log(f"[*] Đã chọn chế độ 🍏 iOS Bloks Native (regfb.py) [XM: {disp_name} | {bm_lbl}]: Khởi tạo phiên qua iOS GraphQL Bloks CAA.", "success")
            if curr_bm == "gmail":
                self.log("[*] iOS Bloks Native (regfb.py): M?i Gmail ?o t?o UID + X?c minh OTP Email theo setting.", "info")
            elif curr_bm == "phone":
                self.log("[*] iOS Bloks Native (regfb.py): M?i S?T ?o theo IP t?o UID + X?c minh OTP Email theo setting.", "info")
            else:
                self.log("[*] iOS Bloks Native (regfb.py): ??ng k? Email tr?c ti?p chu?n regfb.py + X?c minh OTP.", "info")
            if hasattr(self, "cb_bait_mode"):
                self.cb_bait_mode.config(state="readonly")
            if hasattr(self, "frame_nvr_management"):
                self.frame_nvr_management.pack_forget()
            if hasattr(self, "frame_reg_settings") and hasattr(self, "spn_frame"):
                self.frame_reg_settings.pack(fill=tk.X, pady=(2, 4), before=self.spn_frame)
            if hasattr(self, "lbl_accounts_target"):
                self.lbl_accounts_target.config(text="Số acc cần tạo:")
            if hasattr(self, "btn_start"):
                self.btn_start.config(text="▶ BẮT ĐẦU REG iOS BLOKS (regfb.py)")
        elif mode in ("legacy_nv", "legacy"):
            if hasattr(self, "cb_bait_mode"):
                self.cb_bait_mode.config(state="readonly")
            leg_ver = self.get_selected_legacy_verify_mode()
            if leg_ver in ("setting", "verify", "email", "phone"):
                curr_srv = self.get_selected_email_service() if hasattr(self, "get_selected_email_service") else self.config.get("email_service", "")
                curr_stype = self.config.get("metaking_service_type", "")
                is_phone = (curr_srv == "metaking_phone" or curr_stype == "phone")
                if "metaking" in curr_srv:
                    m_dom = self.config.get("metaking_domain", "gmail.com")
                    srv_label = f"👑 Metaking SĐT FB" if is_phone else f"👑 Metaking ({m_dom})"
                elif "custom_hotmail" in curr_srv or "hotmail" in curr_srv:
                    srv_label = "Hotmail (hotmails.txt)"
                elif "10minute" in curr_srv:
                    srv_label = "10MinuteMail (@laoia.com)"
                else:
                    disp_name = self.EMAIL_PROVIDER_REVERSE.get(curr_srv, curr_srv) if hasattr(self, "EMAIL_PROVIDER_REVERSE") else curr_srv
                    srv_label = disp_name
                self.log(f"[*] Đã chọn chế độ Mr-SxR Legacy NV + XÁC MINH THEO SETTING [Dịch vụ: {srv_label}]: Đăng ký Web/Mobile & Xác thực OTP.", "accent")
                if hasattr(self, "btn_start"):
                    self.btn_start.config(text="▶ BẮT ĐẦU REG & XM THEO SETTING (Mr-SxR)")
            else:
                self.log("[*] Đã chọn chế độ Mr-SxR Legacy NV: Đăng ký Web/Mobile nguyên bản Mr-SxR (Trích xuất 10 Tokens, No-Verify).", "accent")
                if hasattr(self, "btn_start"):
                    self.btn_start.config(text="▶ BẮT ĐẦU REG TÀI KHOẢN (Mr-SxR)")
            if hasattr(self, "frame_nvr_management"):
                self.frame_nvr_management.pack_forget()
            if hasattr(self, "frame_reg_settings") and hasattr(self, "spn_frame"):
                self.frame_reg_settings.pack(fill=tk.X, pady=(2, 4), before=self.spn_frame)
            if hasattr(self, "lbl_accounts_target"):
                self.lbl_accounts_target.config(text="Số acc cần tạo:")
        else:
            self.log("[*] Đã chọn chế độ NVR (No-Verify): Đăng ký siêu tốc bằng mồi SĐT ảo, không cần chờ OTP.", "warning")
            if hasattr(self, "frame_nvr_management"):
                self.frame_nvr_management.pack_forget()
            if hasattr(self, "frame_reg_settings") and hasattr(self, "spn_frame"):
                self.frame_reg_settings.pack(fill=tk.X, pady=(2, 4), before=self.spn_frame)
            if hasattr(self, "lbl_accounts_target"):
                self.lbl_accounts_target.config(text="Số acc cần tạo:")
            if hasattr(self, "btn_start"):
                self.btn_start.config(text="▶ BẮT ĐẦU REG TÀI KHOẢN")

    def toggle_mask_metaking_key(self):
        if not hasattr(self, "entry_metaking_key"):
            return
        if self.entry_metaking_key.cget("show") == "*":
            self.entry_metaking_key.config(show="")
            if hasattr(self, "btn_toggle_metaking_key"):
                self.btn_toggle_metaking_key.config(text="🔒 Ẩn Key")
        else:
            self.entry_metaking_key.config(show="*")
            if hasattr(self, "btn_toggle_metaking_key"):
                self.btn_toggle_metaking_key.config(text="👁 Hiện Key")

    def on_metaking_service_type_changed(self):
        st = self.var_metaking_service_type.get()
        if st == "phone":
            if hasattr(self, "frame_metaking_email_opts"):
                self.frame_metaking_email_opts.pack_forget()
            if hasattr(self, "frame_metaking_phone_opts"):
                self.frame_metaking_phone_opts.pack(fill=tk.X, pady=(4, 2))
            if hasattr(self, "cb_email_provider"):
                self.cb_email_provider.set("👑 Metaking: Thuê SĐT SMS FB (Yemen / VN / US / Đa Quốc Gia)")
                self.config["email_service"] = "metaking_phone"
        else:
            if hasattr(self, "frame_metaking_phone_opts"):
                self.frame_metaking_phone_opts.pack_forget()
            if hasattr(self, "frame_metaking_email_opts"):
                self.frame_metaking_email_opts.pack(fill=tk.X, pady=(4, 2))
            raw_d = self.cb_metaking_domain.get().strip().lower() if hasattr(self, "cb_metaking_domain") else "gmail"
            if "gmail" in raw_d:
                disp = "👑 Metaking: Thuê Gmail (gmail.com)"
                srv = "metaking_gmail"
            elif "icloud" in raw_d:
                disp = "👑 Metaking: Thuê iCloud (icloud.com)"
                srv = "metaking_icloud"
            elif "hotmail" in raw_d:
                disp = "👑 Metaking: Thuê Hotmail (hotmail.com)"
                srv = "metaking_hotmail"
            elif "outlook" in raw_d:
                disp = "👑 Metaking: Thuê Outlook (outlook.com)"
                srv = "metaking_outlook"
            else:
                disp = "👑 Thuê OTP Metaking.top (Gmail / iCloud / Hotmail / SĐT)"
                srv = "metaking"
            if hasattr(self, "cb_email_provider"):
                self.cb_email_provider.set(disp)
                self.config["email_service"] = srv

    def test_metaking_api_key(self):
        key = self.entry_metaking_key.get().strip() if hasattr(self, "entry_metaking_key") else self.config.get("metaking_api_key", "")
        if not key:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập API Key Metaking trước khi kiểm tra!")
            return
        if hasattr(self, "lbl_metaking_status"):
            self.lbl_metaking_status.config(text="⏳ Đang kiểm tra kết nối Metaking...", fg=AppTheme.WARNING)

        def _do_test():
            from core.email_service import MetakingEmailProvider
            res = MetakingEmailProvider.test_api_key(key)
            def _update_ui():
                if res.get("success"):
                    bal = res.get("balance")
                    bal_text = f" | Số dư: {bal:,}đ" if isinstance(bal, (int, float)) else (f" | Số dư: {bal}" if bal else "")
                    self.lbl_metaking_status.config(
                        text=f"🟢 API Hợp Lệ{bal_text} | Kết nối thành công!",
                        fg=AppTheme.SUCCESS
                    )
                    self.log(f"[Metaking] Kiểm tra thành công: {res.get('message')}{bal_text}", "success")
                    self.fetch_metaking_email_prices()
                    self.fetch_metaking_phone_prices()
                else:
                    self.lbl_metaking_status.config(
                        text=f"🔴 Lỗi: {res.get('message')}",
                        fg=AppTheme.DANGER
                    )
                    self.log(f"[Metaking] Kiểm tra thất bại: {res.get('message')}", "error")
            self.safe_ui_call(_update_ui)

        threading.Thread(target=_do_test, daemon=True).start()

    def fetch_metaking_email_prices(self):
        key = self.entry_metaking_key.get().strip() if hasattr(self, "entry_metaking_key") else self.config.get("metaking_api_key", "")
        if not key:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập API Key Metaking!")
            return
        raw_srv = self.cb_metaking_server.get() if hasattr(self, "cb_metaking_server") else "1"
        m = re.search(r'\d+', raw_srv)
        srv_num = int(m.group(0)) if m else 1
        if hasattr(self, "lbl_metaking_price_result"):
            self.lbl_metaking_price_result.config(text=f"⏳ Đang tải giá Server {srv_num}...", fg=AppTheme.WARNING)

        def _do_fetch():
            from core.email_service import MetakingEmailProvider
            prices = MetakingEmailProvider.get_email_prices(key, service_id=1, server=srv_num)
            def _update():
                if prices:
                    info_parts = []
                    domains = []
                    for p in prices:
                        dom = p.get("domain", "")
                        pr = p.get("price_vnd") or p.get("price", 0)
                        qty = p.get("quantity", 0)
                        info_parts.append(f"{dom}: {pr:,}đ (Còn {qty:,})")
                        if dom:
                            domains.append(dom)
                    if domains and hasattr(self, "cb_metaking_domain"):
                        self.cb_metaking_domain.config(values=domains)
                    txt = " | ".join(info_parts[:4])
                    self.lbl_metaking_price_result.config(text=f"✅ {txt}", fg=AppTheme.SUCCESS)
                    self.log(f"[Metaking] Bảng giá Server {srv_num}: {txt}", "info")
                else:
                    self.lbl_metaking_price_result.config(text="⚠️ Không lấy được giá (Hết hàng hoặc server bận)", fg=AppTheme.WARNING)
            self.root.after(0, _update)

        threading.Thread(target=_do_fetch, daemon=True).start()

    def fetch_metaking_phone_prices(self):
        key = self.entry_metaking_key.get().strip() if hasattr(self, "entry_metaking_key") else self.config.get("metaking_api_key", "")
        if not key:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập API Key Metaking!")
            return
        if hasattr(self, "lbl_metaking_phone_result"):
            self.lbl_metaking_phone_result.config(text="⏳ Đang tải danh sách quốc gia Facebook...", fg=AppTheme.WARNING)

        def _do_fetch():
            from core.email_service import MetakingEmailProvider
            prices = MetakingEmailProvider.get_phone_prices(key, service_id=67)
            def _update():
                if prices:
                    info_parts = []
                    c_items = []
                    flag_map = {154: "🇾🇪", 118: "🇸🇦", 20: "🇪🇹", 81: "🇨🇱", 9: "🇮🇩", 35: "🇨🇴", 206: "🇺🇸", 18: "🇰🇭", 58: "🇧🇷", 3: "🇺🇸", 89: "🇻🇳", 57: "🇮🇳", 4: "🇵🇱", 5: "🇩🇪", 65: "🇿🇦", 16: "🇬🇧", 54: "🇭🇰", 86: "🇵🇹", 85: "🇨🇭"}
                    for p in prices:
                        c_id = p.get("country_id")
                        c_name = p.get("country_name", "")
                        pr = p.get("price_vnd") or p.get("price", 0)
                        qty = p.get("quantity", 0)
                        flag = flag_map.get(c_id, "🌐")
                        c_item = f"{flag} [{c_id}] {c_name} - {pr:,}đ (Còn {qty:,} số)"
                        c_items.append(c_item)
                        if len(info_parts) < 3:
                            info_parts.append(f"[{c_id}] {c_name}: {pr:,}đ")
                    if hasattr(self, "cb_metaking_country"):
                        self.cb_metaking_country["values"] = c_items
                    txt = " | ".join(info_parts)
                    self.lbl_metaking_phone_result.config(text=f"✅ Đã tải {len(prices)} quốc gia (Top rẻ: {txt})", fg=AppTheme.SUCCESS)
                    self.log(f"[Metaking Phone] Đã nạp {len(prices)} quốc gia SĐT Facebook vào danh sách chọn!", "info")
                else:
                    self.lbl_metaking_phone_result.config(text="⚠️ Không lấy được danh sách quốc gia SĐT", fg=AppTheme.WARNING)
            self.root.after(0, _update)

        threading.Thread(target=_do_fetch, daemon=True).start()

    def select_metaking_as_primary(self):
        st = self.var_metaking_service_type.get() if hasattr(self, "var_metaking_service_type") else self.config.get("metaking_service_type", "email")
        if st == "phone":
            display_name = "👑 Metaking: Thuê SĐT SMS FB (Yemen / VN / US / Đa Quốc Gia)"
            target_srv = "metaking_phone"
        else:
            raw_d = self.cb_metaking_domain.get().strip().lower() if hasattr(self, "cb_metaking_domain") else self.config.get("metaking_domain", "gmail")
            if "gmail" in raw_d:
                display_name = "👑 Metaking: Thuê Gmail (gmail.com)"
                target_srv = "metaking_gmail"
            elif "icloud" in raw_d:
                display_name = "👑 Metaking: Thuê iCloud (icloud.com)"
                target_srv = "metaking_icloud"
            elif "hotmail" in raw_d:
                display_name = "👑 Metaking: Thuê Hotmail (hotmail.com)"
                target_srv = "metaking_hotmail"
            elif "outlook" in raw_d:
                display_name = "👑 Metaking: Thuê Outlook (outlook.com)"
                target_srv = "metaking_outlook"
            else:
                display_name = "👑 Thuê OTP Metaking.top (Gmail / iCloud / Hotmail / SĐT)"
                target_srv = "metaking"

        if hasattr(self, "cb_email_provider"):
            self.cb_email_provider.set(display_name)
        self.config["email_service"] = target_srv
        self.save_config(show_toast=False)
        messagebox.showinfo("Thành công", f"Đã chọn {display_name} làm nguồn cấp OTP mặc định cho hệ thống!")
        self.log(f"[*] Đã đặt {display_name} làm nguồn nhận OTP mặc định!", "success")

    def build_ui(self):
        # 1. Header Frame - Đã bỏ IP và thông tin linh tinh góc phải theo yêu cầu
        header = tk.Frame(self.root, bg=AppTheme.BG_CARD, height=54, bd=0)
        header.pack(fill=tk.X, side=tk.TOP, padx=12, pady=(10, 8))

        lbl_title = tk.Label(
            header,
            text="⚡ TOOL REG FB ĐA LUỒNG - VR OTP & NVR ENGINE",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        )
        lbl_title.pack(side=tk.LEFT, padx=14, pady=10)

        lbl_sub = tk.Label(
            header,
            text="• Hỗ trợ Mồi SĐT Ảo • Xác minh Hotmail / Virtual Mail • Đa Key KiotProxy • 2FA",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        )
        lbl_sub.pack(side=tk.LEFT, padx=6, pady=10)

        # 2. Main Tabbed Notebook Container (Tabs riêng biệt, không chung 1 màn hình)
        main_content = tk.Frame(self.root, bg=AppTheme.BG_DARK)
        main_content.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self.notebook = ttk.Notebook(main_content)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_dashboard = tk.Frame(self.notebook, bg=AppTheme.BG_DARK)
        self.tab_settings = tk.Frame(self.notebook, bg=AppTheme.BG_DARK)
        self.tab_utilities = tk.Frame(self.notebook, bg=AppTheme.BG_DARK)

        self.notebook.add(self.tab_dashboard, text="  📊 BẢNG ĐIỀU KHIỂN & TIẾN TRÌNH  ")
        self.notebook.add(self.tab_settings, text="  ⚙️ CÀI ĐẶT CẤU HÌNH & METAKING  ")
        self.notebook.add(self.tab_utilities, text="  🛠️ TIỆN ÍCH HỆ THỐNG  ")
        self.tab_meta_otp = tk.Frame(self.notebook, bg=AppTheme.BG_DARK)
        # self.notebook.add(self.tab_meta_otp, text="  📲 META AI AUTO OTP (GỬI OTP SĐT)  ")  # An tab theo yeu cau

        # Canvas & Scrollbar cho Tab Cài Đặt (toàn màn hình rộng rãi, cuộn mượt)
        self.left_canvas = tk.Canvas(
            self.tab_settings,
            bg=AppTheme.BG_DARK,
            bd=0,
            highlightthickness=0
        )
        self.left_scrollbar = ttk.Scrollbar(
            self.tab_settings,
            orient=tk.VERTICAL,
            command=self.left_canvas.yview
        )
        self.left_scrollable_frame = tk.Frame(self.left_canvas, bg=AppTheme.BG_DARK)

        self.left_canvas_window = self.left_canvas.create_window(
            (0, 0),
            window=self.left_scrollable_frame,
            anchor="nw"
        )

        def _on_left_frame_configure(event):
            self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

        def _on_left_canvas_configure(event):
            canvas_w = max(700, event.width)
            self.left_canvas.itemconfig(self.left_canvas_window, width=canvas_w)

        self.left_scrollable_frame.bind("<Configure>", _on_left_frame_configure)
        self.left_canvas.bind("<Configure>", _on_left_canvas_configure)
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)

        self.left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        self.left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Xây dựng nội dung Settings trước để các biến cấu hình được gán đầy đủ
        self.build_left_settings(self.left_scrollable_frame)

        # Xây dựng Dashboard (nằm trên Tab 1, bảng hiển thị rộng toàn màn hình)
        self.build_right_monitoring(self.tab_dashboard)
        self.build_meta_otp_tab(self.tab_meta_otp)
        self.build_utilities_tab(self.tab_utilities)

        # Đồng bộ chế độ hiển thị nút bắt đầu theo cấu hình
        self.on_reg_mode_changed()

        # Smooth mousewheel scrolling thông minh cho toàn bộ giao diện: Tự động điều hướng tới widget dưới con trỏ, không giật lag
        def _global_mousewheel_dispatch(event):
            try:
                w = self.root.winfo_containing(event.x_root, event.y_root)
                if not w:
                    return
                # 1. Bảng danh sách tài khoản
                if hasattr(self, "tree") and (w == self.tree or str(w).startswith(str(self.tree))):
                    delta = int(-1 * (event.delta / 120) * 3)
                    self.tree.yview_scroll(delta, "units")
                    return "break"
                # 2. Hộp nhật ký Log
                if hasattr(self, "txt_logs") and (w == self.txt_logs or str(w).startswith(str(self.txt_logs))):
                    delta = int(-1 * (event.delta / 120) * 3)
                    self.txt_logs.yview_scroll(delta, "units")
                    y_pos = self.txt_logs.yview()
                    self._auto_scroll_logs = (len(y_pos) >= 2 and y_pos[1] >= 0.985)
                    return "break"
                # 3. Canvas cài đặt bên trái (Cuộn siêu mượt, loại bỏ bbox tính toán lại gây đơ)
                if hasattr(self, "left_canvas") and (w == self.left_canvas or str(w).startswith(str(self.left_canvas)) or (hasattr(self, "left_scrollable_frame") and str(w).startswith(str(self.left_scrollable_frame)))):
                    delta = int(-1 * (event.delta / 120) * 3)
                    self.left_canvas.yview_scroll(delta, "units")
                    return "break"
            except Exception:
                pass

        try:
            self.root.bind_all("<MouseWheel>", _global_mousewheel_dispatch)
        except Exception:
            pass

        # Pre-warm kho Proxy Free LIVE trong RAM ngay khi bat dau mo Tool
        def _prewarm_proxy():
            try:
                from core.proxy_manager import FreeProxyManager
                fm = FreeProxyManager()
                fm.start_continuous_validator(target_buffer=100)
            except Exception:
                pass
        threading.Thread(target=_prewarm_proxy, daemon=True, name="Prewarm-ProxyPool").start()

    def build_left_settings(self, parent: tk.Frame):
        # Card 1: Tích hợp API Metaking.top
        card_metaking = tk.LabelFrame(
            parent,
            text=" 👑 1. Tích Hợp API Thuê OTP Metaking.top (metaking.top) ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        card_metaking.pack(fill=tk.X, pady=(0, 8))

        mk_key_frame = tk.Frame(card_metaking, bg=AppTheme.BG_CARD)
        mk_key_frame.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            mk_key_frame,
            text="Metaking API Key:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        self.entry_metaking_key = tk.Entry(
            mk_key_frame,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            show="*",
            font=AppTheme.FONT_CODE
        )
        saved_mk_key = self.config.get("metaking_api_key", "")
        self.entry_metaking_key.insert(0, saved_mk_key)
        self.entry_metaking_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 4))

        self.btn_toggle_metaking_key = tk.Button(
            mk_key_frame,
            cursor="hand2",
            text="👁 Hiện Key",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MUTED,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=6,
            pady=1,
            command=self.toggle_mask_metaking_key
        )
        self.btn_toggle_metaking_key.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_test_metaking = tk.Button(
            mk_key_frame,
            cursor="hand2",
            text="🔍 Test API & Số Dư",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=8,
            pady=1,
            command=self.test_metaking_api_key
        )
        self.btn_test_metaking.pack(side=tk.LEFT)

        init_mk_text = "● Trạng thái: 🟢 Đã lưu API Key | Bấm 'Test API & Số Dư' để tải số dư & tồn kho realtime" if saved_mk_key else "● Trạng thái: Chưa kiểm tra (Nhập API Key và bấm 'Test API & Số Dư')"
        init_mk_fg = AppTheme.SUCCESS if saved_mk_key else AppTheme.TEXT_MUTED
        self.lbl_metaking_status = tk.Label(
            card_metaking,
            text=init_mk_text,
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=init_mk_fg,
            anchor="w"
        )
        self.lbl_metaking_status.pack(fill=tk.X, pady=(2, 6))

        srv_type_frame = tk.Frame(card_metaking, bg=AppTheme.BG_CARD)
        srv_type_frame.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            srv_type_frame,
            text="Hình thức thuê:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.var_metaking_service_type = tk.StringVar(value=self.config.get("metaking_service_type", "email"))

        rb_mk_email = tk.Radiobutton(
            srv_type_frame,
            text="📧 Thuê Email OTP (Gmail / iCloud / Hotmail / Outlook)",
            value="email",
            variable=self.var_metaking_service_type,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_metaking_service_type_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_mk_email.pack(side=tk.LEFT, padx=(0, 8))

        rb_mk_phone = tk.Radiobutton(
            srv_type_frame,
            text="📱 Thuê Số SĐT (SMS Facebook)",
            value="phone",
            variable=self.var_metaking_service_type,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_metaking_service_type_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_mk_phone.pack(side=tk.LEFT)

        self.frame_metaking_email_opts = tk.Frame(card_metaking, bg=AppTheme.BG_CARD)

        srv_grid = tk.Frame(self.frame_metaking_email_opts, bg=AppTheme.BG_CARD)
        srv_grid.pack(fill=tk.X, pady=(2, 4))

        tk.Label(srv_grid, text="Cụm Server:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).grid(row=0, column=0, sticky="w", pady=2)
        self.cb_metaking_server = ttk.Combobox(
            srv_grid,
            values=[
                "Server 1 (Đa Domain: Gmail, iCloud, Hotmail, Outlook)",
                "Server 2 (Gmail - Giữ nguyên email khi next)",
                "Server 3 (Gmail)",
                "Server 4 (Gmail Facebook low/high)",
                "Server 5 (Gmail)"
            ],
            width=38,
            state="readonly"
        )
        cur_srv = self.config.get("metaking_server", 1)
        srv_map_idx = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}
        self.cb_metaking_server.current(srv_map_idx.get(cur_srv, 0))
        self.cb_metaking_server.grid(row=0, column=1, sticky="w", padx=(6, 12), pady=2)

        tk.Label(srv_grid, text="Domain:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).grid(row=0, column=2, sticky="w", pady=2)
        self.cb_metaking_domain = ttk.Combobox(
            srv_grid,
            values=[
                "gmail.com (Gmail - 1,422đ)",
                "icloud.com (iCloud - 417đ)",
                "hotmail.com (Hotmail - 89đ)",
                "outlook.com (Outlook - 89đ)",
            ],
            width=28
        )
        saved_dom = self.config.get("metaking_domain", "gmail.com")
        matched_dom = next((v for v in self.cb_metaking_domain["values"] if saved_dom in v), saved_dom)
        self.cb_metaking_domain.set(matched_dom)
        self.cb_metaking_domain.grid(row=0, column=3, sticky="w", padx=(6, 0), pady=2)

        def on_metaking_domain_selected(event=None):
            raw_d = self.cb_metaking_domain.get().strip().lower()
            if "gmail" in raw_d:
                target_srv = "metaking_gmail"
                display_label = "👑 Metaking: Thuê Gmail (gmail.com)"
                dom_clean = "gmail.com"
            elif "icloud" in raw_d:
                target_srv = "metaking_icloud"
                display_label = "👑 Metaking: Thuê iCloud (icloud.com)"
                dom_clean = "icloud.com"
            elif "hotmail" in raw_d:
                target_srv = "metaking_hotmail"
                display_label = "👑 Metaking: Thuê Hotmail (hotmail.com)"
                dom_clean = "hotmail.com"
            elif "outlook" in raw_d:
                target_srv = "metaking_outlook"
                display_label = "👑 Metaking: Thuê Outlook (outlook.com)"
                dom_clean = "outlook.com"
            else:
                target_srv = "metaking"
                display_label = "👑 Thuê OTP Metaking.top (Tùy Chọn Trong Cài Đặt)"
                dom_clean = raw_d.split()[0] if raw_d else "gmail.com"

            self.config["metaking_domain"] = dom_clean
            self.config["metaking_service_type"] = "email"
            if hasattr(self, "cb_email_provider"):
                self.cb_email_provider.set(display_label)
                self.config["email_service"] = target_srv
            self.log(f"[Metaking] 🎯 Đã chọn domain '{dom_clean}' ➔ Tự động đồng bộ Dịch vụ Mail sang '{display_label}'!", "success")

        self.cb_metaking_domain.bind("<<ComboboxSelected>>", on_metaking_domain_selected)

        p_row = tk.Frame(self.frame_metaking_email_opts, bg=AppTheme.BG_CARD)
        p_row.pack(fill=tk.X, pady=(2, 4))

        tk.Label(p_row, text="Mức giá (Server 4):", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT)
        self.cb_metaking_price = ttk.Combobox(
            p_row,
            values=["low (Giá thấp - Tiết kiệm)", "high (Giá cao - Ưu tiên)"],
            width=26,
            state="readonly"
        )
        cur_p = self.config.get("metaking_price", "low")
        self.cb_metaking_price.current(1 if "high" in cur_p else 0)
        self.cb_metaking_price.pack(side=tk.LEFT, padx=(6, 10))

        btn_fetch_pr = tk.Button(
            p_row,
            cursor="hand2",
            text="⚡ Xem Bảng Giá & Tồn Kho Realtime",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            command=self.fetch_metaking_email_prices
        )
        btn_fetch_pr.pack(side=tk.LEFT)

        self.lbl_metaking_price_result = tk.Label(
            self.frame_metaking_email_opts,
            text="",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO,
            anchor="w"
        )
        self.lbl_metaking_price_result.pack(fill=tk.X, pady=(1, 4))

        self.frame_metaking_phone_opts = tk.Frame(card_metaking, bg=AppTheme.BG_CARD)

        phone_row = tk.Frame(self.frame_metaking_phone_opts, bg=AppTheme.BG_CARD)
        phone_row.pack(fill=tk.X, pady=(2, 4))

        tk.Label(phone_row, text="Dịch vụ: FB (ID 67)", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(phone_row, text="Quốc gia:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        metaking_country_list = [
            "🇾🇪 [154] Yemen - 313đ (Còn 4,967 số)",
            "🇸🇦 [118] Saudi Arabia - 313đ (Còn 4,996 số)",
            "🇪🇹 [20] Ethiopia - 313đ (Còn 4,628 số)",
            "🇨🇱 [81] Chile - 782đ (Còn 112 số)",
            "🇮🇩 [9] Indonesia - 782đ (Còn 282 số)",
            "🇨🇴 [35] Colombia - 860đ (Còn 8 số)",
            "🇺🇸 [206] United States (phone|otp) - 999đ (Còn 93 số)",
            "🇰🇭 [18] Cambodia - 1,563đ (Còn 5,000 số)",
            "🇧🇷 [58] Brazil - 1,797đ (Còn 427,243 số)",
            "🇺🇸 [3] United States (virtual) - 1,875đ (Còn 3,002 số)",
            "🇻🇳 [89] Việt Nam - 3,750đ (Còn 13,731 số)",
            "🇮🇳 [57] India - 4,218đ (Còn 303 số)",
            "🇵🇱 [4] Poland - 4,843đ (Còn 54 số)",
            "🇩🇪 [5] Germany - 6,249đ (Còn 90,001 số)",
            "🇿🇦 [65] South Africa - 6,952đ (Còn 13 số)",
            "🇬🇧 [16] United Kingdom - 7,342đ (Còn 317 số)",
            "🇭🇰 [54] Hong Kong - 7,733đ (Còn 28 số)",
            "🇵🇹 [86] Portugal - 8,904đ (Còn 94,520 số)",
            "🇨🇭 [85] Switzerland - 8,904đ (Còn 315 số)",
        ]
        self.cb_metaking_country = ttk.Combobox(
            phone_row,
            values=metaking_country_list,
            width=32
        )
        saved_c_id = self.config.get("metaking_country_id", 154)
        c_pattern = f"[{saved_c_id}]"
        matched_c = next((v for v in metaking_country_list if c_pattern in v), f"[{saved_c_id}]")
        self.cb_metaking_country.set(matched_c)
        self.cb_metaking_country.pack(side=tk.LEFT, padx=(6, 8))

        btn_fetch_ph = tk.Button(
            phone_row,
            cursor="hand2",
            text="⚡ Xem Giá & Quốc Gia SĐT",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            bd=1,
            relief="solid",
            command=self.fetch_metaking_phone_prices
        )
        btn_fetch_ph.pack(side=tk.LEFT)

        self.lbl_metaking_phone_result = tk.Label(
            self.frame_metaking_phone_opts,
            text="💡 Mặc định: Quốc gia 154 (Yemen) ~ 316đ/OTP, kho số dồi dào.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
            anchor="w"
        )
        self.lbl_metaking_phone_result.pack(fill=tk.X, pady=(1, 4))

        if self.config.get("metaking_service_type") == "phone":
            self.frame_metaking_phone_opts.pack(fill=tk.X, pady=(4, 2))
        else:
            self.frame_metaking_email_opts.pack(fill=tk.X, pady=(4, 2))

        btn_set_primary = tk.Button(
            card_metaking,
            cursor="hand2",
            text="🌟 ĐẶT METAKING.TOP LÀM NGUỒN NHẬN OTP CHÍNH (TỰ ĐỘNG CHỌN)",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            pady=4,
            command=self.select_metaking_as_primary
        )
        btn_set_primary.pack(fill=tk.X, pady=(4, 2))

        # Card 2: Chế độ & Luồng
        card_reg = tk.LabelFrame(
            parent,
            text=" ⚙ 2. Cấu hình Chế độ & Đa luồng ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        card_reg.pack(fill=tk.X, pady=(0, 8))

        # Mode Selection (VR OTP vs NVR vs XM Acc NVR - 2 Hàng Rõ Ràng, Không Bị Tràn)
        mode_box = tk.Frame(card_reg, bg=AppTheme.BG_CARD)
        mode_box.pack(fill=tk.X, pady=(2, 4))
        
        mode_row_title = tk.Frame(mode_box, bg=AppTheme.BG_CARD)
        mode_row_title.pack(fill=tk.X, pady=(0, 2))
        tk.Label(mode_row_title, text="Chế độ khởi tạo / xác minh:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        
        self.var_reg_mode = tk.StringVar(value=self.config.get("reg_mode", "vr"))
        
        # Row 1: 2 Chế độ tạo mới (VR OTP & NVR)
        mode_row1 = tk.Frame(mode_box, bg=AppTheme.BG_CARD)
        mode_row1.pack(fill=tk.X, pady=(1, 2))
        
        rb_vr = tk.Radiobutton(
            mode_row1,
            text="🟢 VR OTP (Xác minh Email)",
            value="vr",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_vr.pack(side=tk.LEFT, padx=(0, 6))
        
        rb_nvr = tk.Radiobutton(
            mode_row1,
            text="🟡 NVR (Bypass - Không OTP)",
            value="nvr",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY
        )
        rb_nvr.pack(side=tk.LEFT)

        rb_legacy = tk.Radiobutton(
            mode_row1,
            text="🚀 Legacy NV (Mr-SxR)",
            value="legacy_nv",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY
        )
        rb_legacy.pack(side=tk.LEFT, padx=(6, 0))

        # Row 2: Chế độ xác minh acc NVR riêng biệt, to rõ, hiển thị 100% không bị che khuất
        mode_row2 = tk.Frame(mode_box, bg=AppTheme.BG_CARD)
        mode_row2.pack(fill=tk.X, pady=(3, 2))
        rb_verify_nvr = tk.Radiobutton(
            mode_row2,
            text="⚡ XÁC MINH ACC NVR (Gắn Mail & Nhận OTP Thật)",
            value="verify_nvr",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_verify_nvr.pack(side=tk.LEFT)

        rb_ios_bloks = tk.Radiobutton(
            mode_row2,
            text="🍏 iOS Bloks (regfb.py)",
            value="ios_bloks",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_ios_bloks.pack(side=tk.LEFT, padx=(8, 0))

        # Row 3: Tùy chọn xác minh khi chạy Legacy NV (Mr-SxR)
        self.frame_legacy_opts = tk.Frame(mode_box, bg=AppTheme.BG_CARD)
        self.frame_legacy_opts.pack(fill=tk.X, pady=(2, 2))
        tk.Label(
            self.frame_legacy_opts,
            text="⚙️ Xác minh Legacy (Mr-SxR):",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        ).pack(side=tk.LEFT, padx=(0, 4))
        
        saved_leg_ver = self.config.get("legacy_verify_mode", "none")
        init_leg_lbl = self.REVERSE_LEGACY_VERIFY_MAP.get(saved_leg_ver, self.LEGACY_VERIFY_OPTIONS[0])
        self.cb_legacy_verify = ttk.Combobox(
            self.frame_legacy_opts,
            values=self.LEGACY_VERIFY_OPTIONS,
            state="readonly",
            font=AppTheme.FONT_SMALL,
            width=36
        )
        self.cb_legacy_verify.set(init_leg_lbl)
        self.cb_legacy_verify.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cb_legacy_verify.bind("<<ComboboxSelected>>", self.on_legacy_verify_changed)

        # Row 4: Tùy chọn Server FB cho Legacy NV (Mr-SxR)
        self.frame_legacy_server = tk.Frame(mode_box, bg=AppTheme.BG_CARD)
        self.frame_legacy_server.pack(fill=tk.X, pady=(2, 2))
        tk.Label(
            self.frame_legacy_server,
            text="🌐 Server FB (Legacy):",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        ).pack(side=tk.LEFT, padx=(0, 4))

        saved_mode = self.config.get("server_mode", "single")
        saved_rand_srv = (saved_mode == "random_all") or bool(self.config.get("random_server", False))
        saved_pool = self.get_selected_server_pool()
        pool_cnt = len(saved_pool)

        self.var_random_server = tk.BooleanVar(value=saved_rand_srv)
        self.chk_random_server = tk.Checkbutton(
            self.frame_legacy_server,
            text="🎲 Random tất cả",
            variable=self.var_random_server,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_random_server_toggled
        )
        self.chk_random_server.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_legacy_pool = tk.Button(
            self.frame_legacy_server,
            text=f"🎛️ Nhóm ({pool_cnt}/10)",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=4,
            pady=1,
            cursor="hand2",
            command=self.open_server_pool_dialog
        )
        self.btn_legacy_pool.pack(side=tk.LEFT, padx=(0, 4))

        opts = self.get_current_legacy_server_options()
        saved_srv = self.config.get("server", "m.facebook.com")
        if saved_rand_srv:
            init_srv_lbl = opts[0]
        elif saved_mode == "subset":
            init_srv_lbl = opts[1]
        else:
            init_srv_lbl = self.REVERSE_LEGACY_SERVER_MAP.get(saved_srv, opts[2])

        self.cb_legacy_server = ttk.Combobox(
            self.frame_legacy_server,
            values=opts,
            state="disabled" if saved_rand_srv else "readonly",
            font=AppTheme.FONT_SMALL,
            width=28
        )
        self.cb_legacy_server.set(init_srv_lbl)
        self.cb_legacy_server.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cb_legacy_server.bind("<<ComboboxSelected>>", self.on_legacy_server_changed)

        # 1. Khung Cài Đặt Khởi Tạo (Dành riêng cho Chế độ VR OTP & NVR)
        self.frame_reg_settings = tk.Frame(card_reg, bg=AppTheme.BG_CARD)

        self.var_use_bait = tk.BooleanVar(value=False)
        saved_bait_mode = self.config.get("bait_mode", "phone" if self.config.get("auto_gen_phone", True) else "none")
        self.var_auto_phone = tk.BooleanVar(value=(saved_bait_mode == "phone"))

        bait_box = tk.Frame(self.frame_reg_settings, bg=AppTheme.BG_CARD)
        bait_box.pack(fill=tk.X, pady=(2, 2))
        tk.Label(bait_box, text="Mồi tạo phiên:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_bait_mode = ttk.Combobox(
            bait_box,
            values=self.BAIT_MODE_OPTIONS,
            state="readonly",
        )
        self.set_selected_bait_mode(saved_bait_mode)
        self.cb_bait_mode.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)
        self.cb_bait_mode.bind("<<ComboboxSelected>>", self.on_bait_mode_changed)

        bait_retry_box = tk.Frame(self.frame_reg_settings, bg=AppTheme.BG_CARD)
        bait_retry_box.pack(fill=tk.X, pady=(2, 2))
        self.var_enable_bait_retry = tk.BooleanVar(value=bool(self.config.get("enable_bait_retry", True)))
        chk_enable_retry = tk.Checkbutton(
            bait_retry_box,
            text="Tự động mồi lại khi FB từ chối tạo phiên:",
            variable=self.var_enable_bait_retry,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD
        )
        chk_enable_retry.pack(side=tk.LEFT)
        saved_bait_retries = int(self.config.get("bait_retries", 3))
        self.var_bait_retries = tk.IntVar(value=saved_bait_retries)
        self.spn_bait_retries = tk.Spinbox(
            bait_retry_box,
            from_=1,
            to=10,
            textvariable=self.var_bait_retries,
            width=5,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            insertbackground=AppTheme.TEXT_MAIN,
            buttonbackground=AppTheme.BG_CARD,
        )
        self.spn_bait_retries.pack(side=tk.LEFT, padx=(6, 4))
        tk.Label(bait_retry_box, text="lần (Đổi thông tin mới)", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT)

        self.var_2fa = tk.BooleanVar(value=self.config.get("enable_2fa", True))
        chk_2fa = tk.Checkbutton(
            self.frame_reg_settings, text="Tự động bật bảo mật 2FA (TOTP)", variable=self.var_2fa,
            bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN, selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD
        )
        chk_2fa.pack(anchor="w", pady=2)

        self.var_anti_cp = tk.BooleanVar(value=self.config.get("anti_checkpoint_mode", True))
        chk_anti_cp = tk.Checkbutton(
            self.frame_reg_settings, text="🛡️ Chống khóa Checkpoint 282 (5 Trụ cột Bảo mật)",
            variable=self.var_anti_cp,
            bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT, selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD
        )
        chk_anti_cp.pack(anchor="w", pady=2)

        self.var_auto_ttc = tk.BooleanVar(value=bool(self.config.get("auto_ttc_pipeline", False)))
        def _on_toggle_auto_ttc():
            val = bool(self.var_auto_ttc.get())
            self.config["auto_ttc_pipeline"] = val
            try:
                with open(self.config_path, "w", encoding="utf-8") as f_cfg:
                    json.dump(self.config, f_cfg, indent=4, ensure_ascii=False)
            except Exception:
                pass
            if val:
                self.log("🚀 Đã BẬT: Tự chạy xu khi reg xong (TTC PRO)", "info")
            else:
                self.log("⏹ Đã TẮT: Tự chạy xu khi reg xong (TTC PRO)", "info")

        chk_auto_ttc = tk.Checkbutton(
            self.frame_reg_settings, text="🚀 Tự chạy xu khi reg xong (TTC PRO: Đổi Info ➔ Gán TTC ➔ Cày Xu)",
            variable=self.var_auto_ttc,
            command=_on_toggle_auto_ttc,
            bg=AppTheme.BG_CARD, fg="#10b981", selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD
        )
        chk_auto_ttc.pack(anchor="w", pady=2)

        pwd_frame = tk.Frame(self.frame_reg_settings, bg=AppTheme.BG_CARD)
        pwd_frame.pack(fill=tk.X, pady=(2, 2))
        tk.Label(pwd_frame, text="Mật khẩu FB:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.entry_fb_pwd = tk.Entry(pwd_frame, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid")
        saved_pwd = self.config.get("default_password", "")
        self.entry_fb_pwd.insert(0, saved_pwd)
        self.entry_fb_pwd.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        tk.Label(self.frame_reg_settings, text="💡 Để trống ô trên để hệ thống tự sinh mật khẩu ngẫu nhiên an toàn.", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w", pady=(0, 2))

        # Name Selection Section (Bộ Họ Tên Đa Quốc Gia & File Tùy Chỉnh)
        name_box = tk.Frame(self.frame_reg_settings, bg=AppTheme.BG_CARD)
        name_box.pack(fill=tk.X, pady=(4, 2))
        tk.Label(name_box, text="Bộ họ tên:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_name_type = ttk.Combobox(
            name_box,
            values=[
                "🎲 Lấy ngẫu nhiên Họ, Tên trong File (names.txt)",
                "🌐 Tên Toàn Cầu (Mix tất cả)",
                "🇻🇳 Tên Việt Nam (vi_VN)",
                "🇺🇸 Tên Tây / US-UK (en_US)",
                "🇮🇳 Tên Ấn Độ (hi_IN)",
                "🇹🇭 Tên Thái Lan (th_TH)",
                "🇨🇳 Tên Trung Quốc (zh_CN)",
                "🇰🇷 Tên Hàn Quốc (ko_KR)",
                "🇯🇵 Tên Nhật Bản (ja_JP)",
                "📁 Tên Tự Nhập theo dòng (Kho names.txt)",
                "🌍 Tự động theo Quốc gia Proxy (Khuyên dùng)",
                "🇮🇩 Tên Indonesia (id_ID)",
                "🇵🇭 Tên Philippines (fil_PH)",
                "🇧🇷 Tên Brazil / Latin (pt_BR)",
                "🇷🇺 Tên Nga / Đông Âu (ru_RU)",
                "🇸🇦 Tên Ả Rập / Trung Đông (ar_SA)",
            ],
            width=26,
            state="readonly"
        )
        saved_name_type = self.config.get("name_type", "vietnamese")
        self.set_selected_name_type(saved_name_type)
        self.cb_name_type.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)
        self.cb_name_type.bind("<<ComboboxSelected>>", self.on_name_type_changed)

        name_opt_box = tk.Frame(self.frame_reg_settings, bg=AppTheme.BG_CARD)
        name_opt_box.pack(fill=tk.X, pady=(2, 4))
        self.var_mix_names = tk.BooleanVar(value=self.config.get("mix_file_names", False))
        chk_mix = tk.Checkbutton(
            name_opt_box,
            text="Ghép ngẫu nhiên",
            variable=self.var_mix_names,
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
        )
        chk_mix.pack(side=tk.LEFT)

        btn_edit_names = tk.Button(
            name_opt_box,
            cursor="hand2",
            text="✍ Kho names.txt",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=5,
            pady=0,
            command=self.open_custom_names_dialog,
        )
        btn_edit_names.pack(side=tk.LEFT, padx=(5, 5))

        self.lbl_names_count = tk.Label(
            name_opt_box,
            text="Kho: ... tên",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
        )
        self.lbl_names_count.pack(side=tk.LEFT)
        self.refresh_names_count()

        # Device Profile Section (Hồ sơ thiết bị & User-Agent Engine Mr-SxR)
        device_box = tk.Frame(self.frame_reg_settings, bg=AppTheme.BG_CARD)
        device_box.pack(fill=tk.X, pady=(4, 2))
        tk.Label(device_box, text="Dòng thiết bị:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_device_type = ttk.Combobox(
            device_box,
            values=[
                "📱 Android (FB4A Katana App - Mr.SxR) (Khuyên dùng)",
                "🌐 Android Mobile (SupportsFresco Web)",
                "🍏 Apple iOS (iPhone Safari / App)",
                "📞 Feature Phone (KaiOS / Nokia)",
                "💻 Windows Desktop PC",
                "🎲 Ngẫu nhiên tất cả thiết bị",
            ],
            width=26,
            state="readonly",
        )
        saved_dev_type = self.config.get("device_type", "mr_sxr")
        self.set_selected_device_type(saved_dev_type)
        self.cb_device_type.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)
        self.cb_device_type.bind("<<ComboboxSelected>>", self.on_device_type_changed)

        dev_opt_box = tk.Frame(self.frame_reg_settings, bg=AppTheme.BG_CARD)
        dev_opt_box.pack(fill=tk.X, pady=(2, 4))
        btn_ua_tool = tk.Button(
            dev_opt_box,
            cursor="hand2",
            text="⚡ Tool Sinh User-Agent (Mr-SxR)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=6,
            pady=1,
            command=self.open_ua_generator_tool,
        )
        btn_ua_tool.pack(side=tk.LEFT)
        tk.Label(
            dev_opt_box,
            text="19 Hãng • 2,546 Dòng máy • 462 Bản Katana",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # 2. Khung Quản Lý Acc NVR Cần Xác Minh (Hiển thị khi chọn Chế độ Xác Minh Acc NVR)
        self.frame_nvr_management = tk.Frame(card_reg, bg=AppTheme.BG_CARD)

        lbl_nvr_head = tk.Label(
            self.frame_nvr_management,
            text="📋 QUẢN LÝ ACC NVR CẦN XÁC MINH",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        )
        lbl_nvr_head.pack(anchor="w", pady=(2, 4))

        btn_import_nvr = tk.Button(
            self.frame_nvr_management,
            text="📋 Nhập / Dán Acc NVR (Mọi định dạng)",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            bd=1,
            relief="solid",
            cursor="hand2",
            command=self.open_nvr_import_dialog
        )
        btn_import_nvr.pack(fill=tk.X, pady=(2, 4))

        btn_row_nvr = tk.Frame(self.frame_nvr_management, bg=AppTheme.BG_CARD)
        btn_row_nvr.pack(fill=tk.X, pady=(2, 4))

        btn_load_unver_btn = tk.Button(
            btn_row_nvr,
            cursor="hand2",
            text="📂 Nạp file unverified.txt",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            bd=1,
            relief="solid",
            command=lambda: self.populate_table_with_nvr_accounts()
        )
        btn_load_unver_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_reload_nvr_btn = tk.Button(
            btn_row_nvr,
            cursor="hand2",
            text="🔄 Tải Lại Vào Bảng",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            command=lambda: self.populate_table_with_nvr_accounts(getattr(self, "nvr_accounts_queue", None))
        )
        btn_reload_nvr_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_nvr_count = tk.Label(
            self.frame_nvr_management,
            text="Chưa có acc trên bảng. Bấm nút trên để dán hoặc nạp file.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        )
        self.lbl_nvr_count.pack(anchor="w", pady=(2, 2))

        lbl_nvr_hint = tk.Label(
            self.frame_nvr_management,
            text="💡 Nick hiển thị trực tiếp trên Bảng bên phải (gồm Cookie & Token).\nBấm '▶ BẮT ĐẦU XÁC MINH' để gắn Mail & nhận OTP thật!",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
            justify=tk.LEFT
        )
        lbl_nvr_hint.pack(anchor="w", pady=(0, 4))

        # Hiển thị khung tương ứng theo cấu hình hiện tại
        if self.config.get("reg_mode") == "verify_nvr":
            self.frame_nvr_management.pack(fill=tk.X, pady=(2, 4))
        else:
            self.frame_reg_settings.pack(fill=tk.X, pady=(2, 4))

        # Khung Số luồng & Số acc
        self.spn_frame = tk.Frame(card_reg, bg=AppTheme.BG_CARD)
        self.spn_frame.pack(fill=tk.X, pady=(4, 2))

        tk.Label(self.spn_frame, text="Số luồng:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).grid(row=0, column=0, sticky="w", pady=2)
        self.spn_threads = tk.Spinbox(self.spn_frame, from_=1, to=1000, width=5, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid")
        self.spn_threads.delete(0, tk.END)
        self.spn_threads.insert(0, str(self.config.get("threads", 4)))
        self.spn_threads.grid(row=0, column=1, sticky="w", padx=(5, 15), pady=2)

        target_lbl = "Số acc cần XM:" if self.config.get("reg_mode") == "verify_nvr" else "Số acc cần tạo:"
        self.lbl_accounts_target = tk.Label(self.spn_frame, text=target_lbl, font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN)
        self.lbl_accounts_target.grid(row=0, column=2, sticky="w", pady=2)
        self.spn_accounts = tk.Spinbox(self.spn_frame, from_=1, to=1000, width=6, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid")
        self.spn_accounts.delete(0, tk.END)
        self.spn_accounts.insert(0, str(self.config.get("max_accounts", 10)))
        self.spn_accounts.grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # Card 2: Cấu hình Proxy
        card_proxy = tk.LabelFrame(
            parent,
            text=" 🌐 2. Cấu hình Proxy ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        card_proxy.pack(fill=tk.X, pady=(0, 8))
        self.card_proxy = card_proxy

        prov_box = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        prov_box.pack(fill=tk.X, pady=2)
        tk.Label(prov_box, text="Loại Proxy:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_proxy_provider = ttk.Combobox(
            prov_box,
            values=self.PROXY_PROVIDERS_DISPLAY,
            width=28,
            state="readonly"
        )
        saved_prov = self.config.get("proxy_provider", "kiotproxy")
        self.cb_proxy_provider.set(self.PROXY_PROVIDER_REVERSE.get(saved_prov, self.PROXY_PROVIDERS_DISPLAY[0]))
        self.cb_proxy_provider.bind("<<ComboboxSelected>>", self.on_proxy_provider_changed)
        self.cb_proxy_provider.pack(side=tk.LEFT, padx=8)

        lbl_keys_row = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        lbl_keys_row.pack(fill=tk.X, pady=(4, 2))
        self.lbl_keys_row = lbl_keys_row

        if saved_prov == "proxysocks5":
            initial_title = "Danh sách ProxySocks5 tokenProxy Key (mỗi dòng 1 key):"
        elif saved_prov in ("kiotproxy", "kiotproxy_current"):
            initial_title = "Danh sách KiotProxy Key (mỗi dòng 1 key):"
        elif saved_prov == "proxy_list":
            initial_title = "Danh sách Proxy (host:port hoặc user:pass@host:port):"
        else:
            initial_title = "Danh sách Key / Proxy (Không yêu cầu cho Free/Direct):"

        lbl_keys_title = tk.Label(
            lbl_keys_row,
            text=initial_title,
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        )
        lbl_keys_title.pack(side=tk.LEFT)
        self.lbl_keys_title = lbl_keys_title

        self.btn_toggle_mask = tk.Button(
            lbl_keys_row,
            cursor="hand2",
            text="🔒 Ẩn Key" if not getattr(self, "keys_masked", False) else "👁 Hiện Key",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING if not getattr(self, "keys_masked", False) else AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=6,
            pady=0,
            command=self.toggle_mask_proxy_keys
        )
        self.btn_toggle_mask.pack(side=tk.RIGHT)

        self.txt_proxy_keys = scrolledtext.ScrolledText(
            card_proxy,
            height=4,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            bd=1,
            relief="solid"
        )
        self.txt_proxy_keys.pack(fill=tk.X, pady=2)

        # Dedicated Panel cho File Proxy (thay thế areabox theo yêu cầu người dùng)
        self.panel_proxy_file = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)

        p_row1 = tk.Frame(self.panel_proxy_file, bg=AppTheme.BG_CARD)
        p_row1.pack(fill=tk.X, pady=(2, 4))
        self.lbl_proxy_filepath_title = tk.Label(p_row1, text="📁 File Proxy:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN)
        self.lbl_proxy_filepath_title.pack(side=tk.LEFT)
        self.entry_proxy_filepath = tk.Entry(p_row1, bg=AppTheme.BG_INPUT, fg=AppTheme.ACCENT, font=AppTheme.FONT_CODE, bd=1, relief="solid")
        self.entry_proxy_filepath.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        initial_p_file = self.config.get("proxy_file_path", "proxy.txt") or "proxy.txt"
        self.entry_proxy_filepath.delete(0, tk.END)
        self.entry_proxy_filepath.insert(0, initial_p_file)
        self.entry_proxy_filepath.bind("<FocusOut>", lambda e: self.on_proxy_filepath_entry_changed())
        self.entry_proxy_filepath.bind("<Return>", lambda e: self.on_proxy_filepath_entry_changed())
        btn_browse_p = tk.Button(
            p_row1, cursor="hand2", text="📂 Chọn File .txt", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.ACCENT, fg="#000000", activebackground=AppTheme.ACCENT_HOVER,
            bd=0, padx=10, pady=2, command=self.import_proxy_file
        )
        btn_browse_p.pack(side=tk.RIGHT)

        p_row2 = tk.Frame(self.panel_proxy_file, bg=AppTheme.BG_INPUT, bd=1, relief="solid", padx=8, pady=6)
        p_row2.pack(fill=tk.X, pady=(0, 4))
        self.lbl_file_proxy_summary = tk.Label(
            p_row2, text="📊 Đang kiểm tra file proxy...",
            font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_INPUT, fg=AppTheme.SUCCESS
        )
        self.lbl_file_proxy_summary.pack(anchor="w")

        p_desc = "🎲 Cơ chế: Mỗi luồng tự động bốc NGẪU NHIÊN 1 proxy trong file này để reg (Collision-Free)\n" \
                 "📝 Định dạng hỗ trợ: ip:port hoặc ip:port:user:pass (mỗi dòng 1 proxy, tự lọc tag)"
        self.lbl_file_proxy_desc = tk.Label(
            p_row2, text=p_desc, justify=tk.LEFT,
            font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MUTED
        )
        self.lbl_file_proxy_desc.pack(anchor="w", pady=(2, 0))

        p_row3 = tk.Frame(self.panel_proxy_file, bg=AppTheme.BG_CARD)
        p_row3.pack(fill=tk.X, pady=(2, 2))

        tk.Button(
            p_row3, cursor="hand2", text="📝 Mở File (.txt)", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.INFO, activebackground=AppTheme.BORDER,
            bd=1, relief="solid", command=self.open_proxy_file
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tk.Button(
            p_row3, cursor="hand2", text="🔄 Tải Lại File", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, activebackground=AppTheme.BORDER,
            bd=1, relief="solid", command=self.reload_proxy_file
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tk.Button(
            p_row3, cursor="hand2", text="🎲 Bốc Thử 1 Proxy Ngẫu Nhiên", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT, fg=AppTheme.ACCENT, activebackground=AppTheme.BORDER,
            bd=1, relief="solid", command=self.pick_random_proxy_preview
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tk.Button(
            p_row3, cursor="hand2", text="⚡ Test Live Facebook", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.WARNING, activebackground=AppTheme.BORDER,
            bd=1, relief="solid", command=self.test_proxy_list_facebook_connection
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tk.Button(
            p_row3, cursor="hand2", text="📕 File Proxy Lỗi", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER, activebackground=AppTheme.BORDER,
            bd=1, relief="solid", command=self.open_bad_proxy_file
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        p_row4 = tk.Frame(self.panel_proxy_file, bg=AppTheme.BG_CARD)
        p_row4.pack(fill=tk.X, pady=(4, 2))

        self.var_filter_bad_proxy_from_file = tk.BooleanVar(value=self.config.get("filter_bad_proxy_from_file", True))
        self.chk_filter_bad_proxy = tk.Checkbutton(
            p_row4,
            text="🗑️ Tự động lọc & xóa Proxy Lỗi khỏi file khi chạy, chuyển vào 'proxy_loi.txt'",
            variable=self.var_filter_bad_proxy_from_file,
            bg=AppTheme.BG_CARD, fg=AppTheme.DANGER, selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD, font=AppTheme.FONT_BODY_BOLD,
            command=self._on_toggle_filter_bad_proxy
        )
        self.chk_filter_bad_proxy.pack(side=tk.LEFT)

        self._render_proxy_keys_display()

        self.btn_proxy_row1 = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        btn_chk_all = tk.Button(
            self.btn_proxy_row1,
            cursor="hand2",
            text="🔍 Kiểm tra TẤT CẢ",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.check_all_kiotproxy_keys
        )
        btn_chk_all.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_chk_one = tk.Button(
            self.btn_proxy_row1,
            cursor="hand2",
            text="🔍 Kiểm tra Key 1",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.check_single_kiotproxy_key
        )
        btn_chk_one.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_proxy_row2 = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        btn_rot_all = tk.Button(
            self.btn_proxy_row2,
            cursor="hand2",
            text="🔄 Xoay IP TẤT CẢ",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.rotate_all_kiotproxy_keys
        )
        btn_rot_all.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_rot_one = tk.Button(
            self.btn_proxy_row2,
            cursor="hand2",
            text="🔄 Xoay IP Key 1",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.rotate_single_kiotproxy_key
        )
        btn_rot_one.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_proxy_row3 = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        total_free_srcs = FreeProxyManager.get_total_sources_count()
        btn_view_free_sources = tk.Button(
            self.btn_proxy_row3,
            cursor="hand2",
            text=f"📋 Xem Nguồn ({total_free_srcs})",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.open_free_proxy_sources_dialog
        )
        btn_view_free_sources.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_open_sources_file = tk.Button(
            self.btn_proxy_row3,
            cursor="hand2",
            text="📂 File Nguồn",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.open_proxy_sources_file
        )
        btn_open_sources_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_fetch_free = tk.Button(
            self.btn_proxy_row3,
            cursor="hand2",
            text="🌐 Cào Proxy Free",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.fetch_fresh_free_proxies
        )
        btn_fetch_free.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_test_fb = tk.Button(
            self.btn_proxy_row3,
            cursor="hand2",
            text="⚡ Test Kết Nối FB",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.test_free_proxies_facebook_connection
        )
        btn_test_fb.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_proxy_row4 = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        btn_psocks5_mgr = tk.Button(
            self.btn_proxy_row4,
            cursor="hand2",
            text="📦 Quản lý ProxySocks5.vn (Nạp Order ID / Mua / Gia Hạn)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.open_proxysocks5_manager_dialog
        )
        btn_psocks5_mgr.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 5: Dành riêng cho Danh sách Proxy từ File cấu hình (proxy.txt)
        self.btn_proxy_row5 = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        btn_open_p_file = tk.Button(
            self.btn_proxy_row5,
            cursor="hand2",
            text="📂 Mở File",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.open_proxy_file
        )
        btn_open_p_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_import_p_file = tk.Button(
            self.btn_proxy_row5,
            cursor="hand2",
            text="📥 Chọn File .txt",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.import_proxy_file
        )
        btn_import_p_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_reload_p_file = tk.Button(
            self.btn_proxy_row5,
            cursor="hand2",
            text="🔄 Tải lại file",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.reload_proxy_file
        )
        btn_reload_p_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_save_p_file = tk.Button(
            self.btn_proxy_row5,
            cursor="hand2",
            text="💾 Lưu vào file",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.save_proxies_to_file
        )
        btn_save_p_file.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_test_p_list = tk.Button(
            self.btn_proxy_row5,
            cursor="hand2",
            text="⚡ Test Live FB",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.test_proxy_list_facebook_connection
        )
        btn_test_p_list.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 6: Dành riêng cho mProxy.vn (Proxy 4G/5G xoay IP)
        self.btn_proxy_row6 = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        btn_chk_mproxy = tk.Button(
            self.btn_proxy_row6,
            cursor="hand2",
            text="🔍 Kiểm Tra mProxy (Số Dư & Keys 4G)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.check_all_mproxy_keys
        )
        btn_chk_mproxy.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_rot_mproxy = tk.Button(
            self.btn_proxy_row6,
            cursor="hand2",
            text="🔄 Xoay IP mProxy (Reset IP 4G)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.rotate_all_mproxy_keys
        )
        btn_rot_mproxy.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_mgr_mproxy = tk.Button(
            self.btn_proxy_row6,
            cursor="hand2",
            text="📦 Quản Lý mProxy (Token / Mua Gói)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.open_mproxy_manager_dialog
        )
        btn_mgr_mproxy.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_web_mproxy = tk.Button(
            self.btn_proxy_row6,
            cursor="hand2",
            text="🌐 Trang mProxy.vn",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=lambda: webbrowser.open("https://mproxy.vn")
        )
        btn_web_mproxy.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 7: Dành riêng cho Proxy.vn (proxyxoay.shop)
        self.btn_proxy_row7 = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        btn_chk_pvn = tk.Button(
            self.btn_proxy_row7,
            cursor="hand2",
            text="🔍 Kiểm Tra Proxy.vn",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.check_all_proxyvn_keys
        )
        btn_chk_pvn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_rot_pvn = tk.Button(
            self.btn_proxy_row7,
            cursor="hand2",
            text="🔄 Xoay IP Proxy.vn",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.rotate_all_proxyvn_keys
        )
        btn_rot_pvn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_chk1_pvn = tk.Button(
            self.btn_proxy_row7,
            cursor="hand2",
            text="🔍 Kiểm Tra Key 1",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.check_single_proxyvn_key
        )
        btn_chk1_pvn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_rot1_pvn = tk.Button(
            self.btn_proxy_row7,
            cursor="hand2",
            text="🔄 Xoay IP Key 1",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=self.rotate_single_proxyvn_key
        )
        btn_rot1_pvn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_web_pvn = tk.Button(
            self.btn_proxy_row7,
            cursor="hand2",
            text="🌐 Trang Proxy.vn",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            command=lambda: webbrowser.open("https://proxy.vn")
        )
        btn_web_pvn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_kiot_status = tk.Label(
            card_proxy,
            text="Trạng thái Proxy: Chưa kiểm tra",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        )
        self.lbl_kiot_status.pack(anchor="w", pady=(2, 0))

        # Row 7: Chế độ phân bổ IP cho Luồng (2 chế độ bật/tắt bằng checkbox)
        row_alloc_mode = tk.LabelFrame(
            card_proxy,
            text=" ⚙️ Chế độ phân bổ IP cho Luồng ",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=8,
            pady=4
        )
        row_alloc_mode.pack(fill=tk.X, pady=(4, 3))
        self.row_alloc_mode = row_alloc_mode

        saved_alloc = self.config.get("proxy_alloc_mode", "dedicated")
        is_dedicated = (saved_alloc != "shared")

        self.var_proxy_mode_dedicated = tk.BooleanVar(value=is_dedicated)
        self.var_proxy_mode_shared = tk.BooleanVar(value=not is_dedicated)

        self.chk_proxy_mode_dedicated = tk.Checkbutton(
            row_alloc_mode,
            text="🛡️ Mặc định: Mỗi 1 luồng chỉ 1 IP riêng biệt (Đảm bảo an toàn, chống Checkpoint)",
            variable=self.var_proxy_mode_dedicated,
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS if is_dedicated else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.SUCCESS,
            command=self._on_proxy_mode_dedicated_toggled
        )
        self.chk_proxy_mode_dedicated.pack(anchor="w", pady=(1, 2))

        self.chk_proxy_mode_shared = tk.Checkbutton(
            row_alloc_mode,
            text="⚡ Theo số luồng: Chia đều IP theo số luồng (VD: 30 luồng chia đều cho 6 IP / Key)",
            variable=self.var_proxy_mode_shared,
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT if not is_dedicated else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.ACCENT,
            command=self._on_proxy_mode_shared_toggled
        )
        self.chk_proxy_mode_shared.pack(anchor="w", pady=(0, 2))

        # Row 7: Tự động xoay IP định kỳ mỗi phút / X phút
        row_auto_rot = tk.Frame(card_proxy, bg=AppTheme.BG_CARD)
        row_auto_rot.pack(fill=tk.X, pady=(4, 2))
        self.row_auto_rot = row_auto_rot

        self.var_auto_rotate = tk.BooleanVar(value=bool(self.config.get("auto_rotate_proxy", False)))
        self.chk_auto_rotate = tk.Checkbutton(
            row_auto_rot,
            text="⏱️ Tự động xoay IP định kỳ mỗi:",
            variable=self.var_auto_rotate,
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.ACCENT,
            command=self.on_auto_rotate_toggled
        )
        self.chk_auto_rotate.pack(side=tk.LEFT)

        self.cb_auto_rotate_interval = ttk.Combobox(
            row_auto_rot,
            values=[
                "60s (1 phút)",
                "30s",
                "45s",
                "90s (1.5 phút)",
                "120s (2 phút)",
                "180s (3 phút)",
                "300s (5 phút)"
            ],
            width=14,
            state="readonly",
            font=AppTheme.FONT_SMALL
        )
        saved_inter = self.config.get("auto_rotate_interval", "60s (1 phút)")
        if saved_inter in self.cb_auto_rotate_interval["values"]:
            self.cb_auto_rotate_interval.set(saved_inter)
        else:
            self.cb_auto_rotate_interval.set("60s (1 phút)")
        self.cb_auto_rotate_interval.pack(side=tk.LEFT, padx=(4, 6))
        self.cb_auto_rotate_interval.bind("<<ComboboxSelected>>", lambda e: self.on_auto_rotate_interval_changed())

        self.lbl_auto_rot_hint = tk.Label(
            row_auto_rot,
            text="(mProxy 4G / Kiot / PSocks5)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        )
        self.lbl_auto_rot_hint.pack(side=tk.LEFT)
        try:
            self.on_proxy_provider_changed()
        except Exception:
            pass

        # Card 3: Email Service & Hotmail Tự Nhập
        card_email = tk.LabelFrame(
            parent,
            text=" ✉ 3. Hòm thư & Danh sách Hotmail ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        card_email.pack(fill=tk.X, pady=(0, 8))

        em_box = tk.Frame(card_email, bg=AppTheme.BG_CARD)
        em_box.pack(fill=tk.X, pady=2)
        tk.Label(em_box, text="Dịch vụ Mail:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_email_provider = ttk.Combobox(
            em_box,
            values=self.EMAIL_PROVIDERS_DISPLAY,
            width=28,
            state="readonly"
        )
        saved_srv = self.config.get("email_service", "custom_hotmail")
        default_display = self.EMAIL_PROVIDER_REVERSE.get(saved_srv, self.EMAIL_PROVIDERS_DISPLAY[0])
        self.cb_email_provider.set(default_display)
        self.cb_email_provider.bind("<<ComboboxSelected>>", self.on_email_service_changed)
        self.cb_email_provider.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)

        # Cụm Checkbox tùy chọn các đuôi mail sạch đa nguồn
        saved_custom_domains = self.config.get("selected_custom_domains", [
            "smail1s.com", "laoia.com", "smailwork.com", "hotmailtrusted.com",
            "mailto.plus", "fexpost.com", "mailbox.in.ua", "rover.info", "tanpony.com"
        ])
        if not isinstance(saved_custom_domains, list):
            saved_custom_domains = [
                "smail1s.com", "laoia.com", "smailwork.com", "hotmailtrusted.com",
                "mailto.plus", "fexpost.com", "mailbox.in.ua", "rover.info", "tanpony.com"
            ]

        self.frame_custom_domains = tk.LabelFrame(
            card_email,
            text=" 🎯 Bộ Mail Sạch (Đã thêm @mailto.plus - Chọn tùy ý các đuôi): ",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="groove",
            padx=6,
            pady=4,
        )
        self.frame_custom_domains.pack(fill=tk.X, pady=(4, 6))

        # Hàng 1: Bộ 4 Đuôi Mail Sạch Trọng Tâm (smail1s, laoia, smailwork, mailto.plus)
        row_dom_1 = tk.Frame(self.frame_custom_domains, bg=AppTheme.BG_CARD)
        row_dom_1.pack(fill=tk.X, pady=(1, 2))

        self.var_domain_smail1s = tk.BooleanVar(value=("smail1s.com" in saved_custom_domains))
        chk_dom_smail1s = tk.Checkbutton(
            row_dom_1,
            text="@smail1s.com",
            variable=self.var_domain_smail1s,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_smail1s.pack(side=tk.LEFT, padx=(0, 6))

        self.var_domain_laoia = tk.BooleanVar(value=("laoia.com" in saved_custom_domains))
        chk_dom_laoia = tk.Checkbutton(
            row_dom_1,
            text="@laoia.com",
            variable=self.var_domain_laoia,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_laoia.pack(side=tk.LEFT, padx=(0, 6))

        self.var_domain_smailwork = tk.BooleanVar(value=("smailwork.com" in saved_custom_domains))
        chk_dom_smailwork = tk.Checkbutton(
            row_dom_1,
            text="@smailwork.com",
            variable=self.var_domain_smailwork,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_smailwork.pack(side=tk.LEFT, padx=(0, 6))

        self.var_domain_mailtoplus = tk.BooleanVar(value=("mailto.plus" in saved_custom_domains))
        chk_dom_mailtoplus = tk.Checkbutton(
            row_dom_1,
            text="⭐ @mailto.plus",
            variable=self.var_domain_mailtoplus,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_mailtoplus.pack(side=tk.LEFT)

        # Hàng 2: Các đuôi sạch mở rộng bổ sung
        row_dom_2 = tk.Frame(self.frame_custom_domains, bg=AppTheme.BG_CARD)
        row_dom_2.pack(fill=tk.X, pady=(2, 2))

        self.var_domain_hotmailtrusted = tk.BooleanVar(value=("hotmailtrusted.com" in saved_custom_domains))
        chk_dom_hotmailtrusted = tk.Checkbutton(
            row_dom_2,
            text="@hotmailtrusted.com",
            variable=self.var_domain_hotmailtrusted,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_hotmailtrusted.pack(side=tk.LEFT, padx=(0, 6))

        self.var_domain_fexpost = tk.BooleanVar(value=("fexpost.com" in saved_custom_domains))
        chk_dom_fexpost = tk.Checkbutton(
            row_dom_2,
            text="@fexpost.com",
            variable=self.var_domain_fexpost,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_fexpost.pack(side=tk.LEFT, padx=(0, 6))

        self.var_domain_mailboxinua = tk.BooleanVar(value=("mailbox.in.ua" in saved_custom_domains))
        chk_dom_mailboxinua = tk.Checkbutton(
            row_dom_2,
            text="@mailbox.in.ua",
            variable=self.var_domain_mailboxinua,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_mailboxinua.pack(side=tk.LEFT, padx=(0, 6))

        self.var_domain_roverinfo = tk.BooleanVar(value=("rover.info" in saved_custom_domains))
        chk_dom_roverinfo = tk.Checkbutton(
            row_dom_2,
            text="@rover.info",
            variable=self.var_domain_roverinfo,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_roverinfo.pack(side=tk.LEFT, padx=(0, 6))

        self.var_domain_tanpony = tk.BooleanVar(value=("tanpony.com" in saved_custom_domains))
        chk_dom_tanpony = tk.Checkbutton(
            row_dom_2,
            text="@tanpony.com",
            variable=self.var_domain_tanpony,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL_BOLD,
            command=self.on_custom_domains_changed,
        )
        chk_dom_tanpony.pack(side=tk.LEFT)

        # Hàng 3: Các nút tiện ích chọn nhanh
        row_dom_3 = tk.Frame(self.frame_custom_domains, bg=AppTheme.BG_CARD)
        row_dom_3.pack(fill=tk.X, pady=(3, 1))

        btn_sel_quartet = tk.Button(
            row_dom_3,
            text="⭐ Chọn Bộ 4 Mail Sạch (@mailto.plus + 3 mail gốc)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="groove",
            cursor="hand2",
            padx=6,
            pady=1,
            command=self.select_quartet_custom_domains,
        )
        btn_sel_quartet.pack(side=tk.LEFT, padx=(0, 6))

        btn_sel_all = tk.Button(
            row_dom_3,
            text="✓ Chọn Tất Cả (9 Đuôi)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="groove",
            cursor="hand2",
            padx=6,
            pady=1,
            command=self.select_all_custom_domains,
        )
        btn_sel_all.pack(side=tk.LEFT, padx=(0, 6))

        btn_top_two = tk.Button(
            row_dom_3,
            text="🏆 Live Cao (@mailto.plus + @laoia)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            bd=1,
            relief="groove",
            cursor="hand2",
            padx=6,
            pady=1,
            command=self.select_top_clean_domains,
        )
        btn_top_two.pack(side=tk.LEFT)

        hot_stat_row = tk.Frame(card_email, bg=AppTheme.BG_CARD)
        hot_stat_row.pack(fill=tk.X, pady=(6, 4))
        tk.Label(
            hot_stat_row,
            text="Kho Hotmail (hotmails.txt):",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        self.lbl_hotmail_count = tk.Label(
            hot_stat_row,
            text="Kho: 0 mail",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS
        )
        self.lbl_hotmail_count.pack(side=tk.LEFT, padx=(6, 8))

        btn_refresh_hot = tk.Button(
            hot_stat_row,
            cursor="hand2",
            text="🔄 Làm mới",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=8,
            pady=2,
            command=self.on_click_refresh_hotmail
        )
        btn_refresh_hot.pack(side=tk.RIGHT)

        hot_act_row = tk.Frame(card_email, bg=AppTheme.BG_CARD)
        hot_act_row.pack(fill=tk.X, pady=(2, 4))

        btn_open_hot = tk.Button(
            hot_act_row,
            cursor="hand2",
            text="📂 Mở DS Hotmail",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=4,
            pady=3,
            command=self.open_hotmail_file
        )
        btn_open_hot.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_import_hot = tk.Button(
            hot_act_row,
            cursor="hand2",
            text="📥 Nạp File .txt",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=4,
            pady=3,
            command=self.import_hotmail_file
        )
        btn_import_hot.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_custom_hot = tk.Button(
            hot_act_row,
            cursor="hand2",
            text="✍ Sửa / Xem DS",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=4,
            pady=3,
            command=self.open_custom_hotmail_dialog
        )
        btn_custom_hot.pack(side=tk.LEFT, fill=tk.X, expand=True)

        bench_row = tk.Frame(card_email, bg=AppTheme.BG_CARD)
        bench_row.pack(fill=tk.X, pady=(4, 0))
        btn_bench = tk.Button(
            bench_row,
            cursor="hand2",
            text="📊 Thống Kê & Test Hiệu Quả Đuôi Mail FB",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=4,
            pady=4,
            command=self.open_domain_benchmark_dialog
        )
        btn_bench.pack(fill=tk.X)

        # Tùy chọn Tự động đổi mail khi kẹt xác minh form / NVR
        retry_frame = tk.LabelFrame(
            card_email,
            text=" 🔄 Tự Động Đổi Mail Khi Kẹt Xác Minh (NVR) ",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="groove",
            padx=6,
            pady=4,
        )
        retry_frame.pack(fill=tk.X, pady=(6, 2))

        self.var_retry_on_nvr = tk.BooleanVar(value=self.config.get("retry_on_nvr_with_new_mail", True))
        chk_retry_nvr = tk.Checkbutton(
            retry_frame,
            text="Kẹt form XM: Tự động đổi mail khác xác minh lại",
            variable=self.var_retry_on_nvr,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD,
        )
        chk_retry_nvr.pack(anchor=tk.W)

        opt_retry_row = tk.Frame(retry_frame, bg=AppTheme.BG_CARD)
        opt_retry_row.pack(fill=tk.X, pady=(2, 2))

        tk.Label(
            opt_retry_row,
            text="Loại mail xác minh lại:",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        saved_retry_srv = self.config.get("retry_email_service", "")
        if not saved_retry_srv and self.config.get("retry_use_free_mail", False):
            saved_retry_srv = "auto_rotator"
        if not saved_retry_srv:
            saved_retry_srv = "as_setting"

        self.cb_retry_email_service = ttk.Combobox(
            opt_retry_row,
            values=self.RETRY_EMAIL_SERVICES_DISPLAY,
            width=36,
            state="readonly"
        )
        default_retry_display = self.RETRY_EMAIL_SERVICE_REVERSE.get(saved_retry_srv, self.RETRY_EMAIL_SERVICES_DISPLAY[0])
        self.cb_retry_email_service.set(default_retry_display)
        self.cb_retry_email_service.pack(side=tk.LEFT, padx=(6, 12))

        tk.Label(opt_retry_row, text="Số lần thử:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(4, 4))
        self.spn_max_email_retries = tk.Spinbox(
            opt_retry_row,
            from_=1,
            to=100,
            width=4,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_BODY,
            justify=tk.CENTER,
        )
        self.spn_max_email_retries.delete(0, tk.END)
        self.spn_max_email_retries.insert(0, str(self.config.get("max_otp_email_retries", 15)))
        self.spn_max_email_retries.pack(side=tk.LEFT)

        tk.Label(opt_retry_row, text="Chờ OTP (giây):", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(12, 4))
        self.spn_otp_timeout = tk.Spinbox(
            opt_retry_row,
            from_=5,
            to=180,
            width=4,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_BODY,
            justify=tk.CENTER,
        )
        self.spn_otp_timeout.delete(0, tk.END)
        self.spn_otp_timeout.insert(0, str(self.config.get("otp_timeout", 20)))
        self.spn_otp_timeout.pack(side=tk.LEFT)

        # Card 5: Tự Động Up Kho Hàng Bot Telegram / Web Shop (Media ID)
        card_bot = tk.LabelFrame(
            parent,
            text=" 🤖 5. Tự Động Up Kho Hàng Bot Telegram / Web Shop (Media ID) ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        card_bot.pack(fill=tk.X, pady=(0, 8))

        # 1. Hàng Bật / Tắt chức năng
        row_bot_toggle = tk.Frame(card_bot, bg=AppTheme.BG_CARD)
        row_bot_toggle.pack(fill=tk.X, pady=(2, 6))

        is_bot_on = bool(self.config.get("bot_auto_upload", False))
        self.chk_bot_auto_upload = tk.Checkbutton(
            row_bot_toggle,
            text="⚡ BẬT TỰ ĐỘNG UP NICK LÊN BOT SAU KHI REG (LIVE / NVR)",
            variable=self.var_bot_auto_upload,
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS if is_bot_on else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.SUCCESS,
            command=self._on_bot_auto_upload_toggled
        )
        self.chk_bot_auto_upload.pack(side=tk.LEFT)

        # 2. Hàng Media ID (Quan trọng nhất)
        row_media_id = tk.Frame(card_bot, bg=AppTheme.BG_CARD)
        row_media_id.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            row_media_id,
            text="Media ID Thư Mục Con:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING
        ).pack(side=tk.LEFT)

        self.entry_bot_media_id = tk.Entry(
            row_media_id,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            font=AppTheme.FONT_CODE
        )
        saved_mid = self.config.get("bot_media_id", "0AgACAgUAAxUAAWrdTEFel8nwqyfqdm-JW5tDEZQ-AAJmE2sbA8fhVvptkVWyk7XSAQADAgADYwADPQQ")
        self.entry_bot_media_id.insert(0, saved_mid)
        self.entry_bot_media_id.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 4))

        btn_paste_mid = tk.Button(
            row_media_id,
            cursor="hand2",
            text="📋 Dán",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=6,
            pady=1,
            command=self._paste_bot_media_id
        )
        btn_paste_mid.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_test_bot_media_id = tk.Button(
            row_media_id,
            cursor="hand2",
            text="🔍 Kiểm Tra Media ID",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=8,
            pady=1,
            command=self.test_bot_media_id_connection
        )
        self.btn_test_bot_media_id.pack(side=tk.LEFT)

        # Trạng thái kết nối / tên danh mục con tìm thấy
        self.lbl_bot_media_id_status = tk.Label(
            card_bot,
            text="● Trạng thái: Bấm 'Kiểm Tra Media ID' để tải thông tin thư mục và kiểm tra kết nối bot",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
            anchor="w"
        )
        self.lbl_bot_media_id_status.pack(fill=tk.X, pady=(2, 6))

        # 3. Hàng Cấu hình Bot Server URL & API Key
        row_server_cfg = tk.Frame(card_bot, bg=AppTheme.BG_CARD)
        row_server_cfg.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            row_server_cfg,
            text="Bot / Web URL:",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT)

        self.entry_bot_api_url = tk.Entry(
            row_server_cfg,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            font=AppTheme.FONT_CODE,
            width=28
        )
        self.entry_bot_api_url.insert(0, self.config.get("bot_api_url", "https://shopcl.onrender.com"))
        self.entry_bot_api_url.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(
            row_server_cfg,
            text="Admin API Key:",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT)

        self.entry_bot_api_key = tk.Entry(
            row_server_cfg,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            font=AppTheme.FONT_CODE,
            show="*"
        )
        self.entry_bot_api_key.insert(0, self.config.get("bot_api_key", "MatKhauAdminCuaBan123"))
        self.entry_bot_api_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))

        self.btn_toggle_bot_api_key = tk.Button(
            row_server_cfg,
            cursor="hand2",
            text="👁 Hiện Key",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MUTED,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=4,
            pady=1,
            command=self._toggle_mask_bot_api_key
        )
        self.btn_toggle_bot_api_key.pack(side=tk.LEFT)

        # 4. Hàng định dạng & Nút Up hàng loạt
        row_bot_fmt = tk.Frame(card_bot, bg=AppTheme.BG_CARD)
        row_bot_fmt.pack(fill=tk.X, pady=(4, 4))

        tk.Label(
            row_bot_fmt,
            text="Định dạng up:",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT)

        tk.Label(
            row_bot_fmt,
            text="UID|PASS|COOKIE",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            padx=6,
            pady=2,
            bd=1,
            relief="solid"
        ).pack(side=tk.LEFT, padx=(4, 12))

        self.lbl_bot_upload_stat = tk.Label(
            row_bot_fmt,
            text="Đã up trong phiên: 0 acc",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO
        )
        self.lbl_bot_upload_stat.pack(side=tk.LEFT, padx=(0, 10))

        btn_manual_up_unver = tk.Button(
            row_bot_fmt,
            cursor="hand2",
            text="🚀 Up File accounts_unverified.txt Lên Bot",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=6,
            pady=2,
            command=self.upload_all_unverified_to_bot
        )
        btn_manual_up_unver.pack(side=tk.RIGHT, padx=(4, 0))

        btn_manual_up_all = tk.Button(
            row_bot_fmt,
            cursor="hand2",
            text="🚀 Up File accounts_live.txt Lên Bot",
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=6,
            pady=2,
            command=self.upload_all_live_to_bot
        )
        btn_manual_up_all.pack(side=tk.RIGHT)

        # Card 5.2: Tự Động Kết Hợp Với Tool Verry
        card_verry = tk.LabelFrame(
            parent,
            text=" 🔗 5.2. Kết Hợp Tự Động Với Tool Verry [NVR -> Chờ Ngấu -> Xác Minh] ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        card_verry.pack(fill=tk.X, pady=(0, 8))

        # 1. Hàng Bật / Tắt chức năng
        row_verry_toggle = tk.Frame(card_verry, bg=AppTheme.BG_CARD)
        row_verry_toggle.pack(fill=tk.X, pady=(2, 6))

        is_verry_pipe_on = bool(self.config.get("enable_verry_pipeline", True))
        self.chk_verry_pipeline = tk.Checkbutton(
            row_verry_toggle,
            text="⚡ BẬT TỰ ĐỘNG CHUYỂN ACC NVR SANG TOOL VERRY [Sau thời gian ngấu]",
            variable=self.var_enable_verry_pipeline,
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS if is_verry_pipe_on else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.SUCCESS,
            command=self._on_verry_pipeline_toggled
        )
        self.chk_verry_pipeline.pack(side=tk.LEFT)

        # 2. Hàng Thời gian chờ & Số luồng Verry
        row_verry_opts = tk.Frame(card_verry, bg=AppTheme.BG_CARD)
        row_verry_opts.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            row_verry_opts,
            text="Thời gian chờ ngấu nick:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        self.cb_verry_delay = ttk.Combobox(
            row_verry_opts,
            textvariable=self.var_verry_pipeline_delay,
            values=[
                "1 phút",
                "2 phút (Khuyến nghị)",
                "5 phút",
                "10 phút",
                "15 phút",
                "30 phút"
            ],
            state="readonly",
            width=22,
            font=AppTheme.FONT_BODY
        )
        self.cb_verry_delay.pack(side=tk.LEFT, padx=(6, 16))

        tk.Label(
            row_verry_opts,
            text="Số luồng Verry:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        self.spn_verry_threads = tk.Spinbox(
            row_verry_opts,
            from_=1,
            to=500,
            textvariable=self.var_verry_pipeline_threads,
            width=6,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_BODY,
            justify=tk.CENTER
        )
        self.spn_verry_threads.pack(side=tk.LEFT, padx=(6, 8))

        tk.Label(
            row_verry_opts,
            text="(Chạy nền độc lập khi Tool Verry chưa mở giao diện)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT, padx=(4, 0))

        # 3. Hàng Đường dẫn thư mục Tool Verry
        row_verry_dir = tk.Frame(card_verry, bg=AppTheme.BG_CARD)
        row_verry_dir.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            row_verry_dir,
            text="Thư mục Tool Verry:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        self.entry_verry_dir = tk.Entry(
            row_verry_dir,
            textvariable=self.var_verry_pipeline_dir,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            font=AppTheme.FONT_CODE
        )
        self.entry_verry_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 4))

        btn_browse_verry = tk.Button(
            row_verry_dir,
            cursor="hand2",
            text="📁 Chọn Thư Mục",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=8,
            pady=1,
            command=self._browse_verry_pipeline_dir
        )
        btn_browse_verry.pack(side=tk.LEFT, padx=(0, 4))

        btn_check_verry = tk.Button(
            row_verry_dir,
            cursor="hand2",
            text="🔍 Kiểm Tra Kết Nối",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=8,
            pady=1,
            command=self._check_verry_pipeline_status
        )
        btn_check_verry.pack(side=tk.LEFT)

        # 4. Hàng Trạng thái Hàng đợi
        row_verry_status = tk.Frame(card_verry, bg=AppTheme.BG_CARD)
        row_verry_status.pack(fill=tk.X, pady=(2, 4))

        self.lbl_verry_pipeline_status = tk.Label(
            row_verry_status,
            text="● Trạng thái Pipeline: Sẵn sàng kết nối với Tool Verry",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED,
            anchor="w"
        )
        self.lbl_verry_pipeline_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_refresh_verry = tk.Button(
            row_verry_status,
            cursor="hand2",
            text="🔄 Làm Mới",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=6,
            pady=1,
            command=self._refresh_verry_pipeline_status
        )
        btn_refresh_verry.pack(side=tk.RIGHT)

        # Card 6: Điều khiển & Lưu Cài Đặt
        card_actions = tk.LabelFrame(
            parent,
            text=" 💾 6. Điều Khiển & Lưu Cài Đặt ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        card_actions.pack(fill=tk.X, pady=(0, 8))

        # Hàng chọn định dạng xuất file
        fmt_frame = tk.Frame(card_actions, bg=AppTheme.BG_CARD)
        fmt_frame.pack(fill=tk.X, pady=(2, 6))
        tk.Label(fmt_frame, text="Định dạng lưu:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_save_format = ttk.Combobox(
            fmt_frame,
            values=[
                "UID|PASS|COOKIE|TOKEN|EMAIL",
                "UID|PASS|2FA|COOKIE|TOKEN|EMAIL",
                "UID|PASS|COOKIE|EMAIL",
                "UID|PASS|COOKIE|TOKEN|PASS_MAIL",
                "UID|PASS|COOKIE|TOKEN|RAW_MAIL"
            ],
            width=32
        )
        saved_fmt = self.config.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
        self.cb_save_format.set(saved_fmt)
        self.cb_save_format.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)

        act_btn_row = tk.Frame(card_actions, bg=AppTheme.BG_CARD)
        act_btn_row.pack(fill=tk.X, pady=4)

        btn_save_cfg = tk.Button(
            act_btn_row,
            cursor="hand2",
            text="💾 LƯU CẤU HÌNH VÀO CONFIG.JSON",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg="#000000",
            activebackground=AppTheme.ACCENT_HOVER,
            bd=0,
            height=2,
            command=lambda: self.save_config(show_toast=True)
        )
        btn_save_cfg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_go_dash = tk.Button(
            act_btn_row,
            cursor="hand2",
            text="▶ VỀ BẢNG ĐIỀU KHIỂN & BẮT ĐẦU",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            height=2,
            command=lambda: self.notebook.select(self.tab_dashboard)
        )
        btn_go_dash.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_go_utils2 = tk.Button(
            act_btn_row,
            cursor="hand2",
            text="🛠️ MỞ TIỆN ÍCH HỆ THỐNG",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            height=2,
            command=lambda: self.notebook.select(self.tab_utilities)
        )
        btn_go_utils2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

    def build_right_monitoring(self, parent: tk.Frame):
        # 0. Quick Action Controls Bar (Start, Stop, Chế độ Reg, Mở Cài Đặt)
        quick_bar = tk.Frame(parent, bg=AppTheme.BG_CARD, bd=1, relief="solid", padx=10, pady=8)
        quick_bar.pack(fill=tk.X, pady=(0, 8))

        # Nhóm Nút Start & Stop
        btn_box = tk.Frame(quick_bar, bg=AppTheme.BG_CARD)
        btn_box.pack(side=tk.LEFT)

        self.btn_start = tk.Button(
            btn_box,
            cursor="hand2",
            text="▶ BẮT ĐẦU REG TÀI KHOẢN",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg="#000000",
            activebackground=AppTheme.ACCENT_HOVER,
            bd=0,
            padx=18,
            pady=6,
            command=self.start_execution
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = tk.Button(
            btn_box,
            cursor="hand2",
            text="⏹ DỪNG LẠI",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.DANGER,
            fg="#ffffff",
            activebackground="#dc2626",
            bd=0,
            state=tk.DISABLED,
            padx=16,
            pady=6,
            command=self.stop_execution
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 14))

        # Nhóm Chọn Chế Độ Reg Ngay Trên Dashboard
        mode_box_dash = tk.Frame(quick_bar, bg=AppTheme.BG_CARD)
        mode_box_dash.pack(side=tk.LEFT, padx=(4, 10))

        tk.Label(
            mode_box_dash,
            text="Chế độ:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT, padx=(0, 6))

        rb_dash_vr = tk.Radiobutton(
            mode_box_dash,
            text="🟢 VR OTP (Email)",
            value="vr",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_dash_vr.pack(side=tk.LEFT, padx=(0, 4))

        rb_dash_nvr = tk.Radiobutton(
            mode_box_dash,
            text="🟡 NVR (Bypass)",
            value="nvr",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_dash_nvr.pack(side=tk.LEFT, padx=(0, 4))

        rb_dash_xm = tk.Radiobutton(
            mode_box_dash,
            text="🔵 Xác Minh Acc NVR",
            value="verify_nvr",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_dash_xm.pack(side=tk.LEFT, padx=(0, 4))

        rb_dash_legacy = tk.Radiobutton(
            mode_box_dash,
            text="🚀 Legacy NV (Mr-SxR)",
            value="legacy_nv",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_dash_legacy.pack(side=tk.LEFT, padx=(0, 2))

        rb_dash_ios = tk.Radiobutton(
            mode_box_dash,
            text="🍏 iOS Bloks (regfb.py)",
            value="ios_bloks",
            variable=self.var_reg_mode,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            command=self.on_reg_mode_changed,
            font=AppTheme.FONT_BODY_BOLD
        )
        rb_dash_ios.pack(side=tk.LEFT, padx=(4, 2))

        saved_leg_ver = self.config.get("legacy_verify_mode", "none")
        init_dash_leg = self.REVERSE_DASH_LEGACY_VERIFY_MAP.get(saved_leg_ver, self.DASH_LEGACY_VERIFY_OPTIONS[0])
        self.cb_dash_legacy_verify = ttk.Combobox(
            mode_box_dash,
            values=self.DASH_LEGACY_VERIFY_OPTIONS,
            state="readonly",
            font=AppTheme.FONT_SMALL_BOLD,
            width=16
        )
        self.cb_dash_legacy_verify.set(init_dash_leg)
        self.cb_dash_legacy_verify.pack(side=tk.LEFT, padx=(2, 4))
        self.cb_dash_legacy_verify.bind("<<ComboboxSelected>>", self._on_dash_legacy_verify_selected)

        saved_srv = self.config.get("server", "m.facebook.com")
        saved_rand_srv = bool(self.config.get("random_server", False)) or (str(saved_srv).lower() == "random")
        init_dash_srv = self.REVERSE_DASH_LEGACY_SERVER_MAP.get(saved_srv, self.DASH_LEGACY_SERVER_OPTIONS[1]) if not saved_rand_srv else self.DASH_LEGACY_SERVER_OPTIONS[0]
        self.cb_dash_legacy_server = ttk.Combobox(
            mode_box_dash,
            values=self.DASH_LEGACY_SERVER_OPTIONS,
            state="readonly",
            font=AppTheme.FONT_SMALL_BOLD,
            width=16
        )
        self.cb_dash_legacy_server.set(init_dash_srv)
        self.cb_dash_legacy_server.pack(side=tk.LEFT, padx=(2, 4))
        self.cb_dash_legacy_server.bind("<<ComboboxSelected>>", self._on_dash_legacy_server_selected)

        # Nhóm Chế độ Phân bổ IP ngay trên Dashboard (2 checkbox đồng bộ thời gian thực)
        alloc_box_dash = tk.Frame(quick_bar, bg=AppTheme.BG_CARD)
        alloc_box_dash.pack(side=tk.LEFT, padx=(6, 8))

        tk.Label(
            alloc_box_dash,
            text="IP:",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT, padx=(0, 4))

        saved_alloc_dash = self.config.get("proxy_alloc_mode", "dedicated")
        is_ded_dash = (saved_alloc_dash != "shared")

        self.chk_dash_mode_dedicated = tk.Checkbutton(
            alloc_box_dash,
            text="🛡️ 1 Luồng 1 IP",
            variable=self.var_proxy_mode_dedicated,
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS if is_ded_dash else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.SUCCESS,
            command=self._on_proxy_mode_dedicated_toggled
        )
        self.chk_dash_mode_dedicated.pack(side=tk.LEFT, padx=(0, 2))

        self.chk_dash_mode_shared = tk.Checkbutton(
            alloc_box_dash,
            text="⚡ Chia đều theo số luồng",
            variable=self.var_proxy_mode_shared,
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT if not is_ded_dash else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.ACCENT,
            command=self._on_proxy_mode_shared_toggled
        )
        self.chk_dash_mode_shared.pack(side=tk.LEFT, padx=(0, 2))

        # Checkbox Auto Up Bot ngay tren Dashboard
        self.chk_dash_bot_upload = tk.Checkbutton(
            quick_bar,
            text="🤖 Auto Up Bot",
            variable=self.var_bot_auto_upload,
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS if self.var_bot_auto_upload.get() else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.SUCCESS,
            command=self._on_bot_auto_upload_toggled
        )
        self.chk_dash_bot_upload.pack(side=tk.LEFT, padx=(6, 2))

        # Checkbox Auto Pipeline Verry ngay tren Dashboard
        self.chk_dash_verry_pipeline = tk.Checkbutton(
            quick_bar,
            text="🔗 Chuyển Verry",
            variable=self.var_enable_verry_pipeline,
            font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS if self.var_enable_verry_pipeline.get() else AppTheme.TEXT_MUTED,
            selectcolor=AppTheme.BG_INPUT,
            activebackground=AppTheme.BG_CARD,
            activeforeground=AppTheme.SUCCESS,
            command=self._on_verry_pipeline_toggled
        )
        self.chk_dash_verry_pipeline.pack(side=tk.LEFT, padx=(2, 4))

        # Phía Phải: Nút Mở Cài Đặt
        right_box = tk.Frame(quick_bar, bg=AppTheme.BG_CARD)
        right_box.pack(side=tk.RIGHT)

        btn_go_settings = tk.Button(
            right_box,
            cursor="hand2",
            text="⚙️ CÀI ĐẶT CẤU HÌNH",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=6,
            command=lambda: self.notebook.select(self.tab_settings)
        )
        btn_go_settings.pack(side=tk.RIGHT, padx=(6, 0))

        btn_go_utils = tk.Button(
            right_box,
            cursor="hand2",
            text="🛠️ TIỆN ÍCH",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=6,
            command=lambda: self.notebook.select(self.tab_utilities)
        )
        btn_go_utils.pack(side=tk.RIGHT, padx=(6, 0))

        # 1. Stats Counter Bar
        stats_frame = tk.Frame(parent, bg=AppTheme.BG_CARD, height=44)
        stats_frame.pack(fill=tk.X, pady=(0, 8))

        self.lbl_stat_total = tk.Label(
            stats_frame, text="Tổng: 0", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN
        )
        self.lbl_stat_total.pack(side=tk.LEFT, padx=16, pady=8)

        self.lbl_stat_success = tk.Label(
            stats_frame, text="● LIVE: 0", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS
        )
        self.lbl_stat_success.pack(side=tk.LEFT, padx=16, pady=8)

        self.lbl_stat_failed = tk.Label(
            stats_frame, text="● DIE: 0", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.DANGER
        )
        self.lbl_stat_failed.pack(side=tk.LEFT, padx=16, pady=8)

        self.lbl_stat_unverified = tk.Label(
            stats_frame, text="● CHƯA XÁC MINH: 0", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.WARNING
        )
        self.lbl_stat_unverified.pack(side=tk.LEFT, padx=16, pady=8)

        self.lbl_stat_bot_uploaded = tk.Label(
            stats_frame, text="● UP BOT: 0", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg="#38bdf8"
        )
        self.lbl_stat_bot_uploaded.pack(side=tk.LEFT, padx=16, pady=8)

        # Quick Table Actions Bar (Row 1: Thao tác bảng, Copy, Xóa & Thư mục/Xuất dữ liệu)
        tbl_act_bar = tk.Frame(parent, bg=AppTheme.BG_DARK)
        tbl_act_bar.pack(fill=tk.X, pady=(0, 4))

        btn_import_tbl = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="📥 Nạp Acc Cần XM", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.ACCENT,
            bd=1, relief="solid", command=self.open_nvr_import_dialog
        )
        btn_import_tbl.pack(side=tk.LEFT, padx=(0, 6))

        btn_up_bot_tbl = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="🤖 Up Bot Shop", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg="#38bdf8",
            bd=1, relief="solid", command=self.upload_all_live_to_bot
        )
        btn_up_bot_tbl.pack(side=tk.LEFT, padx=(0, 6))

        btn_sel_all = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="☑ Chọn tất cả", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", command=self.select_all_rows
        )
        btn_sel_all.pack(side=tk.LEFT, padx=(0, 4))

        btn_desel_all = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="☐ Bỏ chọn", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", command=self.deselect_all_rows
        )
        btn_desel_all.pack(side=tk.LEFT, padx=(0, 4))

        btn_sel_hilite = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="🔘 Chọn bôi đen", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", command=self.toggle_selected_highlighted
        )
        btn_sel_hilite.pack(side=tk.LEFT, padx=(0, 6))

        btn_cp_uid = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="📋 Copy UID", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.INFO,
            bd=1, relief="solid", command=self.copy_selected_uids
        )
        btn_cp_uid.pack(side=tk.LEFT, padx=(0, 4))

        btn_cp_all = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="📋 Copy Full", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.INFO,
            bd=1, relief="solid", command=self.copy_selected_rows_data
        )
        btn_cp_all.pack(side=tk.LEFT, padx=(0, 4))

        btn_view_details = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="👁 Xem chi tiết", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", command=self.on_context_view_details
        )
        btn_view_details.pack(side=tk.LEFT, padx=(0, 4))

        btn_del_sel = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="🗑 Xóa dòng chọn", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER,
            bd=1, relief="solid", command=self.delete_selected_rows
        )
        btn_del_sel.pack(side=tk.LEFT, padx=(0, 4))

        btn_clear_all = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="🧹 Xóa sạch bảng", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER,
            bd=1, relief="solid", command=self.clear_entire_table
        )
        btn_clear_all.pack(side=tk.LEFT, padx=(0, 4))

        # Project Folder & Data Export on the Right side of Row 1
        btn_export = tk.Button(
            tbl_act_bar,
            cursor="hand2",
            text="📤 Xuất File", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.ACCENT,
            bd=1, relief="solid", command=self.export_data_dialog
        )
        btn_export.pack(side=tk.RIGHT, padx=(4, 0))

        btn_open_folder = tk.Button(
            tbl_act_bar,
            cursor="hand2", text="📁 Thư mục Tool", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.INFO,
            bd=1, relief="solid", command=self.open_project_folder
        )
        btn_open_folder.pack(side=tk.RIGHT, padx=(4, 0))

        # Row 2 Toolbar: Tìm kiếm, Chọn nhanh trạng thái & 4 File Kết quả
        tbl_tools_bar = tk.Frame(parent, bg=AppTheme.BG_DARK)
        tbl_tools_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            tbl_tools_bar, text="🔍 Tìm:", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK, fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT, padx=(0, 4))

        self.entry_search = tk.Entry(
            tbl_tools_bar, width=15, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", insertbackground=AppTheme.TEXT_MAIN, font=AppTheme.FONT_SMALL
        )
        self.entry_search.pack(side=tk.LEFT, padx=(0, 4))
        self.entry_search.bind("<KeyRelease>", self.on_search_key_release)

        btn_clear_srch = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="✖", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MUTED,
            bd=1, relief="solid", padx=4, pady=0, command=self.clear_search
        )
        btn_clear_srch.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_search_count = tk.Label(
            tbl_tools_bar, text="", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_DARK, fg=AppTheme.INFO
        )
        self.lbl_search_count.pack(side=tk.LEFT, padx=(0, 6))

        btn_flt_live = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="● LIVE", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.SUCCESS,
            bd=1, relief="solid", command=lambda: self.select_by_status("live")
        )
        btn_flt_live.pack(side=tk.LEFT, padx=(0, 4))

        btn_flt_die = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="● DIE", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER,
            bd=1, relief="solid", command=lambda: self.select_by_status("die")
        )
        btn_flt_die.pack(side=tk.LEFT, padx=(0, 4))

        btn_flt_unver = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="● CHƯA XM", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.WARNING,
            bd=1, relief="solid", command=lambda: self.select_by_status("unverified")
        )
        btn_flt_unver.pack(side=tk.LEFT, padx=(0, 4))

        btn_check_live_tbl = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="🔎 Check Live UID", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.SUCCESS,
            bd=1, relief="solid", command=self.check_live_accounts
        )
        btn_check_live_tbl.pack(side=tk.LEFT, padx=(0, 4))

        btn_check_cookie_tbl = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="🍪 Check Cookie", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.INFO,
            bd=1, relief="solid", command=self.check_cookie_accounts
        )
        btn_check_cookie_tbl.pack(side=tk.LEFT, padx=(0, 8))

        # 4 File Openers on the Right side of Row 2 (Balanced neatly)
        btn_open_unver = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="📂 Chưa XM", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.WARNING,
            bd=1, relief="solid", command=self.open_unverified_file
        )
        btn_open_unver.pack(side=tk.RIGHT, padx=(4, 0))

        btn_open_die = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="📂 File DIE", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER,
            bd=1, relief="solid", command=self.open_die_file
        )
        btn_open_die.pack(side=tk.RIGHT, padx=(4, 0))

        btn_open_live = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="📂 File LIVE", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.SUCCESS,
            bd=1, relief="solid", command=self.open_live_file
        )
        btn_open_live.pack(side=tk.RIGHT, padx=(4, 0))

        btn_open_hot_tbl = tk.Button(
            tbl_tools_bar,
            cursor="hand2", text="📂 Hotmail", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.ACCENT,
            bd=1, relief="solid", command=self.open_hotmail_file
        )
        btn_open_hot_tbl.pack(side=tk.RIGHT, padx=(4, 0))

        # 2. Main Treeview Table with Checkbox Column
        table_container = tk.Frame(parent, bg=AppTheme.BG_CARD)
        table_container.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ("select", "stt", "uid", "target", "password", "two_factor", "cookie", "token", "proxy", "status", "time")
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", selectmode="extended")

        self.tree.heading("select", text="☐", anchor="center", command=self.toggle_all_checkboxes)
        self.tree.column("select", width=35, minwidth=35, anchor="center")

        self.tree.heading("stt", text="#", anchor="center")
        self.tree.column("stt", width=40, minwidth=35, anchor="center")

        self.tree.heading("uid", text="UID Facebook")
        self.tree.column("uid", width=130, minwidth=110)

        self.tree.heading("target", text="Email / SĐT Target")
        self.tree.column("target", width=160, minwidth=130)

        self.tree.heading("password", text="Mật khẩu")
        self.tree.column("password", width=95, minwidth=80)

        self.tree.heading("two_factor", text="2FA Secret")
        self.tree.column("two_factor", width=100, minwidth=80)

        self.tree.heading("cookie", text="Cookie Facebook")
        self.tree.column("cookie", width=145, minwidth=100)

        self.tree.heading("token", text="Token (EAAB/EAAA)")
        self.tree.column("token", width=140, minwidth=100)

        self.tree.heading("proxy", text="Proxy IP")
        self.tree.column("proxy", width=120, minwidth=90)

        self.tree.heading("status", text="Tình trạng", anchor="center")
        self.tree.column("status", width=135, minwidth=100, anchor="center")

        self.tree.heading("time", text="Thời gian", anchor="center")
        self.tree.column("time", width=80, minwidth=70, anchor="center")

        # Color Tags: LIVE = Xanh lá, DIE = Đỏ, UNVERIFIED = Vàng, RUNNING = Xanh dương
        self.tree.tag_configure("live", foreground=AppTheme.SUCCESS, font=AppTheme.FONT_BODY_BOLD)
        self.tree.tag_configure("die", foreground=AppTheme.DANGER, font=AppTheme.FONT_BODY_BOLD)
        self.tree.tag_configure("unverified", foreground=AppTheme.WARNING, font=AppTheme.FONT_BODY_BOLD)
        self.tree.tag_configure("unver", foreground=AppTheme.WARNING, font=AppTheme.FONT_BODY_BOLD)
        self.tree.tag_configure("running", foreground=AppTheme.INFO)
        self.tree.tag_configure("maturing", foreground="#38bdf8", font=AppTheme.FONT_BODY_BOLD)

        sb_y = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.tree.yview)
        sb_x = ttk.Scrollbar(table_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        table_container.rowconfigure(0, weight=1)
        table_container.columnconfigure(0, weight=1)

        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", lambda e: self.on_tree_double_click(e))
        self.tree.bind("<space>", self.on_tree_space_pressed)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Control-a>", lambda e: (self.select_all_rows(), "break")[1])
        self.tree.bind("<Control-A>", lambda e: (self.select_all_rows(), "break")[1])
        self.tree.bind("<Delete>", lambda e: self.delete_selected_rows())

        # Smooth mousewheel scrolling cho bang danh sach tai khoan (khong giat khi 30 luong dang chay)
        def _on_tree_mousewheel(event):
            try:
                self.tree.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")
            except Exception:
                pass
            return "break"
        self.tree.bind("<MouseWheel>", _on_tree_mousewheel)

        # 3. Logs Area (Bottom Right)
        log_card = tk.LabelFrame(
            parent,
            text=" 📝 Nhật ký Hoạt động (Logs) ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            padx=8,
            pady=4
        )
        log_card.pack(fill=tk.X, side=tk.BOTTOM)

        log_head = tk.Frame(log_card, bg=AppTheme.BG_CARD)
        log_head.pack(fill=tk.X, pady=(0, 2))

        lbl_log_sub = tk.Label(
            log_head, text="Nhật ký tiến trình thời gian thực", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED
        )
        lbl_log_sub.pack(side=tk.LEFT)

        btn_cp_log = tk.Button(
            log_head,
            cursor="hand2",
            text="📋 Copy Log", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", padx=6, pady=0, command=self.copy_all_logs
        )
        btn_cp_log.pack(side=tk.RIGHT, padx=(4, 0))

        btn_clr_log = tk.Button(
            log_head,
            cursor="hand2",
            text="🧹 Xóa Log", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", padx=6, pady=0, command=self.clear_logs
        )
        btn_clr_log.pack(side=tk.RIGHT)

        self.txt_logs = scrolledtext.ScrolledText(
            log_card,
            height=7,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            bd=0
        )
        self.txt_logs.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

        self.txt_logs.tag_config("success", foreground=AppTheme.SUCCESS)
        self.txt_logs.tag_config("error", foreground=AppTheme.DANGER)
        self.txt_logs.tag_config("warning", foreground=AppTheme.WARNING)
        self.txt_logs.tag_config("info", foreground=AppTheme.INFO)
        self.txt_logs.tag_config("proxy", foreground="#c084fc")

        # Smooth mousewheel va Auto-scroll thong minh: Khi nguoi dung cuon len doc log thi khong bi giat nguoc xuong
        self._auto_scroll_logs = True

        def _on_logs_mousewheel(event):
            try:
                self.txt_logs.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")
                y_pos = self.txt_logs.yview()
                if len(y_pos) >= 2 and y_pos[1] >= 0.985:
                    self._auto_scroll_logs = True
                else:
                    self._auto_scroll_logs = False
            except Exception:
                pass
            return "break"

        self.txt_logs.bind("<MouseWheel>", _on_logs_mousewheel)

        def _on_logs_click(event):
            try:
                y_pos = self.txt_logs.yview()
                if len(y_pos) >= 2 and y_pos[1] >= 0.985:
                    self._auto_scroll_logs = True
            except Exception:
                pass
        self.txt_logs.bind("<ButtonRelease-1>", _on_logs_click)

    def get_selected_name_type(self) -> str:
        if not hasattr(self, "cb_name_type"):
            return self.config.get("name_type", "vietnamese")
        raw = self.cb_name_type.get()
        return NameManager.normalize_category(raw)

    def set_selected_name_type(self, name_type: str):
        if not hasattr(self, "cb_name_type"):
            return
        norm = NameManager.normalize_category(name_type)
        label_map = {
            "vietnamese": "🇻🇳 Tên Việt Nam (vi_VN)",
            "western": "🇺🇸 Tên Tây / US-UK (en_US)",
            "indian": "🇮🇳 Tên Ấn Độ (hi_IN)",
            "thai": "🇹🇭 Tên Thái Lan (th_TH)",
            "chinese": "🇨🇳 Tên Trung Quốc (zh_CN)",
            "korean": "🇰🇷 Tên Hàn Quốc (ko_KR)",
            "japanese": "🇯🇵 Tên Nhật Bản (ja_JP)",
            "indonesian": "🇮🇩 Tên Indonesia (id_ID)",
            "filipino": "🇵🇭 Tên Philippines (fil_PH)",
            "brazilian": "🇧🇷 Tên Brazil / Latin (pt_BR)",
            "russian": "🇷🇺 Tên Nga / Đông Âu (ru_RU)",
            "arabic": "🇸🇦 Tên Ả Rập / Trung Đông (ar_SA)",
            "auto_proxy": "🌍 Tự động theo Quốc gia Proxy (Khuyên dùng)",
            "global": "🌐 Tên Toàn Cầu (Mix tất cả)",
            "file_mix": "🎲 Lấy ngẫu nhiên Họ, Tên trong File (names.txt)",
            "file": "📁 Tên Tự Nhập theo dòng (Kho names.txt)",
        }
        lbl = label_map.get(norm, "🇻🇳 Tên Việt Nam (vi_VN)")
        self.cb_name_type.set(lbl)

    def get_selected_device_type(self) -> str:
        if not hasattr(self, "cb_device_type"):
            return self.config.get("device_type", "mr_sxr")
        raw = self.cb_device_type.get()
        if "Katana" in raw or "Mr.SxR" in raw:
            return "mr_sxr"
        elif "SupportsFresco" in raw:
            return "android_mobile"
        elif "Apple" in raw or "iOS" in raw:
            return "ios"
        elif "Feature" in raw or "KaiOS" in raw:
            return "kaios"
        elif "Windows" in raw:
            return "windows"
        elif "Ngẫu nhiên" in raw:
            return "random"
        return "mr_sxr"

    def set_selected_device_type(self, device_type: str):
        if not hasattr(self, "cb_device_type"):
            return
        dev_map = {
            "mr_sxr": "📱 Android (FB4A Katana App - Mr.SxR) (Khuyên dùng)",
            "android_katana": "📱 Android (FB4A Katana App - Mr.SxR) (Khuyên dùng)",
            "android_mobile": "🌐 Android Mobile (SupportsFresco Web)",
            "ios": "🍏 Apple iOS (iPhone Safari / App)",
            "kaios": "📞 Feature Phone (KaiOS / Nokia)",
            "windows": "💻 Windows Desktop PC",
            "random": "🎲 Ngẫu nhiên tất cả thiết bị",
        }
        lbl = dev_map.get(str(device_type).lower(), "📱 Android (FB4A Katana App - Mr.SxR) (Khuyên dùng)")
        self.cb_device_type.set(lbl)

    def on_device_type_changed(self, event=None):
        self.config["device_type"] = self.get_selected_device_type()

    def open_ua_generator_tool(self):
        """Hộp thoại Tool Sinh User-Agent & Hồ sơ thiết bị (Mr-SxR)."""
        dlg = tk.Toplevel(self.root)
        dlg.title("⚡ Tool Sinh User-Agent Facebook Katana App (Mr-SxR)")
        dlg.geometry("720x460")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)

        tk.Label(
            dlg,
            text="📱 THÔNG TIN THIẾT BỊ & USER-AGENT ENGINE MR-SXR",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.ACCENT
        ).pack(pady=(12, 6))

        txt_info = scrolledtext.ScrolledText(
            dlg,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            wrap=tk.WORD,
            padx=8,
            pady=8
        )
        txt_info.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        try:
            from core.device_manager import get_random_android_device
            sample_device = get_random_android_device()
            info_text = f"Hãng sản xuất: {sample_device.get('brand', 'Samsung')}\nModel: {sample_device.get('model', 'Galaxy')}\nKatana Version: {sample_device.get('katana_ver', '462.0.0.47.108')}\nUser-Agent Mẫu:\n{sample_device.get('user_agent', 'Mozilla/5.0')}\n"
        except Exception:
            info_text = "Hệ thống tự động đồng bộ User-Agent Katana FB4A chuẩn 19 Hãng, 2,546 Dòng máy và 462 Bản Katana tương ứng với từng phiên đăng ký.\n"

        txt_info.insert(tk.END, info_text)
        txt_info.config(state=tk.DISABLED)

        btn_close = tk.Button(
            dlg,
            text="Đóng",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            command=dlg.destroy
        )
        btn_close.pack(pady=(4, 10))

    def on_name_type_changed(self, event=None):
        cat = self.get_selected_name_type()
        if cat == "file_mix" and hasattr(self, "var_mix_names"):
            self.var_mix_names.set(True)
        desc = NameManager.CATEGORY_NAMES.get(cat, cat)
        self.log(f"[*] Đã chọn bộ họ tên đăng ký: {desc}", "info")
        self.refresh_names_count()
        self.save_config(show_toast=False)

    def refresh_names_count(self):
        if not hasattr(self, "lbl_names_count"):
            return
        c_file = getattr(self, "custom_name_file", "names.txt") or self.config.get("custom_name_file", "names.txt")
        count = NameManager.get_names_count(c_file)
        self.lbl_names_count.config(text=f"Kho: {count} tên")

    def open_custom_names_dialog(self):
        c_file = getattr(self, "custom_name_file", "names.txt") or self.config.get("custom_name_file", "names.txt")
        dlg = tk.Toplevel(self.root)
        dlg.title("Quản lý Kho Họ Tên Tùy Chỉnh (names.txt)")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)
        dlg.lift()
        dlg.focus_force()
        dlg.grab_set()

        dlg.update_idletasks()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        dw, dh = 640, 540
        dlg.geometry(f"{dw}x{dh}+{rx + max(0, (rw - dw) // 2)}+{ry + max(0, (rh - dh) // 2)}")
        dlg.minsize(500, 380)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        top_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK, pady=8, padx=12)
        top_bar.pack(fill=tk.X)
        tk.Label(
            top_bar,
            text=f"📁 File: {os.path.abspath(c_file)}",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.ACCENT
        ).pack(side=tk.LEFT)

        info_lbl = tk.Label(
            dlg,
            text="💡 Hỗ trợ: Mỗi dòng 1 họ tên (John Smith, Nguyễn Văn Nam, hoặc First|Last, First,Last). Có thể bật 'Ghép ngẫu nhiên' để tự mix Họ và Tên giữa các dòng!",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED,
            wraplength=590,
            justify=tk.LEFT,
            padx=12
        )
        info_lbl.pack(fill=tk.X, pady=(0, 6))

        txt_names = scrolledtext.ScrolledText(
            dlg,
            wrap=tk.WORD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            bd=1,
            relief="solid",
            padx=8,
            pady=8
        )
        txt_names.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        def reload_text_from_file():
            txt_names.delete("1.0", tk.END)
            if os.path.exists(c_file):
                try:
                    with open(c_file, "r", encoding="utf-8-sig") as f:
                        txt_names.insert(tk.END, f.read())
                except Exception as ex:
                    txt_names.insert(tk.END, f"# Lỗi đọc file: {ex}")

        reload_text_from_file()

        bot_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK, pady=8, padx=12)
        bot_bar.pack(fill=tk.X)

        lbl_status = tk.Label(bot_bar, text="", font=AppTheme.FONT_BODY, bg=AppTheme.BG_DARK, fg=AppTheme.SUCCESS)
        lbl_status.pack(side=tk.LEFT)

        def on_open_notepad():
            try:
                # subprocess at top level
                subprocess.Popen(["notepad.exe", os.path.abspath(c_file)])
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở Notepad: {e}", parent=dlg)

        def on_import_file():
            f_path = filedialog.askopenfilename(
                title="Chọn file họ tên .txt",
                filetypes=[("Text files (*.txt)", "*.txt"), ("Tất cả files", "*.*")]
            )
            if f_path:
                try:
                    with open(f_path, "r", encoding="utf-8-sig") as f:
                        data = f.read()
                    txt_names.delete("1.0", tk.END)
                    txt_names.insert(tk.END, data)
                    lbl_status.config(text=f"Đã nạp nội dung từ {os.path.basename(f_path)}", fg=AppTheme.INFO)
                except Exception as ex:
                    messagebox.showerror("Lỗi", f"Không thể đọc file: {ex}", parent=dlg)

        def on_save_names():
            content = txt_names.get("1.0", tk.END).strip()
            count = NameManager.save_names_to_file(content, filepath=c_file)
            self.refresh_names_count()
            lbl_status.config(text=f"✔ Đã lưu {count} họ tên vào {os.path.basename(c_file)}!", fg=AppTheme.SUCCESS)
            self.log(f"[Kho Tên] Đã lưu và cập nhật {count} họ tên trong '{c_file}'", "success")
            messagebox.showinfo("Thành công", f"Đã lưu và cập nhật thành công {count} họ tên vào kho!", parent=dlg)

        btn_save = tk.Button(
            bot_bar,
            cursor="hand2",
            text="💾 LƯU & CẬP NHẬT KHO TÊN",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg="#FFFFFF",
            activebackground=AppTheme.ACCENT_HOVER,
            bd=0,
            padx=12,
            pady=4,
            command=on_save_names
        )
        btn_save.pack(side=tk.RIGHT, padx=(6, 0))

        btn_notepad = tk.Button(
            bot_bar,
            cursor="hand2",
            text="📂 Notepad",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            padx=8,
            pady=3,
            command=on_open_notepad
        )
        btn_notepad.pack(side=tk.RIGHT, padx=4)

        btn_import = tk.Button(
            bot_bar,
            cursor="hand2",
            text="📥 Nạp file...",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            padx=8,
            pady=3,
            command=on_import_file
        )
        btn_import.pack(side=tk.RIGHT, padx=4)

        btn_reload = tk.Button(
            bot_bar,
            cursor="hand2",
            text="🔄 Tải lại",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            padx=8,
            pady=3,
            command=reload_text_from_file
        )
        btn_reload.pack(side=tk.RIGHT, padx=4)

    def build_context_menu(self):
        self.menu_context = tk.Menu(self.root, tearoff=0, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN, activebackground=AppTheme.ACCENT, activeforeground="#000000")

        self.menu_context.add_command(label="☑ Chọn tất cả", command=self.select_all_rows)
        self.menu_context.add_command(label="☐ Bỏ chọn tất cả", command=self.deselect_all_rows)
        self.menu_context.add_command(label="🔘 Chọn các dòng đang bôi đen", command=self.toggle_selected_highlighted)

        sub_status = tk.Menu(self.menu_context, tearoff=0, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN, activebackground=AppTheme.ACCENT, activeforeground="#000000")
        sub_status.add_command(label="● Chọn tất cả LIVE", command=lambda: self.select_by_status("live"))
        sub_status.add_command(label="● Chọn tất cả DIE", command=lambda: self.select_by_status("die"))
        sub_status.add_command(label="● Chọn tất cả CHƯA XÁC MINH", command=lambda: self.select_by_status("unverified"))
        self.menu_context.add_cascade(label="🎯 Chọn theo tình trạng", menu=sub_status)

        self.menu_context.add_separator()
        self.menu_context.add_command(label="🔎 Check Live UID (Graph API - 100% không dùng Cookie)", command=self.check_live_accounts)
        self.menu_context.add_command(label="🍪 Check Cookie phiên (Xác thực Cookie Live/NVR/DIE/Hết phiên)", command=self.check_cookie_accounts)
        self.menu_context.add_command(label="⚡ Check Live Toàn Diện (UID + Cookie)", command=self.check_live_selected_or_all)

        self.menu_context.add_separator()
        self.menu_context.add_command(label="👁 Xem chi tiết tài khoản", command=self.on_context_view_details)
        self.menu_context.add_command(label="📋 Copy UID các dòng đã chọn", command=self.copy_selected_uids)
        self.menu_context.add_command(label="📋 Copy toàn bộ dữ liệu đã chọn", command=self.copy_selected_rows_data)
        self.menu_context.add_separator()
        self.menu_context.add_separator()
        self.menu_context.add_command(label="🤖 Up các dòng đã chọn lên Bot Shop (Media ID)", command=self.on_context_upload_selected_to_bot)
        self.menu_context.add_command(label="🤖 Up toàn bộ nick LIVE lên Bot Shop", command=self.upload_all_live_to_bot)
        self.menu_context.add_command(label="🤖 Up toàn bộ nick CHƯA XM lên Bot Shop", command=self.upload_all_unverified_to_bot)
        self.menu_context.add_command(label="🗑 Xóa các dòng đã chọn", command=self.delete_selected_rows)

    def show_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            if row_id not in self.tree.selection():
                self.tree.selection_set(row_id)
        try:
            self.menu_context.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_context.grab_release()

    def on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.open_account_details_dialog(item)

    def on_context_view_details(self):
        selected = self.tree.selection()
        if selected:
            self.open_account_details_dialog(selected[0])
            return
        checked = self.get_checked_items()
        if checked:
            self.open_account_details_dialog(checked[0])
        else:
            messagebox.showinfo("Thông báo", "Vui lòng chọn 1 tài khoản trên bảng để xem chi tiết!")

    def open_account_details_dialog(self, item_id: str):
        """Hộp thoại xem chi tiết thông tin tài khoản với khả năng copy từng trường dữ liệu."""
        if not item_id or not self.tree.exists(item_id):
            return
        vals = self._get_tree_values(item_id)
        if not vals or len(vals) < 9:
            return

        stt = vals[1]
        uid = vals[2]
        target = vals[3]
        pwd = vals[4]
        two_fa = vals[5]
        cookie = vals[6] if len(vals) > 6 else ""
        token = vals[7] if len(vals) > 7 else ""
        proxy = vals[8] if len(vals) > 8 else (vals[6] if len(vals) > 6 else "")
        status = vals[9] if len(vals) > 9 else (vals[7] if len(vals) > 7 else "")
        created_time = vals[10] if len(vals) > 10 else (vals[8] if len(vals) > 8 else "")

        acc_obj = getattr(self, "_row_acc_data", {}).get(item_id, {})
        full_cookie = acc_obj.get("cookie") or cookie
        full_token = acc_obj.get("token") or token
        full_line = self._row_full_lines.get(item_id, f"{uid}|{pwd}|{full_token}|{full_cookie}|{target}")

        dlg = tk.Toplevel(self.root)
        dlg.title(f"🔍 Chi Tiết Tài Khoản - UID: {uid}")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        dw, dh = 680, 560
        dlg.geometry(f"{dw}x{dh}+{rx + max(0, (rw - dw) // 2)}+{ry + max(0, (rh - dh) // 2)}")
        dlg.minsize(600, 480)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        head_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=14, pady=10)
        head_frame.pack(fill=tk.X, padx=12, pady=(10, 8))

        status_color = AppTheme.SUCCESS if "LIVE" in status else (AppTheme.DANGER if "DIE" in status else AppTheme.WARNING)
        tk.Label(
            head_frame,
            text=f"TÀI KHOẢN #{stt} | {status}",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=status_color
        ).pack(side=tk.LEFT)

        tk.Label(
            head_frame,
            text=f"Thời gian: {created_time}",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.RIGHT)

        body_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK, padx=12, pady=4)
        body_frame.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("UID Facebook:", uid, AppTheme.ACCENT),
            ("Email / Target:", target, AppTheme.TEXT_MAIN),
            ("Mật khẩu FB:", pwd, AppTheme.TEXT_MAIN),
            ("2FA Secret:", two_fa, AppTheme.WARNING),
            ("Cookie FB:", full_cookie, AppTheme.INFO),
            ("Token FB:", full_token, AppTheme.ACCENT),
            ("Proxy IP:", proxy, AppTheme.TEXT_MUTED),
        ]

        def copy_text(txt: str, name: str):
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            self.log(f"[Copy] Đã copy {name}: {txt[:40]}", "info")

        for label_text, val_text, color in fields:
            row = tk.Frame(body_frame, bg=AppTheme.BG_CARD, padx=8, pady=5, bd=1, relief="solid")
            row.pack(fill=tk.X, pady=3)

            tk.Label(
                row, text=label_text, width=15, anchor="w",
                font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED
            ).pack(side=tk.LEFT)

            ent = tk.Entry(
                row, font=AppTheme.FONT_CODE, bg=AppTheme.BG_INPUT, fg=color,
                readonlybackground=AppTheme.BG_INPUT,
                bd=0, relief="flat", insertbackground=AppTheme.TEXT_MAIN
            )
            ent.insert(0, str(val_text))
            ent.config(state="readonly")
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))

            tk.Button(
                row, cursor="hand2", text="📋 Copy", font=AppTheme.FONT_SMALL,
                bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid", padx=8, pady=1,
                command=lambda t=val_text, n=label_text: copy_text(str(t), n)
            ).pack(side=tk.RIGHT)

        full_frame = tk.LabelFrame(
            body_frame, text=" 📋 Dòng Định Dạng Đầy Đủ (Full Format) ",
            font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT,
            bd=1, relief="solid", padx=8, pady=6
        )
        full_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 4))

        txt_full = tk.Text(
            full_frame, height=3, font=AppTheme.FONT_CODE, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=0, wrap=tk.CHAR
        )
        txt_full.insert("1.0", full_line)
        txt_full.config(state="disabled")
        txt_full.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        bot_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK, padx=12, pady=10)
        bot_bar.pack(fill=tk.X)

        tk.Button(
            bot_bar, cursor="hand2", text="📋 Copy Toàn Bộ Dòng",
            font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.ACCENT, fg="#FFFFFF",
            activebackground=AppTheme.ACCENT_HOVER, bd=0, padx=12, pady=5,
            command=lambda: copy_text(full_line, "Full Line")
        ).pack(side=tk.LEFT)

        tk.Button(
            bot_bar, cursor="hand2", text="❌ Đóng",
            font=AppTheme.FONT_BODY, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN,
            bd=1, relief="solid", padx=14, pady=5,
            command=dlg.destroy
        ).pack(side=tk.RIGHT)

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            if col == "#1":
                item = self.tree.identify_row(event.y)
                if item:
                    vals = list(self._get_tree_values(item))
                    if vals:
                        current_chk = vals[0]
                        vals[0] = "☐" if current_chk == "☑" else "☑"
                        self._update_tree_item(item, values=vals)

    def on_tree_space_pressed(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        for item in selected:
            vals = list(self._get_tree_values(item))
            if vals:
                current_chk = vals[0]
                vals[0] = "☐" if current_chk == "☑" else "☑"
                self._update_tree_item(item, values=vals)

    def toggle_all_checkboxes(self):
        items = self.tree.get_children()
        if not items:
            return
        first_vals = self._get_tree_values(items[0])
        first_val = first_vals[0] if first_vals else "☐"
        new_val = "☐" if first_val == "☑" else "☑"
        for item in items:
            vals = list(self._get_tree_values(item))
            if vals:
                vals[0] = new_val
                self._update_tree_item(item, values=vals)
        self.tree.heading("select", text=new_val)

    def select_all_rows(self):
        for item in self.tree.get_children():
            vals = list(self._get_tree_values(item))
            if vals:
                vals[0] = "☑"
                self._update_tree_item(item, values=vals)
        self.tree.heading("select", text="☑")

    def deselect_all_rows(self):
        for item in self.tree.get_children():
            vals = list(self._get_tree_values(item))
            if vals:
                vals[0] = "☐"
                self._update_tree_item(item, values=vals)
        self.tree.heading("select", text="☐")

    def toggle_selected_highlighted(self):
        for item in self.tree.selection():
            vals = list(self._get_tree_values(item))
            if vals:
                vals[0] = "☑"
                self._update_tree_item(item, values=vals)

    def select_by_status(self, target_status: str):
        target_tags = {target_status}
        if target_status in ("unverified", "unver"):
            target_tags = {"unverified", "unver"}
        for item in self.tree.get_children():
            tags = set(self._get_tree_tags(item))
            vals = list(self._get_tree_values(item))
            if vals:
                if any(t in tags for t in target_tags):
                    vals[0] = "☑"
                else:
                    vals[0] = "☐"
                self._update_tree_item(item, values=vals)

    def get_checked_items(self) -> List[str]:
        checked = []
        for item in self.tree.get_children():
            vals = self._get_tree_values(item)
            if vals and vals[0] == "☑":
                checked.append(item)
        if not checked:
            checked = list(self.tree.selection())
        return checked

    def copy_selected_uids(self):
        items = self.get_checked_items()
        if not items:
            messagebox.showinfo("Thông báo", "Vui lòng tích chọn ít nhất 1 dòng!")
            return
        uids = []
        for item in items:
            vals = self._get_tree_values(item)
            if vals and len(vals) > 2 and vals[2] and vals[2] != "N/A":
                uids.append(vals[2])
        if uids:
            text = "\n".join(uids)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.log(f"[Copy] Đã copy {len(uids)} UID vào Clipboard!", "success")
            messagebox.showinfo("Đã Copy", f"Đã copy {len(uids)} UID vào Clipboard!")
        else:
            messagebox.showwarning("Thông báo", "Các dòng đã chọn không có UID hợp lệ!")

    def copy_selected_rows_data(self):
        items = self.get_checked_items()
        if not items:
            messagebox.showinfo("Thông báo", "Vui lòng tích chọn ít nhất 1 dòng!")
            return
        lines = []
        for item in items:
            if hasattr(self, "_row_full_lines") and item in self._row_full_lines:
                lines.append(self._row_full_lines[item])
            else:
                vals = self._get_tree_values(item)
                if len(vals) >= 11:
                    line = f"{vals[2]}|{vals[4]}|{vals[5]}|{vals[6]}|{vals[7]}|{vals[3]}|{vals[8]}|{vals[9]}"
                else:
                    line = "|".join(str(v) for v in vals[2:])
                lines.append(line)
        text = "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log(f"[Copy] Đã copy {len(lines)} tài khoản vào Clipboard!", "success")
        messagebox.showinfo("Đã Copy", f"Đã copy {len(lines)} tài khoản vào Clipboard!")

    def _on_uids_deleted_by_user(self, uids: List[str]):
        """
        Xử lý triệt để khi người dùng xóa tài khoản khỏi bảng:
        1. Ghi nhớ UID vào self._deleted_pipeline_uids để luồng ngầm không bao giờ nạp lại.
        2. Dọn dẹp cache bộ nhớ (_tree_items_by_uid, _pipeline_ready_times, nvr_accounts_queue).
        3. Xóa UID khỏi file pipeline_nvr_queue.json và accounts_unverified.txt trên đĩa.
        """
        if not uids:
            return
        cleaned_uids = [str(u).strip() for u in uids if str(u).strip() and str(u).strip() != "N/A"]
        if not cleaned_uids:
            return

        if not hasattr(self, "_deleted_pipeline_uids"):
            self._deleted_pipeline_uids = set()
        self._deleted_pipeline_uids.update(cleaned_uids)

        if hasattr(self, "_tree_items_by_uid"):
            for u in cleaned_uids:
                self._tree_items_by_uid.pop(u, None)
        if hasattr(self, "_pipeline_ready_times"):
            for u in cleaned_uids:
                self._pipeline_ready_times.pop(u, None)

        if hasattr(self, "nvr_accounts_queue") and self.nvr_accounts_queue:
            u_set = set(cleaned_uids)
            self.nvr_accounts_queue = [
                a for a in self.nvr_accounts_queue
                if str(a.get("uid") or "").strip() not in u_set
            ]

        # Xóa khỏi hàng đợi pipeline và file accounts_unverified.txt trên đĩa
        try:
            from core.nvr_pipeline_bridge import remove_accounts_from_pipeline
            dirs_to_clean = [os.getcwd()]
            if hasattr(self, "var_verry_pipeline_dir"):
                d = self.var_verry_pipeline_dir.get().strip()
                if d and d not in dirs_to_clean:
                    dirs_to_clean.append(d)
            for d in dirs_to_clean:
                if os.path.exists(d):
                    remove_accounts_from_pipeline(cleaned_uids, verry_dir=d)
        except Exception as e_q:
            logger.debug(f"Error removing UIDs from pipeline: {e_q}")

    def clear_entire_table(self):
        if not self.tree.get_children():
            return
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa sạch toàn bộ tài khoản trên bảng?"):
            all_uids = []
            for item in self.tree.get_children():
                vals = self._get_tree_values(item)
                if vals and len(vals) > 2 and vals[2] and vals[2] != "N/A":
                    all_uids.append(str(vals[2]).strip())
                self.tree.delete(item)

            if not hasattr(self, "_deleted_pipeline_uids"):
                self._deleted_pipeline_uids = set()
            self._deleted_pipeline_uids.update(all_uids)

            self.row_counter = 0
            if hasattr(self, "_row_full_lines"):
                self._row_full_lines.clear()
            if hasattr(self, "_row_acc_data"):
                self._row_acc_data.clear()
            if hasattr(self, "_tree_item_values"):
                self._tree_item_values.clear()
            if hasattr(self, "_tree_item_tags"):
                self._tree_item_tags.clear()
            if hasattr(self, "_worker_item_map"):
                self._worker_item_map.clear()
            if hasattr(self, "_tree_items_by_uid"):
                self._tree_items_by_uid.clear()
            if hasattr(self, "_pipeline_ready_times"):
                self._pipeline_ready_times.clear()
            self.nvr_accounts_queue = []

            # Xóa sạch hàng đợi pipeline trên đĩa
            try:
                from core.nvr_pipeline_bridge import clear_pipeline_queue
                dirs_to_clean = [os.getcwd()]
                if hasattr(self, "var_verry_pipeline_dir"):
                    d = self.var_verry_pipeline_dir.get().strip()
                    if d and d not in dirs_to_clean:
                        dirs_to_clean.append(d)
                for d in dirs_to_clean:
                    if os.path.exists(d):
                        clear_pipeline_queue(d)
            except Exception:
                pass

            self.stat_total = 0
            self.stat_success = 0
            self.stat_failed = 0
            self.stat_unverified = 0
            self.session_new_success = 0
            self.session_new_unver = 0
            self.session_new_failed = 0
            self.update_stats_display()

            # Xóa triệt để cả session_path và session_path.bak
            empty_session = {
                "rows": [],
                "stats": {"total": 0, "success": 0, "failed": 0, "unverified": 0}
            }
            for sf in [self.session_path, self.session_path + ".bak", self.session_path + ".tmp"]:
                try:
                    if os.path.exists(sf):
                        with open(sf, "w", encoding="utf-8") as f:
                            json.dump(empty_session, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            self.save_table_session(force=True)
            self.log("[*] Đã xóa sạch toàn bộ dữ liệu bảng, sẵn sàng cho phiên mới!", "info")

    def delete_selected_rows(self):
        items = self.get_checked_items()
        if not items:
            messagebox.showinfo("Thông báo", "Vui lòng tích chọn dòng cần xóa!")
            return
        if messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa {len(items)} dòng đã chọn?"):
            deleted_uids = []
            for item in items:
                vals = self._get_tree_values(item)
                if vals and len(vals) > 2 and vals[2] and vals[2] != "N/A":
                    deleted_uids.append(str(vals[2]).strip())
                self.tree.delete(item)
                if hasattr(self, "_tree_item_values"):
                    self._tree_item_values.pop(item, None)
                if hasattr(self, "_tree_item_tags"):
                    self._tree_item_tags.pop(item, None)
                if hasattr(self, "_row_full_lines"):
                    self._row_full_lines.pop(item, None)
                if hasattr(self, "_row_acc_data"):
                    self._row_acc_data.pop(item, None)
            if hasattr(self, "_worker_item_map"):
                for wid, itm in list(self._worker_item_map.items()):
                    if itm in items:
                        self._worker_item_map.pop(wid, None)
            self._on_uids_deleted_by_user(deleted_uids)
            self.recalculate_stats_from_tree()
            self.save_table_session(force=True)
            self.log(f"[*] Đã xóa {len(items)} dòng khỏi bảng.", "info")

    def on_search_key_release(self, event=None):
        if getattr(self, "_search_timer_id", None):
            try:
                self.root.after_cancel(self._search_timer_id)
            except Exception:
                pass
        self._search_timer_id = self.root.after(120, self._execute_search)

    def _execute_search(self):
        kw = self.entry_search.get().strip().lower()
        children = self.tree.get_children()
        if not kw:
            self.lbl_search_count.config(text="")
            return

        matches = []
        for item in children:
            vals = self._get_tree_values(item)
            line_str = " ".join(str(v).lower() for v in vals)
            if kw in line_str:
                matches.append(item)

        if matches:
            self.tree.selection_set(matches)
            self.tree.see(matches[0])
            self.lbl_search_count.config(text=f"Khớp: {len(matches)}/{len(children)}")
        else:
            self.tree.selection_remove(self.tree.selection())
            self.lbl_search_count.config(text="Không khớp")

    def clear_search(self):
        self.entry_search.delete(0, tk.END)
        self.lbl_search_count.config(text="")
        self.tree.selection_remove(self.tree.selection())

    def open_project_folder(self):
        folder = os.path.dirname(os.path.abspath(__file__))
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])
            self.log(f"[*] Đã mở thư mục tool: {folder}", "info")
        except Exception as e:
            self.log(f"Lỗi mở thư mục: {e}", "error")

    def export_data_dialog(self):
        children = self.tree.get_children()
        if not children:
            messagebox.showwarning("Thông báo", "Bảng dữ liệu đang trống, không có tài khoản để xuất!", parent=self.root)
            return

        checked_items = [c for c in children if self._get_tree_values(c) and self._get_tree_values(c)[0] == "☑"]
        target_items = checked_items if checked_items else children
        scope_name = f"{len(checked_items)} dòng đã chọn" if checked_items else f"toàn bộ {len(children)} dòng trên bảng"

        filepath = filedialog.asksaveasfilename(
            title=f"Xuất dữ liệu ({scope_name})",
            defaultextension=".txt",
            filetypes=[("Text file (*.txt)", "*.txt"), ("CSV file (*.csv)", "*.csv"), ("All files (*.*)", "*.*")],
            initialfile="accounts_export.txt",
            parent=self.root
        )
        if not filepath:
            return

        is_csv = filepath.lower().endswith(".csv")

        try:
            count = 0
            with open(filepath, "w", encoding="utf-8-sig") as f:
                if is_csv:
                    f.write("STT,UID,Target,Password,TwoFactor,Cookie,Token,Proxy,Status,Time\n")
                for item in target_items:
                    vals = self._get_tree_values(item)
                    if not vals or len(vals) < 9:
                        continue
                    if is_csv:
                        escaped_cols = [f'"{str(v).replace(chr(34), chr(34)+chr(34))}"' for v in vals[1:]]
                        f.write(",".join(escaped_cols) + "\n")
                    else:
                        full_line = self._row_full_lines.get(item)
                        if full_line:
                            f.write(full_line + "\n")
                        elif len(vals) >= 11:
                            f.write(f"{vals[2]}|{vals[4]}|{vals[5]}|{vals[6]}|{vals[7]}|{vals[3]}|{vals[8]}|{vals[9]}\n")
                        else:
                            f.write("|".join(str(v) for v in vals[2:]) + "\n")
                    count += 1

            self.log(f"[Xuất dữ liệu] Đã xuất thành công {count} tài khoản ra file: {os.path.basename(filepath)}", "success")
            messagebox.showinfo("Thành công", f"Đã xuất thành công {count} tài khoản vào file:\n{filepath}", parent=self.root)
        except Exception as e:
            self.log(f"Lỗi xuất file: {e}", "error")
            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}", parent=self.root)

    def clear_logs(self):
        if hasattr(self, "txt_logs"):
            self.txt_logs.delete("1.0", tk.END)
            self._log_line_count = 0
            self._auto_scroll_logs = True

    def copy_all_logs(self):
        if hasattr(self, "txt_logs"):
            text_val = self.txt_logs.get("1.0", tk.END).strip()
            if text_val:
                self.root.clipboard_clear()
                self.root.clipboard_append(text_val)
                self.log("[*] Đã copy toàn bộ nội dung log vào Clipboard.", "info")

    def clear_table_data(self):
        self.clear_entire_table()

    def open_nvr_import_dialog(self):
        """Mở hộp thoại Nhập danh sách tài khoản NVR thông minh."""
        dlg = tk.Toplevel(self.root)
        dlg.title("📋 Nhập & Nhận Diện Thông Minh Danh Sách Acc NVR")
        dlg.geometry("700x530")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        top_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        top_frame.pack(fill=tk.X, padx=14, pady=(12, 6))

        tk.Label(
            top_frame,
            text="📋 NHẬP ACC NVR THÔNG MINH",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.ACCENT
        ).pack(anchor="w")
        tk.Label(
            top_frame,
            text="Dán danh sách acc cần xác minh vào đây. Tự động nhận diện mọi định dạng:\nUID|PASS, UID|PASS|2FA, UID|PASS|COOKIE, COOKIE_ONLY, UID|PASS|2FA|COOKIE|TOKEN|EMAIL...",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(2, 4))

        txt_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        txt_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        txt_input = tk.Text(
            txt_frame,
            wrap=tk.NONE,
            font=AppTheme.FONT_CODE,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid"
        )
        sb_y = ttk.Scrollbar(txt_frame, orient=tk.VERTICAL, command=txt_input.yview)
        sb_x = ttk.Scrollbar(txt_frame, orient=tk.HORIZONTAL, command=txt_input.xview)
        txt_input.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        txt_input.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        txt_frame.grid_rowconfigure(0, weight=1)
        txt_frame.grid_columnconfigure(0, weight=1)

        lbl_analysis = tk.Label(
            dlg,
            text="Chưa có dữ liệu. Hãy dán tài khoản vào khung trên.",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.WARNING,
            anchor="w"
        )
        lbl_analysis.pack(fill=tk.X, padx=14, pady=(4, 6))

        def _analyze(*args):
            raw_text = txt_input.get("1.0", tk.END).strip()
            if not raw_text:
                lbl_analysis.config(text="Chưa có dữ liệu. Hãy dán tài khoản vào khung trên.", fg=AppTheme.WARNING)
                return [], {}
            from core.nvr_verifier import SmartAccountParser
            accs, stats = SmartAccountParser.parse_accounts(raw_text)
            if not accs:
                lbl_analysis.config(text="⚠️ Chưa nhận diện được tài khoản hợp lệ nào!", fg=AppTheme.DANGER)
                return [], {}
            stats_str = ", ".join(f"{k}: {v}" for k, v in stats.items())
            lbl_analysis.config(text=f"✅ Nhận diện: {len(accs)} acc hợp lệ | Định dạng: {stats_str}", fg=AppTheme.SUCCESS)
            return accs, stats

        txt_input.bind("<KeyRelease>", lambda e: _analyze())

        btn_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        btn_bar.pack(fill=tk.X, padx=14, pady=(6, 12))

        def _load_from_file():
            from tkinter import filedialog
            init_dir = os.path.dirname(__file__)
            path = filedialog.askopenfilename(
                initialdir=init_dir,
                title="Chọn file acc NVR",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                parent=dlg
            )
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8-sig") as f_in:
                        content = f_in.read()
                    txt_input.delete("1.0", tk.END)
                    txt_input.insert("1.0", content)
                    _analyze()
                except Exception as e:
                    messagebox.showerror("Lỗi đọc file", str(e), parent=dlg)

        def _paste_clipboard():
            try:
                clp = dlg.clipboard_get()
                if clp:
                    txt_input.insert(tk.END, ("\n" if txt_input.get("1.0", tk.END).strip() else "") + clp.strip())
                    _analyze()
            except Exception:
                pass

        def _clear_all():
            txt_input.delete("1.0", tk.END)
            _analyze()

        def _load_unverified_default():
            if os.path.exists("accounts_unverified.txt"):
                try:
                    with open("accounts_unverified.txt", "r", encoding="utf-8-sig") as f_in:
                        content = f_in.read()
                    txt_input.delete("1.0", tk.END)
                    txt_input.insert("1.0", content)
                    _analyze()
                except Exception as e:
                    messagebox.showerror("Lỗi", str(e), parent=dlg)
            else:
                messagebox.showinfo("Thông báo", "Chưa có file accounts_unverified.txt!", parent=dlg)

        def _load_accounts_default():
            if os.path.exists("accounts.txt"):
                try:
                    with open("accounts.txt", "r", encoding="utf-8-sig") as f_in:
                        content = f_in.read()
                    txt_input.delete("1.0", tk.END)
                    txt_input.insert("1.0", content)
                    _analyze()
                except Exception as e:
                    messagebox.showerror("Lỗi", str(e), parent=dlg)
            else:
                messagebox.showinfo("Thông báo", "Chưa có file accounts.txt!", parent=dlg)

        btn_unver = tk.Button(
            btn_bar,
            cursor="hand2", text="📂 accounts_unverified.txt", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.WARNING, bd=1, relief="solid", command=_load_unverified_default
        )
        btn_unver.pack(side=tk.LEFT, padx=(0, 6))

        btn_accs = tk.Button(
            btn_bar,
            cursor="hand2", text="📂 accounts.txt", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.INFO, bd=1, relief="solid", command=_load_accounts_default
        )
        btn_accs.pack(side=tk.LEFT, padx=(0, 6))

        btn_file = tk.Button(
            btn_bar,
            cursor="hand2", text="📂 Chọn File", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid", command=_load_from_file
        )
        btn_file.pack(side=tk.LEFT, padx=(0, 6))

        btn_paste = tk.Button(
            btn_bar,
            cursor="hand2", text="📋 Dán", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid", command=_paste_clipboard
        )
        btn_paste.pack(side=tk.LEFT, padx=(0, 6))

        btn_clr = tk.Button(
            btn_bar,
            cursor="hand2", text="✖ Xóa", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER, bd=1, relief="solid", command=_clear_all
        )
        btn_clr.pack(side=tk.LEFT)

        def _confirm_and_save():
            accs, stats = _analyze()
            if not accs:
                messagebox.showwarning("Cảnh báo", "Vui lòng dán danh sách tài khoản hợp lệ trước khi xác nhận!", parent=dlg)
                return
            self.nvr_accounts_queue = accs
            stats_str = ", ".join(f"{k}: {v}" for k, v in stats.items())

            self.var_reg_mode.set("verify_nvr")
            self.populate_table_with_nvr_accounts(accs)
            self.on_reg_mode_changed()

            self.log(f"[*] ĐÃ NẠP THÀNH CÔNG {len(accs)} ACC NVR LÊN BẢNG! Định dạng phát hiện: {stats_str}", "success")
            messagebox.showinfo(
                "Đã nạp thành công",
                f"Đã nạp thành công {len(accs)} tài khoản NVR hiển thị lên bảng chờ xác minh!\n- Định dạng: {stats_str}\n- Bấm '▶ BẮT ĐẦU XÁC MINH' để tiến hành gắn Mail & nhận OTP thật!",
                parent=self.root
            )
            dlg.destroy()

        btn_save = tk.Button(
            btn_bar,
            cursor="hand2", text="💾 Xác Nhận & Nạp Vào Tool", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT, fg="#000000", bd=1, relief="solid", command=_confirm_and_save
        )
        btn_save.pack(side=tk.RIGHT)

    def populate_table_with_nvr_accounts(self, accs: Optional[List[Dict[str, Any]]] = None, clear_first: bool = True):
        """
        Nạp danh sách tài khoản NVR trực tiếp vào Bảng chính (self.tree).
        Hiển thị đầy đủ mọi cột: Checkbox, STT, UID, Target, Password, 2FA, Cookie, Token, Proxy, Status, Time.
        """
        if accs is None:
            accs = getattr(self, "nvr_accounts_queue", [])
            if not accs and os.path.exists("accounts_unverified.txt"):
                try:
                    from core.nvr_verifier import SmartAccountParser
                    with open("accounts_unverified.txt", "r", encoding="utf-8-sig") as f_u:
                        content_u = f_u.read()
                    parsed_accs, _ = SmartAccountParser.parse_accounts(content_u)
                    if parsed_accs:
                        accs = parsed_accs
                except Exception as e:
                    logger.debug(f"Error loading accounts_unverified: {e}")

        if not accs:
            return 0

        # Nếu người dùng chủ động nạp lại danh sách thì mở khóa các UID này khỏi danh sách đã xóa
        if hasattr(self, "_deleted_pipeline_uids") and accs:
            for a in accs:
                u_str = str(a.get("uid") or "").strip()
                if u_str:
                    self._deleted_pipeline_uids.discard(u_str)

        self.nvr_accounts_queue = list(accs)

        if not hasattr(self, "_row_full_lines"):
            self._row_full_lines = {}
        if not hasattr(self, "_row_acc_data"):
            self._row_acc_data = {}

        if clear_first and hasattr(self, "tree"):
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.row_counter = 0
            if hasattr(self, "_tree_item_values"):
                self._tree_item_values.clear()
            if hasattr(self, "_tree_item_tags"):
                self._tree_item_tags.clear()
            self._row_full_lines.clear()
            self._row_acc_data.clear()
            if hasattr(self, "_tree_items_by_uid"):
                self._tree_items_by_uid.clear()

        now_str = datetime.now().strftime("%H:%M:%S")
        for acc in accs:
            self.row_counter += 1
            uid = str(acc.get("uid") or "").strip()
            pwd = str(acc.get("password") or "").strip()
            twofa = str(acc.get("two_factor_secret") or "").strip()
            cookie = str(acc.get("cookie") or "").strip()
            token = str(acc.get("token") or "").strip()
            email = str(acc.get("email") or "").strip()
            target = email if email else "(Chờ gắn Mail mới)"

            cookie_disp = (cookie[:32] + "...") if len(cookie) > 32 else cookie
            token_disp = (token[:24] + "...") if len(token) > 24 else token
            acc_px = str(acc.get("proxy") or "").strip()
            proxy_disp = self.mask_ip(acc_px) if acc_px else "(Chờ cấp IP)"

            row_vals = (
                "☑",
                self.row_counter,
                uid or "N/A",
                target,
                pwd,
                twofa,
                cookie_disp,
                token_disp,
                proxy_disp,
                "⏳ Chờ xác minh NVR",
                now_str
            )
            item_id = self.tree.insert("", "end", values=row_vals, tags=("unverified",))
            if hasattr(self, "_tree_item_values"):
                self._tree_item_values[item_id] = list(row_vals)
            if hasattr(self, "_tree_item_tags"):
                self._tree_item_tags[item_id] = ("unverified",)
            if hasattr(self, "_tree_items_by_uid") and uid:
                self._tree_items_by_uid[uid] = item_id
            self._row_full_lines[item_id] = acc.get("raw_line") or (f"{uid}|{pwd}|{token}|{cookie}|{acc_px}" if acc_px else f"{uid}|{pwd}|{token}|{cookie}")
            self._row_acc_data[item_id] = acc

        self.recalculate_stats()
        self.save_table_session()

        # Đồng bộ số lượng trên giao diện
        if hasattr(self, "spn_accounts"):
            self.spn_accounts.delete(0, tk.END)
            self.spn_accounts.insert(0, str(len(accs)))

        if hasattr(self, "lbl_nvr_count"):
            self.lbl_nvr_count.config(
                text=f"✅ Đang có {len(accs)} acc hiển thị trên bảng, sẵn sàng xác minh!",
                fg=AppTheme.SUCCESS
            )

        if hasattr(self, "btn_start"):
            self.btn_start.config(text=f"▶ BẮT ĐẦU XÁC MINH ({len(accs)} ACC NVR)")

        self.log(f"[*] ĐÃ NẠP {len(accs)} TÀI KHOẢN LÊN BẢNG CHỜ XÁC MINH NVR!", "success")
        return len(accs)

    def recalculate_stats(self):
        """Tính toán lại toàn bộ số liệu thống kê dựa trên dữ liệu bảng thực tế."""
        total = 0
        success = 0
        failed = 0
        unver = 0
        for item_id in self.tree.get_children():
            total += 1
            tags = self._get_tree_tags(item_id)
            vals = self._get_tree_values(item_id)
            status_val = str(vals[9] if len(vals) > 9 else (vals[7] if len(vals) > 7 else "")).lower()

            is_die_match = any(t in tags for t in ("die", "failed", "danger")) or any(k in status_val for k in ("die", "282", "khóa", "vô hiệu", "checkpoint", "tạm ngưng", "ufac", "hết phiên"))
            is_live_match = (not is_die_match) and (any(t in tags for t in ("live", "success")) or "live" in status_val) and ("nvr" not in status_val and "chờ" not in status_val)
            is_unver_match = (not is_die_match) and (not is_live_match) and (any(t in tags for t in ("unver", "unverified", "warning", "running", "maturing")) or any(k in status_val for k in ("chưa", "nvr", "chờ", "unver", "đang xử lý")))

            if is_die_match:
                failed += 1
            elif is_live_match:
                success += 1
            elif is_unver_match:
                unver += 1
            else:
                unver += 1

        self.stat_total = total
        self.stat_success = success
        self.stat_failed = failed
        self.stat_unverified = unver
        self.update_stats_display()

    def get_target_items_for_action(self) -> List[str]:
        """Lấy danh sách các dòng mục tiêu dựa trên lựa chọn bôi đen hoặc tích chọn checkbox."""
        sel = list(self.tree.selection()) if hasattr(self, "tree") else []
        checked = []
        if hasattr(self, "tree"):
            for item in self.tree.get_children():
                vals = self._get_tree_values(item)
                if vals and vals[0] == "☑":
                    checked.append(item)
        if len(checked) > 1 and len(sel) <= 1:
            return checked
        if sel:
            return sel
        if checked:
            return checked
        return list(self.tree.get_children()) if hasattr(self, "tree") else []

    def get_selected_items(self) -> List[str]:
        return self.get_target_items_for_action()

    def check_live_accounts(self, items: Optional[List[str]] = None):
        """Kiểm tra Live Profile UID Facebook (Graph API / Avatar công khai) chuẩn 100% chỉ dùng UID, KHÔNG check Cookie."""
        if items is None:
            items = self.get_target_items_for_action()
        if not items:
            messagebox.showinfo("Thông báo", "Bảng tài khoản hiện đang trống!")
            return

        target_rows = []
        for item_id in items:
            vals = list(self._get_tree_values(item_id))
            uid_val = str(vals[2]).strip() if len(vals) >= 3 else ""
            acc_obj = getattr(self, "_row_acc_data", {}).get(item_id, {})
            if not uid_val or not uid_val.isdigit():
                cookie_val = str(vals[6]).strip() if len(vals) >= 7 and str(vals[6]).strip() else (acc_obj.get("cookie") or "")
                if cookie_val:
                    m_u = re.search(r"c_user=(\d+)", cookie_val)
                    if m_u:
                        uid_val = m_u.group(1)
            if not uid_val or not uid_val.isdigit():
                raw_l = getattr(self, "_row_full_lines", {}).get(item_id, "")
                if raw_l:
                    from core.nvr_verifier import SmartAccountParser
                    parsed_l = SmartAccountParser.parse_line(raw_l) or {}
                    uid_val = parsed_l.get("uid") or uid_val

            if uid_val and uid_val.isdigit():
                target_rows.append({
                    "item_id": item_id,
                    "uid": uid_val,
                    "vals": vals
                })

        if not target_rows:
            messagebox.showinfo("Thông báo", "Không tìm thấy UID Facebook hợp lệ trong các dòng đã chọn để Check Live!")
            return

        self.log(f"[*] Bắt đầu Check Live UID Facebook (Graph API / Profile công khai - 100% không check Cookie) cho {len(target_rows)} tài khoản...", "info")

        def worker():
            from core.facebook_checker import check_facebook_uid_live
            from concurrent.futures import ThreadPoolExecutor, as_completed

            live_count = 0
            die_count = 0
            err_count = 0

            def _check_one(item_info):
                i_id = item_info["item_id"]
                u_val = item_info["uid"]
                r_vals = list(item_info["vals"])

                # KIỂM TRA TRỰC TIẾP BẰNG GRAPH API UID (KHÔNG DÙNG COOKIE)
                is_live, msg = check_facebook_uid_live(u_val, proxy=None, timeout=6)
                if is_live:
                    return i_id, u_val, "live", "🟢 LIVE (UID Live)", "live", r_vals
                elif any(k in msg.lower() for k in ("rate limit", "giới hạn", "chặn", "429")):
                    return i_id, u_val, "err", "⚠️ Bị giới hạn tần suất Meta", "warn", r_vals
                elif any(k in msg.lower() for k in ("silhouette", "placeholder")):
                    return i_id, u_val, "nvr", "🟡 NVR / Avatar mặc định (Chưa đặt ảnh)", "unver", r_vals
                else:
                    return i_id, u_val, "die", "🔴 DIE (UID không tồn tại / Đã bị khóa)", "die", r_vals

            with ThreadPoolExecutor(max_workers=min(50, len(target_rows))) as executor:
                futures = [executor.submit(_check_one, t) for t in target_rows]
                for fut in as_completed(futures):
                    try:
                        i_id, u_val, res_type, new_status, new_tag, r_vals = fut.result()
                    except Exception:
                        continue

                    if res_type == "live":
                        live_count += 1
                    elif res_type == "die":
                        die_count += 1
                    else:
                        err_count += 1

                    status_idx = 9 if len(r_vals) > 9 else 7
                    r_vals[status_idx] = new_status

                    def _update(row_id=i_id, v=list(r_vals), t=new_tag):
                        if hasattr(self, "tree") and self.tree.winfo_exists():
                            self._update_tree_item(row_id, values=v, tags=(t,))
                    self.root.after(0, _update)

            def _finish():
                self.recalculate_stats()
                self.save_table_session()

                # Tự động đồng bộ các file lưu kết quả sau khi Check Live UID (chạy ngầm trong ThreadPool, 0ms freeze)
                sync_tasks = []
                for item_info in target_rows:
                    item_id = item_info["item_id"]
                    u_val = item_info["uid"]
                    row_tags = self._get_tree_tags(item_id)
                    full_l = getattr(self, "_row_full_lines", {}).get(item_id, "")
                    if not full_l:
                        r_vals = item_info.get("vals", [])
                        pwd = r_vals[4] if len(r_vals) > 4 else (getattr(self, "_row_acc_data", {}).get(item_id, {}).get("pass", "") or "")
                        ck = r_vals[6] if len(r_vals) > 6 else (getattr(self, "_row_acc_data", {}).get(item_id, {}).get("cookie", "") or "")
                        full_l = f"{u_val}|{pwd}|{ck}"
                    sync_tasks.append((u_val, full_l, row_tags))
                self._sync_accounts_files_batch(sync_tasks)

                summary_log = f"[*] Check Live UID hoàn tất: 🟢 {live_count} LIVE | 🔴 {die_count} DIE/Khóa"
                if err_count > 0:
                    summary_log += f" | ⚠️ {err_count} Lỗi mạng/Rate Limit"
                self.log(summary_log, "success" if live_count > 0 else "info")
                lines_msg = [
                    f"Kết quả Check Live UID {len(target_rows)} tài khoản:",
                    "",
                    f"- 🟢 LIVE (UID tồn tại / Hoạt động): {live_count}",
                    f"- 🔴 DIE / Bị khóa (UID không tồn tại / Đã xóa): {die_count}",
                ]
                if err_count > 0:
                    lines_msg.append(f"- ⚠️ Lỗi mạng / Rate Limit: {err_count}")
                info_msg = "\n".join(lines_msg)
                messagebox.showinfo("Kết quả Check Live UID", info_msg)

            self.root.after(0, _finish)

        threading.Thread(target=worker, daemon=True).start()

    def check_cookie_accounts(self, items: Optional[List[str]] = None):
        """Kiểm tra hiệu lực Cookie phiên đăng nhập Facebook thực tế (Session Facebook Live/Die)."""
        if items is None:
            items = self.get_target_items_for_action()
        if not items:
            messagebox.showinfo("Thông báo", "Bảng tài khoản hiện đang trống!")
            return

        target_rows = []
        for item_id in items:
            vals = list(self._get_tree_values(item_id))
            uid_val = str(vals[2]).strip() if len(vals) >= 3 else ""
            acc_obj = getattr(self, "_row_acc_data", {}).get(item_id, {})
            cookie_val = acc_obj.get("cookie") or ""

            # Nếu cookie bị thiếu hoặc bị cắt ngắn bởi dấu "...", lấy cookie đầy đủ từ _row_full_lines
            if not cookie_val or cookie_val.endswith("...") or ("c_user" not in cookie_val and "xs" not in cookie_val):
                raw_l = getattr(self, "_row_full_lines", {}).get(item_id, "")
                if raw_l:
                    from core.nvr_verifier import SmartAccountParser
                    parsed_l = SmartAccountParser.parse_line(raw_l) or {}
                    cand_ck = parsed_l.get("cookie") or ""
                    if cand_ck and "..." not in cand_ck and ("c_user" in cand_ck or "xs" in cand_ck):
                        cookie_val = cand_ck
                    elif raw_l:
                        for part in raw_l.split("|"):
                            if ("c_user=" in part or "datr=" in part) and "..." not in part:
                                cookie_val = part.strip()
                                break

            # Nếu vẫn thiếu, kiểm tra cột cookie trên bảng nếu không bị cắt xén
            if (not cookie_val or cookie_val.endswith("...")) and len(vals) > 6 and "..." not in str(vals[6]):
                candidate = str(vals[6]).strip()
                if "c_user=" in candidate or "xs=" in candidate:
                    cookie_val = candidate

            if (not uid_val or not uid_val.isdigit()) and cookie_val:
                m_u = re.search(r"c_user=(\d+)", cookie_val)
                if m_u:
                    uid_val = m_u.group(1)

            pwd_val = acc_obj.get("password") or (str(vals[4]).strip() if len(vals) > 4 else "")
            px_val = str(vals[8]).strip() if len(vals) > 8 else ""
            if px_val in ("(Chờ cấp IP)", "(Không proxy)", "N/A", ""):
                px_val = None

            target_rows.append((item_id, uid_val, cookie_val, pwd_val, px_val, vals))

        if not target_rows:
            messagebox.showinfo("Thông báo", "Không tìm thấy dòng nào để kiểm tra Cookie!")
            return

        self.log(f"[*] Bắt đầu Check Cookie phiên Facebook (Mạng Direct 100%, không dùng proxy gán trên acc) cho {len(target_rows)} tài khoản...", "info")

        def worker():
            from core.facebook_checker import check_facebook_account_live_status
            from concurrent.futures import ThreadPoolExecutor, as_completed

            cookie_live_count = 0
            cookie_die_count = 0
            cookie_nvr_count = 0
            no_cookie_count = 0
            unknown_count = 0

            def _check_one(item_tuple):
                i_id, u_val, ck_val, p_val, px, r_vals = item_tuple
                if not ck_val or ck_val.endswith("...") or ("c_user" not in ck_val and "xs" not in ck_val):
                    return i_id, u_val, "no_cookie", "Không có Cookie hoặc Cookie thiếu c_user/xs", r_vals

                st, msg = check_facebook_account_live_status(
                    cookie_str=ck_val,
                    uid=u_val,
                    password=p_val,
                    proxy=None,  # Check Direct 100%, tuyệt đối không dùng proxy gán vào tài khoản
                    timeout=8
                )
                return i_id, u_val, st, msg, r_vals

            with ThreadPoolExecutor(max_workers=min(6, len(target_rows))) as executor:
                futures = [executor.submit(_check_one, t) for t in target_rows]
                for fut in as_completed(futures):
                    try:
                        i_id, u_val, st, msg, r_vals = fut.result()
                    except Exception as e:
                        continue

                    if st == "live":
                        cookie_live_count += 1
                        new_status = "🟢 Cookie LIVE (Đã vào FB)"
                        new_tag = "live"
                    elif st == "nvr":
                        cookie_nvr_count += 1
                        new_status = "🟡 Cookie NVR (Chờ xác minh)"
                        new_tag = "unver"
                    elif st == "die_282":
                        cookie_die_count += 1
                        new_status = "🔴 Cookie DIE (Checkpoint 282)"
                        new_tag = "die"
                    elif st == "session_expired":
                        cookie_die_count += 1
                        new_status = "⚪ Cookie DIE (Hết phiên/Login)"
                        new_tag = "die"
                    elif st == "no_cookie":
                        no_cookie_count += 1
                        new_status = "⚠️ Không có Cookie"
                        new_tag = "die"
                    else:
                        unknown_count += 1
                        new_status = f"⚠️ Lỗi ({msg[:16]})"
                        new_tag = "warn"

                    status_idx = 9 if len(r_vals) > 9 else 7
                    r_vals[status_idx] = new_status

                    def _update(row_id=i_id, v=list(r_vals), t=new_tag):
                        if hasattr(self, "tree") and self.tree.winfo_exists():
                            self._update_tree_item(row_id, values=v, tags=(t,))
                    self.root.after(0, _update)

            def _finish():
                self.recalculate_stats()
                self.save_table_session()

                # Tự động đồng bộ các file lưu kết quả sau khi Check Cookie (chạy ngầm trong ThreadPool, 0ms freeze)
                sync_tasks = []
                for item_id, uid_val, ck_val, pwd_val, px, r_vals in target_rows:
                    row_tags = self._get_tree_tags(item_id)
                    full_l = getattr(self, "_row_full_lines", {}).get(item_id, "")
                    if not full_l:
                        full_l = f"{uid_val}|{pwd_val}|{ck_val}"
                    sync_tasks.append((uid_val, full_l, row_tags))
                self._sync_accounts_files_batch(sync_tasks)

                summary_log = f"[*] Check Cookie hoàn tất: 🟢 {cookie_live_count} Live | 🟡 {cookie_nvr_count} NVR | 🔴 {cookie_die_count} Die/Hết phiên"
                if no_cookie_count > 0:
                    summary_log += f" | ⚠️ {no_cookie_count} Thiếu cookie"
                self.log(summary_log, "success" if cookie_live_count > 0 else "info")
                info_msg = (
                    f"Kết quả Check Cookie {len(target_rows)} tài khoản:\n\n"
                    f"- 🟢 Cookie LIVE (Phiên hợp lệ - Đã vào Facebook): {cookie_live_count}\n"
                    f"- 🟡 Cookie NVR (Tài khoản đang chờ xác minh OTP): {cookie_nvr_count}\n"
                    f"- 🔴 Cookie DIE / Hết phiên đăng nhập: {cookie_die_count}\n"
                )
                if no_cookie_count > 0:
                    info_msg += f"- ⚠️ Tài khoản thiếu Cookie: {no_cookie_count}\n"
                if unknown_count > 0:
                    info_msg += f"- ⚠️ Lỗi mạng / Chưa rõ: {unknown_count}\n"
                messagebox.showinfo("Kết quả Check Cookie", info_msg)

            self.root.after(0, _finish)

        threading.Thread(target=worker, daemon=True).start()

    def check_live_selected_or_all(self):
        """Kiểm tra thực tế trạng thái tài khoản (Live thật / Vẫn NVR / Checkpoint 282 / Hết phiên) bằng Cookie phiên thực."""
        items = self.get_selected_items()
        if not items:
            items = list(self.tree.get_children())
        if not items:
            messagebox.showinfo("Thông báo", "Bảng tài khoản hiện đang trống!")
            return

        target_rows = []
        for item_id in items:
            vals = list(self._get_tree_values(item_id))
            if len(vals) >= 3:
                uid_val = str(vals[2]).strip()
                if uid_val and uid_val.isdigit():
                    target_rows.append((item_id, uid_val, vals))

        if not target_rows:
            messagebox.showinfo("Thông báo", "Không tìm thấy UID Facebook hợp lệ để kiểm tra!")
            return

        self.log(f"[*] Bắt đầu kiểm tra thực tế (Mạng Direct 100%, không dùng proxy gán trên acc) cho {len(target_rows)} tài khoản...", "info")

        def worker():
            from core.facebook_checker import check_facebook_account_live_status
            from concurrent.futures import ThreadPoolExecutor, as_completed

            live_count = 0
            nvr_count = 0
            die_count = 0
            expired_count = 0
            unknown_count = 0

            # Lấy đầy đủ Cookie / Mật khẩu / Proxy cho từng dòng
            task_list = []
            for item_id, uid_val, vals in target_rows:
                acc_obj = getattr(self, "_row_acc_data", {}).get(item_id, {})
                cookie_val = acc_obj.get("cookie") or ""
                pwd_val = acc_obj.get("password") or (str(vals[4]).strip() if len(vals) > 4 else "")
                if not cookie_val or cookie_val.endswith("...") or ("c_user" not in cookie_val and "xs" not in cookie_val):
                    raw_l = getattr(self, "_row_full_lines", {}).get(item_id, "")
                    if raw_l:
                        from core.nvr_verifier import SmartAccountParser
                        parsed_l = SmartAccountParser.parse_line(raw_l) or {}
                        cand_ck = parsed_l.get("cookie") or ""
                        if cand_ck and "..." not in cand_ck and ("c_user" in cand_ck or "xs" in cand_ck):
                            cookie_val = cand_ck
                        elif raw_l:
                            for part in raw_l.split("|"):
                                if ("c_user=" in part or "datr=" in part) and "..." not in part:
                                    cookie_val = part.strip()
                                    break
                        if not pwd_val:
                            pwd_val = parsed_l.get("password") or ""
                if (not cookie_val or cookie_val.endswith("...")) and len(vals) > 6 and "..." not in str(vals[6]):
                    candidate = str(vals[6]).strip()
                    if "c_user=" in candidate or "xs=" in candidate:
                        cookie_val = candidate
                px_val = str(vals[8]).strip() if len(vals) > 8 else ""
                if px_val in ("(Chờ cấp IP)", "(Không proxy)", "N/A", ""):
                    px_val = None

                task_list.append((item_id, uid_val, cookie_val, pwd_val, px_val, vals))

            workers = min(5, len(task_list), 8)

            def _check_one(item_tuple):
                i_id, u_val, ck_val, p_val, px, r_vals = item_tuple
                st, msg = check_facebook_account_live_status(
                    cookie_str=ck_val,
                    uid=u_val,
                    password=p_val,
                    proxy=None,  # Check Direct 100%, tuyệt đối không dùng proxy gán vào tài khoản
                    timeout=8
                )
                return i_id, u_val, st, msg, r_vals

            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(_check_one, t): t for t in task_list}
                for fut in as_completed(future_map):
                    try:
                        i_id, u_val, st, msg, r_vals = fut.result()
                    except Exception as e:
                        t = future_map[fut]
                        i_id, u_val, r_vals = t[0], t[1], t[5]
                        st, msg = "unknown", str(e)

                    if st == "live":
                        live_count += 1
                        new_status = "🟢 LIVE (Đã vào FB)"
                        new_tag = "live"
                    elif st == "nvr":
                        nvr_count += 1
                        new_status = "🟡 VẪN NVR (Chờ XM)"
                        new_tag = "unver"
                    elif st == "die_282":
                        die_count += 1
                        new_status = "🔴 DIE (Checkpoint 282)"
                        new_tag = "die"
                    elif st == "session_expired":
                        expired_count += 1
                        die_count += 1
                        new_status = "⚪ HẾT PHIÊN (Login lại)"
                        new_tag = "die"
                    elif st == "no_cookie":
                        die_count += 1
                        new_status = "⚠️ Không có Cookie"
                        new_tag = "die"
                    else:
                        unknown_count += 1
                        new_status = f"⚠️ CHƯA RÕ ({msg[:20]})"
                        new_tag = "warn"

                    status_idx = 9 if len(r_vals) > 9 else 7
                    r_vals[status_idx] = new_status

                    def _update(row_id=i_id, v=list(r_vals), t=new_tag):
                        if hasattr(self, "tree") and self.tree.winfo_exists():
                            self._update_tree_item(row_id, values=v, tags=(t,))
                    self.root.after(0, _update)

            def _finish():
                self.recalculate_stats()
                self.save_table_session()

                # Tự động đồng bộ các file lưu kết quả sau khi kiểm tra (chạy ngầm trong ThreadPool, 0ms freeze)
                sync_tasks = []
                for item_id, uid_val, ck_val, pwd_val, px, r_vals in task_list:
                    row_tags = self._get_tree_tags(item_id)
                    full_l = getattr(self, "_row_full_lines", {}).get(item_id, "")
                    if not full_l:
                        full_l = f"{uid_val}|{pwd_val}|{ck_val}"
                    sync_tasks.append((uid_val, full_l, row_tags))
                self._sync_accounts_files_batch(sync_tasks)

                summary_log = f"[*] Hoàn tất kiểm tra: 🟢 {live_count} LIVE | 🟡 {nvr_count} VẪN NVR | 🔴 {die_count} DIE"
                if expired_count > 0:
                    summary_log += f" | ⚪ {expired_count} Hết phiên"
                self.log(summary_log, "success" if live_count > 0 else ("warning" if nvr_count > 0 else "info"))

                info_msg = (
                    f"Đã kiểm tra xong {len(target_rows)} tài khoản:\n\n"
                    f"- 🟢 LIVE THỰC TẾ (Đã vào FB): {live_count}\n"
                    f"- 🟡 VẪN NVR (Chờ xác minh OTP): {nvr_count}\n"
                    f"- 🔴 DIE THỰC TẾ (Checkpoint / Hết phiên): {die_count}\n"
                )
                if expired_count > 0:
                    info_msg += f"- ⚪ HẾT PHIÊN ĐĂNG NHẬP: {expired_count}\n"
                if unknown_count > 0:
                    info_msg += f"- ⚠️ CHƯA RÕ / LỖI MẠNG: {unknown_count}\n"

                messagebox.showinfo("Kết quả Kiểm Tra Thực Tế", info_msg)

            self.root.after(0, _finish)

        threading.Thread(target=worker, daemon=True).start()

    def _sync_accounts_files_batch(self, updates: List[Tuple[str, str, Tuple[str, ...]]]):
        """
        Đồng bộ hàng loạt accounts_live.txt, accounts_die.txt, accounts_unverified.txt
        trong ThreadPoolExecutor chạy ngầm, không bao giờ gây đơ / lag / treo Main UI Thread.
        updates: danh sách tuple (uid, full_line, tags)
        """
        if not updates:
            return
        if hasattr(self, "_file_save_executor"):
            self._file_save_executor.submit(self._sync_accounts_files_batch_sync, updates)
        else:
            threading.Thread(target=self._sync_accounts_files_batch_sync, args=(updates,), daemon=True).start()

    def _sync_accounts_files_batch_sync(self, updates: List[Tuple[str, str, Tuple[str, ...]]]):
        if not updates:
            return
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            live_to_add = {}
            die_to_add = {}
            unver_to_add = {}
            remove_from_live = set()
            remove_from_die = set()
            remove_from_unver = set()

            for uid_val, full_l, row_tags in updates:
                u_str = str(uid_val).strip()
                if not u_str or not u_str.isdigit():
                    continue
                tag_set = set(row_tags)
                if "live" in tag_set:
                    live_to_add[u_str] = full_l
                    remove_from_die.add(u_str)
                    remove_from_unver.add(u_str)
                elif "die" in tag_set:
                    die_to_add[u_str] = full_l
                    remove_from_live.add(u_str)
                    remove_from_unver.add(u_str)
                elif "unver" in tag_set or "unverified" in tag_set:
                    unver_to_add[u_str] = full_l
                    remove_from_live.add(u_str)
                    remove_from_die.add(u_str)

            # Đồng bộ accounts_live.txt một lần duy nhất
            if live_to_add or remove_from_live:
                lines = []
                if os.path.exists("accounts_live.txt"):
                    try:
                        with open("accounts_live.txt", "r", encoding="utf-8-sig") as f:
                            lines = [l.strip() for l in f if l.strip()]
                    except Exception:
                        pass
                lines = [l for l in lines if not any(u in l for u in remove_from_live)]
                for u, fl in live_to_add.items():
                    if not any(u in l for l in lines):
                        lines.append(fl)
                try:
                    with open("accounts_live.txt", "w", encoding="utf-8-sig") as f:
                        for l in lines:
                            f.write(l + "\n")
                except Exception:
                    pass

            # Đồng bộ accounts_die.txt một lần duy nhất
            if die_to_add or remove_from_die:
                lines = []
                if os.path.exists("accounts_die.txt"):
                    try:
                        with open("accounts_die.txt", "r", encoding="utf-8-sig") as f:
                            lines = [l.strip() for l in f if l.strip()]
                    except Exception:
                        pass
                lines = [l for l in lines if not any(u in l for u in remove_from_die)]
                for u, fl in die_to_add.items():
                    if not any(u in l for l in lines):
                        lines.append(fl)
                try:
                    with open("accounts_die.txt", "w", encoding="utf-8-sig") as f:
                        for l in lines:
                            f.write(l + "\n")
                except Exception:
                    pass

            # Đồng bộ accounts_unverified.txt một lần duy nhất
            if unver_to_add or remove_from_unver:
                lines = []
                if os.path.exists("accounts_unverified.txt"):
                    try:
                        with open("accounts_unverified.txt", "r", encoding="utf-8-sig") as f:
                            lines = [l.strip() for l in f if l.strip()]
                    except Exception:
                        pass
                lines = [l for l in lines if not any(u in l for u in remove_from_unver)]
                for u, fl in unver_to_add.items():
                    if not any(u in l for l in lines):
                        lines.append(fl)
                try:
                    with open("accounts_unverified.txt", "w", encoding="utf-8-sig") as f:
                        for l in lines:
                            f.write(l + "\n")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Error in _sync_accounts_files_batch_sync: {e}")

    def save_result_by_category(self, result: RegistrationResult, proxy_str: str = ""):
        if hasattr(self, "_file_save_executor"):
            self._file_save_executor.submit(self._save_result_by_category_sync, result, proxy_str)
        else:
            self._save_result_by_category_sync(result, proxy_str)

    def _save_result_by_category_sync(self, result: RegistrationResult, proxy_str: str = ""):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = (result.status or "").lower()
        save_fmt = self.config.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
        if result.two_factor_secret and "2FA" not in str(save_fmt).upper():
            if "PASS|" in str(save_fmt).upper():
                save_fmt = str(save_fmt).replace("PASS|", "PASS|2FA|")
            elif "PASSWORD|" in str(save_fmt).upper():
                save_fmt = str(save_fmt).replace("PASSWORD|", "PASSWORD|2FA|")
            else:
                save_fmt = f"{save_fmt}|2FA"
        # Đảm bảo UID luôn có trong cookie string nếu có cookie (không gọi network trên GUI thread)
        if result.uid and result.cookie_string and "c_user=" not in result.cookie_string:
            result.cookie_string = f"c_user={result.uid}; " + result.cookie_string
        line = result.format_line(save_fmt)
        res_meta = getattr(result, "metadata", {}) or {}
        err_msg_lower = (result.error_message or "").lower()
        from core.email_service import is_checkpoint_die
        has_strict_die_keyword = is_checkpoint_die(err_msg_lower)
        is_explicit_not_die = (not has_strict_die_keyword) and any(k in err_msg_lower for k in (
            "không die", "khong die", "chưa die", "chua die", "nvr", "chờ xác minh",
            "chua xac minh", "chưa xác minh", "dạng checkpoint khác", "form xác minh",
            "chưa thoát trang", "chưa thoát form", "chưa hoàn tất"
        ))
        has_strict_die_marker = bool(
            status in ("checkpoint", "die", "failed_checkpoint", "checkpoint_282", "die_282", "session_expired")
            or res_meta.get("checkpoint") is True
            or res_meta.get("die") is True
            or getattr(result, "is_checkpoint", False)
            or has_strict_die_keyword
        ) and not is_explicit_not_die
        is_checkpoint = bool(has_strict_die_marker)
        is_explicit_nvr = bool(
            not is_checkpoint
            and (
                status in ("unverified", "nvr")
                or res_meta.get("unverified") is True
                or res_meta.get("nvr") is True
                or res_meta.get("not_die") is True
                or is_explicit_not_die
            )
        )
        has_valid_cookie = bool(
            result.cookie_string
            and "c_user=" in result.cookie_string
            and "xs=" in result.cookie_string
            and "xs=deleted" not in result.cookie_string
        )
        is_live_confirmed = bool(
            result.success
            and (status in ("live", "success") or res_meta.get("live_verified") is True or res_meta.get("vr_verified") is True or res_meta.get("verified_nvr") is True)
            and not is_checkpoint
            and not is_explicit_nvr
            and has_valid_cookie
        )
        is_nvr = bool(
            not is_live_confirmed
            and not is_checkpoint
            and is_explicit_nvr
        )
        uid_to_check = str(result.uid or "").strip()

        # BẢO VỆ CHUẨN XÁC: Chế độ No-Verify (none) hoặc Legacy NV chưa xác minh OTP -> TUYỆT ĐỐI KHÔNG ghi accounts_live.txt
        if res_meta.get("verify_mode") == "none" or (res_meta.get("reg_mode") in ("legacy_nv", "legacy") and not (res_meta.get("vr_verified") or res_meta.get("verified_nvr"))):
            is_live_confirmed = False
            is_nvr = bool(not is_checkpoint and uid_to_check and uid_to_check.isdigit() and len(uid_to_check) >= 8)

        has_uid_and_cookie = bool(uid_to_check and uid_to_check.isdigit() and len(uid_to_check) >= 8 and (has_valid_cookie or getattr(result, "cookie_string", "")))
        # Tự động up lên Bot Shop nếu tính năng được bật (Hỗ trợ cả LIVE và NVR hợp lệ)
        should_upload_to_bot = bool(
            hasattr(self, "var_bot_auto_upload")
            and self.var_bot_auto_upload.get()
            and uid_to_check
            and uid_to_check != "N/A"
            and not is_checkpoint
            and (is_live_confirmed or (result.success and has_valid_cookie) or (is_nvr and has_uid_and_cookie))
        )
        if should_upload_to_bot:
            if not hasattr(self, "_bot_uploaded_uids"):
                self._bot_uploaded_uids = set()
            if uid_to_check not in self._bot_uploaded_uids:
                self._bot_uploaded_uids.add(uid_to_check)
                if hasattr(self, "_bot_upload_executor"):
                    self._bot_upload_executor.submit(self.upload_single_account_to_bot, result)
                else:
                    threading.Thread(target=self.upload_single_account_to_bot, args=(result,), daemon=True).start()

        # 1. LIVE / SUCCESS (VR OTP & XM NVR) -> accounts_live.txt & accounts.txt
        if is_live_confirmed:
            try:
                # 1. Deduplication for accounts_live.txt (chống lưu trùng lặp)
                already_in_live = False
                if os.path.exists("accounts_live.txt") and uid_to_check and uid_to_check != "N/A":
                    try:
                        with open("accounts_live.txt", "r", encoding="utf-8-sig", errors="ignore") as f_chk:
                            for l in f_chk:
                                l_clean = l.strip()
                                if not l_clean or l_clean.startswith("#"):
                                    continue
                                parts = l_clean.split("|")
                                if (parts and parts[0].strip() == uid_to_check) or f"c_user={uid_to_check}" in l_clean:
                                    already_in_live = True
                                    break
                    except Exception:
                        already_in_live = False

                if not already_in_live:
                    with open("accounts_live.txt", "a", encoding="utf-8-sig") as f:
                        f.write(line + "\n")

                # 2. Cập nhật hoặc thêm mới vào accounts.txt (ghi đè dòng cũ NVR bằng dòng LIVE mới)
                if os.path.exists("accounts.txt") and uid_to_check and uid_to_check != "N/A":
                    try:
                        with open("accounts.txt", "r", encoding="utf-8-sig", errors="ignore") as f_accs:
                            acc_lines = f_accs.readlines()
                        updated = False
                        new_lines = []
                        for l in acc_lines:
                            l_clean = l.strip()
                            is_match = False
                            if l_clean and not l_clean.startswith("#"):
                                parts = l_clean.split("|")
                                if (parts and parts[0].strip() == uid_to_check) or f"c_user={uid_to_check}" in l_clean:
                                    is_match = True
                            if is_match:
                                if not updated:
                                    new_lines.append(line + "\n")
                                    updated = True
                            else:
                                new_lines.append(l)
                        if not updated:
                            new_lines.append(line + "\n")
                        with open("accounts.txt", "w", encoding="utf-8-sig") as f_accs:
                            f_accs.writelines(new_lines)
                    except Exception as e:
                        self.log(f"Lỗi ghi file accounts.txt: {e}", "error")
                else:
                    with open("accounts.txt", "a", encoding="utf-8-sig") as f:
                        f.write(line + "\n")
            except Exception as e:
                self.log(f"Lỗi ghi file LIVE: {e}", "error")

            # Tự động gỡ khỏi accounts_unverified.txt và accounts_die.txt nếu tài khoản vừa được xác minh thành công
            if uid_to_check and uid_to_check != "N/A":
                for other_fn in ["accounts_unverified.txt", "accounts_die.txt"]:
                    if os.path.exists(other_fn):
                        try:
                            with open(other_fn, "r", encoding="utf-8-sig", errors="ignore") as f_oth:
                                oth_lines = f_oth.readlines()
                            filtered = [ol for ol in oth_lines if not (
                                ol.strip().startswith(uid_to_check + "|")
                                or ol.strip() == uid_to_check
                                or f"c_user={uid_to_check}" in ol
                            )]
                            if len(filtered) < len(oth_lines):
                                with open(other_fn, "w", encoding="utf-8-sig") as f_oth:
                                    f_oth.writelines(filtered)
                        except Exception:
                            pass

            # 3. KÍCH HOẠT PIPELINE TỰ ĐỘNG TTC PRO: Đổi Info -> Gán TTC (1:1) -> Cày Xu
            auto_ttc_enabled = False
            if hasattr(self, "var_auto_ttc") and self.var_auto_ttc is not None:
                try:
                    auto_ttc_enabled = bool(self.var_auto_ttc.get())
                except Exception:
                    auto_ttc_enabled = bool(self.config.get("auto_ttc_pipeline", False))
            else:
                auto_ttc_enabled = bool(self.config.get("auto_ttc_pipeline", False))
            if auto_ttc_enabled and uid_to_check and uid_to_check != "N/A":
                try:
                    from core.ttc_pipeline_bridge import TTCPipelineBridge
                    bridge = TTCPipelineBridge.get_instance()
                    if bridge.is_available():
                        self.log(f"\U0001f680 [Pipeline] \u0110ang chuy\u1ec3n giao nick [{uid_to_check}] sang TTC PRO (\u0110\u1ed5i Info \u2794 G\u00e1n TTC \u2794 C\u00e0y Xu)...", "info")
                        bridge.process_live_account_async(
                            result=result,
                            proxy_str=proxy_str,
                            log_callback=lambda msg, lvl="info": self.log(msg, lvl)
                        )
                    else:
                        self.log("[Pipeline] Kh\u00f4ng t\u00ecm th\u1ea5y d\u1eff li\u1ec7u TTC PRO \u0111\u1ec3 t\u1ef1 \u0111\u1ed9ng k\u00edch ho\u1ea1t", "warning")
                except Exception as ex_pipe:
                    self.log(f"[Pipeline] L\u1ed7i k\u00edch ho\u1ea1t t\u1ef1 \u0111\u1ed9ng TTC PRO: {ex_pipe}", "warning")

        # 2. UNVERIFIED / NVR -> accounts_unverified.txt & accounts.txt (TUYỆT ĐỐI KHÔNG GHI DIE!)
        elif is_nvr and not is_checkpoint and uid_to_check and uid_to_check != "N/A" and uid_to_check.isdigit() and len(uid_to_check) >= 8:
            try:
                # Tự động gỡ khỏi accounts_live.txt nếu trước đó từng bị lưu nhầm vào LIVE
                if os.path.exists("accounts_live.txt") and uid_to_check and uid_to_check != "N/A":
                    try:
                        with open("accounts_live.txt", "r", encoding="utf-8-sig", errors="ignore") as f_live:
                            l_lines = f_live.readlines()
                        f_clean = [ol for ol in l_lines if not (ol.strip().startswith(uid_to_check + "|") or f"c_user={uid_to_check}" in ol)]
                        if len(f_clean) < len(l_lines):
                            with open("accounts_live.txt", "w", encoding="utf-8-sig") as f_live:
                                f_live.writelines(f_clean)
                    except Exception:
                        pass
                already_in_unver = False
                if os.path.exists("accounts_unverified.txt") and uid_to_check and uid_to_check != "N/A":
                    try:
                        with open("accounts_unverified.txt", "r", encoding="utf-8-sig", errors="ignore") as f_chk:
                            for l in f_chk:
                                l_clean = l.strip()
                                if l_clean and (l_clean.startswith(uid_to_check + "|") or f"c_user={uid_to_check}" in l_clean):
                                    already_in_unver = True
                                    break
                    except Exception:
                        already_in_unver = False
                if not already_in_unver:
                    with open("accounts_unverified.txt", "a", encoding="utf-8-sig") as f:
                        f.write(f"{line}|NVR|{now_str}\n")

                already_in_accs = False
                if os.path.exists("accounts.txt") and uid_to_check and uid_to_check != "N/A":
                    try:
                        with open("accounts.txt", "r", encoding="utf-8-sig", errors="ignore") as f_accs:
                            for l in f_accs:
                                l_clean = l.strip()
                                if l_clean and (l_clean.startswith(uid_to_check + "|") or f"c_user={uid_to_check}" in l_clean):
                                    already_in_accs = True
                                    break
                    except Exception:
                        already_in_accs = False
                if not already_in_accs:
                    with open("accounts.txt", "a", encoding="utf-8-sig") as f:
                        f.write(f"{line}|NVR\n")
            except Exception as e:
                self.log(f"Lỗi ghi file Chưa xác minh: {e}", "error")

            # KÍCH HOẠT PIPELINE CHUYỂN SANG TOOL VERRY (NVR)
            if getattr(self, "var_enable_verry_pipeline", None) and self.var_enable_verry_pipeline.get():
                try:
                    from core.nvr_pipeline_bridge import enqueue_nvr_account, _safe_float
                    v_dir = self.var_verry_pipeline_dir.get().strip() if hasattr(self, "var_verry_pipeline_dir") else r"C:\Users\truon\Downloads\verry"
                    delay_val = self.var_verry_pipeline_delay.get() if hasattr(self, "var_verry_pipeline_delay") else "2 phút"
                    delay_m = _safe_float(delay_val, 2.0)
                    enqueue_nvr_account(
                        account_data_or_line=result,
                        delay_minutes=delay_m,
                        verry_dir=v_dir,
                        logger_fn=lambda msg, lvl="info": self.log(msg, lvl)
                    )
                except Exception as ex_pipe:
                    self.log(f"⚠️ [Pipeline Verry] Lỗi đẩy acc vào hàng đợi: {ex_pipe}", "warning")

        # 3. DIE / CHECKPOINT 282 / THẬT SỰ HỎNG -> accounts_die.txt (CHỈ GHI KHI THỰC SỰ LÀ CHECKPOINT/DIE!)
        elif is_checkpoint or status in ("checkpoint", "die_282") or res_meta.get("checkpoint"):
            err = (result.error_message or "Facebook Registration Failed").replace("\n", " ")
            die_line = f"{line}|DIE: {err}|{now_str}"
            try:
                already_in_die = False
                if os.path.exists("accounts_die.txt") and uid_to_check and uid_to_check != "N/A":
                    try:
                        with open("accounts_die.txt", "r", encoding="utf-8-sig", errors="ignore") as f_chk:
                            for l in f_chk:
                                l_clean = l.strip()
                                if l_clean and (l_clean.startswith(uid_to_check + "|") or f"c_user={uid_to_check}" in l_clean):
                                    already_in_die = True
                                    break
                    except Exception:
                        already_in_die = False
                if not already_in_die:
                    with open("accounts_die.txt", "a", encoding="utf-8-sig") as f:
                        f.write(die_line + "\n")

                # Tự động gỡ khỏi accounts_unverified.txt và accounts_live.txt nếu tài khoản bị DIE
                if uid_to_check and uid_to_check != "N/A":
                    for other_fn in ["accounts_unverified.txt", "accounts_live.txt"]:
                        if os.path.exists(other_fn):
                            try:
                                with open(other_fn, "r", encoding="utf-8-sig", errors="ignore") as f_oth:
                                    oth_lines = f_oth.readlines()
                                filtered = [ol for ol in oth_lines if not (
                                    ol.strip().startswith(uid_to_check + "|")
                                    or ol.strip() == uid_to_check
                                    or f"c_user={uid_to_check}" in ol
                                )]
                                if len(filtered) < len(oth_lines):
                                    with open(other_fn, "w", encoding="utf-8-sig") as f_oth:
                                        f_oth.writelines(filtered)
                            except Exception:
                                pass
            except Exception as e:
                self.log(f"Lỗi ghi file DIE: {e}", "error")

    def open_external_file(self, filename: str):
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8-sig") as f:
                f.write(f"# File kết quả: {filename}\n")
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            else:
                subprocess.Popen(["xdg-open", filepath])
            self.log(f"[*] Đã mở file: {filename}", "info")
        except Exception as e:
            self.log(f"Lỗi mở file {filename}: {e}", "error")

    def _on_window_focus(self, event):
        if event.widget == self.root:
            self.refresh_hotmail_count()

    def open_hotmail_file(self):
        filepath = os.path.join(os.path.dirname(__file__), "hotmails.txt")
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8-sig") as f:
                f.write("# Danh sách Hotmail tự nhập (Mỗi dòng 1 tài khoản)\n# Định dạng: email|password|refresh_token|client_id|rec_email|rec_password\n")
        self.open_external_file("hotmails.txt")
        self.refresh_hotmail_count()

    def import_hotmail_file(self):
        filepath = filedialog.askopenfilename(
            title="Chọn file danh sách Hotmail",
            filetypes=[("Text files (*.txt)", "*.txt"), ("All files (*.*)", "*.*")],
            parent=self.root
        )
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

            if not lines:
                messagebox.showwarning("Thông báo", "File được chọn không chứa tài khoản Hotmail hợp lệ nào!", parent=self.root)
                return

            choice = messagebox.askyesnocancel(
                "Nhập danh sách Hotmail",
                f"Đã tìm thấy {len(lines)} dòng tài khoản từ file:\n{os.path.basename(filepath)}\n\n"
                f"• Chọn YES: NỐI THÊM vào kho hiện tại\n"
                f"• Chọn NO: GHI ĐÈ toàn bộ kho hiện tại\n"
                f"• Chọn CANCEL: Hủy bỏ",
                parent=self.root
            )
            if choice is None:
                return

            dest_path = os.path.join(os.path.dirname(__file__), "hotmails.txt")
            if choice is True:
                existing_lines = []
                if os.path.exists(dest_path):
                    with open(dest_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                        existing_lines = [l.strip() for l in f if l.strip()]
                existing_set = set(existing_lines)
                new_added = 0
                with open(dest_path, "a", encoding="utf-8-sig") as f:
                    for line in lines:
                        if line not in existing_set:
                            f.write(line + "\n")
                            existing_set.add(line)
                            new_added += 1
                self.log(f"[Hotmail] Đã nối thêm {new_added} tài khoản mới vào kho hotmails.txt.", "success")
                msg = f"Đã nối thêm {new_added} tài khoản mới vào kho!"
            else:
                with open(dest_path, "w", encoding="utf-8-sig") as f:
                    for line in lines:
                        f.write(line + "\n")
                self.log(f"[Hotmail] Đã ghi đè kho hotmails.txt với {len(lines)} tài khoản.", "success")
                msg = f"Đã ghi đè kho với {len(lines)} tài khoản!"

            DongVanHotmailProvider.load_from_file("hotmails.txt")
            Smail1sHotmailProvider.load_from_file("hotmails.txt")
            count = self.refresh_hotmail_count()
            self.cb_email_provider.set("📧 Dùng Hotmail Tự Nhập (Kho hotmails.txt) (KHUYÊN DÙNG - Nhận OTP 100%)")
            self.on_email_service_changed()
            self.config["email_service"] = "custom_hotmail"
            messagebox.showinfo("Thành công", f"{msg}\nTổng kho hiện có: {count} Hotmail.", parent=self.root)
        except Exception as e:
            self.log(f"Lỗi nhập file Hotmail: {e}", "error")
            messagebox.showerror("Lỗi", f"Không thể đọc file: {e}", parent=self.root)

    def on_click_refresh_hotmail(self):
        count = self.refresh_hotmail_count()
        DongVanHotmailProvider.load_from_file("hotmails.txt")
        Smail1sHotmailProvider.load_from_file("hotmails.txt")
        self.log(f"[Hotmail] Đã làm mới kho: Hiện có {count} tài khoản.", "info")

    def open_live_file(self):
        self.open_external_file("accounts_live.txt")

    def open_die_file(self):
        self.open_external_file("accounts_die.txt")

    def open_unverified_file(self):
        self.open_external_file("accounts_unverified.txt")

    def check_all_proxyvn_keys(self):
        keys = self.get_proxyvn_keys()
        if not keys:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập ít nhất 1 Proxy.vn Key!")
            return

        self.log(f"[Proxy.vn] Bắt đầu kiểm tra {len(keys)} key...", "info")
        self.lbl_kiot_status.config(text=f"Đang kiểm tra {len(keys)} key Proxy.vn...", fg=AppTheme.INFO)

        def worker():
            live_count = 0
            die_count = 0
            for idx, key in enumerate(keys, start=1):
                client = ProxyVNClient(key)
                res = client.get_current_proxy(force_refresh=True)
                masked_k = self.mask_key(key)
                if res.get("success") and (res.get("http") or res.get("raw_http")):
                    live_count += 1
                    ip = res.get("ip") or res.get("http")
                    masked_ip_val = self.mask_ip(ip)
                    loc = res.get("location", "Vietnam")
                    carrier = f" | Nhà mạng: {res.get('carrier')}" if res.get("carrier") else ""
                    exp = f" | Hạn: {res.get('expiration')}" if res.get("expiration") else ""
                    ttc = res.get("ttc", 0)
                    ttc_str = f" | Đổi IP sau: {ttc}s" if ttc > 0 else ""
                    self.event_queue.put(("log", {
                        "message": f"[Proxy.vn #{idx}] 🟢 LIVE | IP: {masked_ip_val} | Vị trí: {loc}{carrier}{exp}{ttc_str}",
                        "tag": "proxy"
                    }))
                elif res.get("success") or res.get("cooldown") or res.get("expiration"):
                    live_count += 1
                    exp = f" | Hạn: {res.get('expiration')}" if res.get("expiration") else ""
                    ttc = res.get("ttc", 0)
                    ttc_str = f" | Đổi IP sau: {ttc}s" if ttc > 0 else ""
                    self.event_queue.put(("log", {
                        "message": f"[Proxy.vn #{idx}] 🟢 LIVE (Đang chờ đổi IP){exp}{ttc_str}",
                        "tag": "proxy"
                    }))
                else:
                    die_count += 1
                    msg = res.get("message", "Key không tồn tại hoặc hết hạn")
                    self.event_queue.put(("log", {
                        "message": f"[Proxy.vn #{idx}] 🔴 DIE/Lỗi | Key: {masked_k} | Lý do: {msg}",
                        "tag": "error"
                    }))

            summary = f"🟢 Live: {live_count} | 🔴 Die: {die_count}"
            self.event_queue.put(("kiot_status", {"text": summary, "live": live_count}))

        threading.Thread(target=worker, daemon=True).start()

    def check_single_proxyvn_key(self):
        keys = self.get_proxyvn_keys()
        if not keys:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Proxy.vn Key!")
            return
        key = keys[0]
        masked_k = self.mask_key(key)
        self.log(f"[Proxy.vn] Đang kiểm tra Key 1: {masked_k}...", "info")

        def worker():
            client = ProxyVNClient(key)
            res = client.get_current_proxy(force_refresh=True)
            if res.get("success") and (res.get("http") or res.get("raw_http")):
                ip = res.get("ip") or res.get("http")
                masked_ip_val = self.mask_ip(ip)
                loc = res.get("location", "Vietnam")
                carrier = f" | Nhà mạng: {res.get('carrier')}" if res.get("carrier") else ""
                exp = f" | Hạn: {res.get('expiration')}" if res.get("expiration") else ""
                ttc = res.get("ttc", 0)
                ttc_str = f" | Đổi IP sau: {ttc}s" if ttc > 0 else ""
                msg = f"Key 1: 🟢 LIVE | IP: {masked_ip_val} | Vị trí: {loc}{carrier}{exp}{ttc_str}"
                self.event_queue.put(("log", {"message": f"[Proxy.vn] {msg}", "tag": "proxy"}))
                self.event_queue.put(("kiot_status", {"text": f"🟢 Key 1 Live: {masked_ip_val}", "live": 1}))
            elif res.get("success") or res.get("cooldown") or res.get("expiration"):
                exp = f" | Hạn: {res.get('expiration')}" if res.get("expiration") else ""
                ttc = res.get("ttc", 0)
                ttc_str = f" | Đổi IP sau: {ttc}s" if ttc > 0 else ""
                msg = f"Key 1: 🟢 LIVE (Đang chờ đổi IP){exp}{ttc_str}"
                self.event_queue.put(("log", {"message": f"[Proxy.vn] {msg}", "tag": "proxy"}))
                self.event_queue.put(("kiot_status", {"text": f"🟢 Key 1 Live (Chờ {ttc}s)", "live": 1}))
            else:
                msg = res.get("message", "Key không tồn tại hoặc hết hạn")
                self.event_queue.put(("log", {"message": f"[Proxy.vn] Key 1: 🔴 DIE ({msg})", "tag": "error"}))
                self.event_queue.put(("kiot_status", {"text": f"🔴 Key 1 DIE: {msg}", "live": 0}))

        threading.Thread(target=worker, daemon=True).start()

    def rotate_all_proxyvn_keys(self, silent: bool = False):
        keys = self.get_proxyvn_keys()
        if not keys:
            if not silent:
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập ít nhất 1 Proxy.vn Key!")
            return
        self._last_auto_rotate_time = time.time()
        self.log(f"[Proxy.vn] 🔄 Yêu cầu xoay IP cho {len(keys)} key...", "warning")

        def worker():
            for idx, key in enumerate(keys, start=1):
                client = ProxyVNClient(key)
                res = client.get_new_proxy(fallback_current=False)
                p_str = res.get("http") or res.get("raw_http")
                if res.get("success") and p_str and res.get("rotated"):
                    masked_ip_val = self.mask_ip(res.get("ip") or p_str)
                    loc = res.get("location", "Vietnam")
                    carrier = f" | {res.get('carrier')}" if res.get("carrier") else ""
                    self.event_queue.put(("log", {
                        "message": f"[Proxy.vn #{idx}] 🔄 Đã đổi sang IP MỚI: {masked_ip_val} ({loc}{carrier})",
                        "tag": "proxy"
                    }))
                else:
                    ttc = res.get("ttc", 0)
                    ttc_msg = f" (Chờ thêm {ttc}s)" if ttc else ""
                    self.event_queue.put(("log", {
                        "message": f"[Proxy.vn #{idx}] ⏳ Chưa thể xoay: {res.get('message', 'Đang trong thời gian chờ')}{ttc_msg}",
                        "tag": "warning"
                    }))

        threading.Thread(target=worker, daemon=True).start()

    def rotate_single_proxyvn_key(self):
        keys = self.get_proxyvn_keys()
        if not keys:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Proxy.vn Key!")
            return
        key = keys[0]
        self.log("[Proxy.vn] Yêu cầu xoay IP Key 1...", "warning")

        def worker():
            client = ProxyVNClient(key)
            res = client.get_new_proxy(fallback_current=False)
            p_str = res.get("http") or res.get("raw_http")
            if res.get("success") and p_str and res.get("rotated"):
                masked_ip_val = self.mask_ip(res.get("ip") or p_str)
                loc = res.get("location", "Vietnam")
                carrier = f" | {res.get('carrier')}" if res.get("carrier") else ""
                self.event_queue.put(("log", {
                    "message": f"[Proxy.vn Key 1] 🔄 Đã đổi sang IP MỚI: {masked_ip_val} ({loc}{carrier})",
                    "tag": "proxy"
                }))
            else:
                ttc = res.get("ttc", 0)
                ttc_msg = f" (Chờ thêm {ttc}s)" if ttc else ""
                self.event_queue.put(("log", {
                    "message": f"[Proxy.vn Key 1] ⏳ Chưa thể xoay: {res.get('message', 'Đang trong thời gian chờ')}{ttc_msg}",
                    "tag": "warning"
                }))

        threading.Thread(target=worker, daemon=True).start()

    def check_all_kiotproxy_keys(self):
        prov = self.get_selected_proxy_provider()
        if prov == "proxysocks5":
            keys = self.get_proxysocks5_keys()
            provider_tag = "ProxySocks5"
        elif prov == "mproxy":
            self.check_all_mproxy_keys()
            return
        elif prov == "proxyvn":
            self.check_all_proxyvn_keys()
            return
        elif prov in ("kiotproxy", "kiotproxy_current"):
            keys = self.get_kiotproxy_keys()
            provider_tag = "KiotProxy"
        else:
            messagebox.showinfo("Thông báo", "Vui lòng chọn loại Proxy là 'ProxySocks5.vn' hoặc 'KiotProxy' để kiểm tra Key!")
            return

        if not keys:
            messagebox.showwarning("Cảnh báo", f"Vui lòng nhập ít nhất 1 {provider_tag} Key!")
            return

        self.log(f"[{provider_tag}] Bắt đầu kiểm tra {len(keys)} key...", "info")
        self.lbl_kiot_status.config(text=f"Đang kiểm tra {len(keys)} key {provider_tag}...", fg=AppTheme.INFO)

        def worker():
            live_count = 0
            die_count = 0
            def _check_one(item):
                idx, key = item
                if prov == "proxysocks5":
                    client = ProxySocks5Client(key, user_token=getattr(self, "proxysocks5_user_token", None))
                    res = client.get_current_proxy(force_refresh=True)
                    if not res.get("success"):
                        res = client.get_new_proxy(fallback_current=True)
                else:
                    client = KiotProxyClient(key)
                    res = client.get_current_proxy()
                    if not res.get("success") and ("ch?a" in str(res.get("message", "")).lower() or "kh?ng t?m th?y proxy ?ang ???c s? d?ng" in str(res.get("message", "")).lower()):
                        res = client.get_new_proxy()
                return idx, key, res

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, len(keys))) as ex:
                results = list(ex.map(_check_one, enumerate(keys, start=1)))

            for idx, key, res in sorted(results, key=lambda x: x[0]):
                masked_k = self.mask_key(key)
                if res.get("success") and (res.get("http") or res.get("socks5")):
                    live_count += 1
                    ip = res.get("ip") or res.get("http")
                    masked_ip_val = self.mask_ip(ip)
                    loc = res.get("location", "VN")
                    ttc = res.get("ttc", res.get("next_change", 0))
                    host_info = f" | Host: {res.get('host')}:{res.get('port_http')}" if res.get('host') else ""
                    self.event_queue.put(("log", {
                        "message": f"[{provider_tag} #{idx}] 🟢 LIVE | IP: {masked_ip_val} | Vị trí: {loc}{host_info} | Đổi IP sau: {ttc}s",
                        "tag": "proxy"
                    }))
                else:
                    die_count += 1
                    msg = res.get("message", "Không có IP hoặc Key hết hạn")
                    self.event_queue.put(("log", {
                        "message": f"[{provider_tag} #{idx}] 🔴 DIE | Key: {masked_k} | Lý do: {msg}",
                        "tag": "error"
                    }))

            summary = f"🟢 Live: {live_count} | 🔴 Die: {die_count}"
            self.event_queue.put(("kiot_status", {"text": summary, "live": live_count}))

        threading.Thread(target=worker, daemon=True).start()

    def check_single_kiotproxy_key(self):
        prov = self.get_selected_proxy_provider()
        if prov == "proxyvn":
            self.check_single_proxyvn_key()
            return
        if prov == "proxysocks5":
            keys = self.get_proxysocks5_keys()
            provider_tag = "ProxySocks5"
        elif prov in ("kiotproxy", "kiotproxy_current"):
            keys = self.get_kiotproxy_keys()
            provider_tag = "KiotProxy"
        else:
            messagebox.showinfo("Thông báo", "Vui lòng chọn loại Proxy là 'ProxySocks5.vn' hoặc 'KiotProxy' để kiểm tra Key!")
            return

        if not keys:
            messagebox.showwarning("Cảnh báo", f"Vui lòng nhập {provider_tag} Key!")
            return
        key = keys[0]
        masked_k = self.mask_key(key)
        self.log(f"[{provider_tag}] Đang kiểm tra Key 1: {masked_k}...", "info")

        def worker():
            if prov == "proxysocks5":
                client = ProxySocks5Client(key, user_token=getattr(self, "proxysocks5_user_token", None))
                res = client.get_current_proxy(force_refresh=True)
                if not res.get("success"):
                    res = client.get_new_proxy(fallback_current=True)
            else:
                client = KiotProxyClient(key)
                res = client.get_current_proxy()

            if res.get("success") and (res.get("http") or res.get("socks5")):
                ip = res.get("ip") or res.get("http")
                masked_ip_val = self.mask_ip(ip)
                loc = res.get("location", "VN")
                ttc = res.get("ttc", res.get("next_change", 0))
                msg = f"Key 1: 🟢 LIVE | IP: {masked_ip_val} | Vị trí: {loc} | TTC: {ttc}s"
                self.event_queue.put(("log", {"message": f"[{provider_tag}] {msg}", "tag": "proxy"}))
                self.event_queue.put(("kiot_status", {"text": f"🟢 Key 1 Live: {masked_ip_val}", "live": 1}))
            else:
                err = res.get("message", "Key lỗi hoặc hết hạn")
                self.event_queue.put(("log", {"message": f"[{provider_tag}] Key 1: 🔴 DIE ({err})", "tag": "error"}))
                self.event_queue.put(("kiot_status", {"text": f"🔴 Key 1 DIE: {err}", "live": 0}))

        threading.Thread(target=worker, daemon=True).start()

    def rotate_all_kiotproxy_keys(self, silent: bool = False):
        prov = self.get_selected_proxy_provider()
        if prov == "proxysocks5":
            keys = self.get_proxysocks5_keys()
            provider_tag = "ProxySocks5"
        elif prov == "mproxy":
            self.rotate_all_mproxy_keys(silent=silent)
            return
        elif prov == "proxyvn":
            self.rotate_all_proxyvn_keys(silent=silent)
            return
        elif prov in ("kiotproxy", "kiotproxy_current"):
            keys = self.get_kiotproxy_keys()
            provider_tag = "KiotProxy"
        else:
            if not silent:
                messagebox.showinfo("Thông báo", "Vui lòng chọn loại Proxy là 'ProxySocks5.vn', 'KiotProxy' hoặc 'mProxy.vn' để xoay IP!")
            return

        if not keys:
            if not silent:
                messagebox.showwarning("Cảnh báo", f"Vui lòng nhập ít nhất 1 {provider_tag} Key!")
            return
        self._last_auto_rotate_time = time.time()
        self.log(f"[{provider_tag}] 🔄 Yêu cầu xoay IP cho {len(keys)} key...", "warning")

        def worker():
            def _rot_one(item):
                idx, key = item
                if prov == "proxysocks5":
                    client = ProxySocks5Client(key, user_token=getattr(self, "proxysocks5_user_token", None))
                    res = client.get_new_proxy(fallback_current=False)
                elif prov == "kiotproxy_current":
                    client = KiotProxyClient(key)
                    res = client.get_current_proxy(force_refresh=True)
                else:
                    client = KiotProxyClient(key)
                    res = client.get_new_proxy()
                return idx, key, res

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, len(keys))) as ex:
                results = list(ex.map(_rot_one, enumerate(keys, start=1)))

            for idx, key, res in sorted(results, key=lambda x: x[0]):
                p_str = res.get("http") or res.get("socks5")
                if res.get("success") and p_str:
                    masked_ip_val = self.mask_ip(res.get("ip") or p_str)
                    self.event_queue.put(("log", {
                        "message": f"[{provider_tag} #{idx}] 🔄 Đã đổi sang IP MỚI: {masked_ip_val} ({res.get('location', 'VN')})",
                        "tag": "proxy"
                    }))
                else:
                    self.event_queue.put(("log", {
                        "message": f"[{provider_tag} #{idx}] ⏳ Chưa thể xoay: {res.get('message', 'Đang trong thời gian chờ')}",
                        "tag": "warning"
                    }))

        threading.Thread(target=worker, daemon=True).start()

    def on_proxy_provider_changed(self, event=None):
        new_prov = self.get_selected_proxy_provider()
        old_prov = getattr(self, "_prev_proxy_provider", None)

        if old_prov and old_prov != new_prov and hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
            if not getattr(self, "keys_masked", False) or old_prov == "proxy_list":
                raw = self.txt_proxy_keys.get("1.0", tk.END)
                lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith("#")]
                if lines and not any("*" in l for l in lines):
                    if old_prov == "proxysocks5":
                        self._raw_proxysocks5_keys = lines
                        self.config["proxysocks5_keys"] = lines
                    elif old_prov == "mproxy":
                        self._raw_mproxy_keys = lines
                        self.config["mproxy_keys"] = lines
                    elif old_prov == "proxyvn":
                        self._raw_proxyvn_keys = lines
                        self.config["proxyvn_keys"] = lines
                        if lines and len(lines[0]) >= 25 and ("-" in lines[0] or "_" in lines[0]):
                            self.mproxy_token = lines[0]
                            self.config["mproxy_token"] = lines[0]
                    elif old_prov in ("kiotproxy", "kiotproxy_current"):
                        self._raw_kiot_keys = lines
                        self.config["kiotproxy_keys"] = lines
                    elif old_prov == "proxy_list":
                        if len(lines) <= 200:
                            self.config["proxy_list"] = lines
                        else:
                            self.config["proxy_list"] = lines[:200]

        self._prev_proxy_provider = new_prov
        self.config["proxy_provider"] = new_prov

        if new_prov == "proxysocks5":
            cnt = len(self.get_proxysocks5_keys())
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=" 🌐 2. Cấu hình Proxy (ProxySocks5.vn) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text=f"Danh sách ProxySocks5 tokenProxy Key ({cnt} key):")
            self.lbl_kiot_status.config(text=f"🔑 Chế độ ProxySocks5.vn ({cnt} Key khả dụng)", fg=AppTheme.INFO)
            self.log(f"[Proxy] 🔑 Đã chọn: ProxySocks5.vn (1 Luồng 1 Token Key xoay riêng). Hiện có {cnt} key. Tự động đổi IP qua API /changeIp và refresh qua /refresh.", "info")
        elif new_prov in ("free_proxy_live", "free_proxy_cached", "free_proxy"):
            from core.proxy_manager import FreeProxyManager
            total_srcs = FreeProxyManager.get_total_sources_count()
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=" 🌐 2. Cấu hình Proxy (Proxy Free Tự Động) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text=f"Danh sách Proxy / Nguồn (Tự động cào từ {total_srcs} nguồn):")
            if new_prov in ("free_proxy", "free_proxy_live"):
                fm = FreeProxyManager()
                fm.purge_all_cache()
                self.lbl_kiot_status.config(text=f"🌐 Proxy Free Cào Mới ({total_srcs} nguồn online)", fg=AppTheme.INFO)
                self.log(f"[Proxy] 🌐 Đã chọn: Proxy Free Cào Mới 100% từ mạng (Đã xóa sạch toàn bộ cache RAM & đĩa). Mỗi lần chạy, tool sẽ cào mới từ {total_srcs} nguồn online, lọc sạch trùng lặp và kiểm định tạo phiên Facebook trước khi reg (Tuyệt đối không lấy proxy cũ).", "info")
            else:
                self.lbl_kiot_status.config(text=f"🎲 Proxy Free Kho Cache ({total_srcs} nguồn)", fg=AppTheme.INFO)
                self.log(f"[Proxy] 🎲 Đã chọn: Proxy Free Kho Sẵn Có (Cache). Tool sẽ bốc từ kho ứng viên có sẵn trong RAM/đĩa và kiểm định kết nối Facebook trước khi reg (Chạy 0ms không cào lại mạng).", "info")
        elif new_prov == "none":
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=" 🌐 2. Cấu hình Proxy (Mạng Trực Tiếp) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text="Mạng Trực Tiếp (Direct IP - Không dùng Proxy):")
            self.lbl_kiot_status.config(text="⚡ Chế độ Không dùng Proxy (Mạng Trực Tiếp Direct)", fg=AppTheme.WARNING)
            self.log("[Proxy] Đã chọn Không dùng Proxy (Direct Connection). Các luồng chạy trực tiếp qua IP máy.", "warning")
        elif new_prov == "proxy_list":
            p_file = self.get_proxy_file_path()
            bname = os.path.basename(p_file)
            p_list = self.get_file_proxies()
            cnt = len(p_list)
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=f" 📁 2. Cấu hình Proxy (File: {bname}) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text=f"Danh sách Proxy từ '{bname}' ({cnt} proxy):")
            self.lbl_kiot_status.config(text=f"📁 File '{bname}': {cnt} proxy khả dụng", fg=AppTheme.INFO)
            self.log(f"[Proxy List] 📁 Đã chọn chế độ Proxy từ file: {p_file} ({cnt} proxy).", "info")
        elif new_prov == "proxyvn":
            cnt = len(self.get_proxyvn_keys())
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=" 🔄 2. Cấu hình Proxy (Proxy.vn Đa Key) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text=f"Danh sách Proxy.vn Key xoay ({cnt} key):")
            self.lbl_kiot_status.config(text=f"🔄 Chế độ Proxy.vn ({cnt} Key khả dụng)", fg=AppTheme.INFO)
            self.log(f"[Proxy] 🔄 Đã chọn: Proxy.vn (proxyxoay.shop). Hiện có {cnt} key xoay.", "info")
        elif new_prov == "mproxy":
            cnt = len(self.get_mproxy_keys())
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=" 📱 2. Cấu hình Proxy (mProxy.vn 4G/5G) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text=f"Token API / Danh sách Key 4G mProxy ({cnt} key):")
            self.lbl_kiot_status.config(text=f"📱 Chế độ mProxy.vn ({cnt} Key 4G khả dụng)", fg=AppTheme.INFO)
            self.log(f"[Proxy] 📱 Đã chọn: mProxy.vn (Proxy 4G/5G SIM vật lý VN). Hiện có {cnt} key. Tự động đổi IP qua API /resetIp.", "info")
        else: # kiotproxy
            cnt = len(self.get_kiotproxy_keys())
            if hasattr(self, "card_proxy"):
                self.card_proxy.config(text=" 🌐 2. Cấu hình Proxy (KiotProxy Đa Key) ")
            if hasattr(self, "lbl_keys_title"):
                self.lbl_keys_title.config(text=f"Danh sách KiotProxy Key ({cnt} key):")
            self.lbl_kiot_status.config(text=f"🔑 Chế độ KiotProxy ({cnt} Key khả dụng)", fg=AppTheme.INFO)

        self._render_proxy_keys_display()

        # Dynamic Toolbar Rows - Chỉ hiển thị hàng nút của provider đang chọn
        for r_name in ("btn_proxy_row1", "btn_proxy_row2", "btn_proxy_row3", "btn_proxy_row4", "btn_proxy_row5", "btn_proxy_row6", "btn_proxy_row7"):
            r = getattr(self, r_name, None)
            if r and r.winfo_exists():
                r.pack_forget()

        anchor = getattr(self, "lbl_kiot_status", None)
        before_kw = {"before": anchor} if (anchor and anchor.winfo_manager() == "pack") else {}

        if new_prov == "proxy_list":
            if hasattr(self, "lbl_keys_row") and self.lbl_keys_row.winfo_exists():
                self.lbl_keys_row.pack_forget()
            if hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
                self.txt_proxy_keys.pack_forget()
            if hasattr(self, "lbl_proxy_filepath_title") and self.lbl_proxy_filepath_title.winfo_exists():
                self.lbl_proxy_filepath_title.config(text="📁 File Proxy:")
            if hasattr(self, "lbl_file_proxy_desc") and self.lbl_file_proxy_desc.winfo_exists():
                self.lbl_file_proxy_desc.config(text="🎲 Cơ chế: Mỗi luồng tự động bốc NGẪU NHIÊN 1 proxy trong file này để reg (Collision-Free)\n📝 Định dạng hỗ trợ: ip:port hoặc ip:port:user:pass (mỗi dòng 1 proxy, tự lọc tag)")
            if hasattr(self, "panel_proxy_file") and self.panel_proxy_file.winfo_exists():
                self.panel_proxy_file.pack(fill=tk.X, pady=2, **before_kw)
            if hasattr(self, "btn_proxy_row5") and self.btn_proxy_row5.winfo_exists():
                self.btn_proxy_row5.pack(fill=tk.X, pady=2, **before_kw)
            self.update_file_proxy_panel()
        elif new_prov in ("free_proxy", "free_proxy_live", "free_proxy_cached"):
            if hasattr(self, "lbl_keys_row") and self.lbl_keys_row.winfo_exists():
                self.lbl_keys_row.pack_forget()
            if hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
                self.txt_proxy_keys.pack_forget()
            if hasattr(self, "lbl_proxy_filepath_title") and self.lbl_proxy_filepath_title.winfo_exists():
                self.lbl_proxy_filepath_title.config(text="📁 File Lưu Proxy LIVE:")
            if hasattr(self, "lbl_file_proxy_desc") and self.lbl_file_proxy_desc.winfo_exists():
                self.lbl_file_proxy_desc.config(text="💾 Tự động lưu 100% Proxy LIVE Facebook cào được vào file này (Định dạng chuẩn: ip:port)\n🌐 Hơn 11,018 nguồn online cào song song, tự động lọc sạch trùng lặp và loại bỏ proxy chết.")
            if hasattr(self, "panel_proxy_file") and self.panel_proxy_file.winfo_exists():
                self.panel_proxy_file.pack(fill=tk.X, pady=2, **before_kw)
            if hasattr(self, "btn_proxy_row3") and self.btn_proxy_row3.winfo_exists():
                self.btn_proxy_row3.pack(fill=tk.X, pady=(2, 4), **before_kw)
            self.update_file_proxy_panel()
        else:
            if hasattr(self, "panel_proxy_file") and self.panel_proxy_file.winfo_exists():
                self.panel_proxy_file.pack_forget()
            if hasattr(self, "lbl_keys_row") and self.lbl_keys_row.winfo_exists():
                self.lbl_keys_row.pack(fill=tk.X, pady=(4, 2), **before_kw)
            if hasattr(self, "txt_proxy_keys") and self.txt_proxy_keys.winfo_exists():
                self.txt_proxy_keys.pack(fill=tk.X, pady=2, **before_kw)

        if new_prov in ("kiotproxy", "kiotproxy_current"):
            if hasattr(self, "btn_proxy_row1") and self.btn_proxy_row1.winfo_exists():
                self.btn_proxy_row1.pack(fill=tk.X, pady=(4, 2), **before_kw)
            if hasattr(self, "btn_proxy_row2") and self.btn_proxy_row2.winfo_exists():
                self.btn_proxy_row2.pack(fill=tk.X, pady=(2, 4), **before_kw)
        elif new_prov == "proxysocks5":
            if hasattr(self, "btn_proxy_row4") and self.btn_proxy_row4.winfo_exists():
                self.btn_proxy_row4.pack(fill=tk.X, pady=(2, 4), **before_kw)
        elif new_prov == "mproxy":
            if hasattr(self, "btn_proxy_row6") and self.btn_proxy_row6.winfo_exists():
                self.btn_proxy_row6.pack(fill=tk.X, pady=(2, 4), **before_kw)
        elif new_prov == "proxyvn":
            if hasattr(self, "btn_proxy_row7") and self.btn_proxy_row7.winfo_exists():
                self.btn_proxy_row7.pack(fill=tk.X, pady=(2, 4), **before_kw)

    def fetch_fresh_free_proxies(self):
        # FreeProxyManager imported at top level
        total_srcs = FreeProxyManager.get_total_sources_count()
        p_file = self.get_proxy_file_path()
        abs_target = p_file if os.path.isabs(p_file) else os.path.join(os.path.dirname(__file__), p_file)
        try:
            FreeProxyManager().auto_save_file = abs_target
        except Exception:
            pass
        self.lbl_kiot_status.config(text=f"🌐 Đang cào & test proxy tươi từ {total_srcs} nguồn online...", fg=AppTheme.INFO)
        self.log(f"[Proxy Free] 🌐 Bắt đầu tải mới 100% từ {total_srcs} nguồn uy tín trực tuyến (xóa cache cũ, không dùng proxy có sẵn)...", "info")
        def worker():
            # FreeProxyManager imported at top level
            fm = FreeProxyManager()
            fm.purge_all_cache()
            last_rep = [0]
            def on_p(c, t, p_str, lat):
                if p_str:
                    try:
                        self.append_live_proxies_to_file([p_str])
                    except Exception:
                        pass
                if c > last_rep[0] and (c % 2 == 0 or c == t or c <= 3):
                    last_rep[0] = c
                    self.event_queue.put(("log", {
                        "message": f"[Proxy Free] 🔍 Đã tìm thấy Proxy LIVE FB: {p_str} ({lat}s) ➔ Đã tự động lưu vào file!",
                        "tag": "success"
                    }))
            live = fm.refresh_live_proxies(target_count=30, callback=on_p, force_fresh=True)
            if live:
                self.event_queue.put(("log", {
                    "message": f"[Proxy Free] 🎉 Đã cào và lọc thành công {len(live)} proxy free LIVE sẵn sàng!",
                    "tag": "success"
                }))
                self.event_queue.put(("kiot_status", {"text": f"🌐 Proxy Free: {len(live)} live sẵn sàng", "live": 1}))
                added = self.append_live_proxies_to_file(live)
                p_file = self.get_proxy_file_path()
                bname = os.path.basename(p_file) if p_file else "file proxy"
                if added > 0:
                    self.event_queue.put(("log", {
                        "message": f"[Proxy Free] 💾 Đã tự động cập nhật {added} proxy LIVE vào '{bname}'!",
                        "tag": "success"
                    }))
                    self.safe_ui_call(self.update_file_proxy_panel)
            else:
                self.event_queue.put(("log", {
                    "message": "[Proxy Free] ⚠️ Không tìm thấy proxy live từ các nguồn. Vui lòng thử lại.",
                    "tag": "warning"
                }))
                self.event_queue.put(("kiot_status", {"text": "🌐 Proxy Free: 0 live", "live": 0}))
        threading.Thread(target=worker, daemon=True).start()

    def rotate_single_kiotproxy_key(self):
        prov = self.get_selected_proxy_provider()
        if prov == "proxyvn":
            self.rotate_single_proxyvn_key()
            return
        if prov == "proxysocks5":
            keys = self.get_proxysocks5_keys()
            provider_tag = "ProxySocks5"
        elif prov in ("kiotproxy", "kiotproxy_current"):
            keys = self.get_kiotproxy_keys()
            provider_tag = "KiotProxy"
        else:
            messagebox.showinfo("Thông báo", "Vui lòng chọn loại Proxy là 'ProxySocks5.vn' hoặc 'KiotProxy' để xoay IP!")
            return

        if not keys:
            messagebox.showwarning("Cảnh báo", f"Vui lòng nhập {provider_tag} Key!")
            return
        key = keys[0]
        self.log(f"[{provider_tag}] Yêu cầu xoay IP Key 1...", "warning")

        def worker():
            if prov == "proxysocks5":
                client = ProxySocks5Client(key, user_token=getattr(self, "proxysocks5_user_token", None))
                res = client.get_new_proxy(fallback_current=False)
            elif prov == "kiotproxy_current":
                client = KiotProxyClient(key)
                res = client.get_current_proxy(force_refresh=True)
            else:
                client = KiotProxyClient(key)
                res = client.get_new_proxy()

            p_str = res.get("http") or res.get("socks5")
            if res.get("success") and p_str:
                masked_ip_val = self.mask_ip(res.get("ip") or p_str)
                self.event_queue.put(("log", {
                    "message": f"[{provider_tag} Key 1] 🔄 IP MỚI: {masked_ip_val}",
                    "tag": "proxy"
                }))
            else:
                self.event_queue.put(("log", {
                    "message": f"[{provider_tag} Key 1] ⏳ Xoay thất bại: {res.get('message', 'Hết hạn hoặc chưa đủ TTC')}",
                    "tag": "warning"
                }))

        threading.Thread(target=worker, daemon=True).start()

    def open_proxysocks5_manager_dialog(self):
        """Hộp thoại quản lý toàn diện ProxySocks5.vn: Nạp keys từ Order ID, mua proxy mới, gia hạn."""
        dlg = tk.Toplevel(self.root)
        dlg.title("📦 Quản Lý & Tích Hợp ProxySocks5.vn")
        dlg.geometry("560x520")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        header_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        header_frame.pack(fill=tk.X, padx=16, pady=(12, 6))
        tk.Label(
            header_frame,
            text="📦 Quản Lý Dịch Vụ ProxySocks5.vn",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.ACCENT
        ).pack(anchor="w")
        tk.Label(
            header_frame,
            text="Tích hợp API mua proxy, nạp danh sách key từ Order ID, đổi IP và gia hạn",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED
        ).pack(anchor="w")

        tok_frame = tk.LabelFrame(
            dlg,
            text=" 🔑 Tài Khoản UserToken ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        tok_frame.pack(fill=tk.X, padx=16, pady=6)

        cur_tok = getattr(self, "proxysocks5_user_token", "QosKHIjPqRnaoQgR6qs4UEkrC6EwXx")
        ent_tok = tk.Entry(
            tok_frame,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            bd=1,
            relief="solid"
        )
        ent_tok.insert(0, cur_tok)
        ent_tok.pack(fill=tk.X, pady=2)

        def save_token():
            val = ent_tok.get().strip()
            if val:
                self.proxysocks5_user_token = val
                self.config["proxysocks5_user_token"] = val
                self.save_config(show_toast=False)
                messagebox.showinfo("Thành công", "Đã lưu UserToken mới!")

        btn_save_tok = tk.Button(
            tok_frame,
            text="💾 Lưu UserToken",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            bd=1,
            relief="solid",
            command=save_token
        )
        btn_save_tok.pack(anchor="e", pady=(4, 0))

        order_frame = tk.LabelFrame(
            dlg,
            text=" 📥 Nạp Token Key từ Order ID ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        order_frame.pack(fill=tk.X, padx=16, pady=6)

        row_o = tk.Frame(order_frame, bg=AppTheme.BG_CARD)
        row_o.pack(fill=tk.X, pady=2)
        tk.Label(row_o, text="Mã Order ID:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        ent_order = tk.Entry(
            row_o,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            bd=1,
            relief="solid"
        )
        ent_order.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        def fetch_order_keys():
            u_tok = ent_tok.get().strip()
            o_id = ent_order.get().strip()
            if not u_tok or not o_id:
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập UserToken và Order ID!")
                return
            save_token()
            lbl_res.config(text="Đang kết nối API ProxySocks5 để lấy danh sách key...", fg=AppTheme.INFO)
            def worker():
                res_list = ProxySocks5Client.get_proxies_by_order(u_tok, o_id)
                if res_list:
                    new_tokens = [p["token"] for p in res_list if p.get("token")]
                    cur_keys = getattr(self, "_raw_proxysocks5_keys", [])
                    merged = list(dict.fromkeys(cur_keys + new_tokens))
                    self._raw_proxysocks5_keys = merged
                    self.config["proxysocks5_keys"] = merged
                    self.event_queue.put(("log", {
                        "message": f"[ProxySocks5] 🎉 Đã nạp thành công {len(new_tokens)} key từ Order {o_id}!",
                        "tag": "success"
                    }))
                    self.event_queue.put(("psocks5_order_done", {
                        "count": len(new_tokens),
                        "total": len(merged),
                        "order": o_id
                    }))
                else:
                    self.event_queue.put(("log", {
                        "message": f"[ProxySocks5] ⚠️ Không tìm thấy proxy nào trong Order {o_id} hoặc Order chưa kích hoạt.",
                        "tag": "warning"
                    }))
                    self.event_queue.put(("psocks5_order_fail", {"order": o_id}))
            threading.Thread(target=worker, daemon=True).start()

        btn_fetch = tk.Button(
            order_frame,
            text="🚀 Tải Danh Sách Token Key & Nạp Vào Tool",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            bd=1,
            relief="solid",
            command=fetch_order_keys
        )
        btn_fetch.pack(fill=tk.X, pady=(4, 2))

        buy_frame = tk.LabelFrame(
            dlg,
            text=" 🛒 Mua Proxy Mới (VN001) ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        buy_frame.pack(fill=tk.X, padx=16, pady=6)

        row_b = tk.Frame(buy_frame, bg=AppTheme.BG_CARD)
        row_b.pack(fill=tk.X, pady=2)
        tk.Label(row_b, text="Số lượng:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        spn_qty = tk.Spinbox(row_b, from_=1, to=50, width=5, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN)
        spn_qty.delete(0, tk.END)
        spn_qty.insert(0, "1")
        spn_qty.pack(side=tk.LEFT, padx=(4, 16))

        tk.Label(row_b, text="Số ngày:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        spn_days = tk.Spinbox(row_b, from_=1, to=30, width=5, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN)
        spn_days.delete(0, tk.END)
        spn_days.insert(0, "1")
        spn_days.pack(side=tk.LEFT, padx=4)

        def buy_action():
            u_tok = ent_tok.get().strip()
            if not u_tok:
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập UserToken!")
                return
            qty = int(spn_qty.get())
            days = int(spn_days.get())
            lbl_res.config(text=f"Đang gửi yêu cầu mua {qty} proxy ({days} ngày)...", fg=AppTheme.INFO)
            def worker():
                res = ProxySocks5Client.buy_proxy(u_tok, product_code="VN001", quantity=qty, day=days)
                if res.get("status") == 200:
                    data = res.get("data", {})
                    order_id = data.get("orderId")
                    proxies = data.get("proxies") or []
                    new_tokens = [p.get("token_key") or p.get("token") for p in proxies if (p.get("token_key") or p.get("token"))]
                    if new_tokens:
                        cur_keys = getattr(self, "_raw_proxysocks5_keys", [])
                        merged = list(dict.fromkeys(cur_keys + new_tokens))
                        self._raw_proxysocks5_keys = merged
                        self.config["proxysocks5_keys"] = merged
                    self.event_queue.put(("log", {
                        "message": f"[ProxySocks5] 🎉 Mua thành công! Order: {order_id} ({len(new_tokens)} proxy nạp vào tool)",
                        "tag": "success"
                    }))
                    self.event_queue.put(("psocks5_buy_done", {"order": order_id, "count": len(new_tokens)}))
                else:
                    msg = res.get("message", "Lỗi mua proxy")
                    self.event_queue.put(("log", {
                        "message": f"[ProxySocks5] ⚠️ Mua thất bại: {msg}",
                        "tag": "warning"
                    }))
                    self.event_queue.put(("psocks5_buy_fail", {"msg": msg}))
            threading.Thread(target=worker, daemon=True).start()

        btn_buy = tk.Button(
            buy_frame,
            text="🛒 Mua Ngay & Tự Động Nạp",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            bd=1,
            relief="solid",
            command=buy_action
        )
        btn_buy.pack(fill=tk.X, pady=(4, 2))

        lbl_res = tk.Label(
            dlg,
            text="Nhập Order ID hoặc bấm Mua để nạp key tự động vào phần mềm",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED
        )
        lbl_res.pack(anchor="w", padx=16, pady=8)

    def get_auto_rotate_interval_seconds(self) -> int:
        val = getattr(self, "cb_auto_rotate_interval", None)
        text_val = val.get().strip() if val else str(self.config.get("auto_rotate_interval", "60s (1 phút)"))
        m_s = re.search(r"(\d+)\s*s", text_val, re.I)
        if m_s:
            try:
                return max(10, int(m_s.group(1)))
            except Exception:
                pass
        m_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:phút|min)", text_val, re.I)
        if m_m:
            try:
                return max(10, int(float(m_m.group(1)) * 60))
            except Exception:
                pass
        return 60

    def on_auto_rotate_toggled(self):
        enabled = bool(self.var_auto_rotate.get())
        self.config["auto_rotate_proxy"] = enabled
        sec = self.get_auto_rotate_interval_seconds()
        min_label = f"{sec}s ({sec // 60} phút)" if sec >= 60 else f"{sec}s"
        if enabled:
            self.log(f"[Auto-Rotate] ⏱️ ĐÃ BẬT tự động xoay IP định kỳ mỗi {min_label}. Hệ thống sẽ tự động gửi lệnh đổi IP mới theo chu kỳ.", "info")
            self._ensure_auto_rotate_daemon_running()
        else:
            self.log("[Auto-Rotate] ⏹️ ĐÃ TẮT tự động xoay IP định kỳ. Proxy sẽ xoay theo từng nick như bình thường.", "info")
        self.save_config(show_toast=False)

    def on_auto_rotate_interval_changed(self):
        val = self.cb_auto_rotate_interval.get().strip()
        self.config["auto_rotate_interval"] = val
        sec = self.get_auto_rotate_interval_seconds()
        min_label = f"{sec}s ({sec // 60} phút)" if sec >= 60 else f"{sec}s"
        if getattr(self, "var_auto_rotate", None) and self.var_auto_rotate.get():
            self.log(f"[Auto-Rotate] ⏱️ Đã đổi chu kỳ tự động xoay IP sang: {min_label}", "info")
        self.save_config(show_toast=False)

    def _sync_alloc_mode_ui(self, mode: str):
        is_ded = (mode == "dedicated")
        if hasattr(self, "var_proxy_mode_dedicated"):
            self.var_proxy_mode_dedicated.set(is_ded)
        if hasattr(self, "var_proxy_mode_shared"):
            self.var_proxy_mode_shared.set(not is_ded)
        if hasattr(self, "chk_proxy_mode_dedicated"):
            self.chk_proxy_mode_dedicated.config(fg=AppTheme.SUCCESS if is_ded else AppTheme.TEXT_MUTED)
        if hasattr(self, "chk_proxy_mode_shared"):
            self.chk_proxy_mode_shared.config(fg=AppTheme.ACCENT if not is_ded else AppTheme.TEXT_MUTED)
        if hasattr(self, "chk_dash_mode_dedicated"):
            self.chk_dash_mode_dedicated.config(fg=AppTheme.SUCCESS if is_ded else AppTheme.TEXT_MUTED)
        if hasattr(self, "chk_dash_mode_shared"):
            self.chk_dash_mode_shared.config(fg=AppTheme.ACCENT if not is_ded else AppTheme.TEXT_MUTED)

    def _on_proxy_mode_dedicated_toggled(self):
        val = bool(self.var_proxy_mode_dedicated.get()) if hasattr(self, "var_proxy_mode_dedicated") else True
        mode = "dedicated" if val else "shared"
        self.config["proxy_alloc_mode"] = mode
        self._sync_alloc_mode_ui(mode)
        if mode == "dedicated":
            self.log("[Proxy] 🔒 Đã chọn Chế độ Mặc định: Mỗi 1 luồng chỉ 1 IP riêng biệt (Đảm bảo an toàn, chống Checkpoint 282).", "info")
        else:
            self.log("[Proxy] ⚡ Đã chọn Chế độ: Chia đều IP theo số luồng (VD: 30 luồng chia đều cho 6 IP / Key).", "info")
        self.save_config(show_toast=False)

    def _on_proxy_mode_shared_toggled(self):
        val = bool(self.var_proxy_mode_shared.get()) if hasattr(self, "var_proxy_mode_shared") else True
        mode = "shared" if val else "dedicated"
        self.config["proxy_alloc_mode"] = mode
        self._sync_alloc_mode_ui(mode)
        if mode == "shared":
            self.log("[Proxy] ⚡ Đã chọn Chế độ: Chia đều IP theo số luồng (VD: 30 luồng chia đều cho 6 IP / Key).", "info")
        else:
            self.log("[Proxy] 🔒 Đã chọn Chế độ Mặc định: Mỗi 1 luồng chỉ 1 IP riêng biệt (Đảm bảo an toàn, chống Checkpoint 282).", "info")
        self.save_config(show_toast=False)
    def get_proxy_alloc_mode(self) -> str:
        try:
            if hasattr(self, "var_proxy_mode_shared") and bool(self.var_proxy_mode_shared.get()):
                return "shared"
            if hasattr(self, "var_proxy_mode_dedicated") and bool(self.var_proxy_mode_dedicated.get()):
                return "dedicated"
        except Exception:
            pass
        return str(self.config.get("proxy_alloc_mode", "dedicated")).lower().strip() 

    def _ensure_auto_rotate_daemon_running(self):
        if getattr(self, "_auto_rotate_timer_scheduled", False):
            return
        self._auto_rotate_timer_scheduled = True
        self._last_auto_rotate_time = time.time()
        self._check_auto_rotate_tick()

    def _check_auto_rotate_tick(self):
        try:
            if not getattr(self, "root", None) or not self.root.winfo_exists():
                return
            if getattr(self, "var_auto_rotate", None) and self.var_auto_rotate.get():
                prov = self.get_selected_proxy_provider()
                if prov in ("mproxy", "kiotproxy", "kiotproxy_current", "proxysocks5", "proxyvn"):
                    sec = self.get_auto_rotate_interval_seconds()
                    now = time.time()
                    if (now - getattr(self, "_last_auto_rotate_time", 0.0)) >= sec:
                        self._last_auto_rotate_time = now
                        # Bảo vệ phiên đăng ký: Nếu đang có luồng chạy, hoãn xoay IP định kỳ để không làm đổi IP lúc đang chờ OTP (gây Checkpoint 282)
                        if getattr(self, "is_running", False):
                            self.event_queue.put(("log", {
                                "message": f"[Auto-Rotate] ⏳ Đang có luồng đăng ký hoạt động ➔ Tạm hoãn xoay IP định kỳ để bảo vệ phiên OTP (Tránh Checkpoint 282 do đổi IP giữa chừng)!",
                                "tag": "info"
                            }))
                        else:
                            min_str = f"{sec}s ({sec // 60} phút)" if sec >= 60 else f"{sec}s"
                            self.event_queue.put(("log", {
                                "message": f"[Auto-Rotate] ⏱️ Đã đến chu kỳ {min_str} ➔ Tự động gửi lệnh xoay IP cho toàn bộ key {prov}...",
                                "tag": "info"
                            }))
                            if prov == "mproxy":
                                self.rotate_all_mproxy_keys(silent=True)
                            elif prov == "proxyvn":
                                self.rotate_all_proxyvn_keys(silent=True)
                            else:
                                self.rotate_all_kiotproxy_keys(silent=True)
        except Exception as e:
            logger.debug(f"Auto-rotate tick error: {e}")
        finally:
            if getattr(self, "root", None) and self.root.winfo_exists():
                self.root.after(1000, self._check_auto_rotate_tick)

    def check_all_mproxy_keys(self):
        tok = self.get_mproxy_token()
        if not tok:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập Token API của mProxy.vn!")
            return

        masked_tok = self.mask_key(tok)
        self.log(f"[mProxy] 🔍 Đang kiểm tra tài khoản mProxy.vn (Token: {masked_tok})...", "info")
        self.lbl_kiot_status.config(text=f"Đang kiểm tra mProxy (Token: {masked_tok})...", fg=AppTheme.INFO)

        def worker():
            bal = MproxyClient.get_balance(tok)
            bal_str = f"{bal:,} VNĐ" if bal is not None else "Không xác định"
            keys = MproxyClient.get_keys(tok)
            self.event_queue.put(("log", {
                "message": f"[mProxy] 💰 Số dư tài khoản: {bal_str} | Số key 4G: {len(keys)}",
                "tag": "success" if (bal is not None and bal > 0) else "info"
            }))

            if not keys:
                self.event_queue.put(("log", {
                    "message": f"[mProxy] ⚠️ Tài khoản hiện chưa có Key 4G nào! Bấm 'Quản Lý mProxy' để xem gói cước hoặc mua key tại mproxy.vn.",
                    "tag": "warning"
                }))
                self.event_queue.put(("kiot_status", {
                    "text": f"mProxy: {bal_str} | 0 Key",
                    "live": 0
                }))
                return

            live_count = 0
            die_count = 0
            key_codes = []
            for idx, k_info in enumerate(keys, start=1):
                k_code = k_info.get("key_code", "")
                if k_code:
                    key_codes.append(k_code)
                client = MproxyClient(tok, key_code=k_code)
                res = client.get_current_proxy(force_refresh=True)
                masked_k = self.mask_key(k_code)
                exp_time = k_info.get("expired_time", "")
                if exp_time and "T" in exp_time:
                    exp_time = exp_time.split("T")[0]
                p_str = res.get("http") or res.get("proxy") or k_info.get("proxy")
                if res.get("success") and p_str:
                    live_count += 1
                    srv = k_info.get("server") or "ip.mproxy.vn"
                    port = k_info.get("server_port") or ""
                    loc = res.get("location", "Vietnam")
                    self.event_queue.put(("log", {
                        "message": f"[mProxy #{idx}] 🟢 LIVE | Key: {masked_k} | Cổng: {srv}:{port} | HSD: {exp_time} | Vị trí: {loc}",
                        "tag": "proxy"
                    }))
                else:
                    die_count += 1
                    msg = res.get("message") or "Không thể kết nối"
                    self.event_queue.put(("log", {
                        "message": f"[mProxy #{idx}] 🔴 DIE | Key: {masked_k} | Lỗi: {msg}",
                        "tag": "error"
                    }))

            formatted_keys = []
            for k_info in keys:
                srv_h = k_info.get("server_host") or "ip.mproxy.vn"
                srv_p = k_info.get("server_port")
                usr = k_info.get("user") or ""
                pwd = k_info.get("password") or k_info.get("key_code") or ""
                if srv_p:
                    formatted_keys.append(f"{srv_h}:{srv_p}:{usr}:{pwd}" if usr and pwd else f"{srv_h}:{srv_p}")
                elif k_info.get("key_code"):
                    formatted_keys.append(str(k_info.get("key_code")))
            if formatted_keys:
                self._raw_mproxy_keys = formatted_keys
                self.config["mproxy_keys"] = formatted_keys

            summary = f"🟢 Live: {live_count} | 🔴 Die: {die_count} (Ví: {bal_str})"
            self.event_queue.put(("kiot_status", {"text": summary, "live": live_count}))

        threading.Thread(target=worker, daemon=True).start()

    def rotate_all_mproxy_keys(self, silent: bool = False):
        tok = self.get_mproxy_token()
        if not tok:
            if not silent:
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập Token API của mProxy.vn!")
            return
        keys = self.get_mproxy_keys()
        self._last_auto_rotate_time = time.time()
        self.log(f"[mProxy] 🔄 Gửi yêu cầu xoay IP 4G cho {len(keys)} key mProxy...", "warning")

        def worker():
            for idx, key in enumerate(keys, start=1):
                client = MproxyClient(tok, key_code=key if key != tok else None)
                res = client.get_new_proxy(fallback_current=False)
                masked_k = self.mask_key(client.key_code or key)
                if res.get("success") and (res.get("http") or res.get("proxy")):
                    masked_ip_val = self.mask_ip(res.get("server") or res.get("ip") or "4G")
                    self.event_queue.put(("log", {
                        "message": f"[mProxy #{idx}] 🔄 Đã đổi sang IP 4G MỚI: {masked_ip_val} (Key: {masked_k})",
                        "tag": "proxy"
                    }))
                else:
                    ttc = res.get("ttc", 30)
                    msg = res.get("message", "Chờ cooldown")
                    self.event_queue.put(("log", {
                        "message": f"[mProxy #{idx}] ⏳ Chưa thể xoay: {msg} (Cooldown {ttc}s)",
                        "tag": "warning"
                    }))

        threading.Thread(target=worker, daemon=True).start()

    def open_mproxy_manager_dialog(self):
        """Hộp thoại quản lý mProxy.vn: Xem số dư, danh sách keys 4G, gói cước và mua/gia hạn."""
        dlg = tk.Toplevel(self.root)
        dlg.title("📱 Quản Lý & Tích Hợp mProxy.vn (Proxy 4G/5G)")
        dlg.geometry("580x580")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        header_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        header_frame.pack(fill=tk.X, padx=16, pady=(12, 6))
        tk.Label(
            header_frame,
            text="📱 Quản Lý Dịch Vụ mProxy.vn (Proxy 4G/5G)",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.ACCENT
        ).pack(anchor="w")
        tk.Label(
            header_frame,
            text="Proxy 4G/5G xoay IP từ SIM vật lý Việt Nam (Viettel, Mobifone, Vinaphone)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED
        ).pack(anchor="w")

        tok_frame = tk.LabelFrame(
            dlg,
            text=" 🔑 Token API mProxy.vn ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.INFO,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        tok_frame.pack(fill=tk.X, padx=16, pady=6)

        cur_tok = getattr(self, "mproxy_token", "CncgWVg-ppCxg7EwH7dFS6ICuv8hzXLaJdF-rzoXQAU")
        ent_tok = tk.Entry(
            tok_frame,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            bd=1,
            relief="solid"
        )
        ent_tok.insert(0, cur_tok)
        ent_tok.pack(fill=tk.X, pady=2)

        row_tok_btn = tk.Frame(tok_frame, bg=AppTheme.BG_CARD)
        row_tok_btn.pack(fill=tk.X, pady=(4, 0))

        lbl_balance = tk.Label(
            row_tok_btn,
            text="Số dư: Đang kiểm tra...",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS
        )
        lbl_balance.pack(side=tk.LEFT)

        def save_token():
            val = ent_tok.get().strip()
            if val:
                self.mproxy_token = val
                self.config["mproxy_token"] = val
                self.save_config(show_toast=False)
                messagebox.showinfo("Thành công", "Đã lưu Token API mProxy mới!", parent=dlg)

        btn_save_tok = tk.Button(
            row_tok_btn,
            text="💾 Lưu Token",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            bd=1,
            relief="solid",
            command=save_token
        )
        btn_save_tok.pack(side=tk.RIGHT, padx=(4, 0))

        # Khung Danh Sách Keys 4G
        keys_frame = tk.LabelFrame(
            dlg,
            text=" 📋 Danh Sách Keys 4G Của Tài Khoản ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.SUCCESS,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        keys_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=6)

        txt_keys_list = scrolledtext.ScrolledText(
            keys_frame,
            height=7,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            insertbackground=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid"
        )
        txt_keys_list.pack(fill=tk.BOTH, expand=True, pady=2)

        fetched_keys_data = []

        def fetch_account_info():
            u_tok = ent_tok.get().strip()
            if not u_tok:
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập Token API!", parent=dlg)
                return
            lbl_balance.config(text="Đang kết nối mProxy.vn...")
            txt_keys_list.delete("1.0", tk.END)
            txt_keys_list.insert("1.0", "Đang tải dữ liệu từ API...")

            def worker():
                bal = MproxyClient.get_balance(u_tok)
                keys = MproxyClient.get_keys(u_tok)
                fetched_keys_data.clear()
                fetched_keys_data.extend(keys)

                def update_ui():
                    b_str = f"{bal:,} VNĐ" if bal is not None else "0 VNĐ"
                    lbl_balance.config(text=f"Số dư: {b_str}")
                    txt_keys_list.delete("1.0", tk.END)
                    if keys:
                        for idx, k in enumerate(keys, 1):
                            k_code = k.get("key_code", "")
                            srv = k.get("server", "ip.mproxy.vn")
                            port = k.get("server_port", "")
                            exp = (k.get("expired_time") or "").split("T")[0]
                            txt_keys_list.insert(tk.END, f"Key #{idx}: {k_code} | Host: {srv}:{port} | HSD: {exp}\n")
                    else:
                        txt_keys_list.insert(tk.END, "# Tài khoản hiện chưa có Key 4G nào.\n# Hãy bấm 'Mua Gói / Nạp Tiền' bên dưới để kích hoạt Key 4G trên mproxy.vn!")

                self.root.after(0, update_ui)

            threading.Thread(target=worker, daemon=True).start()

        def apply_keys_to_tool():
            if not fetched_keys_data:
                u_tok = ent_tok.get().strip()
                if u_tok:
                    self.mproxy_token = u_tok
                    self.config["mproxy_token"] = u_tok
                    self._raw_mproxy_keys = [u_tok]
                    self.config["mproxy_keys"] = [u_tok]
                    self._render_proxy_keys_display()
                    messagebox.showinfo("Thành công", f"Đã nạp Token mProxy vào tool!", parent=dlg)
                    return
                messagebox.showwarning("Thông báo", "Chưa có Key nào được tải!", parent=dlg)
                return
            key_codes = [k["key_code"] for k in fetched_keys_data if k.get("key_code")]
            formatted_keys = []
            for k_info in keys:
                srv_h = k_info.get("server_host") or "ip.mproxy.vn"
                srv_p = k_info.get("server_port")
                usr = k_info.get("user") or ""
                pwd = k_info.get("password") or k_info.get("key_code") or ""
                if srv_p:
                    formatted_keys.append(f"{srv_h}:{srv_p}:{usr}:{pwd}" if usr and pwd else f"{srv_h}:{srv_p}")
                elif k_info.get("key_code"):
                    formatted_keys.append(str(k_info.get("key_code")))
            if formatted_keys:
                self._raw_mproxy_keys = formatted_keys
                self.config["mproxy_keys"] = formatted_keys
                self.save_config(show_toast=False)
                self._render_proxy_keys_display()
                messagebox.showinfo("Thành công", f"Đã nạp {len(key_codes)} Key 4G mProxy vào tool!", parent=dlg)
            else:
                messagebox.showinfo("Thông báo", "Tài khoản chưa có key hoạt động.", parent=dlg)

        row_keys_btn = tk.Frame(keys_frame, bg=AppTheme.BG_CARD)
        row_keys_btn.pack(fill=tk.X, pady=(4, 0))

        btn_refresh_info = tk.Button(
            row_keys_btn,
            text="🔄 Tải Lại Dữ Liệu",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            command=fetch_account_info
        )
        btn_refresh_info.pack(side=tk.LEFT, padx=(0, 4))

        btn_apply_keys = tk.Button(
            row_keys_btn,
            text="📥 Nạp Danh Sách Keys Này Vào Tool",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            bd=1,
            relief="solid",
            command=apply_keys_to_tool
        )
        btn_apply_keys.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Khung Mua Gói & Nạp Tiền
        buy_frame = tk.LabelFrame(
            dlg,
            text=" 🛒 Mua Gói Cước & Nạp Tiền mProxy.vn ",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING,
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )
        buy_frame.pack(fill=tk.X, padx=16, pady=6)

        row_pkg = tk.Frame(buy_frame, bg=AppTheme.BG_CARD)
        row_pkg.pack(fill=tk.X, pady=2)
        tk.Label(row_pkg, text="Chọn gói:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        cb_pkg = ttk.Combobox(
            row_pkg,
            values=[
                "Gói 1: Dùng thử miễn phí 3 ngày (0 VNĐ)",
                "Gói 2: Dùng 1 ngày 4G không giới hạn (15.000 VNĐ)",
                "Gói 4: 80K / 7 ngày 4G không giới hạn (80.000 VNĐ)",
                "Gói 5: 15K có 1GB / 30 ngày (15.000 VNĐ)",
                "Gói 8: 80K có 8GB / 30 ngày (80.000 VNĐ)",
            ],
            width=38,
            state="readonly"
        )
        cb_pkg.current(0)
        cb_pkg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        def buy_package_action():
            u_tok = ent_tok.get().strip()
            if not u_tok:
                messagebox.showwarning("Cảnh báo", "Vui lòng nhập Token API!", parent=dlg)
                return
            sel_idx = cb_pkg.current()
            pkg_ids = [1, 2, 4, 5, 8]
            pkg_id = pkg_ids[sel_idx] if sel_idx < len(pkg_ids) else 1

            lbl_balance.config(text=f"Đang gửi yêu cầu mua gói ID {pkg_id}...")
            def worker():
                res = MproxyClient.buy_package(u_tok, pkg_id)
                msg = res.get("message", "Kết quả mua")
                if res.get("status") == 1:
                    self.event_queue.put(("log", {
                        "message": f"[mProxy] 🎉 Mua gói ID {pkg_id} thành công: {msg}",
                        "tag": "success"
                    }))
                    fetch_account_info()
                else:
                    self.event_queue.put(("log", {
                        "message": f"[mProxy] ⚠️ Mua gói không thành công: {msg}. Hãy nạp tiền trên web mproxy.vn!",
                        "tag": "warning"
                    }))
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Thông báo mua gói",
                        f"Kết quả từ mProxy.vn: {msg}\n\n💡 Bạn có thể nạp tiền hoặc mua trực tiếp trên trang web mproxy.vn dễ dàng bằng mã QR!",
                        parent=dlg
                    ))
            threading.Thread(target=worker, daemon=True).start()

        row_buy_btns = tk.Frame(buy_frame, bg=AppTheme.BG_CARD)
        row_buy_btns.pack(fill=tk.X, pady=(6, 2))

        btn_buy_pkg = tk.Button(
            row_buy_btns,
            text="⚡ Mua Gói Qua API",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            bd=1,
            relief="solid",
            command=buy_package_action
        )
        btn_buy_pkg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_open_web = tk.Button(
            row_buy_btns,
            text="🌐 Mở Web mProxy.vn (Nạp Tiền / Mua Gói)",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            bd=1,
            relief="solid",
            command=lambda: webbrowser.open("https://mproxy.vn")
        )
        btn_open_web.pack(side=tk.LEFT, fill=tk.X, expand=True)

        fetch_account_info()

    def open_custom_hotmail_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("📋 Quản lý & Danh sách Hotmail (hotmails.txt)")
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)
        dlg.grab_set()

        dlg.update_idletasks()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        dw, dh = 780, 560
        dlg.geometry(f"{dw}x{dh}+{rx + max(0, (rw - dw) // 2)}+{ry + max(0, (rh - dh) // 2)}")
        dlg.minsize(640, 420)
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        top_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        top_bar.pack(fill=tk.X, padx=16, pady=(12, 4))

        lbl_instruct = tk.Label(
            top_bar,
            text="Danh sách tài khoản Hotmail (Mỗi dòng 1 tài khoản):\nĐịnh dạng: email|password|refresh_token|client_id|rec_email|rec_password",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MAIN,
            justify="left"
        )
        lbl_instruct.pack(side=tk.LEFT)

        lbl_dialog_count = tk.Label(
            top_bar,
            text="Số lượng: 0 mail",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.ACCENT
        )
        lbl_dialog_count.pack(side=tk.RIGHT, anchor="e")

        txt_hot = scrolledtext.ScrolledText(
            dlg,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            insertbackground=AppTheme.TEXT_MAIN,
            font=AppTheme.FONT_CODE,
            bd=1,
            relief="solid"
        )
        txt_hot.pack(fill=tk.BOTH, expand=True, padx=16, pady=6)

        def update_dialog_count():
            raw = txt_hot.get("1.0", tk.END).strip()
            lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
            lbl_dialog_count.config(text=f"Số lượng: {len(lines)} mail")

        def load_current_file():
            txt_hot.delete("1.0", tk.END)
            hot_file = os.path.join(os.path.dirname(__file__), "hotmails.txt")
            if os.path.exists(hot_file):
                try:
                    with open(hot_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                        content = f.read()
                    txt_hot.insert("1.0", content)
                except Exception as err:
                    self.log(f"Lỗi đọc hotmails.txt: {err}", "error")
            update_dialog_count()

        load_current_file()
        txt_hot.bind("<KeyRelease>", lambda e: update_dialog_count())

        btn_box = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        btn_box.pack(fill=tk.X, padx=16, pady=(6, 14))

        def on_import_from_dialog():
            filepath = filedialog.askopenfilename(
                title="Chọn file danh sách Hotmail để nạp",
                filetypes=[("Text files (*.txt)", "*.txt"), ("All files (*.*)", "*.*")],
                parent=dlg
            )
            if not filepath:
                return
            try:
                with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
                    new_text = f.read().strip()
                if not new_text:
                    messagebox.showwarning("Thông báo", "File rỗng!", parent=dlg)
                    return
                curr_text = txt_hot.get("1.0", tk.END).strip()
                if curr_text:
                    txt_hot.insert(tk.END, "\n" + new_text)
                else:
                    txt_hot.insert("1.0", new_text)
                update_dialog_count()
                messagebox.showinfo("Đã nạp", f"Đã nạp nội dung từ file {os.path.basename(filepath)} vào ô nhập!", parent=dlg)
            except Exception as ex:
                messagebox.showerror("Lỗi", f"Không thể đọc file: {ex}", parent=dlg)

        def on_open_in_notepad():
            self.open_hotmail_file()

        def on_clear_text():
            if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa trắng ô danh sách này?", parent=dlg):
                txt_hot.delete("1.0", tk.END)
                update_dialog_count()

        def on_save_hotmails():
            raw = txt_hot.get("1.0", tk.END).strip()
            hot_file = os.path.join(os.path.dirname(__file__), "hotmails.txt")
            try:
                with open(hot_file, "w", encoding="utf-8-sig") as f:
                    if raw:
                        f.write(raw + "\n")
                    else:
                        f.write("")
                DongVanHotmailProvider.load_from_file(hot_file)
                Smail1sHotmailProvider.load_from_file(hot_file)
                count = self.refresh_hotmail_count()
                self.cb_email_provider.set("📧 Dùng Hotmail Tự Nhập (Kho hotmails.txt) (KHUYÊN DÙNG - Nhận OTP 100%)")
                self.on_email_service_changed()
                self.config["email_service"] = "custom_hotmail"
                self.log(f"[Hotmail] Đã cập nhật thành công kho hotmails.txt ({count} mail).", "success")
                messagebox.showinfo("Thành công", f"Đã lưu danh sách vào kho thành công!\nHiện có: {count} Hotmail.", parent=dlg)
                dlg.destroy()
            except Exception as ex:
                messagebox.showerror("Lỗi", f"Lỗi lưu file hotmails.txt: {ex}", parent=dlg)

        btn_open_np = tk.Button(
            btn_box,
            cursor="hand2",
            text="📝 Mở bằng Notepad",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.INFO,
            bd=1,
            relief="solid",
            padx=10,
            pady=5,
            command=on_open_in_notepad
        )
        btn_open_np.pack(side=tk.LEFT, padx=3)

        btn_imp = tk.Button(
            btn_box,
            cursor="hand2",
            text="📂 Nạp từ file .txt",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            padx=10,
            pady=5,
            command=on_import_from_dialog
        )
        btn_imp.pack(side=tk.LEFT, padx=3)

        btn_reload = tk.Button(
            btn_box,
            cursor="hand2",
            text="🔄 Tải lại",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            padx=10,
            pady=5,
            command=load_current_file
        )
        btn_reload.pack(side=tk.LEFT, padx=3)

        btn_clear = tk.Button(
            btn_box,
            cursor="hand2",
            text="🗑️ Xóa trắng",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.DANGER,
            bd=1,
            relief="solid",
            padx=10,
            pady=5,
            command=on_clear_text
        )
        btn_clear.pack(side=tk.LEFT, padx=3)

        btn_cancel = tk.Button(
            btn_box,
            cursor="hand2",
            text="Đóng",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            bd=1,
            relief="solid",
            padx=12,
            pady=5,
            command=dlg.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, padx=3)

        btn_save = tk.Button(
            btn_box,
            cursor="hand2",
            text="💾 LƯU & CẬP NHẬT KHO",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg="#000000",
            activebackground=AppTheme.ACCENT_HOVER,
            bd=0,
            padx=14,
            pady=5,
            command=on_save_hotmails
        )
        btn_save.pack(side=tk.RIGHT, padx=3)

    def refresh_hotmail_count(self, force_read: bool = False) -> int:
        now_ts = time.time()
        if not force_read and hasattr(self, "_last_hotmail_read_ts"):
            if now_ts - self._last_hotmail_read_ts < 5.0 and hasattr(self, "_cached_hotmail_count"):
                return self._cached_hotmail_count
        self._last_hotmail_read_ts = now_ts
        filepath = os.path.join(os.path.dirname(__file__), "hotmails.txt")
        count = 0
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    lines_m = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                    count = len(lines_m)
            except Exception:
                pass
        self._cached_hotmail_count = count
        if hasattr(self, "lbl_hotmail_count"):
            try:
                self.lbl_hotmail_count.config(text=f"Kho: {count} mail")
            except Exception:
                pass
        return count

    def log(self, text: str, tag: str = "info"):
        if threading.current_thread() is not threading.main_thread():
            if hasattr(self, "event_queue") and self.event_queue is not None:
                self.event_queue.put(("log", {"message": text, "tag": tag}))
            return
        if not hasattr(self, "txt_logs") or not self.root.winfo_exists():
            return
        text = self.mask_ip(str(text))
        now = datetime.now().strftime("%H:%M:%S")
        line = f"[{now}] {text}\n"
        self.txt_logs.insert(tk.END, line, tag)
        if not hasattr(self, "_log_line_count"):
            self._log_line_count = 0
        self._log_line_count += 1
        now_t = time.time()
        if self._log_line_count > 2500 and (now_t - getattr(self, "_last_log_trim_ts", 0.0) > 8.0):
            self._last_log_trim_ts = now_t
            try:
                self.txt_logs.delete("1.0", "801.0")
                self._log_line_count = max(0, self._log_line_count - 800)
            except Exception:
                pass
        try:
            now_sc = time.perf_counter()
            if getattr(self, "_auto_scroll_logs", True):
                if (now_sc - getattr(self, "_last_log_scroll_ts", 0.0)) > 0.15:
                    self._last_log_scroll_ts = now_sc
                    y_pos = self.txt_logs.yview()
                    if len(y_pos) >= 2 and y_pos[1] >= 0.980:
                        self.txt_logs.yview_moveto(1.0)
        except Exception:
            pass

    def update_stats_display(self):
        self.lbl_stat_total.config(text=f"Tổng: {self.stat_total}")
        self.lbl_stat_success.config(text=f"● LIVE: {self.stat_success}")
        self.lbl_stat_failed.config(text=f"● DIE: {self.stat_failed}")
        self.lbl_stat_unverified.config(text=f"● CHƯA XÁC MINH: {self.stat_unverified}")

    def start_execution(self):
        if self.is_running:
            return

        self.save_config(show_toast=False)

        # Làm mới trạng thái kho Hotmail để sẵn sàng cho phiên mới
        try:

            reset_hotmail_pool()

        except Exception:

            pass

        # Trích xuất biến UI an toàn ngay trên Main Thread
        curr_reg_mode = self.var_reg_mode.get() if hasattr(self, "var_reg_mode") else "vr"
        curr_legacy_verify_mode = self.get_selected_legacy_verify_mode()
        curr_2fa = self.var_2fa.get() if hasattr(self, "var_2fa") else True
        curr_anti_cp = self.var_anti_cp.get() if hasattr(self, "var_anti_cp") else True
        curr_bait_mode = self.get_selected_bait_mode()
        curr_auto_phone = (curr_bait_mode == "phone")
        curr_enable_bait_retry = self.var_enable_bait_retry.get() if hasattr(self, "var_enable_bait_retry") else bool(self.config.get("enable_bait_retry", True))
        if not curr_enable_bait_retry:
            curr_bait_retries = 1
        elif hasattr(self, "spn_bait_retries"):
            try:
                curr_bait_retries = max(1, min(10, int(self.spn_bait_retries.get())))
            except Exception:
                curr_bait_retries = int(self.config.get("bait_retries", 3))
        elif hasattr(self, "var_bait_retries"):
            curr_bait_retries = max(1, min(10, int(self.var_bait_retries.get())))
        else:
            curr_bait_retries = int(self.config.get("bait_retries", 3))
        curr_default_pwd = self.entry_fb_pwd.get().strip() if hasattr(self, "entry_fb_pwd") else self.config.get("default_password", "")
        curr_email_service = self.get_selected_email_service()
        # Giữ nguyên cấu hình Mồi của người dùng (Mồi Gmail / Mồi SĐT / Direct)
        curr_selected_domains = self.get_selected_custom_domains() if hasattr(self, "get_selected_custom_domains") else self.config.get("selected_custom_domains", ["smail1s.com", "laoia.com", "smailwork.com"])
        if hasattr(self, "spn_otp_timeout"):
            try:
                curr_otp_timeout = int(self.spn_otp_timeout.get())
            except Exception:
                curr_otp_timeout = int(self.config.get("otp_timeout", 20))
        else:
            curr_otp_timeout = int(self.config.get("otp_timeout", 20))
        curr_name_type = self.get_selected_name_type()
        curr_name_file = getattr(self, "custom_name_file", "names.txt") or self.config.get("custom_name_file", "names.txt")
        curr_mix_names = self.var_mix_names.get() if hasattr(self, "var_mix_names") else False
        curr_retry_on_nvr = self.var_retry_on_nvr.get() if hasattr(self, "var_retry_on_nvr") else self.config.get("retry_on_nvr_with_new_mail", True)
        raw_retry_choice = self.cb_retry_email_service.get() if hasattr(self, "cb_retry_email_service") else ""
        curr_retry_email_service = self.RETRY_EMAIL_SERVICE_MAP.get(raw_retry_choice, self.config.get("retry_email_service", "as_setting"))
        curr_retry_use_free = (curr_retry_email_service == "auto_rotator") or self.config.get("retry_use_free_mail", False)
        try:
            curr_max_email_retries = int(self.spn_max_email_retries.get()) if hasattr(self, "spn_max_email_retries") else int(self.config.get("max_otp_email_retries", 15))
        except Exception:
            curr_max_email_retries = int(self.config.get("max_otp_email_retries", 15))


        # Pre-extract server, device and proxy allocation configs safely on Main Thread (zero Tk calls in subthreads)
        curr_alloc_mode = self.get_proxy_alloc_mode()
        self.config["proxy_alloc_mode"] = curr_alloc_mode
        chosen_mode = self.get_selected_server_mode() if hasattr(self, "get_selected_server_mode") else self.config.get("server_mode", "single")
        chosen_pool = self.get_selected_server_pool() if hasattr(self, "get_selected_server_pool") else self.config.get("server_pool", [])
        chosen_server = self.get_selected_server() if hasattr(self, "get_selected_server") else self.config.get("server", "m.facebook.com")
        curr_device_type = self.config.get("device_type", "mr_sxr")
        curr_save_format = self.config.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
        curr_extract_token = ("TOKEN" in curr_save_format)
        curr_fallback_email_service = self.config.get("fallback_email_service", "10minutemail")
        curr_metaking_api_key = self.config.get("metaking_api_key", "")
        curr_metaking_service_type = self.config.get("metaking_service_type", "email")
        curr_metaking_server = self.config.get("metaking_server", 1)
        curr_metaking_domain = self.config.get("metaking_domain", "hotmail.com") or "hotmail.com"
        curr_metaking_country_id = self.config.get("metaking_country_id", 154)
        curr_metaking_price = self.config.get("metaking_price", "low")
        nvr_list_to_run = []
        if curr_reg_mode == "verify_nvr":
            checked_items = self.get_checked_items()
            acc_map = getattr(self, "_row_acc_data", {})
            if checked_items and len(checked_items) < len(self.tree.get_children()):
                for citm in checked_items:
                    if citm in acc_map:
                        nvr_list_to_run.append(acc_map[citm])
            if not nvr_list_to_run:
                nvr_list_to_run = list(getattr(self, "nvr_accounts_queue", []))
            if not nvr_list_to_run and hasattr(self, "_row_acc_data") and self._row_acc_data:
                nvr_list_to_run = list(self._row_acc_data.values())

        try:
            num_threads = max(1, int(str(self.spn_threads.get()).strip()))
        except Exception:
            num_threads = 4
        self._cached_num_threads = num_threads

        try:
            max_accs = int(self.spn_accounts.get())
        except Exception:
            max_accs = 0

        if max_accs <= 0:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập 'Số acc cần tạo' lớn hơn 0 (ví dụ: 5 hoặc 10)!")
            self.spn_accounts.delete(0, tk.END)
            self.spn_accounts.insert(0, "5")
            return

        provider_name = self.get_selected_proxy_provider()
        kiot_keys = self.get_kiotproxy_keys() if provider_name in ("kiotproxy", "kiotproxy_current") else []
        psocks5_keys = self.get_proxysocks5_keys() if provider_name == "proxysocks5" else []
        mproxy_keys = self.get_mproxy_keys() if provider_name == "mproxy" else []
        proxyvn_keys = self.get_proxyvn_keys() if provider_name == "proxyvn" else []
        if provider_name == "proxyvn" and not proxyvn_keys:
            messagebox.showerror("Lỗi Proxy", "Vui lòng cấu hình ít nhất 1 Proxy.vn Key!")
            return
        if provider_name in ("kiotproxy", "kiotproxy_current") and not kiot_keys:
            messagebox.showerror("Lỗi Proxy", "Vui lòng cấu hình ít nhất 1 KiotProxy Key!")
            return
        if provider_name == "proxysocks5" and not psocks5_keys:
            messagebox.showerror("Lỗi Proxy", "Vui lòng cấu hình ít nhất 1 ProxySocks5 tokenProxy Key!")
            return

        self.session_new_success = 0
        self.session_new_unver = 0
        self.session_new_failed = 0

        if curr_reg_mode == "verify_nvr":
            if not getattr(self, "nvr_accounts_queue", []):
                self.populate_table_with_nvr_accounts()

            nvr_queue = getattr(self, "nvr_accounts_queue", [])
            if not nvr_queue:
                if getattr(self, "var_enable_verry_pipeline", None) and self.var_enable_verry_pipeline.get():
                    self.log("⚡ [Pipeline Verry] Chưa có sẵn acc trong bảng, chuyển sang chế độ CHỜ ACC TỰ ĐỘNG TỪ TOOL REG [sau thời gian ngấu]...", "info")
                else:
                    messagebox.showwarning(
                        "Chưa có tài khoản",
                        "Vui lòng bấm nút '📋 Nhập / Dán Acc NVR' để nạp danh sách tài khoản cần xác minh!"
                    )
                    self.open_nvr_import_dialog()
                    return

        self.is_running = True
        self.stop_event.clear()
        if hasattr(self, "_worker_item_map"):
            self._worker_item_map.clear()
        if hasattr(self, "_worker_target_map"):
            self._worker_target_map.clear()
        self.btn_start.config(state=tk.DISABLED, bg=AppTheme.BORDER)
        self.btn_stop.config(state=tk.NORMAL)

        # Pipeline khởi động: liên kết với Tool Verry hoặc khởi động StandaloneVerryEngine
        if getattr(self, "var_enable_verry_pipeline", None) and self.var_enable_verry_pipeline.get():
            v_dir = self.var_verry_pipeline_dir.get().strip() if hasattr(self, "var_verry_pipeline_dir") else r"C:\Users\truon\Downloads\verry"
            delay_str = self.var_verry_pipeline_delay.get() if hasattr(self, "var_verry_pipeline_delay") else "2 phút"
            from core.nvr_pipeline_bridge import is_verry_gui_running, StandaloneVerryEngine, _safe_int
            if curr_reg_mode != "verify_nvr":
                if is_verry_gui_running(v_dir):
                    self.log(f"🔗 [Pipeline Verry] Đã liên kết với Tool Verry [đang mở]! Nick NVR sau khi reg sẽ hẹn giờ chuyển sang Verry sau {delay_str}.", "info")
                else:
                    v_threads = _safe_int(self.var_verry_pipeline_threads.get() if hasattr(self, "var_verry_pipeline_threads") else 50, 50)
                    engine = StandaloneVerryEngine.get_instance(v_dir, v_threads)
                    engine.set_logger(lambda m, t="info": self.log(m, t))
                    engine.start()

        if curr_reg_mode == "vr":
            mode_desc = "VR OTP (Xác minh OTP)"
        elif curr_reg_mode == "verify_nvr":
            mode_desc = f"Xác minh Acc NVR ({len(getattr(self, 'nvr_accounts_queue', []))} Acc đã nạp)"
        elif curr_reg_mode in ("ios_bloks", "bloks_ios", "regfb"):
            curr_srv = self.get_selected_email_service() if hasattr(self, "get_selected_email_service") else self.config.get("email_service", "")
            disp_name = self.EMAIL_PROVIDER_REVERSE.get(curr_srv, curr_srv) if hasattr(self, "EMAIL_PROVIDER_REVERSE") else curr_srv
            if curr_bait_mode == "gmail":
                bm_lbl = "Mồi Gmail"
            elif curr_bait_mode == "phone":
                bm_lbl = "Mồi SĐT"
            else:
                bm_lbl = "Email trực tiếp (regfb.py)"
            mode_desc = f"🍏 iOS Bloks Native (regfb.py | XM: {disp_name} | {bm_lbl})"
        elif curr_reg_mode in ("legacy_nv", "legacy"):
            if curr_legacy_verify_mode in ("setting", "verify", "email", "phone"):
                curr_srv = self.get_selected_email_service() if hasattr(self, "get_selected_email_service") else self.config.get("email_service", "")
                curr_stype = self.config.get("metaking_service_type", "")
                is_phone = (curr_srv == "metaking_phone" or curr_stype == "phone")
                if "metaking" in curr_srv:
                    m_dom = self.config.get("metaking_domain", "gmail.com")
                    srv_label = f"👑 Metaking SĐT FB" if is_phone else f"👑 Metaking ({m_dom})"
                elif "custom_hotmail" in curr_srv or "hotmail" in curr_srv:
                    srv_label = "Hotmail (hotmails.txt)"
                elif "10minute" in curr_srv:
                    srv_label = "10MinuteMail (@laoia.com)"
                else:
                    disp_name = self.EMAIL_PROVIDER_REVERSE.get(curr_srv, curr_srv) if hasattr(self, "EMAIL_PROVIDER_REVERSE") else curr_srv
                    srv_label = disp_name
                mode_desc = f"Legacy NV (Mr-SxR + XM theo setting: [{srv_label}])"
            else:
                mode_desc = "Legacy NV (Mr-SxR - No-Verify Bypass)"
        else:
            mode_desc = "NVR (No-Verify SĐT Ảo)" 
        self.log(f"[*] BẮT ĐẦU TIẾN TRÌNH: {num_threads} Luồng | Chế độ: {mode_desc} | Mục tiêu: {max_accs} Tài khoản", "info")

        def get_subnet_24(ip_val: str) -> str:
            parts = str(ip_val).strip().split(".")
            if len(parts) >= 3 and parts[0].isdigit():
                return f"{parts[0]}.{parts[1]}.{parts[2]}"
            return str(ip_val)

        def master_worker():
            # Quản lý Proxy & Hotmail song song, độc lập 100% theo từng luồng
            ip_registry = ActiveIpRegistry()
            proxy_manager = ProxyManager()
            free_mgr = None
            alloc_mode = curr_alloc_mode
            actual_threads = num_threads
            _shared_ip_last_submit = {}
            _shared_ip_gate_lock = threading.Lock()
            effective_mproxy_keys = []
            # Lọc và thẩm định danh sách KiotProxy keys khả dụng trước khi gán luồng
            effective_kiot_keys = []
            initial_kiot_info = {}
            if provider_name in ("kiotproxy", "kiotproxy_current") and kiot_keys:
                self.event_queue.put(("log", {
                    "message": f"[KiotProxy] 🔍 Đang thẩm định {len(kiot_keys)} Key để phân bổ IP tối ưu cho {num_threads} luồng...",
                    "tag": "info"
                }))
                def _probe_kiot(item):
                    cand_idx, cand_k = item
                    c_tmp = KiotProxyClient(cand_k)
                    inf_tmp = c_tmp.get_current_proxy(force_refresh=True)
                    if not inf_tmp.get("success") or not inf_tmp.get("http"):
                        inf_tmp = c_tmp.get_new_proxy(fallback_current=True)
                    return cand_idx, cand_k, inf_tmp

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(kiot_keys))) as ex:
                    probe_results = list(ex.map(_probe_kiot, enumerate(kiot_keys)))

                for cand_idx, cand_k, inf_tmp in sorted(probe_results, key=lambda x: x[0]):
                    initial_kiot_info[cand_k] = inf_tmp
                    msg_tmp = str(inf_tmp.get("message", "")).lower()
                    if inf_tmp.get("success") and inf_tmp.get("http"):
                        effective_kiot_keys.append(cand_k)
                    elif not any(bad in msg_tmp for bad in ("hết hạn", "không tìm thấy key", "404", "invalid", "khóa")):
                        # Key hợp lệ (sẽ quay IP tự động khi luồng chạy, không quay trước để tránh dính cooldown)
                        effective_kiot_keys.append(cand_k)
                    else:
                        self.event_queue.put(("log", {
                            "message": f"[KiotProxy] ⚠️ Key #{cand_idx + 1} ({self.mask_key(cand_k)}): {inf_tmp.get('message', 'Lỗi')} -> Tự động loại bỏ key lỗi.",
                            "tag": "warning"
                        }))
                if not effective_kiot_keys:
                    effective_kiot_keys = list(kiot_keys)
                key_cnt = len(effective_kiot_keys)
                actual_threads = num_threads
                threads_per_key = (num_threads + key_cnt - 1) // max(1, key_cnt)
                if num_threads > key_cnt:
                    alloc_mode = "shared"
                    self.event_queue.put(("log", {
                        "message": f"[KiotProxy] ⚡ Không giới hạn số luồng: Khởi chạy ĐỦ {actual_threads} Luồng song song theo đúng cài đặt chia đều cho {key_cnt} Key KiotProxy (~{threads_per_key} luồng/Key)...",
                        "tag": "info"
                    }))
                else:
                    alloc_mode = "dedicated"
                    self.event_queue.put(("log", {
                        "message": f"[KiotProxy] 🛡️ Khởi chạy {actual_threads} Luồng song song trên {actual_threads}/{key_cnt} Key KiotProxy độc lập.",
                        "tag": "info"
                    }))
            elif provider_name == "proxyvn" and proxyvn_keys:
                effective_proxyvn_keys = []
                initial_proxyvn_info = {}
                self.event_queue.put(("log", {
                    "message": f"[Proxy.vn] 🔍 Đang thẩm định {len(proxyvn_keys)} Key để phân bổ IP tối ưu cho {num_threads} luồng...",
                    "tag": "info"
                }))
                def _probe_pvn(item):
                    cand_idx, cand_k = item
                    c_tmp = ProxyVNClient(cand_k)
                    inf_tmp = c_tmp.get_current_proxy(force_refresh=True)
                    return cand_idx, cand_k, inf_tmp

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(proxyvn_keys))) as ex:
                    probe_results = list(ex.map(_probe_pvn, enumerate(proxyvn_keys)))

                for cand_idx, cand_k, inf_tmp in sorted(probe_results, key=lambda x: x[0]):
                    initial_proxyvn_info[cand_k] = inf_tmp
                    msg_tmp = str(inf_tmp.get("message", "")).lower()
                    if inf_tmp.get("success") and (inf_tmp.get("http") or inf_tmp.get("raw_http")):
                        effective_proxyvn_keys.append(cand_k)
                    elif not any(bad in msg_tmp for bad in ("không tồn tại", "not found", "hết hạn", "invalid", "khóa", "404", "102")):
                        effective_proxyvn_keys.append(cand_k)
                    else:
                        self.event_queue.put(("log", {
                            "message": f"[Proxy.vn] ⚠️ Key #{cand_idx + 1} ({self.mask_key(cand_k)}): {inf_tmp.get('message', 'Lỗi')} -> Tự động loại bỏ key lỗi.",
                            "tag": "warning"
                        }))
                if not effective_proxyvn_keys:
                    effective_proxyvn_keys = list(proxyvn_keys)
                key_cnt = len(effective_proxyvn_keys)
                actual_threads = num_threads
                threads_per_key = (num_threads + key_cnt - 1) // max(1, key_cnt)
                if num_threads > key_cnt:
                    alloc_mode = "shared"
                    self.event_queue.put(("log", {
                        "message": f"[Proxy.vn] ⚡ Khởi chạy {actual_threads} Luồng song song theo đúng cài đặt chia đều cho {key_cnt} Key Proxy.vn (~{threads_per_key} luồng/Key)...",
                        "tag": "info"
                    }))
                else:
                    alloc_mode = "dedicated"
                    self.event_queue.put(("log", {
                        "message": f"[Proxy.vn] 🛡️ Khởi chạy {actual_threads} Luồng song song trên {actual_threads}/{key_cnt} Key Proxy.vn độc lập.",
                        "tag": "info"
                    }))
            elif provider_name == "proxysocks5" and psocks5_keys:
                effective_psocks5_keys = []
                self.event_queue.put(("log", {
                    "message": f"[ProxySocks5] 🔍 Đang thẩm định {len(psocks5_keys)} Key để phân bổ IP tối ưu cho {num_threads} luồng...",
                    "tag": "info"
                }))
                for cand_idx, cand_k in enumerate(psocks5_keys):
                    c_tmp = ProxySocks5Client(cand_k, user_token=getattr(self, "proxysocks5_user_token", None))
                    inf_tmp = c_tmp.get_current_proxy()
                    msg_tmp = str(inf_tmp.get("message", "")).lower()
                    if inf_tmp.get("success") and (inf_tmp.get("http") or inf_tmp.get("socks5")):
                        effective_psocks5_keys.append(cand_k)
                    elif not any(bad in msg_tmp for bad in ("không tồn tại", "not found", "hết hạn", "invalid", "khóa", "404")):
                        effective_psocks5_keys.append(cand_k)
                    else:
                        self.event_queue.put(("log", {
                            "message": f"[ProxySocks5] ⚠️ Key #{cand_idx + 1} ({self.mask_key(cand_k)}): {inf_tmp.get('message', 'Lỗi')} -> Tự động loại bỏ key lỗi.",
                            "tag": "warning"
                        }))
                if not effective_psocks5_keys:
                    effective_psocks5_keys = list(psocks5_keys)
                key_cnt = len(effective_psocks5_keys)
                actual_threads = num_threads
                threads_per_key = (num_threads + key_cnt - 1) // max(1, key_cnt)
                if num_threads > key_cnt:
                    alloc_mode = "shared"
                    self.event_queue.put(("log", {
                        "message": f"[ProxySocks5] ⚡ Khởi chạy ĐỦ {actual_threads} Luồng song song theo đúng cài đặt chia đều cho {key_cnt} Key ProxySocks5 (~{threads_per_key} luồng/Key)...",
                        "tag": "info"
                    }))
                else:
                    self.event_queue.put(("log", {
                        "message": f"[ProxySocks5] 🛡️ Khởi chạy {actual_threads} Luồng song song trên {actual_threads}/{key_cnt} Key ProxySocks5 độc lập.",
                        "tag": "info"
                    }))
            elif provider_name == "mproxy":
                tok = self.get_mproxy_token()
                keys_to_eval = list(mproxy_keys) if mproxy_keys else []
                if (not keys_to_eval or len(keys_to_eval) <= 1) and tok:
                    try:
                        fetched = MproxyClient.get_keys(tok)
                        if fetched:
                            f_keys = []
                            for k_data in fetched:
                                srv_h = k_data.get("server_host") or "ip.mproxy.vn"
                                srv_p = k_data.get("server_port")
                                usr = k_data.get("user") or ""
                                pwd = k_data.get("password") or k_data.get("key_code") or ""
                                if srv_p:
                                    f_keys.append(f"{srv_h}:{srv_p}:{usr}:{pwd}" if usr and pwd else f"{srv_h}:{srv_p}")
                                elif k_data.get("key_code"):
                                    f_keys.append(str(k_data.get("key_code")))
                            if f_keys:
                                keys_to_eval = f_keys
                                self._raw_mproxy_keys = f_keys
                                self.config["mproxy_keys"] = f_keys
                    except Exception as e:
                        logger.debug(f"[mProxy] Error auto-fetching keys: {e}")

                self.event_queue.put(("log", {
                    "message": f"[mProxy] 🔍 Đang thẩm định {len(keys_to_eval)} Cổng Proxy 4G mProxy để phân bổ cho {num_threads} luồng...",
                    "tag": "info"
                }))

                for cand_idx, cand_k in enumerate(keys_to_eval):
                    mp_tmp = MproxyClient(tok, key_code=cand_k if cand_k != tok else None)
                    inf_tmp = mp_tmp.get_current_proxy()
                    msg_tmp = str(inf_tmp.get("message", "")).lower()
                    if inf_tmp.get("success") and (inf_tmp.get("http") or inf_tmp.get("proxy")):
                        effective_mproxy_keys.append(cand_k)
                    elif not any(bad in msg_tmp for bad in ("hết hạn", "không tìm thấy", "404", "invalid", "khóa")):
                        effective_mproxy_keys.append(cand_k)
                    else:
                        self.event_queue.put(("log", {
                            "message": f"[mProxy] ⚠️ Cổng #{cand_idx + 1} ({self.mask_key(cand_k)}): {inf_tmp.get('message', 'Lỗi')} -> Tự động loại bỏ cổng lỗi.",
                            "tag": "warning"
                        }))

                if not effective_mproxy_keys:
                    effective_mproxy_keys = list(keys_to_eval) if keys_to_eval else ([tok] if tok else [])

                key_cnt = len(effective_mproxy_keys)
                actual_threads = num_threads
                threads_per_key = (num_threads + key_cnt - 1) // max(1, key_cnt)
                if num_threads > key_cnt:
                    alloc_mode = "shared"
                    self.event_queue.put(("log", {
                        "message": f"[mProxy] ⚡ Khởi chạy ĐỦ {actual_threads} Luồng song song theo đúng cài đặt chia đều cho {key_cnt} Cổng mProxy 4G (~{threads_per_key} luồng/Cổng)...",
                        "tag": "info"
                    }))
                else:
                    self.event_queue.put(("log", {
                        "message": f"[mProxy] 🛡️ Khởi chạy {actual_threads} Luồng song song trên {actual_threads}/{key_cnt} Cổng mProxy riêng biệt.",
                        "tag": "info"
                    }))
            elif provider_name in ("free_proxy_live", "free_proxy_cached", "free_proxy"):
                from core.proxy_manager import FreeProxyManager
                total_srcs = FreeProxyManager.get_total_sources_count()
                free_mgr = FreeProxyManager()
                if provider_name in ("free_proxy", "free_proxy_live"):
                    free_mgr.purge_all_cache()
                    self.event_queue.put(("log", {
                        "message": f"[Proxy Free Online] 🌐 BẮT ĐẦU CÀO MỚI 100%: Đang kết nối trực tiếp {total_srcs} nguồn trực tuyến (Đã xóa sạch cache RAM & đĩa, KHÔNG dùng proxy cũ)...",
                        "tag": "info"
                    }))
                    self.event_queue.put(("kiot_status", {"text": f"🌐 Đang cào tươi {total_srcs} nguồn online...", "live": 0}))
                    fresh_cands = free_mgr.fetch_candidates(max_per_source=150, force_fresh=True)
                    self.event_queue.put(("log", {
                        "message": f"[Proxy Free Online] 🚀 Đã cào tươi thành công {len(fresh_cands)} proxy mới từ internet! Bắt đầu kiểm định kết nối Facebook và phân bổ cho {actual_threads} luồng...",
                        "tag": "success"
                    }))
                else:
                    free_mgr.reset_session()
                    cand_count = len(getattr(free_mgr, "_untested_candidates", []))
                    self.event_queue.put(("log", {
                        "message": f"[Proxy Free Cache] 🎲 Chế độ Kho Sẵn Có: Bốc ngẫu nhiên từ kho {cand_count} proxy trong RAM (0ms không cần cào lại mạng)...",
                        "tag": "info"
                    }))
                ip_registry.reset_session()
                desired_buf = max(150, min(actual_threads * 2, 500))
                free_mgr.start_continuous_validator(target_buffer=desired_buf)

                # PRE-VALIDATION WARM-UP: Đảm bảo có sẵn proxy LIVE Facebook trước khi khởi chạy workers
                target_warm = min(actual_threads, 5)
                warm_start = time.time()
                self.event_queue.put(("log", {
                    "message": f"[Proxy Free] ⏳ Đang kiểm định kết nối Facebook (TLS Handshake & Tạo phiên) cho các proxy tươi...",
                    "tag": "info"
                }))
                while len(getattr(free_mgr, "_live_proxies", [])) < target_warm and (time.time() - warm_start) < 10.0 and not self.stop_event.is_set():
                    time.sleep(0.5)

                live_cnt = len(getattr(free_mgr, "_live_proxies", []))
                if live_cnt > 0:
                    self.event_queue.put(("log", {
                        "message": f"[Proxy Free] 🎉 Đã kiểm định sẵn sàng {live_cnt} proxy LIVE Facebook! Bắt đầu phân bổ độc lập cho {actual_threads} luồng...",
                        "tag": "success"
                    }))
                    self.event_queue.put(("kiot_status", {"text": f"🌐 Proxy Free: {live_cnt} live sẵn sàng", "live": 1}))
                else:
                    self.event_queue.put(("log", {
                        "message": f"[Proxy Free] ⚠️ Đang tiếp tục quét tìm Proxy LIVE Facebook kết nối được m.facebook.com...",
                        "tag": "warning"
                    }))
                    self.event_queue.put(("kiot_status", {"text": "🌐 Proxy Free: Đang dò live...", "live": 0}))
            elif provider_name == "proxy_list":
                proxy_path = self.get_proxy_file_path() if hasattr(self, "get_proxy_file_path") else "proxy.txt"
                if not os.path.exists(proxy_path) and os.path.exists("proxies.txt"):
                    proxy_path = "proxies.txt"



                if proxy_path and os.path.exists(proxy_path) and os.path.getsize(proxy_path) > 0:
                    proxy_manager.auto_remove_bad_from_file = bool(self.config.get("filter_bad_proxy_from_file", True))
                    proxy_manager.bad_proxy_filepath = "proxy_loi.txt"
                    proxy_manager.load_from_file(proxy_path)
                    p_cnt = proxy_manager.alive_count()
                    if p_cnt > 0:
                        actual_threads = num_threads
                        if num_threads > p_cnt:
                            alloc_mode = "shared"
                            self.event_queue.put(('log', {
                                'message': f"[Proxy List] ⚡ Khởi chạy ĐỦ {actual_threads} Luồng song song chia đều cho {p_cnt} proxy trong file '{proxy_path}'...",
                                'tag': 'info'
                            }))
                        else:
                            self.event_queue.put(('log', {
                                'message': f"[Proxy List] 🛡️ Khởi chạy {actual_threads} Luồng song song trên {p_cnt} proxy trong file '{proxy_path}'.",
                                'tag': 'success'
                            }))
                    else:
                        self.event_queue.put(('log', {
                            'message': f"[Proxy List] ⚠️ File proxy '{proxy_path}' không chứa proxy hợp lệ nào! Vui lòng kiểm tra lại file (định dạng IP:Port).",
                            'tag': 'warning'
                        }))
                else:
                    self.event_queue.put(("log", {
                        "message": f"[Proxy List] ⚠️ File proxy '{proxy_path}' không tồn tại hoặc rỗng. Vui lòng kiểm tra lại file (1 dòng 1 proxy)!",
                        "tag": "warning"
                    }))
            elif provider_name == "none":
                self.event_queue.put(("log", {
                    "message": f"[Không Proxy] ⚡ Khởi chạy {num_threads} Luồng kết nối Mạng Trực Tiếp (Direct IP)...",
                    "tag": "info"
                }))

            if curr_email_service in ("custom_hotmail", "dongvanfb", "smail1s", "hotmail") and os.path.exists("hotmails.txt"):
                # reset_hotmail_pool at top level
                from core.email_service import DongVanHotmailProvider, Smail1sHotmailProvider
                reset_hotmail_pool()
                DongVanHotmailProvider.load_from_file("hotmails.txt")
                Smail1sHotmailProvider.load_from_file("hotmails.txt")

            successful_accs = 0
            success_lock = threading.Lock()
            total_attempts = 0
            attempt_lock = threading.Lock()
            nvr_list = list(nvr_list_to_run)
            nvr_idx = 0
            nvr_lock = threading.Lock()
            pipeline_active = bool(getattr(self, "var_enable_verry_pipeline", None) and self.var_enable_verry_pipeline.get())
            pipeline_stop_event = threading.Event()

            if curr_reg_mode == "verify_nvr" and pipeline_active:
                def _pipeline_feeder():
                    from core.nvr_pipeline_bridge import claim_ready_accounts
                    v_dir = self.var_verry_pipeline_dir.get().strip() if hasattr(self, "var_verry_pipeline_dir") else os.getcwd()
                    known_uids = set()
                    with nvr_lock:
                        for acc in nvr_list:
                            u = str(acc.get("uid", "")).strip()
                            if u:
                                known_uids.add(u)

                    while not self.stop_event.is_set() and not pipeline_stop_event.is_set():
                        try:
                            ready_accs = claim_ready_accounts(v_dir, max_count=50, worker_tag="verry_gui")
                            if ready_accs:
                                new_ones = []
                                with nvr_lock:
                                    for ra in ready_accs:
                                        ru = str(ra.get("uid", "")).strip()
                                        if ru and ru not in known_uids:
                                            known_uids.add(ru)
                                            nvr_list.append(ra)
                                            new_ones.append(ra)
                                if new_ones:
                                    self.event_queue.put(("log", {
                                        "message": f"⚡ [Pipeline Verry] Kéo thành công {len(new_ones)} tài khoản NVR đã ngấu từ Tool Reg vào luồng xác minh!",
                                        "tag": "success"
                                    }))
                                    for na in new_ones:
                                        self.event_queue.put(("table_insert_pipeline", na))
                        except Exception as ex_f:
                            logger.warning(f"Error in pipeline feeder: {ex_f}")
                        pipeline_stop_event.wait(timeout=2.0)

                feeder_th = threading.Thread(target=_pipeline_feeder, daemon=True, name="PipelineFeeder")
                feeder_th.start()
            shared_kiot_state = {}
            if provider_name in ("kiotproxy", "kiotproxy_current") and (effective_kiot_keys or kiot_keys):
                kiot_p_keys = effective_kiot_keys if effective_kiot_keys else kiot_keys
                def _init_one_kiot(cand_k):
                    k_client = KiotProxyClient(cand_k)
                    inf = initial_kiot_info.get(cand_k) if "initial_kiot_info" in locals() else None
                    if not inf or not inf.get("success") or not inf.get("http"):
                        inf = k_client.get_current_proxy(force_refresh=True)
                    if not inf.get("success") or not inf.get("http"):
                        inf = k_client.get_new_proxy(fallback_current=True)
                    if not inf.get("success") or not inf.get("http"):
                        cached = KiotProxyClient.get_cached_proxy(cand_k, max_age=300.0)
                        if cached and cached.get("http"):
                            inf = cached
                    p_item = ProxyManager.parse_proxy(inf.get("http")) if (inf and inf.get("http")) else None
                    cur_ip = inf.get("ip") or (p_item.host if p_item else "")
                    loc = inf.get("location", "Vietnam") if inf else "Vietnam"
                    if p_item and cur_ip:
                        p_item.raw = cand_k
                        p_item.country = loc
                        p_item.country_code = normalize_country_code(loc) or "VN"
                        p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                        p_item.real_ip = cur_ip
                    return cand_k, {
                        "lock": threading.Lock(),
                        "session_lock": threading.Lock(),
                        "proxy_obj": p_item,
                        "cur_ip": cur_ip,
                        "last_working_proxy": copy.copy(p_item) if p_item else None,
                        "last_working_ip": cur_ip,
                        "location": loc,
                        "rot_time": time.time(),
                        "last_fetch": time.time(),
                        "next_rotate_allowed_at": 0.0,
                        "rot_lock": threading.Lock(),
                        "active_sessions": 0,
                        "client": k_client,
                        "burned_ips": set(),
                        "need_rotate": False,
                        "fail_count": 0,
                    }

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, max(1, len(kiot_p_keys)))) as _pool_ex:
                    for _k, _st in _pool_ex.map(_init_one_kiot, kiot_p_keys):
                        shared_kiot_state[_k] = _st

            shared_proxyvn_state = {}
            if provider_name == "proxyvn" and (effective_proxyvn_keys or proxyvn_keys):
                proxyvn_p_keys = effective_proxyvn_keys if effective_proxyvn_keys else proxyvn_keys
                def _init_one_pvn(cand_k):
                    pvn_client = ProxyVNClient(cand_k)
                    inf = initial_proxyvn_info.get(cand_k) if "initial_proxyvn_info" in locals() else None
                    if not inf or not inf.get("success") or not inf.get("http"):
                        inf = pvn_client.get_current_proxy(force_refresh=True)
                    if not inf.get("success") or not inf.get("http"):
                        inf = pvn_client.get_new_proxy(fallback_current=True)
                    if not inf.get("success") or not inf.get("http"):
                        cached = ProxyVNClient.get_cached_proxy(cand_k, max_age=300.0)
                        if cached and cached.get("http"):
                            inf = cached
                    p_str = inf.get("http") if inf else None
                    p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                    cur_ip = inf.get("ip") or (p_item.host if p_item else "")
                    loc = inf.get("location", "Vietnam") if inf else "Vietnam"
                    if p_item and cur_ip:
                        p_item.raw = cand_k
                        p_item.country = loc
                        p_item.country_code = normalize_country_code(loc) or "VN"
                        p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                        p_item.real_ip = cur_ip
                    return cand_k, {
                        "lock": threading.Lock(),
                        "session_lock": threading.Lock(),
                        "proxy_obj": p_item,
                        "cur_ip": cur_ip,
                        "last_working_proxy": copy.copy(p_item) if p_item else None,
                        "last_working_ip": cur_ip,
                        "location": loc,
                        "carrier": inf.get("carrier", "") if inf else "",
                        "rot_time": time.time(),
                        "last_fetch": time.time(),
                        "next_rotate_allowed_at": 0.0,
                        "rot_lock": threading.Lock(),
                        "active_sessions": 0,
                        "client": pvn_client,
                        "burned_ips": set(),
                        "need_rotate": False,
                        "fail_count": 0,
                    }

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, max(1, len(proxyvn_p_keys)))) as _pool_ex:
                    for _k, _st in _pool_ex.map(_init_one_pvn, proxyvn_p_keys):
                        shared_proxyvn_state[_k] = _st

            shared_psocks5_state = {}
            if provider_name == "proxysocks5" and (effective_psocks5_keys or psocks5_keys):
                psocks5_p_keys = effective_psocks5_keys if effective_psocks5_keys else psocks5_keys
                for cand_k in psocks5_p_keys:
                    p_client = ProxySocks5Client(cand_k, user_token=getattr(self, "proxysocks5_user_token", None))
                    inf = p_client.get_current_proxy()
                    if not inf.get("success") or not (inf.get("http") or inf.get("socks5")):
                        inf = p_client.get_new_proxy(fallback_current=True)
                    p_str = inf.get("http") or inf.get("socks5")
                    p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                    cur_port = inf.get("port_http") or (p_item.port if p_item else "")
                    cur_ip = f"{inf.get('host', 'sv1.proxysocks5.vn')}:{cur_port}" if cur_port else (inf.get("ip") or (p_item.host if p_item else ""))
                    loc = inf.get("location", "Vietnam")
                    if p_item and cur_ip:
                        p_item.raw = cand_k
                        p_item.country = loc
                        p_item.country_code = normalize_country_code(loc) or "VN"
                        p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                        p_item.real_ip = cur_ip
                    shared_psocks5_state[cand_k] = {
                        "lock": threading.Lock(),
                        "session_lock": threading.Lock(),
                        "proxy_obj": p_item,
                        "cur_ip": cur_ip,
                        "location": loc,
                        "rot_time": time.time(),
                        "last_fetch": time.time(),
                        "active_sessions": 0,
                        "client": p_client,
                    }

            shared_mproxy_state = {}
            if provider_name == "mproxy" and (effective_mproxy_keys or mproxy_keys):
                mproxy_p_keys = effective_mproxy_keys if effective_mproxy_keys else mproxy_keys
                m_tok = getattr(self, "mproxy_token", "") or self.config.get("mproxy_token", "")
                for cand_k in mproxy_p_keys:
                    mp_client = MproxyClient(m_tok, key_code=cand_k if cand_k != m_tok else None)
                    inf = mp_client.get_current_proxy()
                    if not inf.get("success") or not (inf.get("http") or inf.get("proxy")):
                        inf = mp_client.get_new_proxy(fallback_current=True)
                    p_str = inf.get("http") or inf.get("proxy")
                    p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                    cur_ip = inf.get("real_ip") or inf.get("server") or inf.get("ip") or (f"{p_item.host}:{p_item.port}" if p_item else "")
                    loc = inf.get("location", "Vietnam")
                    if p_item and cur_ip:
                        p_item.raw = mp_client.key_code or mp_client.token
                        p_item.country = loc
                        p_item.country_code = normalize_country_code(loc) or "VN"
                        p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                        p_item.real_ip = cur_ip
                    shared_mproxy_state[cand_k] = {
                        "lock": threading.Lock(),
                        "session_lock": threading.Lock(),
                        "proxy_obj": p_item,
                        "cur_ip": cur_ip,
                        "location": loc,
                        "rot_time": time.time(),
                        "last_fetch": time.time(),
                        "active_sessions": 0,
                        "client": mp_client,
                    }

            def single_worker(worker_id: int):
                nonlocal total_attempts, successful_accs, nvr_idx
                # Cá nhân hóa từng luồng - bắt được proxy là chạy ngay lập tức, không để các luồng đợi nhau!

                reg_svc = RegistrationService(
                    event_callback=lambda evt, data: self.handle_service_event(worker_id, evt, data),
                    timeout=25
                )

                # 1. Khởi tạo Proxy song song cho riêng luồng này (Bắt được là reg luôn, không chờ luồng khác!)
                proxy_obj = None
                assigned_ip = "Direct"
                kiot_client = None
                pvn_client = None
                mp_client = None
                key_label = ""
                k_state = None
                p_state = None

                if provider_name in ("kiotproxy", "kiotproxy_current") and (effective_kiot_keys or kiot_keys):
                    keys_pool = effective_kiot_keys if effective_kiot_keys else kiot_keys
                    key_idx = (worker_id - 1) % len(keys_pool)
                    k = keys_pool[key_idx]
                    key_label = f"Key #{key_idx + 1}"
                    base_k = k
                    base_key_idx = key_idx
                    base_key_label = key_label
                    kiot_client = KiotProxyClient(k)

                    if k not in shared_kiot_state:
                        k_client = KiotProxyClient(k)
                        shared_kiot_state[k] = {
                            "lock": threading.Lock(),
                            "session_lock": threading.Lock(),
                            "proxy_obj": None,
                            "cur_ip": "",
                            "last_working_proxy": None,
                            "last_working_ip": "",
                            "location": "Vietnam",
                            "rot_time": time.time(),
                            "last_fetch": time.time(),
                            "next_rotate_allowed_at": 0.0,
                            "rot_lock": threading.Lock(),
                            "active_sessions": 0,
                            "client": k_client,
                        }
                    k_state = shared_kiot_state[k]
                    kiot_client = k_state.get("client") or KiotProxyClient(k)

                    with k_state["lock"]:
                        cached_cand = k_state.get("proxy_obj") or k_state.get("last_working_proxy")
                        if cached_cand:
                            p_item = copy.copy(cached_cand)
                            cur_ip = k_state.get("cur_ip") or k_state.get("last_working_ip")
                            info = {"location": k_state.get("location", "Vietnam"), "ip": cur_ip}
                        else:
                            p_item = None
                            cur_ip = None
                            info = {}

                    if not p_item or not cur_ip:
                        try:
                            info = kiot_client.get_current_proxy(force_refresh=True)
                            if not info.get("success") or not info.get("http"):
                                info = kiot_client.get_new_proxy(fallback_current=True)
                            if not info.get("success") or not info.get("http"):
                                cached = KiotProxyClient.get_cached_proxy(k, max_age=300.0)
                                if cached and cached.get("http"):
                                    info = cached
                            p_item = ProxyManager.parse_proxy(info.get("http")) if (info and info.get("http")) else None
                            cur_ip = info.get("ip") or (p_item.host if p_item else "")
                        except Exception:
                            pass

                        if p_item and cur_ip:
                            p_item.raw = k
                            p_item.country = info.get("location", "Vietnam")
                            p_item.country_code = normalize_country_code(p_item.country) or "VN"
                            p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                            p_item.real_ip = cur_ip
                            with k_state["lock"]:
                                k_state["proxy_obj"] = p_item
                                k_state["cur_ip"] = cur_ip
                                k_state["last_working_proxy"] = copy.copy(p_item)
                                k_state["last_working_ip"] = cur_ip
                                k_state["location"] = p_item.country
                                k_state["rot_time"] = time.time()
                                k_state["last_fetch"] = time.time()
                        else:
                            with k_state["lock"]:
                                if k_state.get("proxy_obj") and k_state.get("cur_ip"):
                                    p_item = copy.copy(k_state["proxy_obj"])
                                    cur_ip = k_state["cur_ip"]
                                    info = {"location": k_state.get("location", "Vietnam"), "ip": cur_ip}

                    need_alt_ip = (len(keys_pool) < actual_threads)
                    if p_item and cur_ip:
                        if ip_registry:
                            ip_registry.lease_ip(worker_id, cur_ip, force=True)
                        p_item.raw = k
                        p_item.country = info.get("location", "Vietnam")
                        p_item.real_ip = cur_ip
                        proxy_obj = p_item
                        assigned_ip = cur_ip
                        display_ip = f"{p_item.host}:{p_item.port}" if getattr(p_item, "port", None) else cur_ip
                        self._worker_proxy_map[worker_id] = display_ip
                        share_tag = f" (Chia sẻ {key_label})" if need_alt_ip else ""
                        self.event_queue.put(("log", {
                            "message": f"[KiotProxy] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP Kiot: {self.mask_ip(cur_ip)} ({info.get('location', 'Vietnam')}){share_tag} ➔ Sẵn sàng reg!",
                            "tag": "success"
                        }))
                    else:
                        proxy_obj = None
                        assigned_ip = ""
                        self.event_queue.put(("log", {
                            "message": f"[KiotProxy] ⏳ Luồng {worker_id} ({key_label}): Đang chờ IP KiotProxy sẵn sàng (Bảo vệ IP máy, chỉ dùng KiotProxy chuẩn)...",
                            "tag": "warning"
                        }))

                elif provider_name == "proxysocks5" and (effective_psocks5_keys or psocks5_keys):
                    psocks5_client = None
                    keys_pool = effective_psocks5_keys if effective_psocks5_keys else psocks5_keys
                    key_idx = (worker_id - 1) % len(keys_pool)
                    k = keys_pool[key_idx]
                    key_label = f"Key #{key_idx + 1}"
                    base_k = k
                    base_key_idx = key_idx
                    base_key_label = key_label
                    psocks5_client = ProxySocks5Client(k, user_token=getattr(self, "proxysocks5_user_token", None))

                    if k not in shared_psocks5_state:
                        shared_psocks5_state[k] = {
                            "lock": threading.Lock(),
                            "session_lock": threading.Lock(),
                            "proxy_obj": None,
                            "cur_ip": "",
                            "location": "Vietnam",
                            "rot_time": time.time(),
                            "last_fetch": time.time(),
                            "active_sessions": 0,
                        }
                    k_state = shared_psocks5_state[k]

                    with k_state["lock"]:
                        cached_p = k_state.get("proxy_obj")
                        cached_ip = k_state.get("cur_ip")
                        consumed = k_state.setdefault("consumed_ips", set())
                        can_use_cached = cached_p and cached_ip and (alloc_mode == "shared" or cached_ip not in consumed) and (time.time() - k_state.get("last_fetch", 0.0)) < 300.0
                        if can_use_cached:
                            p_item = copy.copy(cached_p)
                            cur_ip = cached_ip
                            if alloc_mode == "dedicated":
                                consumed.add(cur_ip)
                            info = {"location": k_state.get("location", "Vietnam"), "ip": cur_ip}
                        else:
                            p_item = None
                            cur_ip = None
                            info = {}

                    if not p_item or not cur_ip:
                        info = psocks5_client.get_current_proxy()
                        if not info.get("success") or not (info.get("http") or info.get("socks5")):
                            info = psocks5_client.get_new_proxy(fallback_current=True)

                        p_str = info.get("http") or info.get("socks5")
                        p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                        cur_port = info.get("port_http") or (p_item.port if p_item else "")
                        cur_ip = f"{info.get('host', 'sv1.proxysocks5.vn')}:{cur_port}" if cur_port else (info.get("ip") or (p_item.host if p_item else ""))

                        retry_psocks5_init = 0
                        while (not p_item or not cur_ip) and retry_psocks5_init < 2 and not self.stop_event.is_set():
                            retry_psocks5_init += 1
                            time.sleep(0.5)
                            info = psocks5_client.get_current_proxy()
                            if not info.get("success") or not (info.get("http") or info.get("socks5")):
                                info = psocks5_client.get_new_proxy(fallback_current=True)
                            p_str = info.get("http") or info.get("socks5")
                            p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                            cur_port = info.get("port_http") or (p_item.port if p_item else "")
                            cur_ip = f"{info.get('host', 'sv1.proxysocks5.vn')}:{cur_port}" if cur_port else (info.get("ip") or (p_item.host if p_item else ""))

                        if p_item and cur_ip:
                            p_item.raw = k
                            p_item.country = info.get("location", "Vietnam")
                            p_item.country_code = normalize_country_code(p_item.country) or "VN"
                            p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                            p_item.real_ip = cur_ip
                            with k_state["lock"]:
                                k_state["proxy_obj"] = p_item
                                k_state["cur_ip"] = cur_ip
                                k_state["location"] = p_item.country
                                k_state["rot_time"] = time.time()
                                k_state["last_fetch"] = time.time()
                        else:
                            with k_state["lock"]:
                                if k_state.get("proxy_obj") and k_state.get("cur_ip"):
                                    p_item = copy.copy(k_state["proxy_obj"])
                                    cur_ip = k_state["cur_ip"]
                                    info = {"location": k_state.get("location", "Vietnam"), "ip": cur_ip}

                    need_alt_ip = (len(keys_pool) < actual_threads)
                    if p_item and cur_ip:
                        if ip_registry:
                            ip_registry.lease_ip(worker_id, cur_ip, force=True)
                        p_item.raw = k
                        p_item.country = info.get("location", "Vietnam")
                        p_item.real_ip = cur_ip
                        proxy_obj = p_item
                        assigned_ip = cur_ip
                        display_ip = f"{p_item.host}:{p_item.port}" if getattr(p_item, "port", None) else cur_ip
                        self._worker_proxy_map[worker_id] = display_ip
                        share_tag = f" (Chia sẻ {key_label})" if need_alt_ip else ""
                        self.event_queue.put(("log", {
                            "message": f"[ProxySocks5] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP: {self.mask_ip(cur_ip)} ({info.get('location', 'Vietnam')}){share_tag} ➔ Sẵn sàng reg!",
                            "tag": "success"
                        }))
                    else:
                        proxy_obj = None
                        assigned_ip = ""
                        self.event_queue.put(("log", {
                            "message": f"[ProxySocks5] ⏳ Luồng {worker_id} ({key_label}): Đang chờ IP ProxySocks5 sẵn sàng...",
                            "tag": "warning"
                        }))

                elif provider_name == "mproxy" and (effective_mproxy_keys or mproxy_keys):
                    keys_pool = effective_mproxy_keys if effective_mproxy_keys else mproxy_keys
                    key_idx = (worker_id - 1) % len(keys_pool)
                    k = keys_pool[key_idx]
                    key_label = f"Cổng #{key_idx + 1}"
                    base_k = k
                    base_key_idx = key_idx
                    base_key_label = key_label
                    m_tok = getattr(self, "mproxy_token", "") or self.config.get("mproxy_token", "")
                    if k not in shared_mproxy_state:
                        mp_client = MproxyClient(m_tok, key_code=k if k != m_tok else None)
                        shared_mproxy_state[k] = {
                            "lock": threading.Lock(),
                            "session_lock": threading.Lock(),
                            "proxy_obj": None,
                            "cur_ip": "",
                            "location": "Vietnam",
                            "rot_time": time.time(),
                            "last_fetch": time.time(),
                            "active_sessions": 0,
                            "client": mp_client,
                        }
                    k_state = shared_mproxy_state[k]
                    mp_client = k_state.get("client") or MproxyClient(m_tok, key_code=k if k != m_tok else None)
                    p_item = None
                    cur_ip = ""
                    if k_state:
                        with k_state["lock"]:
                            consumed = k_state.setdefault("consumed_ips", set())
                            can_use_cached = k_state.get("proxy_obj") and k_state.get("cur_ip") and (alloc_mode == "shared" or k_state["cur_ip"] not in consumed)
                            if can_use_cached:
                                p_item = copy.copy(k_state["proxy_obj"])
                                cur_ip = k_state["cur_ip"]
                                if alloc_mode == "dedicated":
                                    consumed.add(cur_ip)
                    if not p_item or not cur_ip:
                        try:
                            info = mp_client.get_current_proxy(force_refresh=True)
                            if not info.get("success") or not (info.get("http") or info.get("proxy")):
                                info = mp_client.get_new_proxy(fallback_current=True)
                            p_str = info.get("http") or info.get("proxy")
                            p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                            cur_ip = info.get("real_ip") or info.get("server") or info.get("ip") or (f"{p_item.host}:{p_item.port}" if p_item else "")
                            loc = info.get("location", "Vietnam")
                            if p_item and cur_ip:
                                p_item.raw = mp_client.key_code or mp_client.token
                                p_item.country = loc
                                p_item.country_code = normalize_country_code(loc) or "VN"
                                p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                                p_item.real_ip = cur_ip
                                if k_state:
                                    with k_state["lock"]:
                                        k_state["proxy_obj"] = p_item
                                        k_state["cur_ip"] = cur_ip
                                        k_state["location"] = loc
                        except Exception as e_init:
                            logger.debug(f"mProxy init error: {e_init}")
                    need_alt_ip = (len(keys_pool) < actual_threads)
                    if p_item and cur_ip:
                        if ip_registry:
                            ip_registry.lease_ip(worker_id, cur_ip, force=True)
                        proxy_obj = p_item
                        assigned_ip = cur_ip
                        display_ip = f"{p_item.host}:{p_item.port}" if getattr(p_item, "port", None) else cur_ip
                        self._worker_proxy_map[worker_id] = display_ip
                        share_tag = f" (Chia sẻ {key_label})" if need_alt_ip else ""
                        self.event_queue.put(("log", {
                            "message": f"[mProxy] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP 4G: {self.mask_ip(cur_ip)} ({p_item.country}){share_tag} ➔ Sẵn sàng reg!",
                            "tag": "success"
                        }))
                    else:
                        proxy_obj = None
                        assigned_ip = ""
                        self.event_queue.put(("log", {
                            "message": f"[mProxy] ⏳ Luồng {worker_id} ({key_label}): Đang chờ IP mProxy 4G sẵn sàng...",
                            "tag": "warning"
                        }))

                elif provider_name == "proxyvn" and (effective_proxyvn_keys or proxyvn_keys):
                    keys_pool = effective_proxyvn_keys if effective_proxyvn_keys else proxyvn_keys
                    key_idx = (worker_id - 1) % len(keys_pool)
                    k = keys_pool[key_idx]
                    key_label = f"Key #{key_idx + 1}"
                    base_k = k
                    base_key_idx = key_idx
                    base_key_label = key_label
                    if k not in shared_proxyvn_state:
                        pvn_client = ProxyVNClient(k)
                        shared_proxyvn_state[k] = {
                            "lock": threading.Lock(),
                            "session_lock": threading.Lock(),
                            "proxy_obj": None,
                            "cur_ip": "",
                            "last_working_proxy": None,
                            "last_working_ip": "",
                            "location": "Vietnam",
                            "carrier": "",
                            "rot_time": time.time(),
                            "last_fetch": time.time(),
                            "next_rotate_allowed_at": 0.0,
                            "rot_lock": threading.Lock(),
                            "active_sessions": 0,
                            "client": pvn_client,
                        }
                    k_state = shared_proxyvn_state[k]
                    pvn_client = k_state.get("client") or ProxyVNClient(k)
                    p_item = None
                    cur_ip = ""
                    if k_state:
                        with k_state["lock"]:
                            cached_cand = k_state.get("proxy_obj") or k_state.get("last_working_proxy")
                            if cached_cand:
                                p_item = copy.copy(cached_cand)
                                cur_ip = k_state.get("cur_ip") or k_state.get("last_working_ip")
                                info = {"location": k_state.get("location", "Vietnam"), "ip": cur_ip, "carrier": k_state.get("carrier", "")}
                            else:
                                p_item = None
                                cur_ip = None
                                info = {}

                    if not p_item or not cur_ip:
                        try:
                            info = pvn_client.get_current_proxy(force_refresh=True)
                            if not info.get("success") or not info.get("http"):
                                info = pvn_client.get_new_proxy(fallback_current=True)
                            if not info.get("success") or not info.get("http"):
                                cached = ProxyVNClient.get_cached_proxy(k, max_age=300.0)
                                if cached and cached.get("http"):
                                    info = cached
                            p_str = info.get("http") if info else None
                            p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                            cur_ip = info.get("ip") or (p_item.host if p_item else "")
                            loc = info.get("location", "Vietnam") if info else "Vietnam"
                            if p_item and cur_ip:
                                p_item.raw = k
                                p_item.country = loc
                                p_item.country_code = normalize_country_code(loc) or "VN"
                                p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                                p_item.real_ip = cur_ip
                                info = {"location": loc, "ip": cur_ip, "carrier": info.get("carrier", "")}
                                if k_state:
                                    with k_state["lock"]:
                                        k_state["proxy_obj"] = p_item
                                        k_state["cur_ip"] = cur_ip
                                        k_state["last_working_proxy"] = copy.copy(p_item)
                                        k_state["last_working_ip"] = cur_ip
                                        k_state["location"] = loc
                        except Exception:
                            pass

                    if not p_item or not cur_ip:
                        try:
                            t_rot_lock = k_state.setdefault("rot_lock", threading.Lock()) if k_state else threading.Lock()
                            with t_rot_lock:
                                with k_state["lock"]:
                                    if k_state.get("proxy_obj") and k_state.get("cur_ip"):
                                        p_item = copy.copy(k_state["proxy_obj"])
                                        cur_ip = k_state["cur_ip"]
                                        info = {"location": k_state.get("location", "Vietnam"), "ip": cur_ip, "carrier": k_state.get("carrier", "")}
                                if not p_item or not cur_ip:
                                    info = pvn_client.get_current_proxy(force_refresh=False)
                                    if not info.get("success") or not info.get("http"):
                                        info = pvn_client.get_new_proxy(fallback_current=True)
                                    p_str = info.get("http")
                                    p_item = ProxyManager.parse_proxy(p_str) if p_str else None
                                    cur_ip = info.get("ip") or (p_item.host if p_item else "")
                                    loc = info.get("location", "Vietnam")
                                    if p_item and cur_ip:
                                        p_item.raw = k
                                        p_item.country = loc
                                        p_item.country_code = normalize_country_code(loc) or "VN"
                                        p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=cur_ip)
                                        p_item.real_ip = cur_ip
                                        if k_state:
                                            with k_state["lock"]:
                                                k_state["proxy_obj"] = p_item
                                                k_state["cur_ip"] = cur_ip
                                                k_state["last_working_proxy"] = copy.copy(p_item)
                                                k_state["last_working_ip"] = cur_ip
                                                k_state["location"] = loc
                                                k_state["carrier"] = info.get("carrier", "")
                                                k_state["rot_time"] = time.time()
                                                k_state["last_fetch"] = time.time()
                        except Exception as e_init:
                            logger.debug(f"ProxyVN init error: {e_init}")

                    need_alt_ip = (len(keys_pool) < actual_threads)
                    if p_item and cur_ip:
                        if ip_registry:
                            ip_registry.lease_ip(worker_id, cur_ip, force=True)
                        proxy_obj = p_item
                        assigned_ip = cur_ip
                        display_ip = f"{p_item.host}:{p_item.port}" if getattr(p_item, "port", None) else cur_ip
                        self._worker_proxy_map[worker_id] = display_ip
                        share_tag = f" (Chia sẻ {key_label})" if need_alt_ip else ""
                        carrier_str = f" | {info.get('carrier')}" if info.get('carrier') else ""
                        self.event_queue.put(("log", {
                            "message": f"[Proxy.vn] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP: {self.mask_ip(cur_ip)} ({p_item.country}{carrier_str}){share_tag} ➔ Sẵn sàng reg!",
                            "tag": "success"
                        }))
                    else:
                        proxy_obj = None
                        assigned_ip = ""
                        self.event_queue.put(("log", {
                            "message": f"[Proxy.vn] ⏳ Luồng {worker_id} ({key_label}): Đang chờ IP Proxy.vn sẵn sàng...",
                            "tag": "warning"
                        }))

                elif provider_name in ("free_proxy_live", "free_proxy_cached", "free_proxy") and free_mgr:
                    is_fresh_mode = provider_name in ("free_proxy", "free_proxy_live")
                    p_label = "Proxy Free Cào Mới" if is_fresh_mode else "Proxy Free Kho Cache"
                    if worker_id <= 5 or worker_id % 50 == 0:
                        self.event_queue.put(("log", {
                            "message": f"[{p_label}] 🌐 Luồng {worker_id}: Đang lấy proxy LIVE Facebook...",
                            "tag": "info"
                        }))
                    p_free = free_mgr.get_verified_live_proxy(worker_id=worker_id, timeout=2.0, registry=ip_registry, worker_count=actual_threads)
                    if not p_free:
                        p_free = free_mgr.claim_instant_candidate(worker_id=worker_id, registry=ip_registry)
                    if not p_free:
                        wait_start = time.time()
                        wait_loop_cnt = 0
                        while (time.time() - wait_start) < 15.0 and not self.stop_event.is_set():
                            time.sleep(1.0)
                            wait_loop_cnt += 1
                            if wait_loop_cnt % 3 == 0 and (worker_id <= 5 or worker_id % 20 == 0):
                                self.event_queue.put(("log", {
                                    "message": f"[{p_label}] ⏳ Luồng {worker_id}: Đang quét tìm Proxy LIVE Facebook...",
                                    "tag": "info"
                                }))
                            p_free = free_mgr.get_verified_live_proxy(worker_id=worker_id, timeout=1.5, registry=ip_registry)
                            if not p_free:
                                p_free = free_mgr.claim_instant_candidate(worker_id=worker_id, registry=ip_registry)
                            if p_free:
                                break

                    if p_free:
                        if not getattr(p_free, "geo_profile", None):
                            try:
                                p_free.geo_profile = GeoTelephonyResolver.resolve_ip(p_free.real_ip or p_free.host, hint_country=getattr(p_free, "country", None))
                                if p_free.geo_profile:
                                    p_free.country = p_free.geo_profile.country_name
                                    p_free.country_code = p_free.geo_profile.country_code
                            except Exception:
                                pass
                        proxy_obj = p_free
                        assigned_ip = p_free.host
                        if ip_registry and not ip_registry._leased_ips.get(worker_id):
                            ip_registry.lease_ip(worker_id, p_free.real_ip or p_free.host, force=True)
                        lat = getattr(p_free, "latency", 0.5)
                        src_lbl = getattr(p_free, "source_label", "Online")
                        src_str = f" [{src_lbl}]" if src_lbl else ""
                        self.event_queue.put(("log", {
                            "message": f"[{p_label}] 🛡️ Luồng {worker_id} ➔ Bốc Proxy LIVE Facebook{src_str}: {self.mask_ip(p_free.host)}:{p_free.port} (Ping {lat}s | Không trùng) ➔ Khởi tạo phiên ngay!",
                            "tag": "success"
                        }))
                    else:
                        proxy_obj = None
                        assigned_ip = ""
                        self.event_queue.put(("log", {
                            "message": f"[{p_label}] ⏳ Luồng {worker_id}: Đang chờ Proxy LIVE Facebook đạt chuẩn (Bảo vệ IP máy, không chạy Direct)...",
                            "tag": "warning"
                        }))

                elif provider_name == "proxy_list":
                    p_obj = proxy_manager.get_worker_proxy(worker_id, registry=ip_registry)
                    if p_obj:
                        if not getattr(p_obj, "geo_profile", None):
                            try:
                                p_obj.geo_profile = GeoTelephonyResolver.resolve_ip(p_obj.real_ip or p_obj.host, hint_country=getattr(p_obj, "country", None))
                                if p_obj.geo_profile:
                                    p_obj.country = p_obj.geo_profile.country_name
                                    p_obj.country_code = p_obj.geo_profile.country_code
                            except Exception:
                                pass
                        proxy_obj = p_obj
                        assigned_ip = p_obj.host
                        self.event_queue.put(("log", {
                            "message": f"[Proxy List] ✅ Luồng {worker_id} ➔ Proxy ngẫu nhiên: {self.mask_ip(p_obj.host)}:{p_obj.port}",
                            "tag": "info"
                        }))

                elif provider_name == "none":
                    proxy_obj = None
                    assigned_ip = "Direct"

                # 2. Vòng lặp thực hiện reg / xác minh tài khoản
                last_wait_proxy_log = 0.0
                key_held_lock = None
                while not self.stop_event.is_set():
                    # Đảm bảo luồng Free Proxy luôn có proxy trước khi gửi request tới Facebook:
                    if provider_name in ("free_proxy", "free_proxy_live", "free_proxy_cached") and not proxy_obj:
                        p_free = free_mgr.get_verified_live_proxy(worker_id=worker_id, timeout=2.0, registry=ip_registry)
                        if not p_free:
                            p_free = free_mgr.claim_instant_candidate(worker_id=worker_id, registry=ip_registry)
                        if p_free:
                            if not getattr(p_free, "geo_profile", None):
                                try:
                                    p_free.geo_profile = GeoTelephonyResolver.resolve_ip(p_free.real_ip or p_free.host, hint_country=getattr(p_free, "country", None))
                                    if p_free.geo_profile:
                                        p_free.country = p_free.geo_profile.country_name
                                        p_free.country_code = p_free.geo_profile.country_code
                                except Exception:
                                    pass
                            proxy_obj = p_free
                            assigned_ip = p_free.host
                            if ip_registry and not ip_registry._leased_ips.get(worker_id):
                                ip_registry.lease_ip(worker_id, p_free.real_ip or p_free.host, force=True)
                            try:
                                self.append_live_proxies_to_file([p_free])
                            except Exception:
                                pass
                        else:
                            now_wait_t = time.time()
                            if (worker_id == 1 or worker_id % 25 == 0) and (now_wait_t - last_wait_proxy_log > 15.0):
                                last_wait_proxy_log = now_wait_t
                                self.event_queue.put(("log", {
                                    "message": f"[{p_label}] ⏳ Luồng {worker_id}: Đang chờ Proxy LIVE Facebook đạt chuẩn tạo phiên...",
                                    "tag": "info"
                                }))
                            time.sleep(2.0)
                            continue

                    if provider_name in ("kiotproxy", "kiotproxy_current") and not proxy_obj:
                        if k_state:
                            with k_state["lock"]:
                                p_src = k_state.get("proxy_obj") or k_state.get("last_working_proxy")
                                ip_src = k_state.get("cur_ip") or k_state.get("last_working_ip")
                                if p_src:
                                    proxy_obj = copy.copy(p_src)
                                    assigned_ip = ip_src or ""
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                        if not proxy_obj and kiot_client:
                            try:
                                info = kiot_client.get_current_proxy(force_refresh=True)
                                if not info.get("http"):
                                    info = kiot_client.get_new_proxy(fallback_current=True)
                                if info.get("http"):
                                    p_item = ProxyManager.parse_proxy(info["http"])
                                    if p_item:
                                        p_item.raw = k
                                        p_item.country = info.get("location", "Vietnam")
                                        p_item.country_code = normalize_country_code(p_item.country) or "VN"
                                        p_item.real_ip = info.get("ip") or p_item.host
                                        p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=p_item.real_ip)
                                        proxy_obj = p_item
                                        assigned_ip = p_item.real_ip
                                        if ip_registry:
                                            ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                        with k_state["lock"]:
                                            k_state["proxy_obj"] = p_item
                                            k_state["cur_ip"] = assigned_ip
                                        self.event_queue.put(("log", {
                                            "message": f"[KiotProxy] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP: {self.mask_ip(assigned_ip)} ({p_item.country}) ➔ Tiếp tục reg!",
                                            "tag": "success"
                                        }))
                            except Exception:
                                pass
                        if not proxy_obj:
                            self.event_queue.put(("log", {
                                "message": f"[KiotProxy] ⚠️ Luồng {worker_id} ({key_label}): Chưa có IP KiotProxy mới. Tạm hoãn lượt này để bảo vệ IP máy.",
                                "tag": "warning"
                            }))
                            time.sleep(1.0)
                            continue

                    if provider_name == "proxysocks5" and not proxy_obj:
                        if k_state:
                            with k_state["lock"]:
                                if k_state.get("proxy_obj"):
                                    proxy_obj = copy.copy(k_state["proxy_obj"])
                                    assigned_ip = k_state.get("cur_ip", "")
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                        psocks5_wait_start = time.time()
                        while (time.time() - psocks5_wait_start) < 20.0 and not self.stop_event.is_set():
                            time.sleep(2.0)
                            info = psocks5_client.get_current_proxy(force_refresh=True) if psocks5_client else {}
                            if not (info.get("http") or info.get("socks5")) and psocks5_client:
                                info = psocks5_client.get_new_proxy(fallback_current=True)
                            p_str = info.get("http") or info.get("socks5")
                            if p_str:
                                p_item = ProxyManager.parse_proxy(p_str)
                                if p_item:
                                    p_item.raw = k
                                    p_item.country = info.get("location", "Vietnam")
                                    p_item.country_code = normalize_country_code(p_item.country) or "VN"
                                    p_item.real_ip = info.get("ip") or p_item.host
                                    p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=p_item.real_ip)
                                    proxy_obj = p_item
                                    assigned_ip = p_item.real_ip
                                    ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                    self.event_queue.put(("log", {
                                        "message": f"[ProxySocks5] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP: {self.mask_ip(assigned_ip)} ({p_item.country}) ➔ Tiếp tục reg!",
                                        "tag": "success"
                                    }))
                                    break
                        if not proxy_obj:
                            self.event_queue.put(("log", {
                                "message": f"[ProxySocks5] ⚠️ Luồng {worker_id} ({key_label}): Chưa có IP ProxySocks5 mới. Tạm hoãn lượt này.",
                                "tag": "warning"
                            }))
                            time.sleep(3.0)
                            continue
                    if provider_name == "proxyvn" and not proxy_obj:
                        if k_state:
                            with k_state["lock"]:
                                p_src = k_state.get("proxy_obj") or k_state.get("last_working_proxy")
                                ip_src = k_state.get("cur_ip") or k_state.get("last_working_ip")
                                if p_src:
                                    proxy_obj = copy.copy(p_src)
                                    assigned_ip = ip_src or ""
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                        if not proxy_obj and pvn_client:
                            try:
                                info = pvn_client.get_current_proxy(force_refresh=True)
                                if not info.get("http"):
                                    info = pvn_client.get_new_proxy(fallback_current=True)
                                if info.get("http"):
                                    p_item = ProxyManager.parse_proxy(info["http"])
                                    if p_item:
                                        p_item.raw = k
                                        p_item.country = info.get("location", "Vietnam")
                                        p_item.country_code = normalize_country_code(p_item.country) or "VN"
                                        p_item.real_ip = info.get("ip") or p_item.host
                                        p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=p_item.real_ip)
                                        proxy_obj = p_item
                                        assigned_ip = p_item.real_ip
                                        if ip_registry:
                                            ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                        with k_state["lock"]:
                                            k_state["proxy_obj"] = p_item
                                            k_state["cur_ip"] = assigned_ip
                                        self.event_queue.put(("log", {
                                            "message": f"[Proxy.vn] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP: {self.mask_ip(assigned_ip)} ({p_item.country}) ➔ Tiếp tục reg!",
                                            "tag": "success"
                                        }))
                            except Exception:
                                pass
                        if not proxy_obj:
                            self.event_queue.put(("log", {
                                "message": f"[Proxy.vn] ⚠️ Luồng {worker_id} ({key_label}): Chưa có IP Proxy.vn mới. Tạm hoãn lượt này.",
                                "tag": "warning"
                            }))
                            time.sleep(1.0)
                            continue

                    if provider_name == "mproxy" and not proxy_obj:
                        if k_state:
                            with k_state["lock"]:
                                if k_state.get("proxy_obj"):
                                    proxy_obj = copy.copy(k_state["proxy_obj"])
                                    assigned_ip = k_state.get("cur_ip", "")
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                        mproxy_wait_start = time.time()
                        m_tok = getattr(self, "mproxy_token", "") or self.config.get("mproxy_token", "")
                        while (time.time() - mproxy_wait_start) < 20.0 and not self.stop_event.is_set():
                            time.sleep(2.0)
                            info = mp_client.get_current_proxy(force_refresh=True) if mp_client else {}
                            if not (info.get("http") or info.get("proxy")) and mp_client:
                                info = mp_client.get_new_proxy(fallback_current=True)
                            p_str = info.get("http") or info.get("proxy")
                            if p_str:
                                p_item = ProxyManager.parse_proxy(p_str)
                                if p_item:
                                    p_item.raw = mp_client.key_code or mp_client.token
                                    p_item.country = info.get("location", "Vietnam")
                                    p_item.country_code = normalize_country_code(p_item.country) or "VN"
                                    p_item.real_ip = info.get("real_ip") or info.get("server") or info.get("ip") or (f"{p_item.host}:{p_item.port}" if getattr(p_item, "port", None) else p_item.host)
                                    p_item.geo_profile = GeoTelephonyResolver.get_profile_for_country(p_item.country_code, ip=p_item.real_ip)
                                    proxy_obj = p_item
                                    assigned_ip = p_item.real_ip
                                    display_ip = f"{p_item.host}:{p_item.port}" if getattr(p_item, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                    self.event_queue.put(("log", {
                                        "message": f"[mProxy] ✅ Luồng {worker_id} ➔ {key_label} ➔ IP 4G: {self.mask_ip(assigned_ip)} ({p_item.country}) ➔ Tiếp tục reg!",
                                        "tag": "success"
                                    }))
                                    break
                        if not proxy_obj:
                            self.event_queue.put(("log", {
                                "message": f"[mProxy] ⚠️ Luồng {worker_id} ({key_label}): Chưa có IP mProxy 4G mới. Tạm hoãn lượt này để bảo vệ IP máy.",
                                "tag": "warning"
                            }))
                            time.sleep(3.0)
                            continue
                    if provider_name == 'proxy_list' and not proxy_obj:
                        p_obj = proxy_manager.get_worker_proxy(worker_id, registry=ip_registry)
                        if p_obj:
                            if not getattr(p_obj, 'geo_profile', None):
                                try:
                                    p_obj.geo_profile = GeoTelephonyResolver.resolve_ip(p_obj.real_ip or p_obj.host, hint_country=getattr(p_obj, 'country', None))
                                    if p_obj.geo_profile:
                                        p_obj.country = p_obj.geo_profile.country_name
                                        p_obj.country_code = p_obj.geo_profile.country_code
                                except Exception:
                                    pass
                            proxy_obj = p_obj
                            assigned_ip = p_obj.host
                        else:
                            self.event_queue.put(('log', {
                                'message': f"[Proxy List] ⏳ Luồng {worker_id}: Đang chờ proxy khả dụng trong file...",
                                'tag': 'warning'
                            }))
                            time.sleep(3.0)
                            continue
# Chế độ chia đều: Chạy song song toàn bộ luồng đồng thời, không dùng khóa nghẽn session_lock

                    # Đồng bộ proxy mới nhất từ key được cấp phát (Chống tuyệt đối việc dùng IP cũ của luồng trước)
                    if alloc_mode == "shared" and k_state and proxy_obj is None:
                        with k_state["lock"]:
                            if k_state.get("proxy_obj"):
                                proxy_obj = copy.copy(k_state["proxy_obj"])
                                assigned_ip = k_state.get("cur_ip") or proxy_obj.host
                                display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                self._worker_proxy_map[worker_id] = display_ip
                                if ip_registry:
                                    ip_registry.lease_ip(worker_id, assigned_ip, force=True)

                    curr_acc_data = None
                    if curr_reg_mode == "verify_nvr":
                        while not self.stop_event.is_set():
                            with nvr_lock:
                                if nvr_idx < len(nvr_list):
                                    if max_accs > 0 and nvr_idx >= max_accs:
                                        break
                                    now_ts = time.time()
                                    chosen_idx = -1
                                    for scan_i in range(nvr_idx, len(nvr_list)):
                                        cand = nvr_list[scan_i]
                                        cand_ready = float(cand.get("ready_at") or 0.0)
                                        if cand_ready <= 0 or now_ts >= cand_ready:
                                            chosen_idx = scan_i
                                            break
                                    if chosen_idx != -1:
                                        if chosen_idx != nvr_idx:
                                            curr_acc_data = nvr_list.pop(chosen_idx)
                                            nvr_list.insert(nvr_idx, curr_acc_data)
                                        else:
                                            curr_acc_data = nvr_list[nvr_idx]
                                        nvr_idx += 1
                                        current_num = nvr_idx
                                        break
                            if not pipeline_active:
                                break
                            if max_accs > 0 and successful_accs >= max_accs:
                                break
                            if self.stop_event.wait(timeout=1.0):
                                break
                        if not curr_acc_data:
                            break
                    else:
                        with success_lock:
                            if max_accs > 0 and successful_accs >= max_accs:
                                break
                        with attempt_lock:
                            total_attempts += 1
                            current_num = total_attempts

                    target_uid = str(curr_acc_data.get("uid", "")).strip() if (curr_reg_mode == "verify_nvr" and curr_acc_data) else ""
                    if curr_reg_mode == "verify_nvr" and target_uid:
                        self.event_queue.put(("row_state_update", {
                            "uid": target_uid,
                            "worker_id": worker_id,
                            "status": "🔄 Đang xác minh OTP...",
                            "tag": "running"
                        }))
                    acc_custom_proxy = str(curr_acc_data.get("proxy", "")).strip() if (curr_reg_mode == "verify_nvr" and curr_acc_data) else ""
                    if acc_custom_proxy:
                        eff_proxy_str = acc_custom_proxy
                        if not eff_proxy_str.startswith(("http://", "https://", "socks5://", "socks4://")):
                            eff_proxy_str = "http://" + eff_proxy_str
                        display_ip = acc_custom_proxy
                    else:
                        eff_proxy_str = proxy_obj.as_url() if proxy_obj else None
                        if proxy_obj:
                            display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else (assigned_ip or proxy_obj.host)
                        else:
                            display_ip = assigned_ip or "Direct"
                    self._worker_proxy_map[worker_id] = display_ip

                    # Xác định Target ban đầu hiển thị trên bảng, tuyệt đối không để trống gây hiện 'Chờ mail...'
                    initial_target = None
                    eff_bait_mode = curr_bait_mode or "none"
                    if curr_acc_data and curr_acc_data.get("email"):
                        initial_target = curr_acc_data.get("email")
                    elif eff_bait_mode == "gmail":
                        try:
                            from core.email_service import generate_bait_gmail_identifier
                            initial_target = generate_bait_gmail_identifier()
                        except Exception as e_bait:
                            logger.warning(f"Error generating bait gmail: {e_bait}")
                            initial_target = f"user{random.randint(10000, 99999)}@gmail.com"
                    elif eff_bait_mode == "phone":
                        initial_target = f"(L{worker_id}: Mồi SĐT...)"
                    elif curr_reg_mode in ("ios_bloks", "bloks_ios", "regfb") and curr_email_service and str(curr_email_service).lower() not in ("none", "", "disabled"):
                        initial_target = f"(L{worker_id}: Cấp {disp_name}...)"
                    else:
                        initial_target = f"(L{worker_id}: Khởi tạo...)"

                    if worker_id is not None and initial_target:
                        self._worker_target_map[worker_id] = initial_target

                    # ĐỒNG BỘ BẢNG REAL-TIME: Hiện IP Proxy đã cấp và trạng thái Đang xử lý
                    self.event_queue.put(("row_state_update", {
                        "uid": target_uid or None,
                        "worker_id": worker_id,
                        "proxy": display_ip,
                        "status": f"🔄 Luồng {worker_id}: Bắt đầu phiên reg...",
                        "target": initial_target,
                        "password": (curr_acc_data.get("password") if curr_acc_data else curr_default_pwd),
                        "tag": "running"
                    }))

                    proxy_str = eff_proxy_str

                    if curr_reg_mode == "verify_nvr" and curr_acc_data:
                        from core.email_service import get_email_provider
                        from core.nvr_verifier import verify_single_nvr_account

                        curr_srv_lower = str(curr_email_service).lower()
                        if "hotmail" in curr_srv_lower:
                            eff_mtk_dom = "hotmail.com"
                            eff_mtk_stype = "email"
                        elif "outlook" in curr_srv_lower:
                            eff_mtk_dom = "outlook.com"
                            eff_mtk_stype = "email"
                        elif "icloud" in curr_srv_lower:
                            eff_mtk_dom = "icloud.com"
                            eff_mtk_stype = "email"
                        elif "gmail" in curr_srv_lower:
                            eff_mtk_dom = "gmail.com"
                            eff_mtk_stype = "email"
                        elif "phone" in curr_srv_lower:
                            eff_mtk_dom = "hotmail.com"
                            eff_mtk_stype = "phone"
                        else:
                            eff_mtk_dom = curr_metaking_domain
                            eff_mtk_stype = curr_metaking_service_type

                        if "metaking" in curr_srv_lower:
                            email_prov = get_email_provider(
                                curr_email_service,
                                api_key=curr_metaking_api_key,
                                service_type=eff_mtk_stype,
                                server=curr_metaking_server,
                                domain=eff_mtk_dom,
                                service_id=(67 if eff_mtk_stype == "phone" else 1),
                                country_id=curr_metaking_country_id,
                                price=curr_metaking_price,
                            )
                        else:
                            email_prov = get_email_provider(curr_email_service, selected_domains=curr_selected_domains)
                        try:
                            task_input = RegistrationInput(
                                proxy=proxy_obj or proxy_str,
                                device_type=curr_device_type,
                                locale=getattr(getattr(proxy_obj, "geo_profile", None), "locale", "vi_VN") or "vi_VN",
                                password=curr_acc_data.get("password") or curr_default_pwd or None,
                                extra={
                                    "worker_id": worker_id,
                                    "reg_mode": curr_reg_mode,
                                    "legacy_verify_mode": curr_legacy_verify_mode,
                                    "email_service": curr_email_service,
                                    "dongvanfb_api_key": self.config.get("dongvanfb_api_key", ""),
                                    "email_api_key": self.config.get("dongvanfb_api_key", "") or self.config.get("email_api_key", ""),
                                    "domain": self.config.get("domain", ""),
                                    "bait_mode": eff_bait_mode,
                                    "enable_bait_retry": curr_enable_bait_retry,
                                    "bait_retries": curr_bait_retries,
                                    "use_bait_phone": (eff_bait_mode == "phone"),
                                    "use_bait_gmail": (eff_bait_mode == "gmail"),
                                    "selected_domains": curr_selected_domains,
                                    "selected_custom_domains": curr_selected_domains,
                                    "otp_timeout": curr_otp_timeout,
                                    "live_check_delay": 2.0,
                                    "verify_live_status": True,
                                    "skip_auto_file_save": True,
                                    "proxy_ip": assigned_ip,
                                    "proxy_country": getattr(getattr(proxy_obj, "geo_profile", None), "country_name", None) or (proxy_obj.country if (proxy_obj and proxy_obj.country != "Unknown") else None) or (k_state.get("location") if (isinstance(k_state, dict) and k_state) else None),
                                    "country_code": getattr(proxy_obj, "country_code", None) or (getattr(getattr(proxy_obj, "geo_profile", None), "country_code", None)),
                                    "geo_profile": getattr(proxy_obj, "geo_profile", None),
                                    "save_format": curr_save_format,
                                    "enable_2fa": curr_2fa,
                                    "anti_checkpoint_mode": curr_anti_cp,
                                    "email_integrity_guard": curr_anti_cp,
                                    "behavioral_delays": curr_anti_cp,
                                    "session_warmup": curr_anti_cp,
                                    "network_risk_check": curr_anti_cp,
                                    "extract_token": curr_extract_token,
                                    "retry_on_nvr_with_new_mail": curr_retry_on_nvr,
                                    "retry_email_service": curr_retry_email_service,
                                    "max_otp_email_retries": curr_max_email_retries,
                                    "retry_use_free_mail": curr_retry_use_free,
                                    "metaking_api_key": self.config.get("metaking_api_key", ""),
                                    "metaking_service_type": self.config.get("metaking_service_type", "email"),
                                    "metaking_server": self.config.get("metaking_server", 1),
                                    "metaking_domain": self.config.get("metaking_domain", "hotmail.com") or "hotmail.com",
                                    "metaking_service_id": (67 if ("phone" in str(curr_email_service).lower() or self.config.get("metaking_service_type") == "phone") else 1),
                                    "metaking_country_id": self.config.get("metaking_country_id", 154),
                                    "metaking_price": self.config.get("metaking_price", "low"),
                                    "proxy_provider": provider_name,
                                }
                            )
                            stagger_wait = 0.0
                            if alloc_mode == "shared" and assigned_ip and assigned_ip != "Direct":
                                with _shared_ip_gate_lock:
                                    last_req = _shared_ip_last_submit.get(assigned_ip, 0.0)
                                    now_req = time.time()
                                    elapsed_since = now_req - last_req
                                    if elapsed_since < 0.3:
                                        stagger_wait = max(0.0, min(1.0, random.uniform(0.1, 0.3) - elapsed_since))
                                    _shared_ip_last_submit[assigned_ip] = now_req + stagger_wait
                            if stagger_wait > 0:
                                time.sleep(stagger_wait)

                            if k_state:
                                with k_state["lock"]:
                                    k_state["active_sessions"] = k_state.get("active_sessions", 0) + 1
                            try:
                                res = verify_single_nvr_account(
                                    account_data=curr_acc_data,
                                    email_provider=email_prov,
                                    task_input=task_input,
                                    emit_callback=lambda evt, data: self.handle_service_event(worker_id, evt, data)
                                )
                            finally:
                                if k_state:
                                    with k_state["lock"]:
                                        k_state["active_sessions"] = max(0, k_state.get("active_sessions", 1) - 1)
                        except Exception as e:
                            res = RegistrationResult(
                                success=False,
                                status="error",
                                uid=curr_acc_data.get("uid", ""),
                                identifier=curr_acc_data.get("email") or curr_acc_data.get("uid", ""),
                                password=curr_acc_data.get("password", "") or curr_default_pwd or "",
                                error_message=str(e),
                            )
                    else:
                        is_vr_mode = (curr_reg_mode == "vr")
                        effective_use_bait = (eff_bait_mode != "none")
                        is_rand_all = (chosen_mode == "random_all")
                        is_rand_sub = (chosen_mode == "subset")

                        try:
                            task_input = RegistrationInput(
                                proxy=proxy_obj or proxy_str,
                                device_type=curr_device_type,
                                locale=getattr(getattr(proxy_obj, "geo_profile", None), "locale", "vi_VN") or "vi_VN",
                                server=("subset" if is_rand_sub else ("random" if is_rand_all else chosen_server)),
                                password=curr_default_pwd or None,
                                extra={
                                    "worker_id": worker_id,
                                    "reg_mode": curr_reg_mode,
                                    "legacy_verify_mode": curr_legacy_verify_mode,
                                    "server_mode": chosen_mode,
                                    "random_server": is_rand_all,
                                    "random_subset": is_rand_sub,
                                    "server_pool": chosen_pool if is_rand_sub else [],
                                    "bait_mode": eff_bait_mode,
                                    "bait_retries": curr_bait_retries,
                                    "enable_bait_retry": curr_enable_bait_retry,
                                    "use_bait_phone": (eff_bait_mode == "phone"),
                                    "use_bait_gmail": (eff_bait_mode == "gmail"),
                                    "bait_identifier": initial_target if ("@" in str(initial_target or "") and "(" not in str(initial_target or "")) else None,
                                    "auto_gen_phone": (eff_bait_mode == "phone"),
                                    "enable_2fa": curr_2fa,
                                    "default_password": curr_default_pwd,
                                    "email_service": curr_email_service,
                                    "dongvanfb_api_key": self.config.get("dongvanfb_api_key", ""),
                                    "email_api_key": self.config.get("dongvanfb_api_key", "") or self.config.get("email_api_key", ""),
                                    "domain": self.config.get("domain", ""),
                                    "selected_domains": curr_selected_domains,
                                    "selected_custom_domains": curr_selected_domains,
                                    "otp_timeout": curr_otp_timeout,
                                    "skip_auto_file_save": True,
                                    "anti_checkpoint_mode": curr_anti_cp,
                                    "email_integrity_guard": curr_anti_cp,
                                    "behavioral_delays": curr_anti_cp,
                                    "session_warmup": curr_anti_cp,
                                    "network_risk_check": curr_anti_cp,
                                    "proxy_ip": assigned_ip,
                                    "proxy_country": getattr(getattr(proxy_obj, "geo_profile", None), "country_name", None) or (proxy_obj.country if (proxy_obj and proxy_obj.country != "Unknown") else None) or (k_state.get("location") if (isinstance(k_state, dict) and k_state) else None),
                                    "country_code": getattr(proxy_obj, "country_code", None) or (getattr(getattr(proxy_obj, "geo_profile", None), "country_code", None)),
                                    "geo_profile": getattr(proxy_obj, "geo_profile", None),
                                    "name_type": curr_name_type,
                                    "extract_token": curr_extract_token,
                                    "custom_name_file": curr_name_file,
                                    "mix_file_names": curr_mix_names,
                                    "verify_live_status": True,
                                    "live_check_delay": 2.0,
                                    "proxy_provider": provider_name,
                                    "retry_on_nvr_with_new_mail": curr_retry_on_nvr,
                                    "retry_email_service": curr_retry_email_service,
                                    "max_otp_email_retries": curr_max_email_retries,
                                    "retry_use_free_mail": curr_retry_use_free,
                                    "fallback_email_service": curr_fallback_email_service,
                                    "metaking_api_key": curr_metaking_api_key,
                                    "metaking_service_type": curr_metaking_service_type,
                                    "metaking_server": curr_metaking_server,
                                    "metaking_domain": curr_metaking_domain,
                                    "metaking_service_id": (67 if ("phone" in str(curr_email_service).lower() or self.config.get("metaking_service_type") == "phone") else 1),
                                    "metaking_country_id": curr_metaking_country_id,
                                    "metaking_price": curr_metaking_price,
                                }
                            )

                            def _exec_reg_action():
                                stagger_wait = 0.0
                                if assigned_ip and assigned_ip != "Direct":
                                    with _shared_ip_gate_lock:
                                        last_req = _shared_ip_last_submit.get(assigned_ip, 0.0)
                                        now_req = time.time()
                                        base_time = max(now_req, min(last_req, now_req + 2.0))
                                        safe_gap = random.uniform(1.2, 2.5)
                                        target_time = base_time + safe_gap
                                        stagger_wait = max(0.0, target_time - now_req)
                                        _shared_ip_last_submit[assigned_ip] = target_time
                                if stagger_wait > 0:
                                    time.sleep(min(stagger_wait, 4.0))

                                if k_state:
                                    with k_state["lock"]:
                                        k_state["active_sessions"] = k_state.get("active_sessions", 0) + 1
                                try:
                                    return reg_svc.register(task_input)
                                finally:
                                    if k_state:
                                        with k_state["lock"]:
                                            k_state["active_sessions"] = max(0, k_state.get("active_sessions", 1) - 1)

                            res = _exec_reg_action()
                        except Exception as e:
                            res = RegistrationResult(
                                success=False,
                                status="error",
                                error_message=str(e)
                            )

                    if curr_reg_mode == "verify_nvr" and acc_custom_proxy:
                        display_ip = acc_custom_proxy
                    else:
                        if proxy_obj:
                            display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else (assigned_ip or proxy_obj.host)
                        else:
                            display_ip = assigned_ip or "Direct"
                    self._worker_proxy_map[worker_id] = display_ip
                    self.event_queue.put(("result", {
                        "result": res,
                        "worker_id": worker_id,
                        "proxy": display_ip,
                    }))

                    # Đánh giá kết quả tạo tài khoản / phiên:
                    session_created = bool(res.uid or getattr(res, "cookie_string", "") or getattr(res, "cookie", ""))

                    is_genuinely_success = False
                    if curr_reg_mode == "verify_nvr":
                        is_genuinely_success = bool(res.success and (res.uid or getattr(res, "cookie_string", "")))
                        try:
                            from core.nvr_pipeline_bridge import mark_account_result
                            v_dir = self.var_verry_pipeline_dir.get().strip() if hasattr(self, "var_verry_pipeline_dir") else os.getcwd()
                            if is_genuinely_success:
                                rec_line = res.format_line(curr_save_format) if hasattr(res, "format_line") else f"{target_uid}|{res.cookie_string}"
                                mark_account_result(target_uid, success=True, result_line=rec_line, verry_dir=v_dir)
                            else:
                                err_str = getattr(res, "error_message", "") or "Checkpoint"
                                mark_account_result(target_uid, success=False, result_line=f"{target_uid}|{acc_custom_proxy}", verry_dir=v_dir, error=err_str, is_checkpoint=True)
                        except Exception as ex_m:
                            logger.warning(f"Error marking account result in pipeline: {ex_m}")
                    elif curr_reg_mode == "vr":
                        is_genuinely_success = bool(res.success and (res.uid or getattr(res, "cookie_string", "")) and not getattr(res, "is_checkpoint", False))
                    elif curr_reg_mode in ("legacy_nv", "legacy"):
                        if curr_legacy_verify_mode in ("setting", "verify", "email", "phone"):
                            is_genuinely_success = bool(res.success and res.uid and not getattr(res, "is_checkpoint", False) and getattr(res, "status", "") in ("success", "live"))
                        else:
                            is_genuinely_success = bool(res.uid and str(res.uid).isdigit() and len(str(res.uid)) >= 8 and not getattr(res, "is_checkpoint", False) and getattr(res, "status", "") not in ("die", "checkpoint", "error", "failed"))
                    elif curr_reg_mode == "nvr":
                        is_genuinely_success = bool(res.uid and str(res.uid).isdigit() and len(str(res.uid)) >= 8 and not getattr(res, "is_checkpoint", False) and getattr(res, "status", "") not in ("die", "checkpoint", "error", "failed"))
                    elif curr_reg_mode in ("ios_bloks", "bloks_ios", "regfb"):
                        is_genuinely_success = bool(res.success and res.uid and not getattr(res, "is_checkpoint", False) and getattr(res, "status", "") in ("success", "live"))
                    else:
                        is_genuinely_success = bool(res.success and res.uid)

                    if is_genuinely_success:
                        with success_lock:
                            successful_accs += 1
                            if max_accs > 0 and successful_accs >= max_accs:
                                self.event_queue.put(("log", {
                                    "message": f"🎉 [Hoàn Tất] Đã đạt chỉ tiêu {successful_accs}/{max_accs} tài khoản thành công!",
                                    "tag": "success"
                                }))
                                self.stop_event.set()
                                break
                    if session_created:
                        if provider_name in ("free_proxy_live", "free_proxy_cached", "free_proxy") and free_mgr and proxy_obj:
                            free_mgr.record_session_success(proxy_obj)
                    elif not session_created:
                        if provider_name in ("free_proxy_live", "free_proxy_cached", "free_proxy") and free_mgr and proxy_obj:
                            free_mgr.record_session_failure(proxy_obj, reason=getattr(res, "error_message", ""))
                        err_str = getattr(res, "error_message", "") or ""
                        is_actual_proxy_down = any(k in err_str.lower() for k in (
                            "proxy connection failed", "tunnel failed", "could not resolve proxy",
                            "curl: (5)", "curl: (6)", "curl: (7)", "curl: (28)", "curl: (35)", "curl: (56)",
                            "connection refused", "connection reset", "connection aborted", "closed by peer"
                        ))
                        if is_actual_proxy_down or provider_name == "proxy_list":
                            self.event_queue.put(("log", {
                                "message": f"[Luồng {worker_id}] ⚡ Proxy lỗi kết nối mạng / Không tạo được phiên ➔ Đổi sang Proxy khác ngay!",
                                "tag": "info"
                            }))
                            if provider_name == "proxy_list" and proxy_obj:
                                removed_key = proxy_manager.remove_bad_proxy(proxy_obj, reason=err_str[:80] or "Khởi tạo phiên thất bại")
                                if removed_key:
                                    if not hasattr(self, "_bad_proxy_log_counter"):
                                        self._bad_proxy_log_counter = 0
                                    self._bad_proxy_log_counter += 1
                                    if self._bad_proxy_log_counter <= 5 or self._bad_proxy_log_counter % 10 == 0:
                                        rem_cnt = proxy_manager.alive_count()
                                        p_file = self.get_proxy_file_path()
                                        bname = os.path.basename(p_file) if p_file else "file proxy"
                                        self.event_queue.put(("log", {
                                            "message": f"[Proxy File] 🗑️ Đã loại bỏ Proxy lỗi {self.mask_ip(proxy_obj.host)}:{proxy_obj.port} khỏi '{bname}' ➔ Chuyển vào 'proxy_loi.txt' (Còn lại {rem_cnt} proxy)",
                                            "tag": "warning"
                                        }))
                        else:
                            self.event_queue.put(("log", {
                                "message": f"[Luồng {worker_id}] ⚠️ Tạo phiên chưa thành công ({err_str[:60]}) ➔ Chuyển tiếp sang xử lý nick kế tiếp!",
                                "tag": "info"
                            }))

                    if self.stop_event.is_set():
                        break

                    # Kiểm tra xem còn cần chạy tiếp hay không:
                    has_more_accs = False
                    if curr_reg_mode == "verify_nvr":
                        with nvr_lock:
                            has_more_accs = (nvr_idx < len(nvr_list) and (max_accs <= 0 or nvr_idx < max_accs)) or pipeline_active
                    else:
                        with success_lock:
                            has_more_accs = (max_accs <= 0 or successful_accs < max_accs)

                    if not has_more_accs or self.stop_event.is_set():
                        break

                    # Chuẩn bị IP cho nick tiếp theo:
                    # NGUYÊN TẮC VÀNG CHỐNG CHECKPOINT 282: TUYỆT ĐỐI KHÔNG DÙNG LẠI IP CŨ!
                    # Mỗi nick Facebook BẮT BUỘC phải chạy trên 1 IP mới độc lập hoàn toàn.
                    old_p_obj = proxy_obj
                    last_run_die = bool(res and getattr(res, "status", "") in ("die", "checkpoint"))
                    is_run_waf = bool(res and any(k in str(getattr(res, "error_message", "")).lower() for k in ("1351050", "lỗi đăng ký", "lỗi đăng ký", "registration error", "waf", "integrity", "không thể tạo tài khoản", "hạn chế ip")))
                    is_proxy_down = bool(not session_created and is_actual_proxy_down)
                    old_ip = assigned_ip or (proxy_obj.host if proxy_obj else "")
                    if k_state and old_ip:
                        with k_state["lock"]:
                            if alloc_mode == "dedicated":
                                k_state.setdefault("consumed_ips", set()).add(old_ip)
                            if last_run_die or is_run_waf:
                                k_state.setdefault("burned_ips", set()).add(old_ip)
                                k_state["need_rotate"] = True
                            if is_proxy_down:
                                fc = k_state.get("fail_count", 0) + 1
                                k_state["fail_count"] = fc
                                if fc >= 3 or alloc_mode == "dedicated":
                                    k_state.setdefault("burned_ips", set()).add(old_ip)
                                    if k_state.get("cur_ip") == old_ip:
                                        k_state["proxy_obj"] = None
                                        k_state["cur_ip"] = ""
                                    k_state["need_rotate"] = True
                            else:
                                k_state["fail_count"] = 0
                    if is_proxy_down and base_k:
                        if provider_name in ("kiotproxy", "kiotproxy_current") and k_state and k_state.get("fail_count", 0) >= 3:
                            KiotProxyClient.invalidate_cache(base_k)
                        elif provider_name == "proxysocks5":
                            ProxySocks5Client.invalidate_cache(base_k)
                        elif provider_name == "mproxy":
                            MproxyClient.invalidate_cache(base_k)
                        elif provider_name == "proxyvn" and k_state and k_state.get("fail_count", 0) >= 3:
                            ProxyVNClient.invalidate_cache(base_k)
                    proxy_obj = None
                    assigned_ip = ""
                    if ip_registry:
                        try:
                            ip_registry.release_ip(worker_id)
                        except Exception:
                            pass

                    if provider_name in ("kiotproxy", "kiotproxy_current") and (effective_kiot_keys or kiot_keys):
                        try:
                            k_state = shared_kiot_state.get(base_k)
                            kiot_client = (k_state.get("client") if k_state else None) or KiotProxyClient(base_k)
                            rot_success = False
                            first_wait_logged = False
                            while not rot_success and not self.stop_event.is_set():
                                cur_cached_ip = ""
                                cur_cached_p = None
                                burned_set = set()
                                need_rot = False
                                next_rot = 0.0
                                if k_state:
                                    with k_state["lock"]:
                                        cur_cached_ip = k_state.get("cur_ip", "")
                                        cur_cached_p = k_state.get("proxy_obj")
                                        burned_set = set(k_state.get("burned_ips", set()))
                                        need_rot = k_state.get("need_rotate", False)
                                        next_rot = k_state.get("next_rotate_allowed_at", 0.0)

                                # TH 1: Chế độ chỉ dùng IP hiện tại không xoay (kiotproxy_current)
                                if provider_name == "kiotproxy_current":
                                    if cur_cached_p and cur_cached_ip:
                                        proxy_obj = copy.copy(cur_cached_p)
                                        assigned_ip = cur_cached_ip
                                        display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                        self._worker_proxy_map[worker_id] = display_ip
                                        if ip_registry:
                                            ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                        rot_success = True
                                        break

                                # TH 2: Luồng khác trên CÙNG KEY đã xoay sang IP MỚI thành công
                                if cur_cached_p and cur_cached_ip and cur_cached_ip != old_ip and cur_cached_ip not in burned_set:
                                    proxy_obj = copy.copy(cur_cached_p)
                                    assigned_ip = cur_cached_ip
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                    self.event_queue.put(("log", {
                                        "message": f"[Luồng {worker_id}] 🟢 Đã tự động cập nhật sang IP MỚI ({base_key_label}): {self.mask_ip(assigned_ip)} ({proxy_obj.country}) ➔ Tiếp tục reg!",
                                        "tag": "success"
                                    }))
                                    rot_success = True
                                    break

                                # TH 3: Chế độ shared, KHÔNG cần rotate (lượt vừa rồi thành công, IP sạch không bị ban)
                                if alloc_mode == "shared" and not need_rot and old_ip not in burned_set and cur_cached_p and cur_cached_ip and cur_cached_ip not in burned_set:
                                    proxy_obj = copy.copy(cur_cached_p)
                                    assigned_ip = cur_cached_ip
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                    time.sleep(random.uniform(0.1, 0.4))
                                    rot_success = True
                                    break

                                # TH 3.5: Mượn tạm IP sạch của key khác khi key nhà đang dính cooldown xoay IP (TUYỆT ĐỐI KHÔNG ĐỔI base_k!)
                                if alloc_mode == "shared" and len(keys_pool) > 1 and (old_ip in burned_set or need_rot):
                                    borrowed = False
                                    shuffled_pool = list(keys_pool)
                                    random.shuffle(shuffled_pool)
                                    for cand_k in shuffled_pool:
                                        if cand_k == base_k:
                                            continue
                                        c_st = shared_kiot_state.get(cand_k)
                                        if c_st:
                                            with c_st["lock"]:
                                                c_p = c_st.get("proxy_obj")
                                                c_ip = c_st.get("cur_ip", "")
                                                c_burned = c_st.get("burned_ips", set())
                                                c_act = c_st.get("active_sessions", 0)
                                                max_borrow_act = max(4, actual_threads // len(keys_pool) // 2) if len(keys_pool) > 0 else 3
                                                if c_p and c_ip and c_ip != old_ip and c_ip not in c_burned and c_ip not in burned_set and c_act < max_borrow_act:
                                                    proxy_obj = copy.copy(c_p)
                                                    assigned_ip = c_ip
                                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                                    self._worker_proxy_map[worker_id] = display_ip
                                                    if ip_registry:
                                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                                    self.event_queue.put(("log", {
                                                        "message": f"[Luồng {worker_id}] ⚡ Mượn tạm IP ({self.mask_ip(assigned_ip)}) trong khi {base_key_label} đang chờ đổi IP mới ➔ Tiếp tục reg không chờ!",
                                                        "tag": "info"
                                                    }))
                                                    rot_success = True
                                                    borrowed = True
                                                    break
                                    if borrowed:
                                        break

                                # TH 4: Cần xoay sang IP mới cho key này
                                rot_lock = k_state.setdefault("rot_lock", threading.Lock()) if k_state else None
                                if (not rot_lock) or rot_lock.acquire(blocking=False):
                                    try:
                                        now_t = time.time()
                                        if now_t < next_rot:
                                            wait_s = max(0.0, min(next_rot - now_t, 120.0))
                                            if wait_s > 0:
                                                if not first_wait_logged:
                                                    first_wait_logged = True
                                                    self.event_queue.put(("log", {
                                                        "message": f"[Luồng {worker_id}] ⏳ {base_key_label} đang trong thời gian hồi ({int(wait_s)}s) ➔ Đang chờ để xoay IP MỚI...",
                                                        "tag": "info"
                                                    }))
                                                time.sleep(min(wait_s, 2.0))
                                                continue

                                        KiotProxyClient.invalidate_cache(base_k)
                                        rot_res = kiot_client.get_new_proxy(fallback_current=False)
                                        new_http = rot_res.get("http")
                                        new_ip = rot_res.get("ip") or (ProxyManager.parse_proxy(new_http).host if new_http else "")
                                        is_rotated = rot_res.get("rotated", False) or (new_ip and new_ip != old_ip and new_ip not in burned_set)

                                        if rot_res.get("success") and new_http and is_rotated:
                                            new_p = ProxyManager.parse_proxy(new_http)
                                            if new_p:
                                                new_p.raw = kiot_client.api_key
                                                new_p.real_ip = new_ip
                                                new_p.country = rot_res.get("location", "Vietnam")
                                                new_p.country_code = normalize_country_code(new_p.country) or "VN"
                                                new_p.geo_profile = GeoTelephonyResolver.get_profile_for_country(new_p.country_code, ip=new_ip)
                                                proxy_obj = new_p
                                                assigned_ip = new_ip
                                                display_ip = f"{new_p.host}:{new_p.port}" if getattr(new_p, "port", None) else new_ip
                                                self._worker_proxy_map[worker_id] = display_ip
                                                real_ttc = min(max(30, int(rot_res.get("ttc") or rot_res.get("packageTtc") or 60)), 120)
                                                if k_state:
                                                    with k_state["lock"]:
                                                        k_state["proxy_obj"] = new_p
                                                        k_state["cur_ip"] = new_ip
                                                        k_state["last_working_proxy"] = copy.copy(new_p)
                                                        k_state["last_working_ip"] = new_ip
                                                        k_state["location"] = new_p.country
                                                        k_state["rot_time"] = time.time()
                                                        k_state["last_fetch"] = time.time()
                                                        k_state["next_rotate_allowed_at"] = time.time() + real_ttc
                                                        k_state["need_rotate"] = False
                                                        k_state["fail_count"] = 0
                                                if ip_registry:
                                                    ip_registry.lease_ip(worker_id, new_ip, force=True)

                                                mode_tag = "MỚI" if alloc_mode == "dedicated" else "MỚI (Các luồng dùng chung sẽ tự động cập nhật)"
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] 🟢 ĐÃ ĐỔI SANG IP KIOTPROXY {mode_tag} ({base_key_label}): {self.mask_ip(new_ip)} ({new_p.country}) ➔ Sẵn sàng xử lý nick tiếp theo!",
                                                    "tag": "success"
                                                }))
                                                rot_success = True
                                                break
                                        else:
                                            raw_ttc = int(rot_res.get("ttc") or rot_res.get("packageTtc") or 30)
                                            if raw_ttc > 120:
                                                raw_ttc = 60
                                            ttc = min(max(10, raw_ttc), 120)
                                            if k_state:
                                                with k_state["lock"]:
                                                    k_state["next_rotate_allowed_at"] = time.time() + ttc
                                            if not first_wait_logged:
                                                first_wait_logged = True
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] ⏳ KiotProxy ({base_key_label}) đang trong thời gian chờ ({ttc}s) ➔ Đang đợi để lấy IP mới...",
                                                    "tag": "info"
                                                }))
                                            time.sleep(min(float(ttc), 2.0))
                                    finally:
                                        if rot_lock:
                                            try:
                                                rot_lock.release()
                                            except Exception:
                                                pass
                                else:
                                    time.sleep(1.0)
                        except Exception as e:
                            logger.warning(f"Error checking KiotProxy rotation for worker {worker_id}: {e}")

                    elif provider_name == "proxysocks5" and (effective_psocks5_keys or psocks5_keys):
                        try:
                            k_state = shared_psocks5_state.get(base_k)
                            psocks5_client = (k_state.get("client") if k_state else None) or ProxySocks5Client(base_k, user_token=getattr(self, "proxysocks5_user_token", None))
                            rot_success = False
                            first_wait_logged = False
                            while not rot_success and not self.stop_event.is_set():
                                cur_cached_ip = ""
                                cur_cached_p = None
                                if k_state:
                                    with k_state["lock"]:
                                        cur_cached_ip = k_state.get("cur_ip", "")
                                        cur_cached_p = k_state.get("proxy_obj")

                                if alloc_mode == "shared":
                                    burned_set = k_state.get("burned_ips", set()) if k_state else set()
                                    if cur_cached_p and cur_cached_ip and cur_cached_ip not in burned_set:
                                        proxy_obj = copy.copy(cur_cached_p)
                                        assigned_ip = cur_cached_ip
                                        display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                        self._worker_proxy_map[worker_id] = display_ip
                                        if ip_registry:
                                            ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                        rot_success = True
                                        break
                                else:
                                    consumed_set = k_state.setdefault("consumed_ips", set()) if k_state else set()
                                    if cur_cached_p and cur_cached_ip and cur_cached_ip != old_ip and cur_cached_ip not in consumed_set:
                                        proxy_obj = copy.copy(cur_cached_p)
                                        assigned_ip = cur_cached_ip
                                        consumed_set.add(cur_cached_ip)
                                        display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                        self._worker_proxy_map[worker_id] = display_ip
                                        if ip_registry:
                                            ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                        rot_success = True
                                        break

                                rot_lock = k_state.setdefault("rot_lock", threading.Lock()) if k_state else None
                                if (not rot_lock) or rot_lock.acquire(blocking=False):
                                    got_new = False
                                    ttc_wait = 0
                                    try:
                                        ProxySocks5Client.invalidate_cache(base_k)
                                        rot_res = psocks5_client.get_new_proxy(fallback_current=False)
                                        new_str = rot_res.get("http") or rot_res.get("socks5")
                                        new_ip = rot_res.get("ip") or (ProxyManager.parse_proxy(new_str).host if new_str else "")

                                        if rot_res.get("success") and new_str and new_ip and new_ip != old_ip:
                                            new_p = ProxyManager.parse_proxy(new_str)
                                            if new_p:
                                                new_p.raw = psocks5_client.api_key
                                                new_p.real_ip = new_ip
                                                new_p.country = rot_res.get("location", "Vietnam")
                                                new_p.country_code = normalize_country_code(new_p.country) or "VN"
                                                new_p.geo_profile = GeoTelephonyResolver.get_profile_for_country(new_p.country_code, ip=new_ip)
                                                proxy_obj = new_p
                                                assigned_ip = new_ip
                                                display_ip = f"{new_p.host}:{new_p.port}" if getattr(new_p, "port", None) else new_ip
                                                self._worker_proxy_map[worker_id] = display_ip
                                                if k_state:
                                                    with k_state["lock"]:
                                                        k_state["proxy_obj"] = new_p
                                                        k_state["cur_ip"] = new_ip
                                                        k_state["location"] = new_p.country
                                                        k_state["rot_time"] = time.time()
                                                        k_state["last_fetch"] = time.time()
                                                        if alloc_mode == "dedicated":
                                                            k_state.setdefault("consumed_ips", set()).add(new_ip)
                                                if ip_registry:
                                                    ip_registry.lease_ip(worker_id, new_ip, force=True)
                                                mode_tag = "MỚI" if alloc_mode == "dedicated" else "MỚI (Các luồng dùng chung sẽ tự động cập nhật)"
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] 🟢 ĐÃ ĐỔI SANG IP {mode_tag} ({base_key_label}): {self.mask_ip(new_ip)} ({new_p.country}) ➔ Sẵn sàng xử lý tài khoản tiếp theo!",
                                                    "tag": "success"
                                                }))
                                                got_new = True
                                                rot_success = True
                                        else:
                                            ttc_wait = max(3, min(int(rot_res.get("ttc") or 30), 120))
                                    finally:
                                        if rot_lock:
                                            try:
                                                rot_lock.release()
                                            except Exception:
                                                pass

                                    if got_new:
                                        time.sleep(1.0)
                                        break

                                    if alloc_mode == "shared":
                                        burned_set = k_state.get("burned_ips", set()) if k_state else set()
                                        can_reuse = cur_cached_p and cur_cached_ip and cur_cached_ip not in burned_set
                                        if can_reuse:
                                            proxy_obj = copy.copy(cur_cached_p)
                                            assigned_ip = cur_cached_ip
                                            display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                            self._worker_proxy_map[worker_id] = display_ip
                                            if ip_registry:
                                                ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                            time.sleep(random.uniform(0.1, 0.3))
                                            rot_success = True
                                            break
                                        else:
                                            if not first_wait_logged:
                                                first_wait_logged = True
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] ⏳ {base_key_label} đang trong thời gian hồi ({ttc_wait}s) ➔ Đang chờ xoay IP MỚI (IP cũ {self.mask_ip(old_ip)} đã hết hạn mức)...",
                                                    "tag": "info"
                                                }))
                                            wait_start = time.time()
                                            while (time.time() - wait_start) < (ttc_wait + 1.0) and not self.stop_event.is_set():
                                                time.sleep(1.0)
                                    else:
                                        if not first_wait_logged:
                                            first_wait_logged = True
                                            self.event_queue.put(("log", {
                                                "message": f"[Luồng {worker_id}] ⏳ {base_key_label} đang trong thời gian hồi ({ttc_wait}s) ➔ Đang chờ xoay IP MỚI (Tuyệt đối không dùng lại IP cũ {self.mask_ip(old_ip)} để chống Checkpoint 282)...",
                                                "tag": "info"
                                            }))
                                        wait_start = time.time()
                                        while (time.time() - wait_start) < (ttc_wait + 1.0) and not self.stop_event.is_set():
                                            time.sleep(1.0)
                                else:
                                    time.sleep(0.5)
                        except Exception as e:
                            logger.warning(f"Error checking ProxySocks5 rotation for worker {worker_id}: {e}")

                    elif provider_name == "mproxy" and (effective_mproxy_keys or mproxy_keys):
                        try:
                            k_state = shared_mproxy_state.get(base_k)
                            m_tok = getattr(self, "mproxy_token", "") or self.config.get("mproxy_token", "")
                            mproxy_client = (k_state.get("client") if k_state else None) or MproxyClient(m_tok, key_code=base_k if base_k != m_tok else None)
                            cache_id = f"{m_tok}:{base_k}"
                            rot_success = False
                            first_wait_logged = False
                            while not rot_success and not self.stop_event.is_set():
                                cur_cached_ip = ""
                                cur_cached_p = None
                                if k_state:
                                    with k_state["lock"]:
                                        cur_cached_ip = k_state.get("cur_ip", "")
                                        cur_cached_p = k_state.get("proxy_obj")

                                if alloc_mode == "shared":
                                    burned_set = k_state.get("burned_ips", set()) if k_state else set()
                                    if cur_cached_p and cur_cached_ip and cur_cached_ip not in burned_set:
                                        proxy_obj = copy.copy(cur_cached_p)
                                        assigned_ip = cur_cached_ip
                                        display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                        self._worker_proxy_map[worker_id] = display_ip
                                        if ip_registry:
                                            ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                        rot_success = True
                                        break
                                else:
                                    consumed_set = k_state.setdefault("consumed_ips", set()) if k_state else set()
                                    if cur_cached_p and cur_cached_ip and cur_cached_ip != old_ip and cur_cached_ip not in consumed_set:
                                        proxy_obj = copy.copy(cur_cached_p)
                                        assigned_ip = cur_cached_ip
                                        consumed_set.add(cur_cached_ip)
                                        display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                        self._worker_proxy_map[worker_id] = display_ip
                                        if ip_registry:
                                            ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                        rot_success = True
                                        break

                                rot_lock = k_state.setdefault("rot_lock", threading.Lock()) if k_state else None
                                if (not rot_lock) or rot_lock.acquire(blocking=False):
                                    got_new = False
                                    ttc_wait = 0
                                    try:
                                        MproxyClient.invalidate_cache(cache_id)
                                        rot_res = mproxy_client.get_new_proxy(fallback_current=False)
                                        new_str = rot_res.get("http") or rot_res.get("proxy")
                                        new_ip = rot_res.get("real_ip") or rot_res.get("server") or rot_res.get("ip") or (ProxyManager.parse_proxy(new_str).host if new_str else "")

                                        if rot_res.get("success") and new_str and (rot_res.get("rotated") or (new_ip and new_ip != old_ip)):
                                            new_p = ProxyManager.parse_proxy(new_str)
                                            if new_p:
                                                new_p.raw = mproxy_client.key_code or mproxy_client.token
                                                new_p.real_ip = new_ip
                                                new_p.country = rot_res.get("location", "Vietnam")
                                                new_p.country_code = normalize_country_code(new_p.country) or "VN"
                                                new_p.geo_profile = GeoTelephonyResolver.get_profile_for_country(new_p.country_code, ip=new_ip)
                                                proxy_obj = new_p
                                                assigned_ip = new_ip
                                                display_ip = f"{new_p.host}:{new_p.port}" if getattr(new_p, "port", None) else new_ip
                                                self._worker_proxy_map[worker_id] = display_ip
                                                if k_state:
                                                    with k_state["lock"]:
                                                        k_state["proxy_obj"] = new_p
                                                        k_state["cur_ip"] = new_ip
                                                        k_state["location"] = new_p.country
                                                        k_state["rot_time"] = time.time()
                                                        k_state["last_fetch"] = time.time()
                                                        if alloc_mode == "dedicated":
                                                            k_state.setdefault("consumed_ips", set()).add(new_ip)
                                                if ip_registry:
                                                    ip_registry.lease_ip(worker_id, new_ip, force=True)
                                                mode_tag = "MỚI" if alloc_mode == "dedicated" else "MỚI (Các luồng dùng chung sẽ tự động cập nhật)"
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] 🟢 ĐÃ ĐỔI SANG IP 4G {mode_tag} ({base_key_label}): {self.mask_ip(new_ip)} ({new_p.country}) ➔ Sẵn sàng xử lý tài khoản tiếp theo!",
                                                    "tag": "success"
                                                }))
                                                got_new = True
                                                rot_success = True
                                        else:
                                            ttc_wait = max(3, min(int(rot_res.get("ttc") or 30), 120))
                                    finally:
                                        if rot_lock:
                                            try:
                                                rot_lock.release()
                                            except Exception:
                                                pass

                                    if got_new:
                                        time.sleep(1.0)
                                        break

                                    if alloc_mode == "shared":
                                        burned_set = k_state.get("burned_ips", set()) if k_state else set()
                                        can_reuse = cur_cached_p and cur_cached_ip and cur_cached_ip not in burned_set
                                        if can_reuse:
                                            proxy_obj = copy.copy(cur_cached_p)
                                            assigned_ip = cur_cached_ip
                                            display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                            self._worker_proxy_map[worker_id] = display_ip
                                            if ip_registry:
                                                ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                            time.sleep(random.uniform(0.1, 0.3))
                                            rot_success = True
                                            break
                                        else:
                                            if not first_wait_logged:
                                                first_wait_logged = True
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] ⏳ {base_key_label} đang trong thời gian hồi ({ttc_wait}s) ➔ Đang chờ xoay IP MỚI (IP cũ {self.mask_ip(old_ip)} đã hết hạn mức)...",
                                                    "tag": "info"
                                                }))
                                            wait_start = time.time()
                                            while (time.time() - wait_start) < (ttc_wait + 1.0) and not self.stop_event.is_set():
                                                time.sleep(1.0)
                                    else:
                                        if not first_wait_logged:
                                            first_wait_logged = True
                                            self.event_queue.put(("log", {
                                                "message": f"[Luồng {worker_id}] ⏳ {base_key_label} đang trong thời gian hồi ({ttc_wait}s) ➔ Đang chờ xoay IP 4G MỚI (Tuyệt đối không dùng lại IP cũ {self.mask_ip(old_ip)} để chống Checkpoint 282)...",
                                                "tag": "info"
                                            }))
                                        wait_start = time.time()
                                        while (time.time() - wait_start) < (ttc_wait + 1.0) and not self.stop_event.is_set():
                                            time.sleep(1.0)
                                else:
                                    time.sleep(0.5)
                        except Exception as e:
                            logger.warning(f"Error checking mProxy rotation for worker {worker_id}: {e}")

                    elif provider_name == "proxyvn" and (effective_proxyvn_keys or proxyvn_keys):
                        try:
                            k_state = shared_proxyvn_state.get(base_k)
                            pvn_client = (k_state.get("client") if k_state else None) or ProxyVNClient(base_k)
                            rot_success = False
                            first_wait_logged = False
                            while not rot_success and not self.stop_event.is_set():
                                cur_cached_ip = ""
                                cur_cached_p = None
                                burned_set = set()
                                need_rot = False
                                next_rot = 0.0
                                if k_state:
                                    with k_state["lock"]:
                                        cur_cached_ip = k_state.get("cur_ip", "")
                                        cur_cached_p = k_state.get("proxy_obj")
                                        burned_set = set(k_state.get("burned_ips", set()))
                                        need_rot = k_state.get("need_rotate", False)
                                        next_rot = k_state.get("next_rotate_allowed_at", 0.0)

                                # TH 1: Luồng khác trên cùng key đã xoay sang IP MỚI thành công
                                if cur_cached_p and cur_cached_ip and cur_cached_ip != old_ip and cur_cached_ip not in burned_set:
                                    proxy_obj = copy.copy(cur_cached_p)
                                    assigned_ip = cur_cached_ip
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                    self.event_queue.put(("log", {
                                        "message": f"[Luồng {worker_id}] 🟢 Đã tự động đổi sang IP MỚI từ luồng khác ({base_key_label}): {self.mask_ip(assigned_ip)} ({proxy_obj.country}) ➔ Tiếp tục reg!",
                                        "tag": "success"
                                    }))
                                    rot_success = True
                                    break

                                # TH 2: Chế độ shared, KHÔNG cần rotate (lượt vừa rồi thành công, IP sạch)
                                if alloc_mode == "shared" and not need_rot and old_ip not in burned_set and cur_cached_p and cur_cached_ip and cur_cached_ip not in burned_set:
                                    proxy_obj = copy.copy(cur_cached_p)
                                    assigned_ip = cur_cached_ip
                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                    self._worker_proxy_map[worker_id] = display_ip
                                    if ip_registry:
                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                    time.sleep(random.uniform(0.1, 0.4))
                                    rot_success = True
                                    break

                                # TH 2.5: Mượn tạm IP sạch của key khác khi key nhà đang dính cooldown xoay IP (TUYỆT ĐỐI KHÔNG ĐỔI base_k!)
                                if alloc_mode == "shared" and len(keys_pool) > 1 and (old_ip in burned_set or need_rot):
                                    borrowed = False
                                    shuffled_pool = list(keys_pool)
                                    random.shuffle(shuffled_pool)
                                    for cand_k in shuffled_pool:
                                        if cand_k == base_k:
                                            continue
                                        c_st = shared_proxyvn_state.get(cand_k)
                                        if c_st:
                                            with c_st["lock"]:
                                                c_p = c_st.get("proxy_obj")
                                                c_ip = c_st.get("cur_ip", "")
                                                c_burned = c_st.get("burned_ips", set())
                                                c_act = c_st.get("active_sessions", 0)
                                                max_borrow_act = max(4, actual_threads // len(keys_pool) // 2) if len(keys_pool) > 0 else 3
                                                if c_p and c_ip and c_ip != old_ip and c_ip not in c_burned and c_ip not in burned_set and c_act < max_borrow_act:
                                                    proxy_obj = copy.copy(c_p)
                                                    assigned_ip = c_ip
                                                    display_ip = f"{proxy_obj.host}:{proxy_obj.port}" if getattr(proxy_obj, "port", None) else assigned_ip
                                                    self._worker_proxy_map[worker_id] = display_ip
                                                    if ip_registry:
                                                        ip_registry.lease_ip(worker_id, assigned_ip, force=True)
                                                    self.event_queue.put(("log", {
                                                        "message": f"[Luồng {worker_id}] ⚡ Mượn tạm IP ({self.mask_ip(assigned_ip)}) trong khi {base_key_label} đang chờ đổi IP mới ➔ Tiếp tục reg không chờ!",
                                                        "tag": "info"
                                                    }))
                                                    rot_success = True
                                                    borrowed = True
                                                    break
                                    if borrowed:
                                        break

                                # TH 3: Cần xoay sang IP mới cho key này
                                rot_lock = k_state.setdefault("rot_lock", threading.Lock()) if k_state else None
                                if (not rot_lock) or rot_lock.acquire(blocking=False):
                                    try:
                                        now_t = time.time()
                                        if now_t < next_rot:
                                            wait_s = max(0.0, min(next_rot - now_t, 65.0))
                                            if wait_s > 0:
                                                if not first_wait_logged:
                                                    first_wait_logged = True
                                                    self.event_queue.put(("log", {
                                                        "message": f"[Luồng {worker_id}] ⏳ {base_key_label} đang trong thời gian hồi ({int(wait_s)}s) ➔ Đang chờ để xoay IP MỚI...",
                                                        "tag": "info"
                                                    }))
                                                time.sleep(min(wait_s, 2.0))
                                                continue

                                        ProxyVNClient.invalidate_cache(base_k)
                                        rot_res = pvn_client.get_new_proxy(fallback_current=False)
                                        new_str = rot_res.get("http") or rot_res.get("raw_http")
                                        new_ip = rot_res.get("ip") or (ProxyManager.parse_proxy(new_str).host if new_str else "")
                                        is_rotated = rot_res.get("rotated", False) or (new_ip and new_ip != old_ip and new_ip not in burned_set)

                                        if rot_res.get("success") and new_str and is_rotated:
                                            new_p = ProxyManager.parse_proxy(new_str)
                                            if new_p:
                                                new_p.raw = base_k
                                                new_p.real_ip = new_ip
                                                new_p.country = rot_res.get("location", "Vietnam")
                                                new_p.country_code = normalize_country_code(new_p.country) or "VN"
                                                new_p.geo_profile = GeoTelephonyResolver.get_profile_for_country(new_p.country_code, ip=new_ip)
                                                proxy_obj = new_p
                                                assigned_ip = new_ip
                                                display_ip = f"{new_p.host}:{new_p.port}" if getattr(new_p, "port", None) else new_ip
                                                self._worker_proxy_map[worker_id] = display_ip
                                                real_ttc = min(max(30, int(rot_res.get("ttc") or 60)), 65)
                                                if k_state:
                                                    with k_state["lock"]:
                                                        k_state["proxy_obj"] = new_p
                                                        k_state["cur_ip"] = new_ip
                                                        k_state["last_working_proxy"] = copy.copy(new_p)
                                                        k_state["last_working_ip"] = new_ip
                                                        k_state["location"] = new_p.country
                                                        k_state["carrier"] = rot_res.get("carrier", "")
                                                        k_state["rot_time"] = time.time()
                                                        k_state["last_fetch"] = time.time()
                                                        k_state["next_rotate_allowed_at"] = time.time() + real_ttc
                                                        k_state["need_rotate"] = False
                                                        k_state["fail_count"] = 0
                                                if ip_registry:
                                                    ip_registry.lease_ip(worker_id, new_ip, force=True)

                                                mode_tag = "MỚI" if alloc_mode == "dedicated" else "MỚI (Các luồng dùng chung sẽ tự động cập nhật)"
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] 🟢 ĐÃ ĐỔI SANG IP PROXY.VN {mode_tag} ({base_key_label}): {self.mask_ip(new_ip)} ({new_p.country}) ➔ Sẵn sàng xử lý nick tiếp theo!",
                                                    "tag": "success"
                                                }))
                                                rot_success = True
                                                break
                                        else:
                                            raw_ttc = int(rot_res.get("ttc") or 30)
                                            if raw_ttc > 65:
                                                raw_ttc = 60
                                            ttc = min(max(10, raw_ttc), 65)
                                            if k_state:
                                                with k_state["lock"]:
                                                    k_state["next_rotate_allowed_at"] = time.time() + ttc
                                            if not first_wait_logged:
                                                first_wait_logged = True
                                                self.event_queue.put(("log", {
                                                    "message": f"[Luồng {worker_id}] ⏳ Proxy.vn ({base_key_label}) đang trong thời gian chờ ({ttc}s) ➔ Đang đợi để lấy IP mới...",
                                                    "tag": "info"
                                                }))
                                            time.sleep(min(float(ttc), 2.0))
                                    finally:
                                        if rot_lock:
                                            try:
                                                rot_lock.release()
                                            except Exception:
                                                pass
                                else:
                                    time.sleep(1.0)
                        except Exception as e:
                            logger.warning(f"Error checking ProxyVN rotation for worker {worker_id}: {e}")

                    elif provider_name == "proxy_list":
                        try:
                            if old_p_obj and not session_created:
                                removed_key = proxy_manager.remove_bad_proxy(old_p_obj, reason=err_str[:80] or "Không thể tạo phiên")
                                if removed_key:
                                    if not hasattr(self, "_bad_proxy_log_counter"):
                                        self._bad_proxy_log_counter = 0
                                    self._bad_proxy_log_counter += 1
                                    if self._bad_proxy_log_counter <= 5 or self._bad_proxy_log_counter % 10 == 0:
                                        rem_cnt = proxy_manager.alive_count()
                                        p_file = self.get_proxy_file_path()
                                        bname = os.path.basename(p_file) if p_file else "file proxy"
                                        self.event_queue.put(("log", {
                                            "message": f"[Proxy File] 🗑️ Đã loại bỏ Proxy lỗi {self.mask_ip(old_p_obj.host)}:{old_p_obj.port} khỏi '{bname}' ➔ Chuyển vào 'proxy_loi.txt' (Còn lại {rem_cnt} proxy)",
                                            "tag": "warning"
                                        }))
                            new_p = proxy_manager.next_proxy(worker_id=worker_id, registry=ip_registry)
                            if not new_p:
                                self.event_queue.put(("log", {
                                    "message": f"[Proxy List] ⚠️ Danh sách proxy trong file đã hết proxy khả dụng! Vui lòng nạp thêm proxy mới.",
                                    "tag": "warning"
                                }))
                                time.sleep(3.0)
                                continue
                            if new_p:
                                if not getattr(new_p, "geo_profile", None):
                                    try:
                                        new_p.geo_profile = GeoTelephonyResolver.resolve_ip(new_p.real_ip or new_p.host, hint_country=getattr(new_p, "country", None))
                                        if new_p.geo_profile:
                                            new_p.country = new_p.geo_profile.country_name
                                            new_p.country_code = new_p.geo_profile.country_code
                                    except Exception:
                                        pass
                                proxy_obj = new_p
                                assigned_ip = new_p.host
                                display_ip = f"{new_p.host}:{new_p.port}" if getattr(new_p, "port", None) else new_p.host
                                self._worker_proxy_map[worker_id] = display_ip
                                if ip_registry:
                                    ip_registry.lease_ip(worker_id, new_p.real_ip or new_p.host, force=True)
                                self.event_queue.put(("log", {
                                    "message": f"[Proxy List] 🔄 Luồng {worker_id} ➔ Đổi sang Proxy ngẫu nhiên mới: {self.mask_ip(new_p.host)}:{new_p.port}",
                                    "tag": "info"
                                }))
                        except Exception as e:
                            logger.debug(f"Proxy list rotate error: {e}")

                    # Nếu không tạo được phiên 1 lần, chuyển sang luồng tiếp theo ngay tức thì không chờ đợi lâu
                    short_pause = 0.1 if (not session_created) else (random.uniform(0.3, 0.8) if curr_anti_cp else 0.05)
                    self.stop_event.wait(timeout=short_pause)

                if provider_name in ("free_proxy_live", "free_proxy_cached", "free_proxy") and free_mgr:
                    try:
                        free_mgr.release_proxy(worker_id=worker_id)
                    except Exception:
                        pass
                elif provider_name == "proxy_list":
                    try:
                        proxy_manager.release_worker_proxy(worker_id, registry=ip_registry)
                    except Exception:
                        pass
                try:
                    ip_registry.release_ip(worker_id)
                except Exception:
                    pass

            # KHỞI CHẠY LUỒNG ĐỒNG THỜI - MỖI LUỒNG TỰ CÀO PROXY TRỰC TIẾP TỐI ƯU 500 - 2000 LUỒNG
            if provider_name in ("free_proxy_live", "free_proxy_cached", "free_proxy") and free_mgr:
                self.event_queue.put(("log", {
                    "message": f"🌐 Khởi chạy {actual_threads} luồng song song qua hệ thống proxy trực tuyến...",
                    "tag": "info"
                }))

            worker_threads = {}
            worker_lock = threading.Lock()

            def spawn_worker(wid: int):
                with worker_lock:
                    if self.stop_event.is_set():
                        return
                    def _safe_worker():
                        try:
                            single_worker(wid)
                        except Exception as ex:
                            logger.error(f"[Worker-{wid}] Exception: {ex}", exc_info=True)
                            self.event_queue.put(("log", {
                                "message": f"[Luồng {wid}] ⚠️ Luồng gặp ngoại lệ ({ex}) ➔ Giám sát viên sẽ tự động bù lại luồng!",
                                "tag": "warning"
                            }))
                    t = threading.Thread(target=_safe_worker, daemon=True, name=f"Worker-{wid}")
                    worker_threads[wid] = t
                    t.start()

            if provider_name in ("proxysocks5", "kiotproxy", "kiotproxy_current", "mproxy", "proxyvn") and actual_threads > 1:
                # Tránh các luồng đâm vào port proxy cùng 1 microsecond gây timeout 5004ms
                ramp_delay = 0.05 if actual_threads >= 100 else (0.1 if actual_threads >= 30 else (0.2 if actual_threads > 5 else 0.5))
            else:
                ramp_delay = 0.005 if actual_threads >= 200 else (0.01 if actual_threads >= 50 else 0.02)
            for i in range(1, actual_threads + 1):
                spawn_worker(i)
                if ramp_delay > 0:
                    time.sleep(ramp_delay)

            try:
                # Vòng lặp giám sát (Supervisor): Luôn đảm bảo đủ đúng số luồng như setting hoạt động song song độc lập
                while not self.stop_event.is_set():
                    with success_lock:
                        if curr_reg_mode != "verify_nvr" and max_accs > 0 and successful_accs >= max_accs:
                            self.stop_event.set()
                            break

                    if curr_reg_mode == "verify_nvr":
                        with nvr_lock:
                            if nvr_idx >= len(nvr_list) or (max_accs > 0 and nvr_idx >= max_accs):
                                if not pipeline_active or (max_accs > 0 and successful_accs >= max_accs):
                                    all_done = True
                                    with worker_lock:
                                        for wid in range(1, actual_threads + 1):
                                            th = worker_threads.get(wid)
                                            if th and th.is_alive():
                                                all_done = False
                                                break
                                if all_done:
                                    break

                    # Nếu có bất kỳ luồng nào thoát hoặc lỗi ngoài ý muốn, lập tức bù luồng mới để duy trì đúng số luồng
                    if not self.stop_event.is_set():
                        for wid in range(1, actual_threads + 1):
                            with worker_lock:
                                th = worker_threads.get(wid)
                            if th is None or not th.is_alive():
                                need_spawn = False
                                if curr_reg_mode == "verify_nvr":
                                    with nvr_lock:
                                        need_spawn = (nvr_idx < len(nvr_list) and (max_accs <= 0 or nvr_idx < max_accs)) or pipeline_active
                                else:
                                    with success_lock:
                                        need_spawn = (max_accs <= 0 or successful_accs < max_accs)
                                if need_spawn and not self.stop_event.is_set():
                                    spawn_worker(wid)

                    self.stop_event.wait(timeout=0.25)

                with worker_lock:
                    all_th = list(worker_threads.values())
                for th in all_th:
                    if th and th.is_alive():
                        th.join(timeout=1.0)
            except Exception as e:
                logger.error(f"master_worker error: {e}", exc_info=True)
            finally:
                pipeline_stop_event.set()
                try:
                    from core.proxy_manager import FreeProxyManager
                    FreeProxyManager().stop_continuous_validator()
                except Exception:
                    pass
                try:
                    if provider_name == "proxy_list":
                        proxy_manager.flush_bad_proxies_from_file()
                except Exception:
                    pass
                self.event_queue.put(("all_finished", {}))
        threading.Thread(target=master_worker, daemon=True).start()

    def stop_execution(self):
        if not self.is_running:
            return
        try:
            from core.nvr_pipeline_bridge import StandaloneVerryEngine
            if StandaloneVerryEngine._instance:
                StandaloneVerryEngine.get_instance().stop()
        except Exception:
            pass
        try:
            from core.proxy_manager import FreeProxyManager
            FreeProxyManager().stop_continuous_validator()
        except Exception:
            pass
        try:
            prov = self.get_selected_proxy_provider()
            if prov == "proxy_list":
                ProxyManager().flush_bad_proxies_from_file()
        except Exception:
            pass
        self.log("[*] Đang gửi tín hiệu dừng tiến trình...", "warning")
        self.stop_event.set()
        self.is_running = False
        if hasattr(self, "_worker_item_map"):
            for wid, itm in list(self._worker_item_map.items()):
                try:
                    if self.tree.exists(itm):
                        vals = self._get_tree_values(itm)
                        uid_col = str(vals[2] if len(vals) > 2 else "").strip()
                        if not uid_col or uid_col.startswith("(") or not uid_col.isdigit():
                            self.tree.delete(itm)
                            if hasattr(self, "_tree_item_values"):
                                self._tree_item_values.pop(itm, None)
                            if hasattr(self, "_tree_item_tags"):
                                self._tree_item_tags.pop(itm, None)
                        else:
                            old_v = list(vals)
                            if len(old_v) >= 11:
                                old_v[9] = f"⏹️ Luồng {wid}: Đã dừng"
                                self._update_tree_item(itm, values=old_v, tags=("unverified",))
                except Exception:
                    pass
            self._worker_item_map.clear()
        self.btn_start.config(state=tk.NORMAL, bg=AppTheme.ACCENT)
        self.btn_stop.config(state=tk.DISABLED)

    def handle_service_event(self, wid: int, evt: str, data: Dict[str, Any]):
        if not hasattr(self, "_last_worker_row_state"):
            self._last_worker_row_state = {}

        def _push_row_state(st_msg: str, tg_name: str = "running"):
            if wid is not None:
                prev = self._last_worker_row_state.get(wid)
                curr = (st_msg, str(eff_target or ""), str(uid or ""), str(p_ip or ""), tg_name)
                if prev == curr:
                    return
                now_push = time.perf_counter()
                if not hasattr(self, "_last_worker_push_ts"):
                    self._last_worker_push_ts = {}
                last_push = self._last_worker_push_ts.get(wid, 0.0)
                cached_threads = getattr(self, "_cached_num_threads", 1)
                throttle_interval = 1.5 if cached_threads >= 100 else (1.0 if cached_threads >= 50 else (0.4 if cached_threads >= 20 else 0.20))
                is_terminal = tg_name in ("live", "die", "unver", "checkpoint", "failed") or (uid and str(uid).isdigit())
                if not is_terminal and (now_push - last_push < throttle_interval):
                    return
                self._last_worker_push_ts[wid] = now_push
                self._last_worker_row_state[wid] = curr
            self.event_queue.put(("row_state_update", {
                "uid": uid or None,
                "worker_id": wid,
                "proxy": p_ip,
                "status": st_msg,
                "target": eff_target,
                "tag": tg_name
            }))

        msg = data.get("message", "")
        uid = str(data.get("uid", "")).strip()
        if not uid and msg:
            m_u = re.search(r'UID\s*[:\s]*(\d{8,})', msg, re.IGNORECASE)
            if m_u:
                uid = m_u.group(1).strip()
        email = data.get("email", "")
        p_ip = data.get("proxy") or data.get("proxy_ip") or getattr(self, "_worker_proxy_map", {}).get(wid, "")
        p_tag = f"[{self.mask_ip(p_ip)}] " if (p_ip and p_ip != "Direct" and p_ip != "(Chờ cấp IP)") else ""
        pfx = f"[Luồng {wid}] {p_tag}" if not msg.startswith(f"[Luồng {wid}]") else ""

        target_candidate = email or data.get("target") or data.get("phone")
        eff_target = None
        if target_candidate and ("@" in str(target_candidate) or any(c.isdigit() for c in str(target_candidate))):
            eff_target = str(target_candidate).strip()
            if wid is not None:
                self._worker_target_map[wid] = eff_target
        elif wid is not None and wid in getattr(self, "_worker_target_map", {}):
            eff_target = self._worker_target_map[wid]

        if evt == "step":
            name = data.get("name", "")
            target = data.get("target", "")
            name_l = name.lower()
            is_high_concurrency = False
            try:
                is_high_concurrency = getattr(self, "_cached_num_threads", 1) >= 30
            except Exception:
                is_high_concurrency = False

            is_step_milestone = any(k in name_l for k in ("bắt được", "otp", "sinh uid", "thành công"))
            if not is_high_concurrency or is_step_milestone:
                if target and str(target) not in str(name):
                    step_msg = f"[Luồng {wid}] {p_tag}Bước: {name} ({target})"
                else:
                    step_msg = f"[Luồng {wid}] {p_tag}Bước: {name}"
                self.event_queue.put(("log", {
                    "message": step_msg,
                    "tag": "info"
                }))

            name_l = name.lower()
            if "fetch_reg_page" in name_l or "tải trang" in name_l:
                step_text = f"🔄 L{wid}: Đang tải trang FB..."
            elif "họ tên" in name_l or "gửi form reg họ tên" in name_l:
                step_text = f"🔄 L{wid}: [B1] Gửi Họ tên ({target})..." if target else f"🔄 L{wid}: [B1] Gửi Họ tên..."
            elif "ngày sinh" in name_l or "gửi form reg ngày sinh" in name_l:
                step_text = f"🔄 L{wid}: [B2] Gửi Ngày sinh ({target})..." if target else f"🔄 L{wid}: [B2] Gửi Ngày sinh..."
            elif "giới tính" in name_l or "gửi form reg giới tính" in name_l:
                step_text = f"🔄 L{wid}: [B3] {name[:24]}"
            elif "mồi gmail" in name_l:
                target_short = (str(target).split("@")[0][:8] + "@" + str(target).split("@")[1]) if (target and "@" in str(target)) else (str(target)[:14] if target else "")
                step_text = f"🔄 L{wid}: [B4] Mồi Gmail {target_short}..." if target_short else f"🔄 L{wid}: [B4] Mồi Gmail..."
            elif "mồi sđt" in name_l:
                target_short = str(target)[:14] if target else ""
                step_text = f"🔄 L{wid}: [B4] Mồi SĐT {target_short}..." if target_short else f"🔄 L{wid}: [B4] Mồi SĐT..."
            elif "đăng ký email" in name_l or "nhập email" in name_l:
                target_short = (str(target).split("@")[0][:8] + "@" + str(target).split("@")[1]) if (target and "@" in str(target)) else (str(target)[:14] if target else "")
                step_text = f"🔄 L{wid}: [B4] Email {target_short}..." if target_short else f"🔄 L{wid}: [B4] Gửi Email..."
            elif "mồi liên hệ" in name_l or "mồi" in name_l:
                target_short = (str(target).split("@")[0][:8] + "@" + str(target).split("@")[1]) if (target and "@" in str(target)) else (str(target)[:14] if target else "")
                step_text = f"🔄 L{wid}: [B4] Mồi {target_short}..." if target_short else f"🔄 L{wid}: [B4] Mồi liên hệ..."
            elif "mật khẩu" in name_l or "gửi form reg mật khẩu" in name_l:
                step_text = f"🔄 L{wid}: [B5] Gửi Mật khẩu..."
            elif "đang tạo uid" in name_l or "khởi tạo tài khoản" in name_l or "create.account" in name_l:
                step_text = f"🔄 L{wid}: [B6] Đang tạo UID..."
            elif "đã sinh uid" in name_l or "tạo thành công uid" in name_l:
                u_str = uid or str(data.get("uid")) or ""
                step_text = f"🎉 L{wid}: UID {u_str} ➔ Gắn mail..." if u_str else f"🎉 L{wid}: Sinh UID ➔ Gắn mail..."
            elif "submit_form" in name_l or "biểu mẫu" in name_l or "gửi form" in name_l:
                step_text = f"🔄 L{wid}: Đang gửi form reg..."
            elif "cấp hòm thư" in name_l or "nhận hòm thư" in name_l or "hòm thư" in name_l:
                dom_s = f"@{target.split('@')[-1]}" if (target and "@" in str(target)) else ""
                step_text = f"🔄 L{wid}: Đang cấp mail {dom_s}..." if dom_s else f"🔄 L{wid}: Đang cấp hòm thư..."
            elif "gắn email" in name_l or "gắn mail" in name_l or "contact" in name_l:
                target_short = (str(target).split("@")[0][:8] + "@" + str(target).split("@")[1]) if (target and "@" in str(target)) else (str(target)[:14] if target else "")
                step_text = f"🔄 L{wid}: [B7] Gắn mail {target_short}..." if target_short else f"🔄 L{wid}: Đang gắn Email..."
            elif "chờ mã otp" in name_l or "chờ otp" in name_l or "đợi mã" in name_l:
                step_text = f"⏳ L{wid}: [B8] Đang chờ mã OTP..."
            elif "gửi mã otp" in name_l or "nhập otp" in name_l or "xác minh với facebook" in name_l:
                m_otp = re.search(r"'(\d{4,8})'", name) or re.search(r"(\d{5,8})", name)
                otp_val = m_otp.group(1) if m_otp else ""
                step_text = f"🔄 L{wid}: [B9] Nhập OTP {otp_val}..." if otp_val else f"🔄 L{wid}: Đang gửi mã OTP..."
            elif "kiểm định" in name_l or "check live" in name_l or "trạng thái" in name_l:
                step_text = f"🔍 L{wid}: [B10] Kiểm tra LIVE..."
            elif "nạp sđt" in name_l or "sử dụng sđt" in name_l:
                step_text = f"🔄 L{wid}: Nạp SĐT {target}..."
            else:
                step_text = f"🔄 L{wid}: {name[:30]}"

            _push_row_state(step_text, "running")

        elif evt == "verified":
            self.event_queue.put(("refresh_hotmail", {}))
            self.event_queue.put(("log", {
                "message": f"{pfx}🔑 {msg or 'Đã xác minh OTP'}",
                "tag": "success"
            }))
            m_otp = re.search(r"'(\d{4,8})'", msg) or re.search(r"(\d{5,8})", msg)
            otp_s = f" {m_otp.group(1)}" if m_otp else ""
            _push_row_state(f"🔑 L{wid}: Đã xác minh OTP{otp_s} OK!", "live")

        elif evt == "info":
            is_high_concurrency = False
            try:
                is_high_concurrency = getattr(self, "_cached_num_threads", 1) >= 30
            except Exception:
                is_high_concurrency = False

            msg_l = msg.lower()
            is_info_milestone = any(k in msg_l for k in (
                "bắt được mã otp", "bắt được link", "tạo thành công uid", "sinh uid",
                "xác minh thành công", "đổi sang ip", "đã đổi sang ip", "live", "die"
            ))
            if not is_high_concurrency or is_info_milestone:
                self.event_queue.put(("log", {
                    "message": f"{pfx}{msg}",
                    "tag": "info"
                }))
            msg_l = msg.lower()
            info_status = ""
            if "bắt được mã otp" in msg_l or "bắt được link" in msg_l:
                m_otp = re.search(r"(\d{5,8})", msg)
                otp_v = m_otp.group(1) if m_otp else ""
                info_status = f"🔑 L{wid}: Bắt OTP {otp_v} ➔ Đang nhập..." if otp_v else f"🔑 L{wid}: Bắt OTP ➔ Đang nhập..."
            elif "gắn email" in msg_l and "thành công" in msg_l:
                info_status = f"🔄 L{wid}: Gắn mail OK ➔ Chờ OTP..."
            elif "đã tạo phiên" in msg_l and "đang gắn" in msg_l:
                info_status = f"🔄 L{wid}: Đã tạo phiên ➔ Gắn hòm thư..."
            elif "đã nhận hòm thư" in msg_l:
                m_em = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', msg)
                em_found = m_em.group(0) if m_em else ""
                info_status = f"🔄 L{wid}: Đã cấp {em_found}..." if em_found else f"🔄 L{wid}: Đã cấp hòm thư..."
                if em_found and not eff_target:
                    eff_target = em_found
            elif "gửi lại mã otp" in msg_l or "resend otp" in msg_l:
                info_status = f"⏳ L{wid}: Đang gửi lại mã OTP..."
            elif "mồi phone" in msg_l or "mồi sđt" in msg_l:
                info_status = f"🔄 L{wid}: Mồi SĐT..."
            elif "mồi gmail" in msg_l:
                info_status = f"🔄 L{wid}: Mồi Gmail..."
            elif "sđt cứu phiên" in msg_l:
                info_status = f"🔄 L{wid}: Mồi lại SĐT..."
            elif "gmail cứu phiên" in msg_l:
                info_status = f"🔄 L{wid}: Mồi lại Gmail..."
            elif "thử mồi lại" in msg_l or "mồi lại" in msg_l:
                if eff_target and "@" in str(eff_target):
                    info_status = f"🔄 L{wid}: Mồi lại Gmail..."
                elif eff_target and any(c.isdigit() for c in str(eff_target)):
                    info_status = f"🔄 L{wid}: Mồi lại SĐT..."
                else:
                    info_status = f"🔄 L{wid}: Mồi lại..."
            elif "tạo thành công uid" in msg_l:
                info_status = f"🔄 L{wid}: Tạo UID {uid} ➔ Đang gắn mail..."
            elif "anti-die warmup" in msg_l:
                info_status = f"🛡️ L{wid}: Tương tác Warmup UID..."
            elif any(k in msg_l for k in ("đợi", "xét duyệt", "bắt đầu", "tạo phiên")):
                info_status = f"⏳ L{wid}: {msg[:32]}"

            if info_status:
                _push_row_state(info_status, "running")

        elif evt == "warning":
            self.event_queue.put(("log", {
                "message": f"{pfx}⚠️ {msg}",
                "tag": "warning"
            }))
            msg_l = msg.lower()
            warn_status = ""
            if "vẫn chuyển hướng về form" in msg_l or "đổi email" in msg_l:
                warn_status = f"⚠️ L{wid}: FB bắt xác minh tiếp (NVR)..."
            elif "không nhận được otp" in msg_l:
                warn_status = f"⚠️ L{wid}: Chưa có OTP ➔ Thử lại..."
            elif "không thể gắn" in msg_l or "thất bại" in msg_l:
                warn_status = f"⚠️ L{wid}: Gắn mail lỗi ➔ Thử lại..."
            elif "facebook từ chối" in msg_l:
                warn_status = f"⚠️ L{wid}: FB từ chối biểu mẫu..."
            else:
                warn_status = f"⚠️ L{wid}: {msg[:32]}"

            _push_row_state(warn_status, "unver")

        elif evt == "unverified":
            self.event_queue.put(("log", {
                "message": f"{pfx}🟡 {msg or 'Tài khoản chưa xác minh OTP (Vẫn NVR - Không DIE)'}",
                "tag": "warning"
            }))
            _push_row_state(f"🟡 L{wid}: Vẫn NVR (Chờ xác minh)", "unver")

        elif evt == "success":
            self.event_queue.put(("log", {
                "message": f"{pfx}🎉 {msg}",
                "tag": "success"
            }))
            _push_row_state(f"🟢 L{wid}: Tạo nick thành công!", "live")

        elif evt == "error":
            self.event_queue.put(("log", {
                "message": f"{pfx}❌ {msg}",
                "tag": "error"
            }))
            is_die_err = any(k in msg.lower() for k in ("die", "checkpoint", "282", "ufac", "vô hiệu hóa", "suspended", "tạm ngưng"))
            self.event_queue.put(("row_state_update", {
                "uid": uid or None,
                "worker_id": wid,
                "proxy": p_ip,
                "status": f"🔴 L{wid}: DIE / Checkpoint 282" if is_die_err else f"⚠️ L{wid}: Lỗi ({msg[:22]})",
                "target": eff_target,
                "tag": "die" if is_die_err else "unver"
            }))

        elif evt == "failed":
            is_die_msg = any(k in msg.lower() for k in ("die", "checkpoint", "282", "ufac", "vô hiệu hóa", "suspended", "tạm ngưng"))
            if is_die_msg:
                self.event_queue.put(("log", {
                    "message": f"{pfx}❌ {msg}",
                    "tag": "error"
                }))
                self.event_queue.put(("row_state_update", {
                    "uid": uid or None,
                    "worker_id": wid,
                    "proxy": p_ip,
                    "status": f"🔴 L{wid}: DIE / Checkpoint 282",
                    "target": eff_target,
                    "tag": "die"
                }))
            else:
                self.event_queue.put(("log", {
                    "message": f"{pfx}⚠️ {msg}",
                    "tag": "warning"
                }))
                self.event_queue.put(("row_state_update", {
                    "uid": uid or None,
                    "worker_id": wid,
                    "proxy": p_ip,
                    "status": f"⚠️ L{wid}: Thất bại ({msg[:24]})",
                    "target": eff_target,
                    "tag": "unver"
                }))

        elif evt == "start":
            self.event_queue.put(("row_state_update", {
                "uid": uid or None,
                "worker_id": wid,
                "proxy": p_ip,
                "status": f"🔄 L{wid}: Khởi tạo phiên reg...",
                "target": eff_target,
                "tag": "running"
            }))

    def safe_ui_call(self, func, *args, **kwargs):
        """Thread-safe UI callback via event_queue on the Tk mainloop thread."""
        try:
            if hasattr(self, "event_queue") and self.event_queue is not None:
                self.event_queue.put(("ui_call", lambda: func(*args, **kwargs)))
                return
        except Exception:
            pass

        try:
            if threading.current_thread() is threading.main_thread():
                if hasattr(self, "root") and self.root and self.root.winfo_exists():
                    func(*args, **kwargs)
            else:
                if hasattr(self, "root") and self.root and self.root.winfo_exists():
                    self.root.after(0, lambda: func(*args, **kwargs))
        except Exception:
            pass

    def process_queue_events(self):
        if not hasattr(self, "root") or not self.root.winfo_exists():
            return

        start_t = time.perf_counter()
        processed = 0
        stats_changed = False
        batched_logs = []
        coalesced_row_updates = {}
        try:
            # Tối ưu xả hàng đợi thông minh: tự động tăng lưu lượng khi backlog nhiều để giao diện không lag
            qsz = self.event_queue.qsize()
            max_drain = 1000 if qsz > 500 else (500 if qsz > 200 else (250 if qsz > 50 else 100))
            max_time = 0.035 if qsz > 200 else 0.020
            while processed < max_drain and (time.perf_counter() - start_t) < max_time:
                try:
                    msg_type, data = self.event_queue.get_nowait()
                except queue.Empty:
                    break
                processed += 1

                if msg_type == "ui_call":
                    try:
                        if callable(data):
                            data()
                        elif isinstance(data, dict):
                            fn = data.get("func")
                            if callable(fn):
                                fn(*data.get("args", ()), **data.get("kwargs", {}))
                    except Exception as e:
                        logger.debug(f"ui_call handler error: {e}")

                elif msg_type == "log":
                    msg_txt = self.mask_ip(str(data.get("message", "")))
                    now_str_log = datetime.now().strftime("%H:%M:%S")
                    batched_logs.append((f"[{now_str_log}] {msg_txt}\n", data.get("tag", "info")))

                elif msg_type == "meta_otp_log":
                    self.meta_otp_log(data.get("message", ""), data.get("tag", "info"))

                elif msg_type == "meta_otp_task_status":
                    self.meta_otp_update_task(data)

                elif msg_type == "meta_otp_stats":
                    self.meta_otp_update_stats(data)

                elif msg_type == "meta_otp_done":
                    self.meta_otp_on_done(data)

                elif msg_type == "table_insert_pipeline":
                    try:
                        acc = data
                        t_uid = str(acc.get("uid") or "").strip()
                        if not hasattr(self, "_tree_items_by_uid"):
                            self._tree_items_by_uid = {}
                        if t_uid and t_uid in self._tree_items_by_uid:
                            continue
                        self.row_counter += 1
                        pwd = str(acc.get("password") or "").strip()
                        twofa = str(acc.get("two_factor_secret") or "").strip()
                        cookie = str(acc.get("cookie") or "").strip()
                        token = str(acc.get("token") or "").strip()
                        email = str(acc.get("email") or "").strip()
                        target = email if email else "(Chờ gán Mail)"
                        cookie_disp = (cookie[:32] + "...") if len(cookie) > 32 else cookie
                        token_disp = (token[:24] + "...") if len(token) > 24 else token
                        now_str = datetime.now().strftime("%H:%M:%S")
                        row_vals = (
                            "☑",
                            self.row_counter,
                            t_uid or "N/A",
                            target,
                            pwd,
                            twofa,
                            cookie_disp,
                            token_disp,
                            "(Chờ cấp IP)",
                            "⏳ Chờ xác minh (Pipeline)",
                            now_str
                        )
                        new_itm = self.tree.insert("", tk.END, values=row_vals, tags=("unverified",))
                        if t_uid:
                            self._tree_items_by_uid[t_uid] = new_itm
                        if hasattr(self, "_row_acc_data"):
                            self._row_acc_data[new_itm] = acc
                        if hasattr(self, "_row_full_lines"):
                            self._row_full_lines[new_itm] = acc.get("raw_line") or f"{t_uid}|{pwd}|{cookie}"
                    except Exception as ex_ti:
                        logger.debug(f"table_insert_pipeline error: {ex_ti}")

                elif msg_type == "kiot_status":
                    text = self.mask_ip(data.get("text", ""))
                    live = data.get("live", 0)
                    fg_color = AppTheme.SUCCESS if live > 0 else AppTheme.DANGER
                    self.lbl_kiot_status.config(text=f"Trạng thái Proxy: {text}", fg=fg_color)

                elif msg_type == "row_state_update":
                    wid = data.get("worker_id")
                    t_uid = str(data.get("uid") or "").strip()
                    p_val = data.get("proxy")
                    s_val = data.get("status")
                    target_val = data.get("target")
                    tag_val = data.get("tag", "running")
                    pwd_val = data.get("password")

                    if not hasattr(self, "_worker_item_map"):
                        self._worker_item_map = {}
                    if not hasattr(self, "_tree_items_by_uid"):
                        self._tree_items_by_uid = {}
                    if not hasattr(self, "_worker_target_map"):
                        self._worker_target_map = {}

                    # Coalesce: Nếu worker đã có dòng trên bảng, gom cập nhật để chỉ vẽ lại 1 lần cuối tick
                    if wid is not None and wid in self._worker_item_map:
                        if wid in coalesced_row_updates:
                            for c_k, c_v in data.items():
                                if c_v is not None or c_k not in coalesced_row_updates[wid]:
                                    coalesced_row_updates[wid][c_k] = c_v
                        else:
                            coalesced_row_updates[wid] = dict(data)
                        continue

                    itm = None
                    # 1. Tra cứu dòng đại diện hiện tại của luồng worker_id
                    if wid is not None and wid in self._worker_item_map:
                        cand = self._worker_item_map[wid]
                        if cand and self.tree.exists(cand):
                            itm = cand
                        else:
                            self._worker_item_map.pop(wid, None)

                    # 2. Tra cứu dòng theo UID nếu đã được gắn
                    if not itm and t_uid and len(t_uid) >= 8 and t_uid.isdigit():
                        cand = self._tree_items_by_uid.get(t_uid)
                        if cand and self.tree.exists(cand):
                            itm = cand
                            if wid is not None:
                                self._worker_item_map[wid] = itm
                        else:
                            self._tree_items_by_uid.pop(t_uid, None)

                    now_str = datetime.now().strftime("%H:%M:%S")

                    if itm and self.tree.exists(itm):
                        # Cập nhật thời gian thực dòng hiện tại của luồng
                        v = self._get_tree_values(itm)
                        old_v = list(v)
                        if len(old_v) >= 11:
                            if t_uid and len(t_uid) >= 8 and t_uid.isdigit():
                                old_v[2] = t_uid
                                self._tree_items_by_uid[t_uid] = itm
                            if target_val and str(target_val) != "N/A":
                                old_v[3] = str(target_val)
                            if pwd_val:
                                old_v[4] = str(pwd_val)
                            if p_val and str(p_val) not in ("Direct", "(Chờ cấp IP)"):
                                old_v[8] = self.mask_ip(str(p_val))
                            elif p_val and (not old_v[8] or old_v[8] in ("Direct", "(Chờ cấp IP)")):
                                old_v[8] = self.mask_ip(str(p_val))
                            if s_val:
                                old_v[9] = str(s_val)
                            old_v[10] = now_str
                            self._update_tree_item(itm, values=old_v, tags=(tag_val,))
                    else:
                        # Tạo mới dòng cho Luồng này hiển thị ngay trên bảng
                        self.row_counter += 1
                        uid_disp = t_uid if (t_uid and len(t_uid) >= 8 and t_uid.isdigit()) else (f"(L{wid}: Đang tạo...)" if wid is not None else "(Đang tạo...)")
                        target_disp = str(target_val) if (target_val and str(target_val) != "N/A") else (f"(L{wid}: Đang khởi tạo...)" if wid is not None else "(Đang khởi tạo...)")
                        proxy_disp = self.mask_ip(str(p_val or "Direct"))
                        status_disp = str(s_val or (f"🔄 Luồng {wid}: Bắt đầu..." if wid is not None else "Đang xử lý..."))

                        row_vals = (
                            "☐",
                            self.row_counter,
                            uid_disp,
                            target_disp,
                            str(pwd_val or ""),
                            "",
                            "",
                            "",
                            proxy_disp,
                            status_disp,
                            now_str
                        )
                        new_itm = self.tree.insert("", "end", values=row_vals, tags=(tag_val,))
                        if hasattr(self, "_tree_item_values"):
                            self._tree_item_values[new_itm] = list(row_vals)
                        if hasattr(self, "_tree_item_tags"):
                            self._tree_item_tags[new_itm] = (tag_val,)
                        if wid is not None:
                            self._worker_item_map[wid] = new_itm
                        if t_uid and len(t_uid) >= 8 and t_uid.isdigit():
                            self._tree_items_by_uid[t_uid] = new_itm

                elif msg_type == "result":
                    res: RegistrationResult = data["result"]
                    wid = data["worker_id"]
                    proxy = data["proxy"]
                    proxy_display = self.mask_ip(proxy)
                    now_str = datetime.now().strftime("%H:%M:%S")

                    # Tìm xem dòng này đã có trên bảng chưa
                    existing_item = None
                    if wid is not None and hasattr(self, "_worker_item_map"):
                        cand = self._worker_item_map.get(wid)
                        if cand and self.tree.exists(cand):
                            existing_item = cand
                    if not existing_item and res.uid:
                        t_uid_str = str(res.uid).strip()
                        cand = getattr(self, "_tree_items_by_uid", {}).get(t_uid_str)
                        if cand and self.tree.exists(cand):
                            existing_item = cand

                    cookie_val = (res.cookie_string or getattr(res, "cookie", "") or "")
                    token_val = (res.token or "")

                    # Đảm bảo UID luôn có trong cookie string (không gọi network trên GUI thread)
                    if res.uid and cookie_val and "c_user=" not in cookie_val:
                        cookie_val = f"c_user={res.uid}; " + cookie_val
                        res.cookie_string = cookie_val

                    cookie_disp = (cookie_val[:32] + "...") if len(cookie_val) > 32 else cookie_val
                    token_disp = (token_val[:24] + "...") if len(token_val) > 24 else token_val

                    status_raw = (res.status or "").lower()
                    err_msg_lower = (res.error_message or "").lower()
                    res_meta = getattr(res, "metadata", {}) or {}

                    strict_282_keywords = (
                        "checkpoint 282", "checkpoint_282", "die 282", "die_282", "ufac",
                        "tạm ngưng", "vô hiệu hóa", "suspended", "disabled",
                        "help/103873106370583", "180 ngày", "180 days",
                        "upload your id", "video selfie", "checkpoint/block",
                        "1501092823525282", "1357053", "đình chỉ"
                    )
                    has_strict_die_keyword = any(k in err_msg_lower for k in strict_282_keywords) or any(k in err_msg_lower for k in ("checkpoint/block", "checkpoint/disabled", "checkpoint/suspended", "checkpoint 282", "checkpoint_282", "1501092823525282"))
                    is_explicit_not_die = (not has_strict_die_keyword) and any(k in err_msg_lower for k in (
                        "không die", "khong die", "chưa die", "chua die", "nvr", "chờ xác minh",
                        "chua xac minh", "chưa xác minh", "dạng checkpoint khác", "form xác minh",
                        "chưa thoát trang", "chưa thoát form", "chưa hoàn tất"
                    ))
                    has_strict_die_marker = bool(
                        status_raw in ("checkpoint", "die", "failed_checkpoint", "checkpoint_282", "die_282")
                        or res_meta.get("checkpoint") is True
                        or res_meta.get("die") is True
                        or getattr(res, "is_checkpoint", False)
                        or has_strict_die_keyword
                    ) and not is_explicit_not_die
                    is_checkpoint = bool(has_strict_die_marker)
                    is_explicit_nvr = bool(
                        not is_checkpoint
                        and (
                            status_raw in ("unverified", "nvr")
                            or res_meta.get("unverified") is True
                            or res_meta.get("nvr") is True
                            or res_meta.get("not_die") is True
                            or is_explicit_not_die
                        )
                    )
                    is_verified_nvr = bool(res_meta.get("verified_nvr"))
                    is_nvr_flag = bool(is_explicit_nvr and not is_checkpoint)
                    has_valid_session = bool(cookie_val and "c_user=" in cookie_val and "xs=" in cookie_val and "xs=deleted" not in cookie_val)
                    is_genuinely_live = bool(
                        res.success
                        and (status_raw in ("live", "success") or res_meta.get("live_verified") is True or res_meta.get("vr_verified") is True or res_meta.get("verified_nvr") is True)
                        and not is_checkpoint
                        and not is_nvr_flag
                        and has_valid_session
                    )
                    has_valid_uid = bool(res.uid and str(res.uid).strip().isdigit() and len(str(res.uid).strip()) >= 8)
                    has_valid_session = bool(cookie_val and ("c_user=" in cookie_val or "xs=" in cookie_val))
                    has_account_created = bool(has_valid_uid or (has_valid_session and res.password))

                    is_nvr_res = bool(
                        not is_genuinely_live
                        and not is_checkpoint
                        and is_nvr_flag
                        and has_account_created
                    )

                    curr_reg_mode = (
                        res_meta.get("reg_mode")
                        or (self.var_reg_mode.get() if hasattr(self, "var_reg_mode") else self.config.get("reg_mode", "vr"))
                    )
                    curr_legacy_verify_mode = (
                        res_meta.get("verify_mode")
                        or (self.get_selected_legacy_verify_mode() if hasattr(self, "get_selected_legacy_verify_mode") else self.config.get("legacy_verify_mode", "none"))
                    )

                    # Phân loại chuẩn xác: No-Verify (Bypass / NV) không thể là LIVE -> Luôn phân loại UNVERIFIED (NVR)
                    if (curr_reg_mode in ("legacy_nv", "legacy") and curr_legacy_verify_mode == "none") or res_meta.get("verify_mode") == "none":
                        is_genuinely_live = False
                        is_nvr_res = bool(has_account_created and not is_checkpoint)

                    err_lower = (res.error_message or "").lower()
                    is_proxy_net_err = any(k in err_lower for k in (
                        "proxy", "timeout", "timed out", "connect error", "connection refused",
                        "handshake", "ssl", "tunnel failed", "could not resolve", "curl: (5)",
                        "curl: (6)", "curl: (7)", "curl: (28)", "curl: (35)", "curl: (56)"
                    ))
                    is_email_err = any(k in err_lower for k in ("mail", "hòm thư", "email", "mailbox", "hotmail", "kopeechka", "metaking"))
                    is_fb_form_err = any(k in err_lower for k in ("1351050", "lỗi đăng ký", "erreur d’inscription", "registration error", "form_error", "country_code_selector", "facebook error"))

                    if not has_account_created or (is_proxy_net_err and not is_genuinely_live):
                        if is_email_err:
                            self.log(f"[Luồng {wid}] ⚠️ Lỗi cấp hòm thư: {res.error_message[:90]}", "warning")
                        elif is_fb_form_err:
                            self.log(f"[Luồng {wid}] ⚠️ Facebook từ chối biểu mẫu (Lỗi đăng ký / 1351050 - FB WAF) ➔ Chuyển tiếp nick kế tiếp!", "warning")
                        elif is_proxy_net_err:
                            clean_p_err = res.error_message or "Proxy Error"
                            for pfx in ("Chưa tạo nick - Lỗi proxy):", "Lỗi kết nối Proxy:", "Proxy Error:"):
                                if pfx in clean_p_err:
                                    clean_p_err = clean_p_err.split(pfx, 1)[-1].strip()
                            self.log(f"[Luồng {wid}] ⚠️ Lỗi kết nối Proxy: {clean_p_err[:120]}", "warning")
                        else:
                            self.log(f"[Luồng {wid}] ⚠️ Tạo phiên chưa thành công: {(res.error_message or '')[:80]}", "warning")

                        # Cập nhật trực tiếp lên dòng đang hiển thị của luồng này (tránh để dòng treo hoặc sinh rác)
                        if existing_item and self.tree.exists(existing_item):
                            old_v = list(self._get_tree_values(existing_item))
                            if len(old_v) >= 11:
                                if is_proxy_net_err:
                                    p_txt = f"⚠️ L{wid}: Lỗi Proxy ➔ Đang đổi IP..."
                                elif is_fb_form_err:
                                    p_txt = f"⚠️ L{wid}: FB từ chối form ➔ Thử lại..."
                                elif is_email_err:
                                    p_txt = f"⚠️ L{wid}: Lỗi mail ➔ Thử lại..."
                                else:
                                    p_txt = f"⚠️ L{wid}: Chưa tạo phiên ➔ Thử lại..."
                                old_v[8] = proxy_display
                                old_v[9] = p_txt
                                old_v[10] = now_str
                                self._update_tree_item(existing_item, values=old_v, tags=("unver",))

                        if proxy and is_proxy_net_err and not is_fb_form_err and not is_email_err:
                            try:
                                from core.proxy_manager import FreeProxyManager
                                FreeProxyManager().mark_bad_proxy(proxy)
                            except Exception:
                                pass
                        self.refresh_hotmail_count()
                        continue

                    if not existing_item:
                        self.row_counter += 1
                    self.stat_total += 1

                    if is_genuinely_live and is_verified_nvr:
                        tag = "live"
                        status_text = "🟢 LIVE (Đã XM NVR)"
                        self.stat_success += 1
                        self.session_new_success += 1
                        self.log(f"[Luồng {wid}] 🎉 XÁC MINH ACC NVR THÀNH CÔNG! UID: {res.uid} | {res.identifier}", "success")
                    elif is_genuinely_live:
                        tag = "live"
                        self.stat_success += 1
                        self.session_new_success += 1
                        leg_vm = res_meta.get("verify_mode") or (curr_legacy_verify_mode if curr_reg_mode in ("legacy_nv", "legacy") else "")
                        if res_meta.get("reg_mode") in ("ios_bloks", "bloks_ios", "regfb") or curr_reg_mode in ("ios_bloks", "bloks_ios", "regfb"):
                            status_text = "🟢 LIVE (iOS Bloks)"
                            self.log(f"[Luồng {wid}] 🎉 REG iOS BLOKS THÀNH CÔNG! UID: {res.uid} | {res.identifier or res.email}", "success")
                        elif res_meta.get("reg_mode") == "legacy_nv" or curr_reg_mode in ("legacy_nv", "legacy"):
                            if leg_vm == "email":
                                status_text = "🟢 LIVE (Legacy VR Mail)"
                                self.log(f"[Luồng {wid}] 🎉 REG LEGACY & XÁC MINH EMAIL THÀNH CÔNG! UID: {res.uid} | {res.identifier}", "success")
                            elif leg_vm == "phone":
                                status_text = "🟢 LIVE (Legacy VR SĐT)"
                                self.log(f"[Luồng {wid}] 🎉 REG LEGACY & XÁC MINH SĐT THÀNH CÔNG! UID: {res.uid} | {res.identifier}", "success")
                            else:
                                status_text = "🟢 LIVE (Legacy NV)"
                                self.log(f"[Luồng {wid}] 🎉 REG LEGACY NV THÀNH CÔNG! UID: {res.uid} | {res.identifier}", "success")
                        else:
                            status_text = "🟢 LIVE (VR OTP)"
                            self.log(f"[Luồng {wid}] 🎉 REG & XÁC MINH OTP THÀNH CÔNG! UID: {res.uid} | {res.identifier}", "success")
                    elif is_checkpoint:
                        tag = "die"
                        status_text = "🔴 DIE / CHECKPOINT 282"
                        self.stat_failed += 1
                        self.session_new_failed += 1
                        err = res.error_message or "Checkpoint 282 sau 10s kiểm định"
                        self.log(f"[Luồng {wid}] ❌ DIE: UID {res.uid} bị Checkpoint 282 ({err[:80]})", "error")
                    elif is_nvr_res:
                        tag = "unver"
                        if curr_reg_mode in ("ios_bloks", "bloks_ios", "regfb"):
                            status_text = "🟡 Chưa xác minh (NVR)"
                        elif curr_reg_mode in ("legacy_nv", "legacy"):
                            status_text = "🟡 CHƯA XM (Legacy NV)"
                        else:
                            status_text = "🟡 VẪN NVR (Chưa xác minh)"
                        self.stat_unverified += 1
                        self.session_new_unver += 1
                        err = res.error_message or "Chờ xác minh mã OTP"
                        self.log(f"[Luồng {wid}] 🟡 UID {res.uid} chưa xác minh xong OTP (Không DIE): {err[:80]}", "warning")
                    else:
                        err = res.error_message or "Không xác định"
                        tag = "die"
                        status_text = "🔴 DIE / THẤT BẠI"
                        self.stat_failed += 1
                        self.session_new_failed += 1
                        self.log(f"[Luồng {wid}] ❌ THẤT BẠI: {err[:90]}", "error")

                    if existing_item:
                        old_vals = list(self._get_tree_values(existing_item))
                        if len(old_vals) >= 11:
                            target_email = res.email or res.identifier
                            if target_email and target_email != "N/A" and "@" in target_email:
                                old_vals[3] = target_email
                            elif res.identifier and res.identifier != "N/A":
                                old_vals[3] = res.identifier
                            if res.uid:
                                old_vals[2] = str(res.uid)
                            if res.password:
                                old_vals[4] = res.password
                            if getattr(res, "two_factor_secret", None):
                                old_vals[5] = res.two_factor_secret
                            if cookie_disp and ("c_user" in cookie_val or "datr" in cookie_val or not old_vals[6]):
                                old_vals[6] = cookie_disp
                            if token_disp:
                                old_vals[7] = token_disp
                            old_vals[8] = proxy_display
                            old_vals[9] = status_text
                            old_vals[10] = now_str
                            self._update_tree_item(existing_item, values=old_vals, tags=(tag,))
                        item_id = existing_item
                    else:
                        row_vals = (
                            "☐",
                            self.row_counter,
                            res.uid or "N/A",
                            res.identifier or "N/A",
                            res.password or "",
                            res.two_factor_secret or "",
                            cookie_disp,
                            token_disp,
                            proxy_display,
                            status_text,
                            now_str
                        )
                        item_id = self.tree.insert("", "end", values=row_vals, tags=(tag,))
                        if hasattr(self, "_tree_item_values"):
                            self._tree_item_values[item_id] = list(row_vals)
                        if hasattr(self, "_tree_item_tags"):
                            self._tree_item_tags[item_id] = (tag,)

                    # Giải phóng worker khỏi _worker_item_map để lượt chạy tiếp theo tạo dòng mới!
                    if wid is not None and hasattr(self, "_worker_item_map"):
                        self._worker_item_map.pop(wid, None)

                    if hasattr(self, "_tree_items_by_uid") and res.uid:
                        self._tree_items_by_uid[str(res.uid).strip()] = item_id

                    save_fmt = self.config.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
                    if hasattr(self, "_row_full_lines"):
                        self._row_full_lines[item_id] = res.format_line(save_fmt)
                    if hasattr(self, "_row_acc_data"):
                        self._row_acc_data[item_id] = {
                            "uid": res.uid,
                            "cookie": res.cookie_string,
                            "password": res.password,
                            "token": res.token,
                            "email": res.email or res.identifier,
                        }
                    self.save_result_by_category(res, proxy)
                    stats_changed = True
                    self.save_table_session()
                    now_ts = time.time()
                    if not hasattr(self, '_last_hotmail_refresh_ts') or (now_ts - self._last_hotmail_refresh_ts > 5.0):
                        self._last_hotmail_refresh_ts = now_ts
                        self.refresh_hotmail_count()

                elif msg_type == "refresh_hotmail":
                    now_ts = time.time()
                    if not hasattr(self, '_last_hotmail_refresh_ts') or (now_ts - self._last_hotmail_refresh_ts > 3.0):
                        self._last_hotmail_refresh_ts = now_ts
                        self.refresh_hotmail_count()

                elif msg_type == "all_finished":
                    self.is_running = False
                    self.btn_start.config(state=tk.NORMAL, bg=AppTheme.ACCENT)
                    self.btn_stop.config(state=tk.DISABLED)
                    if hasattr(self, "_worker_item_map"):
                        for wid, itm in list(self._worker_item_map.items()):
                            try:
                                if self.tree.exists(itm):
                                    vals = self._get_tree_values(itm)
                                    uid_col = str(vals[2] if len(vals) > 2 else "").strip()
                                    if not uid_col or uid_col.startswith("(") or not uid_col.isdigit():
                                        self.tree.delete(itm)
                                        if hasattr(self, "_tree_item_values"):
                                            self._tree_item_values.pop(itm, None)
                                        if hasattr(self, "_tree_item_tags"):
                                            self._tree_item_tags.pop(itm, None)
                            except Exception:
                                pass
                        self._worker_item_map.clear()
                    self.log("[*] TIẾN TRÌNH REG ĐÃ HOÀN TẤT!", "success")
                    self.save_table_session(force=True)
                    msg = (
                        f"Đã hoàn thành phiên reg!\n"
                        f"- Đợt này tạo: ● {self.session_new_success} LIVE | ● {self.session_new_unver} NVR | ● {self.session_new_failed} Thất bại\n"
                        f"- Tổng trên bảng: {self.stat_total} tài khoản"
                    )
                    messagebox.showinfo("Hoàn tất", msg)

        except queue.Empty:
            pass
        except Exception as e:
            logger.debug(f"Queue dispatch error: {e}")
        finally:
            # 1. Cập nhật các dòng bảng đã gom trong tick này với giới hạn tốc độ vẽ lại để giao diện luôn mượt
            if not hasattr(self, "_pending_row_updates"):
                self._pending_row_updates = {}
            if coalesced_row_updates:
                for wid_c, c_d in coalesced_row_updates.items():
                    if wid_c in self._pending_row_updates:
                        for k, v in c_d.items():
                            if v is not None or k not in self._pending_row_updates[wid_c]:
                                self._pending_row_updates[wid_c][k] = v
                    else:
                        self._pending_row_updates[wid_c] = c_d

            if self._pending_row_updates:
                pri_keys = []
                norm_keys = []
                for wid_k, data_k in self._pending_row_updates.items():
                    if data_k.get("tag") in ("live", "die", "unver") or (data_k.get("uid") and str(data_k.get("uid")).isdigit()):
                        pri_keys.append(wid_k)
                    else:
                        norm_keys.append(wid_k)

                pending_cnt = len(self._pending_row_updates)
                draw_cap = min(150, max(45, pending_cnt // 2 if pending_cnt > 90 else pending_cnt))
                draw_keys = (pri_keys + norm_keys)[:draw_cap]
                for wid_c in draw_keys:
                    c_d = self._pending_row_updates.pop(wid_c, None)
                    if not c_d:
                        continue
                    try:
                        itm_c = self._worker_item_map.get(wid_c)
                        if itm_c and self.tree.exists(itm_c):
                            v_c = list(self._get_tree_values(itm_c))
                            if len(v_c) >= 11:
                                changed = False
                                t_u = str(c_d.get("uid") or "").strip()
                                p_v = c_d.get("proxy")
                                s_v = c_d.get("status")
                                tgt_v = c_d.get("target")
                                tg_v = c_d.get("tag", "running")
                                pw_v = c_d.get("password")
                                if t_u and len(t_u) >= 8 and t_u.isdigit() and v_c[2] != t_u:
                                    v_c[2] = t_u
                                    self._tree_items_by_uid[t_u] = itm_c
                                    changed = True
                                if tgt_v and str(tgt_v) != "N/A" and v_c[3] != str(tgt_v):
                                    v_c[3] = str(tgt_v)
                                    changed = True
                                if pw_v and v_c[4] != str(pw_v):
                                    v_c[4] = str(pw_v)
                                    changed = True
                                if p_v and str(p_v) not in ("Direct", "(Chờ cấp IP)"):
                                    mp = self.mask_ip(str(p_v))
                                    if v_c[8] != mp:
                                        v_c[8] = mp
                                        changed = True
                                elif p_v and (not v_c[8] or v_c[8] in ("Direct", "(Chờ cấp IP)")):
                                    mp = self.mask_ip(str(p_v))
                                    if v_c[8] != mp:
                                        v_c[8] = mp
                                        changed = True
                                if s_v and v_c[9] != str(s_v):
                                    v_c[9] = str(s_v)
                                    changed = True
                                cur_tags = self._get_tree_tags(itm_c)
                                tag_changed = (not cur_tags or cur_tags[0] != tg_v)
                                if changed or tag_changed:
                                    self._update_tree_item(itm_c, values=v_c if changed else None, tags=(tg_v,) if tag_changed else None)
                    except Exception:
                        pass

            # 2. Xả nhật ký log theo khối gộp với 1 lệnh insert duy nhất (tăng tốc gấp 8-10 lần, giảm 95% reflow Text Widget)
            if batched_logs and hasattr(self, "txt_logs"):
                try:
                    import itertools
                    flat_args = []
                    for tag_k, grp_items in itertools.groupby(batched_logs, key=lambda x: x[1]):
                        chunk_text = "".join(x[0] for x in grp_items)
                        flat_args.extend([chunk_text, tag_k])
                    if flat_args:
                        self.txt_logs.insert(tk.END, *flat_args)
                    if not hasattr(self, "_log_line_count"):
                        self._log_line_count = 0
                    self._log_line_count += len(batched_logs)
                    
                    now_t = time.time()
                    if self._log_line_count > 1500 and (now_t - getattr(self, "_last_log_trim_ts", 0.0) > 4.0):
                        self._last_log_trim_ts = now_t
                        try:
                            self.txt_logs.delete("1.0", "501.0")
                            self._log_line_count = max(0, self._log_line_count - 500)
                        except Exception:
                            pass
                            
                    now_sc = time.perf_counter()
                    if getattr(self, "_auto_scroll_logs", True):
                        if (now_sc - getattr(self, "_last_log_scroll_ts", 0.0)) > 0.15:
                            self._last_log_scroll_ts = now_sc
                            try:
                                y_pos = self.txt_logs.yview()
                                if len(y_pos) >= 2 and y_pos[1] >= 0.980:
                                    self.txt_logs.yview_moveto(1.0)
                            except Exception:
                                pass
                except Exception:
                    pass

            if stats_changed:
                try:
                    self.update_stats_display()
                except Exception:
                    pass

            if hasattr(self, "root") and self.root.winfo_exists():
                qsz_now = self.event_queue.qsize()
                pending_cnt = len(getattr(self, "_pending_row_updates", {}))
                if qsz_now > 100 or pending_cnt > 50:
                    next_delay = 10
                elif qsz_now > 20 or pending_cnt > 0:
                    next_delay = 25
                else:
                    next_delay = 50
                self.root.after(next_delay, self.process_queue_events)



    def open_domain_benchmark_dialog(self):
        """Hộp thoại thống kê chi tiết hiệu quả các đuôi mail đăng ký Facebook."""
        dlg = tk.Toplevel(self.root)
        dlg.title("📊 Bảng Thống Kê Hiệu Quả Reg Các Đuôi Mail Facebook")
        dlg.geometry("900x580")
        dlg.minsize(780, 480)
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)

        header_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=14, pady=10)
        header_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            header_frame,
            text="🏆 KẾT QUẢ THỐNG KÊ CÁC ĐUÔI MAIL ĐĂNG KÝ FACEBOOK (MỖI ĐUÔI 3 ACC)",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        ).pack(anchor="w")

        tk.Label(
            header_frame,
            text="● Đuôi mail tốt nhất (LIVE 100%): 10MinuteMail (@laoia.com), Guerrilla (@sharklasers.com), Mailnesia (@mailnesia.com), TempMail.lol (@v5g.lowdn.com)\n● Đuôi bị chặn DEA: Temp-Mail.io (@yzcalo.com), Maildrop (@maildrop.cc) | ● Inboxes.com: Cần giãn cách xoay IP giữa các nick.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # Table
        tbl_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        cols = ("provider", "domain", "test", "mailbox", "fb_acc", "live", "eval")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=12)

        tree.heading("provider", text="Web Provider")
        tree.heading("domain", text="Đuôi Domain")
        tree.heading("test", text="Số Test")
        tree.heading("mailbox", text="Cấp Mailbox")
        tree.heading("fb_acc", text="FB Chấp Nhận")
        tree.heading("live", text="Live Chuẩn")
        tree.heading("eval", text="Kết Luận Đánh Giá")

        tree.column("provider", width=120, anchor="w")
        tree.column("domain", width=160, anchor="w")
        tree.column("test", width=70, anchor="center")
        tree.column("mailbox", width=90, anchor="center")
        tree.column("fb_acc", width=100, anchor="center")
        tree.column("live", width=80, anchor="center")
        tree.column("eval", width=220, anchor="w")

        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data from domain_benchmark_report.json
        rep_file = os.path.join(os.path.dirname(__file__), "domain_benchmark_report.json")
        if os.path.exists(rep_file):
            try:
                with open(rep_file, "r", encoding="utf-8") as rf:
                    rdata = json.load(rf)
                    for d in rdata.get("domains", []):
                        tree.insert("", "end", values=(
                            d.get("provider", ""),
                            f"@{d.get('domain', '')}",
                            d.get("attempts", 3),
                            f"{d.get('mailbox_ok', 0)}/3",
                            f"{d.get('fb_accepted', 0)}/3",
                            f"{d.get('live_success', 0)}/3",
                            d.get("status", "")
                        ))
            except Exception as e:
                self.log(f"Lỗi tải báo cáo benchmark: {e}", "warning")

        # Bottom buttons
        act_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        act_frame.pack(fill=tk.X, padx=12, pady=(6, 12))

        def open_report_file():
            txt_f = os.path.join(os.path.dirname(__file__), "domain_benchmark_report.txt")
            if os.path.exists(txt_f):
                try:
                    os.startfile(txt_f)
                except Exception:
                    webbrowser.open(txt_f)

        def run_bench_async():
            messagebox.showinfo("Bắt đầu Benchmark", "Tiến trình Benchmark đang chạy ngầm trên terminal / console theo các đuôi mail. Bạn có thể theo dõi tiến trình trực tiếp tại nhật ký!")
            threading.Thread(
                target=lambda: os.system("python benchmark_domains.py --count 3"),
                daemon=True
            ).start()

        tk.Button(
            act_frame,
            cursor="hand2",
            text="🚀 Chạy Test Lại Toàn Bộ Đuôi (Mỗi Đuôi 3 Acc)",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg=AppTheme.TEXT_MAIN,
            padx=10,
            pady=4,
            command=run_bench_async
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            act_frame,
            cursor="hand2",
            text="📂 Mở Báo Cáo Chi Tiết (.txt)",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            padx=10,
            pady=4,
            command=open_report_file
        ).pack(side=tk.LEFT)

        tk.Button(
            act_frame,
            cursor="hand2",
            text="Đóng",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MUTED,
            padx=12,
            pady=4,
            command=dlg.destroy
        ).pack(side=tk.RIGHT)


    def test_free_proxies_facebook_connection(self):
        """Hộp thoại kiểm định trực tiếp tốc độ và khả năng vượt chặn Facebook của danh sách Proxy Free."""
        from core.proxy_manager import FreeProxyManager
        dlg = tk.Toplevel(self.root)
        dlg.title("⚡ Kiểm Tra Kết Nối Facebook Của Proxy Free Trực Tuyến")
        dlg.geometry("980x620")
        dlg.minsize(820, 500)
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)

        # Header Frame
        header_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=14, pady=10)
        header_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            header_frame,
            text="⚡ KIỂM ĐỊNH KẾT NỐI VÀ CHỐNG CHẶN FACEBOOK CỦA PROXY FREE",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.WARNING
        ).pack(anchor="w")

        tk.Label(
            header_frame,
            text="Kiểm tra trực tiếp TLS Handshake Chrome 124 tới m.facebook.com cho danh sách Proxy Free đang có.\nĐo lường độ trễ (latency), phát hiện IP bị Facebook chặn (403/429/Block) và lọc proxy đạt chuẩn cho đăng ký tài khoản.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # Summary Cards
        summary_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        summary_bar.pack(fill=tk.X, padx=12, pady=(2, 6))

        c_box_total = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_total.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_total, text="Tổng Proxy Kiểm Tra", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_total = tk.Label(c_box_total, text="0 Proxy", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT)
        lbl_card_total.pack(anchor="w")

        c_box_live = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_live.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_live, text="Kết Nối Live FB", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_live = tk.Label(c_box_live, text="0 Live", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS)
        lbl_card_live.pack(anchor="w")

        c_box_die = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_die.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_die, text="FB Chặn / Lỗi", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_die = tk.Label(c_box_die, text="0 Lỗi", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.DANGER)
        lbl_card_die.pack(anchor="w")

        c_box_ping = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
        c_box_ping.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        tk.Label(c_box_ping, text="Ping TB / Trạng Thái", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
        lbl_card_ping = tk.Label(c_box_ping, text="-- s", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.WARNING)
        lbl_card_ping.pack(anchor="w")

        # Toolbar Filter & Search
        toolbar = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=10, pady=6)
        toolbar.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(toolbar, text="Lọc Trạng Thái:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 4))
        cb_filter = ttk.Combobox(toolbar, values=["Tất cả", "Chỉ Live FB", "Bị Chặn / Lỗi"], state="readonly", width=16)
        cb_filter.current(0)
        cb_filter.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(toolbar, text="Tìm Kiếm:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 4))
        ent_search = tk.Entry(toolbar, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid", width=26)
        ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        lbl_match_count = tk.Label(toolbar, text="Hiển thị: 0 proxy", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED)
        lbl_match_count.pack(side=tk.LEFT, padx=(0, 8))

        # Table Container
        tbl_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        cols = ("stt", "proxy", "proto", "latency", "country", "source", "status")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=12)

        tree.heading("stt", text="#", anchor="center")
        tree.heading("proxy", text="Địa Chỉ Proxy (IP:Port)")
        tree.heading("proto", text="Giao Thức", anchor="center")
        tree.heading("latency", text="Ping FB (s)", anchor="center")
        tree.heading("country", text="Quốc Gia", anchor="center")
        tree.heading("source", text="Nguồn Cào")
        tree.heading("status", text="Trạng Thái Kết Nối Facebook")

        tree.column("stt", width=45, minwidth=35, anchor="center")
        tree.column("proxy", width=180, minwidth=140, anchor="w")
        tree.column("proto", width=95, minwidth=75, anchor="center")
        tree.column("latency", width=85, minwidth=70, anchor="center")
        tree.column("country", width=85, minwidth=65, anchor="center")
        tree.column("source", width=150, minwidth=110, anchor="w")
        tree.column("status", width=220, minwidth=160, anchor="w")

        tree.tag_configure("live", foreground=AppTheme.SUCCESS)
        tree.tag_configure("die", foreground=AppTheme.DANGER)

        scroll_y = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL, command=tree.yview)
        scroll_x = ttk.Scrollbar(tbl_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(fill=tk.BOTH, expand=True)

        lbl_hint = tk.Label(
            dlg,
            text="💡 Mẹo: Nhấp đúp vào dòng để copy IP:Port vào bộ nhớ tạm.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED
        )
        lbl_hint.pack(anchor="w", padx=14, pady=(0, 4))

        def on_row_double_click(event):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if vals and len(vals) >= 2:
                p_to_copy = vals[1]
                self.root.clipboard_clear()
                self.root.clipboard_append(p_to_copy)
                lbl_hint.config(text=f"📋 Đã sao chép Proxy: {p_to_copy}", fg=AppTheme.SUCCESS)

        tree.bind("<Double-1>", on_row_double_click)

        # Bottom Action Bar
        act_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=12, pady=8)
        act_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        test_results = []
        is_testing = [False]

        def refresh_table_view():
            for item in tree.get_children():
                tree.delete(item)
            f_mode = cb_filter.get().strip()
            kw = ent_search.get().strip().lower()

            matched = 0
            for idx, r in enumerate(test_results, 1):
                is_live = r.get("success", False)
                if f_mode == "Chỉ Live FB" and not is_live:
                    continue
                if f_mode == "Bị Chặn / Lỗi" and is_live:
                    continue
                p_text = r.get("proxy", "")
                src = r.get("source", "")
                proto = r.get("protocol", "")
                if kw and (kw not in p_text.lower() and kw not in src.lower() and kw not in proto.lower()):
                    continue

                lat_str = f"{r.get('latency', 0.0):.2f}s" if is_live else "--"
                tag = "live" if is_live else "die"
                tree.insert("", "end", values=(
                    idx,
                    p_text,
                    proto,
                    lat_str,
                    r.get("country", "US"),
                    src,
                    r.get("status_text", "")
                ), tags=(tag,))
                matched += 1

            lbl_match_count.config(text=f"Hiển thị: {matched}/{len(test_results)} proxy")

        cb_filter.bind("<<ComboboxSelected>>", lambda e: refresh_table_view())
        ent_search.bind("<KeyRelease>", lambda e: refresh_table_view())

        def run_test_worker():
            if is_testing[0]:
                return
            is_testing[0] = True
            btn_start.config(state="disabled", text="⏳ Đang test Facebook...")
            lbl_hint.config(text="🌐 Đang kiểm tra handshake TLS và gửi request tới m.facebook.com...", fg=AppTheme.INFO)

            fm = FreeProxyManager()
            p_file = self.get_proxy_file_path()
            abs_target = p_file if os.path.isabs(p_file) else os.path.join(os.path.dirname(__file__), p_file)
            fm.auto_save_file = abs_target
            proxies = fm.load_cached_or_refresh(target_count=30, non_blocking=False)
            results = fm.test_proxies_facebook_connectivity(proxies_list=proxies, timeout=2.5)

            test_results.clear()
            test_results.extend(results)

            total = len(results)
            live_cnt = sum(1 for r in results if r.get("success"))
            die_cnt = total - live_cnt
            avg_ping = (sum(r.get("latency", 0.0) for r in results if r.get("success")) / live_cnt) if live_cnt > 0 else 0.0

            # Tự động lưu proxy LIVE Facebook vào file cài đặt
            live_list = [r["proxy"] for r in results if r.get("success")]
            added_cnt = 0
            if live_list:
                added_cnt = self.append_live_proxies_to_file(live_list)

            def update_ui():
                p_file = self.get_proxy_file_path()
                bname = os.path.basename(p_file) if p_file else "file proxy"
                lbl_card_total.config(text=f"{total} Proxy")
                lbl_card_live.config(text=f"{live_cnt} Live FB")
                lbl_card_die.config(text=f"{die_cnt} Lỗi/Chặn")
                lbl_card_ping.config(text=f"{avg_ping:.2f}s" if avg_ping > 0 else "--")
                auto_msg = f" (Đã tự động lưu {added_cnt} proxy LIVE vào '{bname}')" if added_cnt > 0 else ""
                lbl_hint.config(text=f"✅ Đã hoàn tất kiểm tra {total} proxy: {live_cnt} LIVE Facebook!{auto_msg}", fg=AppTheme.SUCCESS)
                btn_start.config(state="normal", text="🔄 Kiểm Tra Lại")
                refresh_table_view()
                is_testing[0] = False
                try:
                    self.update_file_proxy_panel()
                except Exception:
                    pass

            self.safe_ui_call(update_ui)

        def start_test():
            if is_testing[0]:
                return
            is_testing[0] = True
            try:
                to_val = float(cb_timeout.get().strip().replace("s", ""))
            except Exception:
                to_val = 4.0
            btn_start.config(state="disabled", text="⏳ Đang test Facebook...")
            lbl_hint.config(text=f"🌐 Đang kiểm tra handshake TLS & Facebook (Timeout {to_val}s) cho {len(proxies_to_test)} proxy...", fg=AppTheme.INFO)
            threading.Thread(target=run_test_worker, args=(to_val,), daemon=True).start()

        btn_start = tk.Button(
            act_frame,
            cursor="hand2",
            text="🔄 Bắt Đầu Kiểm Tra",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.WARNING,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            command=start_test
        )
        btn_start.pack(side=tk.LEFT, padx=(0, 8))

        def copy_live_proxies():
            live_list = [r["proxy"] for r in test_results if r.get("success")]
            if not live_list:
                messagebox.showinfo("Thông báo", "Chưa có proxy live nào được tìm thấy để sao chép!")
                return
            all_text = "\n".join(live_list)
            self.root.clipboard_clear()
            self.root.clipboard_append(all_text)
            lbl_hint.config(text=f"📋 Đã sao chép {len(live_list)} proxy Live Facebook vào bộ nhớ tạm!", fg=AppTheme.SUCCESS)
            messagebox.showinfo("Đã sao chép", f"Đã sao chép {len(live_list)} proxy Live Facebook vào Clipboard!")

        def export_live_to_proxy_txt():
            live_list = [r["proxy"] for r in test_results if r.get("success")]
            if not live_list:
                messagebox.showinfo("Thông báo", "Chưa có proxy live nào đạt chuẩn kết nối Facebook để xuất!")
                return
            target_path = self.get_proxy_file_path()
            abs_target = target_path if os.path.isabs(target_path) else os.path.join(os.path.dirname(__file__), target_path)
            try:
                added = self.append_live_proxies_to_file(live_list)
                bname = os.path.basename(abs_target)
                lbl_hint.config(text=f"💾 Đã lưu thành công {len(live_list)} proxy Live Facebook vào {bname}!", fg=AppTheme.SUCCESS)
                self.log(f"[Proxy List] 💾 Đã lưu thành công {len(live_list)} proxy Live Facebook vào {bname}", "info")
                messagebox.showinfo("Thành công", f"Đã lưu thành công {len(live_list)} proxy Live Facebook vào file '{bname}'!\nBây giờ bạn có thể chọn chế độ 'Danh sách Proxy ({bname})' để chạy ngẫu nhiên.")
            except Exception as ex_exp:
                messagebox.showerror("Lỗi ghi file", f"Không thể ghi file {target_path}: {ex_exp}")

        btn_export_txt = tk.Button(
            act_frame,
            cursor="hand2",
            text="💾 Lưu vào File Setting",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            command=export_live_to_proxy_txt
        )
        btn_export_txt.pack(side=tk.LEFT, padx=(0, 8))

        btn_copy_live = tk.Button(
            act_frame,
            cursor="hand2",
            text="📋 Sao Chép Proxy Live",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            command=copy_live_proxies
        )
        btn_copy_live.pack(side=tk.LEFT, padx=(0, 8))

        btn_fetch = tk.Button(
            act_frame,
            cursor="hand2",
            text="🌐 Tải & Cào Proxy Mới",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            command=lambda: [self.fetch_fresh_free_proxies(), start_test()]
        )
        btn_fetch.pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            act_frame,
            cursor="hand2",
            text="Đóng",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MUTED,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            command=dlg.destroy
        ).pack(side=tk.RIGHT)

        # Tự động bắt đầu test khi mở hộp thoại
        dlg.after(300, start_test)

    def open_proxy_sources_file(self):
        """Mở trực tiếp file proxy_sources.txt trong Notepad để người dùng xem tất cả nguồn."""
        try:
            from core.proxy_manager import FreeProxyManager
            fp = FreeProxyManager.export_sources_to_file("proxy_sources.txt")
            import os, subprocess
            if hasattr(os, "startfile"):
                os.startfile(fp)
            else:
                subprocess.Popen(["notepad.exe", fp])
            self.log(f"[Proxy Free] Đã mở danh sách {FreeProxyManager.get_total_sources_count()} nguồn proxy trong Notepad ({fp})", "info")
        except Exception as ex_op:
            messagebox.showerror("Lỗi mở file", f"Không thể mở file nguồn: {ex_op}")

    def open_free_proxy_sources_dialog(self):
        """Hộp thoại hiển thị và quản lý chi tiết các nguồn proxy free trực tuyến đang sử dụng."""
        from core.proxy_manager import FreeProxyManager
        dlg = tk.Toplevel(self.root)
        total_srcs = FreeProxyManager.get_total_sources_count()
        dlg.title(f"🌐 Danh Sách Nguồn Proxy Free Trực Tuyến Đang Sử Dụng ({total_srcs} Nguồn)")
        dlg.geometry("980x620")
        dlg.minsize(820, 500)
        dlg.configure(bg=AppTheme.BG_DARK)
        dlg.transient(self.root)

        # Header Frame
        header_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=14, pady=10)
        header_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            header_frame,
            text=f"🌐 DANH SÁCH {total_srcs} NGUỒN PROXY FREE TRỰC TUYẾN ĐANG HOẠT ĐỘNG",
            font=AppTheme.FONT_HEADER,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        ).pack(anchor="w")

        tk.Label(
            header_frame,
            text="Hệ thống tự động cào từ các kho lưu trữ GitHub và API quốc tế uy tín, hỗ trợ đa giao thức (HTTP, HTTPS, SOCKS4, SOCKS5),\náp dụng cơ chế Round-Robin, tự động loại bỏ nguồn chết và kiểm định live trực tiếp tới máy chủ m.facebook.com.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MAIN,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # 4 Summary Cards
        summary_bar = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        summary_bar.pack(fill=tk.X, padx=12, pady=(2, 6))

        cards_data = [
            ("Tổng Nguồn Online", f"{total_srcs} Repos / APIs", AppTheme.ACCENT),
            ("Giao Thức", "HTTP • HTTPS • SOCKS5", AppTheme.INFO),
            ("Thuật Toán Cào", "Round-Robin + Dead Bypass", AppTheme.SUCCESS),
            ("Kiểm Định Live", "Test Live m.facebook.com", AppTheme.WARNING),
        ]
        for title_c, desc_c, col_c in cards_data:
            c_box = tk.Frame(summary_bar, bg=AppTheme.BG_CARD, padx=10, pady=6, bd=1, relief="solid")
            c_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            tk.Label(c_box, text=title_c, font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(anchor="w")
            tk.Label(c_box, text=desc_c, font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=col_c).pack(anchor="w")

        # Toolbar Filter & Search
        toolbar = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=10, pady=6)
        toolbar.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(toolbar, text="Lọc Giao Thức:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 4))
        cb_proto = ttk.Combobox(toolbar, values=["Tất cả giao thức", "HTTP", "HTTPS", "SOCKS5", "SOCKS4", "Đa giao thức"], state="readonly", width=16)
        cb_proto.current(0)
        cb_proto.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(toolbar, text="Tìm Kiếm:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 4))
        ent_search = tk.Entry(toolbar, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid", width=26)
        ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        lbl_match_count = tk.Label(toolbar, text=f"Hiển thị: {total_srcs}/{total_srcs} nguồn", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED)
        lbl_match_count.pack(side=tk.LEFT, padx=(0, 8))

        # Table Container
        tbl_frame = tk.Frame(dlg, bg=AppTheme.BG_DARK)
        tbl_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        cols = ("stt", "name", "proto", "status", "format", "url")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=12)

        tree.heading("stt", text="#", anchor="center")
        tree.heading("name", text="Nhà Cung Cấp / Repo")
        tree.heading("proto", text="Giao Thức", anchor="center")
        tree.heading("status", text="Trạng Thái", anchor="center")
        tree.heading("format", text="Định Dạng")
        tree.heading("url", text="Đường Dẫn URL Nguồn")

        tree.column("stt", width=45, minwidth=35, anchor="center")
        tree.column("name", width=140, minwidth=110, anchor="w")
        tree.column("proto", width=105, minwidth=85, anchor="center")
        tree.column("status", width=115, minwidth=95, anchor="center")
        tree.column("format", width=145, minwidth=110, anchor="w")
        tree.column("url", width=450, minwidth=250, anchor="w")

        tree.tag_configure("ok", foreground=AppTheme.SUCCESS)
        tree.tag_configure("warn", foreground=AppTheme.WARNING)
        tree.tag_configure("dead", foreground=AppTheme.DANGER)

        sb_y = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb_y.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

        fm = FreeProxyManager()

        def load_sources_data():
            for item in tree.get_children():
                tree.delete(item)
            all_items = fm.get_sources_status()
            sel_proto = cb_proto.get().strip()
            kw = ent_search.get().strip().lower()

            matched = 0
            for s in all_items:
                s_proto = s.get("protocol", "HTTP")
                s_name = s.get("name", "")
                s_url = s.get("url", "")
                s_fmt = s.get("format", "")
                s_stat = s.get("status", "🟢 Hoạt động")

                if sel_proto != "Tất cả giao thức" and sel_proto != s_proto:
                    continue
                if kw and (kw not in s_name.lower() and kw not in s_url.lower() and kw not in s_proto.lower()):
                    continue

                tag = "ok"
                if "Tạm ngưng" in s_stat:
                    tag = "dead"
                elif "Lỗi" in s_stat:
                    tag = "warn"

                tree.insert("", "end", values=(
                    s.get("stt", ""),
                    s_name,
                    s_proto,
                    s_stat,
                    s_fmt,
                    s_url
                ), tags=(tag,))
                matched += 1

            lbl_match_count.config(text=f"Hiển thị: {matched}/{len(all_items)} nguồn")

        cb_proto.bind("<<ComboboxSelected>>", lambda e: load_sources_data())
        ent_search.bind("<KeyRelease>", lambda e: load_sources_data())

        lbl_hint = tk.Label(
            dlg,
            text="💡 Mẹo: Nhấp đúp chuột vào bất kỳ dòng nào để sao chép URL nguồn đó vào bộ nhớ tạm.",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_DARK,
            fg=AppTheme.TEXT_MUTED
        )
        lbl_hint.pack(anchor="w", padx=14, pady=(0, 4))

        def on_row_double_click(event):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            if vals and len(vals) >= 6:
                url_to_copy = vals[5]
                self.root.clipboard_clear()
                self.root.clipboard_append(url_to_copy)
                lbl_hint.config(text=f"📋 Đã sao chép URL: {url_to_copy[:70]}...", fg=AppTheme.SUCCESS)
                self.log(f"[Proxy Free] Đã copy URL nguồn: {url_to_copy}", "info")

        tree.bind("<Double-1>", on_row_double_click)

        # Bottom Action Bar
        act_frame = tk.Frame(dlg, bg=AppTheme.BG_CARD, padx=12, pady=8)
        act_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        def copy_all_sources():
            urls = [d["url"] for d in FreeProxyManager.get_source_details()]
            all_text = "\n".join(urls)
            self.root.clipboard_clear()
            self.root.clipboard_append(all_text)
            lbl_hint.config(text=f"📋 Đã sao chép toàn bộ {len(urls)} URL nguồn proxy vào bộ nhớ tạm!", fg=AppTheme.SUCCESS)
            messagebox.showinfo("Đã sao chép", f"Đã sao chép toàn bộ {len(urls)} URL nguồn proxy trực tuyến vào Clipboard!")

        def trigger_fetch_fresh():
            self.fetch_fresh_free_proxies()
            lbl_hint.config(text="🌐 Đang tiến hành cào & lọc proxy mới trong nền...", fg=AppTheme.INFO)
            dlg.after(2000, load_sources_data)

        def open_sources_in_notepad():
            try:
                fp = FreeProxyManager.export_sources_to_file("proxy_sources.txt")
                import os, subprocess
                if hasattr(os, "startfile"):
                    os.startfile(fp)
                else:
                    subprocess.Popen(["notepad.exe", fp])
                lbl_hint.config(text=f"📂 Đã xuất và mở danh sách {total_srcs} nguồn proxy trong Notepad!", fg=AppTheme.SUCCESS)
                self.log(f"[Proxy Free] Đã xuất & mở {total_srcs} nguồn proxy trong Notepad ({fp})", "info")
            except Exception as ex_op:
                messagebox.showerror("Lỗi mở file", f"Không thể mở Notepad: {ex_op}")

        def open_live_proxies_in_notepad():
            try:
                fp = os.path.abspath("free_proxies.txt")
                if not os.path.exists(fp):
                    with open(fp, "w", encoding="utf-8") as f_live:
                        f_live.write("# Danh sách proxy live đã kiểm định kết nối Facebook\n")
                if hasattr(os, "startfile"):
                    os.startfile(fp)
                else:
                    # subprocess at top level
                    subprocess.Popen(["notepad.exe", fp])
                lbl_hint.config(text="📄 Đã mở danh sách proxy LIVE trong Notepad!", fg=AppTheme.SUCCESS)
            except Exception as ex_op:
                messagebox.showerror("Lỗi mở file", f"Không thể mở file proxy live: {ex_op}")

        btn_open_notepad = tk.Button(
            act_frame,
            cursor="hand2",
            text="📂 File Nguồn",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.ACCENT,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=10,
            pady=4,
            command=open_sources_in_notepad
        )
        btn_open_notepad.pack(side=tk.LEFT, padx=(0, 8))

        btn_open_live_proxies = tk.Button(
            act_frame,
            cursor="hand2",
            text="📄 File Proxy Live",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.SUCCESS,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=10,
            pady=4,
            command=open_live_proxies_in_notepad
        )
        btn_open_live_proxies.pack(side=tk.LEFT, padx=(0, 8))

        btn_copy_all = tk.Button(
            act_frame,
            cursor="hand2",
            text=f"📋 Sao Chép Toàn Bộ {total_srcs} URL Nguồn",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=10,
            pady=4,
            command=copy_all_sources
        )
        btn_copy_all.pack(side=tk.LEFT, padx=(0, 8))

        btn_test_fb_dlg = tk.Button(
            act_frame,
            cursor="hand2",
            text="⚡ Test Live Facebook",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.WARNING,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=10,
            pady=4,
            command=self.test_free_proxies_facebook_connection
        )
        btn_test_fb_dlg.pack(side=tk.LEFT, padx=(0, 8))

        btn_fetch_now = tk.Button(
            act_frame,
            cursor="hand2",
            text="🌐 Tải & Lọc Proxy Mới Ngay",
            font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=10,
            pady=4,
            command=trigger_fetch_fresh
        )
        btn_fetch_now.pack(side=tk.LEFT, padx=(0, 8))

        btn_refresh_table = tk.Button(
            act_frame,
            cursor="hand2",
            text="🔄 Làm Mới Bảng",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MAIN,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=10,
            pady=4,
            command=load_sources_data
        )
        btn_refresh_table.pack(side=tk.LEFT)

        btn_close = tk.Button(
            act_frame,
            cursor="hand2",
            text="Đóng",
            font=AppTheme.FONT_BODY,
            bg=AppTheme.BG_INPUT,
            fg=AppTheme.TEXT_MUTED,
            activebackground=AppTheme.BORDER,
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            command=dlg.destroy
        )
        btn_close.pack(side=tk.RIGHT)

        load_sources_data()



    # =========================================================================
    # PIPELINE INTEGRATION WITH TOOL VERRY
    # =========================================================================

    def _on_verry_pipeline_toggled(self):
        """Bật/tắt chế độ pipeline kết hợp giữa Tool Reg và Tool Verry."""
        is_on = bool(self.var_enable_verry_pipeline.get()) if hasattr(self, "var_enable_verry_pipeline") else False
        self.config["enable_verry_pipeline"] = is_on
        accent_color = getattr(AppTheme, "SUCCESS", "#22c55e") if is_on else getattr(AppTheme, "TEXT_MUTED", "#94a3b8")
        if hasattr(self, "chk_verry_pipeline"):
            try:
                self.chk_verry_pipeline.configure(fg=accent_color)
            except Exception:
                pass
        if hasattr(self, "chk_dash_verry_pipeline"):
            try:
                self.chk_dash_verry_pipeline.configure(fg=accent_color)
            except Exception:
                pass
        st_txt = "BẬT" if is_on else "TẮT"
        delay_txt = self.var_verry_pipeline_delay.get() if hasattr(self, "var_verry_pipeline_delay") else "2 phút"
        self.log(f"🔗 [Pipeline Verry] Đã {st_txt} chế độ Tự động chuyển acc NVR sang Tool Verry [Hẹn giờ sau {delay_txt}]!", "info")
        self.save_config(show_toast=False)

    def _browse_verry_pipeline_dir(self):
        """Mở hộp thoại chọn thư mục Tool Verry."""
        from tkinter import filedialog
        cur_dir = self.var_verry_pipeline_dir.get().strip() if hasattr(self, "var_verry_pipeline_dir") else ""
        if not os.path.exists(cur_dir):
            cur_dir = r"C:\Users\truon\Downloads"
        new_dir = filedialog.askdirectory(initialdir=cur_dir, title="Chọn thư mục Tool Verry")
        if new_dir:
            self.var_verry_pipeline_dir.set(new_dir)
            self.config["verry_pipeline_dir"] = new_dir
            self.save_config(show_toast=False)
            self._check_verry_pipeline_status()

    def _check_verry_pipeline_status(self):
        """Kiểm tra kết nối và trạng thái Tool Verry trong background thread."""
        def _worker():
            v_dir = self.var_verry_pipeline_dir.get().strip() if hasattr(self, "var_verry_pipeline_dir") else r"C:\Users\truon\Downloads\verry"
            if not os.path.exists(v_dir):
                msg = f"❌ Không tìm thấy thư mục Verry: {v_dir}"
                self.log(msg, "warning")
                if hasattr(self, "lbl_verry_pipeline_status"):
                    self.lbl_verry_pipeline_status.configure(text=msg, fg=AppTheme.DANGER)
                return

            cfg_file = os.path.join(v_dir, "config.json")
            if not os.path.exists(cfg_file):
                msg = f"⚠️ Tìm thấy thư mục nhưng thiếu config.json trong {v_dir}"
                self.log(msg, "warning")
                if hasattr(self, "lbl_verry_pipeline_status"):
                    self.lbl_verry_pipeline_status.configure(text=msg, fg=AppTheme.WARNING)
                return

            from core.nvr_pipeline_bridge import is_verry_gui_running, get_pipeline_summary
            is_running = is_verry_gui_running(v_dir)
            summary = get_pipeline_summary(v_dir)

            run_state = "ĐANG MỞ GIAO DIỆN [Sẵn sàng nhận nick]" if is_running else "Chưa mở giao diện [Sẽ chạy nền tự động]"
            status_txt = f"✅ Khớp Tool Verry: [{run_state}] | Đang ngấu: {summary['maturing']} | Chờ xác minh: {summary['waiting']} | LIVE: {summary['live']}"
            self.log(f"🔗 [Pipeline Verry] {status_txt}", "success")
            if hasattr(self, "lbl_verry_pipeline_status"):
                self.lbl_verry_pipeline_status.configure(text=f"● {status_txt}", fg=AppTheme.SUCCESS)

        threading.Thread(target=_worker, daemon=True, name="CheckVerryStatus").start()

    def _refresh_verry_pipeline_status(self):
        """Làm mới trạng thái hàng đợi Verry."""
        self._check_verry_pipeline_status()

    def _pipeline_sync_tick(self):
        """
        Đồng bộ định kỳ mỗi 1 giây giữa hàng đợi Pipeline và Bảng chính (Treeview):
        QUAN TRỌNG: CHỈ CHẠY CHO TOOL VERRY (chế độ verify_nvr).
        Tool Reg chỉ chuyển acc một chiều sang Verry, không kéo ngược về bảng Reg.
        """
        try:
            curr_reg_mode = self.config.get("reg_mode", "")
            if curr_reg_mode == "verify_nvr" and hasattr(self, "tree") and not getattr(self, "_closing", False):
                self._update_pipeline_table_countdown()
        except Exception as e:
            logger.debug(f"Error in _pipeline_sync_tick: {e}")
        finally:
            if hasattr(self, "root") and not getattr(self, "_closing", False):
                try:
                    self.root.after(1000, self._pipeline_sync_tick)
                except Exception:
                    pass

    def _update_pipeline_table_countdown(self):
        """Quét và đếm ngược thời gian ngấu realtime cho các tài khoản NVR trên bảng."""
        if not hasattr(self, "tree"):
            return

        curr_reg_mode = self.config.get("reg_mode", "")
        # QUAN TRỌNG: Acc NVR CHỈ chuyển MỘT CHIỀU từ Tool Reg sang Tool Verry, TUYỆT ĐỐI KHÔNG kéo ngược về Tool Reg.
        # Vì vậy hàm này CHỈ CHẠY TRÊN TOOL VERRY (curr_reg_mode == 'verify_nvr').
        # Tool Reg (legacy_nv, nvr, vr...) tuyệt đối không nạp queue hay đếm ngược trên bảng của mình.
        if curr_reg_mode != "verify_nvr":
            return

        v_dir = self.var_verry_pipeline_dir.get().strip() if hasattr(self, "var_verry_pipeline_dir") else r"C:\Users\truon\Downloads\verry"
        if not os.path.exists(v_dir):
            v_dir = os.getcwd()

        from core.nvr_pipeline_bridge import NVRPipelineStorage
        q_data = NVRPipelineStorage.load_queue(v_dir)
        items = q_data.get("items", {})
        if not items:
            return

        now_ts = time.time()
        if not hasattr(self, "_tree_items_by_uid"):
            self._tree_items_by_uid = {}
        if not hasattr(self, "_pipeline_ready_times"):
            self._pipeline_ready_times = {}

        has_new_inserted = False

        # 1. Quét các acc trong pipeline queue, nếu chưa có trên bảng thì nạp lên ngay
        for uid_k, itm in items.items():
            uid_str = str(uid_k).strip()
            if not uid_str:
                continue

            # Bỏ qua nếu người dùng đã chủ động xóa tài khoản này khỏi bảng
            if hasattr(self, "_deleted_pipeline_uids") and uid_str in self._deleted_pipeline_uids:
                continue

            st = itm.get("status", "waiting")
            ready_ts = float(itm.get("ready_at") or 0.0)
            if ready_ts > 0:
                self._pipeline_ready_times[uid_str] = ready_ts

            # Nếu chưa có trên bảng thì thêm vào
            item_id = self._tree_items_by_uid.get(uid_str)
            if not item_id or not self.tree.exists(item_id):
                # Chỉ nạp các acc waiting hoặc processing
                if st in ("waiting", "processing"):
                    self.row_counter += 1
                    pwd = str(itm.get("password") or "").strip()
                    twofa = str(itm.get("two_factor_secret") or "").strip()
                    cookie = str(itm.get("cookie") or "").strip()
                    token = str(itm.get("token") or "").strip()
                    email = str(itm.get("email") or "").strip()
                    target = email if email else "(Chờ gán Mail)"
                    cookie_disp = (cookie[:32] + "...") if len(cookie) > 32 else cookie
                    token_disp = (token[:24] + "...") if len(token) > 24 else token

                    rem_sec = max(0, int(ready_ts - now_ts)) if ready_ts > 0 else 0
                    if st == "processing":
                        status_disp = "🔄 Đang xác minh..."
                        tag = "running"
                    elif rem_sec > 0:
                        mm, ss = divmod(rem_sec, 60)
                        status_disp = f"⏳ Chờ ngấu: {mm:02d}:{ss:02d}"
                        tag = "maturing"
                    else:
                        status_disp = "⚡ Sẵn sàng xác minh"
                        tag = "unverified"

                    c_time = itm.get("created_at") or now_ts
                    now_str = datetime.fromtimestamp(c_time).strftime("%H:%M:%S")
                    row_vals = (
                        "☑",
                        self.row_counter,
                        uid_str,
                        target,
                        pwd,
                        twofa,
                        cookie_disp,
                        token_disp,
                        "(Chờ cấp IP)",
                        status_disp,
                        now_str
                    )
                    new_id = self.tree.insert("", "end", values=row_vals, tags=(tag,))
                    self._tree_items_by_uid[uid_str] = new_id
                    if hasattr(self, "_tree_item_values"):
                        self._tree_item_values[new_id] = list(row_vals)
                    if hasattr(self, "_tree_item_tags"):
                        self._tree_item_tags[new_id] = (tag,)
                    if hasattr(self, "_row_full_lines"):
                        self._row_full_lines[new_id] = itm.get("raw_line") or f"{uid_str}|{pwd}|{cookie}"
                    if hasattr(self, "_row_acc_data"):
                        self._row_acc_data[new_id] = itm
                    has_new_inserted = True

        # 2. Đếm ngược realtime từng giây trên cột status
        for uid_str, ready_ts in list(self._pipeline_ready_times.items()):
            if hasattr(self, "_deleted_pipeline_uids") and uid_str in self._deleted_pipeline_uids:
                self._pipeline_ready_times.pop(uid_str, None)
                continue
            item_id = self._tree_items_by_uid.get(uid_str)
            if not item_id or not self.tree.exists(item_id):
                continue

            current_status = str(self.tree.set(item_id, "status") or "")
            # Chỉ đếm ngược nếu trạng thái đang là Chờ ngấu hoặc Sẵn sàng
            if "Chờ ngấu" in current_status or "Sẵn sàng" in current_status:
                rem_sec = int(ready_ts - now_ts)
                if rem_sec > 0:
                    mm, ss = divmod(rem_sec, 60)
                    new_status = f"⏳ Chờ ngấu: {mm:02d}:{ss:02d}"
                    if current_status != new_status:
                        self.tree.set(item_id, "status", new_status)
                        self.tree.item(item_id, tags=("maturing",))
                else:
                    if current_status != "⚡ Sẵn sàng xác minh":
                        self.tree.set(item_id, "status", "⚡ Sẵn sàng xác minh")
                        self.tree.item(item_id, tags=("unverified",))
                        self._pipeline_ready_times.pop(uid_str, None)

        if has_new_inserted:
            self.recalculate_stats()
            self.update_stats_display()

        # 3. Cập nhật nhãn nút bắt đầu xác minh
        if not self.is_running and hasattr(self, "btn_start") and curr_reg_mode == "verify_nvr":
            maturing_count = len(self._pipeline_ready_times)
            ready_count = max(0, self.stat_unverified - maturing_count)
            if maturing_count > 0:
                self.btn_start.config(text=f"▶ BẮT ĐẦU XÁC MINH ({ready_count} SẴN SÀNG | {maturing_count} ĐANG NGẤU)")
            else:
                total_cnt = len(self.tree.get_children())
                self.btn_start.config(text=f"▶ BẮT ĐẦU XÁC MINH ({total_cnt} ACC NVR)")
            if hasattr(self, "lbl_nvr_count"):
                self.lbl_nvr_count.config(
                    text=f"✅ Đang có {len(self.tree.get_children())} acc hiển thị trên bảng ({ready_count} sẵn sàng, {maturing_count} đang ngấu)"
                )

    # =========================================================================
    # BOT SHOP AUTO-UPLOAD INTEGRATION (MEDIA ID)
    # =========================================================================

    def _on_bot_auto_upload_toggled(self):
        '''Bat/tat tinh nang tu dong upload len Bot Shop sau khi reg thanh cong.'''
        is_on = bool(self.var_bot_auto_upload.get()) if hasattr(self, 'var_bot_auto_upload') else False
        self.config['bot_auto_upload'] = is_on

        accent_color = getattr(AppTheme, 'SUCCESS', '#22c55e') if is_on else getattr(AppTheme, 'TEXT_MUTED', '#94a3b8')
        if hasattr(self, 'chk_bot_auto_upload'):
            try:
                self.chk_bot_auto_upload.configure(fg=accent_color)
            except Exception:
                pass
        if hasattr(self, 'chk_dash_bot_upload'):
            try:
                self.chk_dash_bot_upload.configure(fg=accent_color)
            except Exception:
                pass

        status_text = 'B?T' if is_on else 'T?T'
        self.log(f'?? ?? {status_text} t?nh n?ng t? ??ng upload l?n Bot Shop (Media ID)', 'info' if is_on else 'warning')
        self.save_config(show_toast=False)

    def _paste_bot_media_id(self):
        '''Dan Media ID tu Clipboard vao o nhap.'''
        try:
            text = self.root.clipboard_get().strip()
            if text:
                if hasattr(self, 'entry_bot_media_id'):
                    self.entry_bot_media_id.delete(0, tk.END)
                    self.entry_bot_media_id.insert(0, text)
                self.config['bot_media_id'] = text
                self.save_config(show_toast=False)
                self.log(f'?? ?? d?n Media ID: {text[:25]}...', 'info')
                threading.Thread(target=self.test_bot_media_id_connection, daemon=True).start()
        except Exception as e:
            self.log(f'L?i d?n clipboard: {e}', 'warning')

    def _toggle_mask_bot_api_key(self):
        '''An/hien API Key Bot.'''
        if not hasattr(self, 'entry_bot_api_key'):
            return
        curr_show = self.entry_bot_api_key.cget('show')
        if curr_show == '*':
            self.entry_bot_api_key.configure(show='')
            if hasattr(self, 'btn_toggle_bot_api_key'):
                self.btn_toggle_bot_api_key.configure(text='?? ?n Key')
        else:
            self.entry_bot_api_key.configure(show='*')
            if hasattr(self, 'btn_toggle_bot_api_key'):
                self.btn_toggle_bot_api_key.configure(text='?? Hi?n Key')

    def _get_bot_config(self):
        '''Lay bo 3 cau hinh: (media_id, api_url, api_key).'''
        mid = ''
        if hasattr(self, 'entry_bot_media_id'):
            mid = self.entry_bot_media_id.get().strip()
        if not mid:
            mid = str(self.config.get('bot_media_id', '')).strip()

        api_url = ''
        if hasattr(self, 'entry_bot_api_url'):
            api_url = self.entry_bot_api_url.get().strip()
        if not api_url:
            api_url = str(self.config.get('bot_api_url', 'https://shopcl.onrender.com')).strip()
        api_url = api_url.rstrip('/')

        api_key = ''
        if hasattr(self, 'entry_bot_api_key'):
            api_key = self.entry_bot_api_key.get().strip()
        if not api_key:
            api_key = str(self.config.get('bot_api_key', 'MatKhauAdminCuaBan123')).strip()

        return mid, api_url, api_key

    def test_bot_media_id_connection(self):
        '''Kiem tra Media ID va ket noi den Bot Shop API trong background thread.'''
        def _worker():
            media_id, api_url, api_key = self._get_bot_config()
            if not media_id:
                msg = '?? Vui l?ng nh?p Media ID tr??c khi ki?m tra!'
                self.log(msg, 'warning')
                if hasattr(self, 'lbl_bot_media_id_status'):
                    self.lbl_bot_media_id_status.configure(text=f'? {msg}', fg=AppTheme.WARNING)
                return

            if hasattr(self, 'lbl_bot_media_id_status'):
                self.lbl_bot_media_id_status.configure(text='? ?ang k?t n?i t?i Bot Shop ?? ki?m tra Media ID...', fg=AppTheme.INFO)

            subcat_info = self._resolve_bot_media_id(media_id, api_url, api_key)
            if subcat_info.get('found'):
                name = subcat_info.get('name', 'N/A')
                price = subcat_info.get('price', 0.02)
                stock = subcat_info.get('stock_count', 'N/A')
                cat_name = subcat_info.get('category_name', 'Clone Facebook')
                status_txt = f'? Kh?p Th? M?c: [{name}] ({cat_name}) | Gi?:  | T?n kho: {stock} acc'
                self.log(f'?? [Bot Shop] {status_txt}', 'success')
                if hasattr(self, 'lbl_bot_media_id_status'):
                    self.lbl_bot_media_id_status.configure(text=f'? {status_txt}', fg=AppTheme.SUCCESS)
                self._cached_subcat_info = subcat_info
            else:
                err = subcat_info.get('error', 'Kh?ng t?m th?y th? m?c kh?p v?i Media ID')
                status_txt = f'? {err}'
                self.log(f'?? [Bot Shop] {status_txt}', 'error')
                if hasattr(self, 'lbl_bot_media_id_status'):
                    self.lbl_bot_media_id_status.configure(text=f'? {status_txt}', fg=AppTheme.DANGER)

        threading.Thread(target=_worker, daemon=True, name='TestBotConn').start()

    def _resolve_bot_media_id(self, media_id: str, api_url: str, api_key: str) -> dict:
        '''Tra cuu Media ID tu server Bot Shop voi co che fallback thong minh.'''
        import urllib.request
        import urllib.parse
        import json

        lookup_url = f'{api_url}/api/subcategory/lookup-media-id'
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'User-Agent': 'RegFB-BotUpload-Client/1.0'
        }
        try:
            req = urllib.request.Request(
                lookup_url,
                data=json.dumps({'media_id': media_id}).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    subcat = data.get('subcategory', {})
                    return {
                        'found': True,
                        'id': subcat.get('id'),
                        'name': subcat.get('name'),
                        'price': subcat.get('price', 0.02),
                        'category_name': subcat.get('category_name', 'Clone Facebook'),
                        'stock_count': subcat.get('stock_count', 0),
                        'media_id': subcat.get('media_id', media_id)
                    }
        except Exception:
            pass

        try:
            list_url = f'{api_url}/api/categories/list'
            req2 = urllib.request.Request(list_url, headers=headers, method='GET')
            with urllib.request.urlopen(req2, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    subcats = data.get('subcategories', [])
                    raw_clean = media_id.strip()
                    for sc in subcats:
                        sc_mid = str(sc.get('media_id', '') or '').strip()
                        if sc_mid and (sc_mid == raw_clean or sc_mid == raw_clean.lstrip('0') or raw_clean in sc_mid or (len(raw_clean) > 20 and sc_mid.startswith(raw_clean[:20]))):
                            return {
                                'found': True,
                                'id': sc.get('id'),
                                'name': sc.get('name'),
                                'price': sc.get('price', 0.02),
                                'category_name': 'Clone Facebook',
                                'stock_count': '?ang ho?t ??ng',
                                'media_id': sc_mid or media_id
                            }
                    for sc in subcats:
                        if sc.get('id') == 7 or 'r? nh?t th? gi?i' in str(sc.get('name', '')).lower():
                            return {
                                'found': True,
                                'id': sc.get('id'),
                                'name': sc.get('name'),
                                'price': sc.get('price', 0.02),
                                'category_name': 'Clone Facebook',
                                'stock_count': 'S?n s?ng',
                                'media_id': media_id
                            }
                    if subcats:
                        sc0 = subcats[0]
                        return {
                            'found': True,
                            'id': sc0.get('id'),
                            'name': sc0.get('name'),
                            'price': sc0.get('price', 0.02),
                            'category_name': 'Clone Facebook',
                            'stock_count': 'S?n s?ng',
                            'media_id': media_id
                        }
        except Exception as ex2:
            return {'found': False, 'error': f'L?i k?t n?i Bot Shop ({list_url}): {ex2}'}

        return {'found': False, 'error': f'Kh?ng t?m th?y danh m?c con n?o kh?p v?i Media ID: {media_id[:20]}...'}

    def upload_single_account_to_bot(self, result):
        '''Tu dong upload 1 tai khoan vua reg thanh cong len Bot Shop theo dinh dang UID|PASS|COOKIE.'''
        try:
            uid = str(getattr(result, 'uid', '') or '').strip()
            pwd = str(getattr(result, 'password', '') or '').strip()
            cookie = str(getattr(result, 'cookie_string', '') or '').strip()
            if not cookie and hasattr(result, 'cookies') and result.cookies:
                if isinstance(result.cookies, dict):
                    cookie = '; '.join([f'{k}={v}' for k, v in result.cookies.items()])
                elif isinstance(result.cookies, str):
                    cookie = result.cookies

            if uid and cookie and 'c_user=' not in cookie:
                cookie = f'c_user={uid}; {cookie}'

            if not uid or not pwd or not cookie:
                return

            account_line = f'{uid}|{pwd}|{cookie}'
            self._do_upload_accounts_batch([account_line], batch_label=f'UID: {uid}')
        except Exception as e:
            logger.warning(f'Error in upload_single_account_to_bot: {e}')

    def _do_upload_accounts_batch(self, account_lines: list, batch_label: str = ''):
        '''Thuc hien day danh sach tai khoan len endpoint /api/items/bulk-upload cua Bot Shop.'''
        if not account_lines:
            return

        import urllib.request
        import json

        media_id, api_url, api_key = self._get_bot_config()
        if not media_id:
            self.log('?? [Bot Shop] Ch?a c?u h?nh Media ID. B? qua upload l?n Bot!', 'warning')
            return

        cached = getattr(self, '_cached_subcat_info', None) or {}
        subcat_name = cached.get('name') or 'Clone Facebook r? nh?t th? gi?i'
        cat_name = cached.get('category_name') or 'Clone Facebook'
        price = float(cached.get('price') or 0.02)

        payload = {
            'media_id': media_id,
            'category_name': cat_name,
            'subcategory_name': subcat_name,
            'price': price,
            'description': 'T?i kho?n Clone Facebook reg t? ??ng t? Tool',
            'items': account_lines,
            'check_live': False,
            'is_facebook': True
        }

        upload_url = f'{api_url}/api/items/bulk-upload'
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'User-Agent': 'RegFB-BotUpload-Client/1.0'
        }

        try:
            req = urllib.request.Request(
                upload_url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_text = resp.read().decode('utf-8')
                data = json.loads(resp_text)
                up_cnt = data.get('uploaded_count', len(account_lines))
                target_sub = data.get('subcategory_name', subcat_name)
                self.stat_bot_uploaded = getattr(self, 'stat_bot_uploaded', 0) + up_cnt

                if hasattr(self, 'lbl_bot_upload_stat'):
                    self.lbl_bot_upload_stat.configure(text=f'?? up trong phi?n: {self.stat_bot_uploaded} acc')
                if hasattr(self, 'lbl_stat_bot_uploaded'):
                    self.lbl_stat_bot_uploaded.configure(text=f'? UP BOT: {self.stat_bot_uploaded}')

                msg = f'?? [Bot Shop] ?? up th?nh c?ng {up_cnt} nick v?o [{target_sub}] (Media ID: {media_id[:12]}...)!'
                if batch_label:
                    msg += f' [{batch_label}]'
                self.log(msg, 'success')

        except urllib.error.HTTPError as he:
            err_body = ''
            try:
                err_body = he.read().decode('utf-8', errors='ignore')
                edata = json.loads(err_body)
                err_detail = edata.get('detail', str(he))
            except Exception:
                err_detail = err_body or str(he)
            self.log(f'? [Bot Shop] Upload th?t b?i (M? {he.code}): {err_detail}', 'error')

        except Exception as ex:
            self.log(f'? [Bot Shop] L?i g?i request upload: {ex}', 'error')

    def upload_all_live_to_bot(self):
        '''Doc va up toan bo tai khoan trong accounts_live.txt len Bot Shop.'''
        self._upload_file_to_bot_generic('accounts_live.txt', 'LIVE')

    def upload_all_unverified_to_bot(self):
        '''Doc va up toan bo tai khoan trong accounts_unverified.txt len Bot Shop.'''
        self._upload_file_to_bot_generic('accounts_unverified.txt', 'CH?A X?C MINH')

    def _upload_file_to_bot_generic(self, filename: str, label: str):
        '''Xu ly doc file bat ky, loc dinh dang UID|PASS|COOKIE va gui hang loat len Bot.'''
        def _worker():
            if not os.path.exists(filename):
                self.log(f'?? [Bot Shop] File {filename} kh?ng t?n t?i tr?n ? ??a!', 'warning')
                return

            try:
                with open(filename, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    raw_lines = f.readlines()
            except Exception as e:
                self.log(f'? [Bot Shop] Kh?ng th? ??c file {filename}: {e}', 'error')
                return

            valid_items = []
            for line in raw_lines:
                clean = line.strip()
                if not clean or clean.startswith('#'):
                    continue
                parts = clean.split('|')
                if len(parts) >= 3:
                    uid = parts[0].strip()
                    pwd = parts[1].strip()
                    cookie = ''
                    for p in parts[2:]:
                        if any(k in p for k in ('c_user=', 'datr=', 'wd=', 'fr=', 'xs=')):
                            cookie = p.strip()
                            break
                    if not cookie:
                        cookie = parts[2].strip()
                    if uid and pwd and cookie:
                        if 'c_user=' not in cookie:
                            cookie = f'c_user={uid}; {cookie}'
                        valid_items.append(f'{uid}|{pwd}|{cookie}')

            if not valid_items:
                self.log(f'?? [Bot Shop] File {filename} kh?ng c? t?i kho?n h?p l? (c?n UID|PASS|COOKIE)!', 'warning')
                return

            self.log(f'? [Bot Shop] ?ang b?t ??u ??y {len(valid_items)} nick {label} t? {filename} l?n Bot Shop...', 'info')
            batch_size = 50
            for i in range(0, len(valid_items), batch_size):
                batch = valid_items[i:i + batch_size]
                self._do_upload_accounts_batch(batch, batch_label=f'{label} {i+1}-{min(i+len(batch), len(valid_items))}/{len(valid_items)}')
                time.sleep(0.5)

        threading.Thread(target=_worker, daemon=True, name='BatchBotUpload').start()

    def on_context_upload_selected_to_bot(self):
        '''Upload cac tai khoan dang duoc chon tren bang len Bot Shop.'''
        checked_ids = self.get_checked_items()
        selected_ids = list(self.tree.selection())
        target_ids = list(dict.fromkeys(checked_ids + selected_ids))

        if not target_ids:
            messagebox.showinfo('Th?ng b?o', 'Vui l?ng t?ch ch?n ho?c b?i ?en ?t nh?t 1 t?i kho?n tr?n b?ng ?? up l?n Bot Shop!')
            return

        def _worker():
            valid_items = []
            for item_id in target_ids:
                if not self.tree.exists(item_id):
                    continue
                vals = self._get_tree_values(item_id)
                if not vals or len(vals) < 7:
                    continue
                uid = str(vals[2]).strip()
                pwd = str(vals[4]).strip()
                cookie = str(vals[6]).strip() if len(vals) > 6 else ''

                acc_obj = getattr(self, '_row_acc_data', {}).get(item_id, {})
                if acc_obj.get('cookie'):
                    cookie = acc_obj.get('cookie')

                if uid and pwd and cookie:
                    if 'c_user=' not in cookie:
                        cookie = f'c_user={uid}; {cookie}'
                    valid_items.append(f'{uid}|{pwd}|{cookie}')

            if not valid_items:
                self.log('?? [Bot Shop] Kh?ng t?m th?y t?i kho?n h?p l? c? Cookie trong c?c d?ng ?? ch?n!', 'warning')
                return

            self.log(f'? [Bot Shop] ?ang up {len(valid_items)} nick ?? ch?n l?n Bot Shop...', 'info')
            self._do_upload_accounts_batch(valid_items, batch_label=f'B?ng ?? ch?n {len(valid_items)} acc')

        threading.Thread(target=_worker, daemon=True, name='SelectedBotUpload').start()


def main():
    root = tk.Tk()
    app = RegFacebookGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

