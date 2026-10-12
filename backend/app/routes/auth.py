"""Register, log in, log out, current user; and the @login_required guard."""

from functools import wraps

from flask import Blueprint, g, request, session

from ..errors import ApiError
from ..services import auth as auth_service

bp = Blueprint("auth", __name__)


def login_required(view):
    """Load the logged-in user into g.user, or answer 401."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            raise ApiError(401, "Please log in")
        user = auth_service.current_user(user_id)
        if user is None:
            session.clear()
            raise ApiError(401, "Please log in")
        g.user = user
        return view(*args, **kwargs)
    return wrapped


def _start_session(user):
    session.clear()
    session["user_id"] = user["id"]
    return user


@bp.post("/auth/register")
def register():
    return _start_session(auth_service.register(request.get_json(silent=True))), 201


@bp.post("/auth/login")
def login():
    return _start_session(auth_service.authenticate(request.get_json(silent=True)))


@bp.post("/auth/logout")
def logout():
    session.clear()
    return {"ok": True}


@bp.get("/auth/me")
@login_required
def me():
    return g.user
