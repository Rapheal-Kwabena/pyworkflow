"""Abstract storage backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class StorageBackend(ABC):
    """Interface all PyWorkflow storage backends must implement."""

    @abstractmethod
    def save_workflow(self, workflow_dict: dict) -> None:
        """Persist a workflow definition/snapshot."""

    @abstractmethod
    def save_run(self, workflow_name: str, report_dict: dict) -> None:
        """Persist the result of a single execution ('run') of a workflow."""

    @abstractmethod
    def get_workflow(self, name: str) -> Optional[dict]:
        """Fetch the most recently saved snapshot of a workflow by name."""

    @abstractmethod
    def list_workflows(self) -> list[str]:
        """List all known workflow names."""

    @abstractmethod
    def get_history(self, workflow_name: str) -> list[dict]:
        """Return all recorded runs for a workflow, oldest first."""

    @abstractmethod
    def delete_workflow(self, name: str) -> None:
        """Remove a workflow and its run history."""

    def save(self, filename: str, data: dict) -> None:
        """Compatibility wrapper to save a workflow with a filename."""
        import json

        if hasattr(self, "workflows_dir"):
            path = getattr(self, "workflows_dir") / filename
            try:
                path.write_text(json.dumps(data, indent=2, default=str))
                return
            except OSError:
                pass
        name = filename[:-5] if filename.endswith(".json") else filename
        if "name" not in data:
            data = {"name": name, **data}
        self.save_workflow(data)

    def load(self, filename: str) -> Optional[dict]:
        """Compatibility wrapper to load a workflow with a filename."""
        import json

        if hasattr(self, "workflows_dir"):
            path = getattr(self, "workflows_dir") / filename
            if path.exists():
                try:
                    return json.loads(path.read_text())
                except json.JSONDecodeError:
                    pass
        name = filename[:-5] if filename.endswith(".json") else filename
        return self.get_workflow(name)
