"""PyWorkflow command line interface.

Operates on workflow definition modules and query histories.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Optional

import click

from pyworkflow.core.workflow import Workflow, WorkflowState
from pyworkflow.storage.json_storage import JSONStorage
from pyworkflow.storage.sqlite import SQLiteStorage

TEMPLATE = '''"""PyWorkflow workflow definition: {name}

Run with:
    pyworkflow run {filename}
"""

from pyworkflow import Task, Workflow


def step_one():
    print("Running step one...")
    return "step one done"


def step_two(context):
    print("Running step two, saw output:", context.get("Step One"))
    return "step two done"


workflow = Workflow("{name}")
workflow.add_task(Task("Step One", step_one))
workflow.add_task(Task("Step Two", step_two, depends_on=["Step One"]))
'''


def _load_workflow(path: str) -> Workflow:
    file_path = Path(path)
    if not file_path.exists():
        alt = Path(f"{path}.py")
        if alt.exists():
            file_path = alt
        else:
            raise click.ClickException(f"Workflow file not found: {path}")

    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"Could not load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(file_path.parent.resolve()))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)

    workflow = getattr(module, "workflow", None)
    if not isinstance(workflow, Workflow):
        raise click.ClickException(
            f"{file_path} must define a module-level `workflow = Workflow(...)`"
        )
    return workflow


def _get_storage(storage_type: str = "sqlite") -> Any:
    """Return the selected storage backend instance."""
    if storage_type == "json":
        return JSONStorage()
    return SQLiteStorage()


def _load_storage_auto(name: str) -> tuple[Any, Optional[dict]]:
    """Try loading the workflow definition from SQLite first, falling back to JSON."""
    sqlite_store = SQLiteStorage()
    try:
        data = sqlite_store.get_workflow(name)
        if data:
            return sqlite_store, data
    except Exception:
        pass

    json_store = JSONStorage()
    try:
        data = json_store.get_workflow(name)
        if data:
            return json_store, data
    except Exception:
        pass

    return sqlite_store, None


def _load_history_auto(name: str) -> list[dict]:
    """Try loading history from SQLite first, falling back to JSON."""
    try:
        sqlite_store = SQLiteStorage()
        history = sqlite_store.get_history(name)
        if history:
            return history
    except Exception:
        pass

    try:
        json_store = JSONStorage()
        history = json_store.get_history(name)
        if history:
            return history
    except Exception:
        pass

    return []


@click.group()
@click.version_option(package_name="pyworkflow")
def cli() -> None:
    """PyWorkflow: automate, schedule, and monitor Python workflows."""


@cli.command()
@click.argument("name")
def create(name: str) -> None:
    """Scaffold a new workflow definition file."""
    filename = name if name.endswith(".py") else f"{name}.py"
    path = Path(filename)
    if path.exists():
        raise click.ClickException(f"{filename} already exists")
    path.write_text(TEMPLATE.format(name=name, filename=filename))
    click.echo(f"Created {filename}")


@cli.command()
@click.argument("path")
@click.option("--parallel", is_flag=True, help="Run independent tasks concurrently.")
@click.option(
    "--store/--no-store", default=True, help="Persist run history to local storage."
)
@click.option(
    "--storage-type",
    type=click.Choice(["sqlite", "json"]),
    default="sqlite",
    help="Database storage backend to use (default: sqlite).",
)
def run(path: str, parallel: bool, store: bool, storage_type: str) -> None:
    """Run a workflow definition file."""
    import os
    import time
    import signal

    workflow = _load_workflow(path)
    click.echo(f"Running workflow: {workflow.name}")

    storage = None
    if store:
        storage = _get_storage(storage_type)
        # Enable state checkpointing in engine
        workflow.storage = storage

        # Save initially as RUNNING to storage with current PID
        wf_dict = workflow.to_dict()
        wf_dict["state"] = WorkflowState.RUNNING.value
        wf_dict["started_at"] = time.time()
        wf_dict["pid"] = os.getpid()
        storage.save_workflow(wf_dict)

        def handle_sigterm(signum, frame):
            workflow.state = WorkflowState.CANCELLED
            workflow.finished_at = time.time()
            workflow.pid = None
            if storage:
                storage.save_workflow(workflow.to_dict())
                storage.save_run(
                    workflow.name,
                    {
                        "success": False,
                        "failed_tasks": [],
                        "skipped_tasks": [],
                        "results": {},
                        "error": "SIGTERM",
                    },
                )
            sys.exit(143)

        signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        report = workflow.run(parallel=parallel)
    except KeyboardInterrupt:
        if store and storage:
            workflow.state = WorkflowState.CANCELLED
            workflow.finished_at = time.time()
            workflow.pid = None
            storage.save_workflow(workflow.to_dict())
            storage.save_run(
                workflow.name,
                {
                    "success": False,
                    "failed_tasks": [],
                    "skipped_tasks": [],
                    "results": {},
                    "error": "KeyboardInterrupt",
                },
            )
        click.secho(
            f"\nWorkflow '{workflow.name}' interrupted and cancelled.", fg="yellow"
        )
        sys.exit(130)

    if store and storage:
        workflow.pid = None
        storage.save_workflow(workflow.to_dict())
        storage.save_run(
            workflow.name,
            {
                "success": report.success,
                "failed_tasks": report.failed_tasks,
                "skipped_tasks": report.skipped_tasks,
                "results": {k: str(v) for k, v in report.results.items()},
            },
        )

    for name, task in workflow.tasks.items():
        symbol = {"COMPLETED": "✔", "SUCCESS": "✔", "FAILED": "✘", "SKIPPED": "→"}.get(
            task.state.value, "•"
        )
        click.echo(f"  {symbol} {name}: {task.state.value}")

    if report.success:
        click.secho(f"Workflow '{workflow.name}' completed successfully.", fg="green")
    else:
        click.secho(
            f"Workflow '{workflow.name}' failed. Failed tasks: {report.failed_tasks}",
            fg="red",
        )
        sys.exit(1)


@cli.command()
@click.argument("name")
def status(name: str) -> None:
    """Show the last known status of a workflow (from local storage)."""
    _, data = _load_storage_auto(name)
    if not data:
        raise click.ClickException(f"No stored workflow found named '{name}'")
    click.echo(f"Workflow: {data['name']}  [{data['state']}]")
    for t in data.get("tasks", []):
        click.echo(f"  - {t['name']}: {t['state']}")


@cli.command()
@click.argument("name")
@click.option("--limit", default=10, help="Number of recent runs to show.")
@click.option(
    "--export",
    type=click.Path(writable=True),
    help="Path to export history as a JSON file.",
)
def history(name: str, limit: int, export: Optional[str]) -> None:
    """Show recent run history for a workflow."""
    records = _load_history_auto(name)
    if not records:
        click.echo(f"No run history for '{name}'")
        return

    selected_records = records[-limit:] if limit > 0 else records

    if export:
        import json

        try:
            path = Path(export)
            path.write_text(json.dumps(selected_records, indent=2, default=str))
            click.echo(f"Exported history of '{name}' to {export}")
        except Exception as exc:
            raise click.ClickException(f"Failed to export history: {exc}")
        return

    for record in selected_records:
        status_str = "SUCCESS" if record.get("success") else "FAILED"
        click.echo(
            f"  [{record.get('timestamp')}] {status_str}  failed={record.get('failed_tasks')}"
        )


@cli.command()
@click.argument("name")
def logs(name: str) -> None:
    """Show detailed logs (errors) from the most recent run of a workflow."""
    records = _load_history_auto(name)
    if not records:
        click.echo(f"No logs for '{name}'")
        return
    latest = records[-1]
    click.echo(
        f"Latest run of '{name}': {'SUCCESS' if latest.get('success') else 'FAILED'}"
    )
    for task_name in latest.get("failed_tasks", []):
        click.echo(f"  FAILED: {task_name}")
    for task_name in latest.get("skipped_tasks", []):
        click.echo(f"  SKIPPED: {task_name}")


@cli.command(name="list")
def list_workflows() -> None:
    """List all workflows known to local storage."""
    # List from both SQLite and JSON and merge
    names = set()
    try:
        names.update(SQLiteStorage().list_workflows())
    except Exception:
        pass
    try:
        names.update(JSONStorage().list_workflows())
    except Exception:
        pass

    if not names:
        click.echo("No workflows stored yet. Run one with `pyworkflow run <file>`.")
        return
    for name in sorted(names):
        click.echo(f"  - {name}")


@cli.command()
@click.argument("name")
def stop(name: str) -> None:
    """Stop/Cancel a running workflow."""
    storage, data = _load_storage_auto(name)
    if not data:
        raise click.ClickException(f"No stored workflow found named '{name}'")

    state = data.get("state")
    pid = data.get("pid")

    if state == "RUNNING" and pid:
        import os
        import signal

        try:
            os.kill(pid, signal.SIGINT)
            click.echo(
                f"Sent stop signal (SIGINT) to workflow '{name}' running under PID {pid}."
            )
            data["state"] = "CANCELLED"
            data["pid"] = None
            storage.save_workflow(data)
        except ProcessLookupError:
            click.echo(
                f"Workflow '{name}' was marked as RUNNING with PID {pid}, but the process is not active."
            )
            data["state"] = "FAILED"
            data["pid"] = None
            storage.save_workflow(data)
    else:
        click.echo(f"Workflow '{name}' is not currently running (state: {state}).")


@cli.command()
@click.argument("name")
def pause(name: str) -> None:
    """Pause a running workflow."""
    storage, data = _load_storage_auto(name)
    if not data:
        raise click.ClickException(f"No stored workflow found named '{name}'")

    state = data.get("state")
    pid = data.get("pid")

    if state == "RUNNING" and pid:
        import os
        import signal

        sig = getattr(signal, "SIGSTOP", None)
        if sig is None:
            click.echo("Pause is not supported on this platform.")
            return
        try:
            os.kill(pid, sig)
            click.echo(
                f"Sent pause signal (SIGSTOP) to workflow '{name}' running under PID {pid}."
            )
            data["state"] = "PAUSED"
            storage.save_workflow(data)
        except ProcessLookupError:
            click.echo(f"Process with PID {pid} not found.")
    else:
        click.echo(f"Workflow '{name}' is not currently running (state: {state}).")


@cli.command()
@click.argument("name")
def resume(name: str) -> None:
    """Resume a paused workflow."""
    storage, data = _load_storage_auto(name)
    if not data:
        raise click.ClickException(f"No stored workflow found named '{name}'")

    state = data.get("state")
    pid = data.get("pid")

    if state == "PAUSED" and pid:
        import os
        import signal

        sig = getattr(signal, "SIGCONT", None)
        if sig is None:
            click.echo("Resume is not supported on this platform.")
            return
        try:
            os.kill(pid, sig)
            click.echo(
                f"Sent resume signal (SIGCONT) to workflow '{name}' running under PID {pid}."
            )
            data["state"] = "RUNNING"
            storage.save_workflow(data)
        except ProcessLookupError:
            click.echo(f"Process with PID {pid} not found.")
    else:
        click.echo(f"Workflow '{name}' is not currently paused (state: {state}).")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
