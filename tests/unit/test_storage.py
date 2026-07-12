from pyworkflow.storage.json_storage import JSONStorage
from pyworkflow.storage.sqlite_storage import SQLiteStorage


def test_save_workflow(tmp_path):
    storage = JSONStorage(tmp_path)
    data = {"name": "test"}
    storage.save("workflow.json", data)
    result = storage.load("workflow.json")
    assert result["name"] == "test"


def test_json_storage_save_and_get_workflow(tmp_path):
    storage = JSONStorage(root=str(tmp_path))
    storage.save_workflow({"name": "WF1", "state": "COMPLETED", "tasks": []})
    result = storage.get_workflow("WF1")
    assert result["name"] == "WF1"
    assert result["state"] == "COMPLETED"


def test_json_storage_missing_workflow_returns_none(tmp_path):
    storage = JSONStorage(root=str(tmp_path))
    assert storage.get_workflow("Nonexistent") is None


def test_json_storage_list_workflows(tmp_path):
    storage = JSONStorage(root=str(tmp_path))
    storage.save_workflow({"name": "A", "tasks": []})
    storage.save_workflow({"name": "B", "tasks": []})
    assert storage.list_workflows() == ["A", "B"]


def test_json_storage_run_history(tmp_path):
    storage = JSONStorage(root=str(tmp_path))
    storage.save_run("WF1", {"success": True})
    storage.save_run("WF1", {"success": False})
    history = storage.get_history("WF1")
    assert len(history) == 2
    assert history[0]["success"] is True
    assert history[1]["success"] is False


def test_json_storage_delete_workflow(tmp_path):
    storage = JSONStorage(root=str(tmp_path))
    storage.save_workflow({"name": "WF1", "tasks": []})
    storage.save_run("WF1", {"success": True})
    storage.delete_workflow("WF1")
    assert storage.get_workflow("WF1") is None
    assert storage.get_history("WF1") == []


def test_sqlite_storage_save_and_get_workflow(tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path=str(db_path))
    storage.save_workflow({"name": "WF1", "state": "COMPLETED", "tasks": []})
    result = storage.get_workflow("WF1")
    assert result["name"] == "WF1"
    storage.close()


def test_sqlite_storage_run_history(tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path=str(db_path))
    storage.save_run("WF1", {"success": True})
    storage.save_run("WF1", {"success": False})
    history = storage.get_history("WF1")
    assert len(history) == 2
    storage.close()


def test_sqlite_storage_upsert_workflow(tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path=str(db_path))
    storage.save_workflow({"name": "WF1", "state": "CREATED", "tasks": []})
    storage.save_workflow({"name": "WF1", "state": "COMPLETED", "tasks": []})
    result = storage.get_workflow("WF1")
    assert result["state"] == "COMPLETED"
    assert storage.list_workflows() == ["WF1"]
    storage.close()
