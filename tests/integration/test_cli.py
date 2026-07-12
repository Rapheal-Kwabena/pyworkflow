import os
import sys
import site
import subprocess
import pytest
from click.testing import CliRunner

from pyworkflow.cli.main import cli


def test_cli_exists():
    cmd = "pyworkflow"
    # Attempt to locate the command in typical Python user-site bin directories
    for base in [
        os.path.join(site.getuserbase(), "bin"),
        os.path.expanduser("~/Library/Python/3.9/bin"),
    ]:
        candidate = os.path.join(base, "pyworkflow")
        if os.path.exists(candidate):
            cmd = candidate
            break

    try:
        result = subprocess.run([cmd, "--help"], capture_output=True, text=True)
        # If it wasn't found (FileNotFoundError), we'll catch and fallback below
    except FileNotFoundError:
        result = None

    if result is None or result.returncode != 0:
        # Fallback to invoking the Python module directly
        result = subprocess.run(
            [sys.executable, "-m", "pyworkflow.cli.main", "--help"],
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0


def test_cli_create_scaffolds_file(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["create", "mywf"])
        assert result.exit_code == 0
        assert os.path.exists("mywf.py")
        content = open("mywf.py").read()
        assert "workflow = Workflow" in content


def test_cli_create_refuses_overwrite(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["create", "mywf"])
        result = runner.invoke(cli, ["create", "mywf"])
        assert result.exit_code != 0


def test_cli_run_executes_workflow(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["create", "mywf"])
        result = runner.invoke(cli, ["run", "mywf.py"])
        assert result.exit_code == 0
        assert "completed successfully" in result.output


def test_cli_list_after_run(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["create", "mywf"])
        runner.invoke(cli, ["run", "mywf.py"])
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "mywf" in result.output


def test_cli_status_unknown_workflow_errors(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["status", "NoSuchWorkflow"])
        assert result.exit_code != 0


def test_cli_history_export(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["create", "mywf"])
        runner.invoke(cli, ["run", "mywf.py"])

        export_file = str(tmp_path / "history_export.json")
        result = runner.invoke(cli, ["history", "mywf", "--export", export_file])
        assert result.exit_code == 0
        assert "Exported history of" in result.output

        import json

        assert os.path.exists(export_file)
        data = json.loads(open(export_file).read())
        assert len(data) > 0
        assert data[0]["success"] is True


def test_cli_stop_pause_resume_mocked(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("HOME", str(tmp_path))

    killed_calls = []

    def mock_kill(pid, sig):
        killed_calls.append((pid, sig))

    monkeypatch.setattr(os, "kill", mock_kill)

    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["create", "mywf"])
        runner.invoke(cli, ["run", "mywf.py", "--storage-type", "json"])

        from pyworkflow.storage.json_storage import JSONStorage

        storage = JSONStorage(root=str(tmp_path / ".pyworkflow"))
        data = storage.get_workflow("mywf")
        data["state"] = "RUNNING"
        data["pid"] = 99999
        storage.save_workflow(data)

        result = runner.invoke(cli, ["stop", "mywf"])
        assert result.exit_code == 0
        assert "Sent stop signal" in result.output
        assert killed_calls == [(99999, 2)]

        data = storage.get_workflow("mywf")
        data["state"] = "RUNNING"
        data["pid"] = 99999
        storage.save_workflow(data)

        killed_calls.clear()
        result = runner.invoke(cli, ["pause", "mywf"])
        assert result.exit_code == 0
        assert "Sent pause signal" in result.output
        import signal

        sigstop = getattr(signal, "SIGSTOP", None)
        if sigstop is not None:
            assert killed_calls == [(99999, sigstop)]

        data = storage.get_workflow("mywf")
        data["state"] = "PAUSED"
        data["pid"] = 99999
        storage.save_workflow(data)

        killed_calls.clear()
        result = runner.invoke(cli, ["resume", "mywf"])
        assert result.exit_code == 0
        assert "Sent resume signal" in result.output
        sigcont = getattr(signal, "SIGCONT", None)
        if sigcont is not None:
            assert killed_calls == [(99999, sigcont)]
