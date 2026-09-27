"""Structured, privacy-conscious logging for HealthSetu."""

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# Context variable to hold the request ID for the current async task
request_id_ctx_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

# Sensitive keys that must NEVER appear in logs
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset({
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "session",
    # Healthcare clinical data safeguards
    "diagnosis",
    "diagnoses",
    "prescription",
    "prescriptions",
    "medication",
    "medications",
    "history",
    "medical_history",
    "clinical_notes",
    "payload",
    "document_content",
    "patient_data",
})


from app.core.log_sanitizer import sanitize_for_log, _EXACT_SENSITIVE_KEYS

def sanitize_log_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize dictionary to redact sensitive or clinical data."""
    return sanitize_for_log(d)


class StructuredJsonFormatter(logging.Formatter):
    """Custom logging formatter that outputs clean, standardized JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        # Retrieve request_id from contextvar or record attribute
        req_id = getattr(record, "request_id", None) or request_id_ctx_var.get()

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if req_id:
            log_data["request_id"] = req_id

        # Attach HTTP context, security event metadata, and extra attributes
        _STANDARD_ATTRS = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "asctime", "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in log_data:
                log_data[key] = val

        # Handle exception information safely
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_data["exception"] = record.exc_text

        # Sanitize entire log data before JSON serializing
        sanitized_data = sanitize_log_dict(log_data)
        return json.dumps(sanitized_data, default=str)


class DevelopmentConsoleFormatter(logging.Formatter):
    """Readable colored or formatted log output for local development."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or request_id_ctx_var.get()
        req_str = f" [{req_id}]" if req_id else ""
        base = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} | {record.levelname:<7} | {record.name}{req_str} - {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(log_level: str = "INFO", is_production: bool = False) -> None:
    """Configure structured logging for the application and standard libraries."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter: logging.Formatter
    if is_production:
        formatter = StructuredJsonFormatter()
    else:
        # Structured JSON can be used in dev if requested, but default to clean dev or json
        # Section 10 states: "Use structured logging... Every request log should contain useful metadata"
        formatter = StructuredJsonFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)

    # Intercept uvicorn loggers so they format identically
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvicorn_logger_name)
        u_logger.handlers = [handler]
        u_logger.propagate = False
        u_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a standard logger for the given name."""
    return logging.getLogger(name)
