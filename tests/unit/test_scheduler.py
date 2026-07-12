import time
from datetime import datetime

import pytest

from pyworkflow.exceptions import SchedulerError
from pyworkflow.scheduler.cron import matches, next_run_time, parse_cron
from pyworkflow.scheduler.scheduler import Scheduler


def test_scheduler_creation():
    scheduler = Scheduler()
    assert scheduler is not None


def test_schedule_task():
    scheduler = Scheduler()
    job = scheduler.schedule("test", interval="daily")
    assert job is not None


def test_run_now_executes_immediately():
    calls = []
    scheduler = Scheduler()
    scheduler.run_now("wf", lambda: calls.append(1))
    assert calls == [1]


def test_run_after_delay_executes_once():
    calls = []
    scheduler = Scheduler(poll_interval=0.05)
    scheduler.run_after("wf", lambda: calls.append(1), delay=0.1)
    time.sleep(0.4)
    scheduler.stop()
    assert calls == [1]


def test_run_every_executes_multiple_times():
    calls = []
    scheduler = Scheduler(poll_interval=0.05)
    scheduler.run_every("wf", lambda: calls.append(1), interval_minutes=0.002)  # 0.12s
    time.sleep(0.5)
    scheduler.stop()
    assert len(calls) >= 2


def test_cancel_job_prevents_future_runs():
    calls = []
    scheduler = Scheduler(poll_interval=0.05)
    job_id = scheduler.run_after("wf", lambda: calls.append(1), delay=0.2)
    scheduler.cancel(job_id)
    time.sleep(0.4)
    scheduler.stop()
    assert calls == []


def test_parse_cron_wildcard():
    fields = parse_cron("* * * * *")
    assert fields[0] == set(range(0, 60))
    assert fields[1] == set(range(0, 24))


def test_parse_cron_invalid_field_count():
    with pytest.raises(SchedulerError):
        parse_cron("* * *")


def test_cron_matches_specific_time():
    fields = parse_cron("30 8 * * *")
    dt = datetime(2026, 7, 12, 8, 30)
    assert matches(fields, dt)
    dt_no_match = datetime(2026, 7, 12, 8, 31)
    assert not matches(fields, dt_no_match)


def test_next_run_time_is_in_the_future():
    now = time.time()
    nxt = next_run_time("0 0 * * *", now)
    assert nxt > now
