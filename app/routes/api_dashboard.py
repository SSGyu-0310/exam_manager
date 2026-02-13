from flask import Blueprint, jsonify, request
from sqlalchemy import func, case
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from app import db
from app.models import (
    Block, Lecture, PreviousExam, Question, 
    PracticeSession, PracticeAnswer, UserNote
)
from app.services.user_scope import attach_current_user, current_user, scope_model, scope_query
from app.services.manage_service import get_dashboard_stats

api_dashboard_bp = Blueprint('api_dashboard', __name__)

@api_dashboard_bp.before_request
def auth_required():
    return attach_current_user(require=True)

@api_dashboard_bp.route('/api/dashboard/stats')
def dashboard_stats():
    user = current_user()
    return jsonify({
        'ok': True,
        'data': get_dashboard_stats(user)
    })

@api_dashboard_bp.route('/api/dashboard/progress')
def get_progress():
    user = current_user()
    today = datetime.utcnow().date()
    # Last 7 days including today
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    window_start = days[0] - timedelta(days=7)
    window_end = today + timedelta(days=1)

    rows = (
        db.session.query(
            func.date(PracticeAnswer.answered_at).label("day"),
            func.count(PracticeAnswer.id).label("total"),
            func.sum(case((PracticeAnswer.is_correct.is_(True), 1), else_=0)).label(
                "correct"
            ),
        )
        .join(PracticeSession, PracticeAnswer.session_id == PracticeSession.id)
        .filter(
            PracticeSession.user_id == user.id,
            PracticeAnswer.answered_at >= datetime.combine(
                window_start, datetime.min.time()
            ),
            PracticeAnswer.answered_at < datetime.combine(
                window_end, datetime.min.time()
            ),
        )
        .group_by("day")
        .all()
    )

    stats_by_day = {}
    for row in rows:
        day_value = row.day
        if isinstance(day_value, str):
            try:
                day_value = datetime.fromisoformat(day_value).date()
            except ValueError:
                continue
        stats_by_day[day_value] = {
            "total": int(row.total or 0),
            "correct": int(row.correct or 0),
        }

    daily_stats = []
    for day in days:
        stats = stats_by_day.get(day, {"total": 0, "correct": 0})
        daily_stats.append(
            {
                "date": day.isoformat(),
                "correct": stats["correct"],
                "total": stats["total"],
            }
        )

    last_week_days = [window_start + timedelta(days=i) for i in range(7)]
    last_week_total = sum(
        stats_by_day.get(day, {"total": 0})["total"] for day in last_week_days
    )
    this_week_total = sum(d["total"] for d in daily_stats)
    
    change = 0
    if last_week_total > 0:
        change = ((this_week_total - last_week_total) / last_week_total) * 100
    elif this_week_total > 0:
        change = 100.0
        
    return jsonify({
        'ok': True,
        'data': {
            'daily': daily_stats,
            'thisWeekTotal': this_week_total,
            'lastWeekTotal': last_week_total,
            'changePercent': round(change, 1)
        }
    })

@api_dashboard_bp.route('/api/dashboard/bookmarks')
def get_bookmarks():
    user = current_user()
    # Return questions with user notes
    questions = (
        scope_query(Question.query, Question, user)
        .join(UserNote)
        .options(selectinload(Question.lecture))
        .order_by(UserNote.updated_at.desc())
        .limit(5)
        .all()
    )
    
    return jsonify({
        'ok': True,
        'data': [
            {
                'id': q.id,
                'title': f"Q{q.question_number}: {q.content[:30]}..." if q.content else f"Question {q.question_number}",
                'lectureId': q.lecture_id,
                'lectureTitle': q.lecture.title if q.lecture else None,
                'type': 'note'
            } for q in questions
        ]
    })

@api_dashboard_bp.route('/api/review/notes')
def review_notes():
    user = current_user()

    note_rows = (
        scope_query(Question.query, Question, user)
        .join(UserNote)
        .with_entities(Question.id)
        .distinct()
        .all()
    )
    note_ids = {row[0] for row in note_rows}

    failed_rows = (
        scope_query(Question.query, Question, user)
        .join(PracticeAnswer, PracticeAnswer.question_id == Question.id)
        .filter(PracticeAnswer.is_correct.is_(False))
        .with_entities(Question.id)
        .distinct()
        .all()
    )
    failed_ids = {row[0] for row in failed_rows}

    question_ids = note_ids | failed_ids
    if not question_ids:
        return jsonify({'ok': True, 'data': []})

    user_wrong_rows = (
        db.session.query(PracticeAnswer.question_id)
        .join(PracticeSession, PracticeAnswer.session_id == PracticeSession.id)
        .filter(
            PracticeSession.user_id == user.id,
            PracticeAnswer.is_correct.is_(False),
            PracticeAnswer.question_id.in_(question_ids),
        )
        .distinct()
        .all()
    )
    user_wrong_ids = {row[0] for row in user_wrong_rows}

    questions = (
        scope_query(Question.query, Question, user)
        .options(selectinload(Question.exam), selectinload(Question.lecture))
        .filter(Question.id.in_(question_ids))
        .order_by(Question.id)
        .all()
    )
    
    return jsonify({
        'ok': True,
        'data': [
            {
                'id': q.id,
                'questionNumber': q.question_number,
                'content': q.content[:100] + "..." if q.content else "",
                'examTitle': q.exam.title,
                'lectureTitle': q.lecture.title if q.lecture else None,
                'hasNote': q.id in note_ids,
                'isWrong': q.id in user_wrong_ids,
            } for q in questions
        ]
    })

@api_dashboard_bp.route('/api/review/weakness')
def review_weakness():
    user = current_user()
    blocks = scope_model(Block, user, include_public=True).all()
    block_ids = [block.id for block in blocks]
    if not block_ids:
        return jsonify({'ok': True, 'data': []})

    rows = (
        db.session.query(
            Lecture.block_id,
            func.count(PracticeAnswer.id).label("total"),
            func.sum(case((PracticeAnswer.is_correct.is_(True), 1), else_=0)).label(
                "correct"
            ),
        )
        .join(PracticeSession, PracticeAnswer.session_id == PracticeSession.id)
        .join(Question, PracticeAnswer.question_id == Question.id)
        .join(Lecture, Question.lecture_id == Lecture.id)
        .filter(
            PracticeSession.user_id == user.id,
            Lecture.block_id.in_(block_ids),
        )
        .group_by(Lecture.block_id)
        .all()
    )

    block_lookup = {block.id: block for block in blocks}
    weakness_data = []
    for row in rows:
        total = int(row.total or 0)
        if total <= 0:
            continue
        correct = int(row.correct or 0)
        block = block_lookup.get(row.block_id)
        if not block:
            continue
        accuracy = (correct / total) * 100
        weakness_data.append(
            {
                "blockId": block.id,
                "blockName": block.name,
                "accuracy": round(accuracy, 1),
                "totalAnswered": total,
            }
        )
            
    return jsonify({
        'ok': True,
        'data': sorted(weakness_data, key=lambda x: x['accuracy'])
    })

@api_dashboard_bp.route('/api/review/history')
def review_history():
    user = current_user()
    sessions = (
        scope_query(PracticeSession.query, PracticeSession, user)
        .options(selectinload(PracticeSession.lecture))
        .order_by(PracticeSession.created_at.desc())
        .all()
    )
    session_ids = [session.id for session in sessions]
    counts_by_session = {}
    if session_ids:
        rows = (
            db.session.query(
                PracticeAnswer.session_id,
                func.count(PracticeAnswer.id).label("total"),
                func.sum(case((PracticeAnswer.is_correct.is_(True), 1), else_=0)).label(
                    "correct"
                ),
            )
            .filter(PracticeAnswer.session_id.in_(session_ids))
            .group_by(PracticeAnswer.session_id)
            .all()
        )
        counts_by_session = {
            row.session_id: {
                "total": int(row.total or 0),
                "correct": int(row.correct or 0),
            }
            for row in rows
        }
    
    return jsonify({
        'ok': True,
        'data': [
            {
                'id': s.id,
                'lectureTitle': s.lecture.title if s.lecture else "Mixed",
                'createdAt': s.created_at.isoformat(),
                'finishedAt': s.finished_at.isoformat() if s.finished_at else None,
                'correctCount': counts_by_session.get(s.id, {}).get("correct", 0),
                'totalCount': counts_by_session.get(s.id, {}).get("total", 0),
                'mode': s.mode
            } for s in sessions
        ]
    })

@api_dashboard_bp.route('/api/dashboard/config')
def get_dashboard_config():
    from flask import current_app
    return jsonify({
        'ok': True,
        'data': {
            'pdf_parser': current_app.config.get('PDF_PARSER_MODE', 'legacy'),
            'local_admin': current_app.config.get('LOCAL_ADMIN_ONLY', False),
            'version': '1.0.0 (Core Features Implemented)',
            'build_date': datetime.utcnow().date().isoformat()
        }
    })
