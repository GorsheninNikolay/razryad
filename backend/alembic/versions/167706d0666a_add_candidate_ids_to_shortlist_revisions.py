"""Add candidate_ids to shortlist_revisions

Revision ID: 167706d0666a
Revises: e8bbacc53c71

Колонка появилась в модели ShortlistRevision на этапе ревизий подборки
(ТЗ 2.1: уточнение запроса не должно терять ранее полученную подборку),
но миграция для неё создана не была. Из-за расхождения модели и схемы
создание ревизии падало на реальной базе с
"table shortlist_revisions has no column named candidate_ids".
Тесты этого не видели: они создают схему из моделей, а не из миграций.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '167706d0666a'
down_revision: Union[str, None] = 'e8bbacc53c71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # nullable: существующие ревизии не имеют зафиксированного состава
    with op.batch_alter_table('shortlist_revisions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('candidate_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('shortlist_revisions', schema=None) as batch_op:
        batch_op.drop_column('candidate_ids')
