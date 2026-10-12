from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import jsonify, request
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def bad_request(message):
    return ApiError(400, message)


def not_found(what="Resource"):
    return ApiError(404, f"{what} not found")


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise bad_request("Expected a JSON object body")
    return data


# --- field parsers -------------------------------------------------------

def require_str(data, key, max_len=None, allow_empty=False):
    value = data.get(key)
    if not isinstance(value, str):
        raise bad_request(f"'{key}' is required")
    value = value.strip()
    if not value and not allow_empty:
        raise bad_request(f"'{key}' cannot be empty")
    if max_len and len(value) > max_len:
        raise bad_request(f"'{key}' must be at most {max_len} characters")
    return value


def optional_str(data, key, max_len=None):
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise bad_request(f"'{key}' must be a string")
    value = value.strip()
    if max_len and len(value) > max_len:
        raise bad_request(f"'{key}' must be at most {max_len} characters")
    return value or None


def require_int(data, key, minimum=None, maximum=None):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise bad_request(f"'{key}' must be an integer")
    if minimum is not None and value < minimum:
        raise bad_request(f"'{key}' must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise bad_request(f"'{key}' must be at most {maximum}")
    return value


def require_decimal(data, key, minimum=None, maximum=None):
    value = data.get(key)
    if isinstance(value, bool) or value is None:
        raise bad_request(f"'{key}' must be a number")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise bad_request(f"'{key}' must be a number")
    if not number.is_finite():
        raise bad_request(f"'{key}' must be a number")
    if minimum is not None and number < minimum:
        raise bad_request(f"'{key}' must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise bad_request(f"'{key}' must be at most {maximum}")
    return number.quantize(Decimal("0.01"))


def parse_datetime(value, key):
    if not isinstance(value, str):
        raise bad_request(f"'{key}' must be an ISO datetime string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise bad_request(f"'{key}' must be an ISO datetime string")
    # Times are naive local times throughout the app.
    return parsed.replace(tzinfo=None, microsecond=0)


def parse_date(value, key):
    if not isinstance(value, str):
        raise bad_request(f"'{key}' must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise bad_request(f"'{key}' must be an ISO date string")


def init_app(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify(error=err.message), err.status

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return jsonify(error=err.description), err.code
