"""add documents.source ('lab' | 'public_api')

Workspace isolation: public-API extractions create a Document with
source='public_api' and must NOT appear in the editor's Documents list
or the vibe-check pool. Spec §7.1 separates Lab and integrator traffic.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.add_column(
            sa.Column(
                'source',
                sa.String(length=16),
                nullable=False,
                server_default='lab',
            )
        )
        batch.create_check_constraint(
            'ck_document_source', "source IN ('lab','public_api')"
        )
        batch.create_index('ix_documents_source', ['source'])


def downgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.drop_index('ix_documents_source')
        batch.drop_constraint('ck_document_source', type_='check')
        batch.drop_column('source')
