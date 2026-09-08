"""Validation and time-window helpers for department-specific calendars."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from itertools import groupby
from typing import Iterable


class CalendarValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TimeWindow:
    day: int
    start: time
    end: time
    period_ids: tuple[str, ...]


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def ranges_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    """Return whether two half-open time ranges share any time."""
    return start_a < end_b and start_b < end_a


def window_within_shift(
    window_start: time,
    window_end: time,
    shift_start: time,
    shift_end: time,
) -> bool:
    return shift_start <= window_start and window_end <= shift_end


def validate_periods(periods: Iterable[object]) -> None:
    """Reject invalid, duplicate, overlapping, or non-chronological periods."""
    ordered = sorted(periods, key=lambda period: (period.day, period.ordinal))
    for day, day_periods_iter in groupby(ordered, key=lambda period: period.day):
        day_periods = list(day_periods_iter)
        ordinals = [period.ordinal for period in day_periods]
        if len(ordinals) != len(set(ordinals)):
            raise CalendarValidationError(f"Day {day} contains duplicate period ordinals")

        previous_end = None
        for period in day_periods:
            if period.start_time >= period.end_time:
                raise CalendarValidationError("Period start must be before its end")
            if previous_end is not None and period.start_time < previous_end:
                raise CalendarValidationError(
                    f"Day {day} periods must be chronological and non-overlapping"
                )
            previous_end = period.end_time


def valid_activity_windows(calendar: object, duration_minutes: int) -> list[TimeWindow]:
    """Build exact-duration windows from adjacent teaching periods only."""
    if duration_minutes <= 0:
        raise CalendarValidationError("Activity duration must be positive")

    periods = list(calendar.periods)
    validate_periods(periods)
    windows: list[TimeWindow] = []

    teaching = [period for period in periods if period.kind == "teaching"]
    ordered = sorted(teaching, key=lambda period: (period.day, period.ordinal))
    for day, day_periods_iter in groupby(ordered, key=lambda period: period.day):
        day_periods = list(day_periods_iter)
        for start_index, first in enumerate(day_periods):
            period_ids = [first.id]
            end = first.end_time
            elapsed = _minutes(end) - _minutes(first.start_time)
            if elapsed == duration_minutes:
                windows.append(TimeWindow(day, first.start_time, end, tuple(period_ids)))
            if elapsed >= duration_minutes:
                continue

            for following in day_periods[start_index + 1:]:
                if following.start_time != end:
                    break
                period_ids.append(following.id)
                end = following.end_time
                elapsed = _minutes(end) - _minutes(first.start_time)
                if elapsed == duration_minutes:
                    windows.append(TimeWindow(day, first.start_time, end, tuple(period_ids)))
                    break
                if elapsed > duration_minutes:
                    break

    return windows
