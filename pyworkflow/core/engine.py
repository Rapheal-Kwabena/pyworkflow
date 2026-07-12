"""The execution engine that walks a Workflow's dependency graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pyworkflow.core.state import TaskState
from pyworkflow.core.execution import ExecutionReport
from pyworkflow.exceptions import TaskExecutionError

if TYPE_CHECKING:
    from pyworkflow.core.workflow import Workflow


class Engine:
    """Executes a workflow's tasks in dependency order.

    The engine groups tasks into "levels" using a topological sort.
    Within a level, tasks run in parallel using process workers if parallel=True,
    otherwise sequentially.
    """

    def __init__(self, workflow: Workflow) -> None:
        self.workflow = workflow

    def execute(
        self, parallel: bool = False, only: Optional[set] = None
    ) -> ExecutionReport:
        wf = self.workflow
        levels = wf._topological_order()
        results: dict = {}
        failed_tasks: list[str] = []
        skipped_tasks: list[str] = []
        first_error: Optional[Exception] = None
        halted = False

        # Load checkpoint if storage is configured
        if wf.storage:
            from pyworkflow.storage.checkpoints import CheckpointManager

            checkpoint_manager = CheckpointManager(wf.storage)
            checkpoint_manager.load_checkpoint(wf)

        for level in levels:
            if halted:
                break

            names_to_run = []
            for n in level:
                t = wf.tasks[n]
                # If checkpoint loaded this task as COMPLETED/SUCCESS, bypass running it
                if t.state in (TaskState.COMPLETED, TaskState.SUCCESS):
                    results[n] = t.output
                    wf.context[n] = t.output
                    continue

                if only is None or n in only or self._depends_on_rerun(n, only):
                    names_to_run.append(n)
                else:
                    # Carry forward context for unselected tasks
                    if t.state in (TaskState.COMPLETED, TaskState.SUCCESS):
                        results[n] = t.output
                        wf.context[n] = t.output

            if not names_to_run:
                continue

            if parallel and len(names_to_run) > 1:
                level_results = self._run_level_parallel(names_to_run)
            else:
                level_results = self._run_level_sequential(names_to_run)

            for name, (ok, error) in level_results.items():
                task = wf.tasks[name]
                if task.state == TaskState.SKIPPED:
                    skipped_tasks.append(name)
                    continue
                if ok:
                    results[name] = task.output
                    wf.context[name] = task.output
                else:
                    failed_tasks.append(name)
                    if first_error is None:
                        first_error = error
                    if not task.continue_on_failure and wf.stop_on_failure:
                        halted = True

        success = len(failed_tasks) == 0
        return ExecutionReport(
            success=success,
            results=results,
            error=first_error,
            failed_tasks=failed_tasks,
            skipped_tasks=skipped_tasks,
        )

    def _depends_on_rerun(self, name: str, only: set) -> bool:
        """True if `name` transitively depends on a task in `only`."""
        wf = self.workflow
        task = wf.tasks[name]
        for dep in task.depends_on:
            if dep in only or self._depends_on_rerun(dep, only):
                return True
        return False

    def _run_level_sequential(self, names: list[str]) -> dict:
        outcomes = {}
        for name in names:
            outcomes[name] = self._run_single(name)
        return outcomes

    def _run_level_parallel(self, names: list[str]) -> dict:
        wf = self.workflow
        from pyworkflow.workers.executor import ProcessExecutor

        executor = ProcessExecutor(max_workers=wf.max_workers)
        return executor.execute_tasks(self._run_single, names)

    def _run_single(self, name: str) -> tuple[bool, Optional[Exception]]:
        wf = self.workflow
        task = wf.tasks[name]

        # Save checkpoint before execution starts (sets state to RUNNING)
        if wf.storage:
            from pyworkflow.storage.checkpoints import CheckpointManager

            CheckpointManager(wf.storage).save_checkpoint(wf)

        try:
            task.run(dict(wf.context))

            # Save checkpoint on success (sets state to COMPLETED)
            if wf.storage:
                from pyworkflow.storage.checkpoints import CheckpointManager

                CheckpointManager(wf.storage).save_checkpoint(wf)

            return (True, None)
        except TaskExecutionError as exc:
            # Save checkpoint on failure (sets state to FAILED)
            if wf.storage:
                from pyworkflow.storage.checkpoints import CheckpointManager

                try:
                    CheckpointManager(wf.storage).save_checkpoint(wf)
                except Exception:
                    pass
            return (False, exc)
        except Exception as exc:  # noqa: BLE001
            if wf.storage:
                from pyworkflow.storage.checkpoints import CheckpointManager

                try:
                    CheckpointManager(wf.storage).save_checkpoint(wf)
                except Exception:
                    pass
            return (False, exc)
