import urllib.request
import smtplib
from pyworkflow import Workflow, Task
from pyworkflow.plugins import PluginManager, registry, EmailPlugin, DatabasePlugin, APIPlugin, AIPlugin


def test_plugin_registration():
    manager = PluginManager()
    manager.register("email")
    assert "email" in manager.plugins


def test_email_plugin(monkeypatch):
    sent_mails = []

    class MockSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def starttls(self):
            pass

        def login(self, user, pwd):
            pass

        def send_message(self, msg):
            sent_mails.append(msg)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(smtplib, "SMTP", MockSMTP)

    email_plugin = EmailPlugin()
    email_plugin.setup(host="smtp.gmail.com", username="user@gmail.com", password="pwd")

    task = email_plugin.make_task("SendMail", to="test@example.com", subject="Hello", body="World")
    wf = Workflow("Email WF")
    wf.add_task(task)
    report = wf.run()

    assert report.success is True
    assert len(sent_mails) == 1
    assert sent_mails[0]["To"] == "test@example.com"


def test_api_plugin(monkeypatch):
    class MockResponse:
        def __init__(self):
            self.status = 200

        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=None):
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    api_plugin = APIPlugin()
    api_plugin.setup(base_url="https://api.example.com")

    task = api_plugin.make_task("FetchAPI", path="/users")
    wf = Workflow("API WF")
    wf.add_task(task)
    report = wf.run()

    assert report.success is True
    assert wf.tasks["FetchAPI"].output["status"] == 200
    assert wf.tasks["FetchAPI"].output["body"] == {"ok": True}


def test_ai_plugin():
    called_prompts = []

    def mock_call_fn(prompt, model=None):
        called_prompts.append((prompt, model))
        if "choices" in prompt or "one of these options" in prompt:
            return "choice_1"
        if "Suggest a structured" in prompt:
            return '{"workflow_name": "Suggested", "tasks": []}'
        return "ai response"

    ai_plugin = AIPlugin()
    ai_plugin.setup(call_fn=mock_call_fn, model="openrouter")

    task1 = ai_plugin.make_task("AITask", prompt="Summarize this")
    task2 = ai_plugin.make_decision_task("AIDecision", question="Choose?", choices=["choice_1", "choice_2"])

    wf = Workflow("AI WF")
    wf.add_task(task1)
    wf.add_task(task2)
    report = wf.run()

    assert report.success is True
    assert wf.tasks["AITask"].output == "ai response"
    assert wf.tasks["AIDecision"].output == "choice_1"
