"""Add industry to candidate_profiles

Revision ID: ad0a50cdae6f
Revises: 167706d0666a

Поле industry добавлено в модель CandidateProfile для хранения отрасли
кандидата, но миграция не была создана. Модель и схема БД разошлись,
что привело к ошибкам при чтении профилей на реальной БД.
Тесты этого не поймали, потому что создают схему из моделей (Base.metadata.create_all),
а не из миграций.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad0a50cdae6f'
down_revision: Union[str, None] = '167706d0666a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: существующие профили не имеют отрасли
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('industry', sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.drop_column('industry')
