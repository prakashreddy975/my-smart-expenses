import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import jsonify, request

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass


def _jwt_secret():
    return (
        os.environ.get("JWT_SECRET_KEY", "").strip()
        or os.environ.get("FLASK_SECRET_KEY", "").strip()
        or "dev-only-set-JWT_SECRET_KEY-in-production"
    )


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def require_auth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        payload = decode_token(auth[7:].strip())
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        request.auth_user_id = int(payload["sub"])
        request.auth_email = str(payload.get("email") or "")
        return f(*args, **kwargs)

    return wrapped
