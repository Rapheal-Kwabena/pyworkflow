"""Custom exception hierarchy used throughout PyWorkflow."""

from __future__ import annotations


class PyWorkflowError(Exception):
    """Base class for all PyWorkflow errors."""


class TaskError(PyWorkflowError):
    """Base class for task-related errors."""


class TaskExecutionError(TaskError):
    """Raised when a task's function raises an exception during execution."""

    def __init__(self, task_name: str, original_exception: BaseException) -> None:
        self.task_name = task_name
        self.original_exception = original_exception
        super().__init__(
            f"Task '{task_name}' failed with "
            f"{type(original_exception).__name__}: {original_exception}"
        )


class TaskTimeoutError(TaskError):
    """Raised when a task exceeds its configured timeout."""

    def __init__(self, task_name: str, timeout: float) -> None:
        self.task_name = task_name
        self.timeout = timeout
        super().__init__(f"Task '{task_name}' timed out after {timeout} seconds")


class DependencyError(PyWorkflowError):
    """Raised when task dependencies are invalid (missing or cyclic)."""


class WorkflowError(PyWorkflowError):
    """Base class for workflow-related errors."""


class WorkflowStateError(WorkflowError):
    """Raised when an operation is attempted in an invalid workflow state."""


class SchedulerError(PyWorkflowError):
    """Base class for scheduler-related errors."""


class StorageError(PyWorkflowError):
    """Base class for storage backend errors."""
