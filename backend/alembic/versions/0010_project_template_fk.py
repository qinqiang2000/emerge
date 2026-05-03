"""project template fk

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-03
"""
from alembic import op


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('projects') as batch_op:
        batch_op.create_foreign_key(
            'fk_projects_template_id',
            'templates',
            ['template_id'],
            ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_constraint('fk_projects_template_id', type_='foreignkey')
