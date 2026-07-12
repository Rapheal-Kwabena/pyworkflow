"""Task primitives for PyWorkflow."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Type

from pyworkflow.exceptions import TaskExecutionError
from pyworkflow.core.state import TaskState


@dataclass
class TaskResult:
    """Captures the outcome of a single task execution attempt."""

    state: TaskState
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    attempt: int = 1
    exception: Optional[Exception] = None

    @property
    def duration(self) -> Optional[float]:
        if self.started_at is None or self.finished_at is None:
            return None
        return self.finished_at - self.started_at


class Task:
    """A single unit of work inside a :class:`~pyworkflow.core.workflow.Workflow`.

    Parameters
    ----------
    name:
        Human readable, unique-within-workflow task name.
    function:
        Callable to execute. It may accept a ``context`` keyword argument
        (the dict of prior task outputs) if it declares one; otherwise it is
        called with whatever ``args``/``kwargs`` were supplied.
    description:
        Optional free-text description.
    args / kwargs:
        Positional/keyword arguments passed to ``function`` on every attempt.
    retries:
        Number of retry attempts after an initial failure (0 = no retries).
    retry_delay:
        Seconds to wait between retry attempts.
    timeout:
        Optional soft timeout in seconds. PyWorkflow does not forcibly kill
        threads, but records a timeout failure if execution exceeds this.
    depends_on:
        Names of tasks that must complete successfully before this task runs.
    condition:
        Optional callable ``(context) -> bool``. If it returns False the task
        is skipped instead of executed.
    on_failure:
        Optional callback ``(task, exception) -> None`` invoked when the task
        ultimately fails (after exhausting retries).
    continue_on_failure:
        If True, a failure in this task does not stop the overall workflow.
    """

    def __init__(
        self,
        name: str,
        function: Callable[..., Any],
        description: str = "",
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        retries: int = 0,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        depends_on: Optional[Iterable[str]] = None,
        condition: Optional[Callable[[dict], bool]] = None,
        on_failure: Optional[Callable[["Task", BaseException], None]] = None,
        continue_on_failure: bool = False,
        input_model: Optional[Type[Any]] = None,
        output_model: Optional[Type[Any]] = None,
        validate_types: bool = False,
    ) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("Task name must be a non-empty string")
        if retries < 0:
            raise ValueError("retries must be >= 0")

        self.name = name
        self.function = function
        self.description = description
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.retries = retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.depends_on = list(depends_on) if depends_on else []
        self.condition = condition
        self.on_failure = on_failure
        self.continue_on_failure = continue_on_failure
        self.input_model = input_model
        self.output_model = output_model
        self.validate_types = validate_types

        self.state: TaskState = TaskState.PENDING

        self.output: Any = None
        self.error: Optional[str] = None
        self.attempts: int = 0
        self.history: list[TaskResult] = []
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

    # -- execution -----------------------------------------------------
    def _call(self, context: dict) -> Any:
        """Call the underlying function, injecting dependencies or ``context``, and performing validations."""
        import inspect
        from pyworkflow.contracts.validation import validate_inputs, validate_output

        try:
            sig = inspect.signature(self.function)
        except (ValueError, TypeError):
            return self.function(*self.args, **self.kwargs)

        params = list(sig.parameters.values())

        # Build arguments to pass
        call_args: tuple = tuple(self.args)
        call_kwargs = dict(self.kwargs)

        positional_params_filled = len(self.args)

        unfilled_params = []
        for i, p in enumerate(params):
            if p.name == "context":
                if "context" not in call_kwargs:
                    call_kwargs["context"] = context
                continue
            if i < positional_params_filled:
                continue
            if p.name in call_kwargs:
                continue
            unfilled_params.append(p)

        dep_outputs = {}
        for dep in self.depends_on:
            if dep in context:
                dep_outputs[dep] = context[dep]

        remaining_deps = list(self.depends_on)
        for p in list(unfilled_params):
            if p.name in dep_outputs:
                call_kwargs[p.name] = dep_outputs[p.name]
                unfilled_params.remove(p)
                if p.name in remaining_deps:
                    remaining_deps.remove(p.name)

        for p in unfilled_params:
            if remaining_deps:
                dep_name = remaining_deps.pop(0)
                if dep_name in dep_outputs:
                    call_kwargs[p.name] = dep_outputs[dep_name]

        if self.input_model:
            call_args, call_kwargs = validate_inputs(self.input_model, sig, call_args, call_kwargs)

        if self.validate_types:
            from pydantic import validate_call
            wrapped = validate_call(self.function)
            result = wrapped(*call_args, **call_kwargs)
        else:
            result = self.function(*call_args, **call_kwargs)

        if self.output_model:
            result = validate_output(self.output_model, result)

        return result

    def run(self, context: dict) -> TaskResult:
        """Execute the task (with retries) inside a process-isolated worker, returning a :class:`TaskResult`.

        This method mutates ``self.state``/``self.output``/``self.error`` and
        also appends a full attempt history for observability.
        """
        if self.condition is not None and not self.condition(context):
            self.state = TaskState.SKIPPED
            result = TaskResult(state=TaskState.SKIPPED)
            self.history.append(result)
            return result

        max_attempts = self.retries + 1

        from pyworkflow.logging.logger import logger
        from pyworkflow.workers.process_worker import ProcessWorker

        for attempt in range(1, max_attempts + 1):
            self.attempts = attempt
            self.state = TaskState.RUNNING if attempt == 1 else TaskState.RETRYING
            logger.info(
                f"Task '{self.name}' (attempt {attempt}/{max_attempts}) started",
                extra={"task_name": self.name},
            )

            worker = ProcessWorker(self)
            result = worker.run(context)
            result.attempt = attempt

            self.started_at = result.started_at
            self.finished_at = result.finished_at
            self.history.append(result)

            duration = (result.finished_at - result.started_at) if result.started_at and result.finished_at else 0.0

            if result.state == TaskState.SUCCESS:
                self.state = TaskState.COMPLETED
                self.output = result.output
                self.error = None
                logger.info(
                    f"Task '{self.name}' (attempt {attempt}/{max_attempts}) succeeded in {duration:.4f}s",
                    extra={"task_name": self.name, "duration": duration},
                )
                return result
            else:
                self.error = result.error
                logger.error(
                    f"Task '{self.name}' (attempt {attempt}/{max_attempts}) failed in {duration:.4f}s. Error: {self.error}",
                    extra={"task_name": self.name, "duration": duration},
                )
                if attempt < max_attempts:
                    time.sleep(self.retry_delay)
                    continue

        self.state = TaskState.FAILED
        last_exc = self.history[-1].exception if (self.history and self.history[-1].exception) else Exception(self.error or f"Task {self.name} failed")
        if self.on_failure is not None:
            try:
                self.on_failure(self, last_exc)
            except Exception:
                pass
        raise TaskExecutionError(self.name, last_exc)

    def execute(self) -> Any:
        """Execute task standalone, returning output or raising original exception."""
        try:
            self.run({})
        except TaskExecutionError as exc:
            raise exc.original_exception
        return self.output

    def reset(self) -> None:
        """Reset task state so the workflow can be re-run from scratch."""
        self.state = TaskState.PENDING
        self.output = None
        self.error = None
        self.attempts = 0
        self.history = []
        self.started_at = None
        self.finished_at = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "output": _safe_repr(self.output),
            "error": self.error,
            "attempts": self.attempts,
            "depends_on": self.depends_on,
            "retries": self.retries,
            "duration": (
                (self.finished_at - self.started_at)
                if self.started_at and self.finished_at
                else None
            ),
        }

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Task(name={self.name!r}, state={self.state.value})"


def _safe_repr(value: Any) -> Any:
    """Best-effort JSON-friendly representation of a task's output."""
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return repr(value)
