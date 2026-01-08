from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.mysql import LONGTEXT

from .database import Base


class QuizRecord(Base):
    """Database table for storing a quiz run for a given Wikipedia URL."""

    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), index=True, unique=True, nullable=False)
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    key_entities_json = Column(Text, nullable=True)
    sections_json = Column(Text, nullable=True)
    quiz_json = Column(Text, nullable=False)  # list of questions as JSON
    related_topics_json = Column(Text, nullable=True)
    raw_html = Column(LONGTEXT, nullable=True)  # Store full page HTML (can be very large)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


