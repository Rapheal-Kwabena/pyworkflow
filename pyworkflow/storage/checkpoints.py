"""State checkpointing manager to save progress and resume workflows."""

from __future__ import annotations

import base64
import pickle
from typing import TYPE_CHECKING, Any

from pyworkflow.core.state import TaskState

if TYPE_CHECKING:
    from pyworkflow.core.workflow import Workflow
    from pyworkflow.storage.database import StorageBackend


def serialize_value(val: Any) -> dict[str, str]:
    """Serialize a Python value to a JSON-safe dictionary using pickle + base64."""
    try:
        pickled = pickle.dumps(val)
        return {
            "__type__": "pickle",
            "data": base64.b64encode(pickled).decode("ascii"),
        }
    except Exception:
        return {"__type__": "repr", "data": repr(val)}


def deserialize_value(payload: Any) -> Any:
    """Deserialize a JSON-safe dictionary back to its original Python value."""
    if isinstance(payload, dict) and "__type__" in payload:
        if payload["__type__"] == "pickle":
            try:
                pickled = base64.b64decode(payload["data"].encode("ascii"))
                return pickle.loads(pickled)
            except Exception:
                return payload["data"]
        return payload["data"]
    return payload


class CheckpointManager:
    """Saves workflow state and recovers task states and outputs to resume runs."""

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    def save_checkpoint(self, workflow: Workflow) -> None:
        """Serialize and save the current state of the workflow and its tasks."""
        tasks_data = []
        for task in workflow.tasks.values():
            tasks_data.append(
                {
                    "name": task.name,
                    "state": task.state.value,
                    "output": serialize_value(task.output),
                    "error": task.error,
                    "attempts": task.attempts,
                    "started_at": task.started_at,
                    "finished_at": task.finished_at,
                }
            )

        checkpoint_data = {
            "name": workflow.name,
            "state": workflow.state.value,
            "created_at": workflow.created_at,
            "started_at": workflow.started_at,
            "finished_at": workflow.finished_at,
            "pid": workflow.pid,
            "tasks": tasks_data,
            "context": {k: serialize_value(v) for k, v in workflow.context.items()},
        }
        self.storage.save_workflow(checkpoint_data)

    def load_checkpoint(self, workflow: Workflow) -> bool:
        """Load and apply saved task states and outputs for completed tasks."""
        data = self.storage.get_workflow(workflow.name)
        if not data:
            return False

        # Apply saved status and outputs to matching tasks
        for task_data in data.get("tasks", []):
            task_name = task_data.get("name")
            if task_name in workflow.tasks:
                task = workflow.tasks[task_name]
                state_str = task_data.get("state")

                # Restore completed tasks
                if state_str in (TaskState.COMPLETED.value, TaskState.SUCCESS.value):
                    task.state = TaskState.COMPLETED
                    task.output = deserialize_value(task_data.get("output"))
                    task.attempts = task_data.get("attempts", 1)
                    task.started_at = task_data.get("started_at")
                    task.finished_at = task_data.get("finished_at")
                    task.error = None
                    # Populate output in the workflow context
                    workflow.context[task_name] = task.output
                elif state_str == TaskState.FAILED.value:
                    # Let the engine know it failed previously but don't skip running
                    task.state = TaskState.FAILED
                    task.error = task_data.get("error")
                    task.attempts = task_data.get("attempts", 1)

        # Restore contextual values
        context_data = data.get("context", {})
        for k, v in context_data.items():
            workflow.context[k] = deserialize_value(v)

        return True
