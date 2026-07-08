"""Centralised logging configuration for the EKS automation package."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def configure_logging(level: str | int = "INFO") -> None:
    """Configure root logging once with a consistent, human-readable format.

    Repeated calls are idempotent: only the effective level is updated after the
    first invocation, so importing modules cannot accumulate duplicate handlers.

    Args:
        level: Log level as a name (``"INFO"``) or numeric value.
    """
    global _configured

    if isinstance(level, str):
        level = logging.getLevelName(level.upper())

    if not _configured:
        logging.basicConfig(level=level, format=_LOG_FORMAT, datefmt=_DATE_FORMAT)
        _configured = True
    else:
        logging.getLogger().setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a package logger, ensuring logging has been configured.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger`.
    """
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
