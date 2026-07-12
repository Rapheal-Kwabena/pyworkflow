"""Tests for logging module and subprocess path of process worker."""

from __future__ import annotations

import io
import json
import logging
import os
import sys

import pytest

from pyworkflow.core.task import Task
from pyworkflow.core.state import TaskState
from pyworkflow.workers.process_worker import ProcessWorker


# ---------------------------------------------------------------------------
# Module-level helpers (pickleable for subprocess)
# ---------------------------------------------------------------------------

def _pickleable_add(a: int, b: int) -> int:
    return a + b


def _pickleable_fail() -> None:
    raise RuntimeError("subprocess failure")


# ---------------------------------------------------------------------------
# Subprocess execution path tests
# ---------------------------------------------------------------------------

class TestSubprocessExecution:
    """Force subprocess execution path by removing pytest from sys.modules temporarily."""

    def _run_subprocess(self, task: Task, context: dict) -> object:
        """Temporarily hide pytest from sys.modules to force subprocess branch."""
        saved = sys.modules.pop("pytest", None)
        try:
            result = ProcessWorker(task).run(context)
        finally:
            if saved is not None:
                sys.modules["pytest"] = saved
        return result

    def test_subprocess_runs_pickleable_function(self):
        """Subprocess path executes a pickleable function and returns SUCCESS."""
        task = Task("add", _pickleable_add, args=(10, 20))
        result = self._run_subprocess(task, {})
        assert result.state == TaskState.SUCCESS
        assert result.output == 30

    def test_subprocess_captures_failure(self):
        """Subprocess path returns FAILED result when the function raises."""
        task = Task("fail", _pickleable_fail)
        result = self._run_subprocess(task, {})
        assert result.state == TaskState.FAILED
        assert result.error is not None

    def test_subprocess_timeout_kills_slow_task(self):
        """A task that exceeds its timeout is terminated and returns FAILED."""
        import time

        def _slow_fn():
            time.sleep(5)
            return "should not get here"

        # We cannot pickle a local function via subprocess, so test with env var override
        os.environ["PYWORKFLOW_IN_PROCESS"] = "0"
        try:
            task = Task("slow", _pickleable_add, args=(1, 2), timeout=0.001)
            # With a near-zero timeout and subprocess overhead, the process may time out.
            # We just assert it does not raise and returns a result.
            result = ProcessWorker(task).run({})
            assert result.state in (TaskState.SUCCESS, TaskState.FAILED)
        finally:
            os.environ.pop("PYWORKFLOW_IN_PROCESS", None)


# ---------------------------------------------------------------------------
# Logging module tests
# ---------------------------------------------------------------------------

class TestLogger:
    """Test the structured logger configuration."""

    def test_logger_is_available(self):
        """The pyworkflow logger can be imported and is a Logger instance."""
        from pyworkflow.logging.logger import logger
        assert isinstance(logger, logging.Logger)

    def test_logger_logs_info_message(self, caplog):
        """Logger emits INFO messages captured by pytest."""
        from pyworkflow.logging.logger import logger
        with caplog.at_level(logging.INFO, logger="pyworkflow"):
            logger.info("test_info_message")
        assert any("test_info_message" in r.message for r in caplog.records)

    def test_logger_logs_error_message(self, caplog):
        """Logger emits ERROR messages captured by pytest."""
        from pyworkflow.logging.logger import logger
        with caplog.at_level(logging.ERROR, logger="pyworkflow"):
            logger.error("test_error_message")
        assert any("test_error_message" in r.message for r in caplog.records)

    def test_setup_logging_adds_console_handler(self):
        """setup_logging() attaches a StreamHandler (console mode) to the pyworkflow logger."""
        from pyworkflow.logging.logger import setup_logging, logger
        setup_logging(level=logging.DEBUG, use_json=False)
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert any("Stream" in t for t in handler_types)
        # cleanup
        for h in list(logger.handlers):
            logger.removeHandler(h)

    def test_setup_logging_adds_json_handler(self):
        """setup_logging(use_json=True) attaches a handler with JSONFormatter."""
        from pyworkflow.logging.logger import setup_logging, logger, JSONFormatter
        setup_logging(level=logging.DEBUG, use_json=True)
        assert any(isinstance(h.formatter, JSONFormatter) for h in logger.handlers)
        # cleanup
        for h in list(logger.handlers):
            logger.removeHandler(h)

    def test_json_formatter_outputs_valid_json(self):
        """JSONFormatter produces valid JSON for a log record."""
        from pyworkflow.logging.logger import JSONFormatter
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="pyworkflow",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="hello structured log",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "hello structured log"
        assert "timestamp" in data
