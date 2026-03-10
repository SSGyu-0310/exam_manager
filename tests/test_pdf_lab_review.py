import io
import json

from flask_jwt_extended import create_access_token

from app import db
from app.models import User
from app.routes.crop import _normalize_continuation_candidate_qnum
from app.services.pdf_lab_review import (
    _build_crop_lookup,
    refresh_session_report,
    update_question_review,
)


def _create_user(email: str, *, is_admin: bool = False) -> User:
    user = User(email=email, is_admin=is_admin)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    return user


def _token_for(user: User) -> str:
    return create_access_token(identity=str(user.id))


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_session(root_dir, session_id: str = "lab_session_01") -> str:
    session_dir = root_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session.json").write_text(
        json.dumps(
            {
                "id": session_id,
                "title": "Seed Session",
                "source_filename": "seed.pdf",
                "stored_pdf_name": "seed.pdf",
                "parser_mode": "legacy",
                "created_at": "2026-03-07T00:00:00Z",
                "created_by": "hisukgyu@gmail.com",
                "crop_images": {},
                "crop_error": None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (session_dir / "questions.json").write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "review_index": 1,
                        "question_number": 1,
                        "content": "첫 번째 문항",
                        "image_path": None,
                        "options": [
                            {"number": 1, "content": "선지 A", "image_path": None, "is_correct": True}
                        ],
                        "answer_options": [1],
                        "answer_text": "선지 A",
                    },
                    {
                        "review_index": 2,
                        "question_number": 2,
                        "content": "두 번째 문항",
                        "image_path": None,
                        "options": [],
                        "answer_options": [],
                        "answer_text": "",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (session_dir / "review.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-03-07T00:00:00Z",
                "items": [
                    {
                        "review_index": 1,
                        "question_number": 1,
                        "status": "pending",
                        "comment": "",
                        "updated_at": None,
                    },
                    {
                        "review_index": 2,
                        "question_number": 2,
                        "status": "pending",
                        "comment": "",
                        "updated_at": None,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (session_dir / "seed.pdf").write_bytes(b"%PDF-1.4\n")
    refresh_session_report(session_id, root_dir=root_dir)
    return session_id


def test_pdf_lab_report_updates_from_review_files(tmp_path):
    session_id = _seed_session(tmp_path)

    update_question_review(
        session_id=session_id,
        review_index=2,
        status="issue",
        comment="페이지 경계에서 문항이 끊김",
        root_dir=tmp_path,
    )

    report_payload = json.loads(
        (tmp_path / session_id / "report.json").read_text(encoding="utf-8")
    )
    assert report_payload["summary"]["issue_count"] == 1
    assert report_payload["summary"]["reviewed_count"] == 1
    assert report_payload["issues"][0]["review_index"] == 2
    assert report_payload["issues"][0]["comment"] == "페이지 경계에서 문항이 끊김"

    report_markdown = (tmp_path / session_id / "report.md").read_text(encoding="utf-8")
    assert "페이지 경계에서 문항이 끊김" in report_markdown


def test_pdf_lab_requires_trusted_or_admin_user(client, app, tmp_path):
    app.config["PDF_LAB_REVIEW_ROOT"] = tmp_path

    with app.app_context():
        regular_user = _create_user("regular@example.com")
        trusted_user = _create_user("hisukgyu@gmail.com")
        regular_token = _token_for(regular_user)
        trusted_token = _token_for(trusted_user)

    denied = client.get(
        "/manage/pdf-lab",
        headers=_auth_header(regular_token),
        follow_redirects=True,
    )
    assert denied.status_code == 200
    assert "hisukgyu@gmail.com 또는 관리자만" in denied.get_data(as_text=True)

    allowed = client.get("/manage/pdf-lab", headers=_auth_header(trusted_token))
    assert allowed.status_code == 200
    assert "PDF 실험실" in allowed.get_data(as_text=True)


def test_pdf_lab_upload_redirects_to_review(client, app, monkeypatch, tmp_path):
    app.config["PDF_LAB_REVIEW_ROOT"] = tmp_path

    with app.app_context():
        trusted_user = _create_user("hisukgyu@gmail.com")
        trusted_token = _token_for(trusted_user)

    def _fake_create_session(**_kwargs):
        return {
            "id": "lab_upload_01",
            "question_count": 3,
        }

    monkeypatch.setattr(
        "app.routes.manage.create_pdf_lab_session",
        _fake_create_session,
    )

    response = client.post(
        "/manage/pdf-lab",
        headers=_auth_header(trusted_token),
        data={
            "title": "업로드 테스트",
            "pdf_file": (io.BytesIO(b"%PDF-1.4\n"), "sample.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/manage/pdf-lab/lab_upload_01")


def test_pdf_lab_review_route_saves_comment(client, app, tmp_path):
    app.config["PDF_LAB_REVIEW_ROOT"] = tmp_path
    session_id = _seed_session(tmp_path)

    with app.app_context():
        trusted_user = _create_user("hisukgyu@gmail.com")
        trusted_token = _token_for(trusted_user)

    page = client.get(
        f"/manage/pdf-lab/{session_id}",
        headers=_auth_header(trusted_token),
    )
    assert page.status_code == 200
    assert "첫 번째 문항" in page.get_data(as_text=True)

    save = client.post(
        f"/manage/pdf-lab/{session_id}/review",
        headers=_auth_header(trusted_token),
        data={
            "review_index": "1",
            "status": "issue",
            "comment": "선지가 비정상적으로 합쳐짐",
            "navigation": "stay",
        },
        follow_redirects=True,
    )

    assert save.status_code == 200
    assert "문항 평가가 저장되었습니다." in save.get_data(as_text=True)

    report_payload = json.loads(
        (tmp_path / session_id / "report.json").read_text(encoding="utf-8")
    )
    assert report_payload["summary"]["issue_count"] == 1
    assert report_payload["issues"][0]["comment"] == "선지가 비정상적으로 합쳐짐"


def test_pdf_lab_delete_route_removes_session(client, app, tmp_path):
    app.config["PDF_LAB_REVIEW_ROOT"] = tmp_path
    session_id = _seed_session(tmp_path)

    with app.app_context():
        trusted_user = _create_user("hisukgyu@gmail.com")
        trusted_token = _token_for(trusted_user)

    response = client.post(
        f"/manage/pdf-lab/{session_id}/delete",
        headers=_auth_header(trusted_token),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "실험실 세션을 삭제했습니다" in response.get_data(as_text=True)
    assert not (tmp_path / session_id).exists()


def test_build_crop_lookup_prefers_first_single_part_when_duplicate_qnum_exists(tmp_path):
    crops_dir = tmp_path / "crops"
    crops_dir.mkdir()
    (crops_dir / "Q01_merged.png").write_bytes(b"png")
    (crops_dir / "Q01_p01_part1.png").write_bytes(b"png")
    (crops_dir / "Q01_p05_part1.png").write_bytes(b"png")
    (crops_dir / "bboxes.json").write_text(
        json.dumps(
            {
                "duplicate_qnums": [1],
                "questions": [
                    {
                        "qnum": 1,
                        "parts": [{"image": "Q01_p01_part1.png"}],
                    },
                    {
                        "qnum": 1,
                        "parts": [{"image": "Q01_p05_part1.png"}],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lookup = _build_crop_lookup(crops_dir)

    assert lookup == {"1": "Q01_p01_part1.png"}


def test_normalize_continuation_candidate_qnum_drops_page_top_option_number():
    assert _normalize_continuation_candidate_qnum(
        1,
        expected_qnum=20,
        is_continuation_candidate=True,
    ) is None
    assert _normalize_continuation_candidate_qnum(
        20,
        expected_qnum=20,
        is_continuation_candidate=True,
    ) == 20
    assert _normalize_continuation_candidate_qnum(
        1,
        expected_qnum=20,
        is_continuation_candidate=False,
    ) == 1
