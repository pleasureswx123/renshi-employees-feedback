"""保留正式计分中间精度，不在结果持久化时强制四位小数。"""

import sqlalchemy as sa
from alembic import op

revision = '20260903_08_feedback_scoring'
down_revision = '20260902_07_feedback_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ('score', 'effective_weight'):
        op.alter_column('fb_score_result', name, existing_type=sa.Numeric(12, 4), type_=sa.Numeric())


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text('LOCK TABLE fb_score_result IN ACCESS EXCLUSIVE MODE'))
    loses_precision = bind.execute(
        sa.text(
            'SELECT EXISTS (SELECT 1 FROM fb_score_result '
            'WHERE score <> round(score, 4) OR effective_weight <> round(effective_weight, 4))'
        )
    ).scalar_one()
    if loses_precision:
        raise RuntimeError('正式结果含超过四位小数的计算依据，拒绝损失精度的降级')
    for name in ('score', 'effective_weight'):
        op.alter_column('fb_score_result', name, existing_type=sa.Numeric(), type_=sa.Numeric(12, 4))
