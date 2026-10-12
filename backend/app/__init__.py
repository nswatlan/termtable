from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import NotFound

from . import db, errors
from .config import Config


class JSONProvider(DefaultJSONProvider):
    """ISO dates (Flask's default is RFC 822) and plain numbers for DECIMAL.
    Keys keep insertion order (e.g. grade categories homework -> final)."""

    sort_keys = False

    @staticmethod
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat(timespec="seconds")
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, time):
            return o.strftime("%H:%M")
        if isinstance(o, timedelta):
            return db.to_time(o).strftime("%H:%M")
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def create_app(config=Config):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config)
    app.config.setdefault("FRONTEND_DIST", str(Path(__file__).resolve().parents[2] / "frontend" / "dist"))
    app.json = JSONProvider(app)

    db.init_app(app)
    errors.init_app(app)

    from .routes import auth, calendar, catalog, gradebook, homework, reviews, schedules, sharing

    for module in (auth, catalog, reviews, schedules, calendar, gradebook, sharing, homework):
        app.register_blueprint(module.bp, url_prefix="/api")

    @app.before_request
    def require_custom_header_on_writes():
        # CSRF defense: cross-site forms cannot set custom headers, and a
        # cross-origin fetch that does would need a CORS preflight we never grant.
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("X-Requested-With") != "fetch":
                return jsonify(error="Missing X-Requested-With header"), 403

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path):
        # API errors and missing assets must not become successful HTML responses.
        if path == "api" or path.startswith("api/") or ".." in path.split("/"):
            abort(404)
        directory = app.config["FRONTEND_DIST"]
        if path:
            try:
                return send_from_directory(directory, path)
            except NotFound:
                if path.startswith("assets/") or Path(path).suffix:
                    abort(404)
        return send_from_directory(directory, "index.html", max_age=0)

    return app
