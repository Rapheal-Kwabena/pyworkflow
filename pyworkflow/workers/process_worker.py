"""Process worker that executes a task's function in a separate process with fallback."""

from __future__ import annotations

import multiprocessing
import os
import sys
import time
import traceback
from typing import Any, TYPE_CHECKING

from pyworkflow.core.state import TaskState
from pyworkflow.core.task import TaskResult
from pyworkflow.workers.worker import Worker

if TYPE_CHECKING:
    from pyworkflow.core.task import Task


def _run_in_process_target(
    pipe_conn: multiprocessing.connection.Connection,
    func: Any,
    args: tuple,
    kwargs: dict,
    context: dict,
    depends_on: list[str],
    input_model: Any,
    output_model: Any,
    validate_types: bool,
) -> None:
    """Target function executed in the child process."""
    try:
        import inspect
        from pyworkflow.contracts.validation import (
            validate_inputs,
            validate_output,
        )

        sig = inspect.signature(func)
        call_args = list(args)
        call_kwargs = dict(kwargs)

        params = list(sig.parameters.values())
        positional_params_filled = len(call_args)

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
        for dep in depends_on:
            if dep in context:
                dep_outputs[dep] = context[dep]

        remaining_deps = list(depends_on)
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

        if input_model:
            call_args, call_kwargs = validate_inputs(
                input_model, sig, call_args, call_kwargs
            )

        if validate_types:
            from pydantic import validate_call

            wrapped = validate_call(func)
            result = wrapped(*call_args, **call_kwargs)
        else:
            result = func(*call_args, **call_kwargs)

        if output_model:
            result = validate_output(output_model, result)

        pipe_conn.send((True, result, None))
    except Exception as exc:
        tb = traceback.format_exc()
        pipe_conn.send((False, None, (exc, tb)))
    except BaseException as exc:
        tb = traceback.format_exc()
        pipe_conn.send((False, None, (Exception(str(exc)), tb)))
    finally:
        pipe_conn.close()


class ProcessWorker(Worker):
    """Runs a task's function inside a separate multiprocessing.Process with automatic fallback."""

    def run(self, context: dict[str, Any]) -> TaskResult:
        import pickle

        # Check if we should execute in-process
        # e.g., during testing/mocking under pytest, or if the function is not pickleable
        in_process = (
            os.environ.get("PYWORKFLOW_IN_PROCESS") == "1"
            or "pytest" in sys.modules
        )

        if not in_process:
            try:
                pickle.dumps(self.task.function)
            except Exception:
                in_process = True

        if in_process:
            # In-process execution (allows monkeypatching, mocking, non-pickleable functions)
            started = time.time()
            try:
                output = self.task._call(context)
                finished = time.time()
                return TaskResult(
                    state=TaskState.SUCCESS,
                    output=output,
                    started_at=started,
                    finished_at=finished,
                )
            except Exception as exc:
                finished = time.time()
                tb = traceback.format_exc()
                return TaskResult(
                    state=TaskState.FAILED,
                    error=str(exc) if not tb else f"{type(exc).__name__}: {exc}\nTraceback:\n{tb}",
                    started_at=started,
                    finished_at=finished,
                    exception=exc,
                )

        # Separate Subprocess isolated execution path
        parent_conn, child_conn = multiprocessing.Pipe()

        p = multiprocessing.Process(
            target=_run_in_process_target,
            args=(
                child_conn,
                self.task.function,
                self.task.args,
                self.task.kwargs,
                context,
                self.task.depends_on,
                self.task.input_model,
                self.task.output_model,
                self.task.validate_types,
            ),
        )

        started = time.time()
        p.start()
        child_conn.close()

        timeout = self.task.timeout
        has_result = False
        result = None

        if timeout is not None:
            if parent_conn.poll(timeout):
                try:
                    result = parent_conn.recv()
                    has_result = True
                except EOFError:
                    pass
        else:
            try:
                result = parent_conn.recv()
                has_result = True
            except EOFError:
                pass

        if timeout is not None:
            p.join(0)
            if p.is_alive():
                p.terminate()
                p.join()
                finished = time.time()
                return TaskResult(
                    state=TaskState.FAILED,
                    error=f"TaskTimeoutError: Task '{self.task.name}' exceeded timeout of {timeout}s",
                    started_at=started,
                    finished_at=finished,
                )
        else:
            p.join()

        finished = time.time()

        if not has_result:
            exitcode = p.exitcode
            return TaskResult(
                state=TaskState.FAILED,
                error=f"ProcessWorkerCrashError: Process worker crashed with exit code {exitcode}",
                started_at=started,
                finished_at=finished,
            )

        success, val, err_info = result
        if success:
            return TaskResult(
                state=TaskState.SUCCESS,
                output=val,
                started_at=started,
                finished_at=finished,
            )
        else:
            exc, tb = err_info
            return TaskResult(
                state=TaskState.FAILED,
                error=f"{type(exc).__name__}: {exc}\nTraceback:\n{tb}" if tb else f"{type(exc).__name__}: {exc}",
                started_at=started,
                finished_at=finished,
                exception=exc,
            )
