"""PyWorkflow: a lightweight Python workflow automation framework.

Example:
    >>> from pyworkflow import workflow, task
    >>>
    >>> @task
    ... def hello():
    ...     return "hello"
    >>>
    >>> flow = workflow("My Flow")
    >>> flow.add(hello)
    >>> flow.run()
"""

from pyworkflow.core.engine import Engine
from pyworkflow.core.execution import ExecutionReport
from pyworkflow.core.task import Task, TaskResult
from pyworkflow.core.state import TaskState, WorkflowState
from pyworkflow.core.workflow import Workflow
from pyworkflow.decorators.task import task
from pyworkflow.exceptions import (
    DependencyError,
    PyWorkflowError,
    SchedulerError,
    StorageError,
    TaskError,
    TaskExecutionError,
    TaskTimeoutError,
    WorkflowError,
    WorkflowStateError,
)

# Export workflow as a factory/alias for Workflow class
workflow = Workflow

__version__ = "0.1.0"

__all__ = [
    "Workflow",
    "workflow",
    "task",
    "WorkflowState",
    "Task",
    "TaskState",
    "TaskResult",
    "Engine",
    "ExecutionReport",
    "PyWorkflowError",
    "TaskError",
    "TaskExecutionError",
    "TaskTimeoutError",
    "DependencyError",
    "WorkflowError",
    "WorkflowStateError",
    "SchedulerError",
    "StorageError",
    "__version__",
]
