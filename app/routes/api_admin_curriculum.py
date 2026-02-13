"""Admin API for managing Public Curriculum Templates."""
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import PublicCurriculumTemplate, User

api_admin_curriculum_bp = Blueprint(
    "api_admin_curriculum", __name__, url_prefix="/api/admin/public/curriculums"
)


def _require_admin():
    """Check if current user is admin. Returns (user, error_response)."""
    user_id = get_jwt_identity()
    if not user_id:
        return None, (jsonify({"ok": False, "code": "UNAUTHORIZED", "message": "Authentication required"}), 401)
    user = db.session.get(User, int(user_id))
    if not user or not user.is_admin:
        return None, (jsonify({"ok": False, "code": "FORBIDDEN", "message": "Admin access required"}), 403)
    return user, None


def _template_payload(template):
    payload = {}
    try:
        payload = json.loads(template.payload_json) if template.payload_json else {}
    except json.JSONDecodeError:
        pass
    return {
        "id": template.id,
        "title": template.title,
        "schoolTag": template.school_tag,
        "gradeTag": template.grade_tag,
        "subjectTag": template.subject_tag,
        "description": template.description,
        "payload": payload,
        "published": template.published,
        "createdBy": template.created_by,
        "createdAt": template.created_at.isoformat() if template.created_at else None,
        "updatedAt": template.updated_at.isoformat() if template.updated_at else None,
    }


@api_admin_curriculum_bp.get("")
@jwt_required()
def list_all_templates():
    """List all templates (including unpublished) for admin."""
    user, error = _require_admin()
    if error:
        return error
    templates = PublicCurriculumTemplate.query.order_by(
        PublicCurriculumTemplate.created_at.desc()
    ).all()
    return jsonify({"ok": True, "data": [_template_payload(t) for t in templates]})


@api_admin_curriculum_bp.post("")
@jwt_required()
def create_template():
    """Create a new template."""
    user, error = _require_admin()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title:
        return jsonify({"ok": False, "code": "TITLE_REQUIRED", "message": "Title is required"}), 400

    payload = data.get("payload", {})
    template = PublicCurriculumTemplate(
        title=title,
        school_tag=data.get("schoolTag"),
        grade_tag=data.get("gradeTag"),
        subject_tag=data.get("subjectTag"),
        description=data.get("description"),
        payload_json=json.dumps({**payload, "schemaVersion": 1}, ensure_ascii=False),
        published=False,
        created_by=user.id,
    )
    db.session.add(template)
    db.session.commit()
    return jsonify({"ok": True, "data": _template_payload(template)}), 201


@api_admin_curriculum_bp.get("/<int:template_id>")
@jwt_required()
def get_template(template_id):
    """Get template detail for admin."""
    user, error = _require_admin()
    if error:
        return error
    template = db.session.get(PublicCurriculumTemplate, template_id)
    if not template:
        return jsonify({"ok": False, "code": "NOT_FOUND", "message": "Template not found"}), 404
    return jsonify({"ok": True, "data": _template_payload(template)})


@api_admin_curriculum_bp.patch("/<int:template_id>")
@jwt_required()
def update_template(template_id):
    """Update template."""
    user, error = _require_admin()
    if error:
        return error

    template = db.session.get(PublicCurriculumTemplate, template_id)
    if not template:
        return jsonify({"ok": False, "code": "NOT_FOUND", "message": "Template not found"}), 404

    data = request.get_json(silent=True) or {}
    if "title" in data:
        template.title = data["title"]
    if "schoolTag" in data:
        template.school_tag = data["schoolTag"]
    if "gradeTag" in data:
        template.grade_tag = data["gradeTag"]
    if "subjectTag" in data:
        template.subject_tag = data["subjectTag"]
    if "description" in data:
        template.description = data["description"]
    if "payload" in data:
        template.payload_json = json.dumps(data["payload"], ensure_ascii=False)

    db.session.commit()
    return jsonify({"ok": True, "data": _template_payload(template)})


@api_admin_curriculum_bp.post("/<int:template_id>/publish")
@jwt_required()
def publish_template(template_id):
    """Publish a template."""
    user, error = _require_admin()
    if error:
        return error

    template = db.session.get(PublicCurriculumTemplate, template_id)
    if not template:
        return jsonify({"ok": False, "code": "NOT_FOUND", "message": "Template not found"}), 404

    template.published = True
    db.session.commit()
    return jsonify({"ok": True, "data": _template_payload(template)})


@api_admin_curriculum_bp.post("/<int:template_id>/unpublish")
@jwt_required()
def unpublish_template(template_id):
    """Unpublish a template."""
    user, error = _require_admin()
    if error:
        return error

    template = db.session.get(PublicCurriculumTemplate, template_id)
    if not template:
        return jsonify({"ok": False, "code": "NOT_FOUND", "message": "Template not found"}), 404

    template.published = False
    db.session.commit()
    return jsonify({"ok": True, "data": _template_payload(template)})


@api_admin_curriculum_bp.delete("/<int:template_id>")
@jwt_required()
def delete_template(template_id):
    """Delete a template."""
    user, error = _require_admin()
    if error:
        return error

    template = db.session.get(PublicCurriculumTemplate, template_id)
    if not template:
        return jsonify({"ok": False, "code": "NOT_FOUND", "message": "Template not found"}), 404

    db.session.delete(template)
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": template_id}})
