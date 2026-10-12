"""Event invitations: the owner's guest list and the invitee's responses."""

from flask import Blueprint, g, request

from ..services import sharing
from .auth import login_required

bp = Blueprint("sharing", __name__)


@bp.get("/users/lookup")
@login_required
def lookup_user():
    return sharing.lookup(g.user, request.args.get("email") or "")


@bp.get("/events/<int:event_id>/invitations")
@login_required
def list_guests(event_id):
    return sharing.list_guests(event_id, g.user)


@bp.post("/events/<int:event_id>/invitations")
@login_required
def invite_guest(event_id):
    return sharing.invite(event_id, g.user, request.get_json(silent=True)), 201


@bp.delete("/events/<int:event_id>/invitations/<int:invitation_id>")
@login_required
def remove_guest(event_id, invitation_id):
    return sharing.remove_guest(event_id, invitation_id, g.user)


@bp.get("/invitations")
@login_required
def my_invitations():
    return sharing.received(g.user["id"], request.args.get("status"))


@bp.get("/invitations/count")
@login_required
def pending_count():
    return sharing.pending_count(g.user["id"])


@bp.post("/invitations/<int:invitation_id>/respond")
@login_required
def respond(invitation_id):
    return sharing.respond(invitation_id, g.user["id"], request.get_json(silent=True))
