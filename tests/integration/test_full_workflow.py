from pyworkflow import Task, Workflow


def download():
    return "data"


def process():
    return "processed"


def upload():
    return "uploaded"


def test_complete_pipeline():
    workflow = Workflow("Data Pipeline")

    workflow.add_task(Task("Download", download))
    workflow.add_task(Task("Process", process))
    workflow.add_task(Task("Upload", upload))

    result = workflow.run()
    assert result is not None
    assert result.success is True
