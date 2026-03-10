from datetime import timedelta

from flask_jwt_extended import create_access_token

from app import db
from app.models import User


def _create_user(email: str, password: str) -> User:
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _set_auth_cookie(client, token: str) -> None:
    client.set_cookie("auth_token", token)


def test_logout_clears_auth_cookie(client, app):
    with app.app_context():
        _create_user("session-user@example.com", "pw1234")

    login_response = client.post(
        "/api/auth/login",
        json={"email": "session-user@example.com", "password": "pw1234"},
    )
    assert login_response.status_code == 200
    login_cookie_headers = login_response.headers.getlist("Set-Cookie")
    assert any("auth_token=" in header for header in login_cookie_headers)

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    logout_cookie_headers = logout_response.headers.getlist("Set-Cookie")
    assert any("auth_token=;" in header for header in logout_cookie_headers)
    assert any("Max-Age=0" in header or "Expires=" in header for header in logout_cookie_headers)


def test_dev_admin_login_route_is_not_available(client):
    response = client.post(
        "/api/auth/dev-admin-login",
        json={"password": "1234"},
    )
    assert response.status_code == 404


def test_legacy_html_redirects_to_pin_login(client, app):
    app.config["LEGACY_UI_PIN"] = "2468"

    response = client.get("/manage/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/legacy-access?next=/manage/")


def test_legacy_pin_login_sets_cookie_and_allows_manage(client, app):
    app.config["LEGACY_UI_PIN"] = "2468"
    app.config["LEGACY_UI_TRUSTED_EMAIL"] = "hisukgyu@gmail.com"

    login_response = client.post(
        "/legacy-access",
        data={"pin": "2468", "next": "/manage/"},
    )
    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith("/manage/")
    login_cookie_headers = login_response.headers.getlist("Set-Cookie")
    assert any("auth_token=" in header for header in login_cookie_headers)

    with app.app_context():
        user = User.query.filter_by(email="hisukgyu@gmail.com").first()
        assert user is not None

    manage_response = client.get("/manage/")
    assert manage_response.status_code == 200
    assert "관리 대시보드" in manage_response.get_data(as_text=True)


def test_expired_legacy_cookie_redirects_to_pin_login(client, app):
    app.config["LEGACY_UI_PIN"] = "2468"

    with app.app_context():
        user = _create_user("expired-manage@example.com", "pw1234")
        expired_token = create_access_token(
            identity=str(user.id),
            expires_delta=timedelta(seconds=-1),
        )

    _set_auth_cookie(client, expired_token)

    response = client.get("/manage/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/legacy-access?next=/manage/")
    cookie_headers = response.headers.getlist("Set-Cookie")
    assert any("auth_token=;" in header for header in cookie_headers)


def test_expired_legacy_cookie_redirects_form_post_to_pin_login(client, app):
    app.config["LEGACY_UI_PIN"] = "2468"

    with app.app_context():
        user = _create_user("expired-manage-post@example.com", "pw1234")
        expired_token = create_access_token(
            identity=str(user.id),
            expires_delta=timedelta(seconds=-1),
        )

    _set_auth_cookie(client, expired_token)

    response = client.post("/manage/pdf-lab", data={"title": "expired"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/legacy-access?next=/manage/pdf-lab")
    cookie_headers = response.headers.getlist("Set-Cookie")
    assert any("auth_token=;" in header for header in cookie_headers)
