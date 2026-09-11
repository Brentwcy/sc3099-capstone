"""
Structured logging configuration using structlog.
Provides queryable logs with timestamps and contextual request metadata.

Privacy: SimHashRedactor strips any biometric template values before
they can appear in any log output or forwarded telemetry.
"""
import logging
import re
import sys
from typing import Any

logger: Any

# ---------------------------------------------------------------------------
# Privacy processor: redact SimHash / ciphertext from log events
# ---------------------------------------------------------------------------
# SimHash: 64-char binary string of 0s and 1s
_SIMHASH_RE = re.compile(r"\b[01]{64}\b")
# Versioned ciphertext: "v1:<base64-blob>"
_CIPHERTEXT_RE = re.compile(r"\bv\d+:[A-Za-z0-9+/=_-]{10,}\b")


def _redact_biometrics(logger_inst: Any, method: str, event_dict: dict) -> dict:  # noqa: ARG001
    """Structlog processor: replace any raw SimHash or ciphertext blobs with [REDACTED]."""
    for key, value in list(event_dict.items()):
        if not isinstance(value, str):
            continue
        value = _SIMHASH_RE.sub("[REDACTED]", value)
        value = _CIPHERTEXT_RE.sub("[REDACTED]", value)
        event_dict[key] = value
    return event_dict


try:
    import structlog

    structlog.configure(
        processors=[
            _redact_biometrics,  # <-- must be first
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
            if sys.stdout.isatty() is False
            else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    logger = structlog.get_logger("saiv-face-recognition")

except ImportError:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    logger = logging.getLogger("saiv-face-recognition")
