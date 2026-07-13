import pytest

from pyworkflow import DependencyError, Task, Workflow, WorkflowState


def sample_task():
    return "success"


def test_workflow_creation():
    workflow = Workflow("Demo")
    assert workflow.name == "Demo"
    assert workflow.state == WorkflowState.CREATED
    assert workflow.tasks == {}


def test_add_task():
    workflow = Workflow("Demo")
    task = Task("Sample", sample_task)
    workflow.add_task(task)
    assert len(workflow.tasks) == 1


def test_workflow_execution():
    workflow = Workflow("Execution")
    workflow.add_task(Task("Run", sample_task))
    result = workflow.run()
    assert result is not None
    assert result.success is True


def test_add_duplicate_task_raises():
    wf = Workflow("Test Workflow")
    wf.add_task(Task("A", lambda: 1))
    with pytest.raises(ValueError):
        wf.add_task(Task("A", lambda: 2))


def test_add_tasks_bulk():
    wf = Workflow("Test Workflow")
    wf.add_tasks([Task("A", sample_task), Task("B", sample_task)])
    assert len(wf.tasks) == 2


def test_then_chains_sequentially():
    wf = Workflow("Test Workflow")
    wf.add_task(Task("A", sample_task))
    wf.then(Task("B", sample_task))
    assert wf.tasks["B"].depends_on == ["A"]


def test_validate_missing_dependency_raises():
    wf = Workflow("Test Workflow")
    wf.add_task(Task("A", sample_task, depends_on=["Ghost"]))
    with pytest.raises(DependencyError):
        wf.validate()


def test_validate_cycle_raises():
    wf = Workflow("Test Workflow")
    wf.add_task(Task("A", sample_task, depends_on=["B"]))
    wf.add_task(Task("B", sample_task, depends_on=["A"]))
    with pytest.raises(DependencyError):
        wf.validate()


def test_chain_two_workflows():
    wf1 = Workflow("First")
    wf1.add_task(Task("A", lambda: "a"))

    wf2 = Workflow("Second")
    wf2.add_task(Task("B", lambda: "b"))

    combined = wf1.chain(wf2)
    assert "A" in combined.tasks and "B" in combined.tasks
    assert combined.tasks["B"].depends_on == ["A"]


def test_reset_clears_state():
    wf = Workflow("Test Workflow")
    wf.add_task(Task("A", sample_task))
    wf.run()
    assert wf.state == WorkflowState.COMPLETED
    wf.reset()
    assert wf.state == WorkflowState.CREATED
    assert wf.tasks["A"].output is None


def test_workflow_visualize():
    wf = Workflow("Viz Test")
    wf.add_task(Task("A", sample_task))
    wf.add_task(Task("B", sample_task, depends_on=["A"], condition=lambda ctx: False))
    out_text = wf.visualize()
    assert ("Workflow: Viz Test" in out_text) or out_text.endswith(".png")

    from pyworkflow.visualization.graph import render_timeline
    wf.run()
    timeline = render_timeline(wf)
    assert "Execution timeline:" in timeline


def test_workflow_visualize_graphviz(monkeypatch):
    import sys
    from unittest.mock import MagicMock

    mock_graphviz = MagicMock()
    sys.modules["graphviz"] = mock_graphviz

    try:
        wf = Workflow("Viz Graphviz")
        wf.add_task(Task("A", sample_task))
        wf.visualize(output_path="test_viz", fmt="png")
        assert mock_graphviz.Digraph.called
    finally:
        sys.modules.pop("graphviz", None)
