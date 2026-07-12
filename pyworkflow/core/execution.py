"""Execution metadata and reports for PyWorkflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecutionReport:
    """Summary of a single workflow execution."""

    success: bool
    results: dict = field(default_factory=dict)
    error: Optional[Exception] = None
    failed_tasks: list = field(default_factory=list)
    skipped_tasks: list = field(default_factory=list)
