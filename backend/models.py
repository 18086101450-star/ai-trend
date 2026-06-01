from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.sql import func
from backend.database import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, index=True)
    category = Column(String(100), default="General")
    explanation = Column(Text, default="")
    meaning = Column(Text, default="")
    application = Column(Text, default="")
    source = Column(String(100), default="arxiv")
    source_url = Column(Text, default="")
    frequency = Column(Integer, default=1)
    trend_score = Column(Float, default=0.0)
    is_trending = Column(Boolean, default=False)
    is_emerging = Column(Boolean, default=False)
    related_keywords = Column(JSON, default=list)
    first_seen = Column(DateTime, server_default=func.now())
    last_seen = Column(DateTime, server_default=func.now(), onupdate=func.now())
    weekly_counts = Column(JSON, default=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "keyword": self.keyword,
            "category": self.category,
            "explanation": self.explanation,
            "meaning": self.meaning,
            "application": self.application,
            "source": self.source,
            "frequency": self.frequency,
            "trend_score": self.trend_score,
            "is_trending": self.is_trending,
            "is_emerging": self.is_emerging,
            "related_keywords": self.related_keywords or [],
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class TrendPrediction(Base):
    __tablename__ = "trend_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    category = Column(String(100), default="General")
    confidence = Column(Float, default=0.0)
    keywords_involved = Column(JSON, default=list)
    predicted_impact = Column(String(50), default="medium")
    time_horizon = Column(String(50), default="short-term")
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "confidence": self.confidence,
            "keywords_involved": self.keywords_involved or [],
            "predicted_impact": self.predicted_impact,
            "time_horizon": self.time_horizon,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScanRecord(Base):
    __tablename__ = "scan_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(50), default="running")
    sources_scanned = Column(JSON, default=list)
    keywords_found = Column(Integer, default=0)
    predictions_made = Column(Integer, default=0)
    error = Column(Text, default="")
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "sources_scanned": self.sources_scanned or [],
            "keywords_found": self.keywords_found,
            "predictions_made": self.predictions_made,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
