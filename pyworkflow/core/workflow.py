"""The Workflow class: PyWorkflow's main user-facing API."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional, TYPE_CHECKING

from pyworkflow.core.engine import Engine, ExecutionReport
from pyworkflow.core.task import Task
from pyworkflow.core.state import TaskState, WorkflowState
from pyworkflow.exceptions import DependencyError, WorkflowStateError

if TYPE_CHECKING:
    from pyworkflow.storage.base import StorageBackend

_default_scheduler = None  # lazily-created shared pyworkflow.scheduler.Scheduler


class Workflow:
    """A named, ordered collection of :class:`~pyworkflow.core.task.Task`.

    Example
    -------
    >>> wf = Workflow("Data Processing")
    >>> wf.add_task(Task("Download", download_fn))
    >>> wf.add_task(Task("Clean", clean_fn, depends_on=["Download"]))
    >>> report = wf.run()
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        max_workers: int = 4,
        stop_on_failure: bool = True,
        storage: Optional[StorageBackend] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.max_workers = max_workers
        self.stop_on_failure = stop_on_failure
        self.storage = storage

        self.tasks: dict[str, Task] = {}
        self._order: list[str] = []
        self.state: WorkflowState = WorkflowState.CREATED
        self.context: dict[str, Any] = {}
        self.created_at: float = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.pid: Optional[int] = None
        self._engine = Engine(self)
        self._on_complete: list[Callable[["Workflow"], None]] = []
        self._on_failure: list[Callable[["Workflow", Exception], None]] = []

    # -- composition -----------------------------------------------------
    def add_task(self, task: Task) -> "Workflow":
        """Add a task to the workflow. Returns self for chaining."""
        if task.name in self.tasks:
            raise ValueError(f"A task named '{task.name}' already exists")
        for dep in task.depends_on:
            if dep not in self.tasks and dep != task.name:
                # Dependency may be added later; validated fully at run() time.
                pass
        self.tasks[task.name] = task
        self._order.append(task.name)
        return self

    def add(self, task_or_func: Any, auto_chain: bool = True) -> "Workflow":
        """Add a task or a decorated task function to the workflow.

        If auto_chain is True and the task doesn't have any depends_on specified
        and there is already a task in the workflow, it automatically depends on
        the last added task.
        """
        if isinstance(task_or_func, Task):
            task = task_or_func
        elif hasattr(task_or_func, "get_task"):
            task = task_or_func.get_task()
        elif callable(task_or_func):
            task = Task(name=task_or_func.__name__, function=task_or_func)
        else:
            raise TypeError("Expected Task, decorated task, or callable")

        if auto_chain and not task.depends_on and self._order:
            task.depends_on.append(self._order[-1])
        self.add_task(task)
        return self

    def add_tasks(self, tasks: list[Task]) -> "Workflow":
        for t in tasks:
            self.add_task(t)
        return self

    def then(self, task: Task) -> "Workflow":
        """Chain a task after the most recently added task (convenience for
        sequential workflow construction)."""
        if self._order:
            last = self._order[-1]
            if last not in task.depends_on:
                task.depends_on.append(last)
        self.add_task(task)
        return self

    def chain(self, other: "Workflow") -> "Workflow":
        """Chain another workflow's tasks after this one's, returning a new
        combined Workflow. Task dependencies from `other` are preserved, and
        `other`'s originally-independent tasks are additionally made
        dependent on this workflow's final task(s)."""
        combined = Workflow(
            f"{self.name} -> {other.name}",
            stop_on_failure=self.stop_on_failure,
            max_workers=self.max_workers,
        )
        for name in self._order:
            combined.add_task(self.tasks[name])
        tail = self._terminal_task_names()
        for name in other._order:
            task = other.tasks[name]
            if not task.depends_on:
                task.depends_on = list(tail)
            combined.add_task(task)
        return combined

    def _terminal_task_names(self) -> list[str]:
        """Tasks that nothing else in this workflow depends on."""
        depended_on: set[str] = set()
        for t in self.tasks.values():
            depended_on.update(t.depends_on)
        return [n for n in self._order if n not in depended_on] or list(self._order)

    def on_complete(self, callback: Callable[["Workflow"], None]) -> "Workflow":
        self._on_complete.append(callback)
        return self

    def on_failure(
        self, callback: Callable[["Workflow", Exception], None]
    ) -> "Workflow":
        self._on_failure.append(callback)
        return self

    # -- validation --------------------------------------------------------
    def validate(self) -> None:
        """Check for missing dependencies and dependency cycles."""
        for task in self.tasks.values():
            for dep in task.depends_on:
                if dep not in self.tasks:
                    raise DependencyError(
                        f"Task '{task.name}' depends on unknown task '{dep}'"
                    )
        self._topological_order()  # raises DependencyError on cycles

    def _topological_order(self) -> list[list[str]]:
        """Return task names grouped into sequential 'levels' that can each
        be executed in parallel (Kahn's algorithm)."""
        in_degree = {name: 0 for name in self.tasks}
        dependents: dict[str, list[str]] = {name: [] for name in self.tasks}
        for name, task in self.tasks.items():
            for dep in task.depends_on:
                in_degree[name] += 1
                dependents[dep].append(name)
        levels: list[list[str]] = []
        remaining = dict(in_degree)
        placed = 0
        current = [n for n, d in remaining.items() if d == 0]
        # preserve insertion order within a level
        current.sort(key=lambda n: self._order.index(n))
        while current:
            levels.append(current)
            placed += len(current)
            next_level: list[str] = []
            for name in current:
                for dependent in dependents[name]:
                    remaining[dependent] -= 1
                    if remaining[dependent] == 0:
                        next_level.append(dependent)
            next_level.sort(key=lambda n: self._order.index(n))
            current = next_level
        if placed != len(self.tasks):
            raise DependencyError(f"Workflow '{self.name}' contains a dependency cycle")
        return levels

    # -- execution -----------------------------------------------------
    def run(self, parallel: bool = False) -> ExecutionReport:
        """Execute the workflow. If ``parallel`` is True, independent tasks
        (as determined by the dependency graph) run concurrently."""
        from pyworkflow.logging.logger import logger
        if self.state == WorkflowState.RUNNING:
            raise WorkflowStateError(f"Workflow '{self.name}' is already running")
        self.validate()
        self.state = WorkflowState.RUNNING
        self.started_at = time.time()
        self.context = {}
        import os
        self.pid = os.getpid()
        logger.info(
            f"Workflow '{self.name}' started (PID: {self.pid})",
            extra={"workflow_name": self.name},
        )
        try:
            report = self._engine.execute(parallel=parallel)
        finally:
            self.pid = None
        self.finished_at = time.time()
        duration = self.finished_at - self.started_at
        self.state = WorkflowState.COMPLETED if report.success else WorkflowState.FAILED
        if report.success:
            logger.info(
                f"Workflow '{self.name}' completed successfully in {duration:.4f}s",
                extra={"workflow_name": self.name, "duration": duration},
            )
            for cb in self._on_complete:
                cb(self)
        else:
            logger.error(
                f"Workflow '{self.name}' failed in {duration:.4f}s. Error: {report.error}",
                extra={"workflow_name": self.name, "duration": duration},
            )
            for fail_cb in self._on_failure:
                fail_cb(self, report.error or Exception("Workflow failed"))
        return report

    def retry_failed_tasks(self, parallel: bool = False) -> ExecutionReport:
        """Re-run only tasks currently in FAILED state (and anything that
        depends on them), keeping successful task outputs in context."""
        failed = [n for n, t in self.tasks.items() if t.state == TaskState.FAILED]
        if not failed:
            return ExecutionReport(success=True, results={}, error=None)

        # Transitively find all tasks that depend on the failed tasks
        to_reset = set(failed)
        changed = True
        while changed:
            changed = False
            for name, task in self.tasks.items():
                if name not in to_reset:
                    for dep in task.depends_on:
                        if dep in to_reset:
                            to_reset.add(name)
                            changed = True
                            break

        for name in to_reset:
            self.tasks[name].reset()

        self.state = WorkflowState.RUNNING
        import os

        self.pid = os.getpid()
        try:
            report = self._engine.execute(parallel=parallel, only=set(failed))
        finally:
            self.pid = None
        self.state = WorkflowState.COMPLETED if report.success else WorkflowState.FAILED
        return report

    def cancel(self) -> None:
        self.state = WorkflowState.CANCELLED
        for task in self.tasks.values():
            if task.state in (TaskState.PENDING, TaskState.RUNNING):
                task.state = TaskState.CANCELLED

    def pause(self) -> None:
        if self.state != WorkflowState.RUNNING:
            raise WorkflowStateError("Only a running workflow can be paused")
        self.state = WorkflowState.PAUSED

    def resume(self) -> None:
        if self.state != WorkflowState.PAUSED:
            raise WorkflowStateError("Only a paused workflow can be resumed")
        self.state = WorkflowState.RUNNING

    def reset(self) -> None:
        """Reset the workflow and all tasks to their initial state."""
        self.state = WorkflowState.CREATED
        self.context = {}
        self.started_at = None
        self.finished_at = None
        for task in self.tasks.values():
            task.reset()

    # -- scheduling --------------------------------------------------------
    def schedule(
        self,
        mode: str = "now",
        *args: Any,
        delay: Optional[float] = None,
        every: Optional[float] = None,
        cron: Optional[str] = None,
        time: Optional[str] = None,
        parallel: bool = False,
        **kwargs: Any,
    ) -> str:
        """Schedule this workflow to run via the shared background scheduler."""
        if args:
            if mode == "daily" and time is None:
                time = args[0]
            elif mode == "cron" and cron is None:
                cron = args[0]
            elif mode == "interval" and every is None:
                every = float(args[0])
            elif mode == "delay" and delay is None:
                delay = float(args[0])

        from pyworkflow.scheduler.scheduler import Scheduler

        global _default_scheduler
        if _default_scheduler is None:
            _default_scheduler = Scheduler()

        def _run():
            self.reset()
            self.run(parallel=parallel)

        if mode == "now":
            return _default_scheduler.run_now(self.name, _run)
        if mode == "delay":
            if delay is None:
                raise ValueError("mode='delay' requires a `delay` (seconds) argument")
            return _default_scheduler.run_after(self.name, _run, delay)
        if mode == "interval":
            if every is None:
                raise ValueError(
                    "mode='interval' requires an `every` (minutes) argument"
                )
            return _default_scheduler.run_every(self.name, _run, every)
        if mode == "cron":
            if cron is None:
                raise ValueError("mode='cron' requires a `cron` expression argument")
            return _default_scheduler.run_cron(self.name, _run, cron)
        if mode == "daily":
            if time is None:
                raise ValueError("mode='daily' requires a `time='HH:MM'` argument")
            return _default_scheduler.run_daily(self.name, _run, time)
        raise ValueError(f"Unknown schedule mode: {mode!r}")

    # -- visualization / reporting --------------------------------------
    def visualize(self, output_path: Optional[str] = None, fmt: str = "png"):
        from pyworkflow.visualization.graph import render_workflow

        return render_workflow(self, output_path=output_path, fmt=fmt)

    def summary(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "duration": (
                (self.finished_at - self.started_at)
                if self.started_at and self.finished_at
                else None
            ),
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "pid": self.pid,
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Workflow(name={self.name!r}, state={self.state.value}, tasks={len(self.tasks)})"
