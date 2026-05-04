"""make api_code globally unique

Drops the per-workspace UniqueConstraint(workspace_id, api_code) and replaces
it with a global UniqueConstraint(api_code). The public route /extract/{api_code}
has no workspace context (spec §7.1), so two workspaces publishing the same
code would be ambiguous.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-04
"""
from alembic import op


revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('projects') as batch:
        batch.drop_constraint('uq_project_workspace_api_code', type_='unique')
        batch.create_unique_constraint('uq_project_api_code', ['api_code'])


def downgrade() -> None:
    with op.batch_alter_table('projects') as batch:
        batch.drop_constraint('uq_project_api_code', type_='unique')
        batch.create_unique_constraint(
            'uq_project_workspace_api_code', ['workspace_id', 'api_code']
        )
