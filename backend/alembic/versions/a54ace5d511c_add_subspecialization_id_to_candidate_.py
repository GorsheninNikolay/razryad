"""add_subspecialization_id_to_candidate_profile

Revision ID: a54ace5d511c
Revises: ad0a50cdae6f
Create Date: 2026-10-06 19:54:36.029016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a54ace5d511c'
down_revision: Union[str, None] = 'ad0a50cdae6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add subspecialization_id column to candidate_profiles (SQLite batch mode)
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subspecialization_id', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # Remove subspecialization_id column from candidate_profiles
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.drop_column('subspecialization_id')
