"""drop ix_documents_source (low selectivity)

Per gate review of commit ef5b13c: with only two distinct values
('lab', 'public_api') and 'lab' dominating cardinality, SQLite will
rarely pick this index. The write cost has no read benefit. The
project-id-only index already on `documents` covers the project-scoped
queries that include the source filter.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-06
"""
from alembic import op


revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.drop_index('ix_documents_source')


def downgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.create_index('ix_documents_source', ['source'])
