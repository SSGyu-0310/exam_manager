import json

from app import db
from app.models import (
    Block,
    ClassificationJob,
    Lecture,
    PreviousExam,
    Question,
    Subject,
)
from app.services import ai_classifier as ai


class _DummyResponse:
    def __init__(self, text: str):
        self.text = text


class _DummyModels:
    def __init__(self, text: str):
        self._text = text

    def generate_content(self, **kwargs):
        return _DummyResponse(self._text)


class _DummyClient:
    def __init__(self, text: str):
        self.models = _DummyModels(text)


class _DummyModelsSequence:
    def __init__(self, texts):
        self._texts = list(texts)
        self.call_count = 0

    def generate_content(self, **kwargs):
        self.call_count += 1
        if not self._texts:
            raise AssertionError("No more mock responses configured")
        return _DummyResponse(self._texts.pop(0))


class _DummyClientWithModels:
    def __init__(self, models):
        self.models = models


class _DummyTypes:
    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class ThinkingConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


def _seed_question():
    block = Block(name="Physiology")
    db.session.add(block)
    db.session.flush()
    lecture = Lecture(block_id=block.id, title="Cardiac cycle", order=1)
    exam = PreviousExam(title="Mock Exam")
    db.session.add_all([lecture, exam])
    db.session.flush()
    question = Question(
        exam_id=exam.id,
        question_number=1,
        content="Which phase follows atrial systole?",
        q_type=Question.TYPE_MULTIPLE_CHOICE,
    )
    db.session.add(question)
    db.session.commit()
    return question, lecture


def _build_classifier(monkeypatch, response_text: str):
    monkeypatch.setattr(ai, "types", _DummyTypes, raising=False)
    classifier = ai.GeminiClassifier.__new__(ai.GeminiClassifier)
    classifier.client = _DummyClient(response_text)
    classifier.model_name = "mock-model"
    classifier.confidence_threshold = 0.7
    classifier.auto_apply_margin = 0.2
    return classifier


def _build_classifier_with_responses(monkeypatch, responses):
    monkeypatch.setattr(ai, "types", _DummyTypes, raising=False)
    response_texts = []
    for response in responses:
        if isinstance(response, str):
            response_texts.append(response)
        else:
            response_texts.append(json.dumps(response, ensure_ascii=False))
    models = _DummyModelsSequence(response_texts)
    classifier = ai.GeminiClassifier.__new__(ai.GeminiClassifier)
    classifier.client = _DummyClientWithModels(models)
    classifier.model_name = "mock-model"
    classifier.confidence_threshold = 0.7
    classifier.auto_apply_margin = 0.2
    return classifier, models


def test_classify_single_rejects_out_of_candidate_lecture_id(app, monkeypatch):
    with app.app_context():
        question, lecture = _seed_question()
        response = json.dumps(
            {
                "lecture_id": lecture.id + 999,
                "confidence": 0.9,
                "reason": "out of scope",
                "study_hint": "",
                "no_match": False,
                "evidence": [],
            }
        )
        classifier = _build_classifier(monkeypatch, response)
        candidates = [
            {
                "id": lecture.id,
                "full_path": "Physiology > Cardiac cycle",
                "evidence": [],
            }
        ]

        result = classifier.classify_single(question, candidates)
        assert result["lecture_id"] is None
        assert result["no_match"] is True


def test_classify_single_forces_no_match_when_quote_not_verbatim(app, monkeypatch):
    with app.app_context():
        question, lecture = _seed_question()
        response = json.dumps(
            {
                "lecture_id": lecture.id,
                "confidence": 0.88,
                "reason": "selected",
                "study_hint": "p.10",
                "no_match": False,
                "evidence": [
                    {
                        "lecture_id": lecture.id,
                        "page_start": 10,
                        "page_end": 10,
                        "chunk_id": 777,
                        "quote": "not-in-snippet",
                    }
                ],
            }
        )
        classifier = _build_classifier(monkeypatch, response)
        candidates = [
            {
                "id": lecture.id,
                "full_path": "Physiology > Cardiac cycle",
                "evidence": [
                    {
                        "page_start": 10,
                        "page_end": 10,
                        "snippet": "real snippet text",
                        "chunk_id": 777,
                    }
                ],
            }
        ]

        result = classifier.classify_single(question, candidates)
        assert result["lecture_id"] is None
        assert result["no_match"] is True
        assert result["evidence"] == []


def test_classify_single_invalid_json_falls_back_to_no_match(app, monkeypatch):
    with app.app_context():
        question, lecture = _seed_question()
        classifier = _build_classifier(monkeypatch, "this is not json")
        candidates = [
            {
                "id": lecture.id,
                "full_path": "Physiology > Cardiac cycle",
                "evidence": [],
            }
        ]

        result = classifier.classify_single(question, candidates)
        assert result["lecture_id"] is None
        assert result["no_match"] is True


def test_build_job_diagnostics_summarizes_reasons(app):
    with app.app_context():
        question, lecture = _seed_question()
        payload = ai.build_job_payload(
            {"signature": "sig-1"},
            [
                {
                    "question_id": question.id,
                    "lecture_id": lecture.id,
                    "confidence": 0.95,
                    "no_match": False,
                    "candidate_ids": [lecture.id],
                    "evidence": [{"chunk_id": 1}],
                    "reason": "high confidence",
                },
                {
                    "question_id": question.id + 1,
                    "lecture_id": None,
                    "confidence": 0.12,
                    "no_match": True,
                    "candidate_ids": [lecture.id],
                    "evidence": [],
                    "reason": "no grounding",
                },
            ],
        )
        job = ClassificationJob(
            status=ClassificationJob.STATUS_COMPLETED,
            total_count=2,
            processed_count=2,
            success_count=2,
            failed_count=0,
            result_json=json.dumps(payload, ensure_ascii=False),
        )
        db.session.add(job)
        db.session.commit()

        diagnostics = ai.build_job_diagnostics(
            job,
            question_ids=[question.id, question.id + 1, 999999],
            include_rows=True,
            row_limit=10,
        )

        summary = diagnostics["summary"]
        assert summary["requested_count"] == 3
        assert summary["inspected_count"] == 2
        assert summary["applyable_count"] == 1
        assert summary["no_match_count"] == 1
        assert summary["missing_result_count"] == 1
        assert len(diagnostics["rows"]) == 2


def test_resolve_exam_subject_lecture_ids_matches_block_subject(app):
    with app.app_context():
        physiology_block = Block(name="Physiology Block", subject="생리학")
        anatomy_block = Block(name="Anatomy Block", subject="해부학")
        db.session.add_all([physiology_block, anatomy_block])
        db.session.flush()

        physiology_lecture = Lecture(
            block_id=physiology_block.id,
            title="Cardiac Cycle",
            order=1,
        )
        anatomy_lecture = Lecture(
            block_id=anatomy_block.id,
            title="Upper Limb",
            order=1,
        )
        exam = PreviousExam(title="Mock", subject="생리학")
        db.session.add_all([physiology_lecture, anatomy_lecture, exam])
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            question_number=1,
            content="dummy",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
        )
        db.session.add(question)
        db.session.commit()

        lecture_ids = ai.resolve_exam_subject_lecture_ids(question)
        assert lecture_ids == [physiology_lecture.id]


def test_resolve_exam_subject_lecture_ids_matches_subject_ref(app):
    with app.app_context():
        subject = Subject(name="내과")
        db.session.add(subject)
        db.session.flush()

        block = Block(name="Internal Block", subject=None, subject_id=subject.id)
        other_block = Block(name="Other Block", subject="외과")
        db.session.add_all([block, other_block])
        db.session.flush()

        internal_lecture = Lecture(block_id=block.id, title="Renal", order=1)
        other_lecture = Lecture(block_id=other_block.id, title="Trauma", order=1)
        exam = PreviousExam(title="Mock", subject="내과")
        db.session.add_all([internal_lecture, other_lecture, exam])
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            question_number=1,
            content="dummy",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
        )
        db.session.add(question)
        db.session.commit()

        lecture_ids = ai.resolve_exam_subject_lecture_ids(question)
        assert lecture_ids == [internal_lecture.id]


def test_resolve_exam_subject_lecture_ids_returns_none_without_match(app):
    with app.app_context():
        block = Block(name="Anatomy Block", subject="해부학")
        db.session.add(block)
        db.session.flush()

        lecture = Lecture(block_id=block.id, title="Spine", order=1)
        exam = PreviousExam(title="Mock", subject="생리학")
        db.session.add_all([lecture, exam])
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            question_number=1,
            content="dummy",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
        )
        db.session.add(question)
        db.session.commit()

        lecture_ids = ai.resolve_exam_subject_lecture_ids(question)
        assert lecture_ids is None


def test_classify_single_rejudge_salvages_strict_match(app, monkeypatch):
    with app.app_context():
        question, lecture = _seed_question()
        extra_lecture_1 = Lecture(block_id=lecture.block_id, title="Hemodynamics", order=2)
        extra_lecture_2 = Lecture(block_id=lecture.block_id, title="Valve disease", order=3)
        db.session.add_all([extra_lecture_1, extra_lecture_2])
        db.session.commit()

        pass1 = {
            "lecture_id": None,
            "confidence": 0.21,
            "reason": "근거 부족",
            "study_hint": "",
            "no_match": True,
            "evidence": [],
        }
        pass2 = {
            "decision_mode": "strict_match",
            "lecture_id": lecture.id,
            "confidence": 0.86,
            "reason": "핵심 용어가 일치",
            "why_not_no_match": "직접 근거가 충분함",
            "evidence": [
                {
                    "lecture_id": lecture.id,
                    "page_start": 10,
                    "page_end": 10,
                    "chunk_id": 777,
                    "quote": "real snippet text",
                }
            ],
        }

        classifier, models = _build_classifier_with_responses(monkeypatch, [pass1, pass2])
        monkeypatch.setenv("CLASSIFIER_REJUDGE_ENABLED", "1")
        monkeypatch.setenv("CLASSIFIER_REJUDGE_MIN_CANDIDATES", "3")
        monkeypatch.setenv("CLASSIFIER_REJUDGE_MIN_CONFIDENCE_STRICT", "0.80")
        monkeypatch.setattr(
            ai.GeminiClassifier,
            "_prepare_rejudge_candidates",
            lambda self, _question, _choices, candidates: candidates,
        )

        candidates = [
            {
                "id": lecture.id,
                "full_path": "Physiology > Cardiac cycle",
                "evidence": [
                    {
                        "page_start": 10,
                        "page_end": 10,
                        "snippet": "real snippet text",
                        "chunk_id": 777,
                    }
                ],
            },
            {
                "id": extra_lecture_1.id,
                "full_path": "Physiology > Hemodynamics",
                "evidence": [
                    {
                        "page_start": 11,
                        "page_end": 11,
                        "snippet": "different snippet",
                        "chunk_id": 778,
                    }
                ],
            },
            {
                "id": extra_lecture_2.id,
                "full_path": "Physiology > Valve disease",
                "evidence": [
                    {
                        "page_start": 12,
                        "page_end": 12,
                        "snippet": "another snippet",
                        "chunk_id": 779,
                    }
                ],
            },
        ]

        result = classifier.classify_single(question, candidates)
        assert models.call_count == 2
        assert result["lecture_id"] == lecture.id
        assert result["no_match"] is False
        assert result["decision_mode"] == "strict_match"
        assert result["rejudge_attempted"] is True
        assert result["rejudge_decision_mode"] == "strict_match"
        assert result["final_decision_source"] == "pass2"


def test_weak_match_is_kept_but_not_auto_applied(app, monkeypatch):
    with app.app_context():
        question, lecture = _seed_question()
        extra_lecture_1 = Lecture(block_id=lecture.block_id, title="Hemodynamics", order=2)
        extra_lecture_2 = Lecture(block_id=lecture.block_id, title="Valve disease", order=3)
        db.session.add_all([extra_lecture_1, extra_lecture_2])
        db.session.commit()

        pass1 = {
            "lecture_id": None,
            "confidence": 0.19,
            "reason": "불확실",
            "study_hint": "",
            "no_match": True,
            "evidence": [],
        }
        pass2 = {
            "decision_mode": "weak_match",
            "lecture_id": lecture.id,
            "confidence": 0.72,
            "reason": "부분 일치",
            "why_not_no_match": "단서는 있으나 강하지 않음",
            "evidence": [
                {
                    "lecture_id": lecture.id,
                    "page_start": 10,
                    "page_end": 10,
                    "chunk_id": 777,
                    "quote": "real snippet text",
                }
            ],
        }

        classifier, _ = _build_classifier_with_responses(monkeypatch, [pass1, pass2])
        monkeypatch.setenv("CLASSIFIER_REJUDGE_ENABLED", "1")
        monkeypatch.setenv("CLASSIFIER_REJUDGE_MIN_CANDIDATES", "3")
        monkeypatch.setenv("CLASSIFIER_REJUDGE_ALLOW_WEAK_MATCH", "1")
        monkeypatch.setenv("CLASSIFIER_REJUDGE_MIN_CONFIDENCE_WEAK", "0.65")
        monkeypatch.setattr(
            ai.GeminiClassifier,
            "_prepare_rejudge_candidates",
            lambda self, _question, _choices, candidates: candidates,
        )

        candidates = [
            {
                "id": lecture.id,
                "full_path": "Physiology > Cardiac cycle",
                "evidence": [
                    {
                        "page_start": 10,
                        "page_end": 10,
                        "snippet": "real snippet text",
                        "chunk_id": 777,
                    }
                ],
            },
            {"id": extra_lecture_1.id, "full_path": "Physiology > Hemodynamics", "evidence": []},
            {"id": extra_lecture_2.id, "full_path": "Physiology > Valve disease", "evidence": []},
        ]
        result = classifier.classify_single(question, candidates)
        assert result["lecture_id"] == lecture.id
        assert result["decision_mode"] == "weak_match"
        assert result["final_decision_source"] == "pass2"

        payload = ai.build_job_payload(
            {"signature": "weak-1"},
            [
                {
                    **result,
                    "question_id": question.id,
                    "candidate_ids": [lecture.id, extra_lecture_1.id, extra_lecture_2.id],
                }
            ],
        )
        job = ClassificationJob(
            status=ClassificationJob.STATUS_COMPLETED,
            total_count=1,
            processed_count=1,
            success_count=1,
            failed_count=0,
            result_json=json.dumps(payload, ensure_ascii=False),
        )
        db.session.add(job)
        db.session.commit()

        app.config["AI_AUTO_APPLY"] = True
        app.config["AI_CONFIDENCE_THRESHOLD"] = 0.7
        app.config["AI_AUTO_APPLY_MARGIN"] = 0.1

        applied_count, report = ai.apply_classification_results(
            [question.id],
            job.id,
            apply_mode="changed",
            return_report=True,
        )
        db.session.refresh(question)

        assert applied_count == 0
        assert report["weak_match_skip_count"] == 1
        assert question.ai_suggested_lecture_id == lecture.id
        assert question.lecture_id is None


def test_rejudge_disabled_keeps_pass1_behavior(app, monkeypatch):
    with app.app_context():
        question, lecture = _seed_question()
        extra_lecture_1 = Lecture(block_id=lecture.block_id, title="Hemodynamics", order=2)
        extra_lecture_2 = Lecture(block_id=lecture.block_id, title="Valve disease", order=3)
        db.session.add_all([extra_lecture_1, extra_lecture_2])
        db.session.commit()

        classifier, models = _build_classifier_with_responses(
            monkeypatch,
            [
                {
                    "lecture_id": None,
                    "confidence": 0.2,
                    "reason": "no match",
                    "study_hint": "",
                    "no_match": True,
                    "evidence": [],
                }
            ],
        )
        monkeypatch.setenv("CLASSIFIER_REJUDGE_ENABLED", "0")
        monkeypatch.setattr(
            ai.GeminiClassifier,
            "_prepare_rejudge_candidates",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
        )

        candidates = [
            {"id": lecture.id, "full_path": "Physiology > Cardiac cycle", "evidence": []},
            {"id": extra_lecture_1.id, "full_path": "Physiology > Hemodynamics", "evidence": []},
            {"id": extra_lecture_2.id, "full_path": "Physiology > Valve disease", "evidence": []},
        ]
        result = classifier.classify_single(question, candidates)

        assert models.call_count == 1
        assert result["lecture_id"] is None
        assert result["no_match"] is True
        assert result["rejudge_attempted"] is False
        assert result["final_decision_source"] == "pass1"


def test_rejudge_not_attempted_when_candidates_below_minimum(app, monkeypatch):
    with app.app_context():
        question, lecture = _seed_question()
        extra_lecture = Lecture(block_id=lecture.block_id, title="Hemodynamics", order=2)
        db.session.add(extra_lecture)
        db.session.commit()

        classifier, models = _build_classifier_with_responses(
            monkeypatch,
            [
                {
                    "lecture_id": None,
                    "confidence": 0.2,
                    "reason": "no match",
                    "study_hint": "",
                    "no_match": True,
                    "evidence": [],
                }
            ],
        )
        monkeypatch.setenv("CLASSIFIER_REJUDGE_ENABLED", "1")
        monkeypatch.setenv("CLASSIFIER_REJUDGE_MIN_CANDIDATES", "3")

        candidates = [
            {"id": lecture.id, "full_path": "Physiology > Cardiac cycle", "evidence": []},
            {"id": extra_lecture.id, "full_path": "Physiology > Hemodynamics", "evidence": []},
        ]
        result = classifier.classify_single(question, candidates)

        assert models.call_count == 1
        assert result["rejudge_attempted"] is False
        assert result["final_decision_source"] == "pass1"


def test_build_job_diagnostics_counts_rejudge_metrics(app):
    with app.app_context():
        payload = ai.build_job_payload(
            {"signature": "diag-rejudge"},
            [
                {
                    "question_id": 1,
                    "lecture_id": 101,
                    "confidence": 0.91,
                    "no_match": False,
                    "candidate_ids": [101, 102],
                    "evidence": [{"chunk_id": 11}],
                    "decision_mode": "strict_match",
                    "rejudge_attempted": True,
                    "rejudge_decision_mode": "strict_match",
                    "final_decision_source": "pass2",
                },
                {
                    "question_id": 2,
                    "lecture_id": 102,
                    "confidence": 0.70,
                    "no_match": False,
                    "candidate_ids": [102, 103],
                    "evidence": [{"chunk_id": 12}],
                    "decision_mode": "weak_match",
                    "rejudge_attempted": True,
                    "rejudge_decision_mode": "weak_match",
                    "final_decision_source": "pass2",
                },
                {
                    "question_id": 3,
                    "lecture_id": None,
                    "confidence": 0.1,
                    "no_match": True,
                    "candidate_ids": [104, 105],
                    "evidence": [],
                    "decision_mode": "no_match",
                    "rejudge_attempted": False,
                    "final_decision_source": "pass1",
                },
            ],
        )
        job = ClassificationJob(
            status=ClassificationJob.STATUS_COMPLETED,
            total_count=3,
            processed_count=3,
            success_count=3,
            failed_count=0,
            result_json=json.dumps(payload, ensure_ascii=False),
        )
        db.session.add(job)
        db.session.commit()

        diagnostics = ai.build_job_diagnostics(job, include_rows=False)
        summary = diagnostics["summary"]

        assert summary["rejudge_attempted_count"] == 2
        assert summary["rejudge_salvaged_count"] == 2
        assert summary["weak_match_count"] == 1
