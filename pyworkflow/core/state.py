"""State definitions for tasks and workflows inside PyWorkflow."""

from enum import Enum


class TaskState(str, Enum):
    """Lifecycle states a single task can be in."""

    CREATED = "CREATED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    COMPLETED = "SUCCESS"  # legacy alias
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class WorkflowState(str, Enum):
    """Lifecycle states a workflow can be in."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
