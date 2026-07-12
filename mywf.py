"""PyWorkflow workflow definition: mywf

Run with:
    pyworkflow run mywf.py
"""

from pyworkflow import Task, Workflow


def step_one():
    print("Running step one...")
    return "step one done"


def step_two(context):
    print("Running step two, saw output:", context.get("Step One"))
    return "step two done"


workflow = Workflow("mywf")
workflow.add_task(Task("Step One", step_one))
workflow.add_task(Task("Step Two", step_two, depends_on=["Step One"]))
