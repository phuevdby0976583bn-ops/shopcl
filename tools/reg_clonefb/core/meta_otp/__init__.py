# -*- coding: utf-8 -*-
"""
core.meta_otp
Modular Meta AI Auto OTP automation engine.
Provides API-based and Selenium-based OTP triggering for phone numbers.
"""

from core.meta_otp.service import MetaOtpService, MetaOtpResult
from core.meta_otp.phone_loader import read_numbers, clean_and_validate
from core.meta_otp.user_agents import (
    USER_AGENT_PROFILES,
    get_user_agent_by_profile,
    get_random_user_agent,
)
from core.meta_otp.proxy_tunnel import LocalProxyTunnel, create_proxy_tunnel
from core.meta_otp.token_extractor import extract_tokens

__all__ = [
    "MetaOtpService",
    "MetaOtpResult",
    "read_numbers",
    "clean_and_validate",
    "USER_AGENT_PROFILES",
    "get_user_agent_by_profile",
    "get_random_user_agent",
    "LocalProxyTunnel",
    "create_proxy_tunnel",
    "extract_tokens",
]
