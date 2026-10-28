# -*- coding: utf-8 -*-
"""
automation.create_task
Refactored RegistrationService (Clean Architecture) for web/mobile Facebook account creation.
Decoupled from UI, terminal colors, and global counters.
Fully centralized in core.registration_service.
"""

from core.registration_service import (
    RegistrationService,
    create_worker,
    _save_success_output,
    _search,
    generate_identity,
    SERVER_MAP,
    LEGACY_DEVICE_TYPES,
)

__all__ = [
    "RegistrationService",
    "create_worker",
    "_save_success_output",
    "_search",
    "generate_identity",
    "SERVER_MAP",
    "LEGACY_DEVICE_TYPES",
]
