from pyworkflow import Task, Workflow


def task():
    return "done"


def create_workflow():
    workflow = Workflow("Benchmark")

    for i in range(100):
        workflow.add_task(Task(f"task-{i}", task))

    return workflow


def test_workflow_speed(benchmark):
    workflow = create_workflow()
    benchmark(workflow.run)
