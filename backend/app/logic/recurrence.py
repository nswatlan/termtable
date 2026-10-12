"""Expanding recurring events into concrete occurrences within a date range.

All datetimes are naive local times. A range is half-open: [range_start, range_end).
An occurrence is included when it overlaps the range at all.
"""

from datetime import datetime, time, timedelta

from dateutil.rrule import DAILY, MONTHLY, WEEKLY, rrule, weekday

WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
FREQUENCIES = {"DAILY": DAILY, "WEEKLY": WEEKLY, "MONTHLY": MONTHLY}


def parse_weekdays(value):
    """'MO,WE,FR' -> [0, 2, 4]. Raises ValueError on unknown codes."""
    if not value:
        return []
    days = []
    for code in value.split(","):
        code = code.strip().upper()
        if code not in WEEKDAY_CODES:
            raise ValueError(f"unknown weekday code: {code!r}")
        index = WEEKDAY_CODES.index(code)
        if index not in days:
            days.append(index)
    return sorted(days)


def format_weekdays(days):
    return ",".join(WEEKDAY_CODES[d] for d in sorted(set(days)))


def _overlaps(start, end, range_start, range_end):
    return start < range_end and end > range_start


def expand_event(event, range_start, range_end):
    """Yield (start, end) pairs for each occurrence of a calendar event row.

    event needs start_at, end_at and optionally recurrence_freq,
    recurrence_interval, recurrence_days and recurrence_until (a date,
    inclusive).
    """
    start, end = event["start_at"], event["end_at"]
    duration = end - start
    freq = event.get("recurrence_freq")
    if not freq:
        if _overlaps(start, end, range_start, range_end):
            yield start, end
        return

    kwargs = {"dtstart": start, "interval": event.get("recurrence_interval") or 1}
    if freq == "WEEKLY":
        days = parse_weekdays(event.get("recurrence_days"))
        # dateutil only yields dtstart if it matches byweekday, so always
        # include the start day: the first occurrence is the one the user made.
        if start.weekday() not in days:
            days.append(start.weekday())
        kwargs["byweekday"] = [weekday(d) for d in days]
    until = event.get("recurrence_until")
    if until:
        kwargs["until"] = datetime.combine(until, time.max)

    rule = rrule(FREQUENCIES[freq], **kwargs)
    # An occurrence overlaps the range iff range_start - duration < occ < range_end.
    for occ_start in rule.between(range_start - duration, range_end, inc=False):
        yield occ_start, occ_start + duration


def expand_weekly_meeting(day_of_week, start_time, end_time,
                          term_start, term_end, range_start, range_end):
    """Yield (start, end) for a class that meets every week on day_of_week
    (0 = Monday) between term_start and term_end inclusive."""
    first = max(term_start, range_start.date())
    last = min(term_end, (range_end - timedelta(microseconds=1)).date())
    current = first + timedelta(days=(day_of_week - first.weekday()) % 7)
    while current <= last:
        start = datetime.combine(current, start_time)
        end = datetime.combine(current, end_time)
        if _overlaps(start, end, range_start, range_end):
            yield start, end
        current += timedelta(days=7)
