"""A minimal, dependency-free 5-field cron expression evaluator.

Supports standard fields ``minute hour day_of_month month day_of_week`` with
``*``, single values, comma lists, ranges (``1-5``), and step values
(``*/15``). This is intentionally simple; for advanced cron semantics
consider a plugin backed by a full-featured library.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pyworkflow.exceptions import SchedulerError

_FIELD_RANGES = [
    (0, 59),  # minute
    (0, 23),  # hour
    (1, 31),  # day of month
    (1, 12),  # month
    (0, 6),  # day of week (0=Sunday)
]


def _parse_field(expr: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in expr.split(","):
        step = 1
        if "/" in part:
            part, step_str = part.split("/")
            step = int(step_str)
        if part == "*":
            rng_lo, rng_hi = lo, hi
        elif "-" in part:
            rng_lo, rng_hi = (int(x) for x in part.split("-"))
        else:
            rng_lo = rng_hi = int(part)
        values.update(range(rng_lo, rng_hi + 1, step))
    return values


def parse_cron(expr: str) -> list[set[int]]:
    fields = expr.strip().split()
    if len(fields) != 5:
        raise SchedulerError(
            f"Invalid cron expression '{expr}': expected 5 fields "
            "(minute hour day month day_of_week)"
        )
    return [
        _parse_field(field, lo, hi) for field, (lo, hi) in zip(fields, _FIELD_RANGES)
    ]


def matches(expr_sets: list[set[int]], dt: datetime) -> bool:
    minute, hour, dom, month, dow = expr_sets
    return (
        dt.minute in minute
        and dt.hour in hour
        and dt.day in dom
        and dt.month in month
        and (dt.weekday() + 1) % 7 in dow  # Python: Mon=0..Sun=6 -> cron: Sun=0..Sat=6
    )


def next_run_time(
    expr: str, after_timestamp: float, search_limit_days: int = 366
) -> float:
    """Find the next UNIX timestamp (minute resolution) matching `expr`,
    strictly after `after_timestamp`."""
    expr_sets = parse_cron(expr)
    dt = datetime.fromtimestamp(after_timestamp).replace(second=0, microsecond=0)
    dt += timedelta(minutes=1)
    limit = dt + timedelta(days=search_limit_days)
    while dt < limit:
        if matches(expr_sets, dt):
            return dt.timestamp()
        dt += timedelta(minutes=1)
    raise SchedulerError(f"No matching run time found for cron expression '{expr}'")
