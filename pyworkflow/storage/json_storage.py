"""Local JSON-file based storage backend.

Layout on disk (default root: ``~/.pyworkflow``)::

    <root>/
        workflows/<name>.json      # latest snapshot of the workflow definition
        history/<name>.jsonl       # one JSON object per line, one per run
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from pyworkflow.exceptions import StorageError
from pyworkflow.storage.base import StorageBackend

import os


class JSONStorage(StorageBackend):
    def __init__(self, root: Optional[str] = None) -> None:
        if root:
            self.root = Path(root)
        else:
            self.root = (
                Path(os.environ.get("HOME", os.path.expanduser("~"))) / ".pyworkflow"
            )
        self.workflows_dir = self.root / "workflows"
        self.history_dir = self.root / "history"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _workflow_path(self, name: str) -> Path:
        return self.workflows_dir / f"{_safe_filename(name)}.json"

    def _history_path(self, name: str) -> Path:
        return self.history_dir / f"{_safe_filename(name)}.jsonl"

    def save_workflow(self, workflow_dict: dict) -> None:
        name = workflow_dict.get("name")
        if not name:
            raise StorageError("workflow_dict must contain a 'name' key")
        try:
            self._workflow_path(name).write_text(
                json.dumps(workflow_dict, indent=2, default=str)
            )
        except OSError as exc:
            raise StorageError(f"Failed to save workflow '{name}': {exc}") from exc

    def save_run(self, workflow_name: str, report_dict: dict) -> None:
        record = {"timestamp": time.time(), **report_dict}
        try:
            with self._history_path(workflow_name).open("a") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            raise StorageError(
                f"Failed to save run history for '{workflow_name}': {exc}"
            ) from exc

    def get_workflow(self, name: str) -> Optional[dict]:
        path = self._workflow_path(name)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list_workflows(self) -> list[str]:
        return sorted(p.stem for p in self.workflows_dir.glob("*.json"))

    def get_history(self, workflow_name: str) -> list[dict]:
        path = self._history_path(workflow_name)
        if not path.exists():
            return []
        records = []
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def delete_workflow(self, name: str) -> None:
        wf_path = self._workflow_path(name)
        hist_path = self._history_path(name)
        if wf_path.exists():
            wf_path.unlink()
        if hist_path.exists():
            hist_path.unlink()


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
