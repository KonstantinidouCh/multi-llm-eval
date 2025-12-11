"""Initial schema for LLM models and evaluations

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create llm_models table
    op.create_table(
        'llm_models',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('provider', sa.String(50), nullable=False, index=True),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Create evaluations table
    op.create_table(
        'evaluations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True, index=True),
        sa.Column('fastest', sa.String(100), default=''),
        sa.Column('highest_quality', sa.String(100), default=''),
        sa.Column('most_cost_effective', sa.String(100), default=''),
        sa.Column('best_overall', sa.String(100), default=''),
    )

    # Create llm_responses table
    op.create_table(
        'llm_responses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evaluation_id', sa.String(36), sa.ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('response', sa.Text(), default=''),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Float(), default=0.0),
        sa.Column('tokens_per_second', sa.Float(), default=0.0),
        sa.Column('input_tokens', sa.Integer(), default=0),
        sa.Column('output_tokens', sa.Integer(), default=0),
        sa.Column('estimated_cost', sa.Float(), default=0.0),
        sa.Column('coherence_score', sa.Float(), default=0.0),
        sa.Column('relevance_score', sa.Float(), default=0.0),
        sa.Column('quality_score', sa.Float(), default=0.0),
    )


def downgrade() -> None:
    op.drop_table('llm_responses')
    op.drop_table('evaluations')
    op.drop_table('llm_models')
