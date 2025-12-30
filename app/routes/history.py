"""학습 이력 Blueprint"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from app import db
from app.models import Question, StudyHistory, UserNote, Block, Lecture

history_bp = Blueprint('history', __name__)


@history_bp.route('/')
def list_history():
    """학습 이력 목록"""
    histories = StudyHistory.query.order_by(StudyHistory.attempt_date.desc()).limit(100).all()
    return render_template('history/list.html', histories=histories)


@history_bp.route('/record', methods=['POST'])
def record_attempt():
    """문제 풀이 결과 기록"""
    question_id = request.form.get('question_id', type=int)
    is_correct = request.form.get('is_correct') == 'true'
    user_answer = request.form.get('user_answer')
    time_spent = request.form.get('time_spent', type=int)
    
    question = Question.query.get_or_404(question_id)
    
    history = StudyHistory(
        question_id=question_id,
        is_correct=is_correct,
        user_answer=user_answer,
        time_spent=time_spent
    )
    db.session.add(history)
    db.session.commit()
    
    # AJAX 요청인 경우 JSON 응답
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'history_id': history.id})
    
    flash('결과가 기록되었습니다.', 'success')
    return redirect(url_for('exam.view_question', 
                          exam_id=question.exam_id, 
                          question_number=question.question_number))


@history_bp.route('/stats')
def stats():
    """학습 통계"""
    total_attempts = StudyHistory.query.count()
    correct_count = StudyHistory.query.filter_by(is_correct=True).count()
    accuracy = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
    
    # 블록별 통계
    block_stats = []
    for block in Block.query.order_by(Block.order).all():
        block_questions = 0
        block_correct = 0
        for lecture in block.lectures:
            for question in lecture.questions:
                attempts = question.histories.count()
                if attempts > 0:
                    block_questions += attempts
                    block_correct += question.histories.filter_by(is_correct=True).count()
        
        block_stats.append({
            'block': block,
            'attempts': block_questions,
            'correct': block_correct,
            'accuracy': (block_correct / block_questions * 100) if block_questions > 0 else 0
        })
    
    return render_template('history/stats.html', 
                         total_attempts=total_attempts,
                         correct_count=correct_count,
                         accuracy=accuracy,
                         block_stats=block_stats)


@history_bp.route('/question/<int:question_id>')
def question_history(question_id):
    """특정 문제 학습 이력"""
    question = Question.query.get_or_404(question_id)
    histories = question.histories.order_by(StudyHistory.attempt_date.desc()).all()
    notes = question.notes.order_by(UserNote.updated_at.desc()).all()
    return render_template('history/question.html', 
                         question=question, 
                         histories=histories,
                         notes=notes)


# ===== 사용자 노트 =====

@history_bp.route('/note/add', methods=['POST'])
def add_note():
    """문제에 노트 추가"""
    question_id = request.form.get('question_id', type=int)
    note_text = request.form.get('note_text')
    
    question = Question.query.get_or_404(question_id)
    
    note = UserNote(
        question_id=question_id,
        note_text=note_text
    )
    db.session.add(note)
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'note_id': note.id})
    
    flash('노트가 추가되었습니다.', 'success')
    return redirect(url_for('exam.view_question',
                          exam_id=question.exam_id,
                          question_number=question.question_number))


@history_bp.route('/note/<int:note_id>/edit', methods=['POST'])
def edit_note(note_id):
    """노트 수정"""
    note = UserNote.query.get_or_404(note_id)
    note.note_text = request.form.get('note_text')
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True})
    
    flash('노트가 수정되었습니다.', 'success')
    return redirect(url_for('history.question_history', question_id=note.question_id))


@history_bp.route('/note/<int:note_id>/delete', methods=['POST'])
def delete_note(note_id):
    """노트 삭제"""
    note = UserNote.query.get_or_404(note_id)
    question_id = note.question_id
    db.session.delete(note)
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True})
    
    flash('노트가 삭제되었습니다.', 'success')
    return redirect(url_for('history.question_history', question_id=question_id))


# ===== 강의별 학습 =====

@history_bp.route('/lecture/<int:lecture_id>')
def lecture_study(lecture_id):
    """강의별 학습 현황"""
    lecture = Lecture.query.get_or_404(lecture_id)
    questions = lecture.questions.order_by(Question.exam_id, Question.question_number).all()
    
    # 각 문제별 학습 현황 계산
    question_stats = []
    for q in questions:
        attempts = q.histories.count()
        correct = q.histories.filter_by(is_correct=True).count()
        question_stats.append({
            'question': q,
            'attempts': attempts,
            'correct': correct,
            'accuracy': (correct / attempts * 100) if attempts > 0 else None
        })
    
    return render_template('history/lecture.html',
                         lecture=lecture,
                         question_stats=question_stats)
