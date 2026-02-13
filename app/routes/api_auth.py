from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
)
from app import db
from app.models import User
from app.services.api_response import (
    success_response as _api_success_response,
    error_response as _api_error_response,
)
from app.services.user_scope import attach_current_user, current_user

api_auth_bp = Blueprint('api_auth', __name__)


def _ok_response(
    data: dict | None = None,
    *,
    status: int = 200,
    code: str | None = None,
    message: str | None = None,
    legacy: dict | None = None,
):
    return _api_success_response(
        data=data,
        status=status,
        code=code,
        message=message,
        legacy=legacy,
    )


def _error_response(
    message: str,
    code: str,
    *,
    status: int = 400,
    data: dict | None = None,
    legacy: dict | None = None,
):
    merged_legacy = {"msg": message}
    if legacy:
        merged_legacy.update(legacy)
    return _api_error_response(
        message=message,
        code=code,
        status=status,
        data=data,
        legacy=merged_legacy,
    )

@api_auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    if not email or not password:
        return _error_response(
            "Email and password required",
            "EMAIL_PASSWORD_REQUIRED",
            status=400,
        )

    if User.query.filter_by(email=email).first():
        return _error_response(
            "User already exists",
            "USER_ALREADY_EXISTS",
            status=409,
        )

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return _ok_response(
        data={
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
        },
        status=201,
        code="USER_REGISTERED",
        message="User registered successfully",
        legacy={"msg": "User registered successfully"},
    )

@api_auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return _error_response(
            "Bad username or password",
            "INVALID_CREDENTIALS",
            status=401,
        )

    access_token = create_access_token(identity=str(user.id))
    response, status = _ok_response(
        data={
            "access_token": access_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "is_admin": user.is_admin,
            },
        },
        code="AUTHENTICATED",
        message="Authenticated.",
        legacy={"access_token": access_token},
    )
    set_access_cookies(response, access_token)
    return response, status


@api_auth_bp.route('/logout', methods=['POST'])
def logout():
    response, status = _ok_response(
        data=None,
        code="LOGGED_OUT",
        message="Logged out",
        legacy={"msg": "Logged out"},
    )
    unset_jwt_cookies(response)
    return response, status

@api_auth_bp.route('/me', methods=['GET'])
def me():
    auth_error = attach_current_user(require=True)
    if auth_error is not None:
        return auth_error

    user = current_user()
    if user is None:
        return _error_response("User not found.", "USER_NOT_FOUND", status=404)

    user_payload = {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
    }
    return _ok_response(
        data=user_payload,
        code="AUTH_USER",
        message="Authenticated user.",
        legacy=user_payload,
    )
