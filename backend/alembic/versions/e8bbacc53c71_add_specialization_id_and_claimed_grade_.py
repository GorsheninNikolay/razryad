"""Add specialization_id and claimed_grade to candidate_profile

Revision ID: e8bbacc53c71
Revises: ce9562014e8e
Create Date: 2026-10-06 00:29:55.242534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8bbacc53c71'
down_revision: Union[str, None] = 'ce9562014e8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add onboarding fields to candidate_profiles
    # Both nullable to support existing profiles without breaking data
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('specialization_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('claimed_grade', sa.String(20), nullable=True))
        batch_op.create_foreign_key(
            'fk_candidate_profiles_specialization_id_specializations',
            'specializations',
            ['specialization_id'], ['id']
        )


def downgrade() -> None:
    # Remove columns (batch mode for SQLite compatibility)
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.drop_constraint('fk_candidate_profiles_specialization_id_specializations', type_='foreignkey')
        batch_op.drop_column('claimed_grade')
        batch_op.drop_column('specialization_id')
