"""扩展完整问卷设计器的富文本说明和页面稳定标识。

Revision ID: 20260902_03_feedback_designer
Revises: 20260902_02_feedback_domain
Create Date: 2026-09-02 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260902_03_feedback_designer'
down_revision: str | Sequence[str] | None = '20260902_02_feedback_domain'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """增加问卷富文本JSON和页面业务标识。"""
    op.add_column(
        'fb_questionnaire_version',
        sa.Column(
            'description_doc',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='问卷富文本说明文档',
        ),
    )
    op.add_column(
        'fb_questionnaire_page',
        sa.Column('page_code', sa.String(length=64), nullable=True, comment='版本内稳定页面标识'),
    )
    op.execute(sa.text("UPDATE fb_questionnaire_page SET page_code = 'P_' || page_id::text WHERE page_code IS NULL"))
    op.alter_column('fb_questionnaire_page', 'page_code', existing_type=sa.String(length=64), nullable=False)
    op.create_unique_constraint(
        'uq_fb_questionnaire_page_version_code',
        'fb_questionnaire_page',
        ['version_id', 'page_code'],
    )


def downgrade() -> None:
    """移除P4增量字段，不影响既有问卷纯文本和页面内容。"""
    op.drop_constraint(
        'uq_fb_questionnaire_page_version_code',
        'fb_questionnaire_page',
        type_='unique',
    )
    op.drop_column('fb_questionnaire_page', 'page_code')
    op.drop_column('fb_questionnaire_version', 'description_doc')
