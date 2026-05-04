"""project_type, published_version_id, prediction.per_field_evidence

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('projects') as batch:
        batch.add_column(
            sa.Column(
                'project_type',
                sa.String(length=32),
                nullable=False,
                server_default='extraction',
            )
        )
        batch.add_column(sa.Column('published_version_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('predictions') as batch:
        # Field-level evidence: page / quote / rationale only. No bbox / coordinates.
        batch.add_column(sa.Column('per_field_evidence', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('predictions') as batch:
        batch.drop_column('per_field_evidence')
    with op.batch_alter_table('projects') as batch:
        batch.drop_column('published_version_id')
        batch.drop_column('project_type')
