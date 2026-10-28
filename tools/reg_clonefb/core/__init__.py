# -*- coding: utf-8 -*-
"""
Core automation framework package following Clean Architecture.
Integrates legacy & modern Facebook account registration workflows.
"""

from core.models import ProxyItem, RegistrationInput, RegistrationResult
from core.http_client import (
    HttpClient,
    HttpClientError,
    ProxyConnectionError,
    RequestTimeoutError,
    DEVICE_TLS_MAPPING,
)
from core.proxy_manager import (
    ProxyManager,
    KiotProxyClient,
    ProxySocks5Client,
    MproxyClient,
    ProxyVNClient,
    FreeProxyManager,
    format_proxy_for_requests,
    get_proxy_list,
    create_proxy_cycle,
    get_no_proxy_data,
    parse_proxy,
    get_ip_info,
    build_proxy_data,
)
from core.session_builder import create_http_session, setup_session_cookies, build_request_context
from core.registration_service import RegistrationService, bind_facebook_session_email, bind_facebook_session_contactpoint, trigger_facebook_confirmation_resend, retrieve_and_verify_otp, register_via_legacy_web, create_worker, _save_success_output, generate_identity
from core.batch_runner import BatchRunner, BatchSummary, run_batch
from core.name_manager import NameManager, GeneratedName
from core.counter import Counter
from core.device_manager import select_device, select_browser, select_server, SERVER_MAP
from core.worker_manager import get_worker_count
from core.password_manager import select_password_config, generate_random_password, get_password
from core.number_manager import (
    process_file_input,
    load_numbers,
    remove_number,
    get_next_number,
    save_numbers,
    extract_from_excel,
    get_number_list_filepath,
)
from core.path_manager import (
    is_termux_or_mobile,
    get_base_storage_dir,
    get_output_dir,
    get_output_filepaths,
)
from core.settings_manager import load_settings
from core.email_service import (
    EmailAccount,
    OTPVerificationResult,
    BaseEmailProvider,
    MailTmProvider,
    GuerrillaMailProvider,
    DongVanEmailProvider,
    DongVanHotmailProvider,
    Smail1sHotmailProvider,
    HotmailAccountManager,
    remove_hotmail,
    KopeechkaEmailProvider,
    get_email_provider,
    extract_otp_code,
    submit_facebook_web_email_otp,
)
from core.nvr_verifier import SmartAccountParser, verify_single_nvr_account
from core.facebook_checker import (
    check_facebook_uid_live,
    batch_check_facebook_uids,
    check_registration_account_live,
)

__all__ = [
    "ProxyItem",
    "RegistrationInput",
    "RegistrationResult",
    "HttpClient",
    "HttpClientError",
    "ProxyConnectionError",
    "RequestTimeoutError",
    "DEVICE_TLS_MAPPING",
    "ProxyManager",
    "KiotProxyClient",
    "ProxySocks5Client",
    "MproxyClient",
    "ProxyVNClient",
    "FreeProxyManager",
    "format_proxy_for_requests",
    "get_proxy_list",
    "create_proxy_cycle",
    "get_no_proxy_data",
    "parse_proxy",
    "get_ip_info",
    "build_proxy_data",
    "create_http_session",
    "setup_session_cookies",
    "build_request_context",
    "RegistrationService",
    "bind_facebook_session_email",
    "bind_facebook_session_contactpoint",
    "trigger_facebook_confirmation_resend",
    "retrieve_and_verify_otp",
    "register_via_legacy_web",
    "create_worker",
    "_save_success_output",
    "generate_identity",
    "BatchRunner",
    "BatchSummary",
    "run_batch",
    "NameManager",
    "GeneratedName",
    "Counter",
    "select_device",
    "select_browser",
    "select_server",
    "SERVER_MAP",
    "get_worker_count",
    "select_password_config",
    "generate_random_password",
    "get_password",
    "process_file_input",
    "load_numbers",
    "remove_number",
    "get_next_number",
    "save_numbers",
    "extract_from_excel",
    "get_number_list_filepath",
    "is_termux_or_mobile",
    "get_base_storage_dir",
    "get_output_dir",
    "get_output_filepaths",
    "load_settings",
    "EmailAccount",
    "OTPVerificationResult",
    "BaseEmailProvider",
    "MailTmProvider",
    "GuerrillaMailProvider",
    "DongVanEmailProvider",
    "DongVanHotmailProvider",
    "Smail1sHotmailProvider",
    "HotmailAccountManager",
    "remove_hotmail",
    "KopeechkaEmailProvider",
    "get_email_provider",
    "extract_otp_code",
    "submit_facebook_web_email_otp",
    "check_facebook_uid_live",
    "batch_check_facebook_uids",
    "check_registration_account_live",
    "SmartAccountParser",
    "verify_single_nvr_account",
]

from core.meta_otp import MetaOtpService, MetaOtpResult
__all__.extend(["MetaOtpService", "MetaOtpResult"])
