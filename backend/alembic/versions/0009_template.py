"""template table

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('schema_json', sa.JSON(), nullable=False),
        sa.Column('global_notes', sa.Text(), nullable=False),
        sa.Column('recommended_model_id', sa.String(length=128), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('builtin', sa.Boolean(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'workspace_id', 'name', 'version',
            name='uq_template_workspace_name_version',
        ),
    )
    op.create_index(
        op.f('ix_templates_workspace_id'), 'templates', ['workspace_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_templates_workspace_id'), table_name='templates')
    op.drop_table('templates')
