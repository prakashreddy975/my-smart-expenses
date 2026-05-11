import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
from auth import create_token, require_auth

app = Flask(__name__)
app.config.setdefault(
    "SECRET_KEY",
    os.environ.get("FLASK_SECRET_KEY", "dev-flask-secret-change-me"),
)

_cors_origins = os.environ.get("CORS_ORIGINS", "").strip()
_cors_kw = {
    "allow_headers": ["Content-Type", "Authorization"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
}
if _cors_origins and _cors_origins != "*":
    _cors_kw["origins"] = [o.strip() for o in _cors_origins.split(",") if o.strip()]
else:
    _cors_kw["origins"] = "*"

CORS(app, resources={r"/api/*": _cors_kw})

db.init_db()


# --- auth (public) ---


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    try:
        uid = db.user_create(email, generate_password_hash(password))
    except ValueError:
        return jsonify({"error": "Email already registered"}), 409
    token = create_token(uid, email)
    return jsonify({"token": token, "user": {"id": uid, "email": email}}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    row = db.user_by_email(email)
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401
    uid = int(row["id"])
    token = create_token(uid, email)
    return jsonify({"token": token, "user": {"id": uid, "email": email}})


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def me():
    row = db.user_by_id(request.auth_user_id)
    if row is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"id": int(row["id"]), "email": row["email"]})


# --- expenses ---


@app.route("/api/expenses", methods=["GET"])
@require_auth
def get_expenses():
    return jsonify(db.expenses_list(request.auth_user_id))


@app.route("/api/expenses", methods=["POST"])
@require_auth
def add_expense():
    data = request.json
    db.expense_add(request.auth_user_id, data)
    return jsonify({"status": "success"}), 201


@app.route("/api/expenses/<int:id>", methods=["DELETE"])
@require_auth
def delete_expense(id):
    db.expense_delete(request.auth_user_id, id)
    return jsonify({"status": "deleted"}), 200


@app.route("/api/analytics", methods=["GET"])
@require_auth
def get_analytics():
    total, categories = db.expenses_analytics(request.auth_user_id)
    if total == 0 and not categories:
        return jsonify({"total": 0, "categories": {}})
    return jsonify({"total": total, "categories": categories})


@app.route("/api/expenses/<int:id>", methods=["PUT"])
@require_auth
def update_expense(id):
    data = request.json
    if db.expense_update(request.auth_user_id, id, data):
        return jsonify({"status": "updated"}), 200
    return jsonify({"error": "Not found"}), 404


# --- banks ---


@app.route("/api/banks", methods=["GET"])
@require_auth
def get_banks():
    return jsonify(db.banks_list(request.auth_user_id))


@app.route("/api/banks", methods=["POST"])
@require_auth
def add_bank():
    data = request.json
    db.bank_add(request.auth_user_id, data)
    return jsonify({"status": "success"}), 201


@app.route("/api/banks/<int:id>", methods=["DELETE"])
@require_auth
def delete_bank(id):
    db.bank_delete(request.auth_user_id, id)
    return jsonify({"status": "deleted"}), 200


@app.route("/api/banks/<int:id>", methods=["PUT"])
@require_auth
def update_bank(id):
    data = request.json
    if db.bank_update(request.auth_user_id, id, data):
        return jsonify({"status": "updated"}), 200
    return jsonify({"error": "Not found"}), 404


# --- bills ---


@app.route("/api/bills", methods=["GET", "POST"])
@require_auth
def handle_bills():
    uid = request.auth_user_id
    if request.method == "POST":
        data = request.json
        db.bill_add(uid, data)
        return jsonify({"status": "success"}), 201
    return jsonify(db.bills_list(uid))


@app.route("/api/bills/<int:id>", methods=["PUT"])
@require_auth
def update_bill(id):
    data = request.json
    if db.bill_update(request.auth_user_id, id, data):
        return jsonify({"status": "updated"}), 200
    return jsonify({"error": "Not found"}), 404


@app.route("/api/bills/<int:id>", methods=["DELETE"])
@require_auth
def delete_bill(id):
    db.bill_delete(request.auth_user_id, id)
    return jsonify({"status": "deleted"}), 200


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)
