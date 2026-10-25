# -*- coding: utf-8 -*-
"""
Web Shop Khách Hàng - Bubba Gump Facebook Clone Shop
Giao diện mua hàng trực tiếp trên Website chia sẻ 100% CSDL với Telegram Bot.
Tích hợp:
- Đầy đủ danh mục to, danh mục con, hiển thị tồn kho & giá bán (VND / USDT).
- Đăng ký, Đăng nhập người dùng (Username/Password hoặc liên kết Telegram ID).
- Nút chuyển nhanh sang Admin Panel khi đăng nhập với tài khoản Admin.
- Mua hàng trực tiếp trừ số dư ví, tự động lọc Live UID Facebook qua Graph API trước khi phát hàng.
- Nạp tiền tự động: Binance Pay (0% phí), BIDV VietQR 24/7, Crypto USDT.
- Lịch sử đơn hàng, xem lại tài khoản đã mua, tải file .txt.
- Biến động số dư & nhật ký nạp / tiêu tiền.
- Chính sách bảo hành & tuyên bố miễn trừ trách nhiệm pháp luật Việt Nam.
- Nút chat Telegram nổi kết nối Admin @truongdvfb để hỗ trợ khách hàng tức thì.
- Chống spam & Anti-DDoS rate limiting.
"""

import html
import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import config
from db import get_db_session, session_commit
from enums.buy_status import BuyStatus
from enums.item_type import ItemType
from enums.language import Language
from enums.user_role import UserRole
from models.bank_order import BankDepositOrder
from models.binance_pay import BinancePayOrder
from models.buy import Buy, BuyDTO
from models.buyItem import BuyItem, BuyItemDTO
from models.category import Category
from models.deposit import Deposit
from models.item import Item
from models.subcategory import Subcategory
from models.user import User
from services.facebook import (
    filter_live_facebook_items,
    is_facebook_clone,
    is_facebook_product,
)
from services.notification import NotificationService
from services.policy_defaults import DEFAULT_WARRANTY_LEGAL_POLICY
from utils.utils import create_access_token, decode_token, hash_password, verify_password

logger = logging.getLogger(__name__)

web_router = APIRouter(tags=["Web Shop"])

# Anti-spam click in-memory lock for buy and recharge
_user_buy_lock: dict[int, float] = {}

USDT_VND_RATE = 25900


def get_rate() -> int:
    try:
        return int(getattr(config, "BANK_BIDV_RATE", USDT_VND_RATE) or USDT_VND_RATE)
    except Exception:
        return USDT_VND_RATE


def format_vnd(amount_usd: float) -> str:
    vnd = int(round(amount_usd * get_rate()))
    return f"{vnd:,} đ".replace(",", ".")


def format_usd(amount_usd: float) -> str:
    return f"${amount_usd:.2f}"


async def get_current_user_info(request: Request, session: AsyncSession) -> tuple[Optional[User], float, bool]:
    """
    Lấy thông tin người dùng đang đăng nhập từ session.
    Trả về: (user_obj, balance_usd, is_admin)
    """
    web_session = request.session.get("web_user")
    token = request.session.get("token")
    is_admin = False

    # Kiểm tra quyền Admin từ token sqladmin
    if token:
        try:
            payload = decode_token(token)
            if payload and payload.get("sub") == UserRole.ADMIN.name:
                is_admin = True
        except Exception:
            pass

    if not web_session:
        # Nếu chưa có web_user nhưng có token admin (ví dụ vừa login /admin)
        if is_admin:
            admin_id_val = config.ADMIN_ID_LIST[0] if config.ADMIN_ID_LIST else 805398854
            stmt_adm = select(User).where(or_(User.telegram_id == admin_id_val, User.web_username == "admin", User.telegram_username == "admin"))
            admin_user = (await session.execute(stmt_adm)).scalar_one_or_none()
            if not admin_user:
                admin_user = User(
                    telegram_id=admin_id_val,
                    telegram_username="admin",
                    web_username="admin",
                    top_up_amount=999.0,
                    consume_records=0.0
                )
                session.add(admin_user)
                await session_commit(session)
            bal = max(0.0, float(admin_user.top_up_amount or 0.0) - float(admin_user.consume_records or 0.0))
            return admin_user, bal, True
        return None, 0.0, False

    user_id = web_session.get("id")
    if not user_id:
        return None, 0.0, False

    stmt = select(User).where(User.id == user_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user or user.is_banned:
        request.session.pop("web_user", None)
        return None, 0.0, False

    # Xác định lại cờ is_admin
    if user.telegram_id in config.ADMIN_ID_LIST or user.web_username == "admin" or user.telegram_username == "admin" or web_session.get("is_admin"):
        is_admin = True

    balance = max(0.0, float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0))
    return user, balance, is_admin


def render_base_layout(
    title: str,
    body_content: str,
    active_nav: str = "home",
    user: Optional[User] = None,
    balance: float = 0.0,
    is_admin: bool = False,
    categories: list = None
) -> str:
    categories = categories or []
    rate = get_rate()
    balance_vnd = format_vnd(balance)
    balance_usd = f"{balance:.2f}$"

    if user:
        display_name = user.web_username or user.telegram_username or f"User #{user.id}"
        admin_button_html = ""
        if is_admin:
            admin_button_html = """
            <a href="/admin" class="btn btn-warning btn-sm fw-bold text-dark me-2 shadow-sm pulse-admin-btn" title="Chuyển sang trang Quản trị Admin Panel">
                <i class="fa-solid fa-gauge-high me-1"></i> Chuyển sang Admin Panel
            </a>
            """
        user_nav_html = f"""
        <div class="d-flex align-items-center flex-wrap gap-2">
            {admin_button_html}
            <div class="dropdown">
                <button class="btn btn-purple dropdown-toggle fw-bold d-flex align-items-center gap-2" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                    <span class="avatar-circle"><i class="fa-solid fa-user"></i></span>
                    <span class="user-display-name">{html.escape(display_name)}</span>
                    <span class="badge bg-light text-purple fw-bold ms-1 balance-badge" data-vnd="{balance_vnd}" data-usd="{balance_usd}">{balance_vnd}</span>
                </button>
                <ul class="dropdown-menu dropdown-menu-end shadow border-0 mt-2">
                    <li class="px-3 py-2 border-bottom">
                        <div class="small text-muted">Số dư khả dụng:</div>
                        <div class="fw-bold text-success fs-5">{balance_vnd} <small class="text-muted">({balance_usd})</small></div>
                    </li>
                    <li><a class="dropdown-item py-2" href="/recharge"><i class="fa-solid fa-wallet text-purple me-2"></i> Nạp tiền số dư</a></li>
                    <li><a class="dropdown-item py-2" href="/orders"><i class="fa-solid fa-box text-primary me-2"></i> Lịch sử đơn hàng</a></li>
                    <li><a class="dropdown-item py-2" href="/balance-history"><i class="fa-solid fa-clock-rotate-left text-info me-2"></i> Biến động số dư</a></li>
                    {f'<li><a class="dropdown-item py-2 text-warning fw-bold" href="/admin"><i class="fa-solid fa-sliders me-2"></i> Quản trị Website (/admin)</a></li>' if is_admin else ''}
                    <li><hr class="dropdown-divider"></li>
                    <li><a class="dropdown-item py-2 text-danger" href="/logout"><i class="fa-solid fa-right-from-bracket me-2"></i> Đăng xuất</a></li>
                </ul>
            </div>
        </div>
        """
    else:
        user_nav_html = """
        <div class="d-flex align-items-center gap-2">
            <a href="/login" class="btn btn-outline-purple btn-sm fw-bold px-3">
                <i class="fa-solid fa-right-to-bracket me-1"></i> Đăng nhập
            </a>
            <a href="/register" class="btn btn-purple btn-sm fw-bold px-3 shadow-sm">
                <i class="fa-solid fa-user-plus me-1"></i> Đăng ký
            </a>
        </div>
        """

    cat_dropdown_html = ""
    for cat in categories:
        cat_dropdown_html += f'<li><a class="dropdown-item" href="/#cat-{cat.id}"><i class="fa-solid fa-folder me-2 text-purple"></i> {html.escape(cat.name)}</a></li>'

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} - Bubba Gump FB Clone Shop</title>
    <!-- Bootstrap 5.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- FontAwesome 6.5 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary-purple: #6f42c1;
            --primary-purple-dark: #59359a;
            --primary-purple-light: #f3e8ff;
            --accent-pink: #d63384;
            --accent-blue: #0d6efd;
            --bg-light: #f8f9fc;
            --text-dark: #2d3748;
        }}
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-light);
            color: var(--text-dark);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .top-bar {{
            background: linear-gradient(90deg, #673ab7 0%, #5e35b1 50%, #512da8 100%);
            color: #ffffff;
            font-size: 13px;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .top-bar a {{
            color: #ffffff;
            text-decoration: none;
            opacity: 0.9;
            transition: opacity 0.2s;
        }}
        .top-bar a:hover {{
            opacity: 1;
            text-decoration: underline;
        }}
        .brand-navbar {{
            background: #ffffff;
            border-bottom: 1px solid #e9ecef;
            padding: 12px 0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        }}
        .brand-logo {{
            font-weight: 800;
            font-size: 22px;
            color: var(--primary-purple);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .brand-logo:hover {{
            color: var(--primary-purple-dark);
        }}
        .search-container {{
            max-width: 480px;
            width: 100%;
        }}
        .search-input {{
            border-radius: 24px;
            padding: 8px 18px 8px 40px;
            border: 1.5px solid #e2e8f0;
            font-size: 14px;
            background: #f8fafc;
            transition: all 0.2s;
        }}
        .search-input:focus {{
            background: #ffffff;
            border-color: var(--primary-purple);
            box-shadow: 0 0 0 3px rgba(111, 66, 193, 0.15);
        }}
        .search-icon {{
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            color: #94a3b8;
            pointer-events: none;
        }}
        .btn-purple {{
            background: linear-gradient(135deg, #6f42c1 0%, #59359a 100%);
            color: #ffffff;
            border: none;
            transition: all 0.2s;
        }}
        .btn-purple:hover, .btn-purple:focus {{
            background: linear-gradient(135deg, #59359a 0%, #4a2d80 100%);
            color: #ffffff;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(111, 66, 193, 0.25);
        }}
        .btn-outline-purple {{
            color: var(--primary-purple);
            border: 1.5px solid var(--primary-purple);
            background: transparent;
        }}
        .btn-outline-purple:hover {{
            background: var(--primary-purple);
            color: #ffffff;
        }}
        .avatar-circle {{
            width: 28px;
            height: 28px;
            background: rgba(255, 255, 255, 0.25);
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
        }}
        .second-navbar {{
            background: #ffffff;
            border-bottom: 1px solid #edf2f7;
            padding: 8px 0;
            font-size: 14px;
            font-weight: 600;
        }}
        .second-navbar .nav-link {{
            color: #4a5568;
            padding: 6px 14px;
            border-radius: 6px;
            transition: all 0.2s;
        }}
        .second-navbar .nav-link:hover, .second-navbar .nav-link.active {{
            color: var(--primary-purple);
            background: var(--primary-purple-light);
        }}
        .notice-card {{
            background: #fffdf5;
            border: 1.5px solid #ffeeba;
            border-left: 5px solid #ff9800;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 24px;
            box-shadow: 0 2px 6px rgba(255, 152, 0, 0.08);
        }}
        .notice-card h5 {{
            color: #e65100;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        .notice-card ul {{
            margin-bottom: 0;
            padding-left: 20px;
        }}
        .notice-card li {{
            margin-bottom: 6px;
            font-size: 13.5px;
            line-height: 1.5;
            color: #4a5568;
        }}
        .cat-pill-btn {{
            border-radius: 20px;
            padding: 8px 18px;
            font-weight: 600;
            font-size: 13.5px;
            border: 1px solid #e2e8f0;
            background: #ffffff;
            color: #4a5568;
            transition: all 0.2s;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .cat-pill-btn:hover, .cat-pill-btn.active {{
            background: linear-gradient(135deg, #6f42c1 0%, #59359a 100%);
            color: #ffffff;
            border-color: #6f42c1;
            box-shadow: 0 4px 10px rgba(111, 66, 193, 0.2);
        }}
        .product-card {{
            background: #ffffff;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 18px 20px;
            transition: all 0.2s;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.02);
            margin-bottom: 14px;
        }}
        .product-card:hover {{
            border-color: #cbd5e1;
            box-shadow: 0 6px 18px rgba(111, 66, 193, 0.08);
            transform: translateY(-1px);
        }}
        .product-title {{
            font-size: 15px;
            font-weight: 700;
            color: #1a202c;
            margin-bottom: 4px;
        }}
        .product-desc {{
            font-size: 13px;
            color: #718096;
            margin-bottom: 10px;
        }}
        .stock-badge {{
            font-size: 12px;
            font-weight: 600;
            background: #f1f5f9;
            color: #475569;
            padding: 4px 10px;
            border-radius: 12px;
        }}
        .stock-badge.has-stock {{
            background: #e0f2fe;
            color: #0369a1;
        }}
        .stock-badge.empty {{
            background: #fee2e2;
            color: #dc2626;
        }}
        .price-badge {{
            font-size: 17px;
            font-weight: 800;
            color: #e11d48;
            font-family: 'Consolas', monospace;
        }}
        .btn-buy {{
            background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%);
            color: #ffffff;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            padding: 8px 20px;
            font-size: 13.5px;
            transition: all 0.2s;
        }}
        .btn-buy:hover {{
            background: linear-gradient(135deg, #db2777 0%, #7c3aed 100%);
            color: #ffffff;
            transform: scale(1.02);
            box-shadow: 0 4px 12px rgba(236, 72, 153, 0.3);
        }}
        .balance-widget-card {{
            background: #ffffff;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
            margin-bottom: 20px;
        }}
        .balance-title {{
            font-size: 13px;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .balance-amount {{
            font-size: 26px;
            font-weight: 800;
            color: var(--primary-purple);
            margin: 6px 0;
            font-family: 'Consolas', monospace;
        }}
        .floating-contact-btn {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 9999;
            display: flex;
            align-items: center;
            gap: 10px;
            background: linear-gradient(135deg, #0088cc 0%, #0077b5 100%);
            color: #ffffff;
            padding: 12px 20px;
            border-radius: 30px;
            text-decoration: none;
            box-shadow: 0 6px 20px rgba(0, 136, 204, 0.4);
            font-weight: 700;
            font-size: 14px;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            animation: pulse-telegram 2.5s infinite;
        }}
        .floating-contact-btn:hover {{
            transform: translateY(-3px) scale(1.04);
            color: #ffffff;
            box-shadow: 0 10px 25px rgba(0, 136, 204, 0.55);
        }}
        @keyframes pulse-telegram {{
            0% {{ box-shadow: 0 0 0 0 rgba(0, 136, 204, 0.6); }}
            70% {{ box-shadow: 0 0 0 14px rgba(0, 136, 204, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(0, 136, 204, 0); }}
        }}
        .pulse-admin-btn {{
            animation: pulse-admin 2s infinite;
        }}
        @keyframes pulse-admin {{
            0% {{ box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7); }}
            70% {{ box-shadow: 0 0 0 10px rgba(255, 193, 7, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(255, 193, 7, 0); }}
        }}
        .custom-toast {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 100000;
            min-width: 280px;
        }}
        footer {{
            margin-top: auto;
            background: #ffffff;
            border-top: 1px solid #e2e8f0;
            padding: 24px 0;
            font-size: 13px;
            color: #64748b;
        }}
    </style>
</head>
<body>

    <!-- 1. Top Announcement Bar -->
    <div class="top-bar">
        <div class="container d-flex justify-content-between align-items-center flex-wrap gap-2">
            <div class="d-flex align-items-center gap-2">
                <i class="fa-solid fa-bullhorn text-warning"></i>
                <span>Chào mừng bạn đến với <strong>Bubba Gump FB Clone Shop</strong> - Hệ thống bán clone Facebook tự động 24/7!</span>
            </div>
            <div class="d-flex align-items-center gap-3">
                <div class="dropdown">
                    <a href="javascript:void(0)" class="dropdown-toggle" data-bs-toggle="dropdown">
                        <i class="fa-solid fa-earth-americas me-1"></i> Vietnamese
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end shadow-sm border-0 small">
                        <li><a class="dropdown-item active" href="javascript:void(0)">🇻🇳 Tiếng Việt</a></li>
                        <li><a class="dropdown-item" href="javascript:void(0)">🇬🇧 English</a></li>
                    </ul>
                </div>
                <div class="dropdown">
                    <a href="javascript:void(0)" class="dropdown-toggle" id="currencyToggleBtn" data-bs-toggle="dropdown">
                        <i class="fa-solid fa-money-bill-transfer me-1"></i> <span id="currentCurrencyLabel">VND (1$ = {rate:,}đ)</span>
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end shadow-sm border-0 small">
                        <li><a class="dropdown-item" href="javascript:void(0)" onclick="setCurrency('VND')">🇻🇳 VNĐ (Việt Nam Đồng)</a></li>
                        <li><a class="dropdown-item" href="javascript:void(0)" onclick="setCurrency('USDT')">💵 USDT (Đô la Mỹ)</a></li>
                    </ul>
                </div>
                <a href="/policy"><i class="fa-solid fa-shield-halved me-1"></i> Chính sách</a>
                <a href="/faq"><i class="fa-solid fa-circle-question me-1"></i> FAQ</a>
                <a href="https://t.me/truongdvfb" target="_blank"><i class="fa-brands fa-telegram me-1"></i> Liên hệ Admin</a>
            </div>
        </div>
    </div>

    <!-- 2. Main Brand Navbar -->
    <header class="brand-navbar">
        <div class="container d-flex justify-content-between align-items-center flex-wrap gap-3">
            <a href="/" class="brand-logo">
                <span style="font-size: 26px;">🦐</span>
                <span>Bubba<span style="color: #0d6efd;">Gump</span><span style="font-size: 13px; font-weight: 600; color: #64748b; margin-left: 4px;">.fb</span></span>
            </a>

            <!-- Search box -->
            <div class="search-container position-relative">
                <i class="fa-solid fa-magnifying-glass search-icon"></i>
                <input type="text" id="globalSearchInput" class="form-control search-input" placeholder="Tìm kiếm sản phẩm (clone, via, hotmail, no2fa...)...">
            </div>

            <!-- User Auth or Profile -->
            {user_nav_html}
        </div>
    </header>

    <!-- 3. Secondary Navigation -->
    <nav class="second-navbar">
        <div class="container d-flex justify-content-between align-items-center flex-wrap gap-2">
            <ul class="nav">
                <li class="nav-item">
                    <a class="nav-link {'active' if active_nav == 'home' else ''}" href="/"><i class="fa-solid fa-house me-1"></i> Trang chủ</a>
                </li>
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown"><i class="fa-solid fa-layer-group me-1"></i> Sản phẩm</a>
                    <ul class="dropdown-menu shadow-sm border-0">
                        {cat_dropdown_html if cat_dropdown_html else '<li><a class="dropdown-item" href="/">Tất cả sản phẩm</a></li>'}
                    </ul>
                </li>
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle {'active' if active_nav == 'recharge' else ''}" href="/recharge" data-bs-toggle="dropdown">
                        <i class="fa-solid fa-wallet me-1"></i> Nạp tiền
                    </a>
                    <ul class="dropdown-menu shadow-sm border-0">
                        <li><a class="dropdown-item" href="/recharge?tab=binance"><i class="fa-solid fa-bolt text-warning me-2"></i> Binance Pay (0% phí - Nhận 1s)</a></li>
                        <li><a class="dropdown-item" href="/recharge?tab=bank"><i class="fa-solid fa-building-columns text-primary me-2"></i> Ngân hàng BIDV (VietQR 24/7)</a></li>
                        <li><a class="dropdown-item" href="/recharge?tab=onchain"><i class="fa-solid fa-coins text-success me-2"></i> Crypto On-chain (USDT)</a></li>
                    </ul>
                </li>
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle {'active' if active_nav in ['orders', 'balance_history'] else ''}" href="#" data-bs-toggle="dropdown">
                        <i class="fa-solid fa-clock-rotate-left me-1"></i> Lịch sử
                    </a>
                    <ul class="dropdown-menu shadow-sm border-0">
                        <li><a class="dropdown-item" href="/orders"><i class="fa-solid fa-box text-primary me-2"></i> Lịch sử đơn hàng đã mua</a></li>
                        <li><a class="dropdown-item" href="/balance-history"><i class="fa-solid fa-list-check text-info me-2"></i> Biến động số dư tài khoản</a></li>
                    </ul>
                </li>
                <li class="nav-item">
                    <a class="nav-link {'active' if active_nav == 'policy' else ''}" href="/policy"><i class="fa-solid fa-shield-halved me-1"></i> Điều khoản & Bảo hành</a>
                </li>
            </ul>

            <div class="d-flex align-items-center gap-3 text-muted small">
                <span><i class="fa-solid fa-headset text-purple me-1"></i> Hỗ trợ: <strong class="text-dark">@truongdvfb</strong></span>
                <span><i class="fa-brands fa-telegram text-primary me-1"></i> Kênh: <a href="https://t.me/truongdvfb" target="_blank" class="text-decoration-none fw-bold">Telegram</a></span>
            </div>
        </div>
    </nav>

    <!-- Main Content Body -->
    <main class="py-4 flex-grow-1">
        {body_content}
    </main>

    <!-- Floating Contact Telegram Button -->
    <a href="https://t.me/truongdvfb" target="_blank" class="floating-contact-btn shadow" title="Chat trực tiếp với Admin qua Telegram">
        <i class="fa-brands fa-telegram fa-xl"></i>
        <span>Chat Telegram Admin (@truongdvfb)</span>
    </a>

    <!-- Footer -->
    <footer>
        <div class="container text-center">
            <div class="mb-2">
                <a href="/" class="text-decoration-none fw-bold text-dark me-3">Trang chủ</a>
                <a href="/policy" class="text-decoration-none text-muted me-3">Chính sách bảo hành & Miễn trừ trách nhiệm</a>
                <a href="/faq" class="text-decoration-none text-muted me-3">Câu hỏi thường gặp</a>
                <a href="https://t.me/truongdvfb" target="_blank" class="text-decoration-none text-muted">Liên hệ Admin</a>
            </div>
            <p class="mb-1 text-muted small">
                © 2026 <strong>Bubba Gump FB Clone Shop</strong>. Tự động kiểm tra LIVE UID Facebook qua Graph API ngay khi bàn giao.
            </p>
            <p class="mb-0 text-muted" style="font-size: 11.5px;">
                Căn cứ Luật An ninh mạng số 24/2018/QH14 & Nghị định 15/2020/NĐ-CP: Mọi tài khoản chỉ phục vụ nghiên cứu & marketing hợp pháp. Nghiêm cấm mọi hành vi vi phạm pháp luật.
            </p>
        </div>
    </footer>

    <!-- Bootstrap 5.3 JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        var currentCurrency = localStorage.getItem('shop_currency') || 'VND';
        var usdRate = {rate};

        function setCurrency(curr) {
            currentCurrency = curr;
            localStorage.setItem('shop_currency', curr);
            updateCurrencyUI();
        }

        function updateCurrencyUI() {
            var label = document.getElementById('currentCurrencyLabel');
            if (label) {
                label.innerText = currentCurrency === 'VND' ? 'VND (1$ = ' + usdRate.toLocaleString('vi-VN') + 'đ)' : 'USDT ($)';
            }
            document.querySelectorAll('.currency-toggle-val').forEach(function(el) {
                var vnd = el.getAttribute('data-vnd');
                var usd = el.getAttribute('data-usd');
                if (currentCurrency === 'VND' && vnd) {
                    el.innerText = vnd;
                } else if (usd) {
                    el.innerText = usd;
                }
            });
        }

        // Live product search filter
        document.addEventListener('DOMContentLoaded', function() {
            updateCurrencyUI();
            var searchInput = document.getElementById('globalSearchInput');
            if (searchInput) {
                searchInput.addEventListener('input', function() {
                    var q = this.value.toLowerCase().trim();
                    document.querySelectorAll('.product-card-item').forEach(function(card) {
                        var text = card.innerText.toLowerCase();
                        card.style.display = text.includes(q) ? '' : 'none';
                    });
                });
            }
        });

        function showWebToast(message, isSuccess = true) {
            var toast = document.createElement('div');
            toast.className = 'custom-toast alert ' + (isSuccess ? 'alert-success' : 'alert-danger') + ' shadow-lg border-0 d-flex align-items-center justify-content-between p-3';
            toast.innerHTML = '<span>' + message + '</span><button type="button" class="btn-close ms-3" onclick="this.parentElement.remove()"></button>';
            document.body.appendChild(toast);
            setTimeout(function() {
                toast.style.transition = 'opacity 0.4s';
                toast.style.opacity = '0';
                setTimeout(function() { toast.remove(); }, 400);
            }, 3500);
        }

        function copyToClipboard(text, successMsg = 'Đã sao chép vào bộ nhớ tạm!') {
            if (!text) return;
            navigator.clipboard.writeText(text).then(function() {
                showWebToast('✅ ' + successMsg, true);
            }).catch(function() {
                var ta = document.createElement('textarea');
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showWebToast('✅ ' + successMsg, true);
            });
        }

        function downloadTextFile(filename, content) {
            var blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
        }
    </script>
</body>
</html>"""

# ==========================================
# 1. TRANG CHỦ WEB SHOP (STOREFRONT)
# ==========================================
@web_router.get("/", response_class=HTMLResponse)
async def web_home(request: Request):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)

        # Lấy danh mục chính
        stmt_cat = select(Category).order_by(Category.id.asc())
        categories = (await session.execute(stmt_cat)).scalars().all()

        # Lấy danh mục con và tính số lượng tồn kho khả dụng
        stmt_sub = (
            select(Subcategory)
            .options(selectinload(Subcategory.category))
            .order_by(Subcategory.category_id.asc(), Subcategory.id.asc())
        )
        subcategories = (await session.execute(stmt_sub)).scalars().all()

        # Tồn kho theo từng subcategory_id
        stock_stmt = (
            select(Item.subcategory_id, func.count(Item.id))
            .where(Item.is_sold == False)
            .group_by(Item.subcategory_id)
        )
        stock_rows = (await session.execute(stock_stmt)).all()
        stock_dict = {row[0]: row[1] for row in stock_rows}

    # Group subcategories by category
    cats_data = []
    for cat in categories:
        sub_items = [s for s in subcategories if s.category_id == cat.id]
        if sub_items:
            cats_data.append({"cat": cat, "subcats": sub_items})

    # Render category filter pills
    pills_html = """
    <a href="javascript:void(0)" class="cat-pill-btn active" onclick="filterCategory('all', this)">
        <i class="fa-solid fa-boxes-stacked"></i> Tất cả sản phẩm
    </a>
    """
    for cat in categories:
        pills_html += f"""
        <a href="javascript:void(0)" class="cat-pill-btn" onclick="filterCategory('{cat.id}', this)">
            <i class="fa-solid fa-folder"></i> {html.escape(cat.name)}
        </a>
        """

    # Render products section
    products_html = ""
    for group in cats_data:
        cat = group["cat"]
        products_html += f"""
        <div class="category-block mb-4" data-cat-id="{cat.id}">
            <div class="d-flex align-items-center gap-2 mb-3 pb-2 border-bottom">
                <span class="fs-4 text-purple"><i class="fa-solid fa-folder-open"></i></span>
                <h5 class="fw-bold mb-0 text-dark">{html.escape(cat.name)}</h5>
            </div>
            <div class="row g-3">
        """
        for sub in group["subcats"]:
            stock_qty = stock_dict.get(sub.id, 0)
            unit_price = float(sub.price or 0.02)
            price_vnd = format_vnd(unit_price)
            price_usd = format_usd(unit_price)
            has_stock = stock_qty > 0
            stock_cls = "has-stock" if has_stock else "empty"
            stock_text = f"Kho hàng: {stock_qty}" if has_stock else "Hết hàng"
            desc_text = html.escape(sub.description or "Clone chất lượng cao, bảo hành 1 đổi 1 trong 24 giờ.")

            buy_btn_html = f"""
            <button class="btn btn-buy" onclick="openBuyModal({sub.id}, '{html.escape(sub.name)}', {unit_price}, {stock_qty})">
                <i class="fa-solid fa-cart-shopping me-1"></i> MUA NGAY
            </button>
            """ if has_stock else """
            <button class="btn btn-secondary disabled" style="border-radius: 8px; font-size: 13.5px;" disabled>
                <i class="fa-solid fa-ban me-1"></i> TẠM HẾT
            </button>
            """

            products_html += f"""
            <div class="col-12 product-card-item" data-cat-id="{cat.id}">
                <div class="product-card d-flex justify-content-between align-items-center flex-wrap gap-3">
                    <div class="flex-grow-1" style="min-width: 260px;">
                        <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                            <h6 class="product-title mb-0">{html.escape(sub.name)}</h6>
                            <span class="stock-badge {stock_cls}"><i class="fa-solid fa-box me-1"></i>{stock_text}</span>
                        </div>
                        <div class="product-desc mb-0">{desc_text}</div>
                    </div>
                    <div class="d-flex align-items-center gap-4 flex-wrap">
                        <div class="text-end">
                            <div class="small text-muted">Đơn giá:</div>
                            <div class="price-badge currency-toggle-val" data-vnd="{price_vnd}" data-usd="{price_usd}">{price_vnd}</div>
                        </div>
                        {buy_btn_html}
                    </div>
                </div>
            </div>
            """
        products_html += "</div></div>"

    if not products_html:
        products_html = """
        <div class="alert alert-light text-center py-5 border">
            <i class="fa-solid fa-box-open fa-3x text-muted mb-3"></i>
            <h5>Chưa có sản phẩm nào trong kho!</h5>
            <p class="text-muted">Vui lòng quay lại sau hoặc liên hệ Admin qua Telegram.</p>
        </div>
        """

    # Right Column User / Quick Info Widget
    balance_vnd_str = format_vnd(balance)
    balance_usd_str = format_usd(balance)
    top_up_str = format_vnd(user.top_up_amount) if user else "0 đ"
    spent_str = format_vnd(user.consume_records) if user else "0 đ"

    right_widget_html = f"""
    <div class="balance-widget-card">
        <div class="balance-title"><i class="fa-solid fa-wallet text-purple me-1"></i> Số dư khả dụng</div>
        <div class="balance-amount currency-toggle-val" data-vnd="{balance_vnd_str}" data-usd="{balance_usd_str}">{balance_vnd_str}</div>
        <div class="small text-muted mb-3">Tỷ giá hiện tại: <strong>1 USDT = {rate:,} đ</strong></div>
        <div class="d-grid gap-2">
            <a href="/recharge" class="btn btn-purple fw-bold py-2 shadow-sm">
                <i class="fa-solid fa-bolt me-1"></i> NẠP TIỀN TỰ ĐỘNG (1s)
            </a>
        </div>
    </div>

    <div class="balance-widget-card">
        <div class="balance-title mb-3"><i class="fa-solid fa-chart-pie text-primary me-1"></i> Thống kê tài khoản</div>
        <div class="d-flex justify-content-between py-2 border-bottom small">
            <span class="text-muted">Tổng tiền đã nạp:</span>
            <strong class="text-success">{top_up_str}</strong>
        </div>
        <div class="d-flex justify-content-between py-2 border-bottom small">
            <span class="text-muted">Tổng tiền đã mua:</span>
            <strong class="text-danger">{spent_str}</strong>
        </div>
        <div class="d-flex justify-content-between pt-2 small">
            <span class="text-muted">Trạng thái:</span>
            <strong class="text-success"><i class="fa-solid fa-circle-check me-1"></i>Hoạt động 24/7</strong>
        </div>
    </div>

    <div class="balance-widget-card bg-light border-0">
        <h6 class="fw-bold mb-2 text-dark"><i class="fa-solid fa-shield-halved text-purple me-1"></i> Cam kết chất lượng</h6>
        <ul class="small text-muted ps-3 mb-0" style="line-height: 1.6;">
            <li>100% clone LIVE khi nhận (Auto Graph API check).</li>
            <li>Bảo hành 1 đổi 1 trong 24 giờ cho tài khoản lỗi ban đầu.</li>
            <li>Nạp tiền tự động qua Binance Pay & BIDV VietQR nhận ngay lập tức.</li>
        </ul>
    </div>
    """

    # Main content assembly
    content = f"""
    <div class="container">
        <!-- Hộp Lưu ý & Cảnh báo pháp lý (Khớp giao diện khuongfb.com) -->
        <div class="notice-card">
            <h5><i class="fa-solid fa-triangle-exclamation me-2"></i>Lưu ý & Tuyên bố miễn trừ trách nhiệm:</h5>
            <ul>
                <li><strong>Bảo quản tài sản:</strong> Đơn hàng sẽ được lưu trữ an toàn trong mục <em>Lịch sử đơn hàng</em>, quý khách vui lòng chủ động lưu lại tài khoản sau khi nhận!</li>
                <li><strong>Tuân thủ pháp luật Việt Nam:</strong> Cấm sử dụng tài khoản với mục đích vi phạm pháp luật (lừa đảo chiếm đoạt tài sản, chống phá Đảng và Nhà Nước CHXHCN Việt Nam). Khi cơ quan chức năng yêu cầu, chúng tôi sẽ hợp tác cung cấp thông tin và tuyên bố <strong>miễn trừ mọi trách nhiệm</strong> đối với các hành vi vi phạm. <a href="/policy" class="fw-bold text-decoration-underline text-danger">Xem chi tiết chính sách pháp lý & bảo hành tại đây!</a></li>
                <li><strong>Hỗ trợ & Nạp tiền:</strong> Nhắn tin Admin Telegram: <strong>@truongdvfb</strong>. Hệ thống hỗ trợ nạp tự động qua <strong>Binance Pay (0% phí)</strong> và <strong>Ngân hàng BIDV VietQR</strong> nhận ngay sau 1-5 giây.</li>
                <li><strong>Binance Pay ID:</strong> <code>805398854</code> | <strong>Telegram Admin:</strong> @truongdvfb.</li>
                <li><strong>Kiểm tra Live:</strong> Hệ thống tự động kiểm tra Live UID Facebook qua Graph API ngay khi phát hàng, cam kết 100% clone Live khi nhận!</li>
            </ul>
        </div>

        <div class="row g-4">
            <!-- Left Main Column (Products) -->
            <div class="col-lg-8 col-md-12">
                <!-- Category Pills -->
                <div class="d-flex align-items-center gap-2 flex-wrap mb-4">
                    {pills_html}
                </div>

                <!-- Products Catalog -->
                <div id="productsCatalogContainer">
                    {products_html}
                </div>
            </div>

            <!-- Right Column (Widgets) -->
            <div class="col-lg-4 col-md-12">
                {right_widget_html}
            </div>
        </div>
    </div>

    <!-- Buy Modal -->
    <div class="modal fade" id="buyModal" tabindex="-1" aria-labelledby="buyModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow-lg">
                <div class="modal-header bg-purple text-white">
                    <h5 class="modal-title fw-bold" id="buyModalLabel">
                        <i class="fa-solid fa-cart-arrow-down me-2"></i> Mua tài khoản trực tiếp
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-4">
                    <!-- Form Step -->
                    <div id="buyModalFormStep">
                        <div class="mb-3">
                            <label class="form-label text-muted small fw-bold">SẢN PHẨM ĐÃ CHỌN:</label>
                            <h6 id="modalSubName" class="fw-bold text-dark fs-5">Tên sản phẩm</h6>
                            <div class="d-flex gap-3 small text-muted">
                                <span>Đơn giá: <strong id="modalUnitPrice" class="text-danger font-monospace">0 đ</strong></span>
                                <span>Còn trong kho: <strong id="modalStockQty" class="text-primary font-monospace">0</strong></span>
                            </div>
                        </div>

                        <div class="mb-3">
                            <label for="buyQtyInput" class="form-label fw-bold">Số lượng cần mua:</label>
                            <div class="input-group mb-2">
                                <button class="btn btn-outline-secondary" type="button" onclick="adjustQty(-1)"><i class="fa-solid fa-minus"></i></button>
                                <input type="number" id="buyQtyInput" class="form-control text-center fw-bold fs-5 font-monospace" value="1" min="1" max="1000">
                                <button class="btn btn-outline-secondary" type="button" onclick="adjustQty(1)"><i class="fa-solid fa-plus"></i></button>
                            </div>
                            <!-- Quick quantity buttons -->
                            <div class="d-flex gap-2 flex-wrap">
                                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="setQty(1)">1</button>
                                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="setQty(5)">5</button>
                                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="setQty(10)">10</button>
                                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="setQty(50)">50</button>
                                <button type="button" class="btn btn-sm btn-outline-primary" onclick="setQtyMax()">Mua tất cả</button>
                            </div>
                        </div>

                        <div class="card bg-light border-0 p-3 mb-3">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <span class="text-muted">Tổng tiền thanh toán:</span>
                                <span id="modalTotalPrice" class="fs-4 fw-bold text-danger font-monospace">0 đ</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center small">
                                <span class="text-muted">Số dư ví hiện tại:</span>
                                <span id="modalUserBalance" class="fw-bold text-success font-monospace" data-val="{balance}">{balance_vnd_str} (${balance:.2f})</span>
                            </div>
                        </div>

                        <div id="balanceAlertBox" class="alert alert-warning py-2 small d-none">
                            <i class="fa-solid fa-triangle-exclamation me-1"></i>
                            <span id="balanceAlertMsg">Số dư không đủ để thanh toán!</span>
                        </div>

                        <input type="hidden" id="modalSubId" value="">
                        <input type="hidden" id="modalRawUnitPrice" value="0.02">
                    </div>

                    <!-- Loading Step -->
                    <div id="buyModalLoadingStep" class="text-center py-4 d-none">
                        <div class="spinner-border text-purple mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
                        <h6 class="fw-bold text-dark">Hệ thống đang xử lý đơn hàng...</h6>
                        <p class="small text-muted mb-0">⚡ Đang tự động kiểm tra Live UID qua Facebook Graph API & trừ tiền vào số dư ví.</p>
                    </div>

                    <!-- Success Delivery Step -->
                    <div id="buyModalSuccessStep" class="d-none">
                        <div class="text-center mb-3">
                            <span class="fs-1 text-success"><i class="fa-solid fa-circle-check"></i></span>
                            <h5 class="fw-bold text-success mb-1">MUA HÀNG THÀNH CÔNG!</h5>
                            <p class="text-muted small">Mã đơn hàng: <strong id="resOrderId">#0</strong> | Số lượng: <strong id="resOrderQty">0</strong></p>
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-muted small fw-bold">DANH SÁCH TÀI KHOẢN ĐÃ CẤP:</label>
                            <textarea id="deliveredAccountsArea" class="form-control font-monospace small bg-light" rows="8" readonly style="line-height: 1.4;"></textarea>
                        </div>
                        <div class="d-flex gap-2">
                            <button type="button" class="btn btn-primary fw-bold flex-grow-1" onclick="copyDeliveredAccounts()">
                                <i class="fa-solid fa-copy me-1"></i> Sao chép tất cả
                            </button>
                            <button type="button" class="btn btn-success fw-bold flex-grow-1" onclick="downloadDeliveredAccounts()">
                                <i class="fa-solid fa-download me-1"></i> Tải file .txt
                            </button>
                        </div>
                    </div>
                </div>
                <div class="modal-footer bg-light" id="buyModalFooter">
                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Đóng</button>
                    <button type="button" id="confirmBuyBtn" class="btn btn-purple fw-bold px-4" onclick="executeBuyOrder()">
                        <i class="fa-solid fa-check me-1"></i> XÁC NHẬN MUA
                    </button>
                    <a href="/recharge" id="rechargeLinkBtn" class="btn btn-success fw-bold d-none">
                        <i class="fa-solid fa-wallet me-1"></i> NẠP TIỀN NGAY
                    </a>
                </div>
            </div>
        </div>
    </div>

    <script>
        var isUserLoggedIn = {'true' if user else 'false'};
        var currentBalanceUsd = {balance};
        var activeSubMaxStock = 0;

        function filterCategory(catId, btn) {
            document.querySelectorAll('.cat-pill-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            document.querySelectorAll('.category-block').forEach(function(block) {
                if (catId === 'all' || block.getAttribute('data-cat-id') === catId) {
                    block.style.display = '';
                } else {
                    block.style.display = 'none';
                }
            });
        }

        function openBuyModal(subId, subName, unitPrice, stockQty) {
            if (!isUserLoggedIn) {
                window.location.href = '/login?next=/';
                return;
            }
            document.getElementById('modalSubId').value = subId;
            document.getElementById('modalSubName').innerText = subName;
            document.getElementById('modalRawUnitPrice').value = unitPrice;
            document.getElementById('modalUnitPrice').innerText = (unitPrice * usdRate).toLocaleString('vi-VN') + ' đ ($' + unitPrice.toFixed(2) + ')';
            document.getElementById('modalStockQty').innerText = stockQty;
            activeSubMaxStock = stockQty;

            document.getElementById('buyQtyInput').value = 1;
            document.getElementById('buyQtyInput').max = stockQty;

            document.getElementById('buyModalFormStep').classList.remove('d-none');
            document.getElementById('buyModalLoadingStep').classList.add('d-none');
            document.getElementById('buyModalSuccessStep').classList.add('d-none');
            document.getElementById('buyModalFooter').classList.remove('d-none');

            recalcModalTotal();
            var modal = new bootstrap.Modal(document.getElementById('buyModal'));
            modal.show();
        }

        function adjustQty(delta) {
            var input = document.getElementById('buyQtyInput');
            var val = parseInt(input.value) || 1;
            val = Math.max(1, Math.min(activeSubMaxStock, val + delta));
            input.value = val;
            recalcModalTotal();
        }

        function setQty(qty) {
            var input = document.getElementById('buyQtyInput');
            var val = Math.max(1, Math.min(activeSubMaxStock, qty));
            input.value = val;
            recalcModalTotal();
        }

        function setQtyMax() {
            setQty(activeSubMaxStock);
        }

        document.getElementById('buyQtyInput').addEventListener('input', recalcModalTotal);

        function recalcModalTotal() {
            var qty = parseInt(document.getElementById('buyQtyInput').value) || 1;
            var unitPrice = parseFloat(document.getElementById('modalRawUnitPrice').value) || 0.02;
            var totalUsd = qty * unitPrice;
            var totalVnd = Math.round(totalUsd * usdRate);

            document.getElementById('modalTotalPrice').innerText = totalVnd.toLocaleString('vi-VN') + ' đ ($' + totalUsd.toFixed(2) + ')';

            var alertBox = document.getElementById('balanceAlertBox');
            var alertMsg = document.getElementById('balanceAlertMsg');
            var confirmBtn = document.getElementById('confirmBuyBtn');
            var rechargeBtn = document.getElementById('rechargeLinkBtn');

            if (totalUsd > currentBalanceUsd) {
                var missing = totalUsd - currentBalanceUsd;
                var missingVnd = Math.round(missing * usdRate);
                alertMsg.innerHTML = 'Số dư ví không đủ! Còn thiếu: <strong>' + missingVnd.toLocaleString('vi-VN') + ' đ ($' + missing.toFixed(2) + ')</strong>';
                alertBox.classList.remove('d-none');
                confirmBtn.classList.add('d-none');
                rechargeBtn.classList.remove('d-none');
            } else {
                alertBox.classList.add('d-none');
                confirmBtn.classList.remove('d-none');
                rechargeBtn.classList.add('d-none');
            }
        }

        function executeBuyOrder() {
            var subId = parseInt(document.getElementById('modalSubId').value);
            var qty = parseInt(document.getElementById('buyQtyInput').value) || 1;

            document.getElementById('buyModalFormStep').classList.add('d-none');
            document.getElementById('buyModalLoadingStep').classList.remove('d-none');
            document.getElementById('buyModalFooter').classList.add('d-none');

            fetch('/api/web/buy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subcategory_id: subId, quantity: qty })
            })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                document.getElementById('buyModalLoadingStep').classList.add('d-none');
                if (data.status === 'success') {
                    document.getElementById('buyModalSuccessStep').classList.remove('d-none');
                    document.getElementById('resOrderId').innerText = '#' + data.order_id;
                    document.getElementById('resOrderQty').innerText = data.quantity;
                    document.getElementById('deliveredAccountsArea').value = data.accounts.join('\n');

                    currentBalanceUsd = data.new_balance;
                    var newVnd = Math.round(currentBalanceUsd * usdRate).toLocaleString('vi-VN') + ' đ';
                    var newUsd = '$' + currentBalanceUsd.toFixed(2);
                    document.querySelectorAll('.balance-badge, .balance-amount').forEach(function(el) {
                        el.setAttribute('data-vnd', newVnd);
                        el.setAttribute('data-usd', newUsd);
                        el.innerText = (currentCurrency === 'VND') ? newVnd : newUsd;
                    });
                } else {
                    alert(data.message || 'Lỗi mua hàng!');
                    document.getElementById('buyModalFormStep').classList.remove('d-none');
                    document.getElementById('buyModalFooter').classList.remove('d-none');
                }
            })
            .catch(function(err) {
                document.getElementById('buyModalLoadingStep').classList.add('d-none');
                document.getElementById('buyModalFormStep').classList.remove('d-none');
                document.getElementById('buyModalFooter').classList.remove('d-none');
                alert('Có lỗi kết nối: ' + err);
            });
        }

        function copyDeliveredAccounts() {
            var text = document.getElementById('deliveredAccountsArea').value;
            copyToClipboard(text, 'Đã sao chép danh sách tài khoản đã cấp!');
        }

        function downloadDeliveredAccounts() {
            var text = document.getElementById('deliveredAccountsArea').value;
            var orderId = document.getElementById('resOrderId').innerText.replace('#', '');
            downloadTextFile('don_hang_' + orderId + '_accounts.txt', text);
        }
    </script>
    """

    return render_base_layout("Trang chủ", content, "home", user, balance, is_admin, categories)


# ==========================================
# 2. API MUA HÀNG TRỰC TIẾP TRÊN WEB
# ==========================================
@web_router.post("/api/web/buy")
async def api_web_buy(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    subcat_id = body.get("subcategory_id")
    quantity = int(body.get("quantity") or 1)

    if not subcat_id or quantity <= 0:
        return JSONResponse({"status": "error", "message": "Thông tin đặt hàng không hợp lệ!"}, status_code=400)

    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        if not user:
            return JSONResponse({"status": "error", "message": "Vui lòng đăng nhập để thực hiện mua hàng!", "require_login": True}, status_code=401)

        # Anti-spam click lock per user (1 second cooldown)
        now = time.time()
        last_click = _user_buy_lock.get(user.id, 0.0)
        if now - last_click < 1.0:
            return JSONResponse({"status": "error", "message": "Thao tác quá nhanh! Vui lòng đợi 1 giây trước khi bấm tiếp."}, status_code=429)
        _user_buy_lock[user.id] = now

        # Lấy thông tin Subcategory
        stmt_sub = select(Subcategory).options(selectinload(Subcategory.category)).where(Subcategory.id == subcat_id)
        subcategory = (await session.execute(stmt_sub)).scalar_one_or_none()
        if not subcategory:
            return JSONResponse({"status": "error", "message": "Sản phẩm không tồn tại!"}, status_code=404)

        unit_price = float(subcategory.price or 0.02)
        total_price = round(unit_price * quantity, 4)

        if balance < total_price:
            return JSONResponse({
                "status": "error",
                "message": f"Số dư không đủ! Cần {total_price:.2f}$, số dư hiện tại còn {balance:.2f}$. Vui lòng nạp thêm tiền."
            }, status_code=400)

        # Lấy các items chưa bán
        cat_name = subcategory.category.name if subcategory.category else ""
        is_fb_pre = is_facebook_product(cat_name, subcategory.name)

        stmt_items = (
            select(Item)
            .where(Item.subcategory_id == subcat_id, Item.is_sold == False)
            .order_by(Item.id.asc())
            .limit(quantity * 3 if is_fb_pre else quantity)
        )
        candidates = (await session.execute(stmt_items)).scalars().all()

        if len(candidates) < quantity:
            return JSONResponse({
                "status": "error",
                "message": f"Kho hàng không đủ số lượng! Hiện chỉ còn {len(candidates)} tài khoản."
            }, status_code=400)

        # Auto Check Live Facebook qua Graph API nếu là clone Facebook
        is_fb = is_fb_pre or any(is_facebook_clone(c.private_data) for c in candidates[:5])

        if is_fb and getattr(config, "FB_CHECK_LIVE_BEFORE_DELIVERY", True):
            live_items, dead_items = await filter_live_facebook_items(candidates, required_qty=quantity)
            if dead_items:
                if getattr(config, "FB_AUTO_DELETE_DIE_ON_DELIVERY", True):
                    await session.execute(delete(Item).where(Item.id.in_([d.id for d in dead_items])))
                else:
                    await session.execute(update(Item).where(Item.id.in_([d.id for d in dead_items])).values(is_sold=True, is_new=False))

            if len(live_items) < quantity:
                await session_commit(session)
                return JSONResponse({
                    "status": "error",
                    "message": f"Kho hàng hiện chỉ còn {len(live_items)} tài khoản LIVE ổn định sau khi quét Graph API. Vui lòng chọn lại số lượng!"
                }, status_code=400)

            purchased_items = live_items[:quantity]
        else:
            purchased_items = candidates[:quantity]

        # Trừ tiền & Cập nhật trạng thái
        user.consume_records = float(user.consume_records or 0.0) + total_price
        for item in purchased_items:
            item.is_sold = True
            item.is_new = False

        # Tạo bản ghi đơn hàng Buy & BuyItem
        buy_record = Buy(
            buyer_id=user.id,
            total_price=total_price,
            discount=0.0,
            status=BuyStatus.COMPLETED
        )
        session.add(buy_record)
        await session.flush()

        buy_item_record = BuyItem(
            buy_id=buy_record.id,
            item_ids=[it.id for it in purchased_items]
        )
        session.add(buy_item_record)
        await session_commit(session)

        # Thông báo Admin qua Telegram bot
        try:
            buy_dto = BuyDTO(
                id=buy_record.id,
                buyer_id=user.id,
                total_price=total_price,
                status=BuyStatus.COMPLETED
            )
            await NotificationService.new_buy(buy_dto, user, session)
        except Exception as e:
            logger.debug(f"Notification error: {e}")

        delivered_lines = [it.private_data for it in purchased_items if it.private_data]
        new_balance = max(0.0, float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0))

        return JSONResponse({
            "status": "success",
            "message": "Mua hàng thành công!",
            "order_id": buy_record.id,
            "quantity": len(purchased_items),
            "total_price": total_price,
            "new_balance": round(new_balance, 2),
            "accounts": delivered_lines
        })
