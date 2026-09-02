"""扩大答卷原始总分容量，保留单题精度与已有正式数据。"""

import sqlalchemy as sa
from alembic import op

revision = '20260902_05_feedback_answering'
down_revision = '20260902_04_feedback_publication'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'fb_answer_sheet',
        'raw_total_score',
        existing_type=sa.Numeric(12, 4),
        type_=sa.Numeric(18, 4),
        existing_nullable=True,
        existing_comment='答卷原始总分',
    )


def downgrade() -> None:
    connection = op.get_bind()
    # 同一事务先锁表，防止检查后又写入超过旧字段容量的正式总分。
    connection.execute(sa.text('LOCK TABLE fb_answer_sheet IN ACCESS EXCLUSIVE MODE'))
    overflowing = connection.scalar(
        sa.text('SELECT count(*) FROM fb_answer_sheet WHERE abs(raw_total_score) >= 100000000')
    )
    if overflowing:
        raise RuntimeError('存在超出旧字段容量的答卷总分，拒绝降级以保护正式数据')
    op.alter_column(
        'fb_answer_sheet',
        'raw_total_score',
        existing_type=sa.Numeric(18, 4),
        type_=sa.Numeric(12, 4),
        existing_nullable=True,
        existing_comment='答卷原始总分',
    )
