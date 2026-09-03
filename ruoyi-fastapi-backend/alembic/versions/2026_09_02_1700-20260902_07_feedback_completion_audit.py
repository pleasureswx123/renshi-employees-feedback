"""新增项目不可逆完成的同事务业务审计表。"""

import sqlalchemy as sa
from alembic import op

revision = '20260902_07_feedback_audit'
down_revision = '20260902_06_feedback_permissions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'fb_project_completion_audit',
        sa.Column('audit_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='项目完成审计ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='完成时冻结问卷版本ID'),
        sa.Column('result', sa.String(length=20), server_default='SUCCESS', nullable=False, comment='完成结果'),
        sa.Column('operator_user_id', sa.BigInteger(), nullable=False, comment='完成人用户ID'),
        sa.Column('operator_name', sa.String(length=64), nullable=False, comment='完成人账号快照'),
        sa.Column('request_id', sa.String(length=64), nullable=True, comment='请求ID'),
        sa.Column('trace_id', sa.String(length=64), nullable=True, comment='链路ID'),
        sa.Column('before_total_count', sa.Integer(), nullable=False, comment='完成前任务总数'),
        sa.Column('before_submitted_count', sa.Integer(), nullable=False, comment='完成前已提交任务数'),
        sa.Column('before_draft_count', sa.Integer(), nullable=False, comment='完成前已暂存任务数'),
        sa.Column('before_pending_count', sa.Integer(), nullable=False, comment='完成前未开始任务数'),
        sa.Column('before_closed_incomplete_count', sa.Integer(), nullable=False, comment='完成前已关闭未完成任务数'),
        sa.Column('closed_assignment_count', sa.Integer(), nullable=False, comment='本次关闭未完成任务数'),
        sa.Column('completion_reason', sa.String(length=500), nullable=False, comment='手动完成原因'),
        sa.Column('completed_time', sa.DateTime(), nullable=False, comment='项目完成时间'),
        sa.Column(
            'create_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='审计记录创建时间',
        ),
        sa.CheckConstraint("result = 'SUCCESS'", name='ck_fb_project_completion_audit_result'),
        sa.CheckConstraint(
            'before_total_count >= 0 '
            'AND before_submitted_count >= 0 '
            'AND before_draft_count >= 0 '
            'AND before_pending_count >= 0 '
            'AND before_closed_incomplete_count >= 0 '
            'AND closed_assignment_count >= 0',
            name='ck_fb_project_completion_audit_counts_nonnegative',
        ),
        sa.CheckConstraint(
            'before_total_count = before_submitted_count + before_draft_count '
            '+ before_pending_count + before_closed_incomplete_count',
            name='ck_fb_project_completion_audit_summary_identity',
        ),
        sa.CheckConstraint(
            'closed_assignment_count = before_draft_count + before_pending_count',
            name='ck_fb_project_completion_audit_closed_count',
        ),
        sa.ForeignKeyConstraint(
            ['project_id'],
            ['fb_project.project_id'],
            name='fk_fb_project_completion_audit_project',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id'],
            ['fb_questionnaire_version.project_id', 'fb_questionnaire_version.version_id'],
            name='fk_fb_project_completion_audit_project_version',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['operator_user_id'],
            ['sys_user.user_id'],
            name='fk_fb_project_completion_audit_operator_user',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('audit_id', name='pk_fb_project_completion_audit'),
        comment='项目完成业务审计表',
    )
    op.create_index(
        'uq_fb_project_completion_audit_success',
        'fb_project_completion_audit',
        ['project_id'],
        unique=True,
        postgresql_where=sa.text("result = 'SUCCESS'"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text('LOCK TABLE fb_project_completion_audit IN ACCESS EXCLUSIVE MODE'))
    audit_count = bind.execute(sa.text('SELECT count(*) FROM fb_project_completion_audit')).scalar_one()
    if audit_count:
        raise RuntimeError('fb_project_completion_audit已有完成审计，拒绝执行破坏性降级')

    op.drop_index('uq_fb_project_completion_audit_success', table_name='fb_project_completion_audit')
    op.drop_table('fb_project_completion_audit')
