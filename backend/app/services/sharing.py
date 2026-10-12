"""Calendar sharing: an event's owner invites other students by the email they
registered with; invitees accept or decline. Accepted (and still-pending)
invitations put the owner's event on the invitee's calendar feed, read live
from calendar_events, so the owner's edits show up everywhere at once.

Invitations are delivered in the app (an "Invitations" panel on the calendar
and a count in the navigation bar), not by sending email.
"""

import pymysql

from ..db import commit
from ..errors import ApiError, bad_request, not_found, require_object, require_str
from ..repositories import events as events_repo
from ..repositories import users as users_repo
from .auth import EMAIL_RE
from .events import owned_event, serialize

RESPONSES = ("accepted", "declined")


def find_invitee(user, email):
    """The registered student with this email, who must not be `user`."""
    if not EMAIL_RE.match(email):
        raise bad_request("Enter a valid email address")
    if email == user["email"].lower():
        raise bad_request("You're already on your own event")
    invitee = users_repo.find_by_email(email)
    if invitee is None:
        raise ApiError(404, f"No Termtable account uses {email}. They need to sign up first.")
    return invitee


def lookup(user, email):
    invitee = find_invitee(user, email.strip().lower())
    return {"email": invitee["email"], "display_name": invitee["display_name"]}


# --- the owner's side -------------------------------------------------------

def list_guests(event_id, user):
    owned_event(event_id, user["id"])
    return events_repo.guests(event_id)


def invite(event_id, user, body):
    owned_event(event_id, user["id"])
    invitee = find_invitee(user, require_str(require_object(body), "email", max_len=255).lower())
    existing = events_repo.find_invitation(event_id, invitee["id"])
    if existing and existing["status"] != "declined":
        raise ApiError(409, f"{invitee['display_name']} is already invited")
    if existing:
        # Re-inviting someone who declined asks them again.
        events_repo.reopen_invitation(existing["id"])
    else:
        try:
            events_repo.create_invitation(event_id, invitee["id"])
        except pymysql.err.IntegrityError:
            raise ApiError(409, f"{invitee['display_name']} is already invited")
    commit()
    return events_repo.guests(event_id)


def remove_guest(event_id, invitation_id, user):
    owned_event(event_id, user["id"])
    if not events_repo.delete_invitation(invitation_id, event_id):
        raise not_found("Invitation")
    commit()
    return events_repo.guests(event_id)


# --- the invitee's side -----------------------------------------------------

def received(user_id, status=None):
    """Invitations sent to the student. status: pending (default), accepted,
    declined or all."""
    status = status or "pending"
    if status == "all":
        rows = events_repo.received(user_id)
    elif status in ("pending", *RESPONSES):
        rows = events_repo.received(user_id, status=status)
    else:
        raise bad_request("'status' must be pending, accepted, declined or all")
    return [serialize(r) for r in rows]


def pending_count(user_id):
    return {"pending": events_repo.pending_count(user_id)}


def respond(invitation_id, user_id, body):
    response = require_object(body).get("response")
    if response not in RESPONSES:
        raise bad_request("'response' must be accepted or declined")
    if events_repo.invitation_for_invitee(invitation_id, user_id) is None:
        raise not_found("Invitation")
    events_repo.set_invitation_status(invitation_id, response)
    commit()
    return serialize(events_repo.received(user_id, invitation_id=invitation_id)[0])
