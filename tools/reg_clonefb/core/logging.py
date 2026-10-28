"""Structured logging helpers that redact known credential fields."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


SENSITIVE_FIELDS = {
    "password",
    "pass",
    "cookie",
    "token",
    "access_token",
    "session",
    "session_token",
    "proxy_password",
    "two_factor_secret",
    "2fa",
}


def redact_fields(values: Dict[str, Any]) -> Dict[str, Any]:
    redacted = {}
    for key, value in values.items():
        normalized = key.lower().replace("-", "_")
        redacted[key] = "***" if normalized in SENSITIVE_FIELDS else value
    return redacted


@dataclass(frozen=True)
class LogRecord:
    timestamp: str
    level: str
    message: str
    account: Optional[str] = None
    worker: Optional[str] = None
    job: Optional[str] = None
    error_type: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data["context"] is not None:
            data["context"] = redact_fields(data["context"])
        return data


def create_log_record(
    level: str,
    message: str,
    *,
    account: Optional[str] = None,
    worker: Optional[str] = None,
    job: Optional[str] = None,
    error: Optional[BaseException] = None,
    context: Optional[Dict[str, Any]] = None,
) -> LogRecord:
    return LogRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        level=level.upper(),
        message=message,
        account=account,
        worker=worker,
        job=job,
        error_type=type(error).__name__ if error else None,
        context=redact_fields(context or {}),
    )
