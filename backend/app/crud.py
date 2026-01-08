import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import models


def get_quiz_by_url(session: Session, url: str) -> Optional[models.QuizRecord]:
    """Return the quiz record for a URL if it already exists (cache hit)."""
    return session.query(models.QuizRecord).filter(models.QuizRecord.url == url).first()


def get_quiz_by_id(session: Session, quiz_id: int) -> Optional[models.QuizRecord]:
    """Return a quiz by database ID."""
    return session.query(models.QuizRecord).filter(models.QuizRecord.id == quiz_id).first()


def list_quizzes(session: Session) -> List[models.QuizRecord]:
    """Return all quizzes ordered by creation time (newest first)."""
    return (
        session.query(models.QuizRecord)
        .order_by(models.QuizRecord.created_at.desc())
        .all()
    )


def create_quiz(
    session: Session,
    url: str,
    raw_html: str,
    analysis: Dict[str, Any],
    quiz_items: List[Dict[str, Any]],
    related_topics: List[str],
) -> models.QuizRecord:
    """Create and save a new quiz record in the database."""
    record = models.QuizRecord(
        url=url,
        title=analysis.get("title"),
        summary=analysis.get("summary"),
        key_entities_json=json.dumps(analysis.get("key_entities", {}), ensure_ascii=False),
        sections_json=json.dumps(analysis.get("sections", []), ensure_ascii=False),
        quiz_json=json.dumps(quiz_items, ensure_ascii=False),
        related_topics_json=json.dumps(related_topics, ensure_ascii=False),
        raw_html=raw_html,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def quiz_to_dict(record: models.QuizRecord) -> Dict[str, Any]:
    """Convert a DB row to a full JSON-friendly dict."""
    return {
        "id": record.id,
        "url": record.url,
        "title": record.title,
        "summary": record.summary,
        "key_entities": json.loads(record.key_entities_json or "{}"),
        "sections": json.loads(record.sections_json or "[]"),
        "quiz": json.loads(record.quiz_json or "[]"),
        "related_topics": json.loads(record.related_topics_json or "[]"),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def quiz_summary_to_dict(record: models.QuizRecord) -> Dict[str, Any]:
    """Convert a DB row to a short summary for the history list."""
    return {
        "id": record.id,
        "url": record.url,
        "title": record.title,
        "summary": (record.summary or "")[:300],
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


