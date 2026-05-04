"""workspace_settings table

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'key', name='uq_workspace_setting_key'),
    )
    op.create_index(
        op.f('ix_workspace_settings_workspace_id'),
        'workspace_settings',
        ['workspace_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_workspace_settings_workspace_id'), table_name='workspace_settings')
    op.drop_table('workspace_settings')
