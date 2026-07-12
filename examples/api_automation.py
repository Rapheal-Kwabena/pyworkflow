"""Example: API Automation workflow showcasing parallel branch execution."""

import time
from pyworkflow import workflow, task


@task
def query_api_endpoint(endpoint: str) -> dict:
    """Simulate query to external API endpoint."""
    print(f"Querying endpoint: {endpoint}...")
    time.sleep(0.3)
    if endpoint == "users":
        return {
            "status": 200,
            "data": [{"id": 1, "role": "admin"}, {"id": 2, "role": "user"}],
        }
    elif endpoint == "status":
        return {"status": 200, "data": {"health": "OK", "db": "connected"}}
    return {"status": 404, "data": {}}


@task
def process_users_role(query_users_api: dict) -> list[int]:
    """Extract admin user ids from API response."""
    print("Processing user roles...")
    admins = [u["id"] for u in query_users_api["data"] if u["role"] == "admin"]
    return admins


@task
def process_system_health(query_health_api: dict) -> str:
    """Extract health metric from status API response."""
    print("Processing system health status...")
    return query_health_api["data"]["health"]


@task
def aggregate_report(
    process_users_role: list[int], process_system_health: str
) -> dict:
    """Combine results from independent processing tasks."""
    print("Aggregating API report...")
    return {
        "admin_ids": process_users_role,
        "system_health": process_system_health,
        "timestamp": time.time(),
    }


# Build workflow
flow = workflow("API Automation Workflow")

# Instantiate query tasks with specific names and arguments
task_users = query_api_endpoint.get_task()
task_users.name = "query_users_api"
task_users.args = ("users",)

task_health = query_api_endpoint.get_task()
task_health.name = "query_health_api"
task_health.args = ("status",)

task_proc_users = process_users_role.get_task()
task_proc_users.depends_on = ["query_users_api"]

task_proc_health = process_system_health.get_task()
task_proc_health.depends_on = ["query_health_api"]

task_agg = aggregate_report.get_task()
task_agg.depends_on = ["process_users_role", "process_system_health"]

flow.add_task(task_users)
flow.add_task(task_health)
flow.add_task(task_proc_users)
flow.add_task(task_proc_health)
flow.add_task(task_agg)

if __name__ == "__main__":
    print("Running parallel branches:")
    report = flow.run(parallel=True)
    print(f"API Flow run success: {report.success}")
    if report.success:
        print(f"Aggregated Result: {report.results['aggregate_report']}")
