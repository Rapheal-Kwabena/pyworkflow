"""Example: Scheduled Report workflow illustrating cron-based scheduling."""

import csv
import io
import time
from pyworkflow import workflow, task


@task
def gather_metrics() -> dict:
    """Collect application metrics."""
    print("Gathering application metrics...")
    return {
        "requests_total": 42350,
        "error_rate": 0.021,
        "avg_response_ms": 143.7,
        "active_users": 1821,
        "timestamp": time.time(),
    }


@task
def format_report(gather_metrics: dict) -> str:
    """Format gathered metrics into a CSV string report."""
    print("Formatting metrics into report...")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    for key, value in gather_metrics.items():
        if key != "timestamp":
            writer.writerow([key, value])
    return output.getvalue()


@task
def send_report(format_report: str) -> bool:
    """Simulate sending the report via email/webhook."""
    print("Sending report (simulated):")
    print("─" * 40)
    print(format_report)
    print("─" * 40)
    # In production: use EmailPlugin or requests.post() to send
    return True


# Build the workflow
flow = workflow("Scheduled Daily Report")
flow.add(gather_metrics)
flow.add(format_report)
flow.add(send_report)


if __name__ == "__main__":
    # Run once immediately
    print("Running scheduled report workflow...")
    report = flow.run()
    print(f"Report dispatched: {report.success}")

    # Schedule to run daily at 08:00
    # job_id = flow.schedule(mode="daily", time="08:00")
    # print(f"Scheduled daily at 08:00 (job_id={job_id})")
