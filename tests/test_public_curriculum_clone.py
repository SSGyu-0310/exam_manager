"""Tests for Public Curriculum Template API."""
import json
import pytest
from app import db
from app.models import User, PublicCurriculumTemplate, Block, Lecture


@pytest.fixture
def admin_user(app):
    """Create an admin user."""
    with app.app_context():
        user = User(email="admin@test.com", is_admin=True)
        user.set_password("adminpass")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def regular_user(app):
    """Create a regular (non-admin) user."""
    with app.app_context():
        user = User(email="user@test.com", is_admin=False)
        user.set_password("userpass")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def second_user(app):
    """Create a second regular user."""
    with app.app_context():
        user = User(email="user2@test.com", is_admin=False)
        user.set_password("user2pass")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def published_template(app, admin_user):
    """Create a published template."""
    with app.app_context():
        template = PublicCurriculumTemplate(
            title="Test Published Template",
            school_tag="테스트고",
            grade_tag="고2",
            subject_tag="생명과학",
            description="A published test template",
            payload_json=json.dumps({
                "blocks": [
                    {
                        "name": "심혈관",
                        "lectures": [
                            {"title": "심전도 원리", "order": 1},
                            {"title": "부정맥", "order": 2},
                        ]
                    }
                ]
            }),
            published=True,
            created_by=admin_user.id,
        )
        db.session.add(template)
        db.session.commit()
        yield template


@pytest.fixture
def unpublished_template(app, admin_user):
    """Create an unpublished template."""
    with app.app_context():
        template = PublicCurriculumTemplate(
            title="Unpublished Template",
            payload_json="{}",
            published=False,
            created_by=admin_user.id,
        )
        db.session.add(template)
        db.session.commit()
        yield template


def get_auth_token(client, email, password):
    """Helper to get JWT token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json.get("access_token")


class TestPublicCatalog:
    """Tests for public catalog endpoints."""

    def test_list_templates_returns_only_published(
        self, client, published_template, unpublished_template
    ):
        """GET /api/public/curriculums returns only published templates."""
        res = client.get("/api/public/curriculums")
        assert res.status_code == 200
        data = res.json
        assert data["ok"] is True

        titles = [t["title"] for t in data["data"]]
        assert "Test Published Template" in titles
        assert "Unpublished Template" not in titles

    def test_get_template_detail_published(self, client, published_template):
        """GET /api/public/curriculums/<id> returns published template."""
        res = client.get(f"/api/public/curriculums/{published_template.id}")
        assert res.status_code == 200
        data = res.json
        assert data["ok"] is True
        assert data["data"]["title"] == "Test Published Template"
        assert "payload" in data["data"]

    def test_get_template_detail_unpublished_404(self, client, unpublished_template):
        """GET /api/public/curriculums/<id> returns 404 for unpublished."""
        res = client.get(f"/api/public/curriculums/{unpublished_template.id}")
        assert res.status_code == 404

    def test_filter_by_tags(self, client, published_template):
        """Templates can be filtered by tags."""
        res = client.get("/api/public/curriculums?schoolTag=테스트고")
        assert res.status_code == 200
        assert len(res.json["data"]) == 1

        res = client.get("/api/public/curriculums?schoolTag=없는태그")
        assert res.status_code == 200
        assert len(res.json["data"]) == 0


class TestClone:
    """Tests for clone endpoint."""

    def test_clone_requires_auth(self, client, published_template):
        """POST /api/public/curriculums/<id>/clone returns 401 without token."""
        res = client.post(f"/api/public/curriculums/{published_template.id}/clone")
        assert res.status_code == 401

    def test_clone_creates_user_owned_data(
        self, client, app, regular_user, published_template
    ):
        """Clone creates Block/Lecture with user_id = current user."""
        token = get_auth_token(client, "user@test.com", "userpass")

        res = client.post(
            f"/api/public/curriculums/{published_template.id}/clone",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 201
        data = res.json
        assert data["ok"] is True
        assert len(data["data"]["blockIds"]) == 1
        assert len(data["data"]["lectureIds"]) == 2

        # Verify ownership
        with app.app_context():
            block = db.session.get(Block, data["data"]["blockIds"][0])
            assert block is not None
            assert block.user_id == regular_user.id
            assert block.name == "심혈관"

            lecture = db.session.get(Lecture, data["data"]["lectureIds"][0])
            assert lecture is not None
            assert lecture.user_id == regular_user.id

    def test_cloned_data_isolated_from_other_users(
        self, client, app, regular_user, second_user, published_template
    ):
        """User B cannot access User A's cloned data."""
        # User A clones
        token_a = get_auth_token(client, "user@test.com", "userpass")
        res = client.post(
            f"/api/public/curriculums/{published_template.id}/clone",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        block_id = res.json["data"]["blockIds"][0]

        # User B tries to access (via manage API)
        token_b = get_auth_token(client, "user2@test.com", "user2pass")
        res = client.get(
            f"/api/manage/blocks/{block_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        # Should be 404 (not found for this user) or 403
        assert res.status_code in [403, 404]

    def test_clone_unpublished_404(self, client, regular_user, unpublished_template):
        """Cannot clone unpublished template."""
        token = get_auth_token(client, "user@test.com", "userpass")
        res = client.post(
            f"/api/public/curriculums/{unpublished_template.id}/clone",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404


class TestAdminAPI:
    """Tests for admin template management."""

    def test_create_template_requires_admin(self, client, regular_user):
        """Non-admin cannot create templates."""
        token = get_auth_token(client, "user@test.com", "userpass")
        res = client.post(
            "/api/admin/public/curriculums",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "New Template", "payload": {}},
        )
        assert res.status_code == 403

    def test_admin_can_create_template(self, client, admin_user):
        """Admin can create templates."""
        token = get_auth_token(client, "admin@test.com", "adminpass")
        res = client.post(
            "/api/admin/public/curriculums",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Admin Created",
                "schoolTag": "서울과고",
                "payload": {"blocks": []},
            },
        )
        assert res.status_code == 201
        assert res.json["data"]["title"] == "Admin Created"
        assert res.json["data"]["published"] is False

    def test_admin_can_publish(self, client, admin_user, unpublished_template):
        """Admin can publish a template."""
        token = get_auth_token(client, "admin@test.com", "adminpass")
        res = client.post(
            f"/api/admin/public/curriculums/{unpublished_template.id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json["data"]["published"] is True

    def test_non_admin_cannot_publish(self, client, regular_user, unpublished_template):
        """Non-admin cannot publish."""
        token = get_auth_token(client, "user@test.com", "userpass")
        res = client.post(
            f"/api/admin/public/curriculums/{unpublished_template.id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
