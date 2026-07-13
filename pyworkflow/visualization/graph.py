"""Render a workflow's task dependency graph and execution timeline.

Uses ``graphviz`` if installed for polished graph output, falling back to a
plain-text dependency map (always available, zero extra dependencies) so
``workflow.visualize()`` never hard-fails just because an optional
visualization library is missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pyworkflow.core.task import TaskState

if TYPE_CHECKING:  # pragma: no cover
    from pyworkflow.core.workflow import Workflow

_STATE_COLORS = {
    TaskState.PENDING: "lightgray",
    TaskState.RUNNING: "gold",
    TaskState.COMPLETED: "palegreen",
    TaskState.FAILED: "salmon",
    TaskState.SKIPPED: "lightblue",
    TaskState.RETRYING: "orange",
    TaskState.CANCELLED: "gray",
}


def render_workflow(
    workflow: "Workflow", output_path: Optional[str] = None, fmt: str = "png"
):
    """Render the workflow's dependency graph.

    If ``graphviz`` (the Python package + system ``dot`` binary) is
    available, renders an image to ``output_path`` (or ``<name>.<fmt>`` in
    the current directory) and returns the path. Otherwise, returns (and
    prints) a plain-text dependency map.
    """
    try:
        return _render_with_graphviz(workflow, output_path, fmt)
    except Exception:
        return _render_text(workflow)


def _render_with_graphviz(
    workflow: "Workflow", output_path: Optional[str], fmt: str
) -> str:
    import graphviz  # type: ignore

    dot = graphviz.Digraph(name=workflow.name, format=fmt)
    dot.attr(rankdir="LR")

    for name, task in workflow.tasks.items():
        color = _STATE_COLORS.get(task.state, "white")
        label = f"{name}\\n[{task.state.value}]"
        dot.node(name, label=label, style="filled", fillcolor=color)

    for name, task in workflow.tasks.items():
        for dep in task.depends_on:
            dot.edge(dep, name)

    target = output_path or workflow.name.replace(" ", "_")
    rendered_path = dot.render(target, cleanup=True)
    return rendered_path


def _render_text(workflow: "Workflow") -> str:
    lines = [f"Workflow: {workflow.name}  [{workflow.state.value}]", ""]
    levels = workflow._topological_order()
    for i, level in enumerate(levels, start=1):
        lines.append(f"Level {i}:")
        for name in level:
            task = workflow.tasks[name]
            deps = (
                f" (depends on: {', '.join(task.depends_on)})"
                if task.depends_on
                else ""
            )
            lines.append(f"  - {name} [{task.state.value}]{deps}")
    text = "\n".join(lines)
    print(text)
    return text


def render_timeline(workflow: "Workflow") -> str:
    """Return a simple text-based execution timeline sorted by start time."""
    rows = []
    for name, task in workflow.tasks.items():
        if task.started_at is None:
            continue
        duration = (task.finished_at - task.started_at) if task.finished_at else None
        rows.append((task.started_at, name, task.state.value, duration))
    rows.sort()

    lines = [f"Execution timeline: {workflow.name}", ""]
    for started_at, name, state, duration in rows:
        dur_str = f"{duration:.3f}s" if duration is not None else "?"
        lines.append(f"  t={started_at:.2f}  {name:<20} [{state}]  duration={dur_str}")
    text = "\n".join(lines)
    print(text)
    return text
