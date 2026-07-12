"""A lightweight, dependency-free scheduler for running workflows.

Supports four scheduling modes:

* ``now``       - run immediately (blocking)
* ``delay``     - run once after N seconds
* ``interval``  - run every N seconds, repeatedly
* ``cron``      - run according to a 5-field cron expression

The scheduler runs on a background thread so the calling program is not
blocked. It does not depend on any third-party cron library; a minimal
cron-expression matcher is implemented in :mod:`pyworkflow.scheduler.cron`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyworkflow.exceptions import SchedulerError
from pyworkflow.scheduler.cron import next_run_time


@dataclass
class ScheduledJob:
    id: str
    workflow_name: str
    run_fn: Callable[[], None]
    mode: str
    next_run: Optional[float] = None
    interval: Optional[float] = None
    cron_expr: Optional[str] = None
    enabled: bool = True
    last_run: Optional[float] = None
    last_error: Optional[str] = None


class Scheduler:
    """Manages one or more scheduled workflow runs on a background thread."""

    def __init__(self, poll_interval: float = 1.0) -> None:
        self.poll_interval = poll_interval
        self._jobs: dict[str, ScheduledJob] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._counter = 0

    # -- job registration -------------------------------------------------
    def run_now(self, workflow_name: str, run_fn: Callable[[], None]) -> str:
        job_id = self._next_id()
        run_fn()
        with self._lock:
            self._jobs[job_id] = ScheduledJob(
                id=job_id,
                workflow_name=workflow_name,
                run_fn=run_fn,
                mode="now",
                last_run=time.time(),
            )
        return job_id

    def run_after(
        self, workflow_name: str, run_fn: Callable[[], None], delay: float
    ) -> str:
        if delay < 0:
            raise SchedulerError("delay must be >= 0")
        job_id = self._next_id()
        job = ScheduledJob(
            id=job_id,
            workflow_name=workflow_name,
            run_fn=run_fn,
            mode="delay",
            next_run=time.time() + delay,
        )
        self._add_job(job)
        return job_id

    def run_every(
        self, workflow_name: str, run_fn: Callable[[], None], interval_minutes: float
    ) -> str:
        if interval_minutes <= 0:
            raise SchedulerError("interval_minutes must be > 0")
        interval_seconds = interval_minutes * 60
        job_id = self._next_id()
        job = ScheduledJob(
            id=job_id,
            workflow_name=workflow_name,
            run_fn=run_fn,
            mode="interval",
            interval=interval_seconds,
            next_run=time.time() + interval_seconds,
        )
        self._add_job(job)
        return job_id

    def run_cron(
        self, workflow_name: str, run_fn: Callable[[], None], cron_expr: str
    ) -> str:
        job_id = self._next_id()
        nxt = next_run_time(cron_expr, time.time())
        job = ScheduledJob(
            id=job_id,
            workflow_name=workflow_name,
            run_fn=run_fn,
            mode="cron",
            cron_expr=cron_expr,
            next_run=nxt,
        )
        self._add_job(job)
        return job_id

    def run_daily(self, workflow_name: str, run_fn: Callable[[], None], at: str) -> str:
        """Convenience wrapper: schedule daily at HH:MM, e.g. at='08:00'."""
        try:
            hour, minute = (int(x) for x in at.split(":"))
        except ValueError as exc:
            raise SchedulerError(f"Invalid time format '{at}', expected HH:MM") from exc
        return self.run_cron(workflow_name, run_fn, f"{minute} {hour} * * *")

    def schedule(
        self,
        workflow_name: str,
        interval: str,
        run_fn: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> ScheduledJob:
        """Map generic schedule request to concrete scheduler methods."""
        fn = run_fn or (lambda: None)
        if interval == "daily":
            at_time = kwargs.get("at", "12:00")
            job_id = self.run_daily(workflow_name, fn, at_time)
        elif interval == "cron":
            cron_expr = kwargs.get("cron", "* * * * *")
            job_id = self.run_cron(workflow_name, fn, cron_expr)
        else:
            try:
                mins = float(interval)
            except ValueError:
                mins = 1.0
            job_id = self.run_every(workflow_name, fn, mins)

        with self._lock:
            return self._jobs[job_id]

    # -- lifecycle ---------------------------------------------------------
    def _add_job(self, job: ScheduledJob) -> None:
        with self._lock:
            self._jobs[job.id] = job
        self.start()

    def _next_id(self) -> str:
        self._counter += 1
        return f"job-{self._counter}"

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval * 2)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def jobs(self) -> list[ScheduledJob]:
        with self._lock:
            return list(self._jobs.values())

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                due = [
                    j
                    for j in self._jobs.values()
                    if j.enabled and j.next_run and j.next_run <= now
                ]
            for job in due:
                self._fire(job)
            self._stop_event.wait(self.poll_interval)

    def _fire(self, job: ScheduledJob) -> None:
        try:
            job.run_fn()
            job.last_error = None
        except Exception as exc:  # noqa: BLE001
            job.last_error = str(exc)
        job.last_run = time.time()

        with self._lock:
            if job.mode == "delay":
                self._jobs.pop(job.id, None)
            elif job.mode == "interval" and job.interval:
                job.next_run = time.time() + job.interval
            elif job.mode == "cron" and job.cron_expr:
                job.next_run = next_run_time(job.cron_expr, time.time())
