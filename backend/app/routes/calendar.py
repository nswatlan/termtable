"""The calendar feed and the student's own events."""

from flask import Blueprint, g, request

from ..services import calendar, events
from .auth import login_required

bp = Blueprint("calendar", __name__)


@bp.get("/calendar")
@login_required
def calendar_feed():
    return calendar.feed(g.user["id"], request.args.get("start"), request.args.get("end"))


@bp.get("/events/<int:event_id>")
@login_required
def get_event(event_id):
    return events.owned_event(event_id, g.user["id"])


@bp.post("/events")
@login_required
def create_event():
    return events.create_event(g.user["id"], request.get_json(silent=True)), 201


@bp.put("/events/<int:event_id>")
@login_required
def update_event(event_id):
    return events.update_event(event_id, g.user["id"], request.get_json(silent=True))


@bp.delete("/events/<int:event_id>")
@login_required
def delete_event(event_id):
    events.delete_event(event_id, g.user["id"])
    return {"ok": True}
