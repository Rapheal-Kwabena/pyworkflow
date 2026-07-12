"""Built-in database plugin: wraps a DB-API 2.0 connection (e.g. sqlite3,
psycopg2) into reusable query Tasks."""

from __future__ import annotations

from typing import Any, Optional

from pyworkflow.core.task import Task
from pyworkflow.plugins.base import Plugin


class DatabasePlugin(Plugin):
    name = "database"

    def __init__(self) -> None:
        self.connection: Optional[Any] = None

    def setup(self, connection: Any, **_: Any) -> None:  # type: ignore[override]
        """`connection` must be a DB-API 2.0 compatible connection object
        (e.g. from sqlite3.connect() or psycopg2.connect())."""
        self.connection = connection

    def _execute(
        self, query: str, params: Optional[tuple] = None, fetch: bool = True
    ) -> Any:
        if self.connection is None:
            raise RuntimeError(
                "DatabasePlugin.setup() must be called before executing queries"
            )
        cursor = self.connection.cursor()
        cursor.execute(query, params or ())
        if fetch and cursor.description is not None:
            columns = [c[0] for c in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
        else:
            result = cursor.rowcount
        self.connection.commit()
        cursor.close()
        return result

    def make_task(
        self,
        name: str,
        query: str,
        params: Optional[tuple] = None,
        fetch: bool = True,
        retries: int = 1,
        **task_kwargs: Any,
    ) -> Task:
        return Task(
            name=name,
            function=self._execute,
            kwargs={"query": query, "params": params, "fetch": fetch},
            retries=retries,
            **task_kwargs,
        )
