"""Built-in email plugin: turns SMTP sending into a reusable Task factory."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any, Optional

from pyworkflow.core.task import Task
from pyworkflow.plugins.base import Plugin


class EmailPlugin(Plugin):
    name = "email"

    def __init__(self) -> None:
        self.host: Optional[str] = None
        self.port: int = 587
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.use_tls: bool = True

    def setup(  # type: ignore[override]
        self,
        host: str,
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        **_: Any,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def _send(
        self, to: str, subject: str, body: str, from_addr: Optional[str] = None
    ) -> str:
        if not self.host:
            raise RuntimeError("EmailPlugin.setup() must be called before sending mail")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr or self.username or "pyworkflow@localhost"
        msg["To"] = to
        msg.set_content(body)

        with smtplib.SMTP(self.host, self.port, timeout=15) as server:
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.send_message(msg)
        return f"email sent to {to}"

    def make_task(
        self,
        name: str,
        to: str,
        subject: str,
        body: str,
        retries: int = 2,
        **task_kwargs: Any,
    ) -> Task:
        """Build a Task that sends this email when the workflow runs."""
        return Task(
            name=name,
            function=self._send,
            kwargs={"to": to, "subject": subject, "body": body},
            retries=retries,
            **task_kwargs,
        )
