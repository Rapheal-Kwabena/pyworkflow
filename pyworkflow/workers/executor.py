"""ProcessExecutor that manages concurrent process-based task executions."""

from __future__ import annotations

import concurrent.futures
from typing import Any, Callable, Iterable


class ProcessExecutor:
    """Manages execution of multiple process-isolated tasks concurrently."""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    def execute_tasks(
        self, run_fn: Callable[[str], Any], task_names: Iterable[str]
    ) -> dict[str, Any]:
        """Execute multiple tasks in parallel using a pool of runner threads

        that manage subprocess execution.
        """
        outcomes: dict[str, Any] = {}
        task_names_list = list(task_names)
        limit = min(self.max_workers, len(task_names_list))
        if limit <= 0:
            return outcomes

        with concurrent.futures.ThreadPoolExecutor(max_workers=limit) as pool:
            future_map = {
                pool.submit(run_fn, name): name for name in task_names_list
            }
            for future in concurrent.futures.as_completed(future_map):
                name = future_map[future]
                try:
                    outcomes[name] = future.result()
                except Exception as exc:
                    outcomes[name] = (False, exc)
        return outcomes
