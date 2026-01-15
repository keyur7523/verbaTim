"""Create conversation tables

Revision ID: 0001
Revises:
Create Date: 2026-01-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("condition", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("intent_id", sa.String(100), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("total_duration_ms", sa.Integer(), nullable=True),
        sa.Column("turn_count", sa.Integer(), nullable=True),
        sa.Column("completed_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_conversation_runs_timestamp", "conversation_runs", ["timestamp"])
    op.create_index("ix_conversation_runs_condition", "conversation_runs", ["condition"])
    op.create_index("ix_conversation_runs_status", "conversation_runs", ["status"])

    op.create_table(
        "conversation_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_runs.id"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("assistant_text", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_conversation_turns_run_id", "conversation_turns", ["run_id"])
    op.create_index("ix_conversation_turns_run_turn", "conversation_turns", ["run_id", "turn_index"])

    op.create_table(
        "turn_evaluator_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_turns.id"), nullable=False),
        sa.Column("evaluator_name", sa.String(100), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_turn_evaluator_results_turn_id", "turn_evaluator_results", ["turn_id"])
    op.create_index("ix_turn_evaluator_results_evaluator_name", "turn_evaluator_results", ["evaluator_name"])

    op.create_table(
        "conversation_evaluator_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_runs.id"), nullable=False),
        sa.Column("evaluator_name", sa.String(100), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_conversation_evaluator_results_run_id", "conversation_evaluator_results", ["run_id"])
    op.create_index(
        "ix_conversation_evaluator_results_evaluator_name",
        "conversation_evaluator_results",
        ["evaluator_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_evaluator_results_evaluator_name", table_name="conversation_evaluator_results")
    op.drop_index("ix_conversation_evaluator_results_run_id", table_name="conversation_evaluator_results")
    op.drop_table("conversation_evaluator_results")

    op.drop_index("ix_turn_evaluator_results_evaluator_name", table_name="turn_evaluator_results")
    op.drop_index("ix_turn_evaluator_results_turn_id", table_name="turn_evaluator_results")
    op.drop_table("turn_evaluator_results")

    op.drop_index("ix_conversation_turns_run_turn", table_name="conversation_turns")
    op.drop_index("ix_conversation_turns_run_id", table_name="conversation_turns")
    op.drop_table("conversation_turns")

    op.drop_index("ix_conversation_runs_status", table_name="conversation_runs")
    op.drop_index("ix_conversation_runs_condition", table_name="conversation_runs")
    op.drop_index("ix_conversation_runs_timestamp", table_name="conversation_runs")
    op.drop_table("conversation_runs")
