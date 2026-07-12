import pytest
import time

from pyworkflow import Task, TaskState, Workflow, TaskExecutionError


def hello():
    return "hello"


def fail():
    raise ValueError("error")


def test_task_creation():
    task = Task("Hello", hello)
    assert task.name == "Hello"


def test_task_output():
    task = Task("Hello", hello)
    result = task.execute()
    assert result == "hello"


def test_task_failure():
    task = Task("Fail", fail)
    with pytest.raises(ValueError):
        task.execute()


def test_sequential_execution_order():
    order = []

    def make(name):
        def fn():
            order.append(name)
            return name

        return fn

    wf = Workflow("Sequential")
    wf.add_task(Task("A", make("A")))
    wf.add_task(Task("B", make("B"), depends_on=["A"]))
    wf.add_task(Task("C", make("C"), depends_on=["B"]))
    report = wf.run()

    assert report.success
    assert order == ["A", "B", "C"]


def test_parallel_execution_runs_independent_tasks():
    wf = Workflow("Parallel", max_workers=4)
    wf.add_task(Task("A", lambda: "a"))
    wf.add_task(Task("B", lambda: "b"))
    wf.add_task(Task("C", lambda: "c", depends_on=["A", "B"]))

    report = wf.run(parallel=True)
    assert report.success
    assert wf.tasks["C"].state == TaskState.COMPLETED
    assert wf.tasks["C"].output == "c"


def test_context_passed_between_tasks():
    def produce():
        return 42

    def consume(context):
        return context["Produce"] * 2

    wf = Workflow("Context Passing")
    wf.add_task(Task("Produce", produce))
    wf.add_task(Task("Consume", consume, depends_on=["Produce"]))
    report = wf.run()

    assert report.success
    assert wf.tasks["Consume"].output == 84


def test_conditional_task_is_skipped():
    wf = Workflow("Conditional")
    wf.add_task(Task("A", lambda: "go"))
    wf.add_task(
        Task(
            "B",
            lambda: "should not run",
            depends_on=["A"],
            condition=lambda context: context["A"] == "stop",
        )
    )
    report = wf.run()

    assert wf.tasks["B"].state == TaskState.SKIPPED
    assert "B" in report.skipped_tasks


def test_task_with_args_and_kwargs():
    def add(a, b, c=0):
        return a + b + c

    wf = Workflow("Args")
    wf.add_task(Task("Add", add, args=(1, 2), kwargs={"c": 3}))
    wf.run()
    assert wf.tasks["Add"].output == 6


def test_failed_task_marks_workflow_failed():
    def boom():
        raise ValueError("kaboom")

    wf = Workflow("Failing")
    wf.add_task(Task("Boom", boom))
    report = wf.run()

    assert not report.success
    assert "Boom" in report.failed_tasks
    assert wf.tasks["Boom"].state == TaskState.FAILED


def test_downstream_task_not_run_after_upstream_failure():
    def boom():
        raise ValueError("kaboom")

    ran = []

    wf = Workflow("Stop On Failure", stop_on_failure=True)
    wf.add_task(Task("Boom", boom))
    wf.add_task(Task("After", lambda: ran.append("After"), depends_on=["Boom"]))
    wf.run()

    assert wf.tasks["After"].state == TaskState.PENDING
    assert not ran


def test_task_retries_before_succeeding():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("not yet")
        return "success"

    task = Task("Flaky", flaky, retries=3, retry_delay=0)
    result = task.run(context={})

    assert result.state == TaskState.COMPLETED
    assert attempts["count"] == 3
    assert task.output == "success"


def test_task_exhausts_retries_and_raises():
    def always_fails():
        raise RuntimeError("nope")

    task = Task("AlwaysFails", always_fails, retries=2, retry_delay=0)
    with pytest.raises(TaskExecutionError):
        task.run(context={})

    assert task.state == TaskState.FAILED
    assert task.attempts == 3


def test_on_failure_callback_invoked():
    captured = {}

    def fail_fn():
        raise ValueError("bad")

    def on_fail(task, exc):
        captured["task_name"] = task.name
        captured["exception"] = str(exc)

    task = Task("Failing", fail_fn, retries=0, on_failure=on_fail)
    with pytest.raises(TaskExecutionError):
        task.run(context={})

    assert captured["task_name"] == "Failing"
    assert "bad" in captured["exception"]


def test_workflow_retry_failed_tasks():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("first attempt fails")
        return "ok"

    wf = Workflow("Retry Workflow")
    wf.add_task(Task("Flaky", flaky, retries=0))
    report = wf.run()
    assert not report.success

    report2 = wf.retry_failed_tasks()
    assert report2.success
    assert wf.tasks["Flaky"].output == "ok"


def test_task_history_records_every_attempt():
    def always_fails():
        raise RuntimeError("nope")

    task = Task("AlwaysFails", always_fails, retries=2, retry_delay=0)
    with pytest.raises(TaskExecutionError):
        task.run(context={})

    assert len(task.history) == 3
    assert all(r.state == TaskState.FAILED for r in task.history)


def test_workflow_retry_resets_downstream_tasks():
    attempts = {"A": 0, "B": 0}

    def fn_a():
        attempts["A"] += 1
        if attempts["A"] == 1:
            raise RuntimeError("A failed")
        return "a_val"

    def fn_b(context):
        attempts["B"] += 1
        assert context.get("A") == "a_val"
        return "b_val"

    wf = Workflow("Retry Downstream Reset")
    wf.add_task(Task("A", fn_a))
    wf.add_task(Task("B", fn_b, depends_on=["A"]))

    report1 = wf.run()
    assert not report1.success
    assert wf.tasks["A"].state == TaskState.FAILED
    assert wf.tasks["B"].state == TaskState.PENDING

    report2 = wf.retry_failed_tasks()
    assert report2.success
    assert wf.tasks["A"].state == TaskState.COMPLETED
    assert wf.tasks["B"].state == TaskState.COMPLETED
    assert wf.tasks["A"].output == "a_val"
    assert wf.tasks["B"].output == "b_val"
    assert attempts["A"] == 2
    assert attempts["B"] == 1
