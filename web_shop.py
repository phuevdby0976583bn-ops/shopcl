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
from models.item import Item
from models.cart import Cart
from models.cartItem import CartItem
from models.user import User
from models.buy import Buy, BuyDTO
from models.buyItem import BuyItem, BuyItemDTO
from models.category import Category
from models.subcategory import Subcategory
from models.deposit import Deposit
from models.button_media import ButtonMedia
from models.payment import Payment
from models.coupon import Coupon
from models.shipping_option import ShippingOption
from models.review import Review
from models.referral import ReferralBonus
from models.binance_pay import BinancePayOrder
from models.bank_order import BankDepositOrder
from models.system_setting import SystemSetting
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

        function setCurrency(curr) {{{{
            currentCurrency = curr;
            localStorage.setItem('shop_currency', curr);
            updateCurrencyUI();
        }}}}

        function updateCurrencyUI() {{{{
            var label = document.getElementById('currentCurrencyLabel');
            if (label) {{{{
                label.innerText = currentCurrency === 'VND' ? 'VND (1$ = ' + usdRate.toLocaleString('vi-VN') + 'đ)' : 'USDT ($)';
            }}}}
            document.querySelectorAll('.currency-toggle-val').forEach(function(el) {{{{
                var vnd = el.getAttribute('data-vnd');
                var usd = el.getAttribute('data-usd');
                if (currentCurrency === 'VND' && vnd) {{{{
                    el.innerText = vnd;
                }}}} else if (usd) {{{{
                    el.innerText = usd;
                }}}}
            }}}});
        }}}}

        // Live product search filter
        document.addEventListener('DOMContentLoaded', function() {{{{
            updateCurrencyUI();
            var searchInput = document.getElementById('globalSearchInput');
            if (searchInput) {{{{
                searchInput.addEventListener('input', function() {{{{
                    var q = this.value.toLowerCase().trim();
                    document.querySelectorAll('.product-card-item').forEach(function(card) {{{{
                        var text = card.innerText.toLowerCase();
                        card.style.display = text.includes(q) ? '' : 'none';
                    }}}});
                }}}});
            }}}}
        }}}});

        function showWebToast(message, isSuccess = true) {{{{
            var toast = document.createElement('div');
            toast.className = 'custom-toast alert ' + (isSuccess ? 'alert-success' : 'alert-danger') + ' shadow-lg border-0 d-flex align-items-center justify-content-between p-3';
            toast.innerHTML = '<span>' + message + '</span><button type="button" class="btn-close ms-3" onclick="this.parentElement.remove()"></button>';
            document.body.appendChild(toast);
            setTimeout(function() {{{{
                toast.style.transition = 'opacity 0.4s';
                toast.style.opacity = '0';
                setTimeout(function() {{{{ toast.remove(); }}}}, 400);
            }}}}, 3500);
        }}}}

        function copyToClipboard(text, successMsg = 'Đã sao chép vào bộ nhớ tạm!') {{{{
            if (!text) return;
            navigator.clipboard.writeText(text).then(function() {{{{
                showWebToast('✅ ' + successMsg, true);
            }}}}).catch(function() {{{{
                var ta = document.createElement('textarea');
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showWebToast('✅ ' + successMsg, true);
            }}}});
        }}}}

        function downloadTextFile(filename, content) {{{{
            var blob = new Blob([content], {{{{ type: 'text/plain;charset=utf-8' }}}});
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
        }}}}
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

        # L?y danh m?c con
        stmt_sub = select(Subcategory).order_by(Subcategory.id.asc())
        subcategories = (await session.execute(stmt_sub)).scalars().all()

        # Map subcategory_id -> category_id t? b?ng items
        cat_map_stmt = select(Item.subcategory_id, Item.category_id).distinct()
        cat_map_rows = (await session.execute(cat_map_stmt)).all()
        sub_to_cat = {row[0]: row[1] for row in cat_map_rows}

        # T?n kho theo t?ng subcategory_id
        stock_stmt = (
            select(Item.subcategory_id, func.count(Item.id))
            .where(Item.is_sold == False)
            .group_by(Item.subcategory_id)
        )
        stock_rows = (await session.execute(stock_stmt)).all()
        stock_dict = {row[0]: row[1] for row in stock_rows}

    # Group subcategories by category
    cats_data = []
    default_cat_id = categories[0].id if categories else 1
    for cat in categories:
        sub_items = [s for s in subcategories if sub_to_cat.get(s.id, default_cat_id) == cat.id]
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

        function filterCategory(catId, btn) {{
            document.querySelectorAll('.cat-pill-btn').forEach(function(b) {{ b.classList.remove('active'); }});
            btn.classList.add('active');
            document.querySelectorAll('.category-block').forEach(function(block) {{
                if (catId === 'all' || block.getAttribute('data-cat-id') === catId) {{
                    block.style.display = '';
                }} else {{
                    block.style.display = 'none';
                }}
            }});
        }}

        function openBuyModal(subId, subName, unitPrice, stockQty) {{
            if (!isUserLoggedIn) {{
                window.location.href = '/login?next=/';
                return;
            }}
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
        }}

        function adjustQty(delta) {{
            var input = document.getElementById('buyQtyInput');
            var val = parseInt(input.value) || 1;
            val = Math.max(1, Math.min(activeSubMaxStock, val + delta));
            input.value = val;
            recalcModalTotal();
        }}

        function setQty(qty) {{
            var input = document.getElementById('buyQtyInput');
            var val = Math.max(1, Math.min(activeSubMaxStock, qty));
            input.value = val;
            recalcModalTotal();
        }}

        function setQtyMax() {{
            setQty(activeSubMaxStock);
        }}

        document.getElementById('buyQtyInput').addEventListener('input', recalcModalTotal);

        function recalcModalTotal() {{
            var qty = parseInt(document.getElementById('buyQtyInput').value) || 1;
            var unitPrice = parseFloat(document.getElementById('modalRawUnitPrice').value) || 0.02;
            var totalUsd = qty * unitPrice;
            var totalVnd = Math.round(totalUsd * usdRate);

            document.getElementById('modalTotalPrice').innerText = totalVnd.toLocaleString('vi-VN') + ' đ ($' + totalUsd.toFixed(2) + ')';

            var alertBox = document.getElementById('balanceAlertBox');
            var alertMsg = document.getElementById('balanceAlertMsg');
            var confirmBtn = document.getElementById('confirmBuyBtn');
            var rechargeBtn = document.getElementById('rechargeLinkBtn');

            if (totalUsd > currentBalanceUsd) {{
                var missing = totalUsd - currentBalanceUsd;
                var missingVnd = Math.round(missing * usdRate);
                alertMsg.innerHTML = 'Số dư ví không đủ! Còn thiếu: <strong>' + missingVnd.toLocaleString('vi-VN') + ' đ ($' + missing.toFixed(2) + ')</strong>';
                alertBox.classList.remove('d-none');
                confirmBtn.classList.add('d-none');
                rechargeBtn.classList.remove('d-none');
            }} else {{
                alertBox.classList.add('d-none');
                confirmBtn.classList.remove('d-none');
                rechargeBtn.classList.add('d-none');
            }}
        }}

        function executeBuyOrder() {{
            var subId = parseInt(document.getElementById('modalSubId').value);
            var qty = parseInt(document.getElementById('buyQtyInput').value) || 1;

            document.getElementById('buyModalFormStep').classList.add('d-none');
            document.getElementById('buyModalLoadingStep').classList.remove('d-none');
            document.getElementById('buyModalFooter').classList.add('d-none');

            fetch('/api/web/buy', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ subcategory_id: subId, quantity: qty }})
            }})
            .then(function(res) {{ return res.json(); }})
            .then(function(data) {{
                document.getElementById('buyModalLoadingStep').classList.add('d-none');
                if (data.status === 'success') {{
                    document.getElementById('buyModalSuccessStep').classList.remove('d-none');
                    document.getElementById('resOrderId').innerText = '#' + data.order_id;
                    document.getElementById('resOrderQty').innerText = data.quantity;
                    document.getElementById('deliveredAccountsArea').value = data.accounts.join('\n');

                    currentBalanceUsd = data.new_balance;
                    var newVnd = Math.round(currentBalanceUsd * usdRate).toLocaleString('vi-VN') + ' đ';
                    var newUsd = '$' + currentBalanceUsd.toFixed(2);
                    document.querySelectorAll('.balance-badge, .balance-amount').forEach(function(el) {{
                        el.setAttribute('data-vnd', newVnd);
                        el.setAttribute('data-usd', newUsd);
                        el.innerText = (currentCurrency === 'VND') ? newVnd : newUsd;
                    }});
                }} else {{
                    alert(data.message || 'Lỗi mua hàng!');
                    document.getElementById('buyModalFormStep').classList.remove('d-none');
                    document.getElementById('buyModalFooter').classList.remove('d-none');
                }}
            }})
            .catch(function(err) {{
                document.getElementById('buyModalLoadingStep').classList.add('d-none');
                document.getElementById('buyModalFormStep').classList.remove('d-none');
                document.getElementById('buyModalFooter').classList.remove('d-none');
                alert('Có lỗi kết nối: ' + err);
            }});
        }}

        function copyDeliveredAccounts() {{
            var text = document.getElementById('deliveredAccountsArea').value;
            copyToClipboard(text, 'Đã sao chép danh sách tài khoản đã cấp!');
        }}

        function downloadDeliveredAccounts() {{
            var text = document.getElementById('deliveredAccountsArea').value;
            var orderId = document.getElementById('resOrderId').innerText.replace('#', '');
            downloadTextFile('don_hang_' + orderId + '_accounts.txt', text);
        }}
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
    try:
        raw_qty = body.get("quantity")
        quantity = int(raw_qty) if raw_qty is not None else 1
    except (ValueError, TypeError):
        quantity = 0

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
        stmt_sub = select(Subcategory).where(Subcategory.id == subcat_id)
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
        cat_name = getattr(subcategory.category, "name", "") if hasattr(subcategory, "category") and subcategory.category else getattr(subcategory, "category_name", "")
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



from urllib.parse import quote

@web_router.api_route("/", methods=["HEAD"], include_in_schema=False)
async def web_home_head():
    return Response(status_code=200)

@web_router.get("/recharge", response_class=HTMLResponse)
async def web_recharge(request: Request, tab: str = Query("binance")):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        stmt_cats = select(Category).order_by(Category.id)
        categories = (await session.execute(stmt_cats)).scalars().all()

    binance_uid = getattr(config, "BINANCE_UID", "805398854") or "805398854"
    bank_stk = getattr(config, "BANK_BIDV_STK", "8838383838") or "8838383838"
    bank_acc_name = getattr(config, "BANK_BIDV_ACCOUNT_NAME", "NGUYEN VAN A") or "NGUYEN VAN A"

    memo_code = f"NAP {user.id}" if user else "NAP <MA_ID_CUA_BAN>"
    vietqr_url = f"https://img.vietqr.io/image/bidv-{bank_stk}-compact2.png?amount=0&addInfo={quote(memo_code)}&accountName={quote(bank_acc_name)}"

    user_alert_html = ""
    if not user:
        user_alert_html = """
        <div class="alert alert-warning border-0 shadow-sm d-flex align-items-center justify-content-between flex-wrap gap-2 mb-4" role="alert">
            <div class="d-flex align-items-center gap-2">
                <i class="fa-solid fa-triangle-exclamation fs-4 text-warning"></i>
                <div>
                    <strong>B?n ch?a ??ng nh?p!</strong>
                    <div class="small">Vui l?ng ??ng nh?p ho?c ??ng k? t?i kho?n ?? h? th?ng c?p m? n?p c? nh?n (NAP &lt;ID&gt;), gi?p ti?n ???c t? ??ng c?ng v?o v? c?a b?n sau 1 gi?y.</div>
                </div>
            </div>
            <div class="d-flex gap-2">
                <a href="/login?next=/recharge" class="btn btn-outline-dark btn-sm fw-bold">??ng nh?p</a>
                <a href="/register?next=/recharge" class="btn btn-purple btn-sm fw-bold">??ng k? m?i</a>
            </div>
        </div>
        """
    else:
        balance_vnd_str = format_vnd(balance)
        user_alert_html = f"""
        <div class="card border-0 shadow-sm rounded-4 mb-4 bg-purple-subtle p-3">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-3">
                <div class="d-flex align-items-center gap-3">
                    <div class="avatar-circle fs-4" style="width: 48px; height: 48px;"><i class="fa-solid fa-wallet"></i></div>
                    <div>
                        <div class="small text-muted">T?i kho?n: <strong class="text-dark">{html.escape(user.web_username or user.telegram_username or str(user.id))}</strong> (ID: <span class="badge bg-purple text-white">#{user.id}</span>)</div>
                        <div class="fs-5 fw-bold text-success">S? d?: {balance_vnd_str} <span class="text-muted fs-6">()</span></div>
                    </div>
                </div>
                <div class="bg-white p-2 px-3 rounded-3 shadow-sm border text-end">
                    <div class="small text-muted">C? ph?p n?p ti?n c? nh?n c?a b?n:</div>
                    <div class="d-flex align-items-center gap-2 mt-1">
                        <code class="fs-5 fw-bold text-danger user-select-all" id="myMemoText">{memo_code}</code>
                        <button class="btn btn-sm btn-outline-secondary" onclick="navigator.clipboard.writeText('{memo_code}'); Swal.fire({{icon:'success', title:'?? sao ch?p c? ph?p!', timer:1200, showConfirmButton:false}});" title="Sao ch?p c? ph?p">
                            <i class="fa-regular fa-copy"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="container py-4">
        <div class="mb-4">
            <nav aria-label="breadcrumb">
                <ol class="breadcrumb mb-1">
                    <li class="breadcrumb-item"><a href="/" class="text-purple text-decoration-none">Trang ch?</a></li>
                    <li class="breadcrumb-item active" aria-current="page">N?p ti?n t?i kho?n</li>
                </ol>
            </nav>
            <h2 class="fw-bold mb-1"><i class="fa-solid fa-wallet text-purple me-2"></i> N?p ti?n v?o t?i kho?n</h2>
            <p class="text-muted">H? th?ng n?p ti?n t? ??ng 24/7. H? tr? Binance Pay (0% ph?), BIDV VietQR v? Crypto USDT.</p>
        </div>

        {user_alert_html}

        <ul class="nav nav-pills mb-4 nav-justified bg-white p-2 rounded-4 shadow-sm border" id="rechargeTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link {'active' if tab != 'bank' and tab != 'onchain' else ''} fw-bold py-3 rounded-3" id="binance-tab" data-bs-toggle="pill" data-bs-target="#binance-pane" type="button" role="tab">
                    <i class="fa-solid fa-bolt text-warning me-2 fs-5"></i> Binance Pay (0% Ph? - Nh?n 1s)
                    <span class="badge bg-danger ms-2">Khuy?n d?ng</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link {'active' if tab == 'bank' else ''} fw-bold py-3 rounded-3" id="bank-tab" data-bs-toggle="pill" data-bs-target="#bank-pane" type="button" role="tab">
                    <i class="fa-solid fa-building-columns text-primary me-2 fs-5"></i> Ng?n h?ng BIDV (VietQR 24/7)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link {'active' if tab == 'onchain' else ''} fw-bold py-3 rounded-3" id="onchain-tab" data-bs-toggle="pill" data-bs-target="#onchain-pane" type="button" role="tab">
                    <i class="fa-solid fa-coins text-success me-2 fs-5"></i> Crypto On-Chain (USDT)
                </button>
            </li>
        </ul>

        <div class="tab-content" id="rechargeTabsContent">
            <!-- TAB 1: BINANCE PAY -->
            <div class="tab-pane fade {'show active' if tab != 'bank' and tab != 'onchain' else ''}" id="binance-pane" role="tabpanel">
                <div class="row g-4">
                    <div class="col-lg-7">
                        <div class="card border-0 shadow-sm rounded-4 h-100 p-4">
                            <div class="d-flex align-items-center justify-content-between mb-3 border-bottom pb-3">
                                <div>
                                    <h5 class="fw-bold mb-0 text-purple"><i class="fa-solid fa-bolt text-warning me-2"></i> N?p qua Binance Pay</h5>
                                    <small class="text-muted">Chuy?n n?i b? Binance - Mi?n ph? 100% ph? giao d?ch</small>
                                </div>
                                <span class="badge bg-success-subtle text-success border border-success fw-bold px-3 py-2 rounded-pill">
                                    <i class="fa-solid fa-circle-check me-1"></i> Nh?n ngay 1 gi?y
                                </span>
                            </div>

                            <div class="mb-4">
                                <label class="form-label text-muted small fw-bold">BINANCE UID NH?N TI?N:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0 fw-bold"><i class="fa-solid fa-id-badge text-purple me-1"></i> UID</span>
                                    <input type="text" class="form-control fw-bold fs-5 bg-white border-start-0 text-purple" id="binanceUidInput" value="{binance_uid}" readonly>
                                    <button class="btn btn-purple px-4" type="button" onclick="navigator.clipboard.writeText('{binance_uid}'); Swal.fire({{icon:'success', title:'?? copy Binance UID!', timer:1200, showConfirmButton:false}});">
                                        <i class="fa-regular fa-copy me-1"></i> Copy UID
                                    </button>
                                </div>
                            </div>

                            <div class="mb-4">
                                <label class="form-label text-muted small fw-bold">N?I DUNG CHUY?N TI?N (REMARK / NOTE):</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0 fw-bold"><i class="fa-solid fa-comment-dots text-danger me-1"></i> Memo</span>
                                    <input type="text" class="form-control fw-bold fs-5 bg-white border-start-0 text-danger" id="binanceMemoInput" value="{memo_code}" readonly>
                                    <button class="btn btn-outline-danger px-4" type="button" onclick="navigator.clipboard.writeText('{memo_code}'); Swal.fire({{icon:'success', title:'?? copy C? ph?p Memo!', timer:1200, showConfirmButton:false}});">
                                        <i class="fa-regular fa-copy me-1"></i> Copy Memo
                                    </button>
                                </div>
                                <div class="form-text text-danger fw-semibold mt-1">
                                    <i class="fa-solid fa-circle-exclamation me-1"></i> <strong>B?t bu?c</strong> nh?p ch?nh x?c n?i dung <code>{memo_code}</code> ?? h? th?ng t? ??ng c?ng ti?n trong 1 gi?y!
                                </div>
                            </div>

                            <div class="bg-light p-3 rounded-3 border mb-4">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="small fw-bold text-muted">T? gi? n?p Binance Pay:</span>
                                    <span class="fw-bold text-success fs-6">1 USDT = 1.00 USD (S? d? Bot)</span>
                                </div>
                                <div class="d-flex justify-content-between align-items-center">
                                    <span class="small fw-bold text-muted">H?n m?c n?p t?i thi?u:</span>
                                    <span class="fw-bold text-dark">0.01 USDT (Kh?ng gi?i h?n)</span>
                                </div>
                            </div>

                            <div class="mt-auto">
                                <a href="https://app.binance.com" target="_blank" class="btn btn-warning w-100 py-3 fw-bold shadow-sm d-flex align-items-center justify-content-center gap-2 text-dark">
                                    <i class="fa-solid fa-arrow-up-right-from-square"></i> M? App Binance ?? n?p ti?n ngay
                                </a>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-5">
                        <div class="card border-0 shadow-sm rounded-4 h-100 p-4">
                            <h6 class="fw-bold mb-3"><i class="fa-solid fa-list-ol text-purple me-2"></i> H??ng d?n 3 b??c n?p Binance Pay:</h6>
                            <div class="step-item d-flex gap-3 mb-3">
                                <div class="step-number bg-purple text-white rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width: 32px; height: 32px; font-weight: bold;">1</div>
                                <div>
                                    <div class="fw-bold">M? App Binance</div>
                                    <div class="small text-muted">B?m v?o bi?u t??ng <strong>Pay (Thanh to?n)</strong> ? g?c tr?n ho?c m?c V? Funding ? Pay.</div>
                                </div>
                            </div>
                            <div class="step-item d-flex gap-3 mb-3">
                                <div class="step-number bg-purple text-white rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width: 32px; height: 32px; font-weight: bold;">2</div>
                                <div>
                                    <div class="fw-bold">G?i ti?n t?i UID</div>
                                    <div class="small text-muted">Ch?n <strong>G?i (Send)</strong> ? Ch?n tab <strong>Binance ID (UID)</strong> ? D?n UID: <code>{binance_uid}</code>.</div>
                                </div>
                            </div>
                            <div class="step-item d-flex gap-3 mb-3">
                                <div class="step-number bg-purple text-white rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width: 32px; height: 32px; font-weight: bold;">3</div>
                                <div>
                                    <div class="fw-bold">?i?n s? ti?n &amp; Memo</div>
                                    <div class="small text-muted">Nh?p s? USDT mu?n n?p. ? ph?n <strong>Ghi ch? / Note (Memo)</strong>: nh?p ??ng <code>{memo_code}</code> r?i b?m X?c nh?n.</div>
                                </div>
                            </div>
                            <div class="alert alert-info border-0 rounded-3 small mt-auto mb-0">
                                <i class="fa-solid fa-bolt me-1 text-warning"></i> Sau khi chuy?n th?nh c?ng, Binance API s? t? ki?m tra v? t?i kho?n c?a b?n s? ???c c?ng ti?n sau 1 gi?y!
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: BANK BIDV VIETQR -->
            <div class="tab-pane fade {'show active' if tab == 'bank' else ''}" id="bank-pane" role="tabpanel">
                <div class="row g-4">
                    <div class="col-lg-6">
                        <div class="card border-0 shadow-sm rounded-4 h-100 p-4">
                            <div class="d-flex align-items-center justify-content-between mb-3 border-bottom pb-3">
                                <div>
                                    <h5 class="fw-bold mb-0 text-primary"><i class="fa-solid fa-building-columns me-2"></i> Chuy?n kho?n BIDV (VietQR)</h5>
                                    <small class="text-muted">Qu?t m? QR t? ??ng ?i?n STK &amp; N?i dung</small>
                                </div>
                                <span class="badge bg-primary-subtle text-primary border border-primary fw-bold px-3 py-2 rounded-pill">
                                    <i class="fa-solid fa-bolt me-1"></i> T? ??ng 30s
                                </span>
                            </div>

                            <div class="mb-3">
                                <label class="form-label text-muted small fw-bold">NG?N H?NG TH? H??NG:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0 fw-bold"><i class="fa-solid fa-bank text-primary"></i></span>
                                    <input type="text" class="form-control fw-bold bg-white border-start-0" value="BIDV - Ng?n h?ng TMCP ??u t? v? Ph?t tri?n VN" readonly>
                                </div>
                            </div>

                            <div class="mb-3">
                                <label class="form-label text-muted small fw-bold">S? T?I KHO?N (STK):</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0 fw-bold"><i class="fa-solid fa-credit-card text-primary"></i></span>
                                    <input type="text" class="form-control fw-bold fs-5 bg-white border-start-0 text-primary" value="{bank_stk}" id="bankStkInput" readonly>
                                    <button class="btn btn-outline-primary px-3" type="button" onclick="navigator.clipboard.writeText('{bank_stk}'); Swal.fire({{icon:'success', title:'?? copy STK BIDV!', timer:1200, showConfirmButton:false}});">
                                        <i class="fa-regular fa-copy"></i>
                                    </button>
                                </div>
                            </div>

                            <div class="mb-3">
                                <label class="form-label text-muted small fw-bold">CH? T?I KHO?N:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0 fw-bold"><i class="fa-solid fa-user-check text-primary"></i></span>
                                    <input type="text" class="form-control fw-bold bg-white border-start-0" value="{bank_acc_name}" readonly>
                                </div>
                            </div>

                            <div class="mb-3">
                                <label class="form-label text-muted small fw-bold">N?I DUNG CHUY?N KHO?N (MEMO):</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0 fw-bold"><i class="fa-solid fa-comment-dots text-danger"></i></span>
                                    <input type="text" class="form-control fw-bold fs-5 bg-white border-start-0 text-danger" value="{memo_code}" id="bankMemoInput" readonly>
                                    <button class="btn btn-outline-danger px-3" type="button" onclick="navigator.clipboard.writeText('{memo_code}'); Swal.fire({{icon:'success', title:'?? copy C? ph?p!', timer:1200, showConfirmButton:false}});">
                                        <i class="fa-regular fa-copy"></i>
                                    </button>
                                </div>
                                <div class="form-text text-danger fw-semibold mt-1">
                                    <i class="fa-solid fa-triangle-exclamation me-1"></i> B?t bu?c chuy?n ??ng n?i dung <code>{memo_code}</code> ?? h? th?ng nh?n di?n t? ??ng!
                                </div>
                            </div>

                            <div class="bg-light p-3 rounded-3 border mt-auto">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small fw-bold text-muted">T? gi? quy ??i:</span>
                                    <span class="fw-bold text-primary">1 USD = {rate:,} VN?</span>
                                </div>
                                <div class="d-flex justify-content-between align-items-center">
                                    <span class="small fw-bold text-muted">N?p t?i thi?u:</span>
                                    <span class="fw-bold text-dark">10,000 VN? (~0.4$)</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-6">
                        <div class="card border-0 shadow-sm rounded-4 h-100 p-4 text-center">
                            <h6 class="fw-bold mb-2"><i class="fa-solid fa-qrcode text-primary me-2"></i> Qu?t m? VietQR chuy?n kho?n nhanh:</h6>
                            <p class="text-muted small mb-3">M? app Ng?n h?ng b?t k? (Vietcombank, MB, Techcombank, VPBank, Momo...) qu?t m? ?? t? ?i?n STK &amp; N?i dung:</p>
                            <div class="d-flex justify-content-center my-auto">
                                <div class="p-3 bg-white rounded-3 shadow-sm border d-inline-block">
                                    <img src="{vietqr_url}" alt="M? VietQR n?p ti?n BIDV" class="img-fluid rounded" style="max-width: 280px; max-height: 280px;" onerror="this.src='https://placehold.co/280x280?text=BIDV+VietQR';">
                                </div>
                            </div>
                            <div class="alert alert-light border small mt-3 mb-0 text-muted">
                                <i class="fa-solid fa-shield-halved text-success me-1"></i> Qu?t m? QR gi?p tr?nh 100% r?i ro chuy?n sai s? t?i kho?n ho?c sai c? ph?p.
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: CRYPTO ON-CHAIN -->
            <div class="tab-pane fade {'show active' if tab == 'onchain' else ''}" id="onchain-pane" role="tabpanel">
                <div class="card border-0 shadow-sm rounded-4 p-4">
                    <div class="d-flex align-items-center justify-content-between mb-4 border-bottom pb-3">
                        <div>
                            <h5 class="fw-bold mb-0 text-success"><i class="fa-solid fa-coins me-2"></i> N?p ti?n Crypto On-Chain (USDT)</h5>
                            <small class="text-muted">H? tr? c?c m?ng TRC20, BEP20 qua c?ng thanh to?n b?o m?t</small>
                        </div>
                        <span class="badge bg-success-subtle text-success border border-success fw-bold px-3 py-2 rounded-pill">
                            <i class="fa-solid fa-shield me-1"></i> B?o m?t On-Chain
                        </span>
                    </div>

                    <div class="row g-4 align-items-center">
                        <div class="col-lg-7">
                            <p class="text-secondary">B?n c? th? n?p ti?n tr?c ti?p b?ng USDT th?ng qua v? On-chain. ??i v?i c?c ??n n?p On-chain s? l??ng l?n ho?c c?n x?c nh?n ngay, vui l?ng nh?n tr?c ti?p cho Admin qua Telegram.</p>
                            <ul class="list-unstyled mb-4">
                                <li class="mb-2"><i class="fa-solid fa-circle-check text-success me-2"></i> H? tr? m?ng: <strong>TRC20 (Tron)</strong>, <strong>BEP20 (BNB Smart Chain)</strong>.</li>
                                <li class="mb-2"><i class="fa-solid fa-circle-check text-success me-2"></i> T? gi? quy ??i: <strong>1 USDT = 1.00 USD</strong> s? d? t?i kho?n.</li>
                                <li class="mb-2"><i class="fa-solid fa-circle-check text-success me-2"></i> H?n m?c t?i thi?u: <strong>10 USDT</strong> (??i v?i On-chain ?? tr?nh ph? m?ng).</li>
                            </ul>
                            <div class="d-flex gap-2 flex-wrap">
                                <a href="https://t.me/truongdvfb" target="_blank" class="btn btn-purple fw-bold px-4 py-2">
                                    <i class="fa-brands fa-telegram me-1"></i> Chat v?i Admin @truongdvfb ?? n?p nhanh
                                </a>
                                <a href="/recharge?tab=binance" class="btn btn-outline-warning fw-bold px-4 py-2 text-dark">
                                    <i class="fa-solid fa-bolt me-1"></i> D?ng Binance Pay ?? ???c 0% ph?
                                </a>
                            </div>
                        </div>
                        <div class="col-lg-5 text-center">
                            <div class="p-4 bg-light rounded-4 border">
                                <i class="fa-solid fa-headset fs-1 text-purple mb-3"></i>
                                <h6 class="fw-bold mb-2">H? tr? N?p ti?n 24/7</h6>
                                <p class="text-muted small mb-3">N?u sau 3-5 ph?t b?n ch?a nh?n ???c s? d? ho?c c? b?t k? th?c m?c n?o, li?n h? ngay:</p>
                                <a href="https://t.me/truongdvfb" target="_blank" class="btn btn-outline-purple btn-sm fw-bold">
                                    <i class="fa-brands fa-telegram me-1"></i> @truongdvfb (Admin Duy Tr??ng)
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return HTMLResponse(content=render_base_layout(
        title="N?p ti?n t?i kho?n - Bubba Gump Clone Shop",
        body_content=content,
        active_nav="recharge",
        user=user,
        balance=balance,
        is_admin=is_admin,
        categories=categories
    ))


@web_router.get("/orders", response_class=HTMLResponse)
async def web_orders(request: Request):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        if not user:
            return RedirectResponse(url="/login?next=/orders", status_code=302)

        stmt_cats = select(Category).order_by(Category.id)
        categories = (await session.execute(stmt_cats)).scalars().all()

        stmt_buys = (
            select(Buy)
            .where(Buy.buyer_id == user.id)
            .options(selectinload(Buy.buyItems))
            .order_by(Buy.id.desc())
        )
        buys = (await session.execute(stmt_buys)).scalars().all()

    orders_rows_html = ""
    if not buys:
        orders_rows_html = """
        <tr>
            <td colspan="6" class="text-center py-5 text-muted">
                <i class="fa-solid fa-box-open fs-1 text-secondary mb-3 d-block"></i>
                <div class="fw-bold fs-5">B?n ch?a c? ??n h?ng n?o</div>
                <div class="small mb-3">H?y ch?n mua c?c t?i kho?n Facebook Clone ch?t l??ng cao tr?n trang ch?!</div>
                <a href="/" class="btn btn-purple btn-sm fw-bold px-4"><i class="fa-solid fa-cart-shopping me-1"></i> Mua h?ng ngay</a>
            </td>
        </tr>
        """
    else:
        for b in buys:
            count = 0
            for bi in b.buyItems:
                if bi.item_ids:
                    count += len(bi.item_ids)
            dt_str = b.created_at.strftime("%d/%m/%Y %H:%M") if b.created_at else "V?a xong"
            price_usd = f""
            price_vnd = format_vnd(b.total_price)

            orders_rows_html += f"""
            <tr>
                <td class="fw-bold text-purple align-middle">#ORD-{b.id}</td>
                <td class="align-middle text-muted small">{dt_str}</td>
                <td class="align-middle"><span class="badge bg-light text-dark border fw-bold">{count} t?i kho?n</span></td>
                <td class="align-middle fw-bold text-success">{price_vnd} <small class="text-muted">({price_usd})</small></td>
                <td class="align-middle"><span class="badge bg-success-subtle text-success border border-success fw-bold"><i class="fa-solid fa-circle-check me-1"></i> Ho?n t?t</span></td>
                <td class="align-middle text-end">
                    <button class="btn btn-sm btn-outline-purple fw-bold me-1" onclick="viewOrderModal({b.id})">
                        <i class="fa-solid fa-eye me-1"></i> Xem t?i kho?n
                    </button>
                    <button class="btn btn-sm btn-outline-success fw-bold" onclick="downloadOrderFile({b.id})">
                        <i class="fa-solid fa-download me-1"></i> T?i .txt
                    </button>
                </td>
            </tr>
            """

    content = f"""
    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
            <div>
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb mb-1">
                        <li class="breadcrumb-item"><a href="/" class="text-purple text-decoration-none">Trang ch?</a></li>
                        <li class="breadcrumb-item active" aria-current="page">L?ch s? ??n h?ng</li>
                    </ol>
                </nav>
                <h2 class="fw-bold mb-0"><i class="fa-solid fa-box text-purple me-2"></i> L?ch s? ??n h?ng ?? mua</h2>
            </div>
            <a href="/" class="btn btn-purple btn-sm fw-bold px-3">
                <i class="fa-solid fa-cart-shopping me-1"></i> Mua th?m t?i kho?n
            </a>
        </div>

        <div class="card border-0 shadow-sm rounded-4 overflow-hidden">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light text-muted small">
                        <tr>
                            <th scope="col" style="min-width: 110px;">M? ??n</th>
                            <th scope="col" style="min-width: 140px;">Th?i gian mua</th>
                            <th scope="col" style="min-width: 110px;">S? l??ng</th>
                            <th scope="col" style="min-width: 160px;">T?ng ti?n</th>
                            <th scope="col" style="min-width: 120px;">Tr?ng th?i</th>
                            <th scope="col" class="text-end" style="min-width: 220px;">H?nh ??ng</th>
                        </tr>
                    </thead>
                    <tbody>
                        {orders_rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- MODAL XEM CHI TI?T T?I KHO?N -->
    <div class="modal fade" id="orderDetailModal" tabindex="-1" aria-labelledby="orderDetailModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content rounded-4 border-0 shadow">
                <div class="modal-header bg-light">
                    <h5 class="modal-title fw-bold" id="orderDetailModalLabel"><i class="fa-solid fa-box text-purple me-2"></i> Chi ti?t ??n h?ng <span id="modalOrderCode" class="text-purple"></span></h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="small text-muted">T?ng c?ng: <strong id="modalOrderCount" class="text-dark">0</strong> t?i kho?n | ??nh d?ng: <code>UID|Pass|2FA|Cookie|Mail</code></div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-purple fw-bold" onclick="copyAllModalAccounts()">
                                <i class="fa-regular fa-copy me-1"></i> Sao ch?p t?t c?
                            </button>
                            <button class="btn btn-sm btn-outline-success fw-bold" onclick="downloadModalAccounts()">
                                <i class="fa-solid fa-download me-1"></i> T?i file .txt
                            </button>
                        </div>
                    </div>
                    <textarea class="form-control font-monospace small bg-light" id="modalOrderTextarea" rows="14" readonly style="font-size: 13px; white-space: pre;"></textarea>
                </div>
                <div class="modal-footer bg-light">
                    <button type="button" class="btn btn-secondary px-4 fw-bold" data-bs-dismiss="modal">??ng</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    let currentOrderAccounts = [];
    let currentOrderId = 0;

    async function viewOrderModal(orderId) {{
        currentOrderId = orderId;
        document.getElementById('modalOrderCode').innerText = '#ORD-' + orderId;
        document.getElementById('modalOrderTextarea').value = '?ang t?i danh s?ch t?i kho?n...';
        const modal = new bootstrap.Modal(document.getElementById('orderDetailModal'));
        modal.show();

        try {{
            const resp = await fetch('/api/web/order/' + orderId);
            const data = await resp.json();
            if (data.status === 'success') {{
                currentOrderAccounts = data.accounts || [];
                document.getElementById('modalOrderCount').innerText = currentOrderAccounts.length;
                document.getElementById('modalOrderTextarea').value = currentOrderAccounts.join('\n');
            }} else {{
                document.getElementById('modalOrderTextarea').value = 'L?i: ' + (data.message || 'Kh?ng th? t?i');
            }}
        }} catch(e) {{
            document.getElementById('modalOrderTextarea').value = 'L?i k?t n?i m?y ch?: ' + e;
        }}
    }}

    function copyAllModalAccounts() {{
        const text = document.getElementById('modalOrderTextarea').value;
        if (!text) return;
        navigator.clipboard.writeText(text);
        Swal.fire({{
            icon: 'success',
            title: '?? sao ch?p!',
            text: 'To?n b? danh s?ch t?i kho?n ?? ???c copy v?o b? nh? ??m.',
            timer: 1500,
            showConfirmButton: false
        }});
    }}

    function downloadModalAccounts() {{
        const text = document.getElementById('modalOrderTextarea').value;
        if (!text) return;
        const blob = new Blob([text], {{ type: 'text/plain;charset=utf-8' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'BubbaGump_Order_' + currentOrderId + '.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }}

    async function downloadOrderFile(orderId) {{
        try {{
            const resp = await fetch('/api/web/order/' + orderId);
            const data = await resp.json();
            if (data.status === 'success' && data.accounts) {{
                const blob = new Blob([data.accounts.join('\n')], {{ type: 'text/plain;charset=utf-8' }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'BubbaGump_Order_' + orderId + '.txt';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }} else {{
                Swal.fire('L?i', data.message || 'Kh?ng th? t?i ??n h?ng', 'error');
            }}
        }} catch(e) {{
            Swal.fire('L?i', 'L?i k?t n?i m?y ch?: ' + e, 'error');
        }}
    }}
    </script>
    """
    return HTMLResponse(content=render_base_layout(
        title="L?ch s? ??n h?ng - Bubba Gump Clone Shop",
        body_content=content,
        active_nav="orders",
        user=user,
        balance=balance,
        is_admin=is_admin,
        categories=categories
    ))


@web_router.get("/api/web/order/{order_id}")
async def api_web_order_detail(order_id: int, request: Request):
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        if not user:
            return JSONResponse({"status": "error", "message": "Vui l?ng ??ng nh?p"}, status_code=401)

        stmt = select(Buy).where(Buy.id == order_id).options(selectinload(Buy.buyItems))
        buy = (await session.execute(stmt)).scalar_one_or_none()
        if not buy:
            return JSONResponse({"status": "error", "message": "Kh?ng t?m th?y ??n h?ng"}, status_code=404)

        if buy.buyer_id != user.id and not is_admin:
            return JSONResponse({"status": "error", "message": "B?n kh?ng c? quy?n xem ??n h?ng n?y"}, status_code=403)

        all_item_ids = []
        for bi in buy.buyItems:
            if bi.item_ids:
                all_item_ids.extend(bi.item_ids)

        accounts = []
        if all_item_ids:
            stmt_items = select(Item).where(Item.id.in_(all_item_ids))
            items = (await session.execute(stmt_items)).scalars().all()
            accounts = [it.private_data for it in items if it.private_data]

        return JSONResponse({
            "status": "success",
            "order_id": order_id,
            "count": len(accounts),
            "total_price": buy.total_price,
            "accounts": accounts
        })


@web_router.get("/balance-history", response_class=HTMLResponse)
async def web_balance_history(request: Request):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        if not user:
            return RedirectResponse(url="/login?next=/balance-history", status_code=302)

        stmt_cats = select(Category).order_by(Category.id)
        categories = (await session.execute(stmt_cats)).scalars().all()

        stmt_dep = select(Deposit).where(Deposit.user_id == user.id).order_by(Deposit.id.desc()).limit(50)
        deposits = (await session.execute(stmt_dep)).scalars().all()

        stmt_buy = select(Buy).where(Buy.buyer_id == user.id).order_by(Buy.id.desc()).limit(50)
        buys = (await session.execute(stmt_buy)).scalars().all()

    timeline = []
    for dep in deposits:
        t = dep.deposit_time or datetime.now(timezone.utc)
        timeline.append({
            "time": t,
            "type": "deposit",
            "amount": float(dep.amount or 0.0),
            "title": "N?p ti?n v?o t?i kho?n",
            "desc": f"N?p qua {dep.method or 'H? th?ng t? ??ng'}",
            "status": "Ho?n t?t"
        })

    for b in buys:
        t = b.created_at or datetime.now(timezone.utc)
        timeline.append({
            "time": t,
            "type": "buy",
            "amount": -float(b.total_price or 0.0),
            "title": f"Mua h?ng - ??n #ORD-{b.id}",
            "desc": "Thanh to?n mua t?i kho?n t? ??ng",
            "status": "Th?nh c?ng"
        })

    timeline.sort(key=lambda x: x["time"], reverse=True)

    rows_html = ""
    if not timeline:
        rows_html = """
        <tr>
            <td colspan="5" class="text-center py-5 text-muted">
                <i class="fa-solid fa-clock-rotate-left fs-1 text-secondary mb-3 d-block"></i>
                <div class="fw-bold fs-5">Ch?a c? bi?n ??ng s? d? n?o</div>
                <div class="small">L?ch s? n?p ti?n v? mua h?ng s? hi?n th? chi ti?t t?i ??y.</div>
            </td>
        </tr>
        """
    else:
        for ev in timeline:
            dt_str = ev["time"].strftime("%d/%m/%Y %H:%M:%S")
            amt = ev["amount"]
            if ev["type"] == "deposit":
                badge_type = '<span class="badge bg-success-subtle text-success border border-success fw-bold"><i class="fa-solid fa-arrow-down me-1"></i> N?p ti?n (+)</span>'
                amt_str = f'<span class="fw-bold text-success">+{format_vnd(amt)} <small class="text-muted">(+)</small></span>'
            else:
                badge_type = '<span class="badge bg-danger-subtle text-danger border border-danger fw-bold"><i class="fa-solid fa-arrow-up me-1"></i> Mua h?ng (-)</span>'
                amt_str = f'<span class="fw-bold text-danger">-{format_vnd(abs(amt))} <small class="text-muted">(-)</small></span>'

            rows_html += f"""
            <tr>
                <td class="align-middle text-muted small">{dt_str}</td>
                <td class="align-middle">{badge_type}</td>
                <td class="align-middle">{amt_str}</td>
                <td class="align-middle fw-semibold text-dark">{html.escape(ev['desc'])}</td>
                <td class="align-middle"><span class="badge bg-light text-success border fw-bold"><i class="fa-solid fa-circle-check me-1"></i> {ev['status']}</span></td>
            </tr>
            """

    content = f"""
    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
            <div>
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb mb-1">
                        <li class="breadcrumb-item"><a href="/" class="text-purple text-decoration-none">Trang ch?</a></li>
                        <li class="breadcrumb-item active" aria-current="page">Bi?n ??ng s? d?</li>
                    </ol>
                </nav>
                <h2 class="fw-bold mb-0"><i class="fa-solid fa-list-check text-purple me-2"></i> L?ch s? bi?n ??ng s? d?</h2>
            </div>
            <a href="/recharge" class="btn btn-purple btn-sm fw-bold px-3">
                <i class="fa-solid fa-plus me-1"></i> N?p ti?n ngay
            </a>
        </div>

        <div class="card border-0 shadow-sm rounded-4 overflow-hidden">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-light text-muted small">
                        <tr>
                            <th scope="col" style="min-width: 150px;">Th?i gian</th>
                            <th scope="col" style="min-width: 130px;">Lo?i giao d?ch</th>
                            <th scope="col" style="min-width: 160px;">Bi?n ??ng</th>
                            <th scope="col" style="min-width: 220px;">N?i dung chi ti?t</th>
                            <th scope="col" style="min-width: 110px;">Tr?ng th?i</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return HTMLResponse(content=render_base_layout(
        title="Bi?n ??ng s? d? - Bubba Gump Clone Shop",
        body_content=content,
        active_nav="balance_history",
        user=user,
        balance=balance,
        is_admin=is_admin,
        categories=categories
    ))


@web_router.get("/policy", response_class=HTMLResponse)
async def web_policy(request: Request):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        stmt_cats = select(Category).order_by(Category.id)
        categories = (await session.execute(stmt_cats)).scalars().all()

    content = f"""
    <div class="container py-4">
        <div class="mb-4">
            <nav aria-label="breadcrumb">
                <ol class="breadcrumb mb-1">
                    <li class="breadcrumb-item"><a href="/" class="text-purple text-decoration-none">Trang ch?</a></li>
                    <li class="breadcrumb-item active" aria-current="page">?i?u kho?n &amp; Ch?nh s?ch b?o h?nh</li>
                </ol>
            </nav>
            <h2 class="fw-bold mb-1"><i class="fa-solid fa-shield-halved text-purple me-2"></i> Ch?nh s?ch b?o h?nh &amp; ?i?u kho?n s? d?ng</h2>
            <p class="text-muted">Tu?n th? nghi?m ng?t Lu?t An ninh m?ng Vi?t Nam 2018 (Lu?t s? 24/2018/QH14) v? c?c quy ??nh th??ng m?i ?i?n t?.</p>
        </div>

        <div class="row g-4">
            <div class="col-lg-8">
                <div class="card border-0 shadow-sm rounded-4 p-4 mb-4">
                    <h5 class="fw-bold text-purple mb-3"><i class="fa-solid fa-scale-balanced me-2"></i> 1. M?c ??ch s? d?ng h?p ph?p</h5>
                    <p class="text-secondary leading-relaxed">
                        T?t c? c?c t?i kho?n clone, t?i kho?n Facebook, t?i kho?n AI, CapCut Pro v? d?ch v? nguy?n li?u ???c cung c?p tr?n h? th?ng c?a ch?ng t?i <strong>ch? ph?c v? cho c?c m?c ??ch h?p ph?p</strong> bao g?m:
                    </p>
                    <ul class="text-secondary">
                        <li>Ki?m th? h? th?ng ph?n m?m, benchmark t?i m?y ch?, t? ??ng h?a QA/QC theo quy tr?nh l?p tr?nh.</li>
                        <li>Ch?y chi?n d?ch qu?ng c?o Marketing (Facebook Ads), seeding th??ng hi?u s?n ph?m tu?n th? ch?nh s?ch qu?ng c?o.</li>
                        <li>H?c t?p, nghi?n c?u an to?n th?ng tin v? b?o m?t m?ng (Cyber Security &amp; Information Safety).</li>
                    </ul>
                    <div class="alert alert-danger border-0 rounded-3 small">
                        <strong><i class="fa-solid fa-triangle-exclamation me-1"></i> C?NH B?O PH?P L?:</strong> Nghi?m c?m tuy?t ??i m?i h?nh vi s? d?ng t?i kho?n v?o m?c ??ch l?a ??o, chi?m ?o?t t?i s?n, tuy?n truy?n ch?ng ph? Nh? n??c, ph?t t?n m? ??c ho?c vi ph?m Lu?t An ninh m?ng 2018. M?i c? nh?n vi ph?m ph?i t? ch?u ho?n to?n tr?ch nhi?m tr??c ph?p lu?t!
                    </div>

                    <h5 class="fw-bold text-purple mt-4 mb-3"><i class="fa-solid fa-check-double me-2"></i> 2. Ch?nh s?ch B?o h?nh (1 ??i 1 trong 24 gi?)</h5>
                    <p class="text-secondary">H? th?ng ?p d?ng ch?nh s?ch b?o h?nh minh b?ch 1 ??i 1 ho?c ho?n ti?n v?o s? d? trong v?ng <strong>24 gi?</strong> k? t? th?i ?i?m giao ??n h?ng ??i v?i c?c tr??ng h?p:</p>
                    <div class="row g-3 mb-3">
                        <div class="col-md-6">
                            <div class="p-3 bg-light rounded-3 border">
                                <div class="fw-bold text-success mb-1"><i class="fa-solid fa-circle-check me-1"></i> ???c b?o h?nh:</div>
                                <ul class="small text-muted mb-0 ps-3">
                                    <li>Sai m?t kh?u (Wrong Password) ngay khi xu?t kho.</li>
                                    <li>M? 2FA b? l?i ho?c kh?ng t?o ???c m? 6 s?.</li>
                                    <li>T?i kho?n b? checkpoint (kh?a) tr??c th?i gian xu?t kho.</li>
                                    <li>T?i kho?n thi?u email / cookie so v?i m? t? g?i h?ng.</li>
                                </ul>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="p-3 bg-light rounded-3 border">
                                <div class="fw-bold text-danger mb-1"><i class="fa-solid fa-circle-xmark me-1"></i> T? ch?i b?o h?nh:</div>
                                <ul class="small text-muted mb-0 ps-3">
                                    <li>?? ??ng nh?p th?nh c?ng nh?ng spam vi ph?m ch?nh s?ch FB.</li>
                                    <li>??ng nh?p h?ng lo?t tr?n c?ng 1 IP b?n m? kh?ng d?ng Proxy.</li>
                                    <li>T? ? ??i Password/Email m? kh?ng tu?n th? quy tr?nh an to?n.</li>
                                    <li>Qu? h?n 24 gi? k? t? th?i ?i?m mua h?ng.</li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <h5 class="fw-bold text-purple mt-4 mb-3"><i class="fa-solid fa-hand-holding-hand me-2"></i> 3. Quy tr?nh Khi?u n?i &amp; H? tr?</h5>
                    <p class="text-secondary">
                        Khi g?p s? c? c?n b?o h?nh, qu? kh?ch vui l?ng gi? nguy?n tr?ng th?i t?i kho?n v? g?i ngay M? ??n h?ng (#ORD-xxx) k?m danh s?ch d?ng l?i qua k?nh Telegram h? tr?:
                    </p>
                    <a href="https://t.me/truongdvfb" target="_blank" class="btn btn-purple fw-bold px-4 py-2">
                        <i class="fa-brands fa-telegram me-1"></i> G?i khi?u n?i t?i Admin: @truongdvfb
                    </a>
                </div>
            </div>

            <div class="col-lg-4">
                <div class="card border-0 shadow-sm rounded-4 p-4 mb-4 bg-purple-subtle">
                    <h6 class="fw-bold text-purple mb-3"><i class="fa-solid fa-headset me-2"></i> K?nh h? tr? duy nh?t</h6>
                    <div class="d-flex align-items-center gap-3 mb-3">
                        <div class="avatar-circle fs-3" style="width: 48px; height: 48px;"><i class="fa-brands fa-telegram"></i></div>
                        <div>
                            <div class="fw-bold">Admin Duy Tr??ng</div>
                            <div class="small text-muted">Telegram: <a href="https://t.me/truongdvfb" target="_blank" class="text-purple fw-bold">@truongdvfb</a></div>
                        </div>
                    </div>
                    <div class="small text-muted">
                        <i class="fa-solid fa-clock me-1"></i> Th?i gian ph?n h?i: 8:00 - 24:00 h?ng ng?y (k? c? Th? 7, Ch? Nh?t &amp; Ng?y l?).
                    </div>
                </div>

                <div class="card border-0 shadow-sm rounded-4 p-4">
                    <h6 class="fw-bold mb-3"><i class="fa-solid fa-circle-info text-info me-2"></i> L?i khuy?n an to?n:</h6>
                    <div class="small text-muted">
                        <p class="mb-2"><i class="fa-solid fa-check text-success me-1"></i> Lu?n d?ng ph?n m?m qu?n l? profile Antidetect (AdsPower, Gologin, Genlogin) khi nu?i s? l??ng l?n.</p>
                        <p class="mb-2"><i class="fa-solid fa-check text-success me-1"></i> G?n Proxy t?nh (IPv4 Residential) ho?c xoay Dcom cho t?ng t?i kho?n.</p>
                        <p class="mb-0"><i class="fa-solid fa-check text-success me-1"></i> ??ng nh?p qua Cookie ho?c 2FA t?i <code>mbasic.facebook.com</code> l?n ??u ?? gi?m thi?u checkpoint.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return HTMLResponse(content=render_base_layout(
        title="Ch?nh s?ch b?o h?nh & ?i?u kho?n - Bubba Gump Clone Shop",
        body_content=content,
        active_nav="policy",
        user=user,
        balance=balance,
        is_admin=is_admin,
        categories=categories
    ))


@web_router.get("/faq", response_class=HTMLResponse)
async def web_faq(request: Request):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        stmt_cats = select(Category).order_by(Category.id)
        categories = (await session.execute(stmt_cats)).scalars().all()

    content = f"""
    <div class="container py-4">
        <div class="mb-4">
            <nav aria-label="breadcrumb">
                <ol class="breadcrumb mb-1">
                    <li class="breadcrumb-item"><a href="/" class="text-purple text-decoration-none">Trang ch?</a></li>
                    <li class="breadcrumb-item active" aria-current="page">C?u h?i th??ng g?p (FAQ)</li>
                </ol>
            </nav>
            <h2 class="fw-bold mb-1"><i class="fa-solid fa-circle-question text-purple me-2"></i> C?u h?i th??ng g?p (FAQ)</h2>
            <p class="text-muted">T?ng h?p c?c th?c m?c ph? bi?n v? mua h?ng, n?p ti?n, b?o h?nh v? k? thu?t nu?i t?i kho?n.</p>
        </div>

        <div class="accordion accordion-flush shadow-sm rounded-4 bg-white p-3 border" id="faqAccordion">
            <div class="accordion-item border-bottom py-2">
                <h2 class="accordion-header" id="faqHead1">
                    <button class="accordion-button fw-bold text-purple collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faqCollapse1">
                        1. ??nh d?ng t?i kho?n nh?n ???c khi mua l? g??
                    </button>
                </h2>
                <div id="faqCollapse1" class="accordion-collapse collapse" data-bs-parent="#faqAccordion">
                    <div class="accordion-body text-secondary">
                        ??nh d?ng chu?n xu?t kho c?a shop th?ng th??ng l?:<br>
                        <code>UID|Pass|2FA_Secret_Key|Cookie|Mail|PassMail</code> ho?c <code>UID|Pass|2FA</code> t?y theo t?ng g?i h?ng m? b?n ch?n.<br>
                        C?c tr??ng d? li?u ???c ng?n c?ch nhau b?ng d?u g?ch ??ng <code>|</code>, r?t thu?n ti?n ?? import th?ng v?o c?c ph?n m?m auto nh? FPlus, MaxCare, MKT Care, v.v.
                    </div>
                </div>
            </div>

            <div class="accordion-item border-bottom py-2">
                <h2 class="accordion-header" id="faqHead2">
                    <button class="accordion-button fw-bold text-purple collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faqCollapse2">
                        2. L?m sao ?? l?y m? b?o m?t 2FA 6 ch? s? khi ??ng nh?p?
                    </button>
                </h2>
                <div id="faqCollapse2" class="accordion-collapse collapse" data-bs-parent="#faqAccordion">
                    <div class="accordion-body text-secondary">
                        B?n copy chu?i <strong>2FA_Secret_Key</strong> (chu?i k? t? vi?t hoa g?m 32 k? t? trong ??n h?ng) ? Truy c?p trang web <a href="https://2fa.live" target="_blank" class="fw-bold text-purple">2fa.live</a> ? D?n chu?i v?o ? v? b?m <strong>Submit</strong> ? H? th?ng s? sinh m? 6 s? thay ??i m?i 30 gi?y ?? b?n ?i?n v?o Facebook.
                    </div>
                </div>
            </div>

            <div class="accordion-item border-bottom py-2">
                <h2 class="accordion-header" id="faqHead3">
                    <button class="accordion-button fw-bold text-purple collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faqCollapse3">
                        3. ??ng nh?p l?m sao ?? t?i kho?n kh?ng b? Checkpoint / Kh?a?
                    </button>
                </h2>
                <div id="faqCollapse3" class="accordion-collapse collapse" data-bs-parent="#faqAccordion">
                    <div class="accordion-body text-secondary">
                        ?? ??t ?? b?n t?i ?a:<br>
                        - Kh?ng bao gi? ??ng nh?p h?ng ch?c t?i kho?n tr?n c?ng 1 tr?nh duy?t Chrome th?ng th??ng.<br>
                        - N?n s? d?ng tr?nh duy?t b?o v? Antidetect (nh? AdsPower, Gologin, Genlogin) ?? c? l?p t?ng m?i tr??ng ph?n c?ng m?y t?nh.<br>
                        - M?i t?i kho?n n?n g?n k?m 1 Proxy ri?ng (Proxy IPv4 t?nh ho?c Dcom xoay IP).<br>
                        - L?n ??u ??ng nh?p, n?n truy c?p qua trang <code>mbasic.facebook.com</code> ho?c d?ng Cookie ?? load phi?n.
                    </div>
                </div>
            </div>

            <div class="accordion-item border-bottom py-2">
                <h2 class="accordion-header" id="faqHead4">
                    <button class="accordion-button fw-bold text-purple collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faqCollapse4">
                        4. Ch?c n?ng Check Live t? ??ng tr??c khi giao h?ng l? g??
                    </button>
                </h2>
                <div id="faqCollapse4" class="accordion-collapse collapse" data-bs-parent="#faqAccordion">
                    <div class="accordion-body text-secondary">
                        H? th?ng c?a ch?ng t?i t?ch h?p s?n t?nh n?ng <strong>Qu?t Live UID th?i gian th?c</strong> qua Facebook Graph API. Tr??c khi xu?t kho v? tr? ti?n, bot s? qu?t to?n b? danh s?ch t?i kho?n trong kho ?? ??m b?o t?i kho?n giao ??n tay b?n <strong>100% ?ang LIVE (c?n ho?t ??ng)</strong>. N?u ph?t hi?n acc die, h? th?ng t? ??ng lo?i b? v? ch?n t?i kho?n live kh?c thay th?!
                    </div>
                </div>
            </div>

            <div class="accordion-item border-bottom py-2">
                <h2 class="accordion-header" id="faqHead5">
                    <button class="accordion-button fw-bold text-purple collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faqCollapse5">
                        5. N?p ti?n qua Binance Pay &amp; Ng?n h?ng bao l?u th? v?o v??
                    </button>
                </h2>
                <div id="faqCollapse5" class="accordion-collapse collapse" data-bs-parent="#faqAccordion">
                    <div class="accordion-body text-secondary">
                        - <strong>Binance Pay (0% ph?)</strong>: Ti?n v?o v? ch? sau <strong>1 gi?y</strong>! Binance API s? nh?n d? li?u t?c th?i ngay khi b?n x?c nh?n g?i.<br>
                        - <strong>Ng?n h?ng BIDV (VietQR 24/7)</strong>: Ti?n t? ??ng c?ng trong kho?ng <strong>30 gi?y</strong> sau khi ng?n h?ng x? l? xong l?nh chuy?n.<br>
                        S? d? tr?n Website v? tr?n Telegram Bot ???c ??ng b? v?i nhau 100%.
                    </div>
                </div>
            </div>

            <div class="accordion-item py-2">
                <h2 class="accordion-header" id="faqHead6">
                    <button class="accordion-button fw-bold text-purple collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faqCollapse6">
                        6. T?i c? th? li?n k?t t?i kho?n ?? d?ng tr?n Bot Telegram kh?ng?
                    </button>
                </h2>
                <div id="faqCollapse6" class="accordion-collapse collapse" data-bs-parent="#faqAccordion">
                    <div class="accordion-body text-secondary">
                        <strong>Ho?n to?n ???c!</strong> Khi b?n b?m ??ng k? t?i kho?n tr?n Website, h?y ?i?n th?m <strong>Telegram ID</strong> c?a b?n v?o ? ??ng k?. H? th?ng s? ngay l?p t?c li?n k?t t?i kho?n Web v?i Bot, gi?p to?n b? s? d? v? l?ch s? giao d?ch tr??c ??y tr?n Telegram Bot hi?n di?n ??y ?? tr?n Website.
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return HTMLResponse(content=render_base_layout(
        title="C?u h?i th??ng g?p FAQ - Bubba Gump Clone Shop",
        body_content=content,
        active_nav="faq",
        user=user,
        balance=balance,
        is_admin=is_admin,
        categories=categories
    ))


@web_router.get("/login", response_class=HTMLResponse)
async def web_login_page(request: Request, next: str = Query("/"), error: Optional[str] = None):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        if user:
            return RedirectResponse(url=next if next and next.startswith("/") else "/", status_code=302)

        stmt_cats = select(Category).order_by(Category.id)
        categories = (await session.execute(stmt_cats)).scalars().all()

    error_html = ""
    if error:
        error_html = f"""
        <div class="alert alert-danger border-0 rounded-3 d-flex align-items-center gap-2 mb-4" role="alert">
            <i class="fa-solid fa-circle-exclamation fs-5"></i>
            <div>{html.escape(error)}</div>
        </div>
        """

    content = f"""
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-7 col-lg-5">
                <div class="card border-0 shadow-lg rounded-4 overflow-hidden">
                    <div class="p-4 bg-purple text-white text-center">
                        <div class="brand-logo justify-content-center text-white mb-2 fs-3">
                            <i class="fa-solid fa-shrimp"></i> Bubba Gump Shop
                        </div>
                        <p class="mb-0 small opacity-75">??ng nh?p t?i kho?n Kh?ch h?ng / Qu?n tr? vi?n</p>
                    </div>

                    <div class="card-body p-4 p-md-5">
                        {error_html}

                        <form method="POST" action="/login" id="loginForm">
                            <input type="hidden" name="next" value="{html.escape(next)}">

                            <div class="mb-3">
                                <label for="usernameInput" class="form-label fw-bold small text-muted">T?n ??ng nh?p / Telegram Username:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0"><i class="fa-solid fa-user text-purple"></i></span>
                                    <input type="text" class="form-control border-start-0" id="usernameInput" name="username" placeholder="Nh?p username (ho?c 'admin')" required autofocus>
                                </div>
                            </div>

                            <div class="mb-4">
                                <label for="passwordInput" class="form-label fw-bold small text-muted">M?t kh?u:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0"><i class="fa-solid fa-lock text-purple"></i></span>
                                    <input type="password" class="form-control border-start-0" id="passwordInput" name="password" placeholder="Nh?p m?t kh?u c?a b?n" required>
                                </div>
                            </div>

                            <button type="submit" class="btn btn-purple w-100 py-3 fw-bold rounded-3 shadow-sm mb-3">
                                <i class="fa-solid fa-right-to-bracket me-2"></i> ??ng nh?p ngay
                            </button>
                        </form>

                        <div class="alert alert-light border small text-muted rounded-3 mb-4">
                            <i class="fa-solid fa-circle-info text-primary me-1"></i>
                            <strong>D?nh cho Admin:</strong> Khi ??ng nh?p v?i t?i kho?n Admin, tr?n thanh ?i?u h??ng s? t? ??ng xu?t hi?n n?t <strong>[ ?? Chuy?n sang Admin Panel ]</strong> ?? qu?n l? to?n b? h? th?ng!
                        </div>

                        <div class="text-center small text-muted">
                            Ch?a c? t?i kho?n? <a href="/register?next={html.escape(next)}" class="text-purple fw-bold text-decoration-none">??ng k? ngay t?i ??y</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return HTMLResponse(content=render_base_layout(
        title="??ng nh?p - Bubba Gump Clone Shop",
        body_content=content,
        active_nav="login",
        user=None,
        balance=0.0,
        is_admin=False,
        categories=categories
    ))


@web_router.post("/login")
async def web_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/")
):
    clean_username = username.strip()
    clean_password = password.strip()
    target_url = next if next and next.startswith("/") else "/"

    async with get_db_session() as session:
        # 1. KI?M TRA ??NG NH?P ADMIN (username == "admin" ho?c kh?p m?t kh?u admin)
        is_admin_candidate = (clean_username.lower() == "admin")
        admin_raw_pw = getattr(config, "SQLADMIN_RAW_PASSWORD", "MatKhauAdminCuaBan123")
        admin_hashed = getattr(config, "SQLADMIN_HASHED_PASSWORD", "")

        is_admin_pw_ok = False
        if clean_password == admin_raw_pw:
            is_admin_pw_ok = True
        elif admin_hashed and verify_password(clean_password, admin_hashed):
            is_admin_pw_ok = True

        if is_admin_candidate and is_admin_pw_ok:
            # T?o Token SqlAdmin
            admin_token = create_access_token({"sub": UserRole.ADMIN.name})
            request.session["token"] = admin_token

            # ??m b?o c? User record ??i di?n cho admin trong DB
            stmt = select(User).where(or_(User.web_username == "admin", User.telegram_username == "admin"))
            admin_user = (await session.execute(stmt)).scalar_one_or_none()
            if not admin_user:
                admin_id_val = config.ADMIN_ID_LIST[0] if config.ADMIN_ID_LIST else 805398854
                admin_user = User(
                    telegram_id=admin_id_val,
                    telegram_username="admin",
                    web_username="admin",
                    password_hash=hash_password(clean_password),
                    top_up_amount=999.0,
                    consume_records=0.0
                )
                session.add(admin_user)
                await session_commit(session)

            request.session["web_user"] = {
                "id": admin_user.id,
                "username": "admin",
                "is_admin": True
            }
            return RedirectResponse(url=target_url, status_code=302)

        # 2. KI?M TRA ??NG NH?P USER TH??NG
        stmt_user = select(User).where(or_(User.web_username == clean_username, User.telegram_username == clean_username))
        if clean_username.isdigit():
            stmt_user = select(User).where(or_(
                User.web_username == clean_username,
                User.telegram_username == clean_username,
                User.telegram_id == int(clean_username)
            ))

        user = (await session.execute(stmt_user)).scalar_one_or_none()
        if not user:
            return RedirectResponse(url=f"/login?error=T%C3%A0i%20kho%E1%BA%A3n%20kh%C3%B4ng%20t%E1%BB%93n%20t%E1%BA%A1i&next={quote(target_url)}", status_code=302)

        if user.is_banned:
            return RedirectResponse(url=f"/login?error=T%C3%A0i%20kho%E1%BA%A3n%20c%E1%BB%A7a%20b%E1%BA%A1n%20%C4%91%C3%A3%20b%E1%BB%8B%20kh%C3%B3a&next={quote(target_url)}", status_code=302)

        if not user.password_hash:
            return RedirectResponse(url=f"/login?error=T%C3%A0i%20kho%E1%BA%A3n%20ch%C6%B0a%20c%C3%B3%20m%E1%BA%ADt%20kh%E1%BA%A9u%20web.%20Vui%20l%C3%B2ng%20b%E1%BA%A5m%20%C4%90%C4%83ng%20k%C3%BD%20v%C3%A0%20nh%E1%BA%ADp%20Telegram%20ID%20%C4%91%E1%BB%83%20t%E1%BA%A1o%20m%E1%BA%ADt%20kh%E1%BA%A9u!&next={quote(target_url)}", status_code=302)

        if not verify_password(clean_password, user.password_hash):
            return RedirectResponse(url=f"/login?error=M%E1%BA%ADt%20kh%E1%BA%A9u%20kh%C3%B4ng%20ch%C3%ADnh%20x%C3%A1c&next={quote(target_url)}", status_code=302)

        # ??ng nh?p User th?nh c?ng
        is_user_admin = False
        if user.telegram_id in config.ADMIN_ID_LIST or user.web_username == "admin" or user.telegram_username == "admin":
            is_user_admin = True
            admin_token = create_access_token({"sub": UserRole.ADMIN.name})
            request.session["token"] = admin_token
        else:
            request.session.pop("token", None)

        request.session["web_user"] = {
            "id": user.id,
            "username": user.web_username or user.telegram_username or str(user.telegram_id),
            "is_admin": is_user_admin
        }
        return RedirectResponse(url=target_url, status_code=302)


@web_router.get("/register", response_class=HTMLResponse)
async def web_register_page(request: Request, next: str = Query("/"), error: Optional[str] = None):
    rate = get_rate()
    async with get_db_session() as session:
        user, balance, is_admin = await get_current_user_info(request, session)
        if user:
            return RedirectResponse(url=next if next and next.startswith("/") else "/", status_code=302)

        stmt_cats = select(Category).order_by(Category.id)
        categories = (await session.execute(stmt_cats)).scalars().all()

    error_html = ""
    if error:
        error_html = f"""
        <div class="alert alert-danger border-0 rounded-3 d-flex align-items-center gap-2 mb-4" role="alert">
            <i class="fa-solid fa-circle-exclamation fs-5"></i>
            <div>{html.escape(error)}</div>
        </div>
        """

    content = f"""
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-7 col-lg-5">
                <div class="card border-0 shadow-lg rounded-4 overflow-hidden">
                    <div class="p-4 bg-purple text-white text-center">
                        <div class="brand-logo justify-content-center text-white mb-2 fs-3">
                            <i class="fa-solid fa-user-plus"></i> ??ng K? T?i Kho?n
                        </div>
                        <p class="mb-0 small opacity-75">T?o t?i kho?n mua h?ng &amp; n?p ti?n t? ??ng</p>
                    </div>

                    <div class="card-body p-4 p-md-5">
                        {error_html}

                        <form method="POST" action="/register" id="registerForm">
                            <input type="hidden" name="next" value="{html.escape(next)}">

                            <div class="mb-3">
                                <label for="regUsername" class="form-label fw-bold small text-muted">T?n ??ng nh?p (Username):</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0"><i class="fa-solid fa-user text-purple"></i></span>
                                    <input type="text" class="form-control border-start-0" id="regUsername" name="username" placeholder="V? d?: truongmmo99" required minlength="3" maxlength="30" autofocus>
                                </div>
                                <div class="form-text small">T? 3-30 k? t?, kh?ng d?u, kh?ng kho?ng tr?ng.</div>
                            </div>

                            <div class="mb-3">
                                <label for="regPassword" class="form-label fw-bold small text-muted">M?t kh?u:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0"><i class="fa-solid fa-lock text-purple"></i></span>
                                    <input type="password" class="form-control border-start-0" id="regPassword" name="password" placeholder="T?i thi?u 6 k? t?" required minlength="6">
                                </div>
                            </div>

                            <div class="mb-3">
                                <label for="regConfirmPassword" class="form-label fw-bold small text-muted">Nh?p l?i m?t kh?u:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0"><i class="fa-solid fa-lock-open text-purple"></i></span>
                                    <input type="password" class="form-control border-start-0" id="regConfirmPassword" name="confirm_password" placeholder="X?c nh?n l?i m?t kh?u" required minlength="6">
                                </div>
                            </div>

                            <div class="mb-4">
                                <label for="regTelegramId" class="form-label fw-bold small text-muted">
                                    Telegram ID <span class="badge bg-light text-muted border">T?y ch?n</span>:
                                </label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light border-end-0"><i class="fa-brands fa-telegram text-purple"></i></span>
                                    <input type="text" class="form-control border-start-0" id="regTelegramId" name="telegram_id" placeholder="Nh?p ID bot ?? ??ng b? s? d?">
                                </div>
                                <div class="form-text small text-muted">
                                    <i class="fa-solid fa-link me-1 text-purple"></i> Nh?p Telegram ID c?a b?n ?? <strong>??ng b? ngay s? d?</strong> ?ang c? tr?n Bot sang Web!
                                </div>
                            </div>

                            <button type="submit" class="btn btn-purple w-100 py-3 fw-bold rounded-3 shadow-sm mb-3">
                                <i class="fa-solid fa-user-check me-2"></i> ??ng k? t?i kho?n
                            </button>
                        </form>

                        <div class="text-center small text-muted">
                            ?? c? t?i kho?n? <a href="/login?next={html.escape(next)}" class="text-purple fw-bold text-decoration-none">??ng nh?p t?i ??y</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return HTMLResponse(content=render_base_layout(
        title="??ng k? t?i kho?n - Bubba Gump Clone Shop",
        body_content=content,
        active_nav="register",
        user=None,
        balance=0.0,
        is_admin=False,
        categories=categories
    ))


@web_router.post("/register")
async def web_register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    telegram_id: Optional[str] = Form(None),
    next: str = Form("/")
):
    clean_un = username.strip()
    clean_pw = password.strip()
    clean_cpw = confirm_password.strip()
    target_url = next if next and next.startswith("/") else "/"

    if len(clean_un) < 3 or len(clean_un) > 30:
        return RedirectResponse(url=f"/register?error=T%C3%AAn%20%C4%91%C4%83ng%20nh%E1%BA%ADp%20ph%E1%BA%A3i%20t%E1%BB%AB%203%20%C4%91%E1%BA%BFn%2030%20k%C3%BD%20t%E1%BB%B1&next={quote(target_url)}", status_code=302)

    if len(clean_pw) < 6:
        return RedirectResponse(url=f"/register?error=M%E1%BA%ADt%20kh%E1%BA%A9u%20ph%E1%BA%A3i%20c%C3%B3%20%C3%ADt%20nh%E1%BA%A5t%206%20k%C3%BD%20t%E1%BB%B1&next={quote(target_url)}", status_code=302)

    if clean_pw != clean_cpw:
        return RedirectResponse(url=f"/register?error=M%E1%BA%ADt%20kh%E1%BA%A9u%20x%C3%A1c%20nh%E1%BA%ADn%20kh%C3%B4ng%20kh%E1%BB%9Bp&next={quote(target_url)}", status_code=302)

    async with get_db_session() as session:
        # Ki?m tra tr?ng username
        stmt_chk = select(User).where(or_(User.web_username == clean_un, User.telegram_username == clean_un))
        existing_user = (await session.execute(stmt_chk)).scalar_one_or_none()
        if existing_user and existing_user.web_username == clean_un:
            return RedirectResponse(url=f"/register?error=T%C3%AAn%20%C4%91%C4%83ng%20nh%E1%BA%ADp%20%C4%91%C3%A3%20t%E1%BB%93n%20t%E1%BA%A1i,%20vui%20l%C3%B2ng%20ch%E1%BB%8Dn%20t%C3%AAn%20kh%C3%A1c&next={quote(target_url)}", status_code=302)

        # X? l? Telegram ID n?u c?
        tid_val = None
        if telegram_id and telegram_id.strip():
            tid_str = telegram_id.strip()
            if tid_str.isdigit():
                tid_val = int(tid_str)
                stmt_tg = select(User).where(User.telegram_id == tid_val)
                tg_user = (await session.execute(stmt_tg)).scalar_one_or_none()
                if tg_user:
                    # Li?n k?t t?i kho?n bot s?n c?
                    tg_user.web_username = clean_un
                    tg_user.password_hash = hash_password(clean_pw)
                    await session_commit(session)
                    is_user_admin = (tg_user.telegram_id in config.ADMIN_ID_LIST)
                    request.session["web_user"] = {
                        "id": tg_user.id,
                        "username": clean_un,
                        "is_admin": is_user_admin
                    }
                    return RedirectResponse(url=target_url, status_code=302)

        # T?o t?i kho?n m?i
        new_user = User(
            web_username=clean_un,
            password_hash=hash_password(clean_pw),
            telegram_id=tid_val,
            top_up_amount=0.0,
            consume_records=0.0
        )
        session.add(new_user)
        await session_commit(session)

        request.session["web_user"] = {
            "id": new_user.id,
            "username": clean_un,
            "is_admin": False
        }
        return RedirectResponse(url=target_url, status_code=302)


@web_router.get("/logout")
async def web_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)

