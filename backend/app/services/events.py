"""A student's own calendar events: validation and CRUD."""

from datetime import datetime, time, timedelta

from ..db import commit
from ..errors import (bad_request, not_found, optional_str, parse_date, parse_datetime,
                      require_int, require_object, require_str)
from ..logic.recurrence import FREQUENCIES, format_weekdays, parse_weekdays
from ..repositories import events as events_repo

COLORS = ("blue", "green", "red", "yellow", "purple", "orange", "teal", "gray")


def serialize(row):
    row["all_day"] = bool(row["all_day"])
    return row


def owned_event(event_id, user_id):
    """The event if this student created it; 404 otherwise."""
    event = events_repo.get_owned(event_id, user_id)
    if event is None:
        raise not_found("Event")
    return serialize(event)


def parse_event(body):
    """Validate an event payload into column values."""
    data = require_object(body)
    title = require_str(data, "title", max_len=200)
    all_day = data.get("all_day", False)
    if not isinstance(all_day, bool):
        raise bad_request("'all_day' must be true or false")
    start_at = parse_datetime(data.get("start_at"), "start_at")
    end_at = parse_datetime(data.get("end_at"), "end_at")
    if all_day:
        # All-day events span whole days with an exclusive end.
        start_at = datetime.combine(start_at.date(), time.min)
        end_at = datetime.combine(end_at.date(), time.min)
        if end_at <= start_at:
            end_at = start_at + timedelta(days=1)
    if end_at <= start_at:
        raise bad_request("The event must end after it starts")

    color = data.get("color") or "blue"
    if color not in COLORS:
        raise bad_request(f"'color' must be one of {', '.join(COLORS)}")

    freq = data.get("recurrence_freq") or None
    interval, days, until = 1, None, None
    if freq is not None:
        if freq not in FREQUENCIES:
            raise bad_request("'recurrence_freq' must be DAILY, WEEKLY or MONTHLY")
        if data.get("recurrence_interval") is not None:
            interval = require_int(data, "recurrence_interval", minimum=1, maximum=99)
        if freq == "WEEKLY":
            try:
                weekday_list = parse_weekdays(data.get("recurrence_days"))
            except ValueError as e:
                raise bad_request(str(e))
            if start_at.weekday() not in weekday_list:
                weekday_list.append(start_at.weekday())
            days = format_weekdays(weekday_list)
        if data.get("recurrence_until"):
            until = parse_date(data["recurrence_until"], "recurrence_until")
            if until < start_at.date():
                raise bad_request("The repeat end date must be on or after the start date")

    return {
        "title": title,
        "description": optional_str(data, "description", max_len=5000),
        "location": optional_str(data, "location", max_len=200),
        "color": color,
        "start_at": start_at,
        "end_at": end_at,
        "all_day": all_day,
        "recurrence_freq": freq,
        "recurrence_interval": interval,
        "recurrence_days": days,
        "recurrence_until": until,
    }


def create_event(user_id, body):
    event_id = events_repo.insert(user_id, parse_event(body))
    commit()
    return owned_event(event_id, user_id)


def update_event(event_id, user_id, body):
    owned_event(event_id, user_id)
    events_repo.update(event_id, user_id, parse_event(body))
    commit()
    return owned_event(event_id, user_id)


def delete_event(event_id, user_id):
    owned_event(event_id, user_id)
    events_repo.delete(event_id, user_id)
    commit()
