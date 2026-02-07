"""Public Curriculum Template API - Browse and Clone templates."""
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import PublicCurriculumTemplate, Block, Lecture, User

api_public_curriculum_bp = Blueprint(
    "api_public_curriculum", __name__, url_prefix="/api/public/curriculums"
)


def _template_summary(template):
    return {
        "id": template.id,
        "title": template.title,
        "schoolTag": template.school_tag,
        "gradeTag": template.grade_tag,
        "subjectTag": template.subject_tag,
        "description": template.description,
        "createdAt": template.created_at.isoformat() if template.created_at else None,
    }


def _template_detail(template):
    payload = {}
    try:
        payload = json.loads(template.payload_json) if template.payload_json else {}
    except json.JSONDecodeError:
        pass
    return {
        **_template_summary(template),
        "payload": payload,
    }


@api_public_curriculum_bp.get("")
def list_templates():
    """List published templates with optional tag filters."""
    query = PublicCurriculumTemplate.query.filter_by(published=True)

    school = request.args.get("school") or request.args.get("schoolTag")
    grade = request.args.get("grade") or request.args.get("gradeTag")
    subject = request.args.get("subject") or request.args.get("subjectTag")
    q = request.args.get("q", "").strip()

    if school:
        query = query.filter(PublicCurriculumTemplate.school_tag == school)
    if grade:
        query = query.filter(PublicCurriculumTemplate.grade_tag == grade)
    if subject:
        query = query.filter(PublicCurriculumTemplate.subject_tag == subject)
    if q:
        query = query.filter(PublicCurriculumTemplate.title.contains(q))

    templates = query.order_by(PublicCurriculumTemplate.created_at.desc()).all()
    return jsonify({"ok": True, "data": [_template_summary(t) for t in templates]})


@api_public_curriculum_bp.get("/<int:template_id>")
def get_template(template_id):
    """Get template detail (must be published)."""
    template = PublicCurriculumTemplate.query.filter_by(
        id=template_id, published=True
    ).first()
    if not template:
        return jsonify({"ok": False, "code": "NOT_FOUND", "message": "Template not found"}), 404
    return jsonify({"ok": True, "data": _template_detail(template)})


@api_public_curriculum_bp.post("/<int:template_id>/clone")
@jwt_required()
def clone_template(template_id):
    """Clone a template into user's private workspace."""
    template = PublicCurriculumTemplate.query.filter_by(
        id=template_id, published=True
    ).first()
    if not template:
        return jsonify({"ok": False, "code": "NOT_FOUND", "message": "Template not found"}), 404

    user_id = int(get_jwt_identity())

    try:
        payload = json.loads(template.payload_json) if template.payload_json else {}
    except json.JSONDecodeError:
        return jsonify({"ok": False, "code": "INVALID_PAYLOAD", "message": "Template payload is invalid"}), 500

    created_block_ids = []
    created_lecture_ids = []

    blocks_data = payload.get("blocks", [])
    for block_data in blocks_data:
        block = Block(
            user_id=user_id,
            name=block_data.get("name", "Untitled Block"),
            description=block_data.get("description"),
            order=block_data.get("order", 0),
        )
        db.session.add(block)
        db.session.flush()
        created_block_ids.append(block.id)

        lectures_data = block_data.get("lectures", [])
        for lec_data in lectures_data:
            lecture = Lecture(
                user_id=user_id,
                block_id=block.id,
                title=lec_data.get("title", "Untitled Lecture"),
                professor=lec_data.get("professor"),
                order=lec_data.get("order", 0),
                description=lec_data.get("description"),
            )
            db.session.add(lecture)
            db.session.flush()
            created_lecture_ids.append(lecture.id)

    db.session.commit()

    return jsonify({
        "ok": True,
        "data": {
            "blockIds": created_block_ids,
            "lectureIds": created_lecture_ids,
        }
    }), 201
