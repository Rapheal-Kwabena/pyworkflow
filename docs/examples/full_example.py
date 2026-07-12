"""A runnable, self-contained example exercising most of PyWorkflow's core
features: dependencies, parallel execution, retries, conditionals, and
reporting.

Run with:
    python docs/examples/full_example.py
"""

from __future__ import annotations

import random
import time

from pyworkflow import Task, Workflow


def download_data():
    time.sleep(0.05)
    return {"rows": 1000, "region": "global"}


def validate_data(context):
    data = context["Download Data"]
    if data["rows"] <= 0:
        raise ValueError("No rows downloaded")
    return {"valid": True}


def flaky_upstream_sync():
    # Simulates an occasionally-flaky network call; retries will handle this.
    if random.random() < 0.5:
        raise ConnectionError("upstream sync timed out")
    return "synced"


def clean_data(context):
    data = context["Download Data"]
    return {"rows": data["rows"] - 12}


def should_alert(context):
    return context["Clean Data"]["rows"] < 500


def send_alert():
    print("  -> ALERT: row count dropped below threshold!")
    return "alert sent"


def analyze_data(context):
    rows = context["Clean Data"]["rows"]
    return f"Analyzed {rows} rows successfully"


def build_workflow() -> Workflow:
    workflow = Workflow("Full Example Pipeline", max_workers=4)

    workflow.add_task(Task("Download Data", download_data))
    workflow.add_task(
        Task("Sync Upstream", flaky_upstream_sync, retries=3, retry_delay=0.1)
    )
    workflow.add_task(
        Task("Validate Data", validate_data, depends_on=["Download Data"])
    )
    workflow.add_task(
        Task(
            "Clean Data",
            clean_data,
            depends_on=["Validate Data"],
        )
    )
    workflow.add_task(
        Task(
            "Send Alert",
            send_alert,
            depends_on=["Clean Data"],
            condition=should_alert,
        )
    )
    workflow.add_task(
        Task(
            "Analyze Data",
            analyze_data,
            depends_on=["Clean Data", "Sync Upstream"],
        )
    )
    return workflow


if __name__ == "__main__":
    workflow = build_workflow()
    report = workflow.run(parallel=True)

    print(f"\nWorkflow '{workflow.name}' finished. Success={report.success}")
    for name, task in workflow.tasks.items():
        print(f"  - {name}: {task.state.value}"
              + (f" -> {task.output}" if task.output is not None else ""))

    if not report.success:
        print("Failed tasks:", report.failed_tasks)
