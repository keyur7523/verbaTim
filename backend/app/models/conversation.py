import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean, ForeignKey, Enum, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.evaluation import RunStatus


class ConversationRun(Base):
    __tablename__ = "conversation_runs"
    __table_args__ = (
        Index("ix_conversation_runs_timestamp", "timestamp"),
        Index("ix_conversation_runs_condition", "condition"),
        Index("ix_conversation_runs_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition = Column(String(50), nullable=False)  # baseline | naive | budgeted | verbatim
    model = Column(String(100), nullable=False)
    status = Column(Enum(RunStatus), default=RunStatus.PENDING)
    timestamp = Column(DateTime, default=datetime.utcnow)
    intent_id = Column(String(100), nullable=True)
    system_prompt = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)
    total_cost_usd = Column(Float, default=0.0)
    total_duration_ms = Column(Integer, default=0)
    turn_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    turns = relationship("ConversationTurn", back_populates="run", cascade="all, delete-orphan")
    evaluator_results = relationship("ConversationEvaluatorResult", back_populates="run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ConversationRun(id={self.id}, condition={self.condition}, status={self.status})>"


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (
        Index("ix_conversation_turns_run_id", "run_id"),
        Index("ix_conversation_turns_run_turn", "run_id", "turn_index"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("conversation_runs.id"), nullable=False)
    turn_index = Column(Integer, nullable=False)
    user_text = Column(Text, nullable=False)
    assistant_text = Column(Text, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    fallback_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("ConversationRun", back_populates="turns")
    evaluator_results = relationship("TurnEvaluatorResult", back_populates="turn", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ConversationTurn(id={self.id}, index={self.turn_index})>"


class TurnEvaluatorResult(Base):
    __tablename__ = "turn_evaluator_results"
    __table_args__ = (
        Index("ix_turn_evaluator_results_turn_id", "turn_id"),
        Index("ix_turn_evaluator_results_evaluator_name", "evaluator_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turn_id = Column(UUID(as_uuid=True), ForeignKey("conversation_turns.id"), nullable=False)
    evaluator_name = Column(String(100), nullable=False)
    passed = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    turn = relationship("ConversationTurn", back_populates="evaluator_results")

    def __repr__(self):
        return f"<TurnEvaluatorResult(id={self.id}, evaluator={self.evaluator_name})>"


class ConversationEvaluatorResult(Base):
    __tablename__ = "conversation_evaluator_results"
    __table_args__ = (
        Index("ix_conversation_evaluator_results_run_id", "run_id"),
        Index("ix_conversation_evaluator_results_evaluator_name", "evaluator_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("conversation_runs.id"), nullable=False)
    evaluator_name = Column(String(100), nullable=False)
    passed = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("ConversationRun", back_populates="evaluator_results")

    def __repr__(self):
        return f"<ConversationEvaluatorResult(id={self.id}, evaluator={self.evaluator_name})>"
