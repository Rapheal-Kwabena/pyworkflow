"""Base Worker class definition."""

from abc import ABC, abstractmethod
from typing import Any
from pyworkflow.core.task import Task, TaskResult


class Worker(ABC):
    """Abstract base worker responsible for running tasks."""

    def __init__(self, task: Task) -> None:
        self.task = task

    @abstractmethod
    def run(self, context: dict[str, Any]) -> TaskResult:
        """Run the task and return its result."""
        pass
