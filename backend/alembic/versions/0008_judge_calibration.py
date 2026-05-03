"""judge calibration table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-03 16:55:26.790186
"""
from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('judge_calibrations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('judge_model_version', sa.String(length=128), nullable=False),
    sa.Column('tp', sa.Integer(), nullable=False),
    sa.Column('fp', sa.Integer(), nullable=False),
    sa.Column('fn', sa.Integer(), nullable=False),
    sa.Column('tn', sa.Integer(), nullable=False),
    sa.Column('observation_count', sa.Integer(), nullable=False),
    sa.Column('last_updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'judge_model_version', name='uq_calibration_project_judge')
    )
    op.create_index(op.f('ix_judge_calibrations_project_id'), 'judge_calibrations', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_judge_calibrations_project_id'), table_name='judge_calibrations')
    op.drop_table('judge_calibrations')
