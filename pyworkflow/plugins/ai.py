"""Built-in AI plugin: turns an LLM call into a reusable workflow Task.

This is intentionally provider-agnostic: you supply a `call_fn(prompt) ->
str` when calling `setup()`, so it works with any SDK (Anthropic, OpenAI,
OpenRouter, a local model, etc.) without PyWorkflow taking a hard dependency
on any of them.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from pyworkflow.core.task import Task
from pyworkflow.plugins.base import Plugin


class AIPlugin(Plugin):
    name = "ai"

    def __init__(self) -> None:
        self.call_fn: Optional[Callable[[str], str]] = None
        self.model: Optional[str] = None

    def setup(  # type: ignore[override]
        self, call_fn: Callable[[str], str], model: Optional[str] = None, **_: Any
    ) -> None:
        """`call_fn` takes a prompt string and returns the model's text
        response. Wire this to whichever LLM SDK/API you use."""
        self.call_fn = call_fn
        self.model = model

    def _run_prompt(self, prompt: str, context: Optional[dict] = None) -> str:
        if self.call_fn is None:
            raise RuntimeError(
                "AIPlugin.setup() must be called before running AI tasks"
            )
        full_prompt = prompt
        if context:
            full_prompt = f"{prompt}\n\nContext from prior tasks:\n{context}"
        return self.call_fn(full_prompt)

    def make_task(
        self,
        name: str,
        prompt: str,
        use_context: bool = True,
        retries: int = 1,
        **task_kwargs: Any,
    ) -> Task:
        """Build a Task that sends `prompt` (optionally plus the workflow's
        accumulated context) to the configured LLM and stores its text
        response as the task output."""

        def _fn(context: dict) -> str:
            return self._run_prompt(prompt, context if use_context else None)

        return Task(name=name, function=_fn, retries=retries, **task_kwargs)

    def make_decision_task(
        self,
        name: str,
        question: str,
        choices: list[str],
        retries: int = 1,
        **task_kwargs: Any,
    ) -> Task:
        """Build a Task where the LLM must pick one of `choices`, useful for
        AI-driven workflow branching."""

        def _fn(context: dict) -> str:
            prompt = (
                f"{question}\n\nRespond with exactly one of these options and "
                f"nothing else: {', '.join(choices)}\n\nContext: {context}"
            )
            answer = self._run_prompt(prompt, None)
            return answer.strip()

        return Task(name=name, function=_fn, retries=retries, **task_kwargs)
