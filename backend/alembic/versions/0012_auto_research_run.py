"""auto_research_run table

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'auto_research_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('starting_version_id', sa.Integer(), nullable=True),
        sa.Column('output_version_id', sa.Integer(), nullable=True),
        sa.Column('judge_model_id', sa.String(length=128), nullable=False),
        sa.Column('researcher_model_id', sa.String(length=128), nullable=False),
        sa.Column('turn_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_turn', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('turn_history', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('termination_reason', sa.String(length=64), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running','completed','failed','early_stopped','manual_stopped')",
            name='ck_auto_research_status',
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['starting_version_id'], ['project_versions.id']),
        sa.ForeignKeyConstraint(['output_version_id'], ['project_versions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_auto_research_runs_project_id'),
        'auto_research_runs',
        ['project_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_auto_research_runs_project_id'), table_name='auto_research_runs')
    op.drop_table('auto_research_runs')
