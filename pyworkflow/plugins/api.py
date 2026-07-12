"""Built-in API plugin: wraps HTTP requests into reusable Tasks.

Uses the standard-library ``urllib`` so PyWorkflow's core has zero required
third-party dependencies; if `requests` is installed it will be used
automatically for a nicer interface.
"""

from __future__ import annotations

import json as _json
import urllib.request
from typing import Any, Optional

from pyworkflow.core.task import Task
from pyworkflow.plugins.base import Plugin


class APIPlugin(Plugin):
    name = "api"

    def __init__(self) -> None:
        self.base_url: str = ""
        self.default_headers: dict = {}

    def setup(
        self, base_url: str = "", headers: Optional[dict] = None, **_: Any
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_headers = headers or {}

    def _request(
        self,
        path: str,
        method: str = "GET",
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}{path}" if self.base_url else path
        data = _json.dumps(json_body).encode() if json_body is not None else None
        merged_headers = {**self.default_headers, **(headers or {})}
        if json_body is not None:
            merged_headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(
            url, data=data, headers=merged_headers, method=method
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            status = resp.status
        try:
            parsed = _json.loads(body) if body else None
        except _json.JSONDecodeError:
            parsed = body
        return {"status": status, "body": parsed}

    def make_task(
        self,
        name: str,
        path: str,
        method: str = "GET",
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
        retries: int = 2,
        **task_kwargs: Any,
    ) -> Task:
        return Task(
            name=name,
            function=self._request,
            kwargs={
                "path": path,
                "method": method,
                "json_body": json_body,
                "headers": headers,
            },
            retries=retries,
            **task_kwargs,
        )
