"""建立评价领域骨架和首期业务表。

Revision ID: 20260902_02_feedback_domain
Revises: 20260902_01_feedback_baseline
Create Date: 2026-09-02 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260902_02_feedback_domain'
down_revision: str | Sequence[str] | None = '20260902_01_feedback_baseline'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column]:
    """返回配置类表统一使用的审计字段。"""
    return [
        sa.Column('create_by', sa.String(length=64), server_default=sa.text("''"), nullable=False, comment='创建者'),
        sa.Column(
            'create_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column('update_by', sa.String(length=64), server_default=sa.text("''"), nullable=False, comment='更新者'),
        sa.Column(
            'update_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='更新时间',
        ),
        sa.Column('remark', sa.String(length=500), nullable=True, comment='备注'),
    ]


def upgrade() -> None:
    """创建首期评价业务表、约束、索引和中文注释。"""
    op.create_table(
        'fb_project',
        sa.Column('project_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='评价项目ID'),
        sa.Column('project_name', sa.String(length=200), nullable=False, comment='评价项目名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='评价项目说明'),
        sa.Column(
            'status',
            sa.String(length=20),
            server_default=sa.text("'PREPARING'"),
            nullable=False,
            comment='项目状态',
        ),
        sa.Column('owner_user_id', sa.BigInteger(), nullable=False, comment='项目负责人用户ID'),
        sa.Column('owner_dept_id', sa.BigInteger(), nullable=True, comment='项目归属部门ID'),
        sa.Column('current_questionnaire_version_id', sa.BigInteger(), nullable=True, comment='当前问卷版本ID'),
        sa.Column('published_by', sa.BigInteger(), nullable=True, comment='发布人用户ID'),
        sa.Column('published_time', sa.DateTime(), nullable=True, comment='发布时间'),
        sa.Column('completed_by', sa.BigInteger(), nullable=True, comment='完成人用户ID'),
        sa.Column('completed_time', sa.DateTime(), nullable=True, comment='完成时间'),
        sa.Column('completion_reason', sa.String(length=500), nullable=True, comment='手动完成原因'),
        sa.Column(
            'del_flag',
            sa.String(length=1),
            server_default=sa.text("'0'"),
            nullable=False,
            comment='删除标志（0存在 2删除）',
        ),
        sa.Column('lock_version', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='乐观锁版本'),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('PREPARING', 'ACTIVE', 'COMPLETED')", name='ck_fb_project_status'),
        sa.CheckConstraint("del_flag IN ('0', '2')", name='ck_fb_project_del_flag'),
        sa.CheckConstraint('lock_version >= 0', name='ck_fb_project_lock_version'),
        sa.CheckConstraint(
            "status = 'PREPARING' OR "
            '(current_questionnaire_version_id IS NOT NULL '
            'AND published_by IS NOT NULL AND published_time IS NOT NULL)',
            name='ck_fb_project_published_fields',
        ),
        sa.CheckConstraint(
            "status <> 'COMPLETED' OR (completed_by IS NOT NULL AND completed_time IS NOT NULL)",
            name='ck_fb_project_completed_fields',
        ),
        sa.ForeignKeyConstraint(
            ['owner_user_id'], ['sys_user.user_id'], name='fk_fb_project_owner_user', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['owner_dept_id'], ['sys_dept.dept_id'], name='fk_fb_project_owner_dept', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['published_by'], ['sys_user.user_id'], name='fk_fb_project_published_user', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['completed_by'], ['sys_user.user_id'], name='fk_fb_project_completed_user', ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('project_id', name='pk_fb_project'),
        comment='评价项目表',
    )
    op.create_index('ix_fb_project_status_create_time', 'fb_project', ['status', 'create_time'])
    op.create_index('ix_fb_project_owner_user_dept', 'fb_project', ['owner_user_id', 'owner_dept_id'])

    op.create_table(
        'fb_questionnaire_version',
        sa.Column('version_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='问卷版本ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_no', sa.Integer(), nullable=False, comment='项目内版本号'),
        sa.Column(
            'status',
            sa.String(length=20),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
            comment='问卷版本状态',
        ),
        sa.Column('title', sa.String(length=200), nullable=False, comment='问卷标题'),
        sa.Column('description', sa.Text(), nullable=True, comment='问卷说明'),
        sa.Column(
            'settings',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment='问卷全局设置',
        ),
        sa.Column(
            'scoring_rule_snapshot',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment='计分规则快照',
        ),
        sa.Column('frozen_by', sa.BigInteger(), nullable=True, comment='冻结人用户ID'),
        sa.Column('frozen_time', sa.DateTime(), nullable=True, comment='冻结时间'),
        sa.Column('lock_version', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='乐观锁版本'),
        *_audit_columns(),
        sa.CheckConstraint('version_no > 0', name='ck_fb_questionnaire_version_no'),
        sa.CheckConstraint("status IN ('DRAFT', 'FROZEN')", name='ck_fb_questionnaire_version_status'),
        sa.CheckConstraint('lock_version >= 0', name='ck_fb_questionnaire_version_lock'),
        sa.CheckConstraint(
            "status <> 'FROZEN' OR (frozen_by IS NOT NULL AND frozen_time IS NOT NULL)",
            name='ck_fb_questionnaire_version_frozen',
        ),
        sa.ForeignKeyConstraint(
            ['project_id'], ['fb_project.project_id'], name='fk_fb_questionnaire_version_project', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['frozen_by'], ['sys_user.user_id'], name='fk_fb_questionnaire_version_frozen_user', ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('version_id', name='pk_fb_questionnaire_version'),
        sa.UniqueConstraint('project_id', 'version_no', name='uq_fb_questionnaire_version_project_no'),
        sa.UniqueConstraint('project_id', 'version_id', name='uq_fb_questionnaire_version_project_id'),
        comment='问卷版本表',
    )
    op.create_index(
        'uq_fb_questionnaire_version_draft',
        'fb_questionnaire_version',
        ['project_id'],
        unique=True,
        postgresql_where=sa.text("status = 'DRAFT'"),
    )
    op.create_foreign_key(
        'fk_fb_project_current_version',
        'fb_project',
        'fb_questionnaire_version',
        ['current_questionnaire_version_id'],
        ['version_id'],
        ondelete='RESTRICT',
    )

    op.create_table(
        'fb_questionnaire_page',
        sa.Column('page_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='问卷页面ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('page_title', sa.String(length=200), nullable=False, comment='页面标题'),
        sa.Column('page_description', sa.Text(), nullable=True, comment='页面说明'),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='页面顺序'),
        *_audit_columns(),
        sa.CheckConstraint('sort_order > 0', name='ck_fb_questionnaire_page_sort'),
        sa.ForeignKeyConstraint(
            ['version_id'],
            ['fb_questionnaire_version.version_id'],
            name='fk_fb_questionnaire_page_version',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('page_id', name='pk_fb_questionnaire_page'),
        sa.UniqueConstraint('version_id', 'sort_order', name='uq_fb_questionnaire_page_version_sort'),
        sa.UniqueConstraint('version_id', 'page_id', name='uq_fb_questionnaire_page_version_id'),
        comment='问卷页面表',
    )

    op.create_table(
        'fb_question',
        sa.Column('question_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='题目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('page_id', sa.BigInteger(), nullable=False, comment='问卷页面ID'),
        sa.Column('question_code', sa.String(length=64), nullable=False, comment='版本内稳定题目标识'),
        sa.Column('question_type', sa.String(length=30), nullable=False, comment='题型'),
        sa.Column('title', sa.Text(), nullable=False, comment='题目标题'),
        sa.Column('description', sa.Text(), nullable=True, comment='题目说明'),
        sa.Column('is_required', sa.Boolean(), server_default=sa.text('false'), nullable=False, comment='是否必答'),
        sa.Column('is_scored', sa.Boolean(), server_default=sa.text('true'), nullable=False, comment='是否参与计分'),
        sa.Column('min_score', sa.Numeric(precision=12, scale=4), nullable=True, comment='最低分'),
        sa.Column('max_score', sa.Numeric(precision=12, scale=4), nullable=True, comment='最高分'),
        sa.Column(
            'decimal_places', sa.SmallInteger(), server_default=sa.text('0'), nullable=False, comment='允许小数位数'
        ),
        sa.Column(
            'config',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment='题型特有配置',
        ),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='页内题目顺序'),
        *_audit_columns(),
        sa.CheckConstraint(
            "question_type IN ('SINGLE_CHOICE', 'STAR_RATING', 'NUMERIC_INPUT', 'SLIDER', 'TEXT')",
            name='ck_fb_question_type',
        ),
        sa.CheckConstraint('sort_order > 0', name='ck_fb_question_sort'),
        sa.CheckConstraint('decimal_places BETWEEN 0 AND 4', name='ck_fb_question_decimal_places'),
        sa.CheckConstraint("question_type <> 'TEXT' OR is_scored = false", name='ck_fb_question_text_not_scored'),
        sa.CheckConstraint(
            "(question_type IN ('STAR_RATING', 'NUMERIC_INPUT', 'SLIDER') "
            'AND min_score IS NOT NULL AND max_score IS NOT NULL AND max_score > min_score) '
            "OR (question_type NOT IN ('STAR_RATING', 'NUMERIC_INPUT', 'SLIDER') "
            'AND min_score IS NULL AND max_score IS NULL)',
            name='ck_fb_question_score_range',
        ),
        sa.ForeignKeyConstraint(
            ['version_id', 'page_id'],
            ['fb_questionnaire_page.version_id', 'fb_questionnaire_page.page_id'],
            name='fk_fb_question_page_version',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('question_id', name='pk_fb_question'),
        sa.UniqueConstraint('version_id', 'question_code', name='uq_fb_question_version_code'),
        sa.UniqueConstraint('page_id', 'sort_order', name='uq_fb_question_page_sort'),
        sa.UniqueConstraint('version_id', 'question_id', name='uq_fb_question_version_id'),
        comment='问卷题目表',
    )
    op.create_index('ix_fb_question_version_type', 'fb_question', ['version_id', 'question_type'])

    op.create_table(
        'fb_question_option',
        sa.Column('option_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='题目选项ID'),
        sa.Column('question_id', sa.BigInteger(), nullable=False, comment='题目ID'),
        sa.Column('option_code', sa.String(length=64), nullable=False, comment='题目内稳定选项标识'),
        sa.Column('option_label', sa.String(length=500), nullable=False, comment='选项文本'),
        sa.Column(
            'score',
            sa.Numeric(precision=12, scale=4),
            server_default=sa.text('0'),
            nullable=False,
            comment='选项原始分',
        ),
        sa.Column(
            'requires_reason', sa.Boolean(), server_default=sa.text('false'), nullable=False, comment='是否要求附加原因'
        ),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='选项顺序'),
        *_audit_columns(),
        sa.CheckConstraint('sort_order > 0', name='ck_fb_question_option_sort'),
        sa.ForeignKeyConstraint(
            ['question_id'], ['fb_question.question_id'], name='fk_fb_question_option_question', ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('option_id', name='pk_fb_question_option'),
        sa.UniqueConstraint('question_id', 'option_code', name='uq_fb_question_option_question_code'),
        sa.UniqueConstraint('question_id', 'sort_order', name='uq_fb_question_option_question_sort'),
        sa.UniqueConstraint('question_id', 'option_id', name='uq_fb_question_option_question_id'),
        comment='题目选项表',
    )

    op.create_table(
        'fb_indicator',
        sa.Column('indicator_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='指标ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('indicator_code', sa.String(length=64), nullable=False, comment='版本内稳定指标标识'),
        sa.Column('indicator_name', sa.String(length=100), nullable=False, comment='指标名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='指标说明'),
        sa.Column('weight', sa.Numeric(precision=12, scale=4), nullable=False, comment='指标权重百分比'),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='指标顺序'),
        *_audit_columns(),
        sa.CheckConstraint('weight >= 0 AND weight <= 100', name='ck_fb_indicator_weight'),
        sa.CheckConstraint('sort_order > 0', name='ck_fb_indicator_sort'),
        sa.ForeignKeyConstraint(
            ['version_id'], ['fb_questionnaire_version.version_id'], name='fk_fb_indicator_version', ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('indicator_id', name='pk_fb_indicator'),
        sa.UniqueConstraint('version_id', 'indicator_code', name='uq_fb_indicator_version_code'),
        sa.UniqueConstraint('version_id', 'indicator_name', name='uq_fb_indicator_version_name'),
        sa.UniqueConstraint('version_id', 'sort_order', name='uq_fb_indicator_version_sort'),
        sa.UniqueConstraint('version_id', 'indicator_id', name='uq_fb_indicator_version_id'),
        comment='评价指标表',
    )

    op.create_table(
        'fb_indicator_question',
        sa.Column('binding_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='指标题目绑定ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('indicator_id', sa.BigInteger(), nullable=False, comment='指标ID'),
        sa.Column('question_id', sa.BigInteger(), nullable=False, comment='题目ID'),
        sa.ForeignKeyConstraint(
            ['version_id', 'indicator_id'],
            ['fb_indicator.version_id', 'fb_indicator.indicator_id'],
            name='fk_fb_indicator_question_indicator',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['version_id', 'question_id'],
            ['fb_question.version_id', 'fb_question.question_id'],
            name='fk_fb_indicator_question_question',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('binding_id', name='pk_fb_indicator_question'),
        sa.UniqueConstraint('question_id', name='uq_fb_indicator_question_question'),
        comment='指标题目绑定表',
    )

    op.create_table(
        'fb_relation',
        sa.Column('relation_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='评价关系ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('relation_code', sa.String(length=64), nullable=False, comment='版本内稳定关系标识'),
        sa.Column('relation_type', sa.String(length=20), nullable=False, comment='评价关系类型'),
        sa.Column('relation_name', sa.String(length=100), nullable=False, comment='评价关系名称'),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False, comment='是否启用'),
        sa.Column(
            'participates_in_score',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
            comment='是否参与综合计分',
        ),
        sa.Column(
            'weight',
            sa.Numeric(precision=12, scale=4),
            server_default=sa.text('0'),
            nullable=False,
            comment='关系配置权重百分比',
        ),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='关系顺序'),
        *_audit_columns(),
        sa.CheckConstraint(
            "relation_type IN ('SUPERVISOR', 'PEER', 'SUBORDINATE', 'SELF', 'OTHER', 'CUSTOM')",
            name='ck_fb_relation_type',
        ),
        sa.CheckConstraint('weight >= 0 AND weight <= 100', name='ck_fb_relation_weight'),
        sa.CheckConstraint('sort_order > 0', name='ck_fb_relation_sort'),
        sa.CheckConstraint("relation_type <> 'SELF' OR weight = 0", name='ck_fb_relation_self_weight'),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id'],
            ['fb_questionnaire_version.project_id', 'fb_questionnaire_version.version_id'],
            name='fk_fb_relation_project_version',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('relation_id', name='pk_fb_relation'),
        sa.UniqueConstraint('version_id', 'relation_code', name='uq_fb_relation_version_code'),
        sa.UniqueConstraint('version_id', 'relation_name', name='uq_fb_relation_version_name'),
        sa.UniqueConstraint('version_id', 'sort_order', name='uq_fb_relation_version_sort'),
        sa.UniqueConstraint('project_id', 'version_id', 'relation_id', name='uq_fb_relation_project_version_id'),
        comment='项目评价关系表',
    )

    op.create_table(
        'fb_project_target',
        sa.Column('target_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='项目被评价人记录ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('target_user_id', sa.BigInteger(), nullable=False, comment='被评价人用户ID'),
        sa.Column('target_user_name', sa.String(length=100), nullable=False, comment='被评价人姓名快照'),
        sa.Column('target_dept_id', sa.BigInteger(), nullable=True, comment='被评价人部门ID快照'),
        sa.Column('target_dept_name', sa.String(length=100), nullable=True, comment='被评价人部门名称快照'),
        sa.Column(
            'only_self_evaluation',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
            comment='发布时是否仅配置自评',
        ),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['project_id'], ['fb_project.project_id'], name='fk_fb_project_target_project', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id'],
            ['fb_questionnaire_version.project_id', 'fb_questionnaire_version.version_id'],
            name='fk_fb_project_target_project_version',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['target_user_id'], ['sys_user.user_id'], name='fk_fb_project_target_user', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['target_dept_id'], ['sys_dept.dept_id'], name='fk_fb_project_target_dept', ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('target_id', name='pk_fb_project_target'),
        sa.UniqueConstraint('project_id', 'target_user_id', name='uq_fb_project_target_project_user'),
        sa.UniqueConstraint(
            'project_id',
            'version_id',
            'target_user_id',
            'target_id',
            name='uq_fb_project_target_assignment_ref',
        ),
        comment='项目被评价人快照表',
    )
    op.create_index('ix_fb_project_target_dept', 'fb_project_target', ['project_id', 'target_dept_id'])

    op.create_table(
        'fb_assignment',
        sa.Column('assignment_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='评价任务ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('evaluator_user_id', sa.BigInteger(), nullable=False, comment='评价人用户ID'),
        sa.Column('evaluator_user_name', sa.String(length=100), nullable=False, comment='评价人姓名快照'),
        sa.Column('evaluator_dept_id', sa.BigInteger(), nullable=True, comment='评价人部门ID快照'),
        sa.Column('evaluator_dept_name', sa.String(length=100), nullable=True, comment='评价人部门名称快照'),
        sa.Column('target_id', sa.BigInteger(), nullable=False, comment='项目被评价人记录ID'),
        sa.Column('target_user_id', sa.BigInteger(), nullable=False, comment='被评价人用户ID'),
        sa.Column('relation_id', sa.BigInteger(), nullable=False, comment='评价关系ID'),
        sa.Column(
            'status',
            sa.String(length=20),
            server_default=sa.text("'PENDING'"),
            nullable=False,
            comment='评价任务状态',
        ),
        sa.Column('saved_time', sa.DateTime(), nullable=True, comment='最近暂存时间'),
        sa.Column('submitted_time', sa.DateTime(), nullable=True, comment='正式提交时间'),
        sa.Column('closed_time', sa.DateTime(), nullable=True, comment='关闭未完成时间'),
        sa.Column('lock_version', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='乐观锁版本'),
        sa.Column(
            'create_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'update_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='更新时间',
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'DRAFT', 'SUBMITTED', 'CLOSED_INCOMPLETE')",
            name='ck_fb_assignment_status',
        ),
        sa.CheckConstraint('lock_version >= 0', name='ck_fb_assignment_lock_version'),
        sa.CheckConstraint("status <> 'DRAFT' OR saved_time IS NOT NULL", name='ck_fb_assignment_draft_time'),
        sa.CheckConstraint(
            "status <> 'SUBMITTED' OR submitted_time IS NOT NULL", name='ck_fb_assignment_submitted_time'
        ),
        sa.CheckConstraint(
            "status <> 'CLOSED_INCOMPLETE' OR closed_time IS NOT NULL", name='ck_fb_assignment_closed_time'
        ),
        sa.ForeignKeyConstraint(
            ['project_id'], ['fb_project.project_id'], name='fk_fb_assignment_project', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['evaluator_user_id'], ['sys_user.user_id'], name='fk_fb_assignment_evaluator_user', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['evaluator_dept_id'], ['sys_dept.dept_id'], name='fk_fb_assignment_evaluator_dept', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['target_user_id'], ['sys_user.user_id'], name='fk_fb_assignment_target_user', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id', 'relation_id'],
            ['fb_relation.project_id', 'fb_relation.version_id', 'fb_relation.relation_id'],
            name='fk_fb_assignment_relation',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id', 'target_user_id', 'target_id'],
            [
                'fb_project_target.project_id',
                'fb_project_target.version_id',
                'fb_project_target.target_user_id',
                'fb_project_target.target_id',
            ],
            name='fk_fb_assignment_target',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('assignment_id', name='pk_fb_assignment'),
        sa.UniqueConstraint(
            'project_id',
            'evaluator_user_id',
            'target_user_id',
            'relation_id',
            name='uq_fb_assignment_business_key',
        ),
        sa.UniqueConstraint('assignment_id', 'project_id', 'version_id', name='uq_fb_assignment_sheet_ref'),
        comment='评价任务表',
    )
    op.create_index('ix_fb_assignment_evaluator_status', 'fb_assignment', ['evaluator_user_id', 'status'])
    op.create_index('ix_fb_assignment_target_status', 'fb_assignment', ['target_user_id', 'status'])
    op.create_index('ix_fb_assignment_project_status', 'fb_assignment', ['project_id', 'status'])

    op.create_table(
        'fb_answer_sheet',
        sa.Column('sheet_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='答卷ID'),
        sa.Column('assignment_id', sa.BigInteger(), nullable=False, comment='评价任务ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column(
            'status', sa.String(length=20), server_default=sa.text("'DRAFT'"), nullable=False, comment='答卷状态'
        ),
        sa.Column('last_page_id', sa.BigInteger(), nullable=True, comment='最近填写页面ID'),
        sa.Column(
            'answered_count', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='已作答题目数量'
        ),
        sa.Column('raw_total_score', sa.Numeric(precision=12, scale=4), nullable=True, comment='答卷原始总分'),
        sa.Column(
            'submission_snapshot',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment='提交时校验与计分输入快照',
        ),
        sa.Column(
            'saved_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='最近保存时间',
        ),
        sa.Column('submitted_time', sa.DateTime(), nullable=True, comment='正式提交时间'),
        sa.Column('lock_version', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='乐观锁版本'),
        sa.Column(
            'create_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'update_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='更新时间',
        ),
        sa.CheckConstraint("status IN ('DRAFT', 'SUBMITTED')", name='ck_fb_answer_sheet_status'),
        sa.CheckConstraint('answered_count >= 0', name='ck_fb_answer_sheet_answered_count'),
        sa.CheckConstraint('lock_version >= 0', name='ck_fb_answer_sheet_lock_version'),
        sa.CheckConstraint(
            "status <> 'SUBMITTED' OR submitted_time IS NOT NULL", name='ck_fb_answer_sheet_submitted_time'
        ),
        sa.ForeignKeyConstraint(
            ['assignment_id', 'project_id', 'version_id'],
            ['fb_assignment.assignment_id', 'fb_assignment.project_id', 'fb_assignment.version_id'],
            name='fk_fb_answer_sheet_assignment',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['last_page_id'],
            ['fb_questionnaire_page.page_id'],
            name='fk_fb_answer_sheet_last_page',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('sheet_id', name='pk_fb_answer_sheet'),
        sa.UniqueConstraint('assignment_id', name='uq_fb_answer_sheet_assignment'),
        sa.UniqueConstraint('sheet_id', 'version_id', name='uq_fb_answer_sheet_version_ref'),
        comment='评价答卷表',
    )
    op.create_index('ix_fb_answer_sheet_project_submitted', 'fb_answer_sheet', ['project_id', 'submitted_time'])

    op.create_table(
        'fb_answer',
        sa.Column('answer_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='单题答案ID'),
        sa.Column('sheet_id', sa.BigInteger(), nullable=False, comment='答卷ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('question_id', sa.BigInteger(), nullable=False, comment='题目ID'),
        sa.Column('answer_type', sa.String(length=20), nullable=False, comment='答案值类型'),
        sa.Column('option_id', sa.BigInteger(), nullable=True, comment='所选选项ID'),
        sa.Column('numeric_value', sa.Numeric(precision=12, scale=4), nullable=True, comment='数值答案'),
        sa.Column('text_value', sa.Text(), nullable=True, comment='文本答案'),
        sa.Column('reason', sa.Text(), nullable=True, comment='选项附加原因'),
        sa.Column('raw_score', sa.Numeric(precision=12, scale=4), nullable=True, comment='题目原始得分'),
        sa.Column(
            'value_snapshot',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment='答案展示值快照',
        ),
        sa.Column(
            'create_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'update_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='更新时间',
        ),
        sa.CheckConstraint("answer_type IN ('OPTION', 'NUMERIC', 'TEXT')", name='ck_fb_answer_type'),
        sa.CheckConstraint(
            "(answer_type = 'OPTION' AND option_id IS NOT NULL AND numeric_value IS NULL AND text_value IS NULL) OR "
            "(answer_type = 'NUMERIC' AND option_id IS NULL AND numeric_value IS NOT NULL AND text_value IS NULL) OR "
            "(answer_type = 'TEXT' AND option_id IS NULL AND numeric_value IS NULL AND text_value IS NOT NULL)",
            name='ck_fb_answer_value_channel',
        ),
        sa.ForeignKeyConstraint(
            ['sheet_id', 'version_id'],
            ['fb_answer_sheet.sheet_id', 'fb_answer_sheet.version_id'],
            name='fk_fb_answer_sheet_version',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['version_id', 'question_id'],
            ['fb_question.version_id', 'fb_question.question_id'],
            name='fk_fb_answer_question_version',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['question_id', 'option_id'],
            ['fb_question_option.question_id', 'fb_question_option.option_id'],
            name='fk_fb_answer_question_option',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('answer_id', name='pk_fb_answer'),
        sa.UniqueConstraint('sheet_id', 'question_id', name='uq_fb_answer_sheet_question'),
        comment='评价单题答案表',
    )
    op.create_index('ix_fb_answer_sheet', 'fb_answer', ['sheet_id'])

    op.create_table(
        'fb_score_result',
        sa.Column('result_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='计分结果ID'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='评价项目ID'),
        sa.Column('version_id', sa.BigInteger(), nullable=False, comment='问卷版本ID'),
        sa.Column('target_id', sa.BigInteger(), nullable=False, comment='项目被评价人记录ID'),
        sa.Column('target_user_id', sa.BigInteger(), nullable=False, comment='被评价人用户ID'),
        sa.Column('result_type', sa.String(length=30), nullable=False, comment='计分结果类型'),
        sa.Column('indicator_id', sa.BigInteger(), nullable=True, comment='指标ID'),
        sa.Column('relation_id', sa.BigInteger(), nullable=True, comment='评价关系ID'),
        sa.Column('score', sa.Numeric(precision=12, scale=4), nullable=True, comment='百分制得分；数据不足时为空'),
        sa.Column(
            'original_weight', sa.Numeric(precision=12, scale=4), nullable=True, comment='发布快照中的原配置权重'
        ),
        sa.Column('effective_weight', sa.Numeric(precision=12, scale=4), nullable=True, comment='实际参与计算权重'),
        sa.Column('expected_count', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='应完成任务数'),
        sa.Column('submitted_count', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='已提交任务数'),
        sa.Column(
            'has_missing_data',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
            comment='是否存在缺失数据',
        ),
        sa.Column('calculation_version', sa.String(length=32), nullable=False, comment='计分规则版本'),
        sa.Column(
            'calculation_basis',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment='可复算的计分输入与过程依据',
        ),
        sa.Column(
            'calculated_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='计算时间',
        ),
        sa.Column(
            'create_time',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='创建时间',
        ),
        sa.CheckConstraint(
            "result_type IN ('INDICATOR_RELATION', 'INDICATOR_COMPOSITE', 'PERSON_TOTAL', 'COVERAGE')",
            name='ck_fb_score_result_type',
        ),
        sa.CheckConstraint('score IS NULL OR (score >= 0 AND score <= 100)', name='ck_fb_score_result_score'),
        sa.CheckConstraint(
            'original_weight IS NULL OR (original_weight >= 0 AND original_weight <= 100)',
            name='ck_fb_score_result_original_weight',
        ),
        sa.CheckConstraint(
            'effective_weight IS NULL OR (effective_weight >= 0 AND effective_weight <= 100)',
            name='ck_fb_score_result_effective_weight',
        ),
        sa.CheckConstraint(
            'expected_count >= 0 AND submitted_count >= 0 AND submitted_count <= expected_count',
            name='ck_fb_score_result_counts',
        ),
        sa.CheckConstraint(
            "(result_type = 'INDICATOR_RELATION' AND indicator_id IS NOT NULL AND relation_id IS NOT NULL) OR "
            "(result_type = 'INDICATOR_COMPOSITE' AND indicator_id IS NOT NULL AND relation_id IS NULL) OR "
            "(result_type IN ('PERSON_TOTAL', 'COVERAGE') AND indicator_id IS NULL AND relation_id IS NULL)",
            name='ck_fb_score_result_dimensions',
        ),
        sa.ForeignKeyConstraint(
            ['project_id'], ['fb_project.project_id'], name='fk_fb_score_result_project', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['target_user_id'], ['sys_user.user_id'], name='fk_fb_score_result_target_user', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id', 'target_user_id', 'target_id'],
            [
                'fb_project_target.project_id',
                'fb_project_target.version_id',
                'fb_project_target.target_user_id',
                'fb_project_target.target_id',
            ],
            name='fk_fb_score_result_target',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['version_id', 'indicator_id'],
            ['fb_indicator.version_id', 'fb_indicator.indicator_id'],
            name='fk_fb_score_result_indicator',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['project_id', 'version_id', 'relation_id'],
            ['fb_relation.project_id', 'fb_relation.version_id', 'fb_relation.relation_id'],
            name='fk_fb_score_result_relation',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('result_id', name='pk_fb_score_result'),
        comment='评价计分结果表',
    )
    op.create_index('ix_fb_score_result_project_target', 'fb_score_result', ['project_id', 'target_user_id'])
    op.create_index(
        'uq_fb_score_indicator_relation',
        'fb_score_result',
        ['project_id', 'target_user_id', 'version_id', 'result_type', 'indicator_id', 'relation_id'],
        unique=True,
        postgresql_where=sa.text("result_type = 'INDICATOR_RELATION'"),
    )
    op.create_index(
        'uq_fb_score_indicator_composite',
        'fb_score_result',
        ['project_id', 'target_user_id', 'version_id', 'result_type', 'indicator_id'],
        unique=True,
        postgresql_where=sa.text("result_type = 'INDICATOR_COMPOSITE'"),
    )
    op.create_index(
        'uq_fb_score_person_result',
        'fb_score_result',
        ['project_id', 'target_user_id', 'version_id', 'result_type'],
        unique=True,
        postgresql_where=sa.text("result_type IN ('PERSON_TOTAL', 'COVERAGE')"),
    )


def downgrade() -> None:
    """删除P2评价业务表，保留RuoYi基线结构。"""
    op.drop_constraint('fk_fb_project_current_version', 'fb_project', type_='foreignkey')
    op.drop_table('fb_score_result')
    op.drop_table('fb_answer')
    op.drop_table('fb_answer_sheet')
    op.drop_table('fb_assignment')
    op.drop_table('fb_project_target')
    op.drop_table('fb_relation')
    op.drop_table('fb_indicator_question')
    op.drop_table('fb_indicator')
    op.drop_table('fb_question_option')
    op.drop_table('fb_question')
    op.drop_table('fb_questionnaire_page')
    op.drop_table('fb_questionnaire_version')
    op.drop_table('fb_project')
