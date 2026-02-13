from app import db
from app.models import User


def _create_user(email: str, password: str) -> User:
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


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
