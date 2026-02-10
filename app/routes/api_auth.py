from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
)
from app import db
from app.models import User

api_auth_bp = Blueprint('api_auth', __name__)


def _is_local_debug_request() -> bool:
    if current_app.config.get("ENV_NAME") == "production":
        return False
    remote_addr = request.remote_addr or ""
    return remote_addr in {"127.0.0.1", "::1"}

@api_auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    if not email or not password:
        return jsonify({"msg": "Email and password required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "User already exists"}), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"msg": "User registered successfully"}), 201

@api_auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=str(user.id))
    response = jsonify(access_token=access_token)
    set_access_cookies(response, access_token)
    return response


@api_auth_bp.route('/dev-admin-login', methods=['POST'])
def dev_admin_login():
    """Local debug helper: issue admin JWT cookie with a shared passphrase."""
    if not _is_local_debug_request():
        return jsonify({"ok": False, "code": "FORBIDDEN", "message": "Not allowed."}), 403

    data = request.get_json(silent=True) or {}
    password = str(data.get("password") or "")
    if password != "1234":
        return jsonify({"ok": False, "code": "INVALID_PASSWORD", "message": "Wrong password."}), 401

    admin_user = User.query.filter_by(is_admin=True).order_by(User.id.asc()).first()
    if admin_user is None:
        admin_user = User(email="local-admin@example.com", is_admin=True)
        admin_user.set_password("1234")
        db.session.add(admin_user)
        db.session.commit()

    access_token = create_access_token(identity=str(admin_user.id))
    response = jsonify({"ok": True, "message": "Admin authenticated."})
    set_access_cookies(response, access_token)
    return response


@api_auth_bp.route('/logout', methods=['POST'])
def logout():
    response = jsonify({"msg": "Logged out"})
    unset_jwt_cookies(response)
    return response

@api_auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return jsonify({
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin
    })
