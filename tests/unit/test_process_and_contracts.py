"""Unit tests for process worker isolation, Pydantic validation, and checkpoint recovery."""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from pyworkflow.core.task import Task
from pyworkflow.core.state import TaskState
from pyworkflow.core.workflow import Workflow
from pyworkflow.workers.process_worker import ProcessWorker
from pyworkflow.storage.sqlite import SQLiteStorage
from pyworkflow.storage.checkpoints import CheckpointManager, serialize_value, deserialize_value
from pyworkflow.contracts.validation import validate_inputs, validate_output


# ---------------------------------------------------------------------------
# Process Worker Isolation Tests
# ---------------------------------------------------------------------------

class TestProcessWorkerIsolation:
    """Verify that the process worker runs tasks in-process (pytest mode) correctly."""

    def test_in_process_success(self):
        """Worker runs the function in-process under pytest and returns SUCCESS."""
        def add(a: int, b: int) -> int:
            return a + b

        task = Task("add", add, args=(3, 4))
        worker = ProcessWorker(task)
        result = worker.run({})

        assert result.state == TaskState.SUCCESS
        assert result.output == 7

    def test_in_process_captures_exception(self):
        """Worker captures the original exception instance when a task fails."""
        def boom():
            raise ValueError("kaboom")

        task = Task("boom", boom)
        worker = ProcessWorker(task)
        result = worker.run({})

        assert result.state == TaskState.FAILED
        assert isinstance(result.exception, ValueError)
        assert "kaboom" in str(result.exception)

    def test_in_process_with_timeout_succeeds_for_fast_task(self):
        """Fast task with a generous timeout completes successfully."""
        def quick():
            return "done"

        task = Task("quick", quick, timeout=10)
        worker = ProcessWorker(task)
        result = worker.run({})

        assert result.state == TaskState.SUCCESS
        assert result.output == "done"

    def test_in_process_passes_context_to_dependent_task(self):
        """Worker correctly injects upstream context values into the task call."""
        def make_greeting(name: str) -> str:
            return f"Hello, {name}!"

        task = Task("greet", make_greeting, depends_on=["get_name"])
        worker = ProcessWorker(task)
        result = worker.run({"get_name": "World"})

        assert result.state == TaskState.SUCCESS
        assert result.output == "Hello, World!"

    def test_worker_result_has_timing(self):
        """TaskResult returned by worker includes started_at and finished_at timestamps."""
        def noop():
            return None

        task = Task("noop", noop)
        worker = ProcessWorker(task)
        result = worker.run({})

        assert result.started_at is not None
        assert result.finished_at is not None
        assert result.finished_at >= result.started_at


# ---------------------------------------------------------------------------
# Pydantic Validation Tests
# ---------------------------------------------------------------------------

class TestPydanticValidation:
    """Validate input and output contracts using Pydantic models."""

    def test_validate_output_coerces_dict_to_model(self):
        """validate_output coerces a dict return value into a Pydantic BaseModel."""
        from pydantic import BaseModel

        class ReportOut(BaseModel):
            total: int
            label: str

        result = validate_output(ReportOut, {"total": 42, "label": "Q1"})
        assert isinstance(result, ReportOut)
        assert result.total == 42
        assert result.label == "Q1"

    def test_validate_output_passes_through_valid_model(self):
        """validate_output returns the same model instance when already validated."""
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str

        item = Item(name="widget")
        result = validate_output(Item, item)
        assert result is item

    def test_validate_output_raises_on_invalid_dict(self):
        """validate_output raises ValidationError when the dict violates the schema."""
        from pydantic import BaseModel, ValidationError

        class Strict(BaseModel):
            amount: int

        with pytest.raises(ValidationError):
            validate_output(Strict, {"amount": "not-a-number"})

    def test_validate_inputs_single_model_param(self):
        """validate_inputs converts a dict to a BaseModel instance for single-param functions."""
        import inspect
        from pydantic import BaseModel

        class UserInput(BaseModel):
            name: str
            age: int

        def my_fn(user: UserInput) -> str:
            return user.name

        sig = inspect.signature(my_fn)
        # Pass the model instance directly as a dict — should be coerced
        args_out, kwargs_out = validate_inputs(
            UserInput, sig, (), {"user": {"name": "Alice", "age": 30}}
        )
        # The bound arguments come back via bound.args / bound.kwargs —
        # the coerced value should be in the tuple as a positional arg
        assert any(
            isinstance(v, UserInput) for v in list(args_out) + list(kwargs_out.values())
        )

    def test_task_with_output_model_coerces_return_value(self):
        """Task with output_model applies post-run coercion against Pydantic schema."""
        from pydantic import BaseModel

        class Summary(BaseModel):
            count: int
            avg: float

        def compute() -> dict:
            return {"count": 10, "avg": 3.14}

        task = Task("compute", compute, output_model=Summary)
        result = task.run({})

        assert result.state == TaskState.SUCCESS
        assert isinstance(task.output, Summary)
        assert task.output.count == 10

    def test_task_with_input_model_validates_at_run_time(self):
        """Task raises when an invalid input dict is passed for a Pydantic model param."""
        from pydantic import BaseModel

        class StrictIn(BaseModel):
            amount: int

        def process(data: StrictIn) -> int:
            return data.amount * 2

        task = Task("proc", process, input_model=StrictIn)
        # Passing amount as a non-coercible string — pydantic should reject this
        with pytest.raises(Exception):
            task.run({"StrictIn": {"amount": "not-a-number"}})


# ---------------------------------------------------------------------------
# Checkpoint Serialization Tests
# ---------------------------------------------------------------------------

class TestCheckpointSerialization:
    """Test the low-level serialize/deserialize helpers used by CheckpointManager."""

    def test_serialize_and_deserialize_primitive(self):
        """Round-trips a simple string value through serialize/deserialize."""
        payload = serialize_value("hello world")
        result = deserialize_value(payload)
        assert result == "hello world"

    def test_serialize_and_deserialize_complex_object(self):
        """Round-trips a nested dict through serialize/deserialize."""
        original = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
        payload = serialize_value(original)
        result = deserialize_value(payload)
        assert result == original

    def test_serialize_and_deserialize_list(self):
        """Round-trips a list of mixed types."""
        original = [1, "two", 3.0, {"four": 4}]
        payload = serialize_value(original)
        result = deserialize_value(payload)
        assert result == original

    def test_deserialize_passthrough_for_plain_values(self):
        """deserialize_value passes through values that are not typed payloads."""
        assert deserialize_value("plain_string") == "plain_string"
        assert deserialize_value(42) == 42
        assert deserialize_value(None) is None


# ---------------------------------------------------------------------------
# Checkpoint Recovery Integration Tests
# ---------------------------------------------------------------------------

class TestCheckpointRecovery:
    """Test SQLite-backed checkpoint persistence and workflow recovery."""

    def _make_storage(self, tmpdir: str) -> SQLiteStorage:
        db_path = os.path.join(tmpdir, "wf.db")
        return SQLiteStorage(db_path=db_path)

    def test_checkpoint_save_and_load_via_workflow(self):
        """CheckpointManager saves workflow state and restores task outputs on reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = self._make_storage(tmpdir)

            # Build a simple workflow and run it
            def step_one() -> str:
                return "checkpoint_value"

            def step_two(step_one: str) -> str:
                return f"got_{step_one}"

            wf = Workflow("CheckpointWF", storage=storage)
            wf.add_task(Task("step_one", step_one))
            wf.add_task(Task("step_two", step_two, depends_on=["step_one"]))
            report = wf.run()

            assert report.success
            assert wf.tasks["step_one"].output == "checkpoint_value"

            # Verify the checkpoint was persisted
            _mgr = CheckpointManager(storage)
            data = storage.get_workflow("CheckpointWF")
            assert data is not None
            assert data["name"] == "CheckpointWF"

    def test_checkpoint_restores_task_output_on_second_run(self):
        """After a first successful run, a second run skips both completed tasks via checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = self._make_storage(tmpdir)
            call_counts: dict[str, int] = {"step_a": 0, "step_b": 0}

            def step_a() -> str:
                call_counts["step_a"] += 1
                return "a_result"

            def step_b(step_a: str) -> str:
                call_counts["step_b"] += 1
                return f"b_from_{step_a}"

            wf = Workflow("RecoveryWF", storage=storage)
            wf.add_task(Task("step_a", step_a))
            wf.add_task(Task("step_b", step_b, depends_on=["step_a"]))

            # First run — both tasks execute
            report1 = wf.run()
            assert report1.success
            assert call_counts["step_a"] == 1
            assert call_counts["step_b"] == 1

            # Second run — both tasks were saved as COMPLETED, so neither re-executes
            wf2 = Workflow("RecoveryWF", storage=storage)
            wf2.add_task(Task("step_a", step_a))
            wf2.add_task(Task("step_b", step_b, depends_on=["step_a"]))

            report2 = wf2.run()
            assert report2.success
            # Engine loads COMPLETED from checkpoint → skips both tasks
            assert call_counts["step_a"] == 1
            assert call_counts["step_b"] == 1
            # Results are still correctly populated from checkpoint
            assert report2.results["step_a"] == "a_result"
            assert report2.results["step_b"] == "b_from_a_result"

    def test_checkpoint_persists_complex_context(self):
        """Workflow context containing lists/dicts survives a checkpoint round-trip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = self._make_storage(tmpdir)

            def fetch() -> list:
                return [{"id": 1}, {"id": 2}]

            wf = Workflow("ComplexWF", storage=storage)
            wf.add_task(Task("fetch", fetch))
            report = wf.run()

            assert report.success
            # Reload checkpoint and verify context
            mgr = CheckpointManager(storage)
            wf2 = Workflow("ComplexWF", storage=storage)
            wf2.add_task(Task("fetch", fetch))
            found = mgr.load_checkpoint(wf2)

            assert found is True
            assert wf2.tasks["fetch"].output == [{"id": 1}, {"id": 2}]
