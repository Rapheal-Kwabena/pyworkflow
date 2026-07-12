"""Decorator to register functions as Tasks inside workflows."""

from __future__ import annotations

from typing import Any, Callable, Optional, Type
from pyworkflow.core.task import Task


class DecoratedTask:
    """Wrapper class for decorated functions that acts as a Task factory."""

    def __init__(self, fn: Callable[..., Any], **task_kwargs: Any) -> None:
        self.fn = fn
        self.task_kwargs = task_kwargs
        self.__name__ = fn.__name__
        self.__doc__ = fn.__doc__ or ""
        self.__wrapped__ = fn

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the raw underlying function directly when called standalone."""
        return self.fn(*args, **kwargs)

    def get_task(self) -> Task:
        """Create and return a configured Task instance based on the function."""
        name = self.task_kwargs.get("name", self.fn.__name__)
        description = self.task_kwargs.get("description", self.fn.__doc__ or "")
        task_opts = {
            k: v
            for k, v in self.task_kwargs.items()
            if k not in ("name", "description")
        }
        return Task(
            name=name,
            function=self.fn,
            description=description,
            **task_opts,
        )


def task(
    fn: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    description: str = "",
    retries: int = 0,
    retry_delay: float = 1.0,
    timeout: Optional[float] = None,
    depends_on: Optional[list[str]] = None,
    condition: Optional[Callable[[dict], bool]] = None,
    on_failure: Optional[Callable[[Any, BaseException], None]] = None,
    continue_on_failure: bool = False,
    input_model: Optional[Type[Any]] = None,
    output_model: Optional[Type[Any]] = None,
    validate_types: bool = False,
) -> Any:
    """Decorator to define a PyWorkflow Task.

    Can be used as @task or @task(retries=3).
    """
    kwargs = {
        "name": name,
        "description": description,
        "retries": retries,
        "retry_delay": retry_delay,
        "timeout": timeout,
        "depends_on": depends_on,
        "condition": condition,
        "on_failure": on_failure,
        "continue_on_failure": continue_on_failure,
        "input_model": input_model,
        "output_model": output_model,
        "validate_types": validate_types,
    }
    # Filter out None values except for parameters where None has meaning
    kwargs = {
        k: v
        for k, v in kwargs.items()
        if v is not None
        or k
        in (
            "timeout",
            "depends_on",
            "condition",
            "on_failure",
            "input_model",
            "output_model",
        )
    }

    if fn is not None:
        return DecoratedTask(fn, **kwargs)

    def decorator(f: Callable[..., Any]) -> DecoratedTask:
        return DecoratedTask(f, **kwargs)

    return decorator
