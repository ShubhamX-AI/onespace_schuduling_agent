# Copyright (c) 2026 Indus Net Technologies Private Limited
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""Tests for logging configuration."""

import logging

from src.core.logging.logger import configure_logging, get_logger


def test_configure_logging_sets_root_level() -> None:
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_default_is_info() -> None:
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_adds_console_handler() -> None:
    configure_logging("INFO")
    handlers = [h for h in logging.getLogger().handlers]
    assert handlers, "root logger should have a handler"


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("src.scheduling.jobs")
    assert logger.name == "src.scheduling.jobs"
    assert isinstance(logger, logging.Logger)
